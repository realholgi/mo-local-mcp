from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.statements import StatementReader


def position(section, item_id):
    return next(row for row in section["lines"] if row["item_id"] == item_id)


class StatementTests(unittest.TestCase):
    def reader(self, extra_sql=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "testfirma.db"
        key_path = Path(directory.name) / "testfirma.key"
        key = b"bericht-testkey!"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA page_size=1024")
        connection.executescript("""
            CREATE TABLE WIRTSCHAFTSJAHR (_rowid INTEGER PRIMARY KEY, Firma_id, Bezeichnung, Von, Bis, Waehrung, Gesperrt);
            INSERT INTO WIRTSCHAFTSJAHR VALUES
                (1,1,'2024','2024-01-01','2024-12-31','EUR',1),
                (2,1,'2025','2025-01-01','2025-12-31','EUR',1),
                (3,2,'2025','2025-01-01','2025-12-31','EUR',1);
            CREATE TABLE KONTOSTRUKTUR (_rowid INTEGER PRIMARY KEY, Firma_id);
            INSERT INTO KONTOSTRUKTUR VALUES (1,1),(2,2);
            CREATE TABLE STRUKTURPOSITION (_rowid INTEGER PRIMARY KEY, Firma_id, Ks_id, ItemId, ParentId,
                VzWechsel, Bezeichnung, Kontoliste, Struktur);
            INSERT INTO STRUKTURPOSITION(Firma_id,Ks_id,ItemId,ParentId,VzWechsel,Bezeichnung,Kontoliste,Struktur) VALUES
                (1,1,1,0,0,'Aktiva','','A'),
                (1,1,2,1,0,'Ausstattung','400','A'),
                (1,1,3,1,0,'Forderungen','1400','A'),
                (1,1,4,1,0,'Verbindlichkeitskonten im Soll','1700','A'),
                (1,1,10,0,0,'Passiva','','P'),
                (1,1,11,10,0,'Eigenkapital','880','P'),
                (1,1,12,10,0,'Verbindlichkeiten einschließlich Steuersollsalden','1576,1780,1790,1700,1400','P'),
                (1,1,13,11,0,'Jahresergebnis','','B'),
                (1,1,20,0,0,'Gewinn und Verlust','','G'),
                (1,1,21,20,1,'Erlöse','8400','G'),
                (1,1,22,20,1,'Aufwendungen','4920','G'),
                (1,1,23,20,0,'Ausgleichsgruppe','','G'),
                (1,1,24,23,1,'Ausgleichsaufwand','4950','G'),
                (1,1,25,23,1,'Ausgleichsertrag','2736','G'),
                (2,2,1,0,0,'Gliederung anderer Firma','','A');
            CREATE TABLE KONTO (Firma_id,Nummer,Bezeichnung,Typ);
            INSERT INTO KONTO VALUES
                (1,400,'Ausstattung','1'),(1,1400,'Forderungen aus Lieferungen und Leistungen','1'),
                (1,1576,'Vorsteuer','1'),(1,1780,'Umsatzsteuervorauszahlungen','1'),(1,1790,'Umsatzsteuer Vorjahr','1'),
                (1,1700,'Verbindlichkeiten','1'),(1,880,'Kapital','1'),(1,8400,'Erlöse','2'),
                (1,4920,'Telefon','2'),(1,4950,'Aufwand','2'),(1,2736,'Ertrag','2'),
                (1,9000,'Vortragskonto','3'),(1,9008,'Forderungsvortrag','3'),(1,10001,'Testkunde','4'),
                (2,400,'Ausstattung anderer Firma','1');
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Wj_id,Datum,Status);
            INSERT INTO BUCHUNG VALUES
                (1,1,1,'2024-01-01',2),(2,1,2,'2025-01-01',3),(3,2,3,'2025-01-01',2);
            CREATE TABLE JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben);
            INSERT INTO JOURNAL VALUES
                (1,1,400,0,400,0),(1,1,10001,1400,500,0),
                (1,1,1576,0,100,0),(1,1,1780,0,200,0),(1,1,1790,0,300,0),
                (1,1,1700,0,0,1000),(1,1,8400,0,0,2000),(1,1,4920,0,800,0),(1,1,880,0,700,0),
                (1,2,400,0,500,0),(1,2,10001,1400,1000,0),
                (1,2,1576,0,200,0),(1,2,1780,0,300,0),(1,2,1790,0,400,0),
                (1,2,1700,0,0,2000),(1,2,8400,0,0,3000),(1,2,4920,0,1000,0),
                (1,2,880,0,1600,0),(1,2,4950,0,100,0),(1,2,2736,0,0,100),
                (1,2,9000,0,7000,0),(1,2,9008,0,0,7000),
                (2,3,400,0,999999,0);
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

    def account_reader(self, extra_sql=""):
        return self.reader("""
            ALTER TABLE BUCHUNG ADD COLUMN Art INTEGER;
            ALTER TABLE BUCHUNG ADD COLUMN BelegNr TEXT;
            UPDATE BUCHUNG SET Art=1,BelegNr='BASIS';
            ALTER TABLE JOURNAL ADD COLUMN _rowid INTEGER;
            ALTER TABLE JOURNAL ADD COLUMN Position INTEGER;
            ALTER TABLE JOURNAL ADD COLUMN Text TEXT;
            ALTER TABLE JOURNAL ADD COLUMN GegenKonto INTEGER;
            ALTER TABLE JOURNAL ADD COLUMN Nummer TEXT;
            ALTER TABLE JOURNAL ADD COLUMN NummerLong INTEGER;
            ALTER TABLE JOURNAL ADD COLUMN Storno INTEGER;
            UPDATE JOURNAL SET _rowid=rowid,Position=1,Text='Basis',GegenKonto=0,
                Nummer='basis',NummerLong=rowid,Storno=0;
            INSERT INTO KONTO VALUES (1,1000,'Kasse','1'),(2,1000,'Kasse anderer Firma','1');
            INSERT INTO BUCHUNG VALUES
                (10,1,2,'2025-01-01',2,2,'EB1'),(11,1,2,'2025-01-01',2,2,'EB2'),
                (12,1,2,'2025-01-02',2,1,'000001'),
                (13,1,2,'2025-01-31',2,1,'000001'),
                (14,1,2,'2025-01-31',3,1,'000002'),
                (15,1,2,'2025-01-31',2,1,'000003'),
                (16,2,3,'2025-01-02',2,1,'VERTRAULICH');
            INSERT INTO JOURNAL VALUES
                (1,10,1000,0,10000,0,100,1,'Eröffnung Soll',9000,'EB1',100,0),
                (1,11,1000,0,0,4000,101,1,'Eröffnung Haben',9000,'EB2',101,0),
                (1,12,1000,0,0,1000,102,1,'Erster Aufwand',4920,'J1',102,0),
                (1,13,1000,0,0,2000,103,1,'Aufwand vor Storno',4920,'J3',300,0),
                (1,14,1000,0,3000,0,104,1,'Storniertes Original',1200,'J2',200,1),
                (1,14,1000,0,-3000,0,105,2,'Umkehrbuchung',1200,'J4',400,2),
                (1,15,1000,0,2000,0,106,1,'Private Zahlungskorrektur',1890,'J5',500,0),
                (2,16,1000,0,999999,0,107,1,'Vertraulicher Vorgang anderer Firma',1890,'J6',600,0);
        """ + extra_sql + """
            ALTER TABLE JOURNAL ADD COLUMN Steuersatz TEXT;
            UPDATE JOURNAL SET Steuersatz=CASE _rowid
                WHEN 102 THEN 'VSt19' WHEN 103 THEN '-'
                WHEN 104 THEN 'USt7' WHEN 105 THEN '' ELSE NULL END;
        """)

    def test_account_statement_separates_opening_from_turnovers(self):
        report = self.account_reader().account_statement(1,2025,1000)
        self.assertEqual(report['opening'],{'entries':2,'debit':'100.00','credit':'40.00','balance':'60.00'})
        self.assertEqual(report['turnovers'],{'debit':'20.00','credit':'30.00'})
        self.assertEqual(report['closing_balance'],'50.00')
        self.assertEqual(report['total_entries'],5)
        self.assertEqual([r['balance'] for r in report['entries']],['50.00','30.00','60.00','30.00','50.00'])
        self.assertEqual(report['entries'][1]['text'],'Aufwand vor Storno')
        self.assertEqual([r['storno'] for r in report['entries']],[0,0,1,2,0])
        self.assertEqual(report['entries'][3]['debit'],'-30.00')
        self.assertFalse(report['truncated'])

    def test_account_statement_preserves_stored_tax_codes(self):
        reader = self.account_reader()
        report = reader.account_statement(1,2025,1000)
        self.assertEqual(
            [entry['tax_code'] for entry in report['entries']],
            ['VSt19','-','USt7','',None],
        )
        page = reader.account_statement(1,2025,1000,limit=1,offset=1)
        self.assertEqual(page['entries'][0]['tax_code'],'-')

    def test_account_statement_page_keeps_full_running_balance_and_totals(self):
        reader = self.account_reader()
        first = reader.account_statement(1,2025,1000,limit=2)
        second = reader.account_statement(1,2025,1000,limit=2,offset=first['next_offset'])
        self.assertEqual(second['entries'][0]['balance'],'60.00')
        self.assertEqual(second['opening'],first['opening'])
        self.assertEqual(second['turnovers'],first['turnovers'])
        self.assertEqual(second['closing_balance'],'50.00')
        self.assertEqual(second['total_entries'],5)
        last = reader.account_statement(1,2025,1000,limit=2,offset=second['next_offset'])
        self.assertEqual([r['text'] for r in last['entries']],['Private Zahlungskorrektur'])
        self.assertIsNone(last['next_offset'])

    def test_account_statement_collective_entries_are_not_duplicated(self):
        reader = self.account_reader("""
            INSERT INTO JOURNAL VALUES (1,2,1400,1400,50,0,108,1,'Direktes Sammelkonto',880,'JS',700,0);
        """)
        collective = reader.account_statement(1,2025,1400)
        personal = reader.account_statement(1,2025,10001)
        self.assertEqual(collective['total_entries'],2)
        self.assertEqual(collective['closing_balance'],'10.50')
        self.assertEqual(personal['total_entries'],1)
        self.assertEqual(personal['closing_balance'],'10.00')

    def test_account_statement_empty_account_and_missing_account_differ(self):
        reader = self.account_reader("INSERT INTO KONTO VALUES (1,1001,'Unbenutzte Kasse','1');")
        empty = reader.account_statement(1,2025,1001)
        self.assertEqual(empty['entries'],[])
        self.assertEqual(empty['turnovers'],{'debit':'0.00','credit':'0.00'})
        self.assertEqual(empty['closing_balance'],'0.00')
        with self.assertRaisesRegex(ValueError,'Kontendefinition'):
            reader.account_statement(1,2025,9999)
        with self.assertRaises(ValueError):
            reader.account_statement(1,2025,1000,limit=501)

    def test_account_statement_negative_balance_has_haben_side(self):
        reader = self.account_reader("""
            INSERT INTO JOURNAL VALUES (1,15,1000,0,0,10000,108,2,'Großer Aufwand',4920,'J7',800,0);
        """)
        report = reader.account_statement(1,2025,1000)
        self.assertEqual(report['entries'][-1]['balance'],'-50.00')
        self.assertEqual(report['entries'][-1]['balance_side'],'H')
        self.assertEqual(report['closing_balance'],'-50.00')

    def test_trial_balance_separates_opening_and_signed_turnovers(self):
        report = self.account_reader().trial_balance(1,2025,1000,1000)
        self.assertEqual(report['accounts'],[{
            'account':1000, 'name':'Kasse',
            'opening':{'debit':'100.00','credit':'40.00','balance':'60.00'},
            'turnovers':{'debit':'20.00','credit':'30.00'},
            'closing_balance':'50.00', 'balance_side':'S',
        }])
        self.assertEqual(report['totals'],{
            'opening':{'debit':'100.00','credit':'40.00','balance':'60.00'},
            'turnovers':{'debit':'20.00','credit':'30.00'},
            'closing_balance':'50.00',
        })
        self.assertEqual(report['currency'],'EUR')
        self.assertEqual(report['fiscal_year']['_rowid'],2)
        self.assertEqual(report['total_accounts'],1)
        self.assertFalse(report['truncated'])
        self.assertIsNone(report['next_offset'])

    def test_trial_balance_collective_accounts_and_carryforwards_are_retained(self):
        reader = self.account_reader("""
            INSERT INTO JOURNAL VALUES (1,2,1400,1400,50,0,108,1,'Direktes Sammelkonto',880,'JS',700,0);
        """)
        report = reader.trial_balance(1,2025,1400,1400)
        self.assertEqual([row['account'] for row in report['accounts']],[1400])
        self.assertEqual(report['accounts'][0]['closing_balance'],'10.50')
        self.assertEqual(report['totals']['turnovers'],{'debit':'10.50','credit':'0.00'})
        self.assertEqual(reader.trial_balance(1,2025,10001,10001)['accounts'],[])
        carryforwards = reader.trial_balance(1,2025,9000,9008)
        self.assertEqual([row['account'] for row in carryforwards['accounts']],[9000,9008])
        self.assertEqual([row['closing_balance'] for row in carryforwards['accounts']],['70.00','-70.00'])
        self.assertEqual([row['balance_side'] for row in carryforwards['accounts']],['S','H'])

    def test_trial_balance_keeps_zero_accounts_nulls_and_raw_name_templates(self):
        reader = self.account_reader("""
            INSERT INTO KONTO VALUES (1,1001,'Kasse {Jahr}','1'),(1,1002,'Unbebucht','1');
            INSERT INTO BUCHUNG VALUES (17,1,2,'2025-06-01',NULL,NULL,'NULLART');
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben)
                VALUES (1,17,1001,0,500,500),(1,17,1001,0,NULL,NULL);
            ALTER TABLE JOURNAL ADD COLUMN BetragSollFW;
            ALTER TABLE JOURNAL ADD COLUMN BetragHabenFW;
            UPDATE JOURNAL SET BetragSollFW=987654,BetragHabenFW=123456;
            DELETE FROM KONTOSTRUKTUR;
            DELETE FROM STRUKTURPOSITION;
        """)
        report = reader.trial_balance(1,2025,1001,1002)
        self.assertEqual(report['accounts'],[{
            'account':1001, 'name':'Kasse {Jahr}',
            'opening':{'debit':'0.00','credit':'0.00','balance':'0.00'},
            'turnovers':{'debit':'5.00','credit':'5.00'},
            'closing_balance':'0.00', 'balance_side':'',
        }])
        self.assertEqual(report['total_accounts'],1)
        self.assertEqual(report['totals']['turnovers'],{'debit':'5.00','credit':'5.00'})

    def test_trial_balance_excludes_wrong_company_year_and_outside_dates(self):
        reader = self.account_reader("""
            INSERT INTO BUCHUNG VALUES
                (17,1,1,'2025-06-01',2,1,'FALSCHES-JAHR'),
                (18,1,2,'2024-12-31',2,1,'ZU-FRUEH'),
                (19,1,2,'2026-01-01',2,1,'ZU-SPAET');
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben)
                VALUES (1,17,1000,0,999999,0),(1,18,1000,0,999999,0),
                    (1,19,1000,0,999999,0),(2,12,1000,0,999999,0),
                    (1,16,1000,0,999999,0);
        """)
        report = reader.trial_balance(1,2025,1000,1000)
        self.assertEqual(report['totals']['closing_balance'],'50.00')
        self.assertEqual(report['totals']['turnovers'],{'debit':'20.00','credit':'30.00'})

    def test_trial_balance_noncalendar_year_includes_both_boundaries(self):
        reader = self.account_reader("""
            UPDATE WIRTSCHAFTSJAHR SET Von='2025-07-01',Bis='2026-06-30',Waehrung='USD' WHERE _rowid=2;
            INSERT INTO BUCHUNG VALUES
                (17,1,2,'2025-07-01',NULL,2,'ERÖFFNUNG'),
                (18,1,2,'2026-06-30',99,NULL,'SCHLUSS'),
                (19,1,2,'2025-06-30',2,1,'ZU-FRUEH'),
                (20,1,2,'2026-07-01',2,1,'ZU-SPAET');
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben)
                VALUES (1,17,1000,0,700,0),(1,18,1000,0,0,200),
                    (1,19,1000,0,999999,0),(1,20,1000,0,999999,0);
        """)
        report = reader.trial_balance(1,2025,1000,1000)
        self.assertEqual(report['currency'],'USD')
        self.assertEqual(report['fiscal_year']['Von'],'2025-07-01')
        self.assertEqual(report['fiscal_year']['Bis'],'2026-06-30')
        self.assertEqual(report['totals'],{
            'opening':{'debit':'7.00','credit':'0.00','balance':'7.00'},
            'turnovers':{'debit':'0.00','credit':'2.00'}, 'closing_balance':'5.00',
        })

    def test_trial_balance_pages_keep_full_filtered_totals(self):
        reader = self.account_reader()
        full = reader.trial_balance(1,2025)
        first = reader.trial_balance(1,2025,limit=2)
        self.assertTrue(first['truncated'])
        self.assertEqual(first['next_offset'],2)
        accounts = list(first['accounts'])
        page = first
        while page['next_offset'] is not None:
            page = reader.trial_balance(1,2025,limit=2,offset=page['next_offset'])
            self.assertEqual(page['totals'],full['totals'])
            self.assertEqual(page['total_accounts'],full['total_accounts'])
            accounts.extend(page['accounts'])
        self.assertEqual(accounts,full['accounts'])
        self.assertEqual(first['totals'],full['totals'])
        self.assertEqual(len({row['account'] for row in accounts}),full['total_accounts'])
        beyond = reader.trial_balance(1,2025,offset=1000)
        self.assertEqual(beyond['accounts'],[])
        self.assertEqual(beyond['totals'],full['totals'])
        self.assertEqual(beyond['total_accounts'],full['total_accounts'])
        self.assertFalse(beyond['truncated'])
        self.assertIsNone(beyond['next_offset'])

    def test_trial_balance_more_than_500_groups_are_summed_before_pagination(self):
        reader = self.account_reader("""
            WITH RECURSIVE n(value) AS (SELECT 20000 UNION ALL SELECT value+1 FROM n WHERE value<20500)
                INSERT INTO KONTO SELECT 1,value,'Synthetisches Konto','1' FROM n;
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben)
                SELECT 1,12,Nummer,0,100,0 FROM KONTO WHERE Firma_id=1 AND Nummer BETWEEN 20000 AND 20500;
        """)
        first = reader.trial_balance(1,2025,20000,20500,limit=500)
        last = reader.trial_balance(1,2025,20000,20500,limit=500,offset=first['next_offset'])
        self.assertEqual(first['total_accounts'],501)
        self.assertEqual(len(first['accounts']),500)
        self.assertEqual(first['next_offset'],500)
        self.assertEqual([row['account'] for row in last['accounts']],[20500])
        self.assertEqual(last['total_accounts'],501)
        self.assertFalse(last['truncated'])
        self.assertIsNone(last['next_offset'])
        self.assertEqual(first['totals'],{
            'opening':{'debit':'0.00','credit':'0.00','balance':'0.00'},
            'turnovers':{'debit':'501.00','credit':'0.00'}, 'closing_balance':'501.00',
        })
        self.assertEqual(last['totals'],first['totals'])

    def test_trial_balance_empty_filter_has_zero_totals(self):
        reader = self.account_reader()
        for bounds in ({'account_from':99999},{'account_to':0},{'account_from':1002,'account_to':1002}):
            with self.subTest(bounds=bounds):
                report = reader.trial_balance(1,2025,**bounds)
                self.assertEqual(report['accounts'],[])
                self.assertEqual(report['total_accounts'],0)
                self.assertEqual(report['totals'],{
                    'opening':{'debit':'0.00','credit':'0.00','balance':'0.00'},
                    'turnovers':{'debit':'0.00','credit':'0.00'}, 'closing_balance':'0.00',
                })
                self.assertFalse(report['truncated'])
                self.assertIsNone(report['next_offset'])

    def test_trial_balance_requires_unique_fiscal_year(self):
        reader = self.account_reader()
        with self.assertRaisesRegex(ValueError,'genau ein Wirtschaftsjahr'):
            reader.trial_balance(1,2026)
        duplicate = self.account_reader("""
            INSERT INTO WIRTSCHAFTSJAHR VALUES (4,1,'Doppeltes Jahr','2025-07-01','2026-06-30','EUR',0);
        """)
        with self.assertRaisesRegex(ValueError,'genau ein Wirtschaftsjahr'):
            duplicate.trial_balance(1,2025)

    def test_trial_balance_requires_unique_definitions_for_all_filtered_accounts(self):
        cases = (
            "DELETE FROM KONTO WHERE Firma_id=1 AND Nummer=1000;",
            "INSERT INTO KONTO VALUES (1,1000,'Doppelte Kasse','1');",
        )
        for sql in cases:
            with self.subTest(sql=sql):
                reader = self.account_reader(sql)
                with self.assertRaisesRegex(ValueError,'Genau eine Kontendefinition in dieser Firma erwartet'):
                    reader.trial_balance(1,2025,1000,1000,offset=10)
                outside = reader.trial_balance(1,2025,1400,1400)
                self.assertEqual(outside['accounts'][0]['closing_balance'],'10.00')

    def test_trial_balance_validates_ids_bounds_and_pagination(self):
        reader = self.account_reader()
        for company, year, arguments in (
            (0,2025,{}), (True,2025,{}), (1,0,{}), (1,10000,{}),
            (1,2025,{'account_from':-1}), (1,2025,{'account_to':-1}),
            (1,2025,{'account_from':'1000'}), (1,2025,{'account_to':True}),
            (1,2025,{'limit':0}), (1,2025,{'limit':501}),
            (1,2025,{'limit':1.5}), (1,2025,{'offset':-1}),
            (1,2025,{'offset':False}),
        ):
            with self.subTest(company=company,year=year,arguments=arguments):
                with self.assertRaises(ValueError):
                    reader.trial_balance(company,year,**arguments)
        with self.assertRaisesRegex(ValueError,'konto_von darf konto_bis nicht überschreiten'):
            reader.trial_balance(1,2025,1001,1000)

    def test_tax_debits_stay_in_stored_liability_position(self):
        report = self.reader().financial_statements(1,2025)
        assets = report['balance_sheet']['assets']
        liabilities = report['balance_sheet']['liabilities_and_equity']
        self.assertEqual(assets['total'],'15.00')
        self.assertEqual(liabilities['total'],'15.00')
        taxes = {row['account']:row['amount'] for row in position(liabilities,12)['accounts']}
        self.assertEqual(taxes,{1576:'-2.00',1700:'20.00',1780:'-3.00',1790:'-4.00'})
        self.assertEqual(position(liabilities,12)['amount'],'11.00')
        self.assertEqual(position(liabilities,11)['amount'],'4.00')

    def test_collective_accounts_and_prior_year_are_not_double_counted(self):
        report = self.reader().financial_statements(1,2025)
        assets = report['balance_sheet']['assets']
        receivables = position(assets,3)
        self.assertEqual(receivables['accounts'],[{
            'account':1400,'name':'Forderungen aus Lieferungen und Leistungen','amount':'10.00','previous_amount':'5.00',
            'absolute_change':'5.00','percentage_change':'100.00','percentage_basis':'absolute_previous'}])
        self.assertEqual(assets['previous_total'],'9.00')
        self.assertEqual(report['previous_fiscal_year']['_rowid'],1)
        self.assertEqual(report['profit_and_loss']['total'],'20.00')
        self.assertEqual(report['profit_and_loss']['previous_total'],'12.00')
        result = position(report['balance_sheet']['liabilities_and_equity'],13)
        self.assertEqual((result['amount'],result['previous_amount']),('20.00','12.00'))

    def test_zero_net_group_keeps_offsetting_accounts_visible(self):
        profit = self.reader().financial_statements(1,2025)['profit_and_loss']
        self.assertEqual(position(profit,23)['amount'],'0.00')
        self.assertEqual(position(profit,24)['amount'],'-1.00')
        self.assertEqual(position(profit,25)['amount'],'1.00')

    def test_dual_listed_accounts_switch_sides_without_moving_tax_debits(self):
        reader = self.reader("""
            INSERT INTO JOURNAL VALUES (1,2,10001,1400,0,2000),(1,2,880,0,2000,0);
        """)
        report = reader.financial_statements(1,2025,include_previous_year=False)
        assets = report['balance_sheet']['assets']
        liabilities = report['balance_sheet']['liabilities_and_equity']
        self.assertNotIn(3,[r['item_id'] for r in assets['lines']])
        amounts = {r['account']:r['amount'] for r in position(liabilities,12)['accounts']}
        self.assertEqual(amounts[1400],'10.00')
        self.assertEqual(amounts[1576],'-2.00')
        self.assertEqual(assets['total'],liabilities['total'])
        self.assertEqual(position(liabilities,11)['amount'],'-16.00')

    def test_missing_prior_year_has_null_not_invented_zero_comparison(self):
        report = self.reader().financial_statements(1,2024)
        self.assertIsNone(report['previous_fiscal_year'])
        self.assertIsNone(report['profit_and_loss']['previous_total'])
        self.assertIsNone(report['profit_and_loss']['lines'][0]['previous_amount'])

    def test_unmapped_or_ambiguous_nonzero_accounts_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError,'fehlt die Berichtszuordnung oder sie ist mehrdeutig'):
            self.reader("""
                INSERT INTO KONTO VALUES (1,9999,'Nicht zugeordnet','1');
                INSERT INTO JOURNAL VALUES (1,2,9999,0,100,0),(1,2,880,0,0,100);
            """).financial_statements(1,2025)
        with self.assertRaisesRegex(ValueError,'fehlt die Berichtszuordnung oder sie ist mehrdeutig'):
            self.reader("""
                INSERT INTO STRUKTURPOSITION(Firma_id,Ks_id,ItemId,ParentId,VzWechsel,Bezeichnung,Kontoliste,Struktur)
                VALUES (1,1,26,20,1,'Doppelte Erlösposition','8400','G');
            """).financial_statements(1,2025)

    def test_unbalanced_journal_or_control_accounts_are_not_hidden(self):
        with self.assertRaisesRegex(ValueError,'nicht ausgeglichen'):
            self.reader('INSERT INTO JOURNAL VALUES (1,2,400,0,1,0);').financial_statements(1,2025)
        with self.assertRaisesRegex(ValueError,'nicht ausgeglichen'):
            self.reader('INSERT INTO JOURNAL VALUES (1,2,9000,0,1,0),(1,2,880,0,0,1);').financial_statements(1,2025)

    def test_company_layout_and_year_must_be_unambiguous(self):
        reader = self.reader()
        with self.assertRaisesRegex(ValueError,'in dieser Firma nicht gefunden'):
            reader.financial_statements(1,2025,structure_id=2)
        with self.assertRaisesRegex(ValueError,'Wirtschaftsjahr'):
            reader.financial_statements(3,2025)
        with self.assertRaises(ValueError):
            reader.financial_statements(True,2025)
        comparison = self.reader("UPDATE WIRTSCHAFTSJAHR SET Waehrung='USD' WHERE _rowid=1;").financial_statements(1,2025)
        self.assertFalse(comparison['comparison']['comparable'])
        self.assertIsNone(comparison['profit_and_loss']['absolute_change'])

    def test_layout_larger_than_query_page_is_read_completely(self):
        reader = self.reader("""
            WITH RECURSIVE n(x) AS (VALUES(30) UNION ALL SELECT x+1 FROM n WHERE x<540)
            INSERT INTO STRUKTURPOSITION(Firma_id,Ks_id,ItemId,ParentId,VzWechsel,Bezeichnung,Kontoliste,Struktur)
            SELECT 1,1,x,20,1,'Leere Position','', 'G' FROM n;
            UPDATE STRUKTURPOSITION SET Kontoliste='' WHERE ItemId=21 AND Firma_id=1;
            UPDATE STRUKTURPOSITION SET Kontoliste='8400',Bezeichnung='Erlös am Ende' WHERE ItemId=540 AND Firma_id=1;
        """)
        profit = reader.financial_statements(1,2025)['profit_and_loss']
        self.assertEqual(position(profit,540)['amount'],'30.00')
        self.assertEqual(profit['total'],'20.00')


if __name__ == '__main__':
    unittest.main()
