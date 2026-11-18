import base64
from pathlib import Path
import sqlite3
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.attachments import MAX_BYTES, list_attachments, read_attachment
from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase


def records(result):
    return [dict(zip(result['columns'], row)) for row in result['rows']]


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.path = root / 'anhaenge.db'
        key_path = root / 'test.key'
        key = b'attachment-test!'
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        db = sqlite3.connect(self.path)
        db.execute('PRAGMA page_size=1024')
        db.executescript('''
            CREATE TABLE ATTACHMENTITEM (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                Art VARCHAR,Groesse INTEGER,Name VARCHAR,Hinzugefuegt DATE,Gesperrt INTEGER,
                Notizen VARCHAR,Source INTEGER,Source_id INTEGER,Link VARCHAR,ParentDate DATE,
                Compressed BOOLEAN,Bezeichnung VARCHAR,Email_Anhang BOOLEAN,Vorlage BOOLEAN,
                ERechnung BOOLEAN,EmbeddedFileNames VARCHAR);
            CREATE TABLE ATTACHMENTCHUNK (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                AttachmentItem_id INTEGER,Position INTEGER,Chunk BLOB);
            CREATE TABLE ATTACHMENT (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                Source INTEGER,Source_id INTEGER,Position INTEGER,Name VARCHAR,
                Depth INTEGER,Height INTEGER,Width INTEGER,Data BLOB,Preview BLOB,Comment VARCHAR);
            CREATE TABLE ATTACHMENTALIAS (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                Art VARCHAR,Groesse INTEGER,Name VARCHAR,Hinzugefuegt DATE,Data BLOB,Notizen VARCHAR);
            CREATE TABLE ATTACHMENTALIAS_ART (_rowid INTEGER PRIMARY KEY,Firma_id INTEGER,
                AttachmentAlias_id INTEGER,DbEntity_id INTEGER,Art INTEGER);
        ''')
        self.payload = bytes(range(256)) * 6000
        items = [
            (1, 1, len(self.payload), 'Roh%_datei', 0, None),
            (2, 1, 4, 'Komprimiert', 1, None),
            (3, 1, 5, 'Fehlerhafte Positionen', 0, None),
            (4, 1, 0, 'Fehlende Chunks', 99, None),
            (5, 1, 0, 'Netzlink', 0, 'https://example.invalid/datei'),
            (6, 1, 0, 'Dateilink', 0, 'file:///nicht/lesen'),
            (7, 1, 0, 'Relativlink', 0, '../nicht/lesen'),
            (8, 1, 600, 'Viele Chunks', 0, None),
            (9, 1, 3, 'Fehlender Anfang', 0, None),
            (10, 1, 3, 'Ungültiger Inhalt', 0, None),
            (11, 1, 0, 'Leere Datei', 0, None),
            (99, 2, 6, 'Fremd', 0, None),
        ]
        db.executemany('''INSERT INTO ATTACHMENTITEM
            (_rowid,Firma_id,Groesse,Name,Compressed,Link,Art,Source,Source_id)
            VALUES (?,?,?,?,?,?,'unbekannt',987,765)''', items)
        chunks = [(30, 1, 1, 2, self.payload[200000:]),
                  (20, 1, 1, 1, self.payload[100000:200000]),
                  (10, 1, 1, 0, self.payload[:100000]),
                  (40, 1, 2, 1, b'\x78\x9c\xff\x00'),
                  (50, 1, 3, 0, b'a'), (51, 1, 3, 0, b'b'),
                  (52, 1, 3, 2, b'c'), (53, 1, 3, None, b'd'),
                  (54, 1, 9, 4, b'abc'), (55, 1, 10, 0, None),
                  (56, 1, 10, 1, b'abc'), (57, 1, 11, 0, b''),
                  (58, 1, 9, 6, b'def'),
                  (90, 2, 1, 0, b'falsch'), (91, 1, 99, 0, b'falsch'),
                  (92, 2, 99, 0, b'fremd!')]
        chunks += [(1000 + n, 1, 8, n, b'x') for n in range(600)]
        db.executemany('INSERT INTO ATTACHMENTCHUNK VALUES (?,?,?,?,?)', chunks)
        db.executemany('''INSERT INTO ATTACHMENT
            (_rowid,Firma_id,Source,Source_id,Name,Data,Preview) VALUES (?,?,987,765,?,?,?)''',
            [(1, 1, 'Alt', b'\x00\xff\xfeABC', b'Nicht ausgeben'),
             (2, 1, 'Leer', b'', b'Vorschau'), (3, 1, 'Fehlend', None, None),
             (4, 1, 'Großer Altanhang', self.payload, None),
             (99, 2, 'Fremd', b'fremd', None)])
        db.executemany('''INSERT INTO ATTACHMENTALIAS
            (_rowid,Firma_id,Art,Groesse,Name,Data) VALUES (?,?,'roh',?,?,?)''',
            [(1, 1, 6, 'Alias', b'\xffalias'), (99, 2, 5, 'Fremd', b'fremd')])
        db.executemany('INSERT INTO ATTACHMENTALIAS_ART VALUES (?,?,?,?,?)',
                       [(1, 1, 1, 123, 987), (2, 2, 1, 124, 988)])
        db.commit()
        db.close()
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
        self.reader = BusinessReader(self.database)

    def tearDown(self):
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_lists_all_storage_without_blob_and_literal_search(self):
        result = list_attachments(self.reader, 1)
        rows = records(result)
        self.assertEqual(result['gesamtzahl'], 16)
        self.assertEqual(len(rows), 16)
        self.assertFalse(result['truncated'])
        self.assertNotIn('Data', result['columns'])
        self.assertNotIn('Preview', result['columns'])
        self.assertFalse(any(isinstance(value, dict) for row in result['rows'] for value in row))
        self.assertEqual({row['Herkunftstabelle'] for row in rows},
                         {'ATTACHMENTITEM', 'ATTACHMENT', 'ATTACHMENTALIAS'})
        item = records(list_attachments(self.reader, 1, '%_'))[0]
        self.assertEqual(item['Source'], 987)
        self.assertEqual(item['Source_id'], 765)
        self.assertEqual(item['Art'], 'unbekannt')
        self.assertEqual(item['Chunks'], 3)
        self.assertEqual(item['Gespeicherte_Bytes'], len(self.payload))
        alias = next(row for row in rows if row['Speicher'] == 'alias')
        self.assertEqual(alias['Zuordnungen'], 1)
        self.assertEqual(list_attachments(self.reader, 3)['rows'], [])

    def test_stable_list_paging_and_caps(self):
        first = list_attachments(self.reader, 1, limit=2)
        second = list_attachments(self.reader, 1, limit=2, offset=first['next_offset'])
        all_rows = list_attachments(self.reader, 1)['rows']
        self.assertEqual(first['rows'] + second['rows'], all_rows[:4])
        self.assertTrue(first['truncated'])
        self.assertEqual(second['gesamtzahl'], 16)
        self.assertEqual(list_attachments(self.reader, 1, offset=100)['rows'], [])
        invalid_pages: list[dict[str, Any]] = [{'limit': 501}, {'limit': 0}, {'offset': -1}]
        for kwargs in invalid_pages:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                list_attachments(self.reader, 1, **kwargs)

    def test_chunk_pages_are_exact_raw_bytes(self):
        parts = []
        offset = 0
        while True:
            result = read_attachment(self.reader, 1, 1, offset=offset, length=MAX_BYTES)
            parts.append(base64.b64decode(result['inhalt_base64']))
            self.assertLessEqual(result['gelieferte_bytes'], MAX_BYTES)
            self.assertEqual(result['chunkmetadaten']['Anzahl'], 3)
            if result['naechster_byteversatz'] is None:
                break
            offset = result['naechster_byteversatz']
        self.assertEqual(b''.join(parts), self.payload)
        part = read_attachment(self.reader, 1, 1, offset=99999, length=3)
        self.assertEqual(base64.b64decode(part['inhalt_base64']), self.payload[99999:100002])
        self.assertEqual(part['auffaelligkeiten'], [])
        beyond = read_attachment(self.reader, 1, 1, offset=len(self.payload) + 1)
        self.assertEqual(beyond['gelieferte_bytes'], 0)
        self.assertFalse(beyond['weitere_bytes'])

    def test_legacy_alias_non_utf8_and_empty(self):
        for storage, expected in [('legacy', b'\x00\xff\xfeABC'), ('alias', b'\xffalias')]:
            with self.subTest(storage=storage):
                result = read_attachment(self.reader, 1, 1, storage, offset=1, length=3)
                self.assertEqual(base64.b64decode(result['inhalt_base64']), expected[1:4])
                self.assertEqual(result['gespeicherte_bytes'], len(expected))
                self.assertEqual(result['naechster_byteversatz'], 4)
        for storage, attachment_id in [('legacy', 2), ('item', 11)]:
            result = read_attachment(self.reader, 1, attachment_id, storage)
            self.assertEqual(result['inhalt_base64'], '')
            self.assertFalse(result['weitere_bytes'])

    def test_large_legacy_blob_is_read_without_querying_full_content(self):
        result = read_attachment(self.reader, 1, 4, 'legacy', offset=1_100_000, length=MAX_BYTES)
        self.assertEqual(base64.b64decode(result['inhalt_base64']),
                         self.payload[1_100_000:1_100_000 + MAX_BYTES])

    def test_blob_reader_enforces_table_company_and_byte_limits(self):
        self.assertEqual(self.database.read_blob('ATTACHMENT', 'Data', 1, 1, 1, 2), b'\xff\xfe')
        for table, column, company, row, offset, length in (
            ('ATTACHMENT', 'Preview', 1, 1, 0, 1),
            ('FIRMA', 'Name', 1, 1, 0, 1),
            ('ATTACHMENT', 'Data', 2, 1, 0, 1),
            ('ATTACHMENT', 'Data', 1, 1, -1, 1),
            ('ATTACHMENT', 'Data', 1, 1, 0, MAX_BYTES + 1),
        ):
            with self.subTest(table=table, column=column, company=company, offset=offset, length=length):
                with self.assertRaises(ValueError):
                    self.database.read_blob(table, column, company, row, offset, length)

    def test_company_scope_and_validation(self):
        for storage in ('item', 'legacy', 'alias'):
            for attachment_id in (99, 12345):
                with self.subTest(storage=storage, attachment_id=attachment_id), self.assertRaises(ValueError):
                    read_attachment(self.reader, 1, attachment_id, storage)
        invalid_ranges: list[dict[str, Any]] = [
            {'offset': -1}, {'offset': True}, {'length': 0}, {'length': MAX_BYTES + 1},
            {'length': True}, {'storage': '../datei'}, {'storage': None}]
        for kwargs in invalid_ranges:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                read_attachment(self.reader, 1, 1, **kwargs)
        for attachment_id in (0, -1, True, '1'):
            with self.subTest(attachment_id=attachment_id), self.assertRaises(ValueError):
                read_attachment(self.reader, 1, attachment_id)

    def test_links_never_open_and_compression_never_unpacks(self):
        with patch('builtins.open', side_effect=AssertionError('Dateizugriff')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('Netzzugriff')), \
                patch('zlib.decompress', side_effect=AssertionError('Entpacken')):
            for attachment_id in (5, 6, 7):
                result = read_attachment(self.reader, 1, attachment_id)
                self.assertEqual(result['linkstatus'], 'Nicht geöffnet')
                self.assertEqual(result['gelieferte_bytes'], 0)
            compressed = read_attachment(self.reader, 1, 2)
            self.assertEqual(base64.b64decode(compressed['inhalt_base64']), b'\x78\x9c\xff\x00')
            self.assertEqual(compressed['compressed_roh'], 1)
            self.assertTrue(any('Kompression' in text for text in compressed['auffaelligkeiten']))
            unknown = read_attachment(self.reader, 1, 4)
            self.assertEqual(unknown['compressed_roh'], 99)

    def test_damage_and_row_cap_are_explicit(self):
        result = read_attachment(self.reader, 1, 3)
        self.assertEqual(result['status'], 'Auffälligkeiten')
        self.assertTrue(any('Chunkpositionen' in text for text in result['auffaelligkeiten']))
        self.assertTrue(any('Groesse' in text for text in result['auffaelligkeiten']))
        missing = read_attachment(self.reader, 1, 4)
        self.assertIn('Keine gespeicherten Chunks', missing['auffaelligkeiten'])
        prefix = read_attachment(self.reader, 1, 9)
        self.assertTrue(any('Anfang' in text for text in prefix['auffaelligkeiten']))
        for storage, attachment_id in [('item', 10), ('legacy', 3)]:
            damaged = read_attachment(self.reader, 1, attachment_id, storage)
            self.assertEqual(damaged['status'], 'Auffälligkeiten')
            self.assertIsNone(damaged['naechster_byteversatz'])
        capped = read_attachment(self.reader, 1, 8, length=600)
        self.assertTrue(capped['abfrage_gekuerzt'])
        self.assertTrue(any('Lücken' in text for text in prefix['auffaelligkeiten']))
        self.assertEqual(capped['gelieferte_bytes'], 500)
        self.assertEqual(capped['naechster_byteversatz'], 500)
        rest = read_attachment(self.reader, 1, 8, offset=500, length=600)
        self.assertEqual(rest['gelieferte_bytes'], 100)
        self.assertIsNone(rest['naechster_byteversatz'])


if __name__ == '__main__':
    unittest.main()
