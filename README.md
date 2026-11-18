# mo-local-mcp

Lokaler, ausschließlich lesender MCP-Server für verschlüsselte MonKey-Office-Datenbankstände.
Entschlüsselung seitenweise im Arbeitsspeicher, keine unverschlüsselte Datenbankdatei,
keine Schreibzugriffe auf die Ursprungsdatenbank.

## Sprache und Beispieldaten

Kommandos, Parameter, Beschreibungen, eigene Ausgabeschlüssel und Meldungen sind Deutsch.
Die früheren englischen MCP-Kommandos werden nicht mehr angeboten.
Unbekannte Parameter werden zurückgewiesen statt stillschweigend ignoriert;
auch Parameter-Validierungsfehler des MCP-Servers werden Deutsch erklärt.
Technische MCP-/JSON-Schema-Bezeichner, Originaldatenbankspalten, selbst gewählte
SQL-Aliase und offizielle Connect-Feldnamen bleiben unverändert.
Gespeicherte Namen und Belegtexte werden nicht übersetzt oder durch erfundene Werte ersetzt.

Fehlgeschlagene Werkzeugaufrufe setzen `isError: true`.
`structuredContent.fehler` enthält einen stabilen `code` und die deutsche `meldung`.
Clients sollen den Code auswerten, nicht den Meldungstext.

| Code | Bedeutung |
| --- | --- |
| `UNBEKANNTES_KOMMANDO` | Das Kommando wird von diesem Prozess nicht angeboten. |
| `UNBEKANNTE_PARAMETER` | Mindestens ein Parametername ist unbekannt. |
| `UNGUELTIGE_PARAMETER` | Pflichtfelder, Datentypen oder Parameterwerte sind ungültig. |
| `ZUGRIFF_VERWEIGERT` | Die Firma ist für diesen Prozess nicht freigegeben. |
| `DATENSTAND_GEAENDERT` | Die Datenbankdatei oder ihr Journalzustand hat sich geändert. Neuer konsistenter Datenstand und Neustart erforderlich. |
| `ABFRAGEGRENZE` | Eine Ausführungs- oder Ausgabegrenze verhindert das Ergebnis. |
| `DATENBANKFEHLER` | Eine Datenbankabfrage oder fachliche Datenprüfung schlägt fehl. |
| `INTERNER_FEHLER` | Ein unerwarteter interner Fehler verhindert die Abfrage. |

**Alle folgenden Beispielkennungen, Vorgänge und Beträge sind vollständig synthetisch.**
Zuerst `firmen_auflisten` aufrufen und eine Firma ausdrücklich auswählen.
Beispiel-IDs nicht ungeprüft verwenden. Private Berichte und echte Geschäftsvorgänge
gehören weder in Beispiele noch in Testdaten.

## Einrichtung

macOS, Python ab 3.13 und [uv](https://docs.astral.sh/uv/) werden benötigt.

```sh
uv sync --frozen
uv run mo-schluessel-wiederherstellen
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db
```

stdin/stdout dienen dem MCP-Protokoll, nicht einer interaktiven SQL-Konsole.
Meldungen gehen nach stderr. Hilfe: `uv run mo-local-mcp --hilfe` beziehungsweise
`uv run mo-schluessel-wiederherstellen --hilfe`.

### Versionierte Pakete installieren

GitHub-Releases enthalten nach erfolgreicher Prüfung ein Wheel, ein Quellpaket und `SHA256SUMS`.
Es gibt keine automatische Veröffentlichung auf PyPI.
Wähle eine vorhandene Version unter [Releases](https://github.com/realholgi/mo-local-mcp/releases).
Lade das Wheel und `SHA256SUMS` aus demselben Release in einen eigenen Ordner.
Die folgende Dateibezeichnung ist ein Beispiel für Version `0.1.0`, keine Zusage eines vorhandenen Releases.

```sh
shasum -a 256 mo_local_mcp-0.1.0-py3-none-any.whl
cat SHA256SUMS
uv tool install --python 3.13 ./mo_local_mcp-0.1.0-py3-none-any.whl
mo-local-mcp --hilfe
```

Vergleiche die Prüfsumme vor der Installation mit dem Eintrag in `SHA256SUMS`.
`uv tool install` richtet eine eigene Umgebung mit beiden Kommandos ein.
Falls die Kommandos nicht gefunden werden, führe `uv tool update-shell` aus und öffne eine neue Shell.
Für MCP-Clients verwende den absoluten Kommandopfad aus `uv tool dir --bin`.
Die Datenbank und die Schlüsseldatei bleiben außerhalb dieser Umgebung.

Zum Aktualisieren beende den MCP-Prozess und lade die Pakete der gewünschten Version.
Prüfe wieder die Prüfsumme. Installiere das neue Wheel mit `uv tool install --force --python 3.13 ./DATEI.whl`.
Starte danach den MCP-Client neu. Für eine Rückkehr installiere das Wheel der vorherigen Version mit demselben Befehl.

### Schlüssel

Das Kommando `mo-schluessel-wiederherstellen` ist auch im Wheel enthalten.

Die Profiltabelle `PROFILE` in `mo_local_mcp/schluessel.py` enthält die erfassten Programmversionen.
Erfasst sind MonKey Office 2026 in den Programmversionen 23.0.2, 23.1.0 und 23.2.4.
Zusätzlich ist MonKey Office 2025 in Programmversion 22.4.0 erfasst.
Der SHA-256 der Programmdatei bestimmt das Profil. Unbekannte Dateien werden abgelehnt.
Ohne `--programmdatei` verwendet das Kommando `/Applications/MonKey Office 2026.app/Contents/MacOS/MonKey Office 2026`.
Es liest die Programmdatei und speichert den Schlüssel. Es führt keinen Anwendungscode aus.
Der Schlüssel erscheint nicht in der Ausgabe. Herstellerprogrammdateien werden nicht verteilt.

Standardziel außerhalb des Projekts:
`~/Library/Application Support/mo-local-mcp/database.key`, Zugriffsmodus `0600`.
Passender vorhandener Inhalt wird wiederverwendet; abweichender Inhalt nicht überschrieben.
Abweichende Pfade:

```sh
uv run mo-schluessel-wiederherstellen \
  --programmdatei "/Applications/MonKey Office 2026.app/Contents/MacOS/MonKey Office 2026" \
  --ausgabe /privater/pfad/datenbank.key
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db \
  --schluesseldatei /privater/pfad/datenbank.key
```

Archivierte Apps an einem anderen Ort benötigen den Pfad zur ausführbaren Datei:

```sh
uv run mo-schluessel-wiederherstellen \
  --programmdatei "/pfad/zum/archiv/MonKey Office 2026 23.0.2.app/Contents/MacOS/MonKey Office 2026"
```

Für 23.1.0 gilt derselbe Aufruf mit dem passenden App-Pfad.
Für MonKey Office 2025 lautet der Pfad innerhalb der App `Contents/MacOS/MonKey Office 2025`.
Für Archive und andere Ablageorte ist `--programmdatei` erforderlich.
Auch eine unterstützte ältere Version am Standardpfad wird über ihren Hash erkannt.
Der Dateiname allein bestimmt die Version nicht. Entscheidend ist der SHA-256 der ausführbaren Datei.
Die vier erfassten Programmdateien liefern denselben 32-Byte-Standardschlüssel.
Die Ableitung wurde für die Archivversionen über das CLI geprüft, ohne die Apps zu starten.
Die Prüfung speicherte keine Schlüsselwerte in Dokumentation oder Testdaten.

#### Neue Programmversionen

Für eine neue Version mit gleichem Ableitungsverfahren ergänze einen Eintrag am Ende von `PROFILE`.
Bestehende Profile bleiben erhalten. Die Reihenfolge der Einträge geht von alt nach neu.

| Feld | Bedeutung |
|---|---|
| Tabellenschlüssel | SHA-256 der genauen Programmdatei |
| `version` | Versionsbezeichnung für Fehlermeldungen |
| `konstanten_offset` | Beginn der Konstantentabelle relativ zu diesem Mach-O-Teil |
| `eintrag_groesse` | Abstand zwischen den Tabelleneinträgen in Bytes |
| `zeiger_offset` | Position des Zeichenkettenzeigers innerhalb eines Eintrags |
| `zeichen_marker` | Erwartetes Byte vor dem Zeichen |
| `zeichenindizes` | Indizes der Zeichenkonstanten in Base64-Ausgabereihenfolge |

Der Leser verwendet immer den ARM64-Teil (`CPU_TYPE_ARM64 = 0x100000C`) der Universal-Mach-O-Datei.
Er liest 64-Bit-Little-Endian-Zeiger und einzelne Base64-Zeichen.
Zeichenkettenzeiger werden über `vmaddr`, `fileoff` und `filesize` dem passenden dateigestützten Segment zugeordnet.
Zeiger auf `__PAGEZERO`, Zero-Fill-Bereiche oder über das Segmentende hinaus werden abgelehnt.
Das Ableitungsformat liefert immer 32 Schlüsselbytes. Der Datenbankleser verwendet davon 16 Bytes für AES-128.
Ein anderes Datei- oder Ableitungsformat erfordert eine Änderung am Leser.

### OMP

Lege bei Bedarf eine lokale `.omp/mcp.json` aus dem folgenden Beispiel an.
OMP startet damit `mo-local-mcp` aus der installierten virtuellen Umgebung.
Git und Veröffentlichungspakete schließen diese rechnergebundene Konfiguration aus.
Nach einem frischen Checkout musst du die Datei selbst anlegen.
Trage dort keine Schlüssel oder Zugangsdaten ein.

Die `beispiel.sdb` im Projektordner dient nur der Entwicklung.
Produktionsdatenquelle und Aktualisierungsverfahren sind noch offen.
Lade die Konfiguration nach Änderungen mit `/mcp reload` neu.
Prüfe sie bei Bedarf mit `/mcp test mo-local-mcp`.
Beide Befehle gehören zu OMP.

Konfigurationsbeispiel mit anzupassenden Platzhalterpfaden:

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

## MCP-Kommandos

| Kommando | Zweck |
| --- | --- |
| `datenbankinformationen` | Datenquelle, Verschlüsselung, Schreibschutz und Grenzen |
| `tabellen_auflisten` | Tabellen/Sichten mit originalem CREATE-SQL |
| `tabelle_beschreiben` | Spalten, Fremdschlüssel, Indizes und Fachbeschreibung |
| `sql_abfragen` | Gebundene SELECT-/WITH-Abfragen; nur mit `--mit-sql` |
| `fachschema_anzeigen` | Fachbegriffe, Einheiten, Wertelisten, Verknüpfungen und Grenzen |
| `firmen_auflisten` | Firmen mit lokalen Kennungen |
| `firma_abrufen` | Vollständiger Firmenstamm einschließlich Anschrift und Steuerangaben |
| `geschaeftsjahre_auflisten` | Zeiträume, Versteuerung, Sperren und Zähler |
| `steuersaetze_auflisten` | Steuerdefinitionen, Konten, UVA und Sperren |
| `kontenplan_anzeigen` | Konten einschließlich unbebuchter/gesperrter Konten und Vorgaben |
| `adressen_suchen` | Kunden-/Lieferantenadressen und Statusfilter |
| `adresse_abrufen` | Vollständige Firmenadresse einschließlich Status und Notizen |
| `verkaufsbelege_auflisten` | Belegarten, Datums-/Adressfilter und gespeicherte Summen |
| `verkaufsbeleg_abrufen` | Belegkopf und geordnete Positionen |
| `einkaufsbelege_auflisten` | Einkaufsbelege mit Belegart-, Datums-, Adress- und Textfilter |
| `einkaufsbeleg_abrufen` | Einkaufsbelegkopf und geordnete Positionen |
| `artikel_auflisten` | Artikel und Leistungen mit Lagerkennzeichen und Stammpreisen |
| `projekte_auflisten` | Projekte, Zeiträume, Notizen und gespeicherter Status |
| `buchungen_auflisten` | Buchungen mit Datums-, Konto- und Textfilter |
| `buchung_abrufen` | Vollständiger Buchungskopf und seitenweise Journalzeilen |
| `offene_posten_auflisten` | Forderungen, Verbindlichkeiten und Gutschriften |
| `offenen_posten_abrufen` | OP-Kopf, Positionen, Zahlungshistorie und Abgleich |
| `zahlungen_auflisten` | Zahlungsköpfe mit Datums-, Adress- und Textfilter |
| `zahlung_abrufen` | Zahlung/Verrechnung mit Belegzuordnungen |
| `bilanz_und_guv_anzeigen` | Gliederungsbasierte Berichte mit Konten und Vorjahr |
| `berichtsnachweis_anzeigen` | Beiträge einer Berichtsposition bis zu Journal- und Buchungszeilen |
| `kontenabstimmung_pruefen` | Hauptbuch, Personenkonten und rekonstruierte OP-Salden zum Stichtag abstimmen |
| `kontoauszug_anzeigen` | Eröffnung, Umsätze, laufende Salden und Steuerschlüssel |
| `summen_und_salden_anzeigen` | Jährliche Hauptbuchübersicht mit Eröffnung, Umsätzen und Endsalden |
| `debitoren_salden_anzeigen` | Journal-Soll, -Haben und Salden der Kundenkonten |
| `kreditoren_salden_anzeigen` | Journal-Soll, -Haben und Salden der Lieferantenkonten |
| `offene_posten_zum_stichtag_anzeigen` | Rekonstruierte Stichtagssalden und Fälligkeiten |
| `offene_posten_altersstruktur_anzeigen` | Stichtagssummen nach Seite, Währung und Altersklasse |
| `steuerjournal_anzeigen` | Steuerjournal einschließlich IST-Versteuerungsnachweisen |
| `umsatzsteuer_voranmeldung_anzeigen` | Gespeicherte monatliche/vierteljährliche UVA |
| `kostenstellen_auflisten` | Kostenstellen, Sperren und vollständige Notizen |
| `zahlungsbedingungen_auflisten` | Fristen, Vorlagen und unveränderte Skontowerte |
| `waehrungen_auflisten` | Währungen, Symbole sowie rohe Faktoren und Kurse |
| `anlagen_auflisten` | Auch abgegangene und abgeschriebene Anlagen |
| `anlage_abrufen` | Anlagenstamm mit gespeicherten Bewegungen |
| `abschreibungsplan_anzeigen` | Gespeicherte Anlagen-/AfA-Bewegungen mit Filtern |
| `belege_suchen` | Gemeinsame Suche in fünf Belegbereichen mit Folgewerkzeugen |
| `belegverknuepfungen_anzeigen` | Unmittelbare gespeicherte Beziehungen zwischen Belegen, Buchungen und Zahlungen |
| `datenqualitaet_pruefen` | Verknüpfungsfehler, Buchungsausgleich und Zahlungsabgleiche |
| `kostenstellen_auswerten` | Kostenstellenbeträge mit deduplizierten Gesamtwerten |
| `konten_monatlich_anzeigen` | Monatliche Hauptbuchbewegungen und getrennte Eröffnungen |
| `guv_monatlich_anzeigen` | Monats-GuV nach gespeicherter Gliederung |
| `datenstand_anzeigen` | Vorhandene Zeiträume und gespeicherte Buchungszeitpunkte |
| `anhaenge_auflisten` | Gespeicherte Anhangsmetadaten ohne BLOB-Inhalt |
| `anhang_lesen` | Begrenzte rohe Anhangsbytes aus der Datenbank als Base64 |

### Parameter und Ergebnisform

- `firma_id` ist bei Fachabfragen zwingend. Kennungen sind lokale `_rowid`-Ganzzahlen,
  keine zugesicherten Connect-IDs. Jede Verknüpfung berücksichtigt die Firma.
- Listen verwenden `anzahl`/`versatz`; `naechster_versatz` verweist auf die nächste Seite.
  Standardmäßig 100, maximal 500 Zeilen. `suche` ist wörtlich, keine Platzhalterauswertung.
  SQLite berücksichtigt Groß-/Kleinschreibung dabei nur im ASCII-Bereich.
- `datum_von`/`datum_bis` sind ISO-Daten `YYYY-MM-DD`, einschließlich beider Grenzen.
  `jahr` bezeichnet bei Finanzberichten den Beginn des gespeicherten Geschäftsjahres.
- Tabellenförmige Ergebnisse: `spalten`, `zeilen`, `gekuerzt`.
  Originalspalten bleiben original, eigene abgeleitete Spalten sind Deutsch.
- Fachwerkzeuge liefern Geld als Dezimalzeichenketten in Währungseinheiten; `geldbetraege`
  nennt die bereits durch 100 geteilten Felder. Nicht erneut umrechnen.
  Reines synthetisches Rechenbeispiel: `12345` ergibt `"123.45"`.
  `sql_abfragen` liefert dagegen weiterhin den Rohwert `12345`.
- Mengen, Prozentsätze, Kurse, Kontonummern und IDs sind keine Geldfelder. Null bleibt null.
  FW/SW sowie Währungen getrennt halten; keine Wechselkurse herleiten.
  Fachlisten bewahren Preisnachkommastellen, Finanz-/Steuerberichte formatieren Geld zweistellig.
- Große Ganzzahlen verlustfrei als Zeichenketten, Binärwerte mit technischem Schlüssel `base64`.

Synthetische Beispielparameter für `verkaufsbelege_auflisten`:

```json
{"firma_id": 101, "belegart": 4, "datum_von": "2028-01-01", "datum_bis": "2028-12-31"}
```

`adressen_suchen`: `rolle` aus `alle`, `kunden`, `lieferanten`; `status` aus
`alle`, `aktiv`, `inaktiv`, `gesperrt`. Ein Statusfilter erfordert eine bestimmte
Rolle. Eine Adresse kann Kunde und Lieferant sein.

`adresse_abrufen` benötigt `firma_id` und `adresse_id`. Das Ergebnis `adresse`
enthält alle Originalspalten und beide Rollenlabels. Auch inaktive, gesperrte
und rollenlose Adressen sind abrufbar. Notizen bleiben vollständig erhalten.

`firma_abrufen` benötigt `firma_id` und liefert `firma` mit allen Originalspalten.
Der Firmenstamm enthält unter anderem Anschrift, Steuerangaben und Kontenplan.
Geschäftsjahre liefert weiterhin `geschaeftsjahre_auflisten`.

`buchungen_auflisten` bietet zusätzlich `belegnummer`, `konto_soll`, `konto_haben`
und `kostenstelle`. `belegnummer` sucht wörtlich in `BelegNr`.
Soll-/Habenkonten wählen Journalzeilen mit einem Betrag ungleich null auf der jeweiligen Seite.
Negative Stornos bleiben enthalten. `kostenstelle` vergleicht `Kostenstelle1` und
`Kostenstelle2` exakt. Mehrere Filter gelten gemeinsam für den Buchungskopf.
Sie müssen nicht dieselbe Journalzeile treffen. Der rohe Buchungsstatus bleibt unverändert.

`verkaufsbelege_auflisten` durchsucht mit `suche` zusätzlich `AuftragsNr`,
`BestellNr` und `Betreff`. Die Suche ist wörtlich.

`einkaufsbelege_auflisten` liest `BESTELLUNG`. Es gelten die gleichen Datums-,
Adress- und Entwurfsregeln wie für Verkaufsbelege.
`suche` durchsucht die Belegnummer, Lieferantenreferenz und den Betreff wörtlich.
`belegart` filtert gespeicherte Codes. Dokumentiert sind:
101 Bestellanfrage, 102 Bestellung, 103 Wareneingang, 104 Eingangsrechnung,
105 Lieferantengutschrift, 106 Rücksendung und 107 Stornierung.
Unbekannte Codes bleiben unverändert sichtbar.
`einkaufsbeleg_abrufen` liefert `beleg` und `positionen`.
`positionen_anzahl`/`positionen_versatz` blättern nur die Positionen.
FW/SW bleiben getrennt. Text- und Alternativpositionen sind kein pauschal summierbarer Aufwand.

`artikel_auflisten` filtert mit `artikelart`, `nur_lagerartikel` und `warengruppe`.
Artikelart 1 bezeichnet Artikel, 2 Leistungen. Weitere Codes bleiben roh.
Die Warengruppe wird exakt verglichen. Gesperrte Artikel bleiben sichtbar.
Geldfelder sind bereits umgerechnet. Mengen, Gewichte und Prozentsätze bleiben unverändert.
Das Werkzeug leitet weder eine Preiswährung noch aktuelle Lagerbestände ab.

`projekte_auflisten` liefert Projektstammdaten mit Zeitraum, Notizen und rohem Status.
Die Liste enthält keine berechneten Projektumsätze, Ergebnisse oder Arbeitszeiten.

`offene_posten_auflisten` filtert mit `datum_von`/`datum_bis` das Belegdatum.
Die Beträge bleiben die gespeicherten OP-Salden des Datenstands.
Für historische Salden dient `offene_posten_zum_stichtag_anzeigen`.

`buchung_abrufen` benötigt `firma_id` und `buchung_id`. Das Ergebnis enthält
`buchung` und `journalzeilen`. Nur die Journalzeilen sind mit
`journal_anzahl`/`journal_versatz` seitenweise abrufbar.
Der vollständige Kopf bleibt auf jeder Seite erhalten. Journalreihenfolge:
`NummerLong`, `Position`, `_rowid`. Vorzeichen, Storno, Steuerschlüssel,
FW/SW und rohe Statuswerte bleiben erhalten. Keine Buchungssummen aus Teilseiten ableiten.

## Fachschema und Quellen

27 Tabellen sind fachlich beschrieben:
`FIRMA`, `ADRESSE`, `AUFTRAG`, `AUFTRAGSPOSITION`, `BUCHUNG`, `JOURNAL`, `POSTEN`,
`POSTENPOSITION`, `WAEHRUNG`, `KONTO`, `STEUERSATZ`, `WIRTSCHAFTSJAHR`,
`KONTOSTRUKTUR`, `STRUKTURPOSITION`, `ZAHLUNG`, `ZAHLUNGSPOSITION`, `KOSTENSTELLE`,
`ZAHLUNGSBEDINGUNG`, `ELSTERMELDUNG`, `ELSTERMELDUNG_NT`, `STEUERERKLAERUNG`,
`ANLAGE`, `ANLAGENPOSITION`, `BESTELLUNG`, `BESTELLPOSITION`, `ARTIKEL`, `PROJEKT`.
Andere Tabellen bleiben technisch lesbar.

Begriffsquelle: JSON-API-Hilfe **23.2.0 / 07.07.26** aus dem
[Connect-Download](https://www.monkey-office.de/download/current/mac/MonKey_Office_Connect.dmg),
Datei `Entwicklerdokumente/Monkey Office Connect JSON-API Hilfe.html`,
SHA-256 `de3836cb7a582ac84118b121088496f663829de9b2c3f030a57a20fe8d706406`.
Sie beschreibt Fachstrukturen, nicht interne Tabellen. Lokale Zuordnungen sind aus
Schema/Datenbeziehungen abgeleitet; App-/PDF-Belege gesondert gekennzeichnet.
Kein Vergleich mit laufendem Connect. Das Fachschema meldet fehlende zugeordnete/
dokumentierte Spalten, Herkunft und Grenzen. Unbekannte Codes nicht umdeuten.

### Vergleich mit anderen MCP-Servern

Die Lesefunktionen wurden mit diesen GitHub-Projekten verglichen:

- [kustus/MO-Connect-MCP](https://github.com/kustus/MO-Connect-MCP):
  Firmendetails, Einkaufsbelege, Artikel, Projekte, Debitoren/Kreditoren und Buchungsfilter.
- [UhlhornHH/monkey-office-mcp](https://github.com/UhlhornHH/monkey-office-mcp):
  Buchungsdetails sowie Belegnummern- und Soll-/Habenkontenfilter.

Die Umsetzung liest lokale Tabellen und verwendet keinen Fremdcode.
Ergänzende Begriffsquelle ist die
[aufbereitete Connect-Referenz 22.1.1](https://github.com/tkaufmann/monkeyoffice-api-docs/tree/main/docs/v22.1.1/endpoints).
Lokale Zuordnungen zu dieser Referenz sind aus dem Schema abgeleitet.
Die Buchungs-, Import- und Anhang-Schreibfunktionen werden nicht übernommen.
Vorlagen zum Anlegen neuer Buchungen sind für den lesenden MCP nicht erforderlich.
Nicht belegte Festschreibungs- und Zahlungsstatuszuordnungen werden nicht nachgebildet.

## Berichte, Konten und Geschäftsjahre

`bilanz_und_guv_anzeigen` liefert `bilanz.aktiva`, `bilanz.passiva`, `guv`,
Hierarchie und Kontenaufschlüsselung; optional `gliederung_id`, `mit_vorjahr`.
**Elternsummen enthalten Unterpositionen und direkte Konten: nicht alle Zeilen addieren.**
Die gespeicherte `STRUKTURPOSITION`-Hierarchie, Kontenlisten und `VzWechsel` bestimmen
Zuordnung/Vorzeichen. Die B-Position übernimmt das GuV-Ergebnis.

Nur ausdrücklich auf beiden Bilanzseiten gelistete Konten wechseln nach Saldenvorzeichen.
Steuer-Sollsalden können Passivpositionen mindern; negatives Eigenkapital bleibt an
gespeicherter Stelle. Persönliche Konten mit positivem `SammelKonto` nicht doppelt zählen.
Neutrale Vortragskonten nur bei gemeinsamer Nullsumme ausschließen.
Alle Perioden/Statuswerte und gebuchte Eröffnungen des Geschäftsjahres; keine doppelte
Vorjahresübernahme. Vorjahr separat mit heutiger Gliederung, fehlendes Vorjahr null.
Mehrdeutige/unvollständige Zuordnungen, Kontenlisten/Hierarchien und unausgeglichene
Daten sind Fehler. Keine eingereichten Abschlüsse, steuerlich bereinigten Gewinne
oder historischen Gliederungsversionen.

Der `vorjahresvergleich` nennt die Vergleichbarkeit von Währung und Zeitraum.
Berichtspositionen, Konten und Summen enthalten `abweichung_absolut` und `abweichung_prozent`.
Die absolute Abweichung ist der aktuelle Betrag minus Vorjahresbetrag.
Die Prozentabweichung bezieht diese Differenz auf den absoluten Vorjahresbetrag.
Bei zwei Nullbeträgen ist sie null. Bei Vorjahresbetrag null und aktuellem Betrag ungleich null bleibt sie `null`.
Ohne vergleichbares Vorjahr bleiben beide Abweichungen `null`. Die Begründung steht im Vergleich.
Unterschiedliche Währungen werden nicht umgerechnet.
Für den Zeitraumvergleich werden Beginn und Ende des Vorjahres um ein Kalenderjahr verschoben.
Der 29. Februar wird dabei zum 28. Februar. Beide Grenzen müssen dem aktuellen Geschäftsjahr entsprechen.

`berichtsnachweis_anzeigen` benötigt `firma_id`, `jahr`, `gliederung_id` und `position_id`.
`position_id` bezeichnet die gespeicherte `ItemId` aus der Berichtsgliederung.
Das Ergebnis zeigt die beteiligten Konten, Vorzeichenfaktoren und Beiträge.
Unterpositionen und die Ergebnisübernahme folgen der Bilanz-/GuV-Berechnung.
`buchungszeilen` enthält die beitragenden Journalzeilen mit `buchung_id`.
Diese ID kann anschließend mit `buchung_abrufen` gelesen werden.
Optional grenzt `konto` die Beiträge auf ein effektives Hauptbuchkonto ein.
Die Seiteneinteilung verändert die Gesamtsumme nicht.

`kontenabstimmung_pruefen` benötigt `firma_id`, `jahr` und `stichtag`.
Es vergleicht Hauptbuch, Personenkonten und rekonstruierte OP-SW-Salden.
Nur gespeicherte Zuordnungen belegen die Verbindung.
Fehlende oder mehrdeutige Zuordnungen, unbekannte Historien und Währungsprobleme verhindern einen bestätigten Abgleich.
Forderungen und Verbindlichkeiten bleiben getrennt.
Differenzen sind Befunde. Sie belegen keine bestimmte Fehlerursache.
Beide neuen Werkzeuge sind im Modus `--ohne-sensible-stammdaten` nicht verfügbar.

`kontoauszug_anzeigen` benötigt `firma_id`, `jahr`, `konto`. Ergebnis trennt
`eroeffnung`, `umsaetze`, `endsaldo`, `buchungszeilen`. Eröffnungen (`BUCHUNG.Art=2`)
bilden den Anfangssaldo, nicht Umsatz. Stornierte Originale und vorzeichenbehaftete
Gegenbuchungen bleiben erhalten. Reihenfolge: Datum, Belegnummer, Journalnummer, Position.
Summen und laufende Salden gelten für das volle Jahr unabhängig von der Seite.
Negativer Saldo bedeutet Haben, positiver Soll. `steuerschluessel` übernimmt
`JOURNAL.Steuersatz`, auch `-`, Leertext und null. Kein Bankauszug oder Kassennachweis.

`summen_und_salden_anzeigen` benötigt `firma_id` und `jahr`.
`konto_von`/`konto_bis` begrenzen die effektiven Hauptbuchkonten einschließlich.
Personenbuchungen zählen einmal im gespeicherten positiven `SammelKonto`,
sonst im `Konto`. Eröffnungen (`BUCHUNG.Art=2`) bleiben von Umsätzen getrennt.
Vortragskonten, Konten mit Aktivität und Nullsaldo sowie vorzeichenbehaftete Stornos
bleiben enthalten. Es gibt keinen Statusfilter.
Das Ergebnis enthält `konten`, `summen` und `anzahl_konten`.
Summen gelten für den vollständigen Kontenfilter vor `anzahl`/`versatz`,
auch bei einer leeren Seite hinter dem Ergebnis.
Alle Beträge verwenden die SW-Währung des gespeicherten Geschäftsjahres.
`name` bleibt die gespeicherte Namensvorlage, ohne Platzhalterauflösung.
Die Liste benötigt keine Abschlussgliederung. Ein Kontenfilter muss nicht ausgeglichen sein.

`debitoren_salden_anzeigen` und `kreditoren_salden_anzeigen` wählen Kunden- bzw.
Lieferantenkonten aus den gespeicherten Adresszuordnungen.
Sie summieren Journal-Soll und -Haben im einschließlich gesetzten Datumsbereich.
Saldo ist Soll minus Haben. Eröffnungen, alle Buchungsstatus und negative Stornos zählen mit.
Diese Beträge sind weder reine Umsätze noch historische OP-Salden.
Konten mit mehreren Adressen zählen einmal.
Ein `adresse_id`-Filter wählt das gesamte zugeordnete Konto, ohne dessen Saldo auf die Adresse aufzuteilen.
FW-/SW-Währung stammen aus Buchung und Geschäftsjahr.
Unterschiedliche Währungspaare bleiben getrennt, auch in den Gesamtsummen.
Fehlende Kontozuordnungen liefern keine erfundenen Nullsalden.

`kontenplan_anzeigen` liefert dagegen Stammdaten mit vollständigen Notizen,
DATEV-/Währungs-/Sperrfeldern und datierten Steuerzuordnungen. `konto_von`/`konto_bis`
sind inklusive. `Bezeichnung` ersetzt `#P#`, die Vorlage bleibt erhalten.
Je Vorgabefeld jüngster nichtleerer Wert, bei gleichem Datum erste Alternative.
Vorgaben ersetzen keine gebuchten Steuerschlüssel. Steuerprozente sind kein Geld;
fehlende Werte bleiben null. Geschäftsjahres-OP-Zähler zählen auch ausgeglichene
Belege, Gutschriften und Entwürfe, nicht nur unbezahlte Rechnungen.

### Kostenstellen und Monatsberichte

`kostenstellen_auswerten` verwendet `datum_von`, `datum_bis` und optional
`kostenstelle`. Der Kostenstellenfilter vergleicht exakt.
Gleiche Werte in `Kostenstelle1` und `Kostenstelle2` zählen pro Journalzeile einmal.
Bei zwei verschiedenen Kostenstellen erhält jede Gruppe die ganze Zeile.
**Kostenstellengruppen deshalb nicht addieren.**
`gesamtwerte` zählt jede passende Quellzeile einmal, unabhängig von der Seite.
FW-/SW-Währungspaare bleiben getrennt. Leere Kostenstellen bilden eine eigene Gruppe.
Eröffnungen und Bewegungen stehen getrennt. Der Bericht leitet keinen Anfangsbestand ab.

`konten_monatlich_anzeigen` benötigt `firma_id` und `jahr`.
Optional begrenzen `konto_von`/`konto_bis` die effektiven Hauptbuchkonten.
Der Bericht zeigt Kalendermonate innerhalb des gespeicherten Geschäftsjahres.
Ein abweichendes Geschäftsjahr muss nicht im Januar beginnen.
Positive Sammelkonten ersetzen Personenkonten genau einmal.
Eröffnungen bleiben getrennt von Bewegungen. Endsalden kumulieren nur gespeicherte Werte ab Jahresbeginn.
Ein fehlender Anfangsvortrag wird nicht ergänzt.
`anzahl`/`versatz` blättern Konten, nicht deren Monate.
Die monatlichen `gesamtwerte` betreffen den vollständigen Kontenfilter.

`guv_monatlich_anzeigen` benötigt ebenfalls `firma_id` und `jahr`.
Bei mehreren gespeicherten Gliederungen ist `gliederung_id` erforderlich.
Der Bericht verwendet die gespeicherte GuV-Hierarchie und ihre Vorzeichenwechsel.
Er zeigt direkte Beträge, Positionssummen und Monatsgewinn.
Eltern- und Unterpositionen dürfen nicht nochmals addiert werden.
Eröffnungen sind ausgeschlossen und separat ausgewiesen.
Fehlende oder mehrdeutige Erfolgskontenzuordnungen führen zu Fehlern.
Es gibt keinen zusätzlichen monatlichen Bilanzausgleich.

## Belegsuche, Verknüpfungen und Datenqualität

`belege_suchen` durchsucht Buchungen, Verkaufsbelege, Einkaufsbelege, Posten und
Zahlungen gemeinsam. Pflichtparameter: `firma_id` und `suche`.
Die Suche ist wörtlich. `datum_von`/`datum_bis` begrenzen das Belegdatum einschließlich.
Treffer sind gemeinsam nach Datum, Bereich und lokaler ID sortiert und paginiert.
Jeder Treffer enthält Herkunft und eine `navigation` mit Folgewerkzeug und Parametern.
Entwürfe bleiben enthalten. Die Suche bildet keine bereichsübergreifenden Geldsummen.

`belegverknuepfungen_anzeigen` benötigt `firma_id`, `bereich` und `datensatz_id`.
Bereiche: `buchung`, `verkauf`, `einkauf`, `posten`, `zahlung`.
Das Werkzeug zeigt unmittelbare eingehende und ausgehende gespeicherte Beziehungen:
Beleg zu Posten, Posten zu Buchung, Zahlung zu Buchung und Zahlungsposition zu Posten.
Gespeicherte Vorbelegbeziehungen sind ebenfalls enthalten.
Fehlende Ziele bleiben ausdrücklich unaufgelöst.
Die Navigation folgt keinen Betrags-, Namens- oder Referenzähnlichkeiten.
Zyklen werden nicht rekursiv verfolgt. Weitere Schritte erfolgen über die ausgegebenen IDs.

`datenqualitaet_pruefen` prüft den vollständigen Bestand einer gewählten Firma.
Der Prüfungsumfang nennt Tabellen, Verknüpfungsfelder und Anzahl der Prüfungen.
Es prüft fehlende gespeicherte Ziele, den Journal-Soll-/Haben-Ausgleich je Buchung
und gespeicherte Zahlungs-/Minderungssummen gegen ihre Zuordnungen.
FW und SW bleiben getrennt. Vorzeichenbehaftete Stornos bleiben erhalten.
Geldvergleiche verwenden kaufmännische Rundung auf 0,01 Währungseinheiten.
Fehlende oder ungültige Beträge sowie nicht vollständig auflösbare Zuordnungen bleiben unbekannt.
`anzahl`/`versatz` begrenzen nur die Befunde. Gesamtzahlen gelten vor der Seiteneinteilung.
Das Werkzeug korrigiert nichts und liefert keinen pauschalen Nachweis vollständiger oder steuerlich richtiger Buchführung.

## Datenstand und Leserechte

`datenstand_anzeigen` benötigt `firma_id`.
Es zeigt die Dateiänderungszeit sowie Anzahl und Belegzeiträume je Bereich.
Erfassungs- und Verbuchungszeitpunkte stammen aus den gespeicherten Buchungsfeldern.
Diese Zeitpunkte haben unterschiedliche Bedeutungen.
Die Dateiänderungszeit ist kein bestätigter Export- oder Sicherungszeitpunkt.
Die jüngste Buchung und vorhandene Geschäftsjahre belegen keine Vollständigkeit oder Aktualität.
Es gibt keine Live-Abfrage und keine automatische Aktualisierung.

Freies SQL ist standardmäßig gesperrt. Fachwerkzeuge bleiben ohne zusätzliche Optionen verfügbar.
Diese Optionen begrenzen den jeweiligen stdio-MCP-Prozess:

```sh
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db \
  --firma-id 101 --firma-id 202
```

- `--firma-id ID` gibt nur diese Firma frei. Die Option ist wiederholbar.
  Firmenlisten filtern vor der Seiteneinteilung. Alle Fachaufrufe prüfen die Freigabe.
  Freies SQL wird bei einer Firmenfreigabeliste immer gesperrt.
- `--mit-sql` bietet `sql_abfragen` ausdrücklich an, sofern weder Firmen- noch Stammdatenbeschränkungen gelten.
- `--ohne-sensible-stammdaten` bietet nur Metadaten und definierte Auswertungen an.
  Firmendetails, Adressen, Detailbelege, Personenkontendetails, Suche und Anhänge sind nicht verfügbar.
  Freies SQL ist ebenfalls gesperrt. Firmenlisten enthalten dann nur lokale IDs.

Im Stammdatenmodus bleiben Geschäftsjahre, Datenstand, Datenqualität, Kostenstellen,
Monatsberichte, Summen-/Saldenliste und Bilanz/GuV verfügbar.
Konten-, Gliederungs- und Kostenstellenbezeichnungen werden nicht anonymisiert.
Dieser Modus ist keine allgemeine Anonymisierung von Buchhaltungsdaten.
Die wirksamen Rechte stehen in `datenbankinformationen.zugriff` und `monkey://zugriff`.
Die Startoptionen ändern keine gespeicherten Datenbankrechte.

## MCP-Ressourcen und Prompts

Zusätzlich zu Werkzeugen bietet der MCP diese Ressourcen:

| URI | Inhalt |
| --- | --- |
| `monkey://fachschema` | Vollständiges dokumentiertes Fachschema mit Einheiten und Grenzen |
| `monkey://fachschema/{tabelle}` | Fachschema einer dokumentierten Tabelle |
| `monkey://zugriff` | Wirksame Leserechte dieses MCP-Prozesses |

Die Ressource enthält keine Geschäftsvorgänge.
`jahresabschluss_pruefen` erwartet `firma_id` und `jahr` als Zeichenketten.
Der Prompt beschreibt die Prüfung mit Datenstand, Qualität und gespeicherter Berichtsgliederung.
`forderungen_erklaeren` erwartet `firma_id` und `stichtag`.
Er beschreibt die Auswertung historischer OP-Salden mit belegten Zahlungsbeziehungen.
Beide Prompts prüfen die Firmenfreigabe und führen selbst keine Datenabfragen aus.
Im eingeschränkten Stammdatenmodus ist der Forderungsprompt nicht verfügbar.
Kein Prompt erlaubt Schreiben, Mahnversand oder Live-Connect.

## Gespeicherte Anhänge

`anhaenge_auflisten` benötigt `firma_id`. `suche` filtert Metadaten wörtlich.
Die Liste nennt die Speicherart für `anhang_lesen`:

- `eintrag`: `ATTACHMENTITEM` mit firmengebundenen `ATTACHMENTCHUNK`-Zeilen.
- `altbestand`: BLOB `ATTACHMENT.Data`, ohne die separate Vorschau.
- `alias`: BLOB `ATTACHMENTALIAS.Data`.

`anhang_lesen` benötigt `firma_id` und `anhang_id`.
`speicher` ist standardmäßig `eintrag`.
`byteversatz` beginnt bei 0. `bytelaenge` ist standardmäßig 65536, maximal 131072 Bytes.
`inhalt_base64` enthält nur den angefragten Bereich.
`naechster_byteversatz` setzt einen vollständigen lesbaren Byteabruf fort.
Große einzelne BLOBs werden inkrementell gelesen, nicht als Ganzes in SQL-Ergebnisse geladen.
Bei mehr als 500 überlappenden Chunks kann ein Abruf kürzer ausfallen; `abfrage_gekuerzt` zeigt dies an.

Das Werkzeug öffnet niemals gespeicherte Links, Dateipfade oder Netzwerkadressen.
Es entpackt keine komprimierten Inhalte und führt keine Dateien aus.
`Source`, `Source_id` und `Art` bleiben Rohwerte.
Eine Zuordnung zu Buchungen wird ohne belegte Typcodes nicht angenommen.
Unbekannte Kompression, fehlende oder mehrdeutige Chunkpositionen und Größenabweichungen bleiben erkennbar.
Die Bedeutung des gespeicherten Größenfelds ist nicht verifiziert.
Die Ausgabe sind rohe Speicherbytes, kein bestätigtes PDF und kein Dateiintegritätsnachweis.

## Offene Posten und Zahlungen

`offene_posten_auflisten`: `seite` aus `forderungen`, `verbindlichkeiten`, `alle`.
Standardmäßig `POSTEN.OffenFW <> 0`; `mit_ausgeglichenen` nimmt geschlossene Posten auf.
Entwürfe ausgeschlossen, historische null-Entwurfsflags gelten als Nichtentwurf.
Negative Gutschriften bleiben negativ. Rechnungen sind kein Zahlungs-/Umsatznachweis.

`offenen_posten_abrufen` benötigt `posten_id`; Ergebnis `posten`, `positionen`,
`zuordnungen`, `zuordnungssummen`, `abgleich`. Positionen und Zahlungen unabhängig mit
`positionen_anzahl`/`positionen_versatz` bzw. `zahlungen_anzahl`/`zahlungen_versatz` lesen.
Gesamtabgleich immer über vollständige Historie, Abweichungen nicht korrigieren.

`zahlungen_auflisten` liefert jeden Zahlungskopf genau einmal, auch ohne Zuordnungen.
Optional filtern `adresse_id`, `datum_von` und `datum_bis`.
`suche` sucht wörtlich in `ReNr`, `BuText` und `Referenz`.
Nullverrechnungen und negative Zahlungen bleiben enthalten. `Art` bleibt unverändert.
FW/SW und verschiedene Währungen nicht addieren. Die lokale `_rowid` führt
zu `zahlung_abrufen` mit derselben `firma_id`.

`zahlung_abrufen` benötigt `zahlung_id`. Kopf gilt für die gesamte Zahlung,
Zuordnungen für OP-Positionen. Nur gespeicherte Zahlungs-/Positions-/Posten-IDs,
stets firmengebunden. Keine geratenen Betrags-/Belegnummernpaare. Gemeinsame
Nullverrechnungen beweisen weder eindeutige Rechnung-Gutschrift-Paare noch
Banküberweisungen. Negative Zahlungen, Erstattungen und Minderungen bleiben erhalten.

Stichtagswerkzeuge verlangen `stichtag`. Belegbrutto abzüglich datierter
Zahlungen/Minderungen bis zu diesem Tag; zukünftige Belege/Zahlungen und Entwürfe
ausgeschlossen. Fehlende Geldwerte, undatierte oder nicht abgeglichene Historien
ergeben `offen_zum_stichtag_FW/SW = null`; `teilberechnet_offen_FW/SW` zeigt nur
die unvollständige Rechnung. Unbekannte Salden zählen, nicht als Null summieren.
Vollständige Filtersummen bleiben seitenunabhängig.

Fälligkeit: gespeichertes `Datum + TageNetto` in Kalendertagen, keine heutigen
Fristvorgaben, Rechts-/Feiertagsanpassung oder Skontoannahme. Altersklassen:
nicht fällig, 1–30/31–60/61–90/über 90 Tage, Guthaben, ausgeglichene und unbekannte Werte.
Vor-Beleg-Zahlungen werden gekennzeichnet. Heutige Mahnflags nicht zurückdatieren;
datierte Hinweise sind kein vollständiger früherer Mahnzustand.
Keine historischen Belegversionen oder Löschprotokolle.

## Steuern und weitere Stammdaten

`steuerjournal_anzeigen` bewahrt Gegenpositionen, Statuswerte, nicht fällige Steuer,
IST-Nachweise und getrennte FW-/SW-Währungen. Nicht jede Zeile als Steuer summieren.

`umsatzsteuer_voranmeldung_anzeigen`: `firma_id`, `jahr`, genau `monat` oder `quartal`.
Gespeicherte UVA: passende Firma/Zeiträume, `Verfahren=ElsterAnmeldung`,
`DatenArt=Umsatzsteuer-Voranmeldung`. Gepackte `ELSTERMELDUNG.Kennzahlen` sind
kein Jahreserklärungs-XML. Bekannte Beträge aus Hundertsteln, Flags/unbekannte Codes roh.
Bei mehreren Fassungen `status=mehrdeutig`, mit `meldung_id` wählen.
`status=gespeichert` beweist keine Abgabe oder aktuelle rechtliche Richtigkeit.

Ohne gespeicherte Meldung ausschließlich `status=teilrekonstruktion` belegbarer
fälliger Steuerkonten-/Bemessungswerte. Eröffnungen und nicht fällige IST-Steuer
ausgeschlossen. Fehlende/mehrdeutige Zuordnungen, Bemessungen und Währungen melden.
Keine erfundene Kz83-Zahllast, Abgaberundung, Umsatz-mal-Steuersatz-Schätzung oder
ersatzweise Jahreserklärung. Nicht zugeordnete neuere/XML-Meldungen nicht unterstützen.

Kostenstellen, Zahlungsbedingungen und Währungen auch bei Sperren sichtbar.
Notizen/Vorlagen nicht kürzen oder ausfüllen. Unbestätigte Skontoskalierung,
Zahlungsarten, Kursrichtung/Faktorregeln bleiben offen; keine historischen Frist-/
Kursversionen und keine abgeleiteten Währungsumrechnungen.

## Anlagen und Abschreibungen

`anlagen_auflisten` durchsucht ID, Inventarnummer, Bezeichnung, Standort, Seriennummer,
Kostenstellenwert und Zusatzangaben wörtlich. Auch abgegangene/vollständig
abgeschriebene Anlagen. `anlage_abrufen` benötigt `anlage_id`, liefert `anlage`
und seitenweise `bewegungen`. `abschreibungsplan_anzeigen` filtert optional Anlage,
`datum_von`/`datum_bis` und `nur_gebuchte`.

Zugänge, AfA, Sonder-AfA, Zuschreibungen und Abgänge stammen aus gespeicherten
Bewegungen. Anlagen-ID und Firma verbinden. Numerischer Text `BuchwertNeu` wird
als Geld umgerechnet. Nutzungs-/Restdauer sind Monate, Kontenfelder Kontonummern.
Kein Währungscode in beiden Tabellen; keine Währung für beliebige Datensätze erfinden.

Auch zukünftige, ungebuchte und historische Zeilen bleiben standardmäßig erhalten.
`nur_gebuchte=true` wählt `Gebucht=1`, keinen unabhängig bestätigten Journalposten.
Letzter künftiger Planwert ist nicht heutiger Buchwert. Keine neue AfA-Berechnung,
Steuerbeurteilung, vollständige Methodencodeliste oder historische Stammdatenwiedergabe.

## Schreibschutz und fester Datenstand

Direkter Dateizugriff, kein automatisches Kopieren/Aktualisieren. Geschlossener,
ruhender, konsistent abgeschlossener Datenbankstand erforderlich, **keine aktive
MonKey-Datei**. Einfaches Kopieren einer laufend veränderten Hauptdatei reicht nicht.

- Nichtleere `-wal`-/`-journal`-Dateien ablehnen; keine Dekodierung/Wiederherstellung.
- Gerätekennung, Inode, Größe und Änderungs-/Statuszeit vor/nach jeder Abfrage prüfen.
  Bei Änderung neuer konsistenter Stand und Serverneustart; keine atomare Live-Datei.
- SQLite nur lesend mit `immutable=1`, `query_only=ON`. VFS lehnt Schreiben/Kürzen ab.
  Autorisierung sperrt Änderungen, weitere Datenbanken, Transaktionen, Erweiterungen
  und externe Dateifunktionen. Eine SELECT-/WITH-Anweisung, nur lesende Schemaeinsicht.
- Höchstens 500 Zeilen, ungefähr eine Million Ergebniszeichen, eine Million Bytes
  je SQLite-Wert, 100.000 SQL-Zeichen, fünf Sekunden SQLite-Ausführung; letztere
  keine harte Gesamtlaufzeit-/Dateisystemgarantie. Temporäre SQLite-Daten im Speicher.
- Schlüssel/entschlüsselte Seiten im Prozessspeicher; Betriebssystem-Auslagerung
  und Absturzabbilder außerhalb der Serverkontrolle. MCP-Hinweise allein schützen nicht.
- Datenbank, Schlüssel und private Abfrageergebnisse nicht versionieren.
  Nur vertrauenswürdige MCP-Clients/Modellanbieter für Buchhaltungsdaten verwenden.

## Verschlüsselungsprofil

Untersuchte Programmversion 23.2.4,
SHA-256 `5fa4249c6d7635546139f51bf5f3e7c20b9a230fcc0fbf27e7d8c8d0e90ba9b5`.
Statische Symbol-/arm64-Disassemblierungsdaten, kein behaupteter Decompiler-Quelltext.
`mOpenDatabase.ScramblingKey` baut aus 29 Konstanten über 44 Arraypositionen eine
permutierte Base64-Zeichenkette. 32 rekonstruierte Schlüsselbytes, davon erste 16
für SEE AES-128. Kein wörtlicher Schlüssel im Quelltext.

Nur beobachtetes SEE-AES-128-OFB-Profil ohne reservierte Nonce-Bytes:
IV aus 1-basierter Seitennummer als 16 Byte Little-Endian; Klartext-Headerbytes
16–23 erhalten. Andere Verfahren, Nonce-Profile, individuelle Schlüssel und künftige
Programmversionen nicht zugesichert. OFB ohne Authentifizierung erkennt nicht jede
bösartige Änderung; die Standardschlüsselableitung ist keine Sicherheitsgarantie.

Referenzen: [SQLite SEE](https://www.sqlite.org/see/doc/trunk/www/readme.wiki),
[Xojo EncryptionKey](https://docs.xojo.com/api/databases/sqlitedatabase.html#sqlitedatabase-encryptionkey),
[Herstellerhinweis](https://prosaldo.zendesk.com/hc/de/community/posts/207908146--sdb-Datei-als-sqlite-Datenbank-%C3%B6ffnen).

## Prüfungen

```sh
uv run python -m unittest discover -s tests -v
```

Nur temporäre synthetische verschlüsselte Testdatenbanken, keine Ursprungsdatenbank
oder privaten Schlüssel. Abgedeckt: Entschlüsselung, Schreib-/Journalabwehr,
Firmenisolation, Einheiten, Filter, Seitennavigation, Berichte, Stornos,
Zahlungsverknüpfungen, unvollständige Historien und gespeicherte Anlagenpläne.
Die deutsche Darstellung prüft zusätzlich unveränderte gespeicherte Werte,
freie SQL-Aliase, Binärwerte und konsistente Status-/Geldspalten.

Die Tests prüfen auch Vorjahresabweichungen, Berichtsnachweise, Kontenabstimmung
und strukturierte Fehlercodes mit synthetischen Daten.
Ein neu gestarteter stdio-MCP wurde zusätzlich mit einem synthetischen verschlüsselten Datenstand geprüft.
Der Aufruf bestätigte Vorjahresabweichung, Ergebnisnachweis und strukturierten Firmenzugriffsfehler.
Die synthetische Datenbank blieb unverändert. Für diese Prüfungen wurde keine Ursprungsdatenbank geöffnet.
Quellpaket und Wheel wurden gebaut. Beide installierten CLI-Kommandos wurden mit `--hilfe` gestartet.

### GitHub Actions

Der Workflow `.github/workflows/ci.yml` startet bei Push, Pull Request oder manuell.
Die Tests laufen unter Linux (`ubuntu-latest`) mit Python 3.13 und 3.14.
Nach erfolgreichen Tests baut ein macOS-Job das Quellpaket und daraus das Wheel.
Dieser Job verwendet den ARM64-Runner `macos-latest`.
Er installiert das Wheel in einer eigenen Umgebung und prüft beide CLI-Einstiegspunkte mit `--hilfe`.
Die Pakete bleiben sieben Tage als CI-Artefakte verfügbar.
Der Workflow veröffentlicht keine Pakete auf PyPI.

## Veröffentlichung und lokale Dateien

Der Projektcode steht unter der MIT-Lizenz. Siehe [LICENSE](LICENSE).

Git ignoriert diese lokalen Dateien und Ordner:

- MCP-Konfiguration: `.omp/`
- Umgebungsdateien: `.env` und `.env.*`
- Schlüssel und Passwortdateien: `*.key`, `*.passwort`, `*.password`, `*.passwd`, `*.secret`
- Weitere Zugangsdaten: `passwort.txt`, `password.txt`, `credentials.json`
- Berichte: `berichte/` und `reports/`

Lege Berichte mit Geschäftsdaten in einem dieser beiden Berichtsordner ab.
Für andere Dateinamen und Ablageorte musst du eigene Ausschlussregeln ergänzen.
Die Regeln wirken nur auf Dateien, die Git noch nicht versioniert.

Das Quellpaket enthält nur diese Dateien:

- Projektcode und Python-Tests
- README und Lizenz
- Paketkonfiguration, Lockdatei, Ausschlussregeln und CI-Workflow

Die Dateiauswahl steht in `pyproject.toml`.

### Release erstellen

Setze die gewünschte stabile Version in `pyproject.toml` und aktualisiere `uv.lock` mit `uv lock`.
Committe diese Dateien zusammen mit den Änderungen.
Erstelle danach einen Tag `vX.Y.Z`, dessen Nummer genau der Paketversion entspricht.
Das Pushen dieses Tags startet `.github/workflows/release.yml`.
Der Workflow prüft die Version, führt die Tests aus und installiert das gebaute Wheel auf macOS.
Er veröffentlicht genau diese geprüften Pakete mit SHA-256-Prüfsummen als GitHub-Release.
Fehlgeschlagene Prüfungen verhindern die Veröffentlichung.
Tags ohne passende stabile Paketversion werden abgelehnt.
Der Workflow startet keine Veröffentlichung allein durch einen normalen Branch-Push.
