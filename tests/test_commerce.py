"""Synthetische Lesetests für Einkauf, Artikel und Projekte."""

from pathlib import Path
import sqlite3
import tempfile
import unittest
from typing import Any

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.commerce import (
    get_purchase_document, list_articles, list_projects, list_purchase_documents,
)
from mo_local_mcp.commerce_catalog import COMMERCE_CATALOG, COMMERCE_MONEY_FIELDS
from mo_local_mcp.database import OfficeDatabase


def records(result):
    return [dict(zip(result["columns"], row)) for row in result["rows"]]


class CommerceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root / "synthetisch.db", root / "synthetisch.key"
        key = b"synthetic-key-01"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA page_size=1024")
        connection.executescript("""
            CREATE TABLE BESTELLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Entwurf,
                BestellNr,LieferNr,Datum,LieferDatum,Adress_id,Posten_id,Projekt_id,Betreff,
                RechnAnschrift,LieferAnschrift,Notizen,Waehrung,Kurs,Gedruckt,Buchung_Status,
                Rabatt,PosGesamtNettoFW,PosGesamtNettoSW,GesamtRabattFW,GesamtRabattSW,
                GesamtNettoFW,GesamtNettoSW,GesamtSteuerFW,GesamtSteuerSW,
                GesamtBruttoFW,GesamtBruttoSW);
            CREATE TABLE BESTELLPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Bestell_id,
                Art,SortNr,Nummer,Menge,Rabatt,Gewicht,EinzelPreisNettoFW,
                EinzelPreisNettoSW,GesamtPreisNettoFW,GesamtPreisNettoSW,
                PreisProStkEK,PreisProStkVK,PreisEKNetto,PreisEKBrutto);
            CREATE TABLE ARTIKEL (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Status,
                ArtikelNr COLLATE NOCASE,Bezeichnung,Beschreibung,Matchcode,EANCode,
                Hersteller,HerstellerNr,Warengruppe COLLATE NOCASE,Lagerartikel,Gesperrt,
                PreisProStkEK,PreisProStkVK,EKPreisNetto,VKGesamtBrutto,
                EKAufwProzentNetto,VKMargeProzentBrutto,MindestBestand,Gewicht);
            CREATE TABLE PROJEKT (_rowid INTEGER PRIMARY KEY,Firma_id,
                ProjektNr COLLATE NOCASE,Bezeichnung,Beschreibung,Bearbeiter,Notizen,
                DatumStart,DatumEnde,Status);
        """)

        def insert(table, **values):
            connection.execute(
                f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})",
                list(values.values()),
            )

        for row_id, company, kind, draft, day in (
            (1, 1, 104, 0, "01"), (2, 1, 102, 1, "02"),
            (3, 1, 999, None, "03"), (4, 2, 104, 0, "01"),
            (5, 1, None, 0, "03"), (6, 1, 107, 2, "04"),
        ):
            insert("BESTELLUNG", _rowid=row_id, Firma_id=company, Art=kind, Entwurf=draft,
                   BestellNr=f"TEST-{row_id}", LieferNr=f"LIEFERANT-{row_id}", Datum="2026-01-" + day, Adress_id=10,
                   Betreff="Synthetischer Einkauf 100%_\\" if row_id == 1 else "Andere",
                   Waehrung="USD", Kurs=0.92345, Rabatt=7.25, Buchung_Status=91,
                   GesamtNettoFW=12345.678, GesamtNettoSW=11400,
                   GesamtSteuerFW=None, GesamtSteuerSW=2166,
                   GesamtBruttoFW=-12345, GesamtBruttoSW=-11400)
        for row_id, company, order, sort, number in (
            (1, 1, 1, 2, 1), (2, 1, 1, 1, 2), (3, 2, 1, 0, 0),
            (4, 1, 2, 0, 0), (5, 1, 1, 1, 2),
        ):
            insert("BESTELLPOSITION", _rowid=row_id, Firma_id=company, Bestell_id=order,
                   Art=2 if row_id == 2 else 999, SortNr=sort, Nummer=number,
                   Menge=1.25, Rabatt=5.75, Gewicht=0.125,
                   EinzelPreisNettoFW=123.456, EinzelPreisNettoSW=111.123,
                   GesamtPreisNettoFW=-345.678, GesamtPreisNettoSW=-300,
                   PreisProStkEK=12.345, PreisProStkVK=67.89,
                   PreisEKNetto=12.3, PreisEKBrutto=None)
        for row_id, company, kind, status, stock, group in (
            (1, 1, 1, 0, 1, "A_%"), (2, 1, 2, 3, 0, "B"),
            (3, 1, 999, 99, 1, "A_%"), (4, 2, 1, 0, 1, "A_%"),
            (5, 1, None, None, None, None),
        ):
            insert("ARTIKEL", _rowid=row_id, Firma_id=company, Art=kind, Status=status,
                   ArtikelNr="TEST-A", Bezeichnung="Test 100%_\\" if row_id == 1 else "Andere",
                   Warengruppe=group, Lagerartikel=stock, Gesperrt=1,
                   PreisProStkEK=123.456, PreisProStkVK=None, EKPreisNetto=765.4321,
                   VKGesamtBrutto=-2345, EKAufwProzentNetto=7.5,
                   VKMargeProzentBrutto=12.25, MindestBestand=1.5, Gewicht=0.125)
        for row_id, company, status in ((1, 1, 0), (2, 1, 4), (3, 1, 99), (4, 2, 6), (5, 1, None)):
            insert("PROJEKT", _rowid=row_id, Firma_id=company, ProjektNr="TEST-P",
                   Bezeichnung="Projekt", Beschreibung="Test 100%_\\" if row_id == 2 else None,
                   Status=status, DatumStart="2026-01-01", DatumEnde=None)
        connection.commit()
        connection.close()
        plain = path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, "little"))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        path.write_bytes(encrypted)
        database = OfficeDatabase(path, key_path)
        self.addCleanup(database.close)
        self.reader = BusinessReader(database)
        self.source = path
        self.encrypted = bytes(encrypted)

    def test_einkauf_entwuerfe_unbekannte_codes_und_mandanten(self):
        rows = records(list_purchase_documents(self.reader, 1))
        self.assertEqual([r["_rowid"] for r in rows], [1, 3, 5])
        self.assertEqual([r["Art_label"] for r in rows], ["Eingangsrechnung", "Unbekannt", "Nicht angegeben"])
        self.assertIsNone(rows[1]["Entwurf"])
        self.assertEqual(rows[0]["Buchung_Status"], 91)
        self.assertEqual(len(records(list_purchase_documents(self.reader, 1, include_drafts=True))), 5)
        self.assertEqual(records(list_purchase_documents(self.reader, 1, document_type=999))[0]["_rowid"], 3)
        self.assertEqual(records(list_purchase_documents(self.reader, 2))[0]["_rowid"], 4)

    def test_einkauf_datumsgrenzen_adressen_und_woertliche_suche(self):
        rows = records(list_purchase_documents(self.reader, 1, date_from="2026-01-03", date_to="2026-01-03", address_id=10))
        self.assertEqual([r["_rowid"] for r in rows], [3, 5])
        self.assertEqual(records(list_purchase_documents(self.reader, 1, address_id=11)), [])
        for text in ("100%", "_", "\\", "sYnThEtIsChEr"):
            self.assertEqual([r["_rowid"] for r in records(list_purchase_documents(self.reader, 1, search=text))], [1])
        self.assertEqual(records(list_purchase_documents(self.reader, 1, search="%' OR 1=1 --")), [])
        self.assertEqual([row["_rowid"] for row in records(
            list_purchase_documents(self.reader, 1, search="LIEFERANT-1"))], [1])

    def test_einkauf_fw_sw_praezision_und_null(self):
        row = records(list_purchase_documents(self.reader, 1))[0]
        self.assertEqual(row["GesamtNettoFW"], "123.45678")
        self.assertEqual(row["GesamtNettoSW"], "114.00")
        self.assertEqual(row["GesamtBruttoFW"], "-123.45")
        self.assertIsNone(row["GesamtSteuerFW"])
        self.assertEqual(row["Waehrung"], "USD")
        self.assertEqual(row["Kurs"], 0.92345)

    def test_einkauf_stabile_seiten(self):
        first = list_purchase_documents(self.reader, 1, limit=1)
        second = list_purchase_documents(self.reader, 1, limit=1, offset=first["next_offset"])
        third = list_purchase_documents(self.reader, 1, limit=1, offset=second["next_offset"])
        self.assertEqual([records(page)[0]["_rowid"] for page in (first, second, third)], [1, 3, 5])
        self.assertIsNone(third["next_offset"])
        self.assertEqual(records(list_purchase_documents(self.reader, 1, offset=100)), [])

    def test_einkaufdetail_firma_positionen_und_entwurf(self):
        result = get_purchase_document(self.reader, 1, 1, position_limit=1)
        self.assertEqual(records(result["document"])[0]["Rabatt"], 7.25)
        row = records(result["positions"])[0]
        self.assertEqual(row["_rowid"], 2)
        self.assertEqual(row["Art_label"], "Manueller Artikel")
        self.assertEqual(row["EinzelPreisNettoFW"], "1.23456")
        self.assertEqual(row["EinzelPreisNettoSW"], "1.11123")
        self.assertEqual(row["PreisProStkEK"], "0.12345")
        self.assertIsNone(row["PreisEKBrutto"])
        self.assertEqual((row["Menge"], row["Rabatt"], row["Gewicht"]), (1.25, 5.75, 0.125))
        following = get_purchase_document(self.reader, 1, 1, position_offset=result["positions"]["next_offset"])
        self.assertEqual([r["_rowid"] for r in records(following["positions"])], [5, 1])
        self.assertEqual(records(following["positions"])[0]["Art_label"], "Unbekannt")
        self.assertEqual(records(get_purchase_document(self.reader, 1, 2)["document"])[0]["Entwurf"], 1)
        for company, document in ((2, 1), (1, 4), (1, 999)):
            with self.assertRaises(ValueError):
                get_purchase_document(self.reader, company, document)

    def test_artikel_filter_preise_und_rohwerte(self):
        rows = records(list_articles(self.reader, 1))
        self.assertEqual([r["_rowid"] for r in rows], [1, 2, 3, 5])
        self.assertEqual([r["Art_label"] for r in rows], ["Artikel", "Leistung", "Unbekannt", "Nicht angegeben"])
        self.assertEqual([r["Status_label"] for r in rows], ["Verkauf und Einkauf", "kein Status", "Unbekannt", "Nicht angegeben"])
        row = rows[0]
        self.assertEqual(row["EKPreisNetto"], "7.654321")
        self.assertEqual(row["VKGesamtBrutto"], "-23.45")
        self.assertIsNone(row["PreisProStkVK"])
        self.assertEqual((row["EKAufwProzentNetto"], row["VKMargeProzentBrutto"], row["MindestBestand"], row["Gewicht"]), (7.5, 12.25, 1.5, 0.125))
        self.assertNotIn("Waehrung", row)
        self.assertNotIn("currency", list_articles(self.reader, 1))
        self.assertEqual([r["_rowid"] for r in records(list_articles(self.reader, 1, stock_only=True, group="a_%"))], [1, 3])
        self.assertEqual(records(list_articles(self.reader, 1, group="%")), [])
        self.assertEqual(records(list_articles(self.reader, 1, article_type=999))[0]["_rowid"], 3)
        self.assertEqual(records(list_articles(self.reader, 1, article_type=2))[0]["Gesperrt"], 1)

    def test_artikel_und_projekte_woertlich_und_seitenstabil(self):
        for function, expected in ((list_articles, 1), (list_projects, 2)):
            for text, article_ids in (("100%", [1]), ("_", [1, 3]), ("\\", [1])):
                expected_ids = article_ids if function is list_articles else [expected]
                self.assertEqual([r["_rowid"] for r in records(function(self.reader, 1, search=text))], expected_ids)
            first = function(self.reader, 1, limit=1)
            second = function(self.reader, 1, limit=1, offset=first["next_offset"])
            self.assertEqual(records(first)[0]["_rowid"], 1)
            self.assertEqual(records(second)[0]["_rowid"], 2)
            self.assertEqual([r["_rowid"] for r in records(function(self.reader, 2))], [4])
        rows = records(list_projects(self.reader, 1))
        self.assertEqual([r["Status_label"] for r in rows], ["", "In Arbeit", "Unbekannt", "Nicht angegeben"])
        self.assertIsNone(rows[0]["DatumEnde"])

    def test_grenzen_und_typen(self):
        for function in (list_purchase_documents, list_articles, list_projects):
            for values in ({"company_id": True}, {"company_id": 0}, {"limit": 0},
                           {"limit": 501}, {"limit": True}, {"offset": -1}, {"offset": 0.5}):
                arguments = {"company_id": 1, **values}
                with self.subTest(function=function.__name__, values=values), self.assertRaises(ValueError):
                    function(self.reader, **arguments)
            self.assertIsInstance(function(self.reader, 1, limit=500), dict)
        purchase_cases: tuple[dict[str, Any], ...] = (
            {"date_from": "2026-02-30"}, {"date_to": "20260101"},
            {"date_from": "2026-02-01", "date_to": "2026-01-01"},
            {"document_type": True}, {"address_id": 0}, {"include_drafts": "false"},
        )
        for values in purchase_cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                list_purchase_documents(self.reader, 1, **values)
        article_cases: tuple[dict[str, Any], ...] = (
            {"article_type": True}, {"stock_only": 1}, {"group": 2},
        )
        for values in article_cases:
            with self.assertRaises(ValueError):
                list_articles(self.reader, 1, **values)
        for values in ({"document_id": 0}, {"document_id": True},
                       {"position_limit": 501}, {"position_offset": -1}):
            arguments = {"document_id": 1, **values}
            with self.assertRaises(ValueError):
                get_purchase_document(self.reader, 1, **arguments)

    def test_katalog_geldfelder_und_unveraenderte_quelle(self):
        self.assertEqual(set(COMMERCE_CATALOG), {"BESTELLUNG", "BESTELLPOSITION", "ARTIKEL", "PROJEKT"})
        self.assertNotIn("Rabatt", COMMERCE_MONEY_FIELDS["BESTELLPOSITION"])
        self.assertNotIn("EKAufwProzentNetto", COMMERCE_MONEY_FIELDS["ARTIKEL"])
        list_purchase_documents(self.reader, 1)
        get_purchase_document(self.reader, 1, 1)
        list_articles(self.reader, 1)
        list_projects(self.reader, 1)
        self.assertEqual(self.source.read_bytes(), self.encrypted)
