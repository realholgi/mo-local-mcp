"""Ausschließlich lesende Entschlüsselung des beobachteten SEE-AES-128-OFB-Formats bei Bedarf."""

import base64
import json
from pathlib import Path
import threading
import time
import uuid

import apsw
from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms


class _EncryptedFile(apsw.VFSFile):
    def __init__(self, name, flags, key, page_size):
        super().__init__("", name, flags)
        self.key = key
        self.page_size = page_size

    def xRead(self, amount, offset):
        result = bytearray()
        end = offset + amount
        for start in range(offset // self.page_size * self.page_size, end, self.page_size):
            raw = super().xRead(self.page_size, start)
            page_number = start // self.page_size + 1
            cipher = Cipher(algorithms.AES(self.key), OFB(page_number.to_bytes(16, "little")))
            decoder = cipher.decryptor()
            page = bytearray(decoder.update(raw) + decoder.finalize())
            if start == 0:
                page[16:24] = raw[16:24]
            result.extend(page[max(offset - start, 0):min(end - start, self.page_size)])
        return bytes(result)

    def xWrite(self, data, offset):
        raise apsw.ReadOnlyError("Schreibzugriffe auf die Datenbank sind gesperrt")

    def xTruncate(self, size):
        raise apsw.ReadOnlyError("Das Kürzen der Datenbank ist gesperrt")


class _EncryptedVFS(apsw.VFS):
    def __init__(self, key, page_size):
        self.name = "mo-local-mcp-" + uuid.uuid4().hex
        self.key = key
        self.page_size = page_size
        super().__init__(self.name, "")

    def xOpen(self, name, flags):
        if not flags[0] & apsw.SQLITE_OPEN_MAIN_DB or flags[0] & apsw.SQLITE_OPEN_READWRITE:
            raise apsw.ReadOnlyError("Nur die schreibgeschützte Hauptdatenbank darf geöffnet werden")
        return _EncryptedFile(name, flags, self.key, self.page_size)


def _authorize(action, first, second, database, source):
    if action in (apsw.SQLITE_SELECT, apsw.SQLITE_READ, apsw.SQLITE_RECURSIVE):
        return apsw.SQLITE_OK
    if action == apsw.SQLITE_FUNCTION and second.lower() not in {
        "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
    }:
        return apsw.SQLITE_OK
    if action == apsw.SQLITE_PRAGMA and first in {"table_xinfo", "foreign_key_list", "index_list"}:
        return apsw.SQLITE_OK
    return apsw.SQLITE_DENY


def _cell(value):
    if isinstance(value, bytes):
        return {"type": "blob", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, int) and abs(value) > 2**53 - 1:
        return str(value)
    return value


class OfficeDatabase:
    """Ein unveränderlicher, ruhender Datenbankstand. Öffnet die Quelle niemals schreibend."""

    def __init__(self, path, key_file):
        self.path = Path(path).expanduser().resolve(strict=True)
        self._lock = threading.Lock()
        self._identity = self._fingerprint()
        with self.path.open("rb") as source:
            header = source.read(100)
        if len(header) != 100 or header[:16] == b"SQLite format 3\0":
            raise ValueError("Ein verschlüsselter MonKey-Office-Datenbankstand wird erwartet")
        self.page_size = int.from_bytes(header[16:18], "big")
        if self.page_size == 1:
            self.page_size = 65536
        if self.page_size not in {512, 1024, 2048, 4096, 8192, 16384, 32768, 65536}:
            raise ValueError("Ungültige Datenbankseitengröße")
        if header[20] != 0 or header[21:24] != b"\x40\x20\x20":
            raise ValueError("Nicht unterstütztes Verschlüsselungsprofil: SEE AES-128-OFB ohne Nonce wird erwartet")
        if self.path.stat().st_size % self.page_size:
            raise ValueError("Unvollständiger Datenbankstand")
        key_path = Path(key_file).expanduser()
        if key_path.stat().st_mode & 0o077:
            raise ValueError("Schlüsseldatei muss privat sein; chmod 600 auf die Schlüsseldatei anwenden")
        key = key_path.read_bytes()
        if not key or key.startswith((b"aes256:", b"rc4:")):
            raise ValueError("Der wiederhergestellte AES-128-Datenbankschlüssel wird erwartet")
        if key.startswith(b"aes128:"):
            key = key[7:]
        if not key:
            raise ValueError("Leerer Verschlüsselungsschlüssel")
        self._vfs = _EncryptedVFS((key * ((16 + len(key) - 1) // len(key)))[:16], self.page_size)
        self._db = None
        try:
            self._db = apsw.Connection(
                self.path.as_uri() + "?immutable=1",
                flags=apsw.SQLITE_OPEN_READONLY | apsw.SQLITE_OPEN_URI,
                vfs=self._vfs.name,
            )
            self._db.execute("PRAGMA query_only=ON")
            self._db.execute("PRAGMA trusted_schema=OFF")
            self._db.execute("PRAGMA temp_store=MEMORY")
            self._db.execute("PRAGMA mmap_size=0")
            self._db.limit(apsw.SQLITE_LIMIT_ATTACHED, 0)
            self._db.limit(apsw.SQLITE_LIMIT_LENGTH, 1_000_000)
            self._db.limit(apsw.SQLITE_LIMIT_SQL_LENGTH, 100_000)
            self._db.set_authorizer(_authorize)
            self.query("SELECT count(*) FROM sqlite_schema")
        except Exception:
            self.close()
            raise

    def _fingerprint(self):
        for suffix in ("-wal", "-journal"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists() and sidecar.stat().st_size:
                raise ValueError("WAL/Journal gefunden. Einen geschlossenen Datenbankstand mit abgeschlossenem Checkpoint verwenden, keine laufende Datenbank")
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def _unchanged(self):
        if self._fingerprint() != self._identity:
            raise ValueError("Datenbankstand wurde verändert. Den Server mit einem ruhenden Datenbankstand neu starten")

    def query(self, sql, parameters=None, limit=100):
        """SELECT-/CTE-Abfragen mit Grenzen für Zeilen, Ausgabegröße, Speicher und VM-Laufzeit ausführen."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("anzahl muss zwischen 1 und 500 liegen")
        if not isinstance(sql, str) or not sql.strip() or len(sql) > 100_000:
            raise ValueError("Eine SELECT-Abfrage mit höchstens 100000 Zeichen angeben")
        statement = sql.strip().removesuffix(";")
        with self._lock:
            self._unchanged()
            deadline = time.monotonic() + 5
            self._db.set_progress_handler(lambda: time.monotonic() > deadline, 1000)
            cursor = self._db.cursor()
            columns = []

            def capture_columns(current, statement, bindings):
                columns.extend(item[0] for item in current.get_description())
                return True

            cursor.set_exec_trace(capture_columns)
            try:
                cursor.execute(f"SELECT * FROM ({statement}\n) LIMIT {limit + 1}", parameters)
                rows = []
                size = 0
                truncated = False
                for row in cursor:
                    if len(rows) == limit:
                        truncated = True
                        break
                    values = [_cell(value) for value in row]
                    size += len(json.dumps(values, ensure_ascii=True))
                    if size > 1_000_000:
                        truncated = True
                        break
                    rows.append(values)
                self._unchanged()
                return {"columns": columns, "rows": rows, "truncated": truncated}
            finally:
                cursor.close()
                self._db.set_progress_handler(None)

    def describe(self, table):
        schema = self.query("SELECT type, sql FROM sqlite_schema WHERE name = ? AND type IN ('table', 'view')", [table])
        if not schema["rows"]:
            raise ValueError("Unbekannte Tabelle oder Sicht")
        return {
            "name": table,
            "type": schema["rows"][0][0],
            "sql": schema["rows"][0][1],
            "columns": self.query("SELECT * FROM pragma_table_xinfo(?)", [table], 500),
            "foreign_keys": self.query("SELECT * FROM pragma_foreign_key_list(?)", [table], 500),
            "indexes": self.query("SELECT * FROM pragma_index_list(?)", [table], 500),
        }

    def close(self):
        if self._db is not None:
            self._db.close()
        self._vfs.unregister()
