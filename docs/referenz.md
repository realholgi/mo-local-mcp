# MCP-Referenz

[Übersicht](../README.md)

## Sprache und Beispieldaten

Kommandos, Parameter, Beschreibungen, eigene Ausgabeschlüssel und Meldungen sind Deutsch.
Die früheren englischen MCP-Kommandos sind nicht mehr verfügbar.
Der Server weist unbekannte Parameter zurück. Er erklärt auch Parameter-Validierungsfehler auf Deutsch.

Folgende Bezeichner bleiben unverändert:

- technische MCP-/JSON-Schema-Bezeichner
- Originaldatenbankspalten
- selbst gewählte SQL-Aliase
- offizielle Connect-Feldnamen

Gespeicherte Namen und Belegtexte werden weder übersetzt noch durch erfundene Werte ersetzt.

Alle Beispielkennungen, Vorgänge und Beträge in dieser Dokumentation sind vollständig synthetisch.
Rufe zuerst `firmen_auflisten` auf und wähle eine Firma ausdrücklich aus.
Verwende Beispiel-IDs nicht ungeprüft. Private Berichte und echte Geschäftsvorgänge gehören weder in Beispiele noch in Testdaten.

## Fehler

Fehlgeschlagene Werkzeugaufrufe setzen `isError: true`.
`structuredContent.fehler` enthält einen stabilen `code` und die deutsche `meldung`.
Clients sollen den Code auswerten, nicht den Meldungstext.

| Code | Bedeutung |
| --- | --- |
| `UNBEKANNTES_KOMMANDO` | Das Kommando wird von diesem Prozess nicht angeboten. |
| `UNBEKANNTE_PARAMETER` | Mindestens ein Parametername ist unbekannt. |
| `UNGUELTIGE_PARAMETER` | Pflichtfelder, Datentypen oder Parameterwerte sind ungültig. |
| `ZUGRIFF_VERWEIGERT` | Die Firma ist für diesen Prozess nicht freigegeben. |
| `DATENSTAND_GEAENDERT` | Die Datenbankdatei oder ihr Journalzustand hat sich geändert. Ein neuer konsistenter Datenstand und ein Neustart sind erforderlich. |
| `ABFRAGEGRENZE` | Eine Ausführungs- oder Ausgabegrenze verhindert das Ergebnis. |
| `DATENBANKFEHLER` | Eine Datenbankabfrage oder fachliche Datenprüfung schlägt fehl. |
| `INTERNER_FEHLER` | Ein unerwarteter interner Fehler verhindert die Abfrage. |

## Gemeinsame Parameter und Ergebnisform

### Firmen und Kennungen

`firma_id` ist bei Fachabfragen zwingend. Kennungen sind lokale `_rowid`-Ganzzahlen.
Sie sind keine zugesicherten Connect-IDs. Jede Verknüpfung berücksichtigt die Firma.

[Sicherheit und wirksame Leserechte](einrichtung.md) beschreibt die Einrichtung.

### Seiten, Suche und Zeiträume

Listen verwenden `anzahl` und `versatz`. `naechster_versatz` verweist auf die nächste Seite.
Der Standard beträgt 100 Zeilen, das Maximum 500 Zeilen.

`suche` sucht wörtlich und wertet keine Platzhalter aus.
SQLite berücksichtigt Groß-/Kleinschreibung dabei nur im ASCII-Bereich.

`datum_von` und `datum_bis` sind ISO-Daten im Format `YYYY-MM-DD`.
Beide Grenzen sind eingeschlossen.
Bei Finanzberichten bezeichnet `jahr` den Beginn des gespeicherten Geschäftsjahres.

### Spalten, Geld und andere Werte

Tabellenförmige Ergebnisse enthalten `spalten`, `zeilen` und `gekuerzt`.
Originalspalten behalten ihre Namen. Eigene abgeleitete Spalten sind Deutsch.

Fachwerkzeuge liefern Geld als Dezimalzeichenketten in Währungseinheiten.
`geldbetraege` nennt die bereits durch 100 geteilten Felder. Rechne diese nicht erneut um.
Im synthetischen Rechenbeispiel ergibt `12345` den Wert `"123.45"`.
`sql_abfragen` liefert dagegen den Rohwert `12345`.

Mengen, Prozentsätze, Kurse, Kontonummern und IDs sind keine Geldfelder. Null bleibt null.
Halte FW/SW und unterschiedliche Währungen getrennt. Leite keine Wechselkurse her.
Fachlisten bewahren Preisnachkommastellen. Finanz-/Steuerberichte formatieren Geld zweistellig.

Große Ganzzahlen erscheinen verlustfrei als Zeichenketten.
Binärwerte verwenden den technischen Schlüssel `base64`.

## Kommandos nach Fachgebiet

### Datenquelle und Schema

| Kommando | Zweck |
| --- | --- |
| `datenbankinformationen` | Datenquelle, Verschlüsselung, Schreibschutz und Grenzen |
| `tabellen_auflisten` | Tabellen/Sichten mit originalem CREATE-SQL |
| `tabelle_beschreiben` | Spalten, Fremdschlüssel, Indizes und Fachbeschreibung |
| `sql_abfragen` | Gebundene SELECT-/WITH-Abfragen; nur mit `--mit-sql` |
| `fachschema_anzeigen` | Fachbegriffe, Einheiten, Wertelisten, Verknüpfungen und Grenzen |
| `datenstand_anzeigen` | Vorhandene Zeiträume und gespeicherte Buchungszeitpunkte |

### Firmen, Adressen und Stammdaten

| Kommando | Zweck |
| --- | --- |
| `firmen_auflisten` | Firmen mit lokalen Kennungen |
| `firma_abrufen` | Vollständiger Firmenstamm einschließlich Anschrift und Steuerangaben |
| `geschaeftsjahre_auflisten` | Zeiträume, Versteuerung, Sperren und Zähler |
| `steuersaetze_auflisten` | Steuerdefinitionen, Konten, UVA und Sperren |
| `kontenplan_anzeigen` | Konten einschließlich unbebuchter/gesperrter Konten und Vorgaben |
| `adressen_suchen` | Kunden-/Lieferantenadressen und Statusfilter |
| `adresse_abrufen` | Vollständige Firmenadresse einschließlich Status und Notizen |
| `artikel_auflisten` | Artikel und Leistungen mit Lagerkennzeichen und Stammpreisen |
| `projekte_auflisten` | Projekte, Zeiträume, Notizen und gespeicherter Status |
| `kostenstellen_auflisten` | Kostenstellen, Sperren und vollständige Notizen |
| `zahlungsbedingungen_auflisten` | Fristen, Vorlagen und unveränderte Skontowerte |
| `waehrungen_auflisten` | Währungen, Symbole sowie rohe Faktoren und Kurse |

### Belege, Buchungen und Zahlungen

| Kommando | Zweck |
| --- | --- |
| `verkaufsbelege_auflisten` | Belegarten, Datums-/Adressfilter und gespeicherte Summen |
| `verkaufsbeleg_abrufen` | Belegkopf und geordnete Positionen |
| `einkaufsbelege_auflisten` | Einkaufsbelege mit Belegart-, Datums-, Adress- und Textfilter |
| `einkaufsbeleg_abrufen` | Einkaufsbelegkopf und geordnete Positionen |
| `buchungen_auflisten` | Buchungen mit Datums-, Konto- und Textfilter |
| `buchung_abrufen` | Vollständiger Buchungskopf und seitenweise Journalzeilen |
| `offene_posten_auflisten` | Forderungen, Verbindlichkeiten und Gutschriften |
| `offenen_posten_abrufen` | OP-Kopf, Positionen, Zahlungshistorie und Abgleich |
| `zahlungen_auflisten` | Zahlungsköpfe mit Datums-, Adress- und Textfilter |
| `zahlung_abrufen` | Zahlung/Verrechnung mit Belegzuordnungen |
| `belege_suchen` | Gemeinsame Suche in fünf Belegbereichen mit Folgewerkzeugen |
| `belegverknuepfungen_anzeigen` | Unmittelbare gespeicherte Beziehungen zwischen Belegen, Buchungen und Zahlungen |
| `anhaenge_auflisten` | Gespeicherte Anhangsmetadaten ohne BLOB-Inhalt |
| `anhang_lesen` | Begrenzte rohe Anhangsbytes aus der Datenbank als Base64 |

### Berichte, Abstimmung und Steuern

| Kommando | Zweck |
| --- | --- |
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
| `datenqualitaet_pruefen` | Verknüpfungsfehler, Buchungsausgleich und Zahlungsabgleiche |
| `kostenstellen_auswerten` | Kostenstellenbeträge mit deduplizierten Gesamtwerten |
| `konten_monatlich_anzeigen` | Monatliche Hauptbuchbewegungen und getrennte Eröffnungen |
| `guv_monatlich_anzeigen` | Monats-GuV nach gespeicherter Gliederung |

### Anlagen

| Kommando | Zweck |
| --- | --- |
| `anlagen_auflisten` | Auch abgegangene und abgeschriebene Anlagen |
| `anlage_abrufen` | Anlagenstamm mit gespeicherten Bewegungen |
| `abschreibungsplan_anzeigen` | Gespeicherte Anlagen-/AfA-Bewegungen mit Filtern |

[Auswertungen](auswertungen.md) erklärt Berichte, OP-Salden, Steuern und Anlagen sowie deren Parameter und Grenzen.

## Parameter für Stammdaten

### Firmenstamm

`firma_abrufen` benötigt `firma_id`. Das Ergebnis `firma` enthält alle Originalspalten.
Dazu gehören unter anderem Anschrift, Steuerangaben und Kontenplan.
Geschäftsjahre liefert `geschaeftsjahre_auflisten`.

### Adressen und Rollen

`adressen_suchen` verwendet diese Filterwerte:

| Parameter | Werte |
| --- | --- |
| `rolle` | `alle`, `kunden`, `lieferanten` |
| `status` | `alle`, `aktiv`, `inaktiv`, `gesperrt` |

Ein Statusfilter erfordert eine bestimmte Rolle. Eine Adresse kann Kunde und Lieferant sein.

`adresse_abrufen` benötigt `firma_id` und `adresse_id`.
Das Ergebnis `adresse` enthält alle Originalspalten und beide Rollenlabels.
Auch inaktive, gesperrte und rollenlose Adressen sind abrufbar. Notizen bleiben vollständig erhalten.

### Artikel und Leistungen

`artikel_auflisten` filtert mit `artikelart`, `nur_lagerartikel` und `warengruppe`.
Artikelart 1 bezeichnet Artikel, 2 Leistungen. Weitere Codes bleiben roh.
Das Werkzeug vergleicht die Warengruppe exakt. Gesperrte Artikel bleiben sichtbar.

Geldfelder sind bereits umgerechnet. Mengen, Gewichte und Prozentsätze bleiben unverändert.
Das Werkzeug leitet weder eine Preiswährung noch aktuelle Lagerbestände ab.

### Projekte

`projekte_auflisten` liefert Projektstammdaten mit Zeitraum, Notizen und rohem Status.
Die Liste enthält keine berechneten Projektumsätze, Ergebnisse oder Arbeitszeiten.

## Parameter für Belege und Buchungen

### Verkaufsbelege

`verkaufsbelege_auflisten` durchsucht mit `suche` zusätzlich `AuftragsNr`, `BestellNr` und `Betreff`.

Synthetische Beispielparameter:

```json
{"firma_id": 101, "belegart": 4, "datum_von": "2028-01-01", "datum_bis": "2028-12-31"}
```

### Einkaufsbelege

`einkaufsbelege_auflisten` liest `BESTELLUNG`.
Es gelten die gleichen Datums-, Adress- und Entwurfsregeln wie für Verkaufsbelege.
Weitere Belegregeln stehen unter [Auswertungen](auswertungen.md).

`suche` durchsucht die Belegnummer, Lieferantenreferenz und den Betreff wörtlich.
`belegart` filtert gespeicherte Codes:

| Code | Belegart |
| --- | --- |
| 101 | Bestellanfrage |
| 102 | Bestellung |
| 103 | Wareneingang |
| 104 | Eingangsrechnung |
| 105 | Lieferantengutschrift |
| 106 | Rücksendung |
| 107 | Stornierung |

Unbekannte Codes bleiben unverändert sichtbar.

`einkaufsbeleg_abrufen` liefert `beleg` und `positionen`.
`positionen_anzahl` und `positionen_versatz` blättern nur die Positionen.
FW/SW bleiben getrennt. Text- und Alternativpositionen sind kein pauschal summierbarer Aufwand.

### Buchungslisten und Filter

`buchungen_auflisten` bietet zusätzlich `belegnummer`, `konto_soll`, `konto_haben` und `kostenstelle`.

- `belegnummer` sucht wörtlich in `BelegNr`.
- Soll-/Habenkonten wählen Journalzeilen mit einem Betrag ungleich null auf der jeweiligen Seite. Negative Stornos bleiben enthalten.
- `kostenstelle` vergleicht `Kostenstelle1` und `Kostenstelle2` exakt.

Mehrere Filter gelten gemeinsam für den Buchungskopf. Sie müssen nicht dieselbe Journalzeile treffen.
Der rohe Buchungsstatus bleibt unverändert.

### Einzelbuchungen und Journalzeilen

`buchung_abrufen` benötigt `firma_id` und `buchung_id`.
Das Ergebnis enthält `buchung` und `journalzeilen`.
Nur die Journalzeilen sind mit `journal_anzahl` und `journal_versatz` seitenweise abrufbar.
Der vollständige Kopf bleibt auf jeder Seite erhalten.

Die Journalreihenfolge ist `NummerLong`, `Position`, `_rowid`.
Vorzeichen, Storno, Steuerschlüssel, FW/SW und rohe Statuswerte bleiben erhalten.
Leite keine Buchungssummen aus Teilseiten ab.

Die Datumsfilter und historischen Salden von `offene_posten_auflisten` erklärt [Auswertungen](auswertungen.md).

## MCP-Ressourcen und Prompts

### Ressourcen

| URI | Inhalt |
| --- | --- |
| `monkey://fachschema` | Vollständiges dokumentiertes Fachschema mit Einheiten und Grenzen |
| `monkey://fachschema/{tabelle}` | Fachschema einer dokumentierten Tabelle |
| `monkey://zugriff` | Wirksame Leserechte dieses MCP-Prozesses |

Die Ressourcen enthalten keine Geschäftsvorgänge.

### Prompts

`jahresabschluss_pruefen` erwartet `firma_id` und `jahr` als Zeichenketten.
Der Prompt beschreibt die Prüfung mit Datenstand, Qualität und gespeicherter Berichtsgliederung.

`forderungen_erklaeren` erwartet `firma_id` und `stichtag`.
Er beschreibt die Auswertung historischer OP-Salden mit belegten Zahlungsbeziehungen.

Beide Prompts prüfen die Firmenfreigabe. Sie führen selbst keine Datenabfragen aus.
Im eingeschränkten Stammdatenmodus ist der Forderungsprompt nicht verfügbar.
Kein Prompt erlaubt Schreiben, Mahnversand oder Live-Connect.
Die [Einrichtung](einrichtung.md) erklärt die Sicherheits- und Leserechteeinstellungen.
