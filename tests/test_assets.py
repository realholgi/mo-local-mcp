from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.assets import get_asset, get_depreciation_schedule, list_assets
from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase


def records(result):
    return [dict(zip(result["columns"], row)) for row in result["rows"]]


class AssetTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.path = root / "office.db"
        key_path = root / "test.key"
        key = b"anlagen-testkey!"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA page_size=1024")
        db.executescript(r"""
            CREATE TABLE ANLAGE (
                _rowid INTEGER PRIMARY KEY, _timestamp TIMESTAMP, _version INTEGER,
                Firma_id INTEGER, SD_InventarNr VARCHAR, SD_Bezeichnung VARCHAR,
                SD_Standort VARCHAR, SD_SerienNr VARCHAR, SD_Kostenstelle VARCHAR,
                SD_KontoAnlage INTEGER, SD_KontoAfa INTEGER, SD_Zusatzangaben VARCHAR,
                ZU_AHKosten DOUBLE, ZU_Datum DATE, ZU_Nutzungsdauer INTEGER,
                ZU_AfaBeginnDatum DATE, ZU_Restwert DOUBLE, ZU_AfaRunden BOOLEAN,
                ZU_AfaMethode INTEGER, ZU_AfaSatz DOUBLE, ZU_AfaWechsel BOOLEAN,
                ZU_KontoVerrech INTEGER, ZU_Historisch BOOLEAN, AB_Datum DATE,
                AB_KontoAbgang INTEGER, AB_Verkauf BOOLEAN, AB_Verkaufspreis DOUBLE,
                AB_KontoVerkauf INTEGER, AB_KontoVerrech INTEGER, AB_Historisch BOOLEAN,
                ZU_Buchung_id INTEGER, AB_AbgBuchung_id INTEGER, AB_VerkBuchung_id INTEGER,
                SD_Steuerfrei BOOLEAN, AB_Steuerfrei BOOLEAN, ZU_SAfaZeitraum INTEGER,
                SD_AVEUR_Kz VARCHAR
            );
            INSERT INTO ANLAGE (
                _rowid,Firma_id,SD_InventarNr,SD_Bezeichnung,SD_Standort,SD_SerienNr,
                SD_Kostenstelle,SD_KontoAnlage,SD_KontoAfa,SD_Zusatzangaben,
                ZU_AHKosten,ZU_Nutzungsdauer,ZU_Restwert,ZU_AfaMethode,ZU_AfaSatz,
                ZU_AfaRunden,ZU_Historisch,AB_Verkaufspreis,ZU_SAfaZeitraum,
                ZU_Buchung_id
            ) VALUES
                (10,1,'A','Testrechner','Testbüro','Serie10','Testteam',400,4830,'Vollständige Testnotizen',
                 246810,36,NULL,77,33.33,9,1,-2500.25,999,7654),
                (11,1,'A','Zweiter Testrechner',NULL,NULL,NULL,400,4830,NULL,
                 NULL,NULL,100,3,NULL,NULL,NULL,NULL,NULL,NULL),
                (12,1,'B%_\','Beschreibung%_\','Standort%_\','Serie%_\','Kostenstelle%_\',
                 400,4830,'Notizen%_\',0,12,0,4,100,0,0,0,0,NULL),
                (13,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,
                 NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
                (99,2,'A','Fremd%_\','Fremd%_\','Fremd%_\','Fremd%_\',
                 9999,9998,'Fremd%_\',999999,120,100,1,10,0,0,999999,0,NULL);
            CREATE TABLE ANLAGENPOSITION (
                _rowid INTEGER PRIMARY KEY, _timestamp TIMESTAMP, _version INTEGER,
                Firma_id INTEGER, Anlage_id INTEGER, Position INTEGER, Datum DATE,
                Vorgang INTEGER, Text VARCHAR, BuchwertAlt DOUBLE, Zugang DOUBLE,
                Abgang DOUBLE, Zuschreibung DOUBLE, Abschreibung DOUBLE, Prozent DOUBLE,
                Bemessung DOUBLE, RestND INTEGER, BuchwertNeu VARCHAR, Gebucht BOOLEAN,
                Historisch BOOLEAN, SonderAfA DOUBLE, AfAKonto INTEGER, Steuerfrei BOOLEAN
            );
            INSERT INTO ANLAGENPOSITION (
                _rowid,Firma_id,Anlage_id,Position,Datum,Vorgang,Text,BuchwertAlt,
                Zugang,Abgang,Zuschreibung,Abschreibung,Prozent,Bemessung,RestND,
                BuchwertNeu,Gebucht,Historisch,SonderAfA,AfAKonto,Steuerfrei
            ) VALUES
                (100,1,10,1,'2026-01-01',1,'Anschaffung',246810,-125,NULL,0.5,
                 -11110,33.33,246810,35,'-12345.678',1,0,12.345,4830,9),
                (101,1,10,1,'2026-12-31',2,'Gebuchte Abschreibung',246810,0,0,0,
                 11110,33.33,246810,24,'135790',1,0,0,4830,0),
                (102,1,10,2,'2099-12-31',2,'Zukünftig ungebucht',135790,0,0,0,
                 22220,33.33,246810,12,'86420',0,0,0,4830,0),
                (103,1,10,3,'2025-12-31',2,'Historisch',86420,0,0,0,
                 22220,33.33,246810,6,'43210',NULL,1,0,4830,0),
                (104,1,10,4,'2027-01-01',5,'Abgang',43210,0,43210,0,
                 0,0,246810,0,'0',0,1,0,4830,0),
                (105,1,10,5,NULL,88,'Unbekannter Rohcode',NULL,NULL,NULL,NULL,
                 NULL,NULL,NULL,NULL,NULL,9,9,NULL,NULL,NULL),
                (110,1,11,1,'2026-01-01',2,'Andere Anlage',100,0,0,0,
                 0,0,100,1,'100',1,0,0,4830,0),
                (120,1,12,1,'2026-12-31',2,'Andere Anlage an der oberen Datumsgrenze',100,0,0,0,
                 0,0,100,1,'100',0,0,0,4830,0),
                (190,2,10,1,'2026-01-01',2,'Falsche Bewegungsfirma',0,0,0,0,
                 0,0,0,0,'0',1,0,0,9998,0),
                (191,1,99,1,'2026-01-01',2,'Falsche Anlagenfirma',0,0,0,0,
                 0,0,0,0,'0',1,0,0,9998,0),
                (192,1,777,1,'2026-01-01',2,'Fehlende Anlage',0,0,0,0,
                 0,0,0,0,'0',1,0,0,9998,0),
                (199,2,99,1,'2026-01-01',2,'Fremde Bewegung',999999,0,0,0,
                 0,0,999999,120,'999999',1,0,0,9998,0);
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
        database = OfficeDatabase(self.path, key_path)
        self.addCleanup(database.close)
        self.reader = BusinessReader(database)

    def test_company_scope_rejects_foreign_headers_and_mismatched_movements(self):
        self.assertEqual({row["_rowid"] for row in records(list_assets(self.reader, 1))}, {10, 11, 12, 13})
        for asset_id in (99, 777):
            with self.subTest(asset_id=asset_id), self.assertRaises(ValueError):
                get_asset(self.reader, 1, asset_id)
        detail = get_asset(self.reader, 1, 10)
        self.assertEqual(records(detail["asset"])[0]["_rowid"], 10)
        self.assertEqual([row["_rowid"] for row in records(detail["movements"])], [100, 101, 102, 103, 104, 105])
        self.assertEqual([row["_rowid"] for row in records(get_depreciation_schedule(self.reader, 1))],
                         [100, 101, 102, 103, 104, 105, 110, 120])
        self.assertEqual([row["_rowid"] for row in records(get_depreciation_schedule(self.reader, 2))], [199])
        self.assertEqual(list_assets(self.reader, 3)["rows"], [])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_money_preserves_sign_null_and_numeric_text_without_scaling_raw_fields(self):
        asset = records(get_asset(self.reader, 1, 10)["asset"])[0]
        for field, expected in {
            "ZU_AHKosten": "2468.10", "ZU_Restwert": None, "AB_Verkaufspreis": "-25.0025",
            "ZU_Nutzungsdauer": 36, "ZU_AfaSatz": 33.33, "ZU_AfaMethode": 77,
            "ZU_AfaRunden": 9, "ZU_Historisch": 1, "SD_KontoAnlage": 400,
            "SD_KontoAfa": 4830, "ZU_SAfaZeitraum": 999, "ZU_Buchung_id": 7654,
        }.items():
            with self.subTest(field=field):
                self.assertEqual(asset[field], expected)
        listed = records(list_assets(self.reader, 1, search="10"))[0]
        self.assertEqual(listed["ZU_AHKosten"], "2468.10")
        movements = records(get_depreciation_schedule(self.reader, 1, asset_id=10))
        for field, expected in {
            "BuchwertAlt": "2468.10", "Zugang": "-1.25", "Abgang": None,
            "Zuschreibung": "0.005", "Abschreibung": "-111.10", "Bemessung": "2468.10",
            "BuchwertNeu": "-123.45678", "SonderAfA": "0.12345", "Prozent": 33.33,
            "RestND": 35, "AfAKonto": 4830, "Steuerfrei": 9,
            "SD_KontoAnlage": 400, "SD_KontoAfa": 4830,
        }.items():
            with self.subTest(field=field):
                self.assertEqual(movements[0][field], expected)
        self.assertIsNone(movements[-1]["BuchwertNeu"])
        self.assertEqual(movements[-1]["Vorgang"], 88)
        self.assertEqual(movements[-1]["Gebucht"], 9)

    def test_default_retains_future_historical_disposal_and_unknown_booking_states(self):
        rows = {row["_rowid"]: row for row in records(get_depreciation_schedule(self.reader, 1, asset_id=10))}
        self.assertEqual(set(rows), {100, 101, 102, 103, 104, 105})
        self.assertEqual(rows[102]["Datum"], "2099-12-31")
        self.assertEqual(rows[103]["Historisch"], 1)
        self.assertEqual(rows[104]["Vorgang"], 5)
        self.assertEqual(rows[104]["Abgang"], "432.10")
        self.assertEqual([row["_rowid"] for row in records(
            get_depreciation_schedule(self.reader, 1, booked_only=True))], [100, 101, 110])

    def test_date_bounds_are_inclusive_and_compose_with_asset_filter(self):
        rows = records(get_depreciation_schedule(self.reader, 1, date_from="2026-01-01", date_to="2026-12-31"))
        self.assertEqual([row["_rowid"] for row in rows], [100, 101, 110, 120])
        rows = records(get_depreciation_schedule(self.reader, 1, asset_id=10,
                                                date_from="2026-01-01", date_to="2026-12-31"))
        self.assertEqual([row["_rowid"] for row in rows], [100, 101])
        rows = records(get_depreciation_schedule(self.reader, 1, asset_id=12,
                                                date_from="2026-12-31", date_to="2026-12-31"))
        self.assertEqual([row["_rowid"] for row in rows], [120])
        for bounds in ({"date_from": "2026-12-31", "date_to": "2026-01-01"},
                       {"date_from": "2026-1-1"}, {"date_to": "2026-02-30"}):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                get_depreciation_schedule(self.reader, 1, **bounds)

    def test_search_treats_wildcards_literally_across_each_supported_field(self):
        for search in ("%", "_", "\\", "B%_\\", "beschreibung%_\\", "Standort%_\\",
                       "Serie%_\\", "Kostenstelle%_\\", "Notizen%_\\", "12"):
            with self.subTest(search=search):
                self.assertEqual([row["_rowid"] for row in records(list_assets(self.reader, 1, search))], [12])
        self.assertEqual(list_assets(self.reader, 1, "Fremd")["rows"], [])
        self.assertEqual(list_assets(self.reader, 1, "nicht vorhanden")["rows"], [])

    def test_pagination_is_stable_with_equal_inventory_numbers_and_positions(self):
        for function, kwargs, expected in (
            (list_assets, {}, [13, 10, 11, 12]),
            (get_depreciation_schedule, {}, [100, 101, 102, 103, 104, 105, 110, 120]),
            (get_depreciation_schedule, {"asset_id": 10}, [100, 101, 102, 103, 104, 105]),
        ):
            with self.subTest(function=function.__name__, kwargs=kwargs):
                seen = []
                offset = 0
                for index in range(len(expected)):
                    page = function(self.reader, 1, limit=1, offset=offset, **kwargs)
                    seen.extend(row["_rowid"] for row in records(page))
                    self.assertEqual(page["next_offset"], index + 1 if index + 1 < len(expected) else None)
                    offset += 1
                self.assertEqual(seen, expected)
                self.assertEqual(function(self.reader, 1, offset=100, **kwargs)["rows"], [])
        first = get_asset(self.reader, 1, 10, limit=1)
        second = get_asset(self.reader, 1, 10, limit=1, offset=1)
        self.assertEqual([row["_rowid"] for row in records(first["movements"])], [100])
        self.assertEqual(first["movements"]["next_offset"], 1)
        self.assertEqual([row["_rowid"] for row in records(second["movements"])], [101])
        self.assertEqual(records(second["asset"])[0]["_rowid"], 10)


if __name__ == "__main__":
    unittest.main()
