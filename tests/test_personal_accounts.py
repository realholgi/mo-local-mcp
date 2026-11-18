import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.personal_accounts import list_personal_balances


def balance(result, account, currency: str | None = "EUR", system_currency: str | None = "EUR"):
    return next(row for row in result["entries"] if row["konto"] == account
                and row["waehrung_fw"] == currency and row["waehrung_sw"] == system_currency)


class PersonalAccountTests(unittest.TestCase):
    def reader(self, extra_sql=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "personenkonten.db"
        key_path = Path(directory.name) / "personenkonten.key"
        key = b"personal-key-123"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA page_size=1024")
        connection.executescript("""
            CREATE TABLE ADRESSE (_rowid INTEGER PRIMARY KEY, Firma_id, KZ_AdressNr, KZ_Matchcode,
                RA_Firma1, RA_Vorname, RA_Nachname, KF_Konto, LF_Konto,
                KF_Status, LF_Status, KF_Waehrung, LF_Waehrung);
            INSERT INTO ADRESSE VALUES
                (10,1,'A10','Beide','Synthetisch Eins','','',10000,70000,1,3,'CHF','GBP'),
                (11,1,'A11','Geteilt','Synthetisch Zwei','','',10000,0,2,0,'USD',''),
                (12,1,'A12','Unbebucht','Synthetisch Drei','','',10001,70001,3,2,'EUR','EUR'),
                (13,1,'A13','Ohne Konto','Synthetisch Vier','','',NULL,0,1,1,'EUR','EUR'),
                (14,1,'A14','Ohne Rolle','Synthetisch Fünf','','',0,0,0,0,'',''),
                (15,2,'A15','Andere Firma','Synthetisch Sechs','','',10000,70000,1,1,'EUR','EUR'),
                (16,1,'A16','Zuordnung ohne Status','Synthetisch Sieben','','',10002,0,0,0,'EUR','');
            CREATE TABLE WIRTSCHAFTSJAHR (_rowid INTEGER PRIMARY KEY, Firma_id, Waehrung);
            INSERT INTO WIRTSCHAFTSJAHR VALUES (1,1,'EUR'),(2,1,'CHF'),(3,2,'GBP');
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY, Firma_id, Wj_id, Datum, Art, Status, Waehrung);
            INSERT INTO BUCHUNG VALUES
                (1,1,1,'2026-01-01',2,99,'EUR'),
                (2,1,1,'2026-01-02',1,0,'EUR'),
                (3,1,1,'2026-01-31',1,3,'EUR'),
                (4,1,1,'2026-02-01',1,1,'EUR'),
                (5,1,1,'2026-01-15',1,2,'USD'),
                (6,1,2,'2026-01-15',1,2,'USD'),
                (7,2,3,'2026-01-02',1,2,'EUR');
            CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY, Firma_id, Buchung_id, Konto,
                BetragSoll, BetragHaben, BetragSollFW, BetragHabenFW, Storno);
            INSERT INTO JOURNAL VALUES
                (1,1,1,10000,10000,0,10000,0,0),
                (2,1,2,10000,2000,0,2000,0,0),
                (3,1,3,10000,-500,1000,-500,1000,1),
                (4,1,4,10000,100,0,100,0,0),
                (5,1,5,10000,900,0,1000,0,0),
                (6,1,6,10000,800,0,1000,0,0),
                (7,1,2,70000,0,4000,0,4000,0),
                (8,1,3,70000,0,-1000,0,-1000,1),
                (9,2,7,10000,999999,0,999999,0,0),
                (10,2,2,10000,999999,0,999999,0,0),
                (11,1,7,10000,999999,0,999999,0,0),
                (12,1,2,12345,888888,0,888888,0,0);
        """)
        connection.executescript(extra_sql)
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
        return BusinessReader(database)

    def test_customer_signed_journal_and_shared_account_count_once(self):
        result = list_personal_balances(self.reader(), 1, date_to="2026-01-31")
        row = balance(result, 10000)
        self.assertEqual(row["journalzeilen"], 3)
        self.assertEqual(row["eroeffnungszeilen"], 1)
        self.assertEqual((row["soll_sw"], row["haben_sw"], row["saldo_sw"]),
                         ("115.00", "10.00", "105.00"))
        self.assertEqual((row["soll_fw"], row["haben_fw"], row["saldo_fw"]),
                         ("115.00", "10.00", "105.00"))
        self.assertEqual([address["adresse_id"] for address in row["adressen"]], [10, 11])
        self.assertEqual([address["status"] for address in row["adressen"]], [1, 2])
        self.assertEqual(row["adressen"][0]["stammwaehrung"], "CHF")
        self.assertEqual(result["totals"][0]["saldo_sw"], "105.00")
        self.assertIn("Kein historischer OP-Saldo", result["hinweise"][0])

    def test_supplier_role_does_not_guess_account_type(self):
        result = list_personal_balances(self.reader(), 1, side="supplier")
        row = balance(result, 70000)
        self.assertEqual(row["saldo_sw"], "-30.00")
        self.assertEqual(row["haben_fw"], "30.00")
        self.assertEqual(row["adressen"][0]["status"], 3)
        self.assertEqual(result["seite"], "Kreditoren")
        self.assertEqual(result["total_entries"], 3)
        self.assertEqual({row["konto"] for row in result["entries"]}, {70000, 70001, None})

    def test_currency_pairs_are_actual_booking_and_year_currencies(self):
        result = list_personal_balances(self.reader(), 1)
        euro = balance(result, 10000, "USD", "EUR")
        swiss = balance(result, 10000, "USD", "CHF")
        self.assertEqual((euro["soll_sw"], euro["soll_fw"]), ("9.00", "10.00"))
        self.assertEqual((swiss["soll_sw"], swiss["soll_fw"]), ("8.00", "10.00"))
        self.assertEqual(len(result["totals"]), 3)
        self.assertEqual({(row["waehrung_fw"], row["waehrung_sw"]) for row in result["totals"]},
                         {("EUR", "EUR"), ("USD", "EUR"), ("USD", "CHF")})

    def test_all_mandant_joins_are_scoped(self):
        result = list_personal_balances(self.reader(), 2)
        row = balance(result, 10000, "EUR", "GBP")
        self.assertEqual(row["journalzeilen"], 1)
        self.assertEqual(row["saldo_sw"], "9999.99")
        self.assertEqual([address["adresse_id"] for address in row["adressen"]], [15])
        self.assertEqual(result["total_entries"], 1)

    def test_address_filter_selects_shared_account_not_fraction(self):
        reader = self.reader()
        result = list_personal_balances(reader, 1, address_id=11)
        self.assertEqual(result["total_entries"], 3)
        self.assertEqual(balance(result, 10000)["saldo_sw"], "106.00")
        self.assertEqual([row["adresse_id"] for row in result["entries"][0]["adressen"]], [10, 11])
        for address_id in (15, 999, 14):
            with self.subTest(address_id=address_id):
                empty = list_personal_balances(reader, 1, address_id=address_id)
                self.assertEqual(empty["entries"], [])
                self.assertEqual(empty["totals"], [])

    def test_missing_account_is_unknown_unbooked_account_is_zero(self):
        result = list_personal_balances(self.reader(), 1)
        unbooked = balance(result, 10001, None, None)
        self.assertEqual(unbooked["saldo_sw"], "0.00")
        self.assertEqual(unbooked["journalzeilen"], 0)
        self.assertEqual(unbooked["adressen"][0]["status"], 3)
        self.assertEqual(balance(result, 10002, None, None)["saldo_fw"], "0.00")
        missing = balance(result, None, None, None)
        self.assertEqual(missing["kontozuordnung"], "fehlt")
        self.assertIsNone(missing["saldo_sw"])
        self.assertIsNone(missing["soll_fw"])
        self.assertEqual(missing["adressen"][0]["adresse_id"], 13)
        self.assertEqual(result["total_entries"], 6)

    def test_date_bounds_include_endpoints_and_keep_unbooked_masters(self):
        result = list_personal_balances(self.reader(), 1, date_from="2026-01-02", date_to="2026-01-31")
        row = balance(result, 10000)
        self.assertEqual((row["soll_sw"], row["haben_sw"], row["saldo_sw"]), ("15.00", "10.00", "5.00"))
        self.assertEqual(row["eroeffnungszeilen"], 0)
        empty_period = list_personal_balances(self.reader(), 1, date_from="2030-01-01")
        self.assertEqual(empty_period["totals"], [])
        self.assertEqual(empty_period["total_entries"], 4)
        self.assertEqual(balance(empty_period, 10000, None, None)["saldo_sw"], "0.00")

    def test_pagination_never_changes_complete_filter_totals(self):
        reader = self.reader()
        whole = list_personal_balances(reader, 1)
        collected = []
        offset = 0
        while True:
            page = list_personal_balances(reader, 1, limit=2, offset=offset)
            self.assertEqual(page["totals"], whole["totals"])
            self.assertEqual(page["total_entries"], whole["total_entries"])
            collected.extend(page["entries"])
            if not page["truncated"]:
                self.assertIsNone(page["next_offset"])
                break
            offset = page["next_offset"]
        self.assertEqual(collected, whole["entries"])
        past = list_personal_balances(reader, 1, offset=100)
        self.assertEqual(past["entries"], [])
        self.assertFalse(past["truncated"])
        self.assertEqual(past["totals"], whole["totals"])

    def test_totals_add_distinct_accounts_not_address_copies(self):
        reader = self.reader("""
            INSERT INTO JOURNAL VALUES (13,1,2,10001,123,45,123,45,0);
        """)
        result = list_personal_balances(reader, 1)
        total = next(row for row in result["totals"] if row["waehrung_fw"] == "EUR")
        self.assertEqual(total["soll_sw"], "117.23")
        self.assertEqual(total["haben_sw"], "10.45")
        self.assertEqual(total["saldo_sw"], "106.78")
        self.assertEqual(total["journalzeilen"], 5)

    def test_missing_currency_never_invents_or_combines_money(self):
        reader = self.reader("""
            INSERT INTO BUCHUNG VALUES (8,1,3,'2026-01-15',1,99,'USD'),
                (9,1,999,'2026-01-15',1,99,''),(10,1,1,'2026-01-15',1,99,NULL);
            INSERT INTO JOURNAL VALUES (13,1,8,10000,700,0,900,0,0),
                (14,1,9,10000,800,0,1000,0,0),(15,1,10,10000,600,0,800,0,0);
        """)
        result = list_personal_balances(reader, 1)
        foreign_year = balance(result, 10000, "USD", None)
        self.assertIsNone(foreign_year["soll_sw"])
        self.assertEqual(foreign_year["saldo_fw"], "9.00")
        missing_both = balance(result, 10000, None, None)
        self.assertIsNone(missing_both["saldo_sw"])
        self.assertIsNone(missing_both["saldo_fw"])
        missing_fw = balance(result, 10000, None, "EUR")
        self.assertIsNone(missing_fw["soll_fw"])
        self.assertEqual(missing_fw["saldo_sw"], "6.00")
        total = next(row for row in result["totals"] if row["waehrung_fw"] == "USD"
                     and row["waehrung_sw"] is None)
        self.assertIsNone(total["saldo_sw"])

    def test_more_than_one_source_page_retains_all_masters_and_groups(self):
        reader = self.reader("""
            WITH RECURSIVE numbers(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM numbers WHERE n<510)
            INSERT INTO ADRESSE(_rowid,Firma_id,KF_Konto,KF_Status)
                SELECT 100+n,1,20000+n,1 FROM numbers;
            INSERT INTO JOURNAL(Firma_id,Buchung_id,Konto,BetragSoll,BetragHaben,BetragSollFW,BetragHabenFW)
                SELECT 1,2,KF_Konto,100,0,100,0 FROM ADRESSE WHERE _rowid>100;
        """)
        result = list_personal_balances(reader, 1, offset=500, limit=20)
        self.assertEqual(result["total_entries"], 516)
        self.assertEqual(len(result["entries"]), 16)
        total = next(row for row in result["totals"] if row["waehrung_fw"] == "EUR")
        self.assertEqual(total["saldo_sw"], "616.00")
        self.assertFalse(result["truncated"])

    def test_empty_amount_cells_follow_existing_journal_zero_convention(self):
        reader = self.reader("""
            INSERT INTO JOURNAL VALUES (13,1,2,10001,NULL,NULL,NULL,NULL,0);
        """)
        row = balance(list_personal_balances(reader, 1), 10001)
        self.assertEqual(row["soll_sw"], "0.00")
        self.assertEqual(row["saldo_fw"], "0.00")

    def test_validation(self):
        reader = self.reader()
        cases: tuple[dict, ...] = (
            {"company_id": True}, {"company_id": 0}, {"side": "invalid"},
            {"address_id": 0}, {"address_id": True}, {"limit": 501},
            {"limit": 0}, {"limit": True}, {"offset": -1},
            {"date_from": "2026-02-30"}, {"date_to": "20260101"},
            {"date_from": "2026-02-01", "date_to": "2026-01-01"},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                kwargs.setdefault("company_id", 1)
                list_personal_balances(reader, **kwargs)


if __name__ == "__main__":
    unittest.main()
