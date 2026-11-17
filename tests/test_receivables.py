from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.receivables import get_open_items_as_of, get_open_item_aging


def records(result):
    return [dict(zip(result['columns'], row)) for row in result['rows']]


class ReceivableTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root=Path(directory.name)
        path,key_path=root/'testfirma.db',root/'test.key'
        key=b'historie-testkey'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db=sqlite3.connect(path)
        db.execute('PRAGMA page_size=1024')
        db.executescript('''
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id DEFAULT 1,Art DEFAULT 0,Adress_id DEFAULT 1,
                ReNr,Datum,PKonto DEFAULT 10000,BuText DEFAULT '',Waehrung DEFAULT 'EUR',
                GesamtBruttoFW,GesamtBruttoSW,BezahltFW DEFAULT 0,BezahltSW DEFAULT 0,
                MinderungFW DEFAULT 0,MinderungSW DEFAULT 0,OffenFW,OffenSW,Entwurf DEFAULT 0,
                TageNetto DEFAULT 0,NichtMahnen DEFAULT 0,Mahnstufe DEFAULT 0,
                DatumMahnung1,DatumMahnung2,DatumMahnung3,DatumMahnung4);
            CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id);
            CREATE TABLE ZAHLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum);
            CREATE TABLE ZAHLUNGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Zahlung_id,
                Postenposition_id,BetragZahlFW,BetragZahlSW,BetragMindFW,BetragMindSW);
        ''')
        def item(item_id,datum,gross,**extra):
            fields={'_rowid':item_id,'ReNr':f'R{item_id}','Datum':datum,'GesamtBruttoFW':gross,'GesamtBruttoSW':gross}
            fields.update(extra)
            db.execute('INSERT INTO POSTEN('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',list(fields.values()))
            db.execute('INSERT INTO POSTENPOSITION VALUES(?,?,?)',(item_id,fields.get('Firma_id',1),item_id))
        item(1,'2025-01-01',11900,BezahltFW=10900,BezahltSW=10900,MinderungFW=1000,MinderungSW=1000,
             TageNetto=14,Mahnstufe=2,DatumMahnung1='2025-01-20',DatumMahnung2='2025-03-01')
        item(2,'2025-01-02',-1000,Art=1,BezahltFW=-1000,BezahltSW=-1000)
        item(3,'2025-02-01',5000)
        item(4,'2024-12-01',2000,NichtMahnen=1)
        item(5,'2025-01-31',3000)
        item(6,'2025-01-01',4000,TageNetto=None)
        item(7,'2025-01-01',5000,BezahltFW=1000,BezahltSW=1000)
        item(8,'2025-01-01',5000,BezahltFW=1000,BezahltSW=1000)
        item(9,'2025-01-01',None)
        item(17,'2025-01-01',5000)
        item(18,'2025-01-01',5000,Mahnstufe=0,DatumMahnung1='',DatumMahnung2='',DatumMahnung3='',DatumMahnung4='')
        item(10,'2025-01-01',10000,Waehrung='USD',GesamtBruttoSW=9500)
        item(11,'2025-01-01',5000,Art=2,PKonto=70000)
        item(12,'2025-01-01',99999,Firma_id=2)
        item(13,'2025-01-01',99999,Entwurf=1)
        item(14,'2025-01-01',5000,BezahltFW=2000,BezahltSW=2000)
        item(15,'2025-01-01',5000,BezahltFW=1000,BezahltSW=1000)
        item(16,'2025-01-01',5000,BezahltFW=2000,BezahltSW=2000)
        for item_id,days in enumerate([30,31,60,61,90,91],20):
            item(item_id,(date(2025,1,31)-timedelta(days=days)).isoformat(),100)
        payments=[
            (101,1,'2025-01-10',1,5000,0), (102,1,'2025-02-10',1,5900,1000),
            (201,1,'2025-02-10',2,-1000,0), (801,1,None,8,1000,0),
            (1401,1,'2024-12-31',14,2000,0), (1501,1,'2025-01-01',15,3000,0),
            (1502,1,'2025-01-25',15,-2000,0), (1601,1,'2025-01-31',16,2000,0),
            (9901,2,'2025-01-01',1,99999,0),
            (1701,1,'2025-01-02',17,None,0),
        ]
        for payment_id,company,datum,item_id,paid,reduction in payments:
            db.execute('INSERT INTO ZAHLUNG VALUES(?,?,?)',(payment_id,company,datum))
            db.execute('INSERT INTO ZAHLUNGSPOSITION VALUES(?,?,?,?,?,?,?,?)',
                       (payment_id,company,payment_id,item_id,paid,paid,reduction,reduction))
        db.commit()
        db.close()
        plain=path.read_bytes()
        encrypted=bytearray()
        for start in range(0,len(plain),1024):
            encoder=Cipher(algorithms.AES(key),OFB((start//1024+1).to_bytes(16,'little'))).encryptor()
            encrypted.extend(encoder.update(plain[start:start+1024])+encoder.finalize())
        encrypted[16:24]=plain[16:24]
        path.write_bytes(encrypted)
        self.original=path.read_bytes()
        self.path=path
        database=OfficeDatabase(path,key_path)
        self.addCleanup(database.close)
        self.reader=BusinessReader(database)

    def details(self,**kwargs):
        return get_open_items_as_of(self.reader,1,'2025-01-31',**kwargs)

    def test_future_receipts_reductions_and_documents_are_cut_off(self):
        rows={row['_rowid']:row for row in records(self.details())}
        self.assertEqual((rows[1]['paid_as_of_FW'],rows[1]['reduction_as_of_FW'],rows[1]['open_as_of_FW']),('50.00','0.00','69.00'))
        self.assertEqual(rows[2]['open_as_of_FW'],'-10.00')
        self.assertNotIn(3,rows)
        self.assertNotIn(12,rows)
        self.assertNotIn(13,rows)
        self.assertEqual(rows[16]['open_as_of_FW'],'30.00')
        after={row['_rowid']:row for row in records(get_open_items_as_of(self.reader,1,'2025-02-28'))}
        self.assertNotIn(1,after)
        self.assertNotIn(2,after)
        closed={row['_rowid']:row for row in records(get_open_items_as_of(self.reader,1,'2025-02-28',include_settled=True))}
        self.assertEqual(closed[1]['open_as_of_FW'],'0.00')
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_missing_and_undated_histories_remain_unknown(self):
        rows={row['_rowid']:row for row in records(self.details())}
        self.assertEqual(rows[7]['history_status'],'mismatch')
        self.assertEqual(rows[7]['calculated_open_FW'],'50.00')
        for item in [7,8,9,17]:self.assertIsNone(rows[item]['open_as_of_FW'])
        self.assertEqual(rows[8]['history_status'],'unknown')
        summary=records(self.details()['totals'])
        unknown=next(row for row in summary if row['side']=='receivable' and row['Waehrung']=='EUR' and row['aging_bucket']=='unknown_balance')
        self.assertEqual(unknown['unknown_balance_count'],4)
        self.assertIsNone(unknown['open_FW'])

    def test_empty_dunning_dates_are_not_recorded_notices(self):
        rows={row['_rowid']:row for row in records(self.details())}
        self.assertEqual(rows[18]['Mahnstufe'],0)
        self.assertEqual(rows[18]['observed_dunning_level_as_of'],0)

    def test_due_dates_bucket_boundaries_and_dunning_evidence(self):
        rows={row['_rowid']:row for row in records(self.details())}
        self.assertEqual((rows[1]['due_date'],rows[1]['days_overdue'],rows[1]['aging_bucket']),('2025-01-15',16,'1_30'))
        self.assertEqual((rows[1]['Mahnstufe'],rows[1]['observed_dunning_level_as_of']),(2,1))
        self.assertEqual(rows[1]['dunning_candidate'],1)
        self.assertEqual((rows[4]['overdue'],rows[4]['dunning_candidate']),(1,0))
        self.assertEqual((rows[5]['overdue'],rows[5]['aging_bucket']),(0,'not_due'))
        self.assertEqual(rows[6]['aging_bucket'],'unknown_due_date')
        self.assertIsNone(rows[6]['overdue'])
        self.assertEqual(rows[2]['aging_bucket'],'credit')
        self.assertEqual(rows[2]['overdue'],0)
        self.assertEqual([rows[item]['aging_bucket'] for item in range(20,26)],['1_30','31_60','31_60','61_90','61_90','over_90'])
        overdue=records(self.details(overdue_only=True))
        self.assertTrue(all(row['open_as_of_FW'] is not None and row['overdue']==1 for row in overdue))
        self.assertNotIn(2,[row['_rowid'] for row in overdue])

    def test_signed_reversals_prepayments_sides_and_currencies_stay_separate(self):
        rows={row['_rowid']:row for row in records(self.details(side='all'))}
        self.assertEqual(rows[15]['open_as_of_FW'],'40.00')
        self.assertEqual((rows[14]['open_as_of_FW'],rows[14]['pre_document_allocations']),('30.00',1))
        self.assertEqual((rows[10]['Waehrung'],rows[10]['open_as_of_FW'],rows[10]['open_as_of_SW']),('USD','100.00','95.00'))
        self.assertEqual(rows[11]['side'],'payable')
        receivable=records(self.details())
        self.assertNotIn(11,[row['_rowid'] for row in receivable])
        summary=records(get_open_item_aging(self.reader,1,'2025-01-31',side='all'))
        usd=next(row for row in summary if row['Waehrung']=='USD')
        self.assertEqual((usd['open_FW'],usd['open_SW']),('100.00','95.00'))
        payable=next(row for row in summary if row['side']=='payable')
        self.assertEqual(payable['open_FW'],'50.00')

    def test_full_summary_survives_pagination_and_invalid_inputs_fail(self):
        full=self.details()
        first=self.details(limit=1)
        second=self.details(limit=1,offset=first['next_offset'])
        self.assertEqual(first['totals'],full['totals'])
        self.assertEqual(second['totals'],full['totals'])
        for kwargs in [{'as_of':'20250131'},{'as_of':'2025-02-30'},{'side':'ungueltig'},{'include_settled':'ja'}]:
            args={'company_id':1,'as_of':'2025-01-31',**kwargs}
            with self.assertRaises(ValueError):get_open_items_as_of(self.reader,**args)


if __name__=='__main__':unittest.main()
