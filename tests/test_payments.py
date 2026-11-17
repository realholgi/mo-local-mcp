from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase


def records(result):
    return [dict(zip(result['columns'], row)) for row in result['rows']]


class PaymentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root/'office.db', root/'test.key'
        key = b'payment-test-key'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(path)
        db.execute('PRAGMA page_size=1024')
        db.executescript('''
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Adress_id,ReNr,Datum,
                PKonto,BuText,Waehrung,GesamtBruttoFW,BezahltFW,MinderungFW,OffenFW,
                GesamtBruttoSW,BezahltSW,MinderungSW,OffenSW,Entwurf);
            INSERT INTO POSTEN VALUES
                (1,1,0,1,'RE1','2025-01-01',10000,'Rechnung','EUR',11900,11000,900,0,11900,11000,900,0,NULL),
                (2,1,1,1,'GS1','2025-01-02',10000,'Gutschrift','EUR',-1000,-1000,0,0,-1000,-1000,0,0,0),
                (3,1,0,1,'RE2','2025-01-01',10000,'Andere Rechnung','EUR',3000,3000,0,0,3000,3000,0,0,0),
                (4,1,1,1,'GS2','2025-01-01',10000,'Erstattung','EUR',-2000,-2000,0,0,-2000,-2000,0,0,0),
                (5,1,0,1,'STORNO','2025-01-01',10000,'Stornierte Zahlung','EUR',5000,1000,0,4000,5000,1000,0,4000,0),
                (6,1,0,1,'UNBEZAHLT','2025-01-01',10000,'Keine Zahlung','EUR',5000,0,0,5000,5000,0,0,5000,0),
                (7,1,0,1,'ENTWURF','2025-01-01',10000,'Ausdrücklicher Entwurf','EUR',5000,0,0,5000,5000,0,0,5000,1),
                (8,1,2,1,'USD','2025-01-01',70000,'Verbindlichkeit','USD',10000,10000,0,0,9500,9500,0,0,0),
                (9,1,0,1,'FEHLEND','2025-01-01',10000,'Fehlende Historie','EUR',5000,4000,0,1000,5000,4000,0,1000,0),
                (10,1,0,1,'UNBEKANNT','2025-01-01',10000,'Unbekannte Summen','EUR',5000,NULL,0,NULL,5000,NULL,0,NULL,0),
                (99,2,0,1,'RE1','2025-01-01',10000,'Geheime gleiche Referenz','EUR',99999,99999,0,0,99999,99999,0,0,0);
            CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id,Position,
                BuText,EKonto,Steuersatz,BetragBruttoFW,BetragBruttoSW);
            INSERT INTO POSTENPOSITION VALUES
                (11,1,1,1,'Aufteilung eins',8400,'USt19',7000,7000),
                (12,1,1,2,'Aufteilung zwei',8400,'USt7',4900,4900),
                (21,1,2,1,'Gutschrift',8400,'USt19',-1000,-1000),
                (31,1,3,1,'Andere Rechnung',8400,'USt19',3000,3000),
                (41,1,4,1,'Erstattung',8400,'USt19',-2000,-2000),
                (51,1,5,1,'Gegenbuchung',8400,'USt19',5000,5000),
                (61,1,6,1,'Unbezahlt',8400,'USt19',5000,5000),
                (81,1,8,1,'USD-Kosten',4920,'VSt19',10000,9500),
                (99,2,99,1,'Geheime Position',8400,'USt19',99999,99999);
            CREATE TABLE ZAHLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,ReNr,Waehrung,
                Buchung_id,FKonto,GesamtZahlFW,GesamtZahlSW,GesamtMindFW,GesamtMindSW);
            INSERT INTO ZAHLUNG VALUES
                (10,1,'2025-01-10','SAMMELZAHLUNG','EUR',1,1200,13000,13000,900,900),
                (20,1,'2025-01-11','AUSGLEICH','EUR',0,0,0,0,0,0),
                (30,1,'2025-01-12','ERSTATTUNG','EUR',2,1200,-2000,-2000,0,0),
                (40,1,'2025-01-13','ZAHLUNG','EUR',3,1200,3000,3000,0,0),
                (41,1,'2025-01-14','GEGENBUCHUNG','EUR',4,1200,-2000,-2000,0,0),
                (50,1,'2025-01-15','USD-ZAHLUNG','EUR',5,1200,9500,9500,0,0),
                (99,2,'2025-01-10','SAMMELZAHLUNG','EUR',6,1200,99999,99999,0,0);
            CREATE TABLE ZAHLUNGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Zahlung_id,
                Position,Postenposition_id,BetragZahlFW,BetragZahlSW,BetragMindFW,BetragMindSW,MKonto,MBuText);
            INSERT INTO ZAHLUNGSPOSITION VALUES
                (101,1,10,1,11,6000,6000,500,500,8736,'Skonto'),
                (102,1,10,2,12,4000,4000,400,400,8736,'Skonto'),
                (103,1,10,3,31,3000,3000,0,0,0,''),
                (201,1,20,1,11,1000,1000,0,0,0,''),
                (202,1,20,2,21,-1000,-1000,0,0,0,''),
                (301,1,30,1,41,-2000,-2000,0,0,0,''),
                (401,1,40,1,51,3000,3000,0,0,0,''),
                (402,1,41,1,51,-2000,-2000,0,0,0,''),
                (501,1,50,1,81,10000,9500,0,0,0,''),
                (991,2,99,1,11,99999,99999,0,0,0,'Geheime fremde Zuordnung'),
                (992,1,99,1,11,99999,99999,0,0,0,'Zahlung anderer Firma'),
                (993,1,10,4,99,99999,99999,0,0,0,'Position anderer Firma');
        ''')
        db.commit()
        db.close()
        plain = path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start//1024+1).to_bytes(16,'little'))).encryptor()
            encrypted.extend(encoder.update(plain[start:start+1024])+encoder.finalize())
        encrypted[16:24] = plain[16:24]
        path.write_bytes(encrypted)
        database = OfficeDatabase(path,key_path)
        self.addCleanup(database.close)
        self.reader = BusinessReader(database)

    def test_split_batch_payment_reconciles_only_this_items_allocations(self):
        report = self.reader.open_item(1,1)
        self.assertEqual([row['BetragZahlFW'] for row in records(report['allocations'])],['60.00','40.00','10.00'])
        total = records(report['allocation_totals'])[0]
        self.assertEqual((total['entry_count'],total['BetragZahlFW'],total['BetragMindFW']),(3,'110.00','9.00'))
        self.assertTrue(report['reconciliation']['matches'])
        self.assertEqual(records(report['reconciliation']['differences'])[0]['BezahltFW'],'0.00')
        batch = self.reader.payment(1,10)
        self.assertEqual(records(batch['payment'])[0]['GesamtZahlFW'],'130.00')
        self.assertEqual([row['item_id'] for row in records(batch['allocations'])],[1,1,3])

    def test_credit_clearing_and_refund_keep_signed_amounts_and_item_types(self):
        clearing = self.reader.payment(1,20)
        self.assertEqual(records(clearing['payment'])[0]['GesamtZahlFW'],'0.00')
        rows = records(clearing['allocations'])
        self.assertEqual([(row['item_id'],row['item_type_label'],row['BetragZahlFW']) for row in rows],
                         [(1,'DebitorRechnung','10.00'),(2,'DebitorGutschrift','-10.00')])
        credit = self.reader.open_item(1,2)
        self.assertEqual(records(credit['item'])[0]['GesamtBruttoFW'],'-10.00')
        self.assertTrue(credit['reconciliation']['matches'])
        self.assertEqual(records(self.reader.payment(1,30)['payment'])[0]['GesamtZahlFW'],'-20.00')

    def test_independent_pagination_retains_full_history_totals(self):
        first = self.reader.open_item(1,1,position_limit=1,payment_limit=1)
        second = self.reader.open_item(1,1,position_limit=1,position_offset=first['positions']['next_offset'],
                                       payment_limit=1,payment_offset=first['allocations']['next_offset'])
        self.assertEqual(records(second['positions'])[0]['Position'],2)
        self.assertEqual(records(second['allocations'])[0]['_rowid'],102)
        self.assertEqual(first['allocation_totals'],second['allocation_totals'])
        self.assertTrue(second['reconciliation']['matches'])
        page = self.reader.payment(1,20,limit=1,offset=1)
        self.assertEqual(records(page['allocations'])[0]['item_id'],2)
        self.assertIsNone(page['allocations']['next_offset'])
        self.assertEqual(records(page['payment'])[0]['GesamtZahlFW'],'0.00')

    def test_negative_payment_and_foreign_currency_are_not_reinterpreted(self):
        reversed_payment = self.reader.open_item(1,5)
        self.assertEqual([row['BetragZahlFW'] for row in records(reversed_payment['allocations'])],['30.00','-20.00'])
        self.assertTrue(reversed_payment['reconciliation']['matches'])
        foreign = self.reader.open_item(1,8)
        row = records(foreign['allocations'])[0]
        self.assertEqual((row['item_currency'],row['payment_currency'],row['BetragZahlFW'],row['BetragZahlSW']),
                         ('USD','EUR','100.00','95.00'))
        self.assertTrue(foreign['reconciliation']['matches'])

    def test_unpaid_mismatched_and_unspecified_histories_are_distinct(self):
        unpaid = self.reader.open_item(1,6)
        self.assertEqual(unpaid['allocations']['rows'],[])
        self.assertTrue(unpaid['reconciliation']['matches'])
        missing = self.reader.open_item(1,9)
        self.assertFalse(missing['reconciliation']['matches'])
        self.assertEqual(records(missing['reconciliation']['differences'])[0]['BezahltFW'],'40.00')
        unknown = self.reader.open_item(1,10)
        self.assertIsNone(unknown['reconciliation']['matches'])
        self.assertIsNone(records(unknown['reconciliation']['differences'])[0]['BezahltFW'])

    def test_company_scope_and_explicit_settled_draft_discovery(self):
        with self.assertRaises(ValueError):
            self.reader.open_item(2,1)
        with self.assertRaises(ValueError):
            self.reader.payment(2,10)
        with self.assertRaises(ValueError):
            self.reader.open_item(1,9999)
        with self.assertRaises(ValueError):
            self.reader.payment(1,0)
        default = {row['_rowid'] for row in records(self.reader.open_items(1))}
        all_items = {row['_rowid'] for row in records(self.reader.open_items(1,include_settled=True))}
        self.assertNotIn(1,default)
        self.assertIn(1,all_items)
        self.assertNotIn(7,all_items)
        self.assertNotIn(99,all_items)
        self.assertEqual(records(self.reader.open_item(1,7)['item'])[0]['Entwurf'],1)
        with self.assertRaises(ValueError):
            self.reader.open_items(1,include_settled='ja')


if __name__ == '__main__':
    unittest.main()
