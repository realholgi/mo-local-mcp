from pathlib import Path
import sqlite3
import tempfile
import unittest
from typing import Any

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.quality import check_data_quality


_SCHEMA = '''
CREATE TABLE AUFTRAG (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id);
CREATE TABLE BESTELLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id);
CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Waehrung);
CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY,Firma_id,Buchung_id,
    BetragSoll,BetragHaben,BetragSollFW,BetragHabenFW);
CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id,Buchung_id,BuchungSR_id,
    Waehrung,BezahltFW,BezahltSW,MinderungFW,MinderungSW);
CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id);
CREATE TABLE ZAHLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Buchung_id,ValutaBuchung_id,
    Waehrung,GesamtZahlFW,GesamtZahlSW,GesamtMindFW,GesamtMindSW);
CREATE TABLE ZAHLUNGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Zahlung_id,
    Postenposition_id,SteuerBuchung_id,BetragZahlFW,BetragZahlSW,BetragMindFW,BetragMindSW);
INSERT INTO BUCHUNG VALUES (1,1,'EUR');
INSERT INTO JOURNAL VALUES (1,1,1,-300,0,-400,0),(2,1,1,0,-300,0,-400);
INSERT INTO POSTEN VALUES (1,1,1,0,'EUR',-300,-240,-20,-16);
INSERT INTO POSTENPOSITION VALUES (1,1,1);
INSERT INTO ZAHLUNG VALUES (1,1,1,NULL,'EUR',-300,-240,-20,-16);
INSERT INTO ZAHLUNGSPOSITION VALUES
    (1,1,1,1,0,-100,-80,-10,-8),(2,1,1,1,NULL,-200,-160,-10,-8);
INSERT INTO AUFTRAG VALUES (1,1,1),(2,1,0),(3,1,NULL);
INSERT INTO BESTELLUNG VALUES (1,1,1);
'''


class QualityTests(unittest.TestCase):
    def reader(self, changes=''):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root / 'office.db', root / 'test.key'
        key = b'quality-test-key'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(path)
        db.execute('PRAGMA page_size=1024')
        db.executescript(_SCHEMA + changes)
        db.commit()
        db.close()
        plain = path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, 'little'))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        path.write_bytes(encrypted)
        original = path.read_bytes()
        self.addCleanup(lambda: self.assertEqual(path.read_bytes(), original))
        database = OfficeDatabase(path, key_path)
        self.addCleanup(database.close)
        return BusinessReader(database)

    def test_balanced_signed_data_has_explicit_scope_without_global_pass(self):
        report = check_data_quality(self.reader(), 1)
        self.assertEqual(report['gesamtanzahl'], 0)
        self.assertEqual(report['maengel'], [])
        self.assertEqual(report['pruefungsumfang']['pruefungen']['journal_soll_haben'], 2)
        self.assertEqual(report['pruefungsumfang']['datensaetze']['ZAHLUNGSPOSITION'], 2)
        self.assertEqual(report['pruefungsumfang']['pruefungen']['posten_abgleich'], 4)
        self.assertIn('Keine Korrekturen', report['basis'][-1])
        self.assertNotIn('erfolgreich', report)

    def test_missing_stored_links_cover_all_document_journal_and_payment_paths(self):
        report = check_data_quality(self.reader('''
            UPDATE AUFTRAG SET Posten_id=91 WHERE _rowid=1;
            UPDATE BESTELLUNG SET Posten_id=92;
            UPDATE JOURNAL SET Buchung_id=93 WHERE _rowid=1;
            UPDATE POSTEN SET BuchungSR_id=94;
            UPDATE POSTENPOSITION SET Posten_id=95;
            UPDATE ZAHLUNG SET ValutaBuchung_id=96;
            UPDATE ZAHLUNGSPOSITION SET SteuerBuchung_id=97 WHERE _rowid=1;
            UPDATE ZAHLUNGSPOSITION SET Zahlung_id=98,Postenposition_id=99 WHERE _rowid=2;
        '''), 1)
        links = [row for row in report['maengel'] if row['kategorie'] == 'fehlende_verknuepfung']
        self.assertEqual(len(links), 9)
        self.assertEqual({row['ziel_id'] for row in links}, set(range(91, 100)))
        unknown = [row for row in report['maengel'] if row['kategorie'] == 'posten_abgleich']
        self.assertEqual(len(unknown), 4)
        self.assertTrue(all(row['status'] == 'unbekannt' and row['zuordnungssumme'] is None for row in unknown))

    def test_cross_company_targets_do_not_resolve_or_disclose_other_contents(self):
        report = check_data_quality(self.reader('''
            INSERT INTO POSTEN VALUES (20,2,0,0,'FREMD',999999,999999,0,0);
            INSERT INTO POSTENPOSITION VALUES (20,2,20);
            INSERT INTO ZAHLUNG VALUES (20,2,0,0,'FREMD',999999,999999,0,0);
            INSERT INTO BUCHUNG VALUES (20,2,'FREMD');
            INSERT INTO JOURNAL VALUES (20,2,1,999999,0,999999,0);
            INSERT INTO ZAHLUNGSPOSITION VALUES (20,2,1,1,0,999999,999999,0,0);
            UPDATE AUFTRAG SET Posten_id=20 WHERE _rowid=1;
            UPDATE ZAHLUNGSPOSITION SET Zahlung_id=20 WHERE _rowid=1;
            UPDATE ZAHLUNGSPOSITION SET Postenposition_id=20 WHERE _rowid=2;
            UPDATE POSTEN SET Buchung_id=20;
        '''), 1)
        self.assertEqual(report['anzahl_nach_kategorie']['fehlende_verknuepfung'], 4)
        self.assertEqual(report['pruefungsumfang']['datensaetze']['JOURNAL'], 2)
        self.assertNotIn('999999', str(report))
        self.assertNotIn('FREMD', str(report))
        self.assertEqual(report['anzahl_nach_kategorie']['journal_saldo'], 0)

    def test_mismatches_report_separate_fields_and_preserve_negative_amounts(self):
        report = check_data_quality(self.reader('''
            UPDATE JOURNAL SET BetragHaben= -200 WHERE _rowid=2;
            UPDATE POSTEN SET BezahltFW=-250,MinderungSW=-15;
            UPDATE ZAHLUNG SET GesamtZahlSW=-200;
        '''), 1)
        rows = {(row['tabelle'], row['feld']): row for row in report['maengel']}
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows['BUCHUNG', 'SW']['differenz'], '-1.00')
        self.assertEqual(rows['POSTEN', 'BezahltFW']['kopf'], '-2.50')
        self.assertEqual(rows['POSTEN', 'BezahltFW']['zuordnungssumme'], '-3.00')
        self.assertEqual(rows['POSTEN', 'BezahltFW']['differenz'], '0.50')
        self.assertEqual(rows['POSTEN', 'MinderungSW']['differenz'], '0.01')
        self.assertEqual(rows['ZAHLUNG', 'GesamtZahlSW']['differenz'], '0.40')

    def test_null_amounts_are_unknown_instead_of_zero_or_match(self):
        report = check_data_quality(self.reader('''
            UPDATE JOURNAL SET BetragSollFW=NULL WHERE _rowid=1;
            UPDATE POSTEN SET MinderungSW=NULL;
            UPDATE ZAHLUNGSPOSITION SET BetragZahlFW=NULL WHERE _rowid=1;
        '''), 1)
        rows = {(row['tabelle'], row['feld']): row for row in report['maengel']}
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row['status'] == 'unbekannt' for row in rows.values()))
        self.assertIsNone(rows['POSTEN', 'BezahltFW']['zuordnungssumme'])
        self.assertIsNone(rows['ZAHLUNG', 'GesamtZahlFW']['zuordnungssumme'])
        self.assertIsNone(rows['POSTEN', 'MinderungSW']['kopf'])

    def test_foreign_currency_payment_fw_is_not_compared_with_item_fw(self):
        report = check_data_quality(self.reader("UPDATE ZAHLUNG SET Waehrung='USD';"), 1)
        self.assertEqual(report['gesamtanzahl'], 2)
        self.assertEqual({row['feld'] for row in report['maengel']}, {'GesamtZahlFW', 'GesamtMindFW'})
        self.assertTrue(all(row['status'] == 'unbekannt' for row in report['maengel']))

    def test_empty_allocations_and_missing_journal_are_distinct(self):
        report = check_data_quality(self.reader('DELETE FROM ZAHLUNGSPOSITION; DELETE FROM JOURNAL;'), 1)
        self.assertEqual(report['anzahl_nach_kategorie']['journal_saldo'], 2)
        self.assertEqual(report['anzahl_nach_status'], {'mangel': 8, 'unbekannt': 2})
        self.assertTrue(all(row['zuordnungssumme'] == '0.00' for row in report['maengel']
                            if row['kategorie'] in {'posten_abgleich', 'zahlung_abgleich'}))

    def test_binary_float_residue_does_not_create_false_cent_difference(self):
        report = check_data_quality(self.reader('''
            UPDATE JOURNAL SET BetragSoll=0.1+0.2,BetragSollFW=0.1+0.2 WHERE _rowid=1;
            UPDATE JOURNAL SET BetragHaben=0.3,BetragHabenFW=0.3 WHERE _rowid=2;
            UPDATE POSTEN SET BezahltFW=0.1+0.2,BezahltSW=0.1+0.2;
            UPDATE ZAHLUNG SET GesamtZahlFW=0.3,GesamtZahlSW=0.3;
            UPDATE ZAHLUNGSPOSITION SET BetragZahlFW=0.1,BetragZahlSW=0.1 WHERE _rowid=1;
            UPDATE ZAHLUNGSPOSITION SET BetragZahlFW=0.2,BetragZahlSW=0.2 WHERE _rowid=2;
        '''), 1)
        self.assertEqual(report['gesamtanzahl'], 0)

    def test_full_counts_before_pagination_and_complete_bulk_reads(self):
        reader = self.reader('''
            WITH RECURSIVE ids(n) AS (VALUES(10) UNION ALL SELECT n+1 FROM ids WHERE n<520)
            INSERT INTO AUFTRAG SELECT n,1,999 FROM ids;
        ''')
        first = check_data_quality(reader, 1, limit=500)
        second = check_data_quality(reader, 1, limit=500, offset=first['naechster_versatz'])
        self.assertEqual(first['gesamtanzahl'], 511)
        self.assertEqual(first['anzahl_nach_kategorie']['fehlende_verknuepfung'], 511)
        self.assertEqual(first['pruefungsumfang']['datensaetze']['AUFTRAG'], 514)
        self.assertTrue(first['gekuerzt'])
        self.assertEqual(first['naechster_versatz'], 500)
        self.assertEqual(second['gesamtanzahl'], 511)
        self.assertEqual(second['anzahl'], 11)
        self.assertFalse(second['gekuerzt'])
        self.assertIsNone(second['naechster_versatz'])
        ids = [row['datensatz_id'] for row in first['maengel'] + second['maengel']]
        self.assertEqual(ids, list(range(10, 521)))
        self.assertEqual(check_data_quality(reader, 1, offset=999)['maengel'], [])

    def test_invalid_company_and_page_arguments_fail_before_reading(self):
        for value in (0, -1, True, '1', None, 1.5):
            with self.subTest(company_id=value), self.assertRaises(ValueError):
                check_data_quality(None, value)
        cases: list[dict[str, Any]] = [
            {'limit': 0}, {'limit': 501}, {'limit': True}, {'offset': -1}, {'offset': '0'},
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                check_data_quality(None, 1, **arguments)


if __name__ == '__main__':
    unittest.main()
