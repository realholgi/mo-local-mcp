"""Synthetische Integrationstests des Connect-Belegadapters."""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.connect import ConnectReader
from mo_local_mcp.connect_documents import handle
from mo_local_mcp.database import OfficeDatabase


class ConnectDocumentTests(unittest.TestCase):
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
            CREATE TABLE FIRMA (_rowid INTEGER PRIMARY KEY, Name);
            INSERT INTO FIRMA VALUES (1,'Testmandant Eins'),(2,'Testmandant Zwei');
            CREATE TABLE ADRESSE (_rowid INTEGER PRIMARY KEY,Firma_id,RA_Firma1,RA_Vorname,RA_Nachname);
            INSERT INTO ADRESSE VALUES (10,1,'Synthetischer Kunde','',''),(20,2,'Fremder Testkunde','','');
            CREATE TABLE PROJEKT (_rowid INTEGER PRIMARY KEY,Firma_id,ProjektNr);
            INSERT INTO PROJEKT VALUES (1,1,'TEST-PROJEKT'),(2,2,'FREMD-PROJEKT');
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Adress_id,ReNr,Datum,
                PKonto, BuText,Waehrung,GesamtBruttoFW REAL,BezahltFW REAL,MinderungFW REAL,
                OffenFW REAL,Zahlungsart);
            INSERT INTO POSTEN VALUES
                (1,1,0,10,'TEST-OFFEN','2026-01-01',10000,'Testforderung','EUR',12000,0,0,12000,0),
                (2,1,0,10,'TEST-TEIL','2026-01-02',10000,'Testteilzahlung','EUR',12000,2000,1000,9000,0),
                (3,1,0,10,'TEST-BEZAHLT','2026-01-03',10000,'Testausgleich','EUR',12000,11000,1000,0,0),
                (4,1,1,10,'TEST-GUTSCHRIFT','2026-01-04',10000,'Testgutschrift','EUR',-5000,0,0,-5000,0),
                (5,1,2,10,'TEST-KREDITOR','2026-01-05',70000,'Testverbindlichkeit','USD',3000,0,0,3000,0),
                (6,2,0,20,'FREMD-POSTEN','2026-01-01',10000,'Fremd','EUR',7000,0,0,7000,0);
            CREATE TABLE AUFTRAG (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Entwurf,Adress_id,Posten_id,
                AuftragsNr,Datum,LieferDatum,Projekt_id,Betreff,Notizen,Waehrung,
                GesamtNettoSW REAL,GesamtBruttoSW REAL,GesamtNettoFW REAL,GesamtBruttoFW REAL,BestellNr);
            INSERT INTO AUFTRAG VALUES
                (100,1,4,0,10,1,'TEST-1','2026-01-01',NULL,1,'Alpha 100%','','EUR',10000,12000,10000,12000,'REF'),
                (101,1,4,0,10,2,'TEST-2','2026-01-02',NULL,0,'Beta','','EUR',10000,12000,10000,12000,''),
                (102,1,4,0,10,3,'TEST-3','2026-01-03',NULL,0,'Gamma','','EUR',10000,12000,10000,12000,''),
                (103,1,1,0,10,0,'TEST-ANGEBOT','2026-01-04',NULL,0,'Angebot','','EUR',1000,1200,1000,1200,''),
                (104,1,4,0,10,0,'TEST-OHNE-OP','2026-01-05',NULL,0,'Rechnung ohne Posten','','EUR',1000,1200,1000,1200,''),
                (105,2,4,0,20,6,'FREMD-BELEG','2026-01-01',NULL,2,'Fremd','','EUR',5000,7000,5000,7000,''),
                (106,1,4,0,20,6,'TEST-FREMDE-RELATION','2026-01-06',NULL,2,'Defekte Relation','','EUR',5000,7000,5000,7000,'');
            CREATE TABLE BESTELLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Adress_id,Posten_id,
                BestellNr,Datum,LieferDatum,Projekt_id,Betreff,Notizen,GesamtNettoFW REAL,GesamtBruttoFW REAL);
            INSERT INTO BESTELLUNG VALUES
                (200,1,4,10,5,'TEST-EINKAUF','2026-01-05',NULL,0,'Einkauf 100%','',2500,3000),
                (201,2,4,20,6,'FREMD-EINKAUF','2026-01-05',NULL,2,'Fremd','',5000,7000);
            CREATE TABLE AUFTRAGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Auftrag_id,Nummer,
                Art,Bezeichnung,ArtikelNr,Menge,EinzelPreisNettoFW REAL,GesamtPreisNettoFW REAL);
            INSERT INTO AUFTRAGSPOSITION VALUES
                (1,1,100,2,3,'Testtext','',0,0,0),(2,1,100,1,2,'Testartikel','TEST-A',2,5000,10000),
                (3,2,100,3,3,'Fremdposition','',0,0,0);
            CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id,Position,
                BuText,EKonto,BetragBruttoFW REAL,BetragBruttoSW REAL,BetragNettoFW REAL,
                BetragNettoSW REAL,BetragSteuerFW REAL,BetragSteuerSW REAL,Steuersatz,Kostenstelle1,Kostenstelle2);
            INSERT INTO POSTENPOSITION VALUES
                (1,1,4,1,'Negative Testposition',8400,-5000,-5000,-4200,-4200,-800,-800,'TEST','A','B'),
                (2,2,4,2,'Fremde Position',8400,999,999,999,999,0,0,'TEST','','');
        """)
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
        self.reader = ConnectReader(database)

    def call(self, method, params=None, firma_id=1) -> dict:
        return handle(self.reader, method, params or {}, firma_id)

    def sales(self, **filters) -> list[dict]:
        return self.call("verkaufbelegList", {"VerkaufbelegFilter": filters})["VerkaufbelegListitem"]

    def test_datum_inklusive_und_verknuepfte_adresse(self):
        rows = self.sales(DatumVon="2026-01-02", DatumBis="2026-01-03", Adresse_ID="10")
        self.assertEqual([row["Verkaufbeleg_ID"] for row in rows], ["101", "102"])
        self.assertEqual(rows[0]["GesamtBruttoSW"], "120.0")
        self.assertEqual(self.sales(Adresse_ID="20"), [])
        for filters in ({"DatumVon": "2026-02-30"},
                        {"DatumVon": "2026-02-01", "DatumBis": "2026-01-01"}):
            with self.assertRaises(ValueError):
                self.sales(**filters)

    def test_rechnung_und_angebot_sind_vereinigung(self):
        rows = self.sales(Rechnung=True, Angebot=True, DatumBis="2026-01-04")
        self.assertEqual([row["VerkaufbelegArt"] for row in rows], [4, 4, 4, 1])
        self.assertEqual(self.sales(Rechnung=False, Angebot=False), [])
        with self.assertRaises(ValueError):
            self.sales(Rechnung="true")

    def test_zahlungstatus_nur_aus_posten(self):
        for status, expected in ((0, ["103", "104"]), (1, ["100"]), (2, ["101"]), (3, ["102"])):
            rows = self.sales(Zahlungstatus=status, DatumBis="2026-01-05")
            self.assertEqual([row["Verkaufbeleg_ID"] for row in rows], expected)
        with self.assertRaises(ValueError):
            self.sales(Zahlungstatus=1)
        with self.assertRaises(ValueError):
            self.sales(Zahlungstatus="offen")

    def test_einkauf_nutzt_bestellung_und_fw(self):
        rows = self.call("einkaufbelegList", {"EinkaufbelegFilter": {
            "DatumVon": "2026-01-05", "DatumBis": "2026-01-05", "Adresse_ID": "10",
            "Suchtext": "100%", "Zahlungstatus": 1}})["EinkaufbelegListitem"]
        self.assertEqual([row["Einkaufbeleg_ID"] for row in rows], ["200"])
        self.assertEqual(rows[0]["GesamtBruttoFW"], "30.0")
        self.assertEqual(rows[0]["BestellNr"], "TEST-EINKAUF")

    def test_get_ist_firmengebunden_und_positionen_sortiert(self):
        item = self.call("verkaufbelegGet", {"Verkaufbeleg_ID": "100"})["VerkaufbelegItem"]
        self.assertEqual(item["Posten_ID"], "1")
        self.assertEqual(item["Zahlungstatus"], 1)
        self.assertEqual(item["Projekt_ID"], "1")
        positions = item["VerkaufbelegPositionItemList"]["VerkaufbelegPositionItem"]
        self.assertEqual([row["Nummer"] for row in positions], ["1", "2"])
        self.assertEqual(positions[0]["GesamtPreisNettoFW"], "100.0")
        for method, params in (("verkaufbelegGet", {"Verkaufbeleg_ID": "105"}),
                               ("offenePostenGet", {"Posten_ID": "6"})):
            with self.assertRaises(ValueError):
                self.call(method, params)

    def test_negative_op_und_seitenfilter(self):
        params = {"offenePostenFilter": {"DatumVon": "2026-01-04", "DatumBis": "2026-01-05",
                                        "Adresse_ID": "10", "NurOffene": True}}
        rows = self.call("offenePostenList", params)["OffenePostenListItem"]
        self.assertEqual([row["Posten_ID"] for row in rows], ["4", "5"])
        self.assertEqual(rows[0]["Offen"], "-50.0")
        debitors = self.call("offenePostenListDebitoren", params)["OffenePostenListItem"]
        creditors = self.call("offenePostenListKreditoren", params)["OffenePostenListItem"]
        self.assertEqual([row["Postenart"] for row in debitors], [1])
        self.assertEqual([row["Postenart"] for row in creditors], [2])
        item = self.call("offenePostenGet", {"Posten_ID": "4"})["OffenePostenItem"]
        positions = item["OffenePostenPositionItemList"]["OffenePostenPositionItem"]
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["BetragBruttoFW"], "-50.0")
        self.assertEqual(item["Waehrung"], "EUR")

    def test_offizielle_wrapper_und_explizit_ausgeglichene(self):
        rows = self.call("offenePostenListDebitoren", {"OffenePostenFilter": {
            "NurOffene": False}})["OffenePostenListItem"]
        self.assertIn("3", [row["Posten_ID"] for row in rows])
        rows = self.call("offenePostenListDebitoren")["OffenePostenListItem"]
        self.assertNotIn("3", [row["Posten_ID"] for row in rows])

    def test_unbekannte_filter_und_mehrdeutige_wrapper_abgelehnt(self):
        for method, params in (
            ("verkaufbelegList", {"VerkaufbelegFilter": {"Unbekannt": True}}),
            ("einkaufbelegList", {"EinkaufbelegFilter": {"Unbekannt": True}}),
            ("offenePostenList", {"offenePostenFilter": {"NurOffene": "true"}}),
            ("offenePostenList", {"OffenePostenFilter": {}, "offenePostenFilter": {}}),
            ("verkaufbelegGet", {"Verkaufbeleg_ID": "100 OR 1=1"}),
        ):
            with self.subTest(method=method, params=params), self.assertRaises(ValueError):
                self.call(method, params)

    def test_suchtext_ist_woertlich(self):
        self.assertEqual([row["Verkaufbeleg_ID"] for row in self.sales(Suchtext="100%")], ["100"])
        self.assertEqual(self.sales(Suchtext="_"), [])
