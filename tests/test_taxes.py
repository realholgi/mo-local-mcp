from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.taxes import get_tax_journal, get_vat_return


def packed(values):
    return str(len(values)).zfill(6) + ''.join(str(len(v)).zfill(6) + v for v in values)


def records(result):
    return [dict(zip(result['columns'], row)) for row in result['rows']]


class TaxTests(unittest.TestCase):
    def fixture(self, extra=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root / 'testfirma.db', root / 'test.key'
        key = b'steuer-testkey!!'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(path)
        db.execute('PRAGMA page_size=1024')
        db.executescript('''
            CREATE TABLE ELSTERMELDUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Verfahren,DatenArt,Vorgang,Jahr,
                Zeitraum,ZeitraumCode,DatumVon,DatumBis,Berechnungsart,Status,Land,SSS,Meldung_id,Kennzahlen);
            CREATE TABLE ELSTERMELDUNG_NT (_rowid INTEGER PRIMARY KEY,Firma_id,Method,DataType,Process,
                DateFrom,DateTo,Status,Report_id,TaxReport);
            CREATE TABLE STEUERERKLAERUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datenart,Jahr,Kennzahlen);
            INSERT INTO STEUERERKLAERUNG VALUES (1,1,'Umsatzsteuererklärung','2025','<root/>');
            CREATE TABLE WIRTSCHAFTSJAHR (_rowid INTEGER PRIMARY KEY,Firma_id,Waehrung,Versteuerung);
            INSERT INTO WIRTSCHAFTSJAHR VALUES (1,1,'EUR',2),(2,2,'USD',1);
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Wj_id,Datum,Art,Status,Waehrung);
            INSERT INTO BUCHUNG VALUES (1,1,1,'2025-01-10',3,0,'EUR'),(2,1,1,'2025-03-10',1,3,'EUR'),
                (3,1,1,'2025-03-11',1,0,'USD'),(4,2,2,'2025-03-10',1,0,'USD'),
                (5,1,1,'2025-03-01',2,0,'EUR');
            CREATE TABLE STEUERSATZ (_rowid INTEGER PRIMARY KEY,Firma_id,Name,Typ,KontoSteuer1,KontoSteuer2,
                KontoSteuerNF,UVASteuer1,UVASteuer2,UVABemessung1,UVABemessung2,OSS);
            INSERT INTO STEUERSATZ VALUES (1,1,'USt19',1,1776,0,1766,'81','','','',0),
                (2,1,'VSt19',2,1576,0,0,'66','','','',0),
                (3,2,'USt19',1,1776,0,1766,'99','','','',0);
            CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY,Firma_id,Buchung_id,Position DEFAULT 1,
                Konto,GegenKonto DEFAULT 1200,Steuersatz DEFAULT '-',Steuer_id DEFAULT 0,Storno DEFAULT 0,
                Versteuerung DEFAULT 0,SteuerStatus DEFAULT 0,BetragSoll DEFAULT 0,BetragHaben DEFAULT 0,
                BetragSollFW DEFAULT 0,BetragHabenFW DEFAULT 0,IV_Steuersatz DEFAULT '',
                IV_BetragSoll DEFAULT 0,IV_BetragHaben DEFAULT 0,IV_Konto DEFAULT 0,IV_KontoUStE DEFAULT 0,
                BetragBemSoll DEFAULT 0,BetragBemHaben DEFAULT 0,DatumVerbucht DEFAULT '2026-11-01',
                OSS_ISO_LK DEFAULT '',OSS_Prozent DEFAULT 0,OSS_Typ DEFAULT 0);
            INSERT INTO JOURNAL (_rowid,Firma_id,Buchung_id,Konto,Steuersatz,BetragHaben,Versteuerung)
                VALUES (1,1,1,8400,'USt19',10000,2);
            INSERT INTO JOURNAL (_rowid,Firma_id,Buchung_id,Konto,BetragHaben,BetragBemSoll)
                VALUES (2,1,1,1766,1900,10000);
            INSERT INTO JOURNAL (_rowid,Firma_id,Buchung_id,Konto,BetragHaben,IV_Steuersatz,IV_BetragHaben)
                VALUES (3,1,2,1776,1900,'USt19',10000),(4,1,2,1776,-190,'USt19',-1000);
            INSERT INTO JOURNAL (_rowid,Firma_id,Buchung_id,Konto,BetragSoll,BetragBemSoll,Storno)
                VALUES (5,1,3,1576,380,2000,0),(6,1,3,1576,-190,1000,2),
                       (7,2,4,1576,99999,99999,0),(8,1,5,1576,99999,99999,0);
            INSERT INTO JOURNAL (_rowid,Firma_id,Buchung_id,Konto,Steuersatz,BetragSoll,BetragSollFW)
                VALUES (9,1,3,4920,'VSt19',2000,2300);
        ''')
        db.execute('''INSERT INTO ELSTERMELDUNG VALUES
            (1,1,'ElsterAnmeldung','Umsatzsteuer-Voranmeldung','','2025','Februar 2025','02',
             '2025-02-01 00:00:00','2025-02-28 00:00:00','25',4,1,0,123,?)''',
                   [packed(['81', '100000', '66', '1900', '83', '17100', '10', '1', '999', 'abc'])])
        db.execute('''INSERT INTO ELSTERMELDUNG SELECT 99,2,Verfahren,DatenArt,Vorgang,Jahr,Zeitraum,
            ZeitraumCode,DatumVon,DatumBis,Berechnungsart,Status,Land,SSS,Meldung_id,Kennzahlen
            FROM ELSTERMELDUNG WHERE _rowid=1''')
        if extra:
            extra(db)
        db.commit()
        db.close()
        plain = path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, 'little'))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        path.write_bytes(encrypted)
        database = OfficeDatabase(path, key_path)
        self.addCleanup(database.close)
        return BusinessReader(database)

    def test_stored_uva_uses_exact_identity_not_annual_declaration(self):
        report = get_vat_return(self.fixture(), 1, 2025, month=2)
        self.assertEqual(report['status'], 'stored')
        self.assertEqual(report['report']['_rowid'], 1)
        values = {v['code']: v for v in report['figures']}
        self.assertEqual(values['81']['amount'], '1000.00')
        self.assertEqual(values['66']['amount'], '19.00')
        self.assertEqual(values['83']['amount'], '171.00')
        self.assertIsNone(values['10']['amount'])
        self.assertEqual(values['999']['raw_value'], 'abc')
        self.assertIsNone(values['999']['amount'])

    def test_ist_invoice_is_not_due_until_actual_receipt_and_signed_reduction(self):
        reader = self.fixture()
        january = get_vat_return(reader, 1, 2025, month=1)
        self.assertEqual(january['figures'], [])
        self.assertEqual(january['coverage']['non_due_rows_excluded'], 1)
        march = get_vat_return(reader, 1, 2025, month=3)
        values = {v['code']: v for v in march['figures']}
        self.assertEqual(values['81']['amount'], '90.00')
        self.assertEqual(values['81']['actual_tax'], '17.10')
        self.assertEqual(values['81']['journal_ids'], [3, 4])
        self.assertEqual(values['66']['amount'], '1.90')
        self.assertEqual(values['66']['journal_ids'], [5, 6])
        self.assertNotIn('83', values)
        self.assertEqual(march['coverage']['opening_rows_excluded'], 1)

    def test_accrual_tax_lines_use_stored_base_not_rate_or_expense_duplicates(self):
        def extra(db):
            db.execute('UPDATE WIRTSCHAFTSJAHR SET Versteuerung=1 WHERE Firma_id=1')
            db.execute("UPDATE JOURNAL SET IV_Steuersatz='',BetragBemSoll=10000,IV_BetragHaben=0 WHERE _rowid=3")
        result = get_vat_return(self.fixture(extra), 1, 2025, month=3)
        values = {v['code']: v for v in result['figures']}
        self.assertEqual(values['81']['amount'], '90.00')
        self.assertEqual(values['66']['amount'], '1.90')

    def test_direct_tax_posting_without_base_is_not_fabricated(self):
        def extra(db):
            db.execute("UPDATE JOURNAL SET IV_Steuersatz='',IV_BetragHaben=0 WHERE _rowid=3")
        result = get_vat_return(self.fixture(extra), 1, 2025, month=3)
        values = {v['code']: v for v in result['figures']}
        self.assertEqual(values['81']['amount'], '-10.00')
        self.assertTrue(any(v.get('journal_id') == 3 and v.get('actual_tax') == '19.00' for v in result['issues']))

    def test_journal_preserves_currency_reversal_and_company_with_pagination(self):
        reader = self.fixture()
        page = get_tax_journal(reader, 1, '2025-03-01', '2025-03-31', limit=2)
        self.assertIsNotNone(page['next_offset'])
        rows = []
        while True:
            rows.extend(records(page))
            if page['next_offset'] is None:
                break
            page = get_tax_journal(reader, 1, '2025-03-01', '2025-03-31', limit=2, offset=page['next_offset'])
        self.assertNotIn(7, [r['_rowid'] for r in rows])
        reversal = next(r for r in rows if r['_rowid'] == 6)
        self.assertEqual((reversal['BetragSoll'], reversal['Storno']), ('-1.90', 2))
        expense = next(r for r in rows if r['_rowid'] == 9)
        self.assertEqual((expense['FW_currency'], expense['SW_currency']), ('USD', 'EUR'))
        self.assertEqual((expense['BetragSoll'], expense['BetragSollFW']), ('20.00', '23.00'))

    def test_report_revisions_require_identity_and_paginate_figures(self):
        def extra(db):
            db.execute('''INSERT INTO ELSTERMELDUNG SELECT 2,Firma_id,Verfahren,DatenArt,Vorgang,Jahr,
                Zeitraum,ZeitraumCode,DatumVon,DatumBis,Berechnungsart,Status,Land,SSS,Meldung_id,Kennzahlen
                FROM ELSTERMELDUNG WHERE _rowid=1''')
        reader = self.fixture(extra)
        self.assertEqual(get_vat_return(reader, 1, 2025, month=2)['status'], 'ambiguous')
        page = get_vat_return(reader, 1, 2025, month=2, report_id=2, limit=1, offset=1)
        self.assertEqual(page['figures'][0]['code'], '66')
        self.assertEqual(page['next_offset'], 2)
        with self.assertRaises(ValueError):
            get_vat_return(reader, 1, 2025, month=2, report_id=99)

    def test_unsupported_stored_evidence_never_falls_back_to_reconstruction(self):
        for payload in ('<root/>', packed(['81', '1', '81', '2']), packed(['81']), packed(['81', 'NaN'])):
            with self.subTest(payload=payload):
                reader = self.fixture(lambda db: db.execute('UPDATE ELSTERMELDUNG SET Kennzahlen=? WHERE _rowid=1', [payload]))
                result = get_vat_return(reader, 1, 2025, month=2)
                self.assertEqual(result['status'], 'unsupported')
                self.assertEqual(result['figures'], [])

    def test_unknown_modern_report_and_ambiguous_accounts_are_explicit(self):
        def modern(db):
            db.execute("INSERT INTO ELSTERMELDUNG_NT VALUES (1,1,'unbekannt','unbekannt','','2025-03-01','2025-03-31',0,0,'<x/>')")
        self.assertEqual(get_vat_return(self.fixture(modern), 1, 2025, month=3)['status'], 'unsupported')
        def ambiguous(db):
            db.execute("INSERT INTO STEUERSATZ VALUES (4,1,'Andere Steuer',2,1576,0,0,'61','','','',0)")
        result = get_vat_return(self.fixture(ambiguous), 1, 2025, month=3)
        self.assertNotIn('66', [v['code'] for v in result['figures']])
        self.assertTrue(any(v['reason'] == 'Mehrdeutige Steuerkontenzuordnung' for v in result['issues']))

    def test_quarter_and_argument_validation(self):
        reader = self.fixture()
        report = get_vat_return(reader, 1, 2025, quarter=1)
        self.assertEqual((report['date_from'], report['date_to']), ('2025-01-01', '2025-03-31'))
        for kwargs in ({}, {'month': 1, 'quarter': 1}, {'month': True}, {'month': 13}, {'quarter': 5}):
            with self.assertRaises(ValueError):
                get_vat_return(reader, 1, 2025, **kwargs)
        with self.assertRaises(ValueError):
            get_tax_journal(reader, 1, '2025-03-31', '2025-03-01')
