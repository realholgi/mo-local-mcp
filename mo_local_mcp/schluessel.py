#!/usr/bin/env python3
"""Den beobachteten Standardschlüssel aus der installierten MonKey-Office-Version wiederherstellen.

Es wird kein Anwendungscode ausgeführt, keine Herstellerprogrammdatei kopiert und kein Schlüssel ausgegeben.
Unbekannte Programmdateien erfordern einen bekannten Konstantenaufbau und eine passende Datenbank.
"""

from mo_local_mcp.kommandozeile import DeutscherArgumentParser
import base64
from dataclasses import dataclass
import hashlib
import mmap
from pathlib import Path
import os
import struct
import tempfile

import apsw

from mo_local_mcp.database import OfficeDatabase


STANDARD_PROGRAMMDATEI = Path("/Applications/MonKey Office 2026.app/Contents/MacOS/MonKey Office 2026")
CPU_TYPE_ARM64 = 0x100000C
SCHLUESSELLAENGE = 32
MH_MAGIC_64 = 0xFEEDFACF
LC_SEGMENT_64 = 0x19

FAT_HEADER = struct.Struct(">II")
FAT_ARCH = struct.Struct(">IIIII")
MACH_HEADER_64 = struct.Struct("<IiiIIIII")
LADEBEFEHL_HEADER = struct.Struct("<II")
SEGMENT_64 = struct.Struct("<II16sQQQQiiII")
ZEIGER_64 = struct.Struct("<Q")


@dataclass(frozen=True)
class Schluesselprofil:
    version: str
    konstanten_offset: int
    eintrag_groesse: int
    zeiger_offset: int
    zeichen_marker: int
    zeichenindizes: tuple[int, ...]


PROFILE = {
    "fdb7e8328ea808ab40e5dde0e8d77e7efc9098d0157bdd96f530709e2f76ae2e": Schluesselprofil(
        version="2025 22.4.0",
        konstanten_offset=0x88DC810,
        eintrag_groesse=40,
        zeiger_offset=8,
        zeichen_marker=1,
        zeichenindizes=(17, 8, 1, 25, 14, 12, 3, 15, 0, 2, 3, 27, 13, 8, 6,
                       10, 4, 21, 12, 20, 4, 18, 17, 7, 26, 11, 16, 21, 18,
                       19, 28, 5, 16, 24, 1, 15, 17, 12, 23, 22, 5, 11, 16, 9),
    ),
    "6a77b42e15182aa936672eaa575b3b19cb42f28ddf1089d879ad89dc64311175": Schluesselprofil(
        version="2026 23.0.2",
        konstanten_offset=0x8A105B0,
        eintrag_groesse=40,
        zeiger_offset=8,
        zeichen_marker=1,
        zeichenindizes=(17, 8, 1, 25, 14, 12, 3, 15, 0, 2, 3, 27, 13, 8, 6,
                       10, 4, 21, 12, 20, 4, 18, 17, 7, 26, 11, 16, 21, 18,
                       19, 28, 5, 16, 24, 1, 15, 17, 12, 23, 22, 5, 11, 16, 9),
    ),
    "685a6a61b4a948538e53aac1a02beb7a39ba9dbd1afef7a6384fc41ebc877b02": Schluesselprofil(
        version="2026 23.1.0",
        konstanten_offset=0x8AD1C38,
        eintrag_groesse=40,
        zeiger_offset=8,
        zeichen_marker=1,
        zeichenindizes=(17, 8, 1, 25, 14, 12, 3, 15, 0, 2, 3, 27, 13, 8, 6,
                       10, 4, 21, 12, 20, 4, 18, 17, 7, 26, 11, 16, 21, 18,
                       19, 28, 5, 16, 24, 1, 15, 17, 12, 23, 22, 5, 11, 16, 9),
    ),
    "5fa4249c6d7635546139f51bf5f3e7c20b9a230fcc0fbf27e7d8c8d0e90ba9b5": Schluesselprofil(
        version="2026 23.2.4",
        konstanten_offset=0x8F957C0,
        eintrag_groesse=40,
        zeiger_offset=8,
        zeichen_marker=1,
        zeichenindizes=(17, 8, 1, 25, 14, 12, 3, 15, 0, 2, 3, 27, 13, 8, 6,
                       10, 4, 21, 12, 20, 4, 18, 17, 7, 26, 11, 16, 21, 18,
                       19, 28, 5, 16, 24, 1, 15, 17, 12, 23, 22, 5, 11, 16, 9),
    ),
}


def _segmente(daten, arm_offset, arm_groesse):
    """Liest die virtuellen Adressen und Dateibereiche der ARM64-Segmente."""
    if arm_groesse < MACH_HEADER_64.size or arm_offset + arm_groesse > len(daten):
        raise ValueError("Unvollständiger ARM64-Teil")
    magic, _, _, _, anzahl, groesse, _, _ = MACH_HEADER_64.unpack_from(daten, arm_offset)
    if magic != MH_MAGIC_64:
        raise ValueError("Ein 64-Bit-Little-Endian-Mach-O wird erwartet")
    position = arm_offset + MACH_HEADER_64.size
    ende = position + groesse
    if ende > arm_offset + arm_groesse or anzahl * LADEBEFEHL_HEADER.size > groesse:
        raise ValueError("Ungültiger Bereich der Mach-O-Ladebefehle")
    segmente = []
    for _ in range(anzahl):
        if position + LADEBEFEHL_HEADER.size > ende:
            raise ValueError("Unvollständiger Mach-O-Ladebefehl")
        befehl, laenge = LADEBEFEHL_HEADER.unpack_from(daten, position)
        if laenge < LADEBEFEHL_HEADER.size or position + laenge > ende:
            raise ValueError("Ungültige Länge eines Mach-O-Ladebefehls")
        if befehl == LC_SEGMENT_64:
            if laenge < SEGMENT_64.size:
                raise ValueError("Unvollständiger LC_SEGMENT_64-Ladebefehl")
            _, _, _, vmaddr, vmsize, fileoff, filesize, _, _, _, _ = SEGMENT_64.unpack_from(daten, position)
            if filesize > vmsize or fileoff + filesize > arm_groesse:
                raise ValueError("Ungültiger Dateibereich eines Mach-O-Segments")
            segmente.append((vmaddr, fileoff, filesize))
        position += laenge
    if position != ende:
        raise ValueError("Ungültige Gesamtlänge der Mach-O-Ladebefehle")
    return segmente


def _dateiversatz(zeiger, segmente, laenge):
    """Berechnet den Dateiversatz im ARM64-Teil für einen vollständig dateigestützten Bereich."""
    for vmaddr, fileoff, filesize in segmente:
        if vmaddr <= zeiger and zeiger + laenge <= vmaddr + filesize:
            return fileoff + zeiger - vmaddr
    raise ValueError("Zeiger liegt außerhalb dateigestützter Mach-O-Segmente")


def _arm64_bereich(daten):
    if len(daten) < MACH_HEADER_64.size:
        raise ValueError("Unvollständige Programmdatei")
    if daten[:4] == struct.pack("<I", MH_MAGIC_64):
        if MACH_HEADER_64.unpack_from(daten)[1] != CPU_TYPE_ARM64:
            raise ValueError("Kein ARM64-Teil vorhanden")
        return 0, len(daten)
    magic, anzahl = FAT_HEADER.unpack_from(daten)
    if magic != 0xCAFEBABE or FAT_HEADER.size + anzahl * FAT_ARCH.size > len(daten):
        raise ValueError("Ungültige Universal-Mach-O-Datei")
    for index in range(anzahl):
        cpu, _, offset, groesse, _ = FAT_ARCH.unpack_from(daten, FAT_HEADER.size + index * FAT_ARCH.size)
        if cpu == CPU_TYPE_ARM64:
            return offset, groesse
    raise ValueError("Kein ARM64-Teil vorhanden")


def _profil_lesen(daten, arm_offset, segmente, profil, tabellen_offset):
    laenge = max(profil.zeichenindizes) * profil.eintrag_groesse + profil.zeiger_offset + ZEIGER_64.size
    if not any(fileoff <= tabellen_offset and tabellen_offset + laenge <= fileoff + filesize
               for _, fileoff, filesize in segmente):
        raise ValueError("Konstantentabelle liegt außerhalb dateigestützter Mach-O-Segmente")
    zeichen = bytearray()
    for index in range(max(profil.zeichenindizes) + 1):
        position = arm_offset + tabellen_offset + profil.eintrag_groesse * index + profil.zeiger_offset
        zeiger = ZEIGER_64.unpack_from(daten, position)[0]
        position = arm_offset + _dateiversatz(zeiger, segmente, 2)
        if daten[position] != profil.zeichen_marker:
            raise ValueError("Unerwarteter Aufbau der kompilierten Zeichenkette")
        zeichen.append(daten[position + 1])
    kodiert = bytes(zeichen[index] for index in profil.zeichenindizes)
    schluessel = base64.b64decode(kodiert, validate=True)
    if len(schluessel) != SCHLUESSELLAENGE or base64.b64encode(schluessel) != kodiert:
        raise ValueError("Unerwartete Länge oder nicht kanonische Base64-Kodierung des Schlüssels")
    return schluessel


def _kandidaten(daten, arm_offset, segmente):
    """Findet bekannte Tabellenmuster über den Zeiger auf das Base64-Endzeichen."""
    muster = {
        (profil.eintrag_groesse, profil.zeiger_offset, profil.zeichen_marker, profil.zeichenindizes): profil
        for profil in PROFILE.values()
    }
    gefunden = set()
    for profil in muster.values():
        # 32 Schlüsselbytes ergeben 44 Base64-Zeichen mit genau einem abschließenden '='.
        if len(profil.zeichenindizes) != 44:
            continue
        zeiger = set()
        for vmaddr, fileoff, filesize in segmente:
            position = arm_offset + fileoff
            ende = position + filesize
            while (position := daten.find(bytes((profil.zeichen_marker, ord("="))), position, ende)) != -1:
                zeiger.add(vmaddr + position - arm_offset - fileoff)
                position += 2
        if not zeiger:
            continue
        positionen = []
        with memoryview(daten) as ansicht:
            for _, fileoff, filesize in segmente:
                # Alle acht Ausrichtungen erhalten auch ungerade Tabellenpositionen.
                for ausrichtung in range(min(8, filesize)):
                    start = arm_offset + fileoff + ausrichtung
                    ende = start + (filesize - ausrichtung) // 8 * 8
                    with ansicht[start:ende] as bereich:
                        positionen.extend(
                            start + index * 8 - arm_offset
                            for index, (wert,) in enumerate(ZEIGER_64.iter_unpack(bereich))
                            if wert in zeiger
                        )
        for position in positionen:
            tabellen_offset = (position - profil.zeiger_offset
                               - profil.zeichenindizes[-1] * profil.eintrag_groesse)
            try:
                kandidat = _profil_lesen(daten, arm_offset, segmente, profil, tabellen_offset)
            except ValueError:
                continue
            if kandidat not in gefunden:
                gefunden.add(kandidat)
                yield kandidat


def _datenbank_pruefen(datenbank, schluessel):
    """Prüft das Schema mit dem vorhandenen Nur-Lese-Zugriff und einer kurzlebigen privaten Schlüsseldatei."""
    with tempfile.TemporaryDirectory(prefix="mo-schluessel-") as verzeichnis:
        pfad = Path(verzeichnis) / "database.key"
        with open(pfad, "xb", opener=lambda name, flags: os.open(name, flags, 0o600)) as datei:
            datei.write(schluessel)
        try:
            quelle = OfficeDatabase(datenbank, pfad)
        except (apsw.NotADBError, apsw.CorruptError):
            return False
        quelle.close()
        return True


def schluessel_wiederherstellen(programmdatei, datenbank=None):
    """Liest bekannte Hashprofile oder sucht bekannte Muster mit anschließender Datenbankprüfung."""
    with Path(programmdatei).open("rb") as quelle:
        profil = PROFILE.get(hashlib.file_digest(quelle, "sha256").hexdigest())
        if profil is None and datenbank is None:
            raise ValueError("Nicht unterstützte Programmdatei. Für die Mustersuche --datenbank angeben")
        if os.fstat(quelle.fileno()).st_size == 0:
            raise ValueError("Leere Programmdatei")
        with mmap.mmap(quelle.fileno(), 0, access=mmap.ACCESS_READ) as daten:
            arm_offset, arm_groesse = _arm64_bereich(daten)
            segmente = _segmente(daten, arm_offset, arm_groesse)
            if profil is not None:
                schluessel = _profil_lesen(daten, arm_offset, segmente, profil, profil.konstanten_offset)
                if datenbank is not None and not _datenbank_pruefen(datenbank, schluessel):
                    raise ValueError("Der wiederhergestellte Schlüssel passt nicht zur Datenbank")
                return schluessel
            passend = None
            for kandidat in _kandidaten(daten, arm_offset, segmente):
                if _datenbank_pruefen(datenbank, kandidat):
                    if passend is not None:
                        raise ValueError("Mehrere passende Schlüssel gefunden; Programmdatei ist nicht eindeutig")
                    passend = kandidat
            if passend is None:
                raise ValueError("Kein bekanntes Konstantenmuster mit passendem Datenbankschlüssel gefunden")
            return passend


def main():
    """Wählt die Programmdatei und speichert den Schlüssel mit Dateirechten 0600, ohne vorhandene Dateien zu überschreiben."""
    parser = DeutscherArgumentParser(description=__doc__)
    parser.add_argument("--programmdatei", type=Path, default=STANDARD_PROGRAMMDATEI,
                        help=f"Pfad zur Programmdatei; Standard: {STANDARD_PROGRAMMDATEI}")
    parser.add_argument("--ausgabe", type=Path, default=Path.home() / "Library/Application Support/mo-local-mcp/database.key", help="Zielpfad der privaten Schlüsseldatei")
    parser.add_argument("--datenbank", type=Path,
                        help="Ruhender verschlüsselter Datenbankstand zur lesenden Schlüsselprüfung; bei unbekannter Programmdatei erforderlich")
    argumente = parser.parse_args()
    if not argumente.programmdatei.is_file():
        parser.error(f"Programmdatei nicht gefunden: {argumente.programmdatei}; --programmdatei angeben")
    schluessel = schluessel_wiederherstellen(argumente.programmdatei, argumente.datenbank)
    argumente.ausgabe.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(argumente.ausgabe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if argumente.ausgabe.read_bytes() != schluessel:
            raise ValueError("Ausgabedatei enthält bereits andere Daten; Überschreiben wird verweigert") from None
        print(f"Passender Schlüssel bereits unter {argumente.ausgabe} vorhanden")
        return
    with os.fdopen(fd, "wb") as ausgabe:
        ausgabe.write(schluessel)
    print(f"Privater Schlüssel unter {argumente.ausgabe} gespeichert")


if __name__ == "__main__":
    main()
