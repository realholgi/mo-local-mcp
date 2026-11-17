from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.master_catalog import MASTERS_CATALOG
from mo_local_mcp.masters import list_cost_centers, list_currencies, list_payment_terms


def records(result):
    return [dict(zip(result["columns"], row)) for row in result["rows"]]


class MasterTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.path = root / "office.db"
        key_path = root / "test.key"
        key = b"master-test-key!"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA page_size=1024")
        db.executescript(r"""
            CREATE TABLE KOSTENSTELLE (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                Name VARCHAR COLLATE NOCASE,Beschreibung VARCHAR,Bemerkung VARCHAR,Buchungssperre BOOLEAN);
            INSERT INTO KOSTENSTELLE VALUES
                (10,1,'Alpha','Hauptstelle','Vollständige Notizen erhalten',1),
                (11,1,'Alpha','Zweigstelle',NULL,0),
                (12,1,'Sonderfall','Wörtliche %_\ Zeichen','Suchnadel in Notizen',9),
                (13,1,NULL,NULL,NULL,NULL),
                (99,2,'Alpha','Wörtliche %_\ Zeichen','Privat',1);
            CREATE TABLE ZAHLUNGSBEDINGUNG (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                Bezeichnung VARCHAR COLLATE NOCASE,Zahlungsart INTEGER,TageNetto INTEGER,
                ZBText VARCHAR,TageSkonto INTEGER,ProzentSkonto DOUBLE,NichtMahnen BOOLEAN,
                FakturaArt INTEGER,Bankkonto_id INTEGER,Gesperrt BOOLEAN,Standard BOOLEAN);
            INSERT INTO ZAHLUNGSBEDINGUNG VALUES
                (20,1,'Alpha',999,28,'Vorlage #ProzentSkonto# und vollständige Notizen',14,200.0,1,777,42,1,1),
                (21,1,'Alpha',4,14,'Andere Beschreibung',7,2.5,0,0,NULL,0,0),
                (22,1,'Sonderfall',NULL,NULL,'Wörtliche %_\ Zeichen',NULL,NULL,9,NULL,0,9,NULL),
                (23,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
                (99,2,'Alpha',4,30,'Wörtliche %_\ Zeichen',10,300.0,1,0,42,1,1);
            CREATE TABLE WAEHRUNG (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                ISOCode VARCHAR COLLATE NOCASE,Name VARCHAR COLLATE NOCASE,Zeichen VARCHAR,
                Faktor INTEGER,Kurs DOUBLE);
            INSERT INTO WAEHRUNG VALUES
                (30,1,'USD','Dollar','$',100,1.23456),
                (31,1,'USD','Dollar','$',1,0.005),
                (32,1,'ZZZ','Wörtliche %_\ Zeichen','~',1000,123.456),
                (33,1,NULL,NULL,NULL,NULL,NULL),
                (99,2,'USD','Wörtliche %_\ Zeichen','$',100,999.99);
        """)
        db.commit()
        db.close()
        plain = self.path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, "little"))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        self.path.write_bytes(encrypted)
        self.original_bytes = bytes(encrypted)
        self.database = OfficeDatabase(self.path, key_path)
        self.addCleanup(self.database.close)
        self.reader = BusinessReader(self.database)

    def test_company_scope_and_missing_company(self):
        for function in (list_cost_centers, list_payment_terms, list_currencies):
            with self.subTest(function=function.__name__):
                rows = records(function(self.reader, 1))
                self.assertEqual(len(rows), 4)
                self.assertEqual({row["Firma_id"] for row in rows}, {1})
                self.assertNotIn(99, [row["_rowid"] for row in rows])
                self.assertEqual([row["_rowid"] for row in records(function(self.reader, 2))], [99])
                empty = function(self.reader, 3)
                self.assertEqual(empty["rows"], [])
                self.assertIsNone(empty["next_offset"])

    def test_literal_search_does_not_expand_wildcards(self):
        for function, expected in ((list_cost_centers, 12), (list_payment_terms, 22), (list_currencies, 32)):
            for search in ("%", "_", "\\", "WöRTLICHE", str(expected)):
                with self.subTest(function=function.__name__, search=search):
                    self.assertEqual([row["_rowid"] for row in records(function(self.reader, 1, search))], [expected])
            self.assertEqual(function(self.reader, 1, "%' OR 1=1 --")["rows"], [])
        self.assertEqual(records(list_cost_centers(self.reader, 1, "suchnadel"))[0]["_rowid"], 12)
        self.assertEqual(records(list_currencies(self.reader, 1, "$"))[0]["ISOCode"], "USD")

    def test_stable_pagination_including_equal_names_and_nulls(self):
        for function in (list_cost_centers, list_payment_terms, list_currencies):
            with self.subTest(function=function.__name__):
                expected = records(function(self.reader, 1))
                actual, offset = [], 0
                while offset is not None:
                    page = function(self.reader, 1, limit=1, offset=offset)
                    actual.extend(records(page))
                    offset = page["next_offset"]
                self.assertEqual(actual, expected)
                self.assertEqual(function(self.reader, 1, offset=100)["rows"], [])

    def test_locked_rows_full_notes_and_unknown_boolean_values(self):
        cost = records(list_cost_centers(self.reader, 1, "10"))[0]
        self.assertEqual((cost["Buchungssperre"], cost["Buchungssperre_label"]), (1, "Gesperrt"))
        self.assertEqual(cost["Bemerkung"], "Vollständige Notizen erhalten")
        unknown_cost = records(list_cost_centers(self.reader, 1, "12"))[0]
        self.assertEqual((unknown_cost["Buchungssperre"], unknown_cost["Buchungssperre_label"]), (9, "Unbekannt"))
        term = records(list_payment_terms(self.reader, 1, "20"))[0]
        self.assertEqual((term["Gesperrt_label"], term["NichtMahnen_label"], term["Standard_label"]),
                         ("Gesperrt", "Nicht mahnen", "Ja"))
        self.assertEqual(term["ZBText"], "Vorlage #ProzentSkonto# und vollständige Notizen")
        self.assertEqual((term["Zahlungsart"], term["FakturaArt"], term["Bankkonto_id"]), (999, 777, 42))
        unknown = records(list_payment_terms(self.reader, 1, "22"))[0]
        self.assertEqual((unknown["NichtMahnen_label"], unknown["Gesperrt_label"], unknown["Standard_label"]),
                         ("Unbekannt", "Unbekannt", "Nicht angegeben"))
        unspecified = records(list_cost_centers(self.reader, 1, "13"))[0]
        self.assertIsNone(unspecified["Buchungssperre"])
        self.assertEqual(unspecified["Buchungssperre_label"], "Nicht angegeben")

    def test_discount_and_fx_values_are_raw_not_money(self):
        terms = list_payment_terms(self.reader, 1)
        by_id = {row["_rowid"]: row for row in records(terms)}
        self.assertEqual((by_id[20]["ProzentSkonto"], by_id[21]["ProzentSkonto"]), (200.0, 2.5))
        self.assertIsNone(by_id[22]["ProzentSkonto"])
        self.assertEqual((by_id[20]["TageNetto"], by_id[20]["TageSkonto"]), (28, 14))
        self.assertIn("nicht verifiziert", terms["units"]["ProzentSkonto"])
        currencies = list_currencies(self.reader, 1)
        by_id = {row["_rowid"]: row for row in records(currencies)}
        self.assertEqual((by_id[30]["Faktor"], by_id[30]["Kurs"]), (100, 1.23456))
        self.assertEqual((by_id[31]["Faktor"], by_id[31]["Kurs"]), (1, 0.005))
        self.assertEqual((by_id[32]["Faktor"], by_id[32]["Kurs"]), (1000, 123.456))
        self.assertIsNone(by_id[33]["Faktor"])
        self.assertIsNone(by_id[33]["Kurs"])
        self.assertNotIn("money", terms)
        self.assertNotIn("money", currencies)

    def test_readers_do_not_change_encrypted_source(self):
        for function in (list_cost_centers, list_payment_terms, list_currencies):
            function(self.reader, 1)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_invalid_company_and_page_arguments(self):
        for function in (list_cost_centers, list_payment_terms, list_currencies):
            for company_id in (True, 0, -1, "1"):
                with self.subTest(function=function.__name__, company_id=company_id):
                    with self.assertRaises(ValueError):
                        function(self.reader, company_id)
            with self.assertRaises(ValueError):
                function(self.reader, 1, offset=-1)
            with self.assertRaises(ValueError):
                function(self.reader, 1, limit=501)

    def test_currency_catalog_preserves_connect_mapping(self):
        self.assertEqual(MASTERS_CATALOG["WAEHRUNG"]["api_structures"], ["WaehrungListItem"])
        self.assertEqual(MASTERS_CATALOG["WAEHRUNG"]["api_fields"],
                         {"Name": "Name", "Isocode": "ISOCode", "Kurs": "Kurs"})
        for table in ("KOSTENSTELLE", "ZAHLUNGSBEDINGUNG"):
            self.assertNotIn("api_fields", MASTERS_CATALOG[table])
            self.assertIn("Aus dem Datenbankstand abgeleitet", MASTERS_CATALOG[table]["mapping_basis"])
