"""Synthetische Vertragsprüfungen der lesenden Connect-Stammdaten."""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.connect import ConnectReader
from mo_local_mcp.connect_masters import EXTENSIONS, METHODS, handle
from mo_local_mcp.database import OfficeDatabase


class ConnectMastersTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.path = root / 'synthetisch.db'
        key_path = root / 'synthetisch.key'
        key = b'connect-masters!'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        connection = sqlite3.connect(self.path)
        connection.execute('PRAGMA page_size=1024')
        connection.executescript('''
            CREATE TABLE FIRMA (_rowid INTEGER PRIMARY KEY, Name, Zusatz, Strasse,
                Geschaeftsfuehrer, Registergericht, LgName, Passwort);
            INSERT INTO FIRMA VALUES
                (1,'Testfirma Alpha','Zusatz A','Testweg','Testleitung','Testgericht','Objekt A','geheim'),
                (2,'Testfirma Beta','Zusatz B','Testweg B','Andere Leitung','Gericht B','Objekt B','privat');
            CREATE TABLE ADRESSE (_rowid INTEGER PRIMARY KEY, Firma_id, KZ_AdressNr,
                KZ_Matchcode, KZ_Kategorie, RA_Firma1, RA_Firma2, RA_Vorname, RA_Nachname,
                RA_Plz, RA_Ort, RA_Strasse, RA_StrasseNr, RA_Email, KF_Status, LF_Status,
                KF_Konto, LF_Konto, KF_ErtrKonto, SO_Bemerkung, KB_KKNummer, Kennwort);
            INSERT INTO ADRESSE VALUES
                (10,1,'A10','Alpha','Test','Testkunde',NULL,NULL,NULL,'00000','Testort','Testweg','1',
                 'kontakt@example.invalid',1,0,10000,NULL,8000,'Vollständige Notizen','nicht exponieren','geheim'),
                (11,1,'A11','Beta','Test','Testlieferant',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,2,NULL,70000,NULL,NULL,NULL,NULL),
                (12,1,'A12','%_','Test','Beide Rollen',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,3,1,10000,70000,NULL,NULL,NULL,NULL),
                (13,1,'A13','Neutral','Test','Keine Rolle',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL),
                (90,2,'Fremd','Alpha','Test','Fremdfirma',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,1,10000,70000,NULL,NULL,NULL,NULL);
            CREATE TABLE ARTIKEL (_rowid INTEGER PRIMARY KEY,Firma_id,Art,ArtikelNr,
                Matchcode,Bezeichnung,Beschreibung,Warengruppe,Lagerartikel);
            INSERT INTO ARTIKEL VALUES
                (20,1,1,'AR20','Alpha','Testartikel','Beschreibung','Gruppe %_',1),
                (21,1,2,'AR21','Beta','Testleistung','Beschreibung','Gruppe B',0),
                (91,2,1,'AR91','Alpha','Fremdartikel','Beschreibung','Gruppe %_',1);
            CREATE TABLE PROJEKT (_rowid INTEGER PRIMARY KEY,Firma_id,ProjektNr,
                Bezeichnung,Beschreibung,DatumStart,DatumEnde,Status);
            INSERT INTO PROJEKT VALUES
                (30,1,'P30','Testprojekt','Beschreibung %_','2026-01-01','2026-12-31',4),
                (92,2,'P92','Fremdprojekt','Beschreibung %_',NULL,NULL,0);
            CREATE TABLE KOSTENSTELLE (_rowid INTEGER PRIMARY KEY,Firma_id,Name,
                Beschreibung,Bemerkung,Buchungssperre);
            INSERT INTO KOSTENSTELLE VALUES (40,1,'KS40','Test','Notiz',1),(93,2,'KS93','Fremd','Notiz',0);
            CREATE TABLE KONTO (_rowid INTEGER PRIMARY KEY,Firma_id,Nummer,
                Bezeichnung,Typ,Steuertyp,Bemerkung,Buchungssperre,Waehrung);
            INSERT INTO KONTO VALUES
                (50,1,10000,'Personenkonto','D',0,'Notiz',0,'EUR'),
                (51,1,8000,'Testerlöse','E',3,'Notiz',1,'EUR'),
                (94,2,10000,'Fremdkonto','D',0,'Notiz',0,'EUR');
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id,Art,Adress_id,
                Datum,Waehrung,OffenFW,OffenSW,Entwurf);
            INSERT INTO POSTEN VALUES
                (100,1,0,10,'2026-01-01','EUR',10000,10000,0),
                (101,1,1,10,'2026-01-02','EUR',-2000,-2000,0),
                (102,1,0,10,'2026-01-03','USD',5000,4500,0),
                (103,1,0,12,'2026-01-02','EUR',700,700,0),
                (104,1,0,10,'2026-01-02','EUR',99999,99999,1),
                (105,2,0,10,'2026-01-02','EUR',99999,99999,0),
                (106,1,0,90,'2026-01-02','EUR',99999,99999,0),
                (107,1,2,11,'2026-01-02','EUR',3000,3000,0),
                (108,1,3,11,'2026-01-03','EUR',-500,-500,0),
                (109,1,2,12,'2026-01-03','USD',NULL,100,0);
            CREATE TABLE BENUTZER (_rowid INTEGER PRIMARY KEY,Benutzername,Kennwort);
            INSERT INTO BENUTZER VALUES (1,'privat','geheim');
        ''')
        connection.commit()
        connection.close()
        plain = self.path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, 'little'))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        self.path.write_bytes(encrypted)
        self.original = bytes(encrypted)
        self.database = OfficeDatabase(self.path, key_path)
        self.addCleanup(self.database.close)
        self.reader = ConnectReader(self.database)

    def call(self, method, params=None, firma_id: object = 1):
        return handle(self.reader, method, {} if params is None else params, firma_id)

    def test_company_list_and_exact_company_detail_without_credentials(self):
        self.assertEqual(self.call('firmaList', firma_id=None), {'FirmaListItem': [
            {'Firma_ID': '1', 'Bezeichnung': 'Testfirma Alpha', 'Zusatz': 'Zusatz A'},
            {'Firma_ID': '2', 'Bezeichnung': 'Testfirma Beta', 'Zusatz': 'Zusatz B'},
        ]})
        detail = self.call('firmaGet')['FirmaItem']
        self.assertEqual(detail['Firma_Name'], 'Testfirma Alpha')
        self.assertEqual(detail['Firma_RegisterGericht'], 'Testgericht')
        self.assertEqual(detail['Firma_LGName'], 'Objekt A')
        self.assertNotIn('Firma_BankIBAN', detail)
        self.assertNotIn('Firma_Passwort', detail)
        self.assertNotIn('geheim', str(detail))

    def test_company_required_for_every_company_method(self):
        for method in METHODS - {'firmaList'}:
            for company in (None, 0, True, '999', '1 OR 1=1'):
                with self.subTest(method=method, company=company), self.assertRaises(ValueError):
                    self.call(method, firma_id=company)

    def test_address_roles_and_statuses(self):
        for status, expected in ((-2, ['10', '11', '12', '13']), (-1, ['10', '12']),
                                 (0, ['11', '13']), (1, ['10']), (2, []), (3, ['12'])):
            actual = self.call('adresseList', {'AdresseFilter': {'KundenStatus': status}})
            self.assertEqual([row['Adresse_ID'] for row in actual['AdresseListItem']], expected)
        both = self.call('adresseList', {'AdresseFilter': {'KundenStatus': -1, 'LieferantenStatus': -1}})
        self.assertEqual([row['Adresse_ID'] for row in both['AdresseListItem']], ['12'])
        suppliers = self.call('adresseList', {'AdresseFilter': {'LieferantenStatus': 2}})
        self.assertEqual(suppliers['AdresseListItem'][0]['Adresse_ID'], '11')

    def test_address_ids_details_and_no_sensitive_card_or_credentials(self):
        detail = self.call('adresseGet', {'Adresse_ID': '10'})['AdresseItem']
        self.assertEqual(detail['Adresse_ID'], '10')
        self.assertEqual(detail['KF_Ertragkonto'], 8000)
        self.assertEqual(detail['Notizen'], 'Vollständige Notizen')
        self.assertEqual(detail['RA_Email'], 'kontakt@example.invalid')
        self.assertNotIn('VersionKey', detail)
        self.assertNotIn('KB_KKNummer', detail)
        self.assertNotIn('Kennwort', detail)
        for address_id in ('90', '', '-1', '10 OR 1=1', True, 1.5, None):
            with self.subTest(address_id=address_id), self.assertRaises(ValueError):
                self.call('adresseGet', {'Adresse_ID': address_id})

    def test_literal_searches_and_article_filters(self):
        addresses = self.call('adresseList', {'AdresseFilter': {'Matchcode': '%_'}})
        self.assertEqual(addresses['AdresseListItem'][0]['Adresse_ID'], '12')
        articles = self.call('artikelList', {'ArtikelFilter': {
            'Suchtext': 'Test', 'Warengruppe': '%_', 'Artikelart': 1, 'nurLagerArtikel': True}})
        self.assertEqual(articles['ArtikelListItem'], [{
            'Artikel_ID': '20', 'Matchcode': 'Alpha', 'ArtikelArt': 1, 'ArtikelNr': 'AR20',
            'Warengruppe': 'Gruppe %_', 'Bezeichnung': 'Testartikel'}])
        self.assertEqual(len(self.call('artikelList', {'ArtikelFilter': {'nurLagerArtikel': False}})['ArtikelListItem']), 2)
        projects = self.call('projektList', {'ProjektFilter': {'Suchtext': '%_'}})['ProjektListItem']
        self.assertEqual(projects, [{'Projekt_ID': '30', 'ProjektNr': 'P30', 'Bezeichnung': 'Testprojekt',
                                    'DatumVon': '2026-01-01', 'DatumBis': '2026-12-31', 'ProjektStatus': 4}])

    def test_explicit_extensions_and_account_range(self):
        self.assertEqual(EXTENSIONS, {'kostenstellenList', 'buchungKontoList', 'debitorList', 'kreditorList'})
        costs = self.call('kostenstellenList')
        self.assertTrue(costs['LokaleLeseerweiterung'])
        self.assertEqual(costs['KostenstelleListItem'][0]['Kostenstelle_ID'], '40')
        accounts = self.call('buchungKontoList', {'BuchungKontoFilter': {
            'Suchtext': 'Notiz', 'KontoVon': 8000, 'KontoBis': 8000}})
        self.assertEqual(accounts['BuchungKontoListItem'][0]['Konto_ID'], '51')
        self.assertNotIn('Saldo', accounts['BuchungKontoListItem'][0])

    def test_debtor_balances_use_address_not_shared_account_and_separate_currencies(self):
        result = self.call('debitorList')
        self.assertTrue(result['LokaleLeseerweiterung'])
        rows = result['DebitorListItem']
        self.assertEqual([row['Adresse_ID'] for row in rows], ['10', '12'])
        self.assertEqual(rows[0]['Salden'], [
            {'Waehrung': 'EUR', 'SaldoFW': '80', 'SaldoSW': '80', 'Beleganzahl': 2},
            {'Waehrung': 'USD', 'SaldoFW': '50', 'SaldoSW': '45', 'Beleganzahl': 1},
        ])
        self.assertEqual(rows[1]['Salden'][0]['SaldoFW'], '7')

    def test_creditor_balances_credit_notes_and_unknowns(self):
        rows = self.call('kreditorList')['KreditorListItem']
        self.assertEqual([row['Adresse_ID'] for row in rows], ['11', '12'])
        self.assertEqual(rows[0]['Salden'][0]['SaldoFW'], '25')
        self.assertIsNone(rows[1]['Salden'][0]['SaldoFW'])
        self.assertEqual(rows[1]['Salden'][0]['SaldoSW'], '1')

    def test_balance_dates_filter_documents_not_historical_payments(self):
        result = self.call('debitorList', {'DebitorFilter': {
            'DatumVon': '2026-01-02', 'DatumBis': '2026-01-02', 'Adresse_ID': '10'}})
        self.assertEqual(result['DebitorListItem'][0]['Salden'], [
            {'Waehrung': 'EUR', 'SaldoFW': '-20', 'SaldoSW': '-20', 'Beleganzahl': 1}])
        self.assertIn('Kein historischer Stichtagssaldo', result['Basis'])
        empty = self.call('debitorList', {'DebitorFilter': {'DatumBis': '2025-12-31'}})
        self.assertEqual(empty['DebitorListItem'][0]['Salden'], [])

    def test_unknown_filters_and_invalid_values_fail_instead_of_ignoring(self):
        bad = (
            ('firmaGet', {'Benutzer': True}), ('adresseList', {'AdresseFilter': {'KundenStatus': True}}),
            ('adresseList', {'AdresseFilter': {'KundenStatus': 4}}),
            ('adresseList', {'AdresseFilter': {'Matchcode': None}}),
            ('artikelList', {'ArtikelFilter': {'nurLagerArtikel': 1}}),
            ('artikelList', {'ArtikelFilter': {'Artikelart': True}}),
            ('projektList', {'ProjektFilter': {'Unbekannt': 1}}),
            ('buchungKontoList', {'BuchungKontoFilter': {'KontoVon': 9000, 'KontoBis': 8000}}),
            ('buchungKontoList', {'BuchungKontoFilter': {'KontoVon': True}}),
            ('debitorList', {'DebitorFilter': {'DatumVon': '2026-02-30'}}),
            ('kreditorList', {'KreditorFilter': {'DatumVon': '2026-02-02', 'DatumBis': '2026-01-01'}}),
            ('kreditorList', {'KreditorFilter': {'Adresse_ID': '90 OR 1=1'}}),
        )
        for method, params in bad:
            with self.subTest(method=method, params=params), self.assertRaises(ValueError):
                self.call(method, params)
        with self.assertRaises(ValueError):
            self.call('benutzerList')

    def test_reading_preserves_encrypted_source(self):
        for method in METHODS - {'adresseGet'}:
            self.call(method)
        self.call('adresseGet', {'Adresse_ID': '10'})
        self.assertEqual(self.path.read_bytes(), self.original)
