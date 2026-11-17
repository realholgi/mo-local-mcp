import base64
from pathlib import Path
import sqlite3
import tempfile
import unittest

import apsw
from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.database import OfficeDatabase, _EncryptedFile


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "office.db"
        self.key = self.root / "database.key"
        self.key.write_bytes(b"synthetisch-test!")
        self.key.chmod(0o600)
        plain = sqlite3.connect(self.path)
        plain.execute("PRAGMA page_size=1024")
        plain.executescript("""
            CREATE TABLE company (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE invoice (id INTEGER PRIMARY KEY, company_id INTEGER REFERENCES company(id), amount REAL, payload BLOB);
            CREATE INDEX invoice_company ON invoice(company_id);
            INSERT INTO company VALUES(1, 'Testfirma');
        """)
        plain.executemany("INSERT INTO invoice VALUES(?, 1, ?, ?)",
                          [(i, i / 10, b"testinhalt" * 40) for i in range(1, 201)])
        plain.commit()
        plain.close()
        self.plain = self.path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(self.plain), 1024):
            cipher = Cipher(algorithms.AES(self.key.read_bytes()[:16]), OFB((start // 1024 + 1).to_bytes(16, "little")))
            encoder = cipher.encryptor()
            encrypted.extend(encoder.update(self.plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = self.plain[16:24]
        self.path.write_bytes(encrypted)
        self.original = bytes(encrypted)
        self.database = OfficeDatabase(self.path, self.key)
        self.addCleanup(self.database.close)

    def test_multi_page_query_binding_and_pagination(self):
        result = self.database.query(
            "WITH totals AS (SELECT company_id, count(*) AS n, sum(amount) AS total FROM invoice GROUP BY company_id) "
            "SELECT name, n, total FROM totals JOIN company ON company.id=company_id WHERE name=:name",
            {"name": "Testfirma"},
        )
        self.assertEqual(result["rows"][0][:2], ["Testfirma", 200])
        self.assertAlmostEqual(result["rows"][0][2], 2010)
        result = self.database.query("SELECT id FROM invoice ORDER BY id", limit=2)
        self.assertEqual(result, {"columns": ["id"], "rows": [[1], [2]], "truncated": True})
        result = self.database.query("SELECT id FROM invoice WHERE id > ? ORDER BY id", [198], 2)
        self.assertEqual(result["rows"], [[199], [200]])
        self.assertFalse(result["truncated"])

    def test_empty_results_and_duplicate_columns(self):
        self.assertEqual(self.database.query("SELECT id FROM invoice WHERE 0"),
                         {"columns": ["id"], "rows": [], "truncated": False})
        result = self.database.query("SELECT 1 AS value, 2 AS value")
        self.assertEqual(result["rows"], [[1, 2]])
        self.assertEqual(len(result["columns"]), 2)

    def test_schema_and_lossless_values(self):
        description = self.database.describe("invoice")
        self.assertIn("company_id", [row[1] for row in description["columns"]["rows"]])
        self.assertEqual(description["foreign_keys"]["rows"][0][2], "company")
        self.assertEqual(description["indexes"]["rows"][0][1], "invoice_company")
        result = self.database.query("SELECT 9223372036854775807, x'00ff', NULL")
        self.assertEqual(result["rows"], [["9223372036854775807", {"type": "blob", "base64": base64.b64encode(b'\0\xff').decode()}, None]])

    def test_refuses_writes_attachments_extensions_and_multiple_statements(self):
        statements = [
            "DELETE FROM invoice", "UPDATE invoice SET amount=0 RETURNING id",
            "DROP TABLE invoice", "PRAGMA query_only=OFF", "VACUUM INTO 'abfluss.db'",
            "ATTACH DATABASE ':memory:' AS other", "SELECT 1); DELETE FROM invoice; --",
            "SELECT 1; SELECT 2", "SELECT load_extension('fehlt')",
            "SELECT * FROM pragma_journal_mode('DELETE')",
            "SELECT writefile('abfluss.db', 'privat')", "SELECT readfile('/etc/passwd')",
        ]
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(apsw.Error):
                self.database.query(sql)
        self.assertEqual(self.database.query("SELECT count(*) FROM invoice")["rows"], [[200]])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["database.key", "office.db"])

    def test_rejects_changed_snapshot_and_sidecars(self):
        wal = Path(str(self.path) + "-wal")
        wal.write_bytes(b"Daten ohne abgeschlossenen Checkpoint")
        with self.assertRaisesRegex(ValueError, "WAL/Journal"):
            self.database.query("SELECT 1")
        wal.unlink()
        self.path.write_bytes(self.original)
        with self.assertRaisesRegex(ValueError, "Datenbankstand wurde verändert"):
            self.database.query("SELECT 1")

    def test_wrong_key_and_nonce_profile_fail_closed(self):
        wrong = self.root / "wrong.key"
        wrong.write_bytes(b"falscher-schluessel")
        wrong.chmod(0o600)
        with self.assertRaises(apsw.NotADBError):
            OfficeDatabase(self.path, wrong)
        changed = bytearray(self.original)
        changed[20] = 12
        self.path.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "Nicht unterstütztes Verschlüsselungsprofil"):
            OfficeDatabase(self.path, self.key)

    def test_reads_crossing_page_boundaries(self):
        flags = [apsw.SQLITE_OPEN_MAIN_DB | apsw.SQLITE_OPEN_READONLY, 0]
        file = _EncryptedFile(str(self.path), flags, self.key.read_bytes()[:16], 1024)
        try:
            for offset, length in [(0, 100), (16, 8), (1000, 80), (2040, 3072)]:
                self.assertEqual(file.xRead(length, offset), self.plain[offset:offset + length])
        finally:
            file.xClose()

    def test_limits_values_and_result_size(self):
        for limit in [0, 501, True, 2.5]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.database.query("SELECT 1", limit=limit)
        result = self.database.query("SELECT zeroblob(200000) FROM invoice", limit=10)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["rows"]), 3)
        with self.assertRaises(apsw.TooBigError):
            self.database.query("SELECT zeroblob(1000001)")


if __name__ == "__main__":
    unittest.main()
