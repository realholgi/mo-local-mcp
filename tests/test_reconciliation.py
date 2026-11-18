import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.reconciliation import reconcile_accounts


class ReconciliationTests(unittest.TestCase):
    def reader(self, extra_sql=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root / "abstimmung.db", root / "abstimmung.key"
        key = b"reconcile-key123"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(path)
        db.execute("PRAGMA page_size=1024")
        db.executescript("""
            CREATE TABLE WIRTSCHAFTSJAHR (_rowid INTEGER PRIMARY KEY,Firma_id,Von,Bis,Waehrung);
            INSERT INTO WIRTSCHAFTSJAHR VALUES
                (1,1,'2025-01-01','2025-12-31','EUR'),
                (2,1,'2024-01-01','2024-12-31','EUR'),
                (3,2,'2025-01-01','2025-12-31','GBP');
            CREATE TABLE KONTO (_rowid INTEGER PRIMARY KEY,Firma_id,Nummer);
            INSERT INTO KONTO VALUES (1,1,10000),(2,1,70000),(3,1,1400),(4,1,1600),
                (5,2,10000),(6,2,1400);
            CREATE TABLE ADRESSE (_rowid INTEGER PRIMARY KEY,Firma_id,KF_Konto,LF_Konto,KF_Status,LF_Status);
            INSERT INTO ADRESSE VALUES (1,1,10000,0,1,0),(2,1,0,70000,0,1),
                (3,2,10000,0,1,0),(4,1,10000,0,1,0);
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Wj_id,Datum,Waehrung,Art);
            INSERT INTO BUCHUNG VALUES (1,1,1,'2025-01-01','EUR',2),
                (2,1,1,'2025-01-15','EUR',1),(3,1,1,'2025-02-01','EUR',1),
                (4,2,3,'2025-01-01','GBP',1);
            CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY,Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben);
            INSERT INTO JOURNAL VALUES (1,1,1,10000,1400,10000,0),
                (2,1,2,10000,1400,-1000,0),(3,1,2,70000,1600,0,4000),
                (4,1,3,10000,1400,9900,0),(5,2,4,10000,1400,99999,0);
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id DEFAULT 1,Art DEFAULT 0,Adress_id DEFAULT 1,
                ReNr,Datum,PKonto DEFAULT 10000,BuText DEFAULT '',Waehrung DEFAULT 'EUR',
                GesamtBruttoFW,GesamtBruttoSW,BezahltFW DEFAULT 0,BezahltSW DEFAULT 0,
                MinderungFW DEFAULT 0,MinderungSW DEFAULT 0,OffenFW,OffenSW,Entwurf DEFAULT 0,
                TageNetto DEFAULT 0,NichtMahnen DEFAULT 0,Mahnstufe DEFAULT 0,
                DatumMahnung1,DatumMahnung2,DatumMahnung3,DatumMahnung4);
            INSERT INTO POSTEN (_rowid,Datum,GesamtBruttoFW,GesamtBruttoSW)
                VALUES (1,'2024-12-01',10000,10000);
            INSERT INTO POSTEN (_rowid,Datum,GesamtBruttoFW,GesamtBruttoSW,Art)
                VALUES (2,'2025-01-15',-1000,-1000,1);
            INSERT INTO POSTEN (_rowid,Datum,GesamtBruttoFW,GesamtBruttoSW,Art,PKonto)
                VALUES (3,'2025-01-15',4000,4000,2,70000);
            INSERT INTO POSTEN (_rowid,Datum,GesamtBruttoFW,GesamtBruttoSW,Firma_id)
                VALUES (4,'2025-01-15',99999,99999,2);
            CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id);
            INSERT INTO POSTENPOSITION VALUES (1,1,1),(2,1,2),(3,1,3);
            CREATE TABLE ZAHLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum);
            CREATE TABLE ZAHLUNGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Zahlung_id,
                Postenposition_id,BetragZahlFW,BetragZahlSW,BetragMindFW,BetragMindSW);
        """)
        db.executescript(extra_sql)
        db.commit()
        db.close()
        plain = path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, "little"))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        path.write_bytes(encrypted)
        self.path, self.original = path, path.read_bytes()
        database = OfficeDatabase(path, key_path)
        self.addCleanup(database.close)
        return BusinessReader(database)

    def result(self, sql="", **kwargs):
        return reconcile_accounts(self.reader(sql), 1, 2025, "2025-01-31", **kwargs)

    def entry(self, result, kind, account):
        return next(row for row in result["entries"] if row["pruefung"] == kind and row["konto"] == account)

    def test_exact_signed_opening_and_credit_balances_reconcile(self):
        result = self.result()
        self.assertEqual(result["status"], "abgestimmt")
        self.assertEqual(result["total_entries"], 4)
        customer = self.entry(result, "Personenkonto_OP", 10000)
        self.assertEqual((customer["saldo_links_sw"], customer["saldo_rechts_sw"]), ("90.00", "90.00"))
        supplier = self.entry(result, "Personenkonto_OP", 70000)
        self.assertEqual((supplier["saldo_links_sw"], supplier["saldo_rechts_sw"]), ("-40.00", "-40.00"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_direct_collective_posting_is_real_difference_without_double_count(self):
        result = self.result("INSERT INTO JOURNAL VALUES (6,1,2,1400,0,250,0);")
        row = self.entry(result, "Hauptbuch_Personenkonten", 1400)
        self.assertEqual(row["status"], "abweichung")
        self.assertEqual((row["saldo_links_sw"], row["saldo_rechts_sw"], row["differenz_sw"]),
                         ("92.50", "90.00", "2.50"))
        self.assertEqual(row["gruende"], [])

    def test_op_difference_is_not_explained_away(self):
        result = self.result("UPDATE POSTEN SET GesamtBruttoSW=10200 WHERE _rowid=1;")
        row = self.entry(result, "Personenkonto_OP", 10000)
        self.assertEqual(row["status"], "abweichung")
        self.assertEqual(row["differenz_sw"], "-2.00")
        self.assertEqual(row["gruende"], [])

    def test_missing_payment_history_never_uses_calculated_partial_balance(self):
        result = self.result("UPDATE POSTEN SET BezahltFW=1000,BezahltSW=1000 WHERE _rowid=1;")
        row = self.entry(result, "Personenkonto_OP", 10000)
        self.assertEqual(row["status"], "nicht_abstimmbar")
        self.assertEqual(row["unbekannte_op_salden"], 1)
        self.assertIsNone(row["saldo_rechts_sw"])
        self.assertIsNone(row["differenz_sw"])
        self.assertEqual(row["bekannte_op_summe_sw"], "-10.00")
        self.assertTrue(any("Zahlungshistorie abweichend" in reason for reason in row["gruende"]))

    def test_future_payment_is_not_deducted_from_historical_balance(self):
        result = self.result("""
            UPDATE POSTEN SET BezahltFW=10000,BezahltSW=10000 WHERE _rowid=1;
            INSERT INTO ZAHLUNG VALUES (1,1,'2025-02-01');
            INSERT INTO ZAHLUNGSPOSITION VALUES (1,1,1,1,10000,10000,0,0);
        """)
        self.assertEqual(result["status"], "abgestimmt")
        self.assertEqual(self.entry(result, "Personenkonto_OP", 10000)["saldo_rechts_sw"], "90.00")

    def test_undated_payment_history_is_unknown(self):
        result = self.result("""
            UPDATE POSTEN SET BezahltFW=10000,BezahltSW=10000 WHERE _rowid=1;
            INSERT INTO ZAHLUNG VALUES (1,1,NULL);
            INSERT INTO ZAHLUNGSPOSITION VALUES (1,1,1,1,10000,10000,0,0);
        """)
        row = self.entry(result, "Personenkonto_OP", 10000)
        self.assertEqual(row["status"], "nicht_abstimmbar")
        self.assertIsNone(row["saldo_rechts_sw"])

    def test_missing_or_conflicting_account_definitions_and_mapping_block_comparison(self):
        for sql in (
            "DELETE FROM KONTO WHERE Firma_id=1 AND Nummer=10000;",
            "INSERT INTO KONTO VALUES (7,1,10000);",
            "UPDATE JOURNAL SET SammelKonto=0 WHERE _rowid=1;",
            "UPDATE JOURNAL SET SammelKonto=1600 WHERE _rowid=1;",
            "UPDATE ADRESSE SET LF_Konto=10000 WHERE _rowid=1;",
        ):
            with self.subTest(sql=sql):
                row = self.entry(self.result(sql), "Personenkonto_OP", 10000)
                self.assertEqual(row["status"], "nicht_abstimmbar")
                self.assertIsNone(row["differenz_sw"])
                self.assertTrue(row["gruende"])

    def test_currency_and_period_uncertainties_never_reconcile(self):
        for sql in (
            "UPDATE WIRTSCHAFTSJAHR SET Waehrung='CHF' WHERE _rowid=2;",
            "DELETE FROM WIRTSCHAFTSJAHR WHERE _rowid=2;",
            "UPDATE BUCHUNG SET Waehrung='USD' WHERE _rowid=2;",
            "UPDATE BUCHUNG SET Waehrung=NULL WHERE _rowid=2;",
            "UPDATE BUCHUNG SET Wj_id=2 WHERE _rowid=2;",
            "UPDATE BUCHUNG SET Datum='2024-12-31' WHERE _rowid=1;",
            "INSERT INTO WIRTSCHAFTSJAHR VALUES (4,1,'2024-12-01','2025-02-01','EUR');",
        ):
            with self.subTest(sql=sql):
                result = self.result(sql)
                self.assertEqual(result["status"], "nicht_abstimmbar")
                self.assertTrue(any(row["gruende"] for row in result["entries"]))

    def test_missing_roles_and_unknown_journal_accounts_are_visible(self):
        for sql in (
            "UPDATE ADRESSE SET KF_Konto=NULL WHERE _rowid=1;",
            "INSERT INTO JOURNAL VALUES (6,1,2,12345,1400,0,0);",
            "INSERT INTO JOURNAL VALUES (6,1,999,10000,1400,0,0);",
            "UPDATE POSTEN SET PKonto=NULL WHERE _rowid=1;",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(self.result(sql)["status"], "nicht_abstimmbar")

    def test_full_sums_and_status_counts_survive_all_pages(self):
        reader = self.reader("INSERT INTO JOURNAL VALUES (6,1,2,1400,0,250,0);")
        whole = reconcile_accounts(reader, 1, 2025, "2025-01-31")
        entries = []
        for offset in range(whole["total_entries"]):
            page = reconcile_accounts(reader, 1, 2025, "2025-01-31", limit=1, offset=offset)
            self.assertEqual(page["totals"], whole["totals"])
            self.assertEqual(page["status_anzahl"], whole["status_anzahl"])
            self.assertEqual(page["status"], whole["status"])
            entries.extend(page["entries"])
        self.assertEqual(entries, whole["entries"])
        beyond = reconcile_accounts(reader, 1, 2025, "2025-01-31", offset=100)
        self.assertEqual(beyond["entries"], [])
        self.assertEqual(beyond["totals"], whole["totals"])
        self.assertIsNone(beyond["next_offset"])

    def test_missing_year_and_out_of_year_cutoff_have_explicit_findings(self):
        reader = self.reader()
        for year, cutoff in ((2023, "2023-01-01"), (2025, "2026-01-01")):
            result = reconcile_accounts(reader, 1, year, cutoff)
            self.assertEqual(result["status"], "nicht_abstimmbar")
            self.assertEqual(result["entries"][0]["pruefung"], "Zeitraum")
            self.assertTrue(result["entries"][0]["gruende"])

    def test_shared_collective_account_and_invalid_op_dates_are_not_reconciled(self):
        for sql in (
            "UPDATE JOURNAL SET SammelKonto=1400 WHERE Konto=70000 AND Firma_id=1;",
            "UPDATE POSTEN SET Datum=NULL WHERE _rowid=1;",
            "UPDATE POSTEN SET Datum='2025-02-30' WHERE _rowid=1;",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(self.result(sql)["status"], "nicht_abstimmbar")

    def test_payment_in_different_system_currency_period_is_not_comparable(self):
        result = self.result("""
            INSERT INTO WIRTSCHAFTSJAHR VALUES (5,1,'2026-01-01','2026-12-31','CHF');
            UPDATE POSTEN SET BezahltFW=10000,BezahltSW=10000 WHERE _rowid=1;
            INSERT INTO ZAHLUNG VALUES (1,1,'2026-01-01');
            INSERT INTO ZAHLUNGSPOSITION VALUES (1,1,1,1,10000,10000,0,0);
        """)
        self.assertEqual(result["status"], "nicht_abstimmbar")
        row = self.entry(result, "Personenkonto_OP", 10000)
        self.assertTrue(any("Zahlungsperiode" in reason for reason in row["gruende"]))

    def test_invalid_parameters_fail(self):
        reader = self.reader()
        for args in ((True, 2025, "2025-01-31"), (1, 10000, "2025-01-31"),
                     (1, 2025, "2025-02-30"), (1, 2025, None)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                reconcile_accounts(reader, *args)
        for kwargs in ({"limit": 501}, {"limit": 0}, {"offset": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                reconcile_accounts(reader, 1, 2025, "2025-01-31", **kwargs)


class ReconciliationMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_registered_tool_uses_synthetic_data_and_full_totals(self):
        from mo_local_mcp.server import create_server

        fixture = ReconciliationTests(methodName="runTest")
        self.addCleanup(fixture.doCleanups)
        reader = fixture.reader("INSERT INTO JOURNAL VALUES (6,1,2,1400,0,250,0);")
        server = create_server(reader.database)
        tools = {tool.name: tool for tool in await server.list_tools()}
        self.assertIn("kontenabstimmung_pruefen", tools)
        schema = tools["kontenabstimmung_pruefen"].inputSchema
        self.assertEqual(set(schema["required"]), {"firma_id", "jahr", "stichtag"})
        result = await server.call_tool("kontenabstimmung_pruefen", {
            "firma_id": 1, "jahr": 2025, "stichtag": "2025-01-31", "anzahl": 1,
        })
        payload = json.loads(result[0].text)
        self.assertEqual(payload["status"], "abweichung")
        self.assertEqual(payload["anzahl_buchungszeilen"], 4)
        self.assertEqual(len(payload["buchungszeilen"]), 1)
        self.assertTrue(payload["gekuerzt"])
        self.assertEqual(payload["naechster_versatz"], 1)
        self.assertEqual(len(payload["summen"]), 4)
        self.assertEqual(fixture.path.read_bytes(), fixture.original)

    async def test_registered_tool_is_hidden_in_restricted_mode(self):
        from mo_local_mcp.server import create_server

        server = create_server(None, sensible_stammdaten_erlaubt=False)
        self.assertNotIn("kontenabstimmung_pruefen", {tool.name for tool in await server.list_tools()})
