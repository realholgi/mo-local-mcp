import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.analytics import cost_center_report, monthly_accounts, monthly_profit_and_loss
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.statements import StatementReader


class AnalyticsTests(unittest.TestCase):
    def reader(self, extra_sql=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "synthetisch.db"
        key_path = Path(directory.name) / "synthetisch.key"
        key = b"bericht-testkey!"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA page_size=1024")
        connection.executescript("""
            CREATE TABLE WIRTSCHAFTSJAHR (_rowid, Firma_id, Bezeichnung, Von, Bis, Waehrung, Gesperrt);
            INSERT INTO WIRTSCHAFTSJAHR VALUES
                (1,1,'2025/26','2025-04-01','2026-03-31','EUR',0),
                (1,2,'2025/26','2025-04-01','2026-03-31','CHF',0);
            CREATE TABLE KONTO (Firma_id, Nummer, Bezeichnung, Typ);
            INSERT INTO KONTO VALUES
                (1,1000,'Kasse','1'), (1,1400,'Forderungen','1'),
                (1,4000,'Aufwand','2'), (1,8000,'Ertrag','2'), (1,9000,'Vortrag','3'),
                (2,4000,'Andere Firma','1');
            CREATE TABLE BUCHUNG (_rowid, Firma_id, Wj_id, Datum, Art, Status, Waehrung);
            INSERT INTO BUCHUNG VALUES
                (1,1,1,'2025-04-01',2,1,'EUR'),
                (2,1,1,'2025-04-15',1,2,'USD'),
                (3,1,1,'2025-05-15',1,3,'USD'),
                (4,1,1,'2026-03-31',1,0,'EUR'),
                (2,2,1,'2025-04-15',1,2,'CHF'),
                (5,1,1,'2025-03-31',1,2,'EUR');
            CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY, Firma_id, Buchung_id, Konto, SammelKonto,
                BetragSoll, BetragHaben, BetragSollFW, BetragHabenFW, Kostenstelle1, Kostenstelle2);
            INSERT INTO JOURNAL VALUES
                (1,1,1,1000,0,10000,0,10000,0,'A','A'),
                (2,1,1,9000,0,0,10000,0,10000,NULL,NULL),
                (3,1,2,4000,0,1200,0,1500,0,'A','B'),
                (4,1,2,8000,0,0,3000,0,3750,'A','A'),
                (5,1,3,4000,0,-200,0,-250,0,'A','B'),
                (6,1,4,8000,0,0,500,0,500,'B',NULL),
                (7,1,2,10001,1400,500,0,625,0,NULL,NULL),
                (8,1,2,1400,1400,100,0,125,0,NULL,NULL),
                (9,2,2,4000,0,999999,0,999999,0,'A','B'),
                (10,1,5,4000,0,999999,0,999999,0,NULL,NULL);
            CREATE TABLE KONTOSTRUKTUR (_rowid, Firma_id);
            INSERT INTO KONTOSTRUKTUR VALUES (1,1),(1,2);
            CREATE TABLE STRUKTURPOSITION (Firma_id,Ks_id,ItemId,ParentId,VzWechsel,Bezeichnung,Kontoliste,Struktur);
            INSERT INTO STRUKTURPOSITION VALUES
                (1,1,1,0,0,'Aktiva','','A'),
                (1,1,2,0,0,'Passiva','','P'),
                (1,1,3,2,0,'Jahresergebnis','','B'),
                (1,1,10,0,0,'GuV','','G'),
                (1,1,11,10,0,'Betrieb','','G'),
                (1,1,12,11,1,'Ertrag','8000','G'),
                (1,1,13,11,1,'Aufwand','4000','G'),
                (2,1,10,0,0,'Andere Firma','4000','G');
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
        return StatementReader(database)

    def test_cost_centers_deduplicate_fields_but_not_distinct_centers(self):
        report = cost_center_report(self.reader(), 1, '2025-04-01', '2026-03-31')
        usd = [row for row in report['kostenstellen'] if row['fw_waehrung'] == 'USD']
        a = next(row for row in usd if row['kostenstelle'] == 'A')
        b = next(row for row in usd if row['kostenstelle'] == 'B')
        self.assertEqual(a['journalzeilen'], 3)
        self.assertEqual(a['sw']['bewegungen'], {'soll': '10.00', 'haben': '30.00', 'saldo': '-20.00'})
        self.assertEqual(b['fw']['bewegungen']['soll'], '12.50')
        total = next(row for row in report['gesamtwerte'] if row['fw_waehrung'] == 'USD')
        self.assertEqual(total['journalzeilen'], 5)
        self.assertEqual(total['sw']['bewegungen']['soll'], '16.00')
        self.assertEqual(total['sw_waehrung'], 'EUR')
        euro_a = next(row for row in report['kostenstellen'] if row['kostenstelle'] == 'A' and row['fw_waehrung'] == 'EUR')
        self.assertEqual(euro_a['sw']['eroeffnung']['saldo'], '100.00')
        self.assertIn('nicht addiert', report['grundlage'])

    def test_cost_center_filter_and_pages_preserve_full_filtered_totals(self):
        reader = self.reader()
        full = cost_center_report(reader, 1, cost_center='B')
        page = cost_center_report(reader, 1, cost_center='B', limit=1)
        self.assertEqual(page['gesamtwerte'], full['gesamtwerte'])
        self.assertEqual(page['anzahl_gesamt'], 2)
        self.assertEqual(page['naechster_versatz'], 1)
        tail = cost_center_report(reader, 1, cost_center='B', limit=1, offset=1)
        self.assertFalse(tail['gekuerzt'])
        self.assertIsNone(tail['naechster_versatz'])

    def test_missing_currencies_remain_unknown(self):
        reader = self.reader("UPDATE WIRTSCHAFTSJAHR SET Waehrung=NULL WHERE Firma_id=1; UPDATE BUCHUNG SET Waehrung=NULL WHERE Firma_id=1;")
        report = cost_center_report(reader, 1)
        self.assertFalse(report['kostenstellen'][0]['waehrungen_bekannt'])
        self.assertIsNone(report['kostenstellen'][0]['sw_waehrung'])
        account = monthly_accounts(reader, 1, 2025, 1000, 1000)['konten'][0]
        self.assertIsNone(account['monate'][0]['endsaldo'])

    def test_noncalendar_months_openings_and_collective_accounts(self):
        report = monthly_accounts(self.reader(), 1, 2025)
        self.assertEqual(report['gesamtwerte'][0]['monat'], '2025-04')
        self.assertEqual(report['gesamtwerte'][-1]['monat'], '2026-03')
        self.assertEqual(len(report['gesamtwerte']), 12)
        self.assertNotIn(10001, [row['konto'] for row in report['konten']])
        collective = next(row for row in report['konten'] if row['konto'] == 1400)
        self.assertEqual(collective['monate'][0]['bewegungen']['soll'], '6.00')
        cash = next(row for row in report['konten'] if row['konto'] == 1000)
        self.assertEqual(cash['monate'][0]['eroeffnung']['saldo'], '100.00')
        self.assertEqual(cash['monate'][-1]['endsaldo'], '100.00')
        expense = next(row for row in report['konten'] if row['konto'] == 4000)
        self.assertEqual(expense['monate'][1]['bewegungen']['soll'], '-2.00')
        self.assertEqual(expense['monate'][-1]['endsaldo'], '10.00')

    def test_more_than_500_journal_rows_and_accounts_are_complete(self):
        reader = self.reader("""
            WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<510)
            INSERT INTO JOURNAL SELECT 100+x,1,2,10000+x,0,1,0,1,0,'M','M' FROM n;
            WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<510)
            INSERT INTO KONTO SELECT 1,10000+x,'Synthetisch','1' FROM n;
        """)
        centers = cost_center_report(reader, 1, cost_center='M')
        self.assertEqual(centers['kostenstellen'][0]['journalzeilen'], 510)
        self.assertEqual(centers['gesamtwerte'][0]['sw']['bewegungen']['soll'], '5.10')
        first = monthly_accounts(reader, 1, 2025, 10001, 10510, limit=500)
        self.assertEqual(first['anzahl_gesamt'], 510)
        self.assertEqual(len(first['konten']), 500)
        last = monthly_accounts(reader, 1, 2025, 10001, 10510, limit=500, offset=500)
        self.assertEqual(len(last['konten']), 10)
        self.assertEqual(last['gesamtwerte'], first['gesamtwerte'])
        self.assertEqual(last['gesamtwerte'][0]['bewegungen']['soll'], '5.10')
        self.assertFalse(last['gekuerzt'])

    def test_profit_rolls_up_saved_layout_without_monthly_balance_requirement(self):
        report = monthly_profit_and_loss(self.reader(), 1, 2025)
        self.assertEqual(report['jahresbewegungsgewinn'], '25.00')
        self.assertEqual([row['gewinn'] for row in report['monate'][:2]], ['18.00', '2.00'])
        self.assertEqual(report['monate'][-1]['gewinn'], '5.00')
        april = report['monate'][0]['positionen']
        self.assertEqual([row['position_id'] for row in april], [10,11,12,13])
        self.assertEqual([row['betrag'] for row in april], ['18.00','18.00','30.00','-12.00'])
        self.assertEqual(sum(float(row['gewinn']) for row in report['monate']), 25.0)

    def test_profit_excludes_opening_on_success_account(self):
        reader = self.reader("INSERT INTO JOURNAL VALUES (11,1,1,8000,0,0,2000,0,2000,'A',NULL);")
        report = monthly_profit_and_loss(reader, 1, 2025)
        self.assertEqual(report['jahresbewegungsgewinn'], '25.00')
        self.assertEqual(report['ausgeschlossene_eroeffnungen'][0]['eroeffnung']['haben'], '120.00')

    def test_profit_rejects_missing_duplicate_and_cross_section_assignments(self):
        changes = [
            "UPDATE STRUKTURPOSITION SET Kontoliste='' WHERE Firma_id=1 AND ItemId=13;",
            "UPDATE STRUKTURPOSITION SET Kontoliste='4000' WHERE Firma_id=1 AND ItemId=11;",
            "UPDATE STRUKTURPOSITION SET Kontoliste='4000' WHERE Firma_id=1 AND ItemId=1;",
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'GuV-Zuordnung'):
                monthly_profit_and_loss(self.reader(change), 1, 2025)

    def test_profit_rejects_balance_account_in_profit_layout(self):
        reader = self.reader("UPDATE STRUKTURPOSITION SET Kontoliste='4000,1400' WHERE Firma_id=1 AND ItemId=13;")
        with self.assertRaisesRegex(ValueError, 'kein Erfolgskonto'):
            monthly_profit_and_loss(reader, 1, 2025)

    def test_profit_checks_offsetting_months_even_with_zero_annual_balance(self):
        reader = self.reader("""
            UPDATE STRUKTURPOSITION SET Kontoliste='' WHERE Firma_id=1 AND ItemId=13;
            UPDATE JOURNAL SET BetragSoll=-1200 WHERE _rowid=5;
        """)
        with self.assertRaisesRegex(ValueError, 'GuV-Zuordnung'):
            monthly_profit_and_loss(reader, 1, 2025)

    def test_validation_and_explicit_structure_selection(self):
        reader = self.reader()
        with self.assertRaises(ValueError):
            monthly_accounts(reader, 1, 2025, limit=501)
        with self.assertRaises(ValueError):
            cost_center_report(reader, 1, date_from='2025-04-31')
        with self.assertRaises(ValueError):
            monthly_accounts(reader, 1, 2025, 8000, 4000)
        with self.assertRaisesRegex(ValueError, 'Wirtschaftsjahr'):
            monthly_accounts(reader, 1, 2026)
        with self.assertRaises(ValueError):
            monthly_profit_and_loss(reader, 1, 2025, structure_id=2)
