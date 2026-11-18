# Einrichtung und Betrieb

[Übersicht](../README.md)

## Voraussetzungen

Du benötigst macOS, Python ab 3.13 und [uv](https://docs.astral.sh/uv/).
Verwende einen geschlossenen, ruhenden und konsistent abgeschlossenen Datenbankstand.
Eine aktive MonKey-Datei ist nicht geeignet.
Eine Kopie der laufend veränderten Hauptdatei allein reicht nicht.

Es gibt keine Live-Verbindung und keine automatische Aktualisierung.
Produktionsdatenquelle und Aktualisierungsverfahren legst du selbst fest.
Die `beispiel.sdb` im Projektordner dient nur der Entwicklung.

## Installation

Für die Installation ohne Checkout gilt der [Schnellstart](../README.md#schnellstart).
Die folgenden Beispiele mit `uv run` beziehen sich auf einen Checkout.
Bei einer Installation als uv-Tool rufst du die Kommandos direkt ohne `uv run` auf.

### Aus dem Quellcode

Führe im Projektordner aus:

```sh
uv sync --frozen
uv run mo-schluessel-wiederherstellen
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db
```

### Versioniertes Paket

Wähle eine vorhandene Version unter [Releases](https://github.com/realholgi/mo-local-mcp/releases).
Ein erfolgreiches Release enthält ein Wheel, ein Quellpaket und `SHA256SUMS`.
Es gibt keine automatische Veröffentlichung auf PyPI.
Lade das Wheel und `SHA256SUMS` aus demselben Release in einen eigenen Ordner.

```sh
shasum -a 256 mo_local_mcp-1.0.0-py3-none-any.whl
cat SHA256SUMS
uv tool install --python 3.13 ./mo_local_mcp-1.0.0-py3-none-any.whl
mo-local-mcp --hilfe
```

Vergleiche die Prüfsumme vor der Installation mit dem Eintrag in `SHA256SUMS`.
`uv tool install` richtet eine eigene Umgebung mit beiden Kommandos ein.
Falls die Kommandos nicht gefunden werden, führe `uv tool update-shell` aus.
Öffne danach eine neue Shell.
Den Ordner für absolute Kommandopfade zeigt `uv tool dir --bin`.
Datenbank und Schlüsseldatei bleiben außerhalb dieser Umgebung.

### Aktualisieren und zurücksetzen

1. Beende den MCP-Prozess.
2. Lade das Wheel und die Prüfsummen der gewünschten Version.
3. Prüfe die Prüfsumme.
4. Installiere das Wheel mit `uv tool install --force --python 3.13 ./DATEI.whl`.
5. Starte den MCP-Client neu.

Für eine Rückkehr installierst du mit demselben Befehl das Wheel der vorherigen Version.

## Schlüssel wiederherstellen

`mo-schluessel-wiederherstellen` ist im Wheel enthalten.
Es liest die Programmdatei, startet aber keinen Anwendungscode.
Schlüsselwerte erscheinen nicht in der Ausgabe. Herstellerprogrammdateien werden nicht verteilt.

Diese exakten Programmversionen sind über ihren Datei-Hash erfasst:

| App | Programmversionen |
| --- | --- |
| MonKey Office 2025 | 22.4.0 |
| MonKey Office 2026 | 23.0.2, 23.1.0, 23.2.4 |

Der SHA-256 der ausführbaren Datei bestimmt das Profil, nicht der App-Name.
Für unbekannte Dateien sucht das Werkzeug den bekannten Konstantenaufbau ohne feste Tabellenposition.
Dazu ist `--datenbank` mit einem ruhenden verschlüsselten Datenbankstand erforderlich.
Nur ein eindeutiger Schlüssel, mit dem sich das Datenbankschema lesen lässt, wird gespeichert.
Die Datenbank bleibt schreibgeschützt. Ein WAL oder Journal mit Inhalt wird abgelehnt.
Ohne `--programmdatei` gilt dieser Standardpfad:

`/Applications/MonKey Office 2026.app/Contents/MacOS/MonKey Office 2026`

Auch eine unterstützte ältere Version an diesem Pfad wird über ihren Hash erkannt.
Der Schlüssel wird standardmäßig hier mit Dateirechten `0600` gespeichert:

`~/Library/Application Support/mo-local-mcp/database.key`

Passender vorhandener Inhalt wird wiederverwendet. Abweichender Inhalt wird nicht überschrieben.
Andere Programm- und Schlüsselpfade wählst du ausdrücklich:

```sh
uv run mo-schluessel-wiederherstellen \
  --programmdatei "/Applications/MonKey Office 2026.app/Contents/MacOS/MonKey Office 2026" \
  --ausgabe /privater/pfad/datenbank.key
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db \
  --schluesseldatei /privater/pfad/datenbank.key
```

Bei einer unbekannten Programmversion ergänze die Datenbank zur Schlüsselprüfung:

```sh
uv run mo-schluessel-wiederherstellen \
  --programmdatei "/pfad/zur/MonKey Office.app/Contents/MacOS/MonKey Office" \
  --datenbank /absoluter/pfad/entwicklungsstand.db \
  --ausgabe /privater/pfad/datenbank.key
```

`--datenbank` prüft auch Schlüssel aus bekannten Hashprofilen, wenn du die Option angibst.
Geänderte Zeichenreihenfolgen, Tabellenformate oder Verschlüsselungsverfahren erfordern weiterhin eine Anpassung am Leser.

Archive an anderen Orten benötigen den Pfad zur ausführbaren Datei:

```sh
uv run mo-schluessel-wiederherstellen \
  --programmdatei "/pfad/zum/archiv/MonKey Office 2026 23.0.2.app/Contents/MacOS/MonKey Office 2026"
```

Für 23.1.0 gilt derselbe Aufruf mit dem passenden App-Pfad.
Bei MonKey Office 2025 lautet der Pfad innerhalb der App `Contents/MacOS/MonKey Office 2025`.
Die vier erfassten Programmdateien liefern denselben 32-Byte-Standardschlüssel.
Die Archivversionen wurden über das CLI geprüft, ohne die Apps zu starten.
Dabei wurden keine Schlüsselwerte in Dokumentation oder Testdaten gespeichert.
Technische Details stehen unter [Schlüsselprofile](entwicklung.md#schlüsselprofile).

## OMP einrichten

Lege bei Bedarf eine lokale `.omp/mcp.json` an.
OMP startet `mo-local-mcp` aus der installierten Umgebung.
Passe die Platzhalterpfade an:

```json
{
  "mcpServers": {
    "mo-local-mcp": {
      "command": "/absoluter/pfad/.venv/bin/mo-local-mcp",
      "args": ["--datenbank", "/absoluter/pfad/entwicklungsstand.db"]
    }
  }
}
```

Nach einem frischen Checkout musst du diese Datei selbst anlegen.
Git und Veröffentlichungspakete schließen die rechnergebundene Konfiguration aus.
Trage dort keine Schlüssel oder Zugangsdaten ein.

Lade die Konfiguration nach Änderungen mit `/mcp reload` neu.
Prüfe sie bei Bedarf mit `/mcp test mo-local-mcp`.
Beide Befehle gehören zu OMP.

## Leserechte begrenzen

Die Startoptionen gelten für genau diesen stdio-MCP-Prozess.
Sie ändern keine gespeicherten Datenbankrechte.
Ohne zusätzliche Optionen sind die Fachwerkzeuge verfügbar. Freies SQL ist gesperrt.

```sh
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db \
  --firma-id 101 --firma-id 202
```

| Option | Wirkung |
| --- | --- |
| `--firma-id ID` | Gibt nur diese Firma frei. Die Option ist wiederholbar. Firmenlisten filtern vor der Seiteneinteilung. Alle Fachaufrufe prüfen die Freigabe. Freies SQL bleibt gesperrt. |
| `--mit-sql` | Bietet `sql_abfragen` an, wenn keine Firmen- oder Stammdatenbeschränkung gilt. |
| `--ohne-sensible-stammdaten` | Bietet nur Metadaten und definierte Auswertungen an. Sperrt Firmendetails, Adressen, Detailbelege, Personenkontendetails, Suche, Anhänge und freies SQL. Firmenlisten enthalten nur lokale IDs. |

Im eingeschränkten Stammdatenmodus bleiben diese Bereiche verfügbar:
Geschäftsjahre, Datenstand, Datenqualität, Kostenstellen, Monatsberichte, Summen-/Saldenliste und Bilanz/GuV.
`berichtsnachweis_anzeigen` und `kontenabstimmung_pruefen` sind in diesem Modus nicht verfügbar.
Konten-, Gliederungs- und Kostenstellenbezeichnungen werden nicht anonymisiert.
Der Modus ist deshalb keine allgemeine Anonymisierung von Buchhaltungsdaten.
Die wirksamen Rechte stehen in `datenbankinformationen.zugriff` und `monkey://zugriff`.

## Schreibschutz und Abfragegrenzen

Der Server liest die angegebene Datei direkt. Er kopiert oder aktualisiert sie nicht.

- Nichtleere `-wal`- oder `-journal`-Dateien werden abgelehnt, nicht dekodiert oder wiederhergestellt.
- Vor und nach jeder Abfrage prüft der Server Gerätekennung, Inode, Größe sowie Änderungs- und Statuszeit.
  Bei einer Änderung benötigst du einen neuen konsistenten Datenstand und einen Serverneustart.
  Das Verfahren garantiert keine atomare Sicht auf eine Live-Datei.
- SQLite verwendet `immutable=1` und `query_only=ON`.
  Die VFS lehnt Schreiben und Kürzen ab.
  Die Autorisierung sperrt Änderungen, weitere Datenbanken, Transaktionen, Erweiterungen und externe Dateifunktionen.
- SQL erlaubt eine SELECT-/WITH-Anweisung und nur lesende Schemaeinsicht.
- Eine Abfrage liefert höchstens 500 Zeilen und ungefähr eine Million Ergebniszeichen.
  Weitere Grenzen sind eine Million Bytes je SQLite-Wert und 100.000 SQL-Zeichen.
- Die SQLite-Ausführung ist auf fünf Sekunden begrenzt.
  Das ist keine harte Grenze für Gesamtlaufzeit oder Dateisystemzugriffe.
  Temporäre SQLite-Daten bleiben im Arbeitsspeicher.

Schlüssel und entschlüsselte Seiten liegen im Prozessspeicher.
Auslagerung und Absturzabbilder kontrolliert das Betriebssystem, nicht der Server.
MCP-Hinweise allein schützen diese Daten nicht.
Verwende für Buchhaltungsdaten nur vertrauenswürdige MCP-Clients und Modellanbieter.
Versioniere keine Datenbanken, Schlüssel oder privaten Abfrageergebnisse.
Die [Ausschlussregeln](entwicklung.md#lokale-dateien) helfen beim Schutz lokaler Dateien.
