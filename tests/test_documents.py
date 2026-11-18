from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase
from mo_local_mcp.documents import document_links, search_documents


class DocumentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root / 'office.db', root / 'test.key'
        key = b'document-testkey'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(path)
        db.execute('PRAGMA page_size=1024')
        db.executescript('''
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,BelegNr,Text,Referenz,Waehrung);
            CREATE TABLE AUFTRAG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,AuftragsNr,BestellNr,Betreff,
                Waehrung,Entwurf,Posten_id);
            CREATE TABLE BESTELLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,BestellNr,LieferNr,Betreff,
                Waehrung,Entwurf,Posten_id);
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,ReNr,BuText,Referenz,Waehrung,
                Entwurf,Buchung_id,BuchungSR_id);
            CREATE TABLE ZAHLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,ReNr,BuText,Referenz,Waehrung,
                Buchung_id,ValutaBuchung_id);
            CREATE TABLE AUFTRAG_VORBELEG (_rowid INTEGER PRIMARY KEY,Firma_id,Auftrag_id,Vorbeleg_id);
            CREATE TABLE BESTELL_VORBELEG (_rowid INTEGER PRIMARY KEY,Firma_id,Bestell_id,Vorbeleg_id);
            CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Posten_id);
            CREATE TABLE ZAHLUNGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Zahlung_id,Postenposition_id);
            INSERT INTO BUCHUNG VALUES
                (30,1,'2025-01-02','SUCHE B','Buchungstext','B-Referenz','EUR'),
                (31,1,'2025-01-03','Einzel','100%_voll\\ständig','Literal','EUR'),
                (32,1,'2025-01-03','Leer',NULL,NULL,'EUR'),
                (99,2,'2025-01-02','SUCHE geheim','Fremde Buchung','vertraulich','EUR');
            INSERT INTO AUFTRAG VALUES
                (10,1,'2025-01-02','SUCHE V','Bestell-Referenz','Verkaufstext','USD',1,20),
                (11,1,'2025-01-04','Folge','F-Referenz','Folgetext','EUR',0,0),
                (99,2,'2025-01-02','SUCHE geheim','vertraulich','Fremder Verkauf','EUR',0,20);
            INSERT INTO BESTELLUNG VALUES
                (12,1,'2025-01-02','SUCHE E','Liefer-Referenz','Einkaufstext','EUR',0,20),
                (13,1,'2025-01-05','Weiter','L13','Nächster Einkauf','EUR',NULL,NULL),
                (99,2,'2025-01-02','SUCHE geheim','vertraulich','Fremder Einkauf','EUR',0,20);
            INSERT INTO POSTEN VALUES
                (20,1,'2025-01-02','SUCHE P','Postentext','P-Referenz','EUR',0,30,99),
                (21,1,'2025-01-04','Anderer Posten','Postentext','R21','USD',NULL,0,NULL),
                (99,2,'2025-01-02','SUCHE geheim','Fremder Posten','vertraulich','EUR',0,30,0);
            INSERT INTO ZAHLUNG VALUES
                (40,1,'2025-01-02','SUCHE Z','Zahlungstext','Z-Referenz','EUR',30,999),
                (41,1,'2025-01-04','Ausgleich','Zahlungstext','R41','USD',0,NULL),
                (99,2,'2025-01-02','SUCHE geheim','Fremde Zahlung','vertraulich','EUR',30,0);
            INSERT INTO AUFTRAG_VORBELEG VALUES
                (1,1,10,11),(2,1,10,11),(3,1,11,10),(4,1,10,10),
                (5,1,10,999),(6,1,99,10),(7,2,99,10),(8,1,10,0),(9,1,10,NULL);
            INSERT INTO BESTELL_VORBELEG VALUES (1,1,12,13),(2,1,13,12),(3,2,99,12);
            INSERT INTO POSTENPOSITION VALUES
                (200,1,20),(201,1,20),(202,1,21),(203,1,999),(204,1,0),(299,2,20);
            INSERT INTO ZAHLUNGSPOSITION VALUES
                (100,1,40,200),(101,1,40,201),(102,1,40,202),(103,1,40,999),
                (104,1,40,299),(105,1,40,203),(106,1,40,0),(107,1,40,204),
                (108,2,40,200),(109,1,99,200),(110,1,41,200),
                (111,1,0,200),(112,1,NULL,200),(113,1,40,NULL);
        ''')
        # Viele gleiche Datumswerte erzwingen die stabile bereichsübergreifende
        # Sortierung. Alle Daten bleiben synthetisch und im temporären Verzeichnis.
        db.executemany('INSERT INTO BUCHUNG VALUES (?,1,?,?,?,?,?)', [
            (1000 + i, '2025-02-01', f'SEITE {i}', '', '', 'EUR') for i in range(505)
        ])
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
        self.reader = BusinessReader(database)

    def test_joint_search_stable_pages_company_and_navigation(self):
        first = search_documents(self.reader, 1, 'SUCHE', limit=2)
        second = search_documents(self.reader, 1, 'SUCHE', limit=2, offset=first['naechster_versatz'])
        third = search_documents(self.reader, 1, 'SUCHE', limit=2, offset=second['naechster_versatz'])
        rows = first['treffer'] + second['treffer'] + third['treffer']
        self.assertEqual([(r['bereich'], r['id']) for r in rows],
                         [('buchung', 30), ('einkauf', 12), ('posten', 20), ('verkauf', 10), ('zahlung', 40)])
        self.assertTrue(first['gekuerzt'])
        self.assertFalse(third['gekuerzt'])
        self.assertIsNone(third['naechster_versatz'])
        self.assertEqual(third['anzahl'], 1)
        self.assertEqual(rows[3]['entwurf'], 1)
        self.assertEqual(rows[3]['waehrung'], 'USD')
        self.assertEqual(rows[3]['referenz'], 'Bestell-Referenz')
        self.assertEqual(rows[3]['text'], 'Verkaufstext')
        self.assertEqual(rows[3]['navigation'], {'werkzeug': 'verkaufsbeleg_abrufen',
                         'parameter': {'firma_id': 1, 'beleg_id': 10}})
        self.assertNotIn('vertraulich', repr(rows))
        self.assertEqual(len(search_documents(self.reader, 2, 'SUCHE')['treffer']), 5)

    def test_literal_search_all_fields_and_inclusive_dates(self):
        for search in ('100%', '_voll', '\\ständig', '100%_voll\\ständig'):
            with self.subTest(search=search):
                self.assertEqual([r['id'] for r in search_documents(self.reader, 1, search)['treffer']], [31])
        self.assertEqual(search_documents(self.reader, 1, "' OR 1=1 --")['treffer'], [])
        for search, area in [('Buchungstext', 'buchung'), ('Bestell-Referenz', 'verkauf'),
                             ('Liefer-Referenz', 'einkauf'), ('P-Referenz', 'posten'), ('Z-Referenz', 'zahlung')]:
            with self.subTest(search=search):
                self.assertEqual(search_documents(self.reader, 1, search)['treffer'][0]['bereich'], area)
        self.assertEqual(len(search_documents(self.reader, 1, 'SUCHE', '2025-01-02', '2025-01-02')['treffer']), 5)
        self.assertEqual(search_documents(self.reader, 1, 'SUCHE', '2025-01-03')['treffer'], [])
        self.assertEqual(search_documents(self.reader, 1, 'unauffindbar')['treffer'], [])

    def test_search_limit_500_has_complete_continuation(self):
        first = search_documents(self.reader, 1, 'SEITE', limit=500)
        second = search_documents(self.reader, 1, 'SEITE', limit=500, offset=first['naechster_versatz'])
        self.assertEqual(first['anzahl'], 500)
        self.assertEqual(first['naechster_versatz'], 500)
        self.assertEqual([r['id'] for r in second['treffer']], list(range(1500, 1505)))
        self.assertIsNone(second['naechster_versatz'])
        empty = search_documents(self.reader, 1, 'SEITE', offset=600)
        self.assertEqual(empty['treffer'], [])
        self.assertIsNone(empty['naechster_versatz'])

    def test_cycles_are_immediate_and_duplicate_previous_edges_collapse(self):
        result = document_links(self.reader, 1, 'verkauf', 10)
        edges = result['verknuepfungen']
        previous = [e for e in edges if e['beziehung'] == 'AUFTRAG_VORBELEG']
        self.assertEqual(len(previous), 5)
        self.assertEqual([e['beziehungs_id'] for e in previous if (e['quelle_id'], e['ziel_id']) == (10, 11)], [1])
        self.assertEqual([e['richtung'] for e in previous if e['quelle_id'] == e['ziel_id']], ['beidseitig'])
        self.assertEqual(len(edges), 6)
        self.assertFalse(any(e['ziel_bereich'] == 'buchung' for e in edges))
        self.assertTrue(any(e['richtung'] == 'eingehend' for e in edges))
        for edge in previous:
            if edge['quelle_id'] == 99 or edge['ziel_id'] == 999:
                self.assertEqual(edge['status'], 'Verknüpfung nicht auflösbar')
        foreign_source = next(e for e in previous if e['quelle_id'] == 99)
        self.assertIsNone(foreign_source['quelle_navigation'])
        self.assertNotIn('vertraulich', repr(result))
        purchase = document_links(self.reader, 1, 'einkauf', 12)['verknuepfungen']
        self.assertEqual(len(purchase), 3)
        self.assertEqual(sum(e['beziehung'] == 'BESTELL_VORBELEG' for e in purchase), 2)

    def test_shared_payment_paths_and_broken_targets_remain_explicit(self):
        with patch.object(self.reader.database, 'query', wraps=self.reader.database.query) as query:
            result = document_links(self.reader, 1, 'zahlung', 40)
            self.assertEqual(query.call_count, 2)
        edges = result['verknuepfungen']
        allocations = {e['zahlungsposition_id']: e for e in edges if e['zahlungsposition_id'] is not None}
        self.assertEqual(set(allocations), {100, 101, 102, 103, 104, 105})
        self.assertEqual(allocations[100]['ziel_id'], 20)
        self.assertEqual(allocations[101]['ziel_id'], 20)
        self.assertEqual(allocations[102]['ziel_id'], 21)
        self.assertEqual(allocations[100]['postenposition_id'], 200)
        for position_id in (103, 104, 105):
            edge = allocations[position_id]
            self.assertEqual(edge['status'], 'Verknüpfung nicht auflösbar')
            self.assertIsNone(edge['ziel_navigation'])
        self.assertIsNone(allocations[104]['ziel_id'])
        self.assertEqual(allocations[104]['postenposition_id'], 299)
        missing_booking = next(e for e in edges if e['beziehung'] == 'ZAHLUNG.ValutaBuchung_id')
        self.assertEqual(missing_booking['ziel_id'], 999)
        self.assertIsNone(missing_booking['ziel_navigation'])
        self.assertEqual(len(edges), 8)
        self.assertNotIn('vertraulich', repr(result))

    def test_incoming_payment_and_booking_edges_stay_in_company(self):
        edges = document_links(self.reader, 1, 'posten', 20)['verknuepfungen']
        incoming = {e['zahlungsposition_id']: e for e in edges if e['zahlungsposition_id'] is not None}
        self.assertEqual(set(incoming), {100, 101, 109, 110})
        self.assertEqual(incoming[109]['status'], 'Verknüpfung nicht auflösbar')
        self.assertIsNone(incoming[109]['quelle_navigation'])
        self.assertEqual(incoming[110]['quelle_navigation']['parameter'], {'firma_id': 1, 'zahlung_id': 41})
        foreign_booking = next(e for e in edges if e['beziehung'] == 'POSTEN.BuchungSR_id')
        self.assertIsNone(foreign_booking['ziel_navigation'])
        booking = document_links(self.reader, 1, 'buchung', 30)['verknuepfungen']
        self.assertEqual([(e['quelle_bereich'], e['quelle_id']) for e in booking], [('posten', 20), ('zahlung', 40)])
        for edge in booking:
            self.assertEqual(edge['richtung'], 'eingehend')
            self.assertEqual(edge['status'], 'aufgelöst')
            self.assertEqual(edge['ziel_navigation']['parameter'], {'firma_id': 1, 'buchung_id': 30})
        self.assertEqual(document_links(self.reader, 1, 'buchung', 32)['verknuepfungen'], [])

    def test_links_pages_match_single_page_without_duplicates(self):
        all_edges = document_links(self.reader, 1, 'zahlung', 40)['verknuepfungen']
        edges, offset = [], 0
        while offset is not None:
            page = document_links(self.reader, 1, 'zahlung', 40, limit=2, offset=offset)
            self.assertLessEqual(page['anzahl'], 2)
            edges.extend(page['verknuepfungen'])
            offset = page['naechster_versatz']
        self.assertEqual(edges, all_edges)
        self.assertEqual(len({(e['beziehung'], e['beziehungs_id']) for e in edges}), len(edges))
        page = document_links(self.reader, 1, 'zahlung', 40, offset=500)
        self.assertEqual(page['verknuepfungen'], [])
        self.assertIsNone(page['naechster_versatz'])

    def test_validation_and_foreign_roots(self):
        for kwargs in ({'limit': 501}, {'limit': 0}, {'limit': True}, {'offset': -1}, {'offset': False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_documents(self.reader, 1, '', **kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                document_links(self.reader, 1, 'buchung', 30, **kwargs)
        for date_from, date_to in (('2025-02-30', None), (None, '01.01.2025'),
                                  ('2025-02-01', '2025-01-01')):
            with self.subTest(date_from=date_from, date_to=date_to), self.assertRaises(ValueError):
                search_documents(self.reader, 1, '', date_from=date_from, date_to=date_to)
        for company in (0, True, '1'):
            with self.subTest(company=company), self.assertRaises(ValueError):
                search_documents(self.reader, company, '')
        for area in ('AUFTRAG', 'falsch', "buchung' OR 1=1", None, []):
            with self.subTest(area=area), self.assertRaises(ValueError):
                document_links(self.reader, 1, area, 30)
        for record_id in (0, False, '30'):
            with self.subTest(record_id=record_id), self.assertRaises(ValueError):
                document_links(self.reader, 1, 'buchung', record_id)
        for area in ('buchung', 'verkauf', 'einkauf', 'posten', 'zahlung'):
            with self.subTest(area=area), self.assertRaisesRegex(ValueError, 'nicht gefunden'):
                document_links(self.reader, 1, area, 99)
        with self.assertRaises(ValueError):
            search_documents(self.reader, 1, None)


if __name__ == '__main__':
    unittest.main()
