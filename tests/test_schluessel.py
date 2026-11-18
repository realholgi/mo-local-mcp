"""Versionsprofile mit synthetischen Universal-Programmdateien prüfen."""

import base64
from contextlib import closing, redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
from pathlib import Path
import stat
import struct
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from mo_local_mcp import schluessel
from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms


class SchluesselprofilTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.alt_key = bytes(range(32))
        self.neu_key = bytes(range(32, 64))
        alt_hash, self.alt, self.alt_datei = self.programmdatei("alt", self.alt_key, False)
        neu_hash, self.neu, self.neu_datei = self.programmdatei("neu", self.neu_key, True)
        profiles = patch.dict(schluessel.PROFILE, {alt_hash: self.alt, neu_hash: self.neu}, clear=True)
        profiles.start()
        self.addCleanup(profiles.stop)
        standardpfad = patch.object(schluessel, "STANDARD_PROGRAMMDATEI", self.neu_datei)
        standardpfad.start()
        self.addCleanup(standardpfad.stop)

    def programmdatei(self, name, key, neu):
        path = self.root / name
        encoded = base64.b64encode(key)
        constants = list(dict.fromkeys(encoded))
        if neu:
            constants.reverse()
        profil = schluessel.Schluesselprofil(
            version="Synthetisch 2.0" if neu else "Synthetisch 1.0",
            konstanten_offset=0x380 if neu else 0x300,
            eintrag_groesse=24 if neu else 16,
            zeiger_offset=8 if neu else 0,
            zeichen_marker=2 if neu else 1,
            zeichenindizes=tuple(constants.index(value) for value in encoded),
        )
        slice_offset = 192 if neu else 128
        text_vmaddr = 0x200000000 if neu else 0x100000000
        strings_vmaddr = text_vmaddr + (0x8000 if neu else 0x4000)
        strings_fileoff = 0x1800 if neu else 0x1000
        data = bytearray(slice_offset + strings_fileoff + 2 * len(constants))
        struct.pack_into(">II", data, 0, 0xCAFEBABE, 2)
        struct.pack_into(">IIIII", data, 8, 0x1000007, 0, 64, 16, 0)
        struct.pack_into(">IIIII", data, 28, 0x100000C, 0, slice_offset, len(data) - slice_offset, 0)
        struct.pack_into("<IiiIIIII", data, slice_offset, 0xFEEDFACF, 0x100000C, 0, 2, 4, 240, 0, 0)
        position = slice_offset + 32
        for name, vmaddr, vmsize, fileoff, filesize in (
            (b"__PAGEZERO", 0, text_vmaddr, 0, 0),
            (b"__TEXT", text_vmaddr, 0x1000, 0, 0x1000),
            (b"__CONST", strings_vmaddr, 0x1000, strings_fileoff, 2 * len(constants)),
        ):
            struct.pack_into("<II16sQQQQiiII", data, position, 0x19, 72, name,
                             vmaddr, vmsize, fileoff, filesize, 7, 3, 0, 0)
            position += 72
        struct.pack_into("<II16s", data, position, 0x1B, 24, b"synthetische-uuid")
        for index, value in enumerate(constants):
            location = slice_offset + profil.konstanten_offset + profil.eintrag_groesse * index + profil.zeiger_offset
            struct.pack_into("<Q", data, location, strings_vmaddr + 2 * index)
            location = slice_offset + strings_fileoff + 2 * index
            data[location:location + 2] = bytes((profil.zeichen_marker, value))
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest(), profil, path

    def cli(self, *arguments):
        output = io.StringIO()
        with patch.object(sys, "argv", ["mo-schluessel-wiederherstellen", *map(str, arguments)]), redirect_stdout(output):
            schluessel.main()
        return output.getvalue()

    def datenbank(self, key):
        path = self.root / f"synthetisch-{key[0]}.db"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("PRAGMA page_size=1024")
            connection.execute("CREATE TABLE synthetisch (nummer INTEGER)")
            connection.execute("INSERT INTO synthetisch VALUES (42)")
            connection.commit()
        klartext = path.read_bytes()
        verschluesselt = bytearray()
        for start in range(0, len(klartext), 1024):
            encoder = Cipher(algorithms.AES(key[:16]), OFB((start // 1024 + 1).to_bytes(16, "little"))).encryptor()
            verschluesselt.extend(encoder.update(klartext[start:start + 1024]) + encoder.finalize())
        verschluesselt[16:24] = klartext[16:24]
        path.write_bytes(verschluesselt)
        return path

    def unbekannte_datei(self, profil, path, tabellen_offset=0x700):
        data = bytearray(path.read_bytes())
        arm_offset = struct.unpack_from(">IIIII", data, 28)[2]
        laenge = max(profil.zeichenindizes) * profil.eintrag_groesse + profil.zeiger_offset + 8
        start = arm_offset + profil.konstanten_offset
        tabelle = data[start:start + laenge]
        data[start:start + laenge] = bytes(laenge)
        data[arm_offset + tabellen_offset:arm_offset + tabellen_offset + laenge] = tabelle
        unknown = self.root / "unbekannt"
        unknown.write_bytes(data)
        return unknown

    def zweite_tabelle(self, path, profil, zeichenindex, ersatz):
        data = bytearray(path.read_bytes())
        arm_offset = struct.unpack_from(">IIIII", data, 28)[2]
        laenge = max(profil.zeichenindizes) * profil.eintrag_groesse + profil.zeiger_offset + 8
        data[arm_offset + 0xC00:arm_offset + 0xC00 + laenge] = data[arm_offset + 0x700:arm_offset + 0x700 + laenge]
        segment = arm_offset + 32 + 2 * 72
        vmaddr, _, fileoff, filesize = struct.unpack_from("<QQQQ", data, segment + 24)
        data.extend(bytes((profil.zeichen_marker, ord(ersatz))))
        struct.pack_into("<Q", data, segment + 48, filesize + 2)
        struct.pack_into(">I", data, 40, len(data) - arm_offset)
        struct.pack_into("<Q", data, arm_offset + 0xC00 + profil.eintrag_groesse * zeichenindex + profil.zeiger_offset,
                         vmaddr + filesize)
        path.write_bytes(data)

    def test_falscher_kandidat_neben_passendem_kandidaten_wird_verworfen(self):
        unknown = self.unbekannte_datei(self.alt, self.alt_datei)
        self.zweite_tabelle(unknown, self.alt, self.alt.zeichenindizes[0], "B")
        self.assertEqual(schluessel.schluessel_wiederherstellen(unknown, self.datenbank(self.alt_key)), self.alt_key)

    def test_mehrdeutige_32_byte_schluessel_mit_gleichem_aes_teil_werden_abgelehnt(self):
        unknown = self.unbekannte_datei(self.alt, self.alt_datei)
        self.zweite_tabelle(unknown, self.alt, self.alt.zeichenindizes[-2], "4")
        destination = self.root / "mehrdeutig.key"
        with self.assertRaisesRegex(ValueError, "Mehrere passende Schlüssel"):
            self.cli("--programmdatei", unknown, "--datenbank", self.datenbank(self.alt_key),
                     "--ausgabe", destination)
        self.assertFalse(destination.exists())

    def test_unbekanntes_40_byte_layout_benoetigt_keinen_festen_offset(self):
        data = bytearray(self.alt_datei.read_bytes())
        arm_offset = struct.unpack_from(">IIIII", data, 28)[2]
        zeiger = [
            struct.unpack_from("<Q", data, arm_offset + self.alt.konstanten_offset + index * 16)[0]
            for index in range(max(self.alt.zeichenindizes) + 1)
        ]
        for index, adresse in enumerate(zeiger):
            struct.pack_into("<Q", data, arm_offset + 0x700 + index * 40 + 8, adresse)
        unknown = self.root / "unbekannt-40"
        unknown.write_bytes(data)
        profil = replace(self.alt, eintrag_groesse=40, zeiger_offset=8)
        with patch.dict(schluessel.PROFILE, {"synthetisches-muster": profil}):
            self.assertEqual(schluessel.schluessel_wiederherstellen(unknown, self.datenbank(self.alt_key)), self.alt_key)


    def test_unbekannter_hash_mit_verschobener_tabelle_wird_lesend_geprueft(self):
        for profil, path, key in ((self.alt, self.alt_datei, self.alt_key),
                                  (self.neu, self.neu_datei, self.neu_key)):
            with self.subTest(version=profil.version):
                unknown = self.unbekannte_datei(profil, path)
                database = self.datenbank(key)
                vorher = database.read_bytes(), database.stat().st_mtime_ns
                destination = self.root / f"{path.name}.key"
                output = self.cli("--programmdatei", unknown, "--datenbank", database, "--ausgabe", destination)
                self.assertEqual(destination.read_bytes(), key)
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
                self.assertEqual((database.read_bytes(), database.stat().st_mtime_ns), vorher)
                self.assertFalse(Path(str(database) + "-wal").exists())
                self.assertFalse(Path(str(database) + "-journal").exists())
                self.assertNotIn(base64.b64encode(key).decode(), output)
                database.unlink()

    def test_unbekannte_datei_ohne_datenbank_scheitert(self):
        unknown = self.unbekannte_datei(self.alt, self.alt_datei)
        with self.assertRaisesRegex(ValueError, "--datenbank"):
            schluessel.schluessel_wiederherstellen(unknown)

    def test_falsche_datenbank_erzeugt_keine_ausgabedatei(self):
        unknown = self.unbekannte_datei(self.alt, self.alt_datei)
        database = self.datenbank(self.neu_key)
        destination = self.root / "kein-verzeichnis" / "datenbank.key"
        with self.assertRaisesRegex(ValueError, "Kein bekanntes Konstantenmuster"):
            self.cli("--programmdatei", unknown, "--datenbank", database, "--ausgabe", destination)
        self.assertFalse(destination.parent.exists())

    def test_bekanntes_profil_prueft_ausdruecklich_gewaehlte_datenbank(self):
        database = self.datenbank(self.neu_key)
        with self.assertRaisesRegex(ValueError, "passt nicht"):
            schluessel.schluessel_wiederherstellen(self.alt_datei, database)
        self.assertEqual(schluessel.schluessel_wiederherstellen(self.neu_datei, database), self.neu_key)

    def test_geaendertes_muster_und_nicht_dateigestuetzte_tabelle_scheitern(self):
        database = self.datenbank(self.alt_key)
        original = self.unbekannte_datei(self.alt, self.alt_datei).read_bytes()
        arm_offset = struct.unpack_from(">IIIII", original, 28)[2]
        for offset, wert in ((arm_offset + 0x700, 0),
                             (arm_offset + 32 + 72 + 48, 0x700)):
            with self.subTest(offset=offset):
                data = bytearray(original)
                struct.pack_into("<Q", data, offset, wert)
                path = self.root / "defekt"
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "Kein bekanntes Konstantenmuster"):
                    schluessel.schluessel_wiederherstellen(path, database)

    def test_laufender_datenbankstand_wird_abgelehnt(self):
        database = self.datenbank(self.alt_key)
        Path(str(database) + "-wal").write_bytes(b"synthetisch")
        unknown = self.unbekannte_datei(self.alt, self.alt_datei)
        with self.assertRaisesRegex(ValueError, "WAL/Journal"):
            schluessel.schluessel_wiederherstellen(unknown, database)

    def test_unbekanntes_duennes_arm64_macho_wird_erkannt(self):
        unknown = self.unbekannte_datei(self.alt, self.alt_datei)
        data = unknown.read_bytes()
        arm_offset = struct.unpack_from(">IIIII", data, 28)[2]
        unknown.write_bytes(data[arm_offset:])
        self.assertEqual(schluessel.schluessel_wiederherstellen(unknown, self.datenbank(self.alt_key)), self.alt_key)

    def test_defekte_unbekannte_programmdateien_melden_valueerror(self):
        database = self.datenbank(self.alt_key)
        for data in (b"", b"unvollstaendig", struct.pack(">II", 0xCAFEBABE, 500) + bytes(24)):
            with self.subTest(data=data):
                path = self.root / "defekt"
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    schluessel.schluessel_wiederherstellen(path, database)


    def test_beide_profile_waehlen_arm64_und_eigene_adressen_und_reihenfolge(self):
        self.assertEqual(schluessel.schluessel_wiederherstellen(self.alt_datei), self.alt_key)
        self.assertEqual(schluessel.schluessel_wiederherstellen(self.neu_datei), self.neu_key)

    def test_archivlayout_mit_40_byte_eintraegen_und_verschobener_tabelle(self):
        original = self.alt_datei.read_bytes()
        arm_offset = struct.unpack_from(">I", original, 36)[0]
        zeiger = [
            struct.unpack_from("<Q", original, arm_offset + self.alt.konstanten_offset
                               + index * self.alt.eintrag_groesse + self.alt.zeiger_offset)[0]
            for index in range(max(self.alt.zeichenindizes) + 1)
        ]
        for tabellen_offset in (0x400, 0x600):
            with self.subTest(tabellen_offset=tabellen_offset):
                data = bytearray(original)
                for index, adresse in enumerate(zeiger):
                    struct.pack_into("<Q", data, arm_offset + tabellen_offset + index * 40 + 8, adresse)
                path = self.root / f"archiv-{tabellen_offset}"
                path.write_bytes(data)
                profil = replace(self.alt, konstanten_offset=tabellen_offset,
                                 eintrag_groesse=40, zeiger_offset=8)
                digest = hashlib.sha256(data).hexdigest()
                with patch.dict(schluessel.PROFILE, {digest: profil}):
                    self.assertEqual(schluessel.schluessel_wiederherstellen(path), self.alt_key)

    def test_zeiger_in_pagezero_zerofill_oder_ueber_segmentende_scheitern(self):
        original = self.neu_datei.read_bytes()
        arm_offset = struct.unpack_from(">IIIII", original, 28)[2]
        segment = arm_offset + 32 + 2 * 72
        vmaddr, _, _, filesize = struct.unpack_from("<QQQQ", original, segment + 24)
        for pointer in (0x80, vmaddr + filesize, vmaddr + filesize - 1, 0xFFFFFFFFFFFFFFFF):
            with self.subTest(pointer=pointer):
                data = bytearray(original)
                location = arm_offset + self.neu.konstanten_offset + self.neu.zeiger_offset
                struct.pack_into("<Q", data, location, pointer)
                self.neu_datei.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                with patch.dict(schluessel.PROFILE, {digest: self.neu}):
                    with self.assertRaisesRegex(ValueError, "dateigestützter"):
                        schluessel.schluessel_wiederherstellen(self.neu_datei)

    def test_ungueltige_ladebefehle_werden_abgelehnt(self):
        original = self.neu_datei.read_bytes()
        arm_offset = struct.unpack_from(">IIIII", original, 28)[2]
        for offset, value in ((20, len(original)), (32 + 4, 0), (32 + 72 + 4, 64)):
            with self.subTest(offset=offset):
                data = bytearray(original)
                struct.pack_into("<I", data, arm_offset + offset, value)
                self.neu_datei.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                with patch.dict(schluessel.PROFILE, {digest: self.neu}):
                    with self.assertRaisesRegex(ValueError, "Ladebefehl"):
                        schluessel.schluessel_wiederherstellen(self.neu_datei)

    def test_hash_statt_dateiname_bestimmt_profil(self):
        renamed = self.root / "beliebiger-name"
        self.neu_datei.rename(renamed)
        self.assertEqual(schluessel.schluessel_wiederherstellen(renamed), self.neu_key)

    def test_neuer_tabelleneintrag_wird_ohne_programmpfad_verwendet(self):
        destination = self.root / "privat" / "neu.key"
        output = self.cli("--ausgabe", destination)
        self.assertEqual(destination.read_bytes(), self.neu_key)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertNotIn(repr(self.neu_key), output)

    def test_aeltere_version_am_standardpfad_wird_nach_hash_erkannt(self):
        self.neu_datei.write_bytes(self.alt_datei.read_bytes())
        destination = self.root / "alt.key"
        self.cli("--ausgabe", destination)
        self.assertEqual(destination.read_bytes(), self.alt_key)

    def test_expliziter_pfad_waehlt_aeltere_installation(self):
        destination = self.root / "explizit.key"
        self.cli("--programmdatei", self.alt_datei, "--ausgabe", destination)
        self.assertEqual(destination.read_bytes(), self.alt_key)

    def test_unbekannter_hash_erzeugt_keine_schluesseldatei(self):
        unknown = self.root / "unbekannt"
        unknown.write_bytes(b"Unbekannte synthetische Programmdatei")
        destination = self.root / "nicht-erstellen" / "datenbank.key"
        with self.assertRaisesRegex(ValueError, "Nicht unterstützte Programmdatei"):
            self.cli("--programmdatei", unknown, "--ausgabe", destination)
        self.assertFalse(destination.parent.exists())

    def test_fehlende_installation_meldet_cli_fehler(self):
        self.neu_datei.unlink()
        destination = self.root / "fehlend.key"
        output = io.StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as result:
            self.cli("--ausgabe", destination)
        self.assertEqual(result.exception.code, 2)
        self.assertIn("--programmdatei angeben", output.getvalue())
        self.assertFalse(destination.exists())

    def test_expliziter_pfad_funktioniert_ohne_standardinstallation(self):
        self.neu_datei.unlink()
        destination = self.root / "archiv.key"
        self.cli("--programmdatei", self.alt_datei, "--ausgabe", destination)
        self.assertEqual(destination.read_bytes(), self.alt_key)

    def test_profile_mit_falschem_marker_oder_schluessellaenge_scheitern(self):
        digest = hashlib.sha256(self.neu_datei.read_bytes()).hexdigest()
        profil = replace(self.neu, zeichen_marker=3)
        with patch.dict(schluessel.PROFILE, {digest: profil}), self.assertRaisesRegex(ValueError, "Aufbau"):
            schluessel.schluessel_wiederherstellen(self.neu_datei)
        for laenge in (31, 33):
            digest, profil, path = self.programmdatei(f"laenge-{laenge}", bytes(range(laenge)), True)
            with self.subTest(laenge=laenge), patch.dict(schluessel.PROFILE, {digest: profil}):
                with self.assertRaisesRegex(ValueError, "Länge"):
                    schluessel.schluessel_wiederherstellen(path)

    def test_vorhandene_schluessel_bleiben_geschuetzt(self):
        destination = self.root / "vorhanden.key"
        self.cli("--ausgabe", destination)
        identity = destination.stat().st_ino, destination.stat().st_mtime_ns
        self.cli("--ausgabe", destination)
        self.assertEqual((destination.stat().st_ino, destination.stat().st_mtime_ns), identity)
        destination.write_bytes(b"Anderer synthetischer Schluessel")
        with self.assertRaisesRegex(ValueError, "Überschreiben wird verweigert"):
            self.cli("--ausgabe", destination)
        self.assertEqual(destination.read_bytes(), b"Anderer synthetischer Schluessel")
