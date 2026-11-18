# Entwicklung und technische Grundlagen

[Übersicht](../README.md)

## Schlüsselprofile

Die Profiltabelle `PROFILE` liegt in [`mo_local_mcp/schluessel.py`](../mo_local_mcp/schluessel.py).
Sie enthält Datei-Hashes, Versionsangaben und Ableitungsdaten, keine Programmpfade.
Den Standardpfad und andere Ablageorte beschreibt die [Einrichtung](einrichtung.md#schlüssel-wiederherstellen).

Für eine neue Version mit gleichem Ableitungsverfahren ergänze einen Eintrag in `PROFILE`.
Behalte die vorhandenen Profile bei und sortiere die Einträge von alt nach neu.

| Feld | Bedeutung |
| --- | --- |
| Tabellenschlüssel | SHA-256 der genauen Programmdatei |
| `version` | Versionsbezeichnung für Fehlermeldungen |
| `konstanten_offset` | Beginn der Konstantentabelle relativ zum Mach-O-Teil |
| `eintrag_groesse` | Abstand zwischen Tabelleneinträgen in Bytes |
| `zeiger_offset` | Position des Zeichenkettenzeigers innerhalb eines Eintrags |
| `zeichen_marker` | Erwartetes Byte vor dem Zeichen |
| `zeichenindizes` | Indizes der Zeichenkonstanten in Base64-Ausgabereihenfolge |

Der Leser verwendet den ARM64-Teil (`CPU_TYPE_ARM64 = 0x100000C`) der Universal-Mach-O-Datei.
Er liest 64-Bit-Little-Endian-Zeiger und einzelne Base64-Zeichen.
`vmaddr`, `fileoff` und `filesize` ordnen Zeichenkettenzeiger dem dateigestützten Segment zu.
Zeiger auf `__PAGEZERO`, Zero-Fill-Bereiche oder über das Segmentende hinaus werden abgelehnt.
Ein anderes Datei- oder Ableitungsformat erfordert eine Änderung am Leser.

### Offsetfreie Mustersuche

Bei unbekanntem Datei-Hash sucht der Leser die Tabellenmuster aus `PROFILE`.
Dabei verwendet er Eintragsgröße, Zeigerposition, Zeichenmarker und Zeichenindizes.
Die feste Tabellenposition und Versionsbezeichnung werden nicht benötigt.
Die Suche unterstützt Universal-Mach-O-Dateien und einzelne ARM64-Mach-O-Dateien.

32 Schlüsselbytes ergeben 44 Base64-Zeichen mit einem abschließenden `=`.
Der Leser sucht dateigestützte Zeichenkonstanten für dieses Endzeichen.
Über ihre Zeiger und den bekannten Zeichenindex bestimmt er mögliche Tabellenanfänge.
Die Zeigersuche liest 64-Bit-Werte ohne Kopie über alle acht Byte-Ausrichtungen.
Ein Mengenvergleich ersetzt den langsamen regulären Ausdruck mit vielen Zeigeralternativen.
Er prüft alle Tabellenzeiger, Zeichenmarker, die Schlüssellänge und die kanonische Base64-Kodierung.

Für diese Suche ist `--datenbank` erforderlich.
Jeden unterschiedlichen Kandidaten prüft `OfficeDatabase` durch lesenden Zugriff auf `sqlite_schema`.
Dazu wird kurzzeitig eine Schlüsseldatei mit Rechten `0600` in einem privaten temporären Verzeichnis angelegt.
Das Verzeichnis wird auch bei Fehlern entfernt.
Erst nach genau einem passenden Kandidaten speichert das CLI die Ausgabedatei.
Mehrere passende 32-Byte-Schlüssel werden abgelehnt, auch wenn ihre ersten 16 Bytes übereinstimmen.

Die Suche erkennt bekannte Konstantenaufbauten an neuen Positionen, keine beliebigen Ableitungsroutinen.
Neue Zeichenreihenfolgen oder Tabellenformate benötigen weiterhin ein passendes Muster.
Die Datenbankprüfung bestätigt das unterstützte Verschlüsselungsprofil, nicht die Unversehrtheit aller Geschäftsdaten.

Die Mustersuche wurde mit MonKey Office 2024 21.4.3 (Build 21.4.3.3.191) geprüft.
Ohne neues Hashprofil fand und bestätigte das CLI den Schlüssel in rund zehn Sekunden.
Die App wurde nicht gestartet. Größe und Änderungszeiten der Entwicklungsdatenbank blieben unverändert.
Die temporäre Schlüsseldatei hatte Rechte `0600` und wurde nach der Prüfung entfernt.

## Verschlüsselungsprofil

Die statische Symbol- und ARM64-Analyse untersuchte unter anderem Programmversion 23.2.4:

`5fa4249c6d7635546139f51bf5f3e7c20b9a230fcc0fbf27e7d8c8d0e90ba9b5`

Dieser SHA-256 bezeichnet die Programmdatei. Die Analyse liefert keinen ursprünglichen Quelltext.
`mOpenDatabase.ScramblingKey` baut aus 29 Konstanten über 44 Arraypositionen eine permutierte Base64-Zeichenkette.
Daraus entstehen 32 Schlüsselbytes. Der Datenbankleser verwendet die ersten 16 Bytes für SEE AES-128.
Der Projektquelltext enthält keinen wörtlichen Schlüssel.

Unterstützt ist das beobachtete SEE-AES-128-OFB-Profil ohne reservierte Nonce-Bytes:

- Der IV entsteht aus der 1-basierten Seitennummer als 16 Byte Little-Endian.
- Die Klartext-Headerbytes 16–23 bleiben erhalten.
- Andere Verfahren, Nonce-Profile, individuelle Schlüssel und künftige Programmversionen sind nicht zugesichert.
- OFB ohne Authentifizierung erkennt nicht jede bösartige Änderung.
  Die Standardschlüsselableitung ist keine Sicherheitsgarantie.

Quellen:

- [SQLite SEE](https://www.sqlite.org/see/doc/trunk/www/readme.wiki)
- [Xojo EncryptionKey](https://docs.xojo.com/api/databases/sqlitedatabase.html#sqlitedatabase-encryptionkey)
- [Herstellerhinweis](https://prosaldo.zendesk.com/hc/de/community/posts/207908146--sdb-Datei-als-sqlite-Datenbank-%C3%B6ffnen)

## Fachschema und Quellen

27 Tabellen sind fachlich beschrieben:

`FIRMA`, `ADRESSE`, `AUFTRAG`, `AUFTRAGSPOSITION`, `BUCHUNG`, `JOURNAL`, `POSTEN`,
`POSTENPOSITION`, `WAEHRUNG`, `KONTO`, `STEUERSATZ`, `WIRTSCHAFTSJAHR`,
`KONTOSTRUKTUR`, `STRUKTURPOSITION`, `ZAHLUNG`, `ZAHLUNGSPOSITION`, `KOSTENSTELLE`,
`ZAHLUNGSBEDINGUNG`, `ELSTERMELDUNG`, `ELSTERMELDUNG_NT`, `STEUERERKLAERUNG`,
`ANLAGE`, `ANLAGENPOSITION`, `BESTELLUNG`, `BESTELLPOSITION`, `ARTIKEL`, `PROJEKT`.

Andere Tabellen bleiben technisch lesbar.
Die [MCP-Referenz](referenz.md) beschreibt den Zugriff auf das Fachschema.

Die Begriffe stammen aus der JSON-API-Hilfe **23.2.0 / 07.07.26** im
[Connect-Download](https://www.monkey-office.de/download/current/mac/MonKey_Office_Connect.dmg):

- Datei: `Entwicklerdokumente/Monkey Office Connect JSON-API Hilfe.html`
- SHA-256: `de3836cb7a582ac84118b121088496f663829de9b2c3f030a57a20fe8d706406`

Die Hilfe beschreibt Fachstrukturen, keine internen Tabellen.
Lokale Zuordnungen sind aus Schema und Datenbeziehungen abgeleitet.
App- und PDF-Belege sind gesondert gekennzeichnet.
Die Zuordnungen wurden nicht mit laufendem Connect verglichen.
Das Fachschema nennt fehlende zugeordnete oder dokumentierte Spalten sowie Herkunft und Grenzen.
Unbekannte Codes werden nicht umgedeutet.

## Prüfungen

```sh
uv run python -m unittest discover -s tests -v
```

Tests verwenden nur temporäre synthetische verschlüsselte Datenbanken, keine Ursprungsdatenbanken oder privaten Schlüssel.
Sie prüfen Entschlüsselung, Schreib- und Journalabwehr, Firmenisolation, Einheiten, Filter und Seitennavigation.
Fachliche Tests decken Berichte, Stornos, Zahlungsverknüpfungen, unvollständige Historien und gespeicherte Anlagenpläne ab.
Weitere Prüfungen betreffen Vorjahresabweichungen, Berichtsnachweise, Kontenabstimmung und strukturierte Fehlercodes.

Die Ausgabetests prüfen unveränderte gespeicherte Werte, freie SQL-Aliase, Binärwerte und konsistente Status- und Geldspalten.
Ein neu gestarteter stdio-MCP wurde zusätzlich mit einem synthetischen verschlüsselten Datenstand geprüft.
Die Aufrufe bestätigten Vorjahresabweichung, Ergebnisnachweis und strukturierten Firmenzugriffsfehler.
Die Datenbank blieb unverändert. Dabei wurde keine Ursprungsdatenbank geöffnet.
Quellpaket und Wheel wurden gebaut und beide installierten CLI-Kommandos mit `--hilfe` gestartet.

### GitHub Actions

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) startet bei Push, Pull Request oder manuell.
Die Tests laufen unter Linux (`ubuntu-latest`) mit Python 3.13 und 3.14.
Nach erfolgreichen Tests baut der ARM64-Runner `macos-latest` das Quellpaket und daraus das Wheel.
Er installiert das Wheel in einer eigenen Umgebung und prüft beide CLI-Einstiegspunkte mit `--hilfe`.
Die Pakete bleiben sieben Tage als CI-Artefakte verfügbar. Dieser Workflow veröffentlicht keine Pakete auf PyPI.

## Lokale Dateien

Git ignoriert diese Dateien und Ordner:

| Inhalt | Ausschlussregeln |
| --- | --- |
| MCP-Konfiguration | `.omp/` |
| Umgebungsdateien | `.env`, `.env.*` |
| Schlüssel und Passwortdateien | `*.key`, `*.passwort`, `*.password`, `*.passwd`, `*.secret` |
| Weitere Zugangsdaten | `passwort.txt`, `password.txt`, `credentials.json` |
| Berichte | `berichte/`, `reports/` |

Lege Berichte mit Geschäftsdaten in `berichte/` oder `reports/` ab.
Ergänze für andere Namen oder Ablageorte eigene Ausschlussregeln.
Die Regeln gelten nur für Dateien, die Git noch nicht versioniert.

## Pakete und Releases

Das Quellpaket enthält Projektcode, Python-Tests, README, Dokumentation und Lizenz.
Hinzu kommen Paketkonfiguration, Lockdatei, Ausschlussregeln und GitHub-Workflows.
Die Dateiauswahl steht in [`pyproject.toml`](../pyproject.toml).
Der Projektcode steht unter der [MIT-Lizenz](../LICENSE).

### Release erstellen

1. Setze die stabile Version in `pyproject.toml`.
2. Aktualisiere `uv.lock` mit `uv lock`.
3. Schreibe `docs/releases/vX.Y.Z.md` mit Funktionen, Voraussetzungen, Installation und konkreten Grenzen.
4. Committe Versionsdateien, Releasehinweise und die weiteren Änderungen.
5. Erstelle einen Tag `vX.Y.Z`, dessen Nummer genau der Paketversion entspricht.
6. Pushe den Tag.

Der Tag startet [`.github/workflows/release.yml`](../.github/workflows/release.yml).
Der Workflow prüft die Version, führt Tests aus und installiert das gebaute Wheel auf macOS.
Er veröffentlicht genau diese geprüften Pakete mit SHA-256-Prüfsummen als GitHub-Release.
Die Veröffentlichung verwendet die versionierten Releasehinweise. Fehlende oder leere Hinweise stoppen den Workflow vor den Tests.
Fehlgeschlagene Prüfungen oder Tags ohne passende stabile Paketversion verhindern die Veröffentlichung.
Ein normaler Branch-Push startet keine Veröffentlichung.
