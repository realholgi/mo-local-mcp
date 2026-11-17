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

### Schlüssel

Das Kommando `mo-schluessel-wiederherstellen` ist auch im Wheel enthalten.

Die Profiltabelle `PROFILE` in `mo_local_mcp/schluessel.py` enthält die erfassten Programmversionen.
Aktuell ist MonKey Office 2026, Programmversion 23.2.4, eingetragen.
Der SHA-256 der Programmdatei bestimmt das Profil. Unbekannte Dateien werden abgelehnt.
Ohne `--programmdatei` sucht das Kommando vom letzten Profil rückwärts nach einer vorhandenen Installation.
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

#### Neue Programmversionen

Für eine neue Version mit gleichem Ableitungsverfahren ergänze einen Eintrag am Ende von `PROFILE`.
Bestehende Profile bleiben erhalten. Die Reihenfolge der Einträge geht von alt nach neu.

| Feld | Bedeutung |
|---|---|
| Tabellenschlüssel | SHA-256 der genauen Programmdatei |
| `version` | Versionsbezeichnung für Fehlermeldungen |
| `programmdatei` | Standardpfad zur installierten Programmdatei |
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
| `sql_abfragen` | Gebundene SELECT-/WITH-Abfragen |
| `fachschema_anzeigen` | Fachbegriffe, Einheiten, Wertelisten, Verknüpfungen und Grenzen |
| `firmen_auflisten` | Firmen mit lokalen Kennungen |
| `geschaeftsjahre_auflisten` | Zeiträume, Versteuerung, Sperren und Zähler |
| `steuersaetze_auflisten` | Steuerdefinitionen, Konten, UVA und Sperren |
| `kontenplan_anzeigen` | Konten einschließlich unbebuchter/gesperrter Konten und Vorgaben |
| `adressen_suchen` | Kunden-/Lieferantenadressen und Statusfilter |
| `verkaufsbelege_auflisten` | Belegarten, Datums-/Adressfilter und gespeicherte Summen |
| `verkaufsbeleg_abrufen` | Belegkopf und geordnete Positionen |
| `buchungen_auflisten` | Buchungen mit Datums-, Konto- und Textfilter |
| `offene_posten_auflisten` | Forderungen, Verbindlichkeiten und Gutschriften |
| `offenen_posten_abrufen` | OP-Kopf, Positionen, Zahlungshistorie und Abgleich |
| `zahlung_abrufen` | Zahlung/Verrechnung mit Belegzuordnungen |
| `bilanz_und_guv_anzeigen` | Gliederungsbasierte Berichte mit Konten und Vorjahr |
| `kontoauszug_anzeigen` | Eröffnung, Umsätze, laufende Salden und Steuerschlüssel |
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

## Fachschema und Quellen

23 Tabellen sind fachlich beschrieben:
`FIRMA`, `ADRESSE`, `AUFTRAG`, `AUFTRAGSPOSITION`, `BUCHUNG`, `JOURNAL`, `POSTEN`,
`POSTENPOSITION`, `WAEHRUNG`, `KONTO`, `STEUERSATZ`, `WIRTSCHAFTSJAHR`,
`KONTOSTRUKTUR`, `STRUKTURPOSITION`, `ZAHLUNG`, `ZAHLUNGSPOSITION`, `KOSTENSTELLE`,
`ZAHLUNGSBEDINGUNG`, `ELSTERMELDUNG`, `ELSTERMELDUNG_NT`, `STEUERERKLAERUNG`,
`ANLAGE`, `ANLAGENPOSITION`. Andere Tabellen bleiben technisch lesbar.

Begriffsquelle: JSON-API-Hilfe **23.2.0 / 07.07.26** aus dem
[Connect-Download](https://www.monkey-office.de/download/current/mac/MonKey_Office_Connect.dmg),
Datei `Entwicklerdokumente/Monkey Office Connect JSON-API Hilfe.html`,
SHA-256 `de3836cb7a582ac84118b121088496f663829de9b2c3f030a57a20fe8d706406`.
Sie beschreibt Fachstrukturen, nicht interne Tabellen. Lokale Zuordnungen sind aus
Schema/Datenbeziehungen abgeleitet; App-/PDF-Belege gesondert gekennzeichnet.
Kein Vergleich mit laufendem Connect. Das Fachschema meldet fehlende zugeordnete/
dokumentierte Spalten, Herkunft und Grenzen. Unbekannte Codes nicht umdeuten.

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
Mehrdeutige/unvollständige Zuordnungen, Kontenlisten/Hierarchien, unausgeglichene
Daten und abweichende Vergleichswährungen sind Fehler. Keine eingereichten Abschlüsse,
steuerlich bereinigten Gewinne oder historischen Gliederungsversionen.

`kontoauszug_anzeigen` benötigt `firma_id`, `jahr`, `konto`. Ergebnis trennt
`eroeffnung`, `umsaetze`, `endsaldo`, `buchungszeilen`. Eröffnungen (`BUCHUNG.Art=2`)
bilden den Anfangssaldo, nicht Umsatz. Stornierte Originale und vorzeichenbehaftete
Gegenbuchungen bleiben erhalten. Reihenfolge: Datum, Belegnummer, Journalnummer, Position.
Summen und laufende Salden gelten für das volle Jahr unabhängig von der Seite.
Negativer Saldo bedeutet Haben, positiver Soll. `steuerschluessel` übernimmt
`JOURNAL.Steuersatz`, auch `-`, Leertext und null. Kein Bankauszug oder Kassennachweis.

`kontenplan_anzeigen` liefert dagegen Stammdaten mit vollständigen Notizen,
DATEV-/Währungs-/Sperrfeldern und datierten Steuerzuordnungen. `konto_von`/`konto_bis`
sind inklusive. `Bezeichnung` ersetzt `#P#`, die Vorlage bleibt erhalten.
Je Vorgabefeld jüngster nichtleerer Wert, bei gleichem Datum erste Alternative.
Vorgaben ersetzen keine gebuchten Steuerschlüssel. Steuerprozente sind kein Geld;
fehlende Werte bleiben null. Geschäftsjahres-OP-Zähler zählen auch ausgeglichene
Belege, Gutschriften und Entwürfe, nicht nur unbezahlte Rechnungen.

## Offene Posten und Zahlungen

`offene_posten_auflisten`: `seite` aus `forderungen`, `verbindlichkeiten`, `alle`.
Standardmäßig `POSTEN.OffenFW <> 0`; `mit_ausgeglichenen` nimmt geschlossene Posten auf.
Entwürfe ausgeschlossen, historische null-Entwurfsflags gelten als Nichtentwurf.
Negative Gutschriften bleiben negativ. Rechnungen sind kein Zahlungs-/Umsatznachweis.

`offenen_posten_abrufen` benötigt `posten_id`; Ergebnis `posten`, `positionen`,
`zuordnungen`, `zuordnungssummen`, `abgleich`. Positionen und Zahlungen unabhängig mit
`positionen_anzahl`/`positionen_versatz` bzw. `zahlungen_anzahl`/`zahlungen_versatz` lesen.
Gesamtabgleich immer über vollständige Historie, Abweichungen nicht korrigieren.

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

## Lesender Connect-kompatibler HTTP-Zugang

Zusätzlich zum bestehenden MCP bietet `mo-local-connect` den Endpunkt
`POST http://127.0.0.1:8084/monkeyOfficeConnectJSON`. Andere MCP-Server können
ihn statt eines laufenden Connect-Servers ansprechen. Er verwendet denselben
schreibgeschützten Dateileser, keinen cubeSQL-Server und keine Live-Datenbank.
Der vorhandene stdio-MCP bleibt unverändert.

### Start und Anmeldung

Eine private UTF-8-Datei mit einem selbst gewählten HTTP-Passwort anlegen,
Dateirechte `600` setzen und den Adapter starten:

```bash
uv run mo-local-connect \
  --datenbank "/Pfad/zum/ruhenden-datenstand.sdb" \
  --schluesseldatei "$HOME/Library/Application Support/mo-local-mcp/database.key" \
  --benutzer "lokaler-leser" \
  --passwortdatei "$HOME/Library/Application Support/mo-local-mcp/connect.passwort"
```

Alternativ Benutzer und Passwort über `MO_CONNECT_BENUTZER` und
`MO_CONNECT_PASSWORT` bereitstellen; das Passwort wird nicht als
Kommandozeilenargument angenommen. `--port` ändert den Standardport `8084`.
Benutzer und Passwort sind unabhängig von MonKey-Benutzern und dem
Datenbankschlüssel.

Jeder Aufruf benötigt HTTP Basic Auth und `Content-Type: application/json`.
Mit `{"firmaList":""}` die verfügbaren Firmen abfragen. Bei allen anderen
Aufrufen die zurückgegebene `Firma_ID` ausdrücklich als Header `mbl-ident`
senden. Antworten verwenden `<Methode>Response.ReturnData` und
`ReturnStatus.Statuscode`; Fehler sind niemals erfolgreiche leere Listen.

Der Server bindet ausschließlich an `127.0.0.1`. Andere Rechner und übliche
Docker-Netzwerke erreichen ihn nicht direkt. Browserzugriffe mit `Origin`
werden abgelehnt; es gibt keine CORS-Freigabe. Keine Zugangsdaten, URLs oder
Nutzdaten werden in HTTP-Zugriffsprotokolle geschrieben.

### Untersuchte MCP-Clients und abgedeckte Aufrufe

Die Implementierung orientiert sich an den tatsächlich gesendeten Payloads aus
[kustus/MO-Connect-MCP](https://github.com/kustus/MO-Connect-MCP/blob/main/index.js)
und
[UhlhornHH/monkey-office-mcp](https://github.com/UhlhornHH/monkey-office-mcp/blob/main/monkey_office_mcp_server.py),
recherchiert am 17.11.2026. Für die Antwortstrukturen wurde ergänzend die
[Connect-Referenz 22.1.1](https://github.com/tkaufmann/monkeyoffice-api-docs/blob/main/docs/v22.1.1/llms.txt)
herangezogen. Die vorhandenen lokalen Fachzuordnungen beruhen weiterhin auf der
oben genannten Dokumentation 23.2.0 und dem lokalen Schema.

| Bereich | Aufrufe |
|---|---|
| Firmen | `firmaList`, `firmaGet` |
| Buchungen | `buchungList`, `buchungGet`, `buchungFilterTemplate`, `buchungTemplate` |
| Adressen | `adresseList`, `adresseGet` |
| Steuern | `steuersatzList` |
| Belege | `verkaufbelegList`, `verkaufbelegGet`, `einkaufbelegList` |
| Offene Posten | `offenePostenListDebitoren`, `offenePostenListKreditoren`, `offenePostenGet` |
| Weitere Stammdaten | `artikelList`, `projektList` |
| Lokale Client-Erweiterungen | `offenePostenList`, `kostenstellenList`, `buchungKontoList`, `debitorList`, `kreditorList` |

Für kustus `MO_URL` auf den lokalen Endpunkt setzen; `MO_USER` und `MO_PASS`
müssen der Adapter-Anmeldung entsprechen. `MO_FIRMA_KEY` ist die lokale
`Firma_ID` aus `firmaList`, nicht eine früher verwendete Connect-Kennung.
Bei Uhlhorn entsprechend `MONKEY_API_URL`, `MONKEY_API_USER`,
`MONKEY_API_PASS` und `MONKEY_FIRMA_NAME` konfigurieren. Letzteres muss exakt
der `Bezeichnung` aus `firmaList` entsprechen.

Die Client-Erweiterungen sind keine Zusage, dass diese Methodennamen beim
Hersteller existieren. Kostenstellen, Konten sowie Debitoren-/Kreditorenlisten
kennzeichnen ihre abweichende Bedeutung mit `LokaleLeseerweiterung` und `Basis`.
`offenePostenList` vereinigt die beiden OP-Seiten im dokumentierten
`OffenePostenListItem`-Format.

### Bewusste Kompatibilitätsgrenzen

- Kein vollständiger Connect-Ersatz und kein Vergleich mit laufendem Connect.
  Geprüft sind die lokalen Verträge und ausgewählte originale
  HTTP-/Auswertefunktionen beider Clients, nicht deren vollständiger MCP-Betrieb.
- Alle IDs sind lokale Ersatz-IDs als Zeichenketten. Alte Connect-IDs und
  `VersionKey` werden weder übernommen noch erfunden. Nur belegte Felder werden
  abgebildet; fehlende Felder sind keine bestätigten leeren Werte.
- Ohne Datumsfilter wird der gesamte Datenstand betrachtet, nicht automatisch
  das aktive Geschäftsjahr. Datumsgrenzen sind einschließlich.
- `FestschreibStatus=4` funktioniert; `1` und `2` werden abgelehnt, weil die lokale
  Statuszuordnung nicht verifiziert ist. `FestschreibStatus` im Buchungsdetail
  ist `null`; `LokalStatus` bewahrt den rohen lokalen Wert.
- Buchungsjournale erhalten gespeicherte Steuer-Schlüsselzeichenketten statt
  einer erfundenen numerischen Steuer-ID. `LokalStorno` und
  `LokalOSSProzent` sind lokale Zusatzfelder. Nicht belegte OSS-Steuersatz- und
  Attachment-Zuordnungen werden nicht vorgetäuscht.
- Beleg-Zahlungsstatus wird nur über die firmengebundene gespeicherte
  OP-Verknüpfung bestimmt. Verwaiste Verknüpfungen verhindern die Auswertung
  ausdrücklich. Rechnungsart allein beweist keine offene Zahlung.
- `debitorList`/`kreditorList` summieren aktuell gespeicherte OP-Restbeträge nach
  Adresse und Währung. Datumsfilter begrenzen das Belegdatum, nicht einen
  historischen Zahlungsstand. Gutschriften behalten ihr Vorzeichen;
  FW und SW bleiben getrennt.
- Nicht benötigte offizielle Filter, etwa OP-Filter `OpDatum`, `BetragVon`,
  `BetragBis` und `Zahlungsart`, werden ausdrücklich abgelehnt. Unbekannte
  Parameter werden nicht stillschweigend ignoriert.
- Maximal 500 Ergebniszeilen je Abfrage, ungefähr eine Million Ausgabezeichen
  und 100.000 Anfragebytes. Bei Überschreitung erfolgt ein Fehler statt einer
  unmarkiert gekürzten Liste; Filter enger setzen. Keine automatische Pagination.
- Schreibende und ausführende Aufrufe wie `buchungAdd`, Anhänge hinzufügen,
  Ändern, Löschen, Weiterleiten und Drucken sind gesperrt. Eine Buchungsvorlage
  erlaubt keine anschließende Buchung.

Die unveränderte Originaldatenbank bleibt ausschließlich lesend geöffnet.
Auch der HTTP-Zugang erfordert einen geschlossenen, ruhenden und konsistenten
Datenstand gemäß den obigen Schutzregeln.

### Abgrenzung zum Herstellerprodukt

Laut [Hersteller](https://www.monkey-office.de/products/officeconnect/index.php)
benötigt reguläres Connect HTTP(S)/JSON-Zugriff auf eine MonKey-Datenbank auf
cubeSQL, eine passende Hauptversion und eine persönliche Lizenznummer;
die Connect-Registrierung ist kostenlos. Das ist eine separate Anbindung.
Hier wurde das Herstellerprodukt weder installiert noch aktiviert.

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

Die Sprachumstellung wurde über einen neu gestarteten stdio-MCP mit allen
28 Kommandos einschließlich deutscher Parameter, Fehlerantworten, Fachschema,
Status-/Geldmetadaten und unverändertem Originaldateninhalt geprüft.
Prüfsumme und Dateimetadaten der Ursprungsdatenbank blieben unverändert;
es wurden keine WAL-, Journal- oder SHM-Dateien angelegt.

### GitHub Actions

Der Workflow `.github/workflows/ci.yml` startet bei Push, Pull Request oder manuell.
Er führt die Tests nur auf macOS mit Python 3.13 und 3.14 aus.
Nach erfolgreichen Tests baut er das Quellpaket und daraus das Wheel.
Er installiert das Wheel in einer eigenen Umgebung und prüft alle drei CLI-Einstiegspunkte mit `--hilfe`.
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
