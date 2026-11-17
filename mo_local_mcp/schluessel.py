#!/usr/bin/env python3
"""Den beobachteten Standardschlüssel aus der installierten MonKey-Office-Version wiederherstellen.

Es wird kein Anwendungscode ausgeführt, keine Herstellerprogrammdatei kopiert und kein Schlüssel ausgegeben.
Der Hash der exakten Programmdatei sperrt die Wiederherstellung für andere Anwendungsversionen.
"""

from mo_local_mcp.kommandozeile import DeutscherArgumentParser
import base64
from dataclasses import dataclass
import hashlib
import mmap
from pathlib import Path
import os
import struct


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
    programmdatei: Path
    konstanten_offset: int
    eintrag_groesse: int
    zeiger_offset: int
    zeichen_marker: int
    zeichenindizes: tuple[int, ...]


PROFILE = {
    "5fa4249c6d7635546139f51bf5f3e7c20b9a230fcc0fbf27e7d8c8d0e90ba9b5": Schluesselprofil(
        version="2026 23.2.4",
        programmdatei=Path("/Applications/MonKey Office 2026.app/Contents/MacOS/MonKey Office 2026"),
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


def schluessel_wiederherstellen(programmdatei):
    """Wählt das Hashprofil, liest die ARM64-Zeichenkonstanten und dekodiert 32 Schlüsselbytes."""
    with Path(programmdatei).open("rb") as quelle:
        profil = PROFILE.get(hashlib.file_digest(quelle, "sha256").hexdigest())
        if profil is None:
            versionen = ", ".join(eintrag.version for eintrag in PROFILE.values())
            raise ValueError(f"Nicht unterstützte Programmdatei. Erfasste Versionen: {versionen}")
        with mmap.mmap(quelle.fileno(), 0, access=mmap.ACCESS_READ) as daten:
            _, anzahl = FAT_HEADER.unpack_from(daten)
            architekturen = [
                FAT_ARCH.unpack_from(daten, FAT_HEADER.size + FAT_ARCH.size * index)
                for index in range(anzahl)
            ]
            arm_offset, arm_groesse = next((architektur[2], architektur[3]) for architektur in architekturen if architektur[0] == CPU_TYPE_ARM64)
            segmente = _segmente(daten, arm_offset, arm_groesse)
            zeichen = []
            for index in range(max(profil.zeichenindizes) + 1):
                position = arm_offset + profil.konstanten_offset + profil.eintrag_groesse * index + profil.zeiger_offset
                zeiger = ZEIGER_64.unpack_from(daten, position)[0]
                position = arm_offset + _dateiversatz(zeiger, segmente, 2)
                if daten[position] != profil.zeichen_marker:
                    raise ValueError("Unerwarteter Aufbau der kompilierten Zeichenkette")
                zeichen.append(bytes(daten[position + 1:position + 2]))
            base64_zeichen = b"".join(zeichen[index] for index in profil.zeichenindizes)
            schluessel = base64.b64decode(base64_zeichen, validate=True)
            if len(schluessel) != SCHLUESSELLAENGE:
                raise ValueError("Unerwartete Länge des wiederhergestellten Schlüssels")
            return schluessel


def main():
    """Wählt die Programmdatei und speichert den Schlüssel mit Dateirechten 0600, ohne vorhandene Dateien zu überschreiben."""
    parser = DeutscherArgumentParser(description=__doc__)
    parser.add_argument("--programmdatei", type=Path, help="Pfad zur Programmdatei; ohne Angabe die neueste erfasste Installation verwenden")
    parser.add_argument("--ausgabe", type=Path, default=Path.home() / "Library/Application Support/mo-local-mcp/database.key", help="Zielpfad der privaten Schlüsseldatei")
    argumente = parser.parse_args()
    if argumente.programmdatei is None:
        argumente.programmdatei = next(
            (profil.programmdatei for profil in reversed(PROFILE.values()) if profil.programmdatei.is_file()),
            None,
        )
        if argumente.programmdatei is None:
            parser.error("Keine erfasste Installation gefunden; --programmdatei angeben")
    schluessel = schluessel_wiederherstellen(argumente.programmdatei)
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
