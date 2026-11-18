# Auswertungen

[Übersicht](../README.md)

Startoptionen und Leserechte stehen in [Einrichtung](einrichtung.md).
Allgemeine MCP-Formate stehen in der [Referenz](referenz.md).

## Datenstand

`datenstand_anzeigen` benötigt `firma_id`.
Es zeigt die Dateiänderungszeit sowie Anzahl und Belegzeiträume je Bereich.
Erfassungs- und Verbuchungszeitpunkte stammen aus gespeicherten Buchungsfeldern und haben unterschiedliche Bedeutungen.

Die Dateiänderungszeit bestätigt keinen Export- oder Sicherungszeitpunkt.
Die jüngste Buchung und vorhandene Geschäftsjahre belegen weder Vollständigkeit noch Aktualität.
Es gibt keine Live-Abfrage und keine automatische Aktualisierung.

## Bilanz und GuV

### Jahresbericht

`bilanz_und_guv_anzeigen` liefert `bilanz.aktiva`, `bilanz.passiva`, `guv`, die Hierarchie und eine Kontenaufschlüsselung.
Optional sind `gliederung_id` und `mit_vorjahr`.

Die gespeicherte `STRUKTURPOSITION`-Hierarchie, Kontenlisten und `VzWechsel` bestimmen Zuordnung und Vorzeichen.
Die B-Position übernimmt das GuV-Ergebnis.
**Elternsummen enthalten Unterpositionen und direkte Konten. Nicht alle Zeilen addieren.**

Für die Zuordnung gelten diese Regeln:

- Nur Konten, die ausdrücklich auf beiden Bilanzseiten stehen, wechseln nach Saldenvorzeichen.
- Steuer-Sollsalden können Passivpositionen mindern.
- Negatives Eigenkapital bleibt an der gespeicherten Stelle.
- Persönliche Konten mit positivem `SammelKonto` zählen nicht doppelt.
- Neutrale Vortragskonten werden nur bei gemeinsamer Nullsumme ausgeschlossen.

Der Bericht berücksichtigt alle Perioden und Statuswerte sowie gebuchte Eröffnungen des Geschäftsjahres.
Er übernimmt das Vorjahr nicht doppelt.
Das Vorjahr wird separat mit der heutigen Gliederung berechnet. Ein fehlendes Vorjahr ist null.

Mehrdeutige oder unvollständige Zuordnungen, Kontenlisten und Hierarchien sowie unausgeglichene Daten führen zu Fehlern.
Der Bericht liefert keine eingereichten Abschlüsse, steuerlich bereinigten Gewinne oder historischen Gliederungsversionen.

### Vorjahresvergleich

`vorjahresvergleich` nennt die Vergleichbarkeit von Währung und Zeitraum.
Berichtspositionen, Konten und Summen enthalten `abweichung_absolut` und `abweichung_prozent`.

Die absolute Abweichung ist der aktuelle Betrag minus Vorjahresbetrag.
Die Prozentabweichung bezieht diese Differenz auf den absoluten Vorjahresbetrag.

- Bei zwei Nullbeträgen ist die Prozentabweichung null.
- Bei Vorjahresbetrag null und aktuellem Betrag ungleich null bleibt sie `null`.
- Ohne vergleichbares Vorjahr bleiben beide Abweichungen `null`. Der Vergleich nennt den Grund.

Unterschiedliche Währungen werden nicht umgerechnet.
Für den Zeitraumvergleich werden Beginn und Ende des Vorjahres um ein Kalenderjahr verschoben.
Der 29. Februar wird dabei zum 28. Februar.
Beide Grenzen müssen dem aktuellen Geschäftsjahr entsprechen.

### Nachweis einer Berichtsposition

`berichtsnachweis_anzeigen` benötigt `firma_id`, `jahr`, `gliederung_id` und `position_id`.
`position_id` bezeichnet die gespeicherte `ItemId` aus der Berichtsgliederung.
Das Ergebnis zeigt beteiligte Konten, Vorzeichenfaktoren und Beiträge.
Unterpositionen und Ergebnisübernahme folgen der Bilanz-/GuV-Berechnung.

`buchungszeilen` enthält die beitragenden Journalzeilen mit `buchung_id`.
Mit dieser ID kann `buchung_abrufen` die Buchung lesen.
Optional begrenzt `konto` die Beiträge auf ein effektives Hauptbuchkonto.
Die Seiteneinteilung verändert die Gesamtsumme nicht.

### Monatliche GuV

`guv_monatlich_anzeigen` benötigt `firma_id` und `jahr`.
Bei mehreren gespeicherten Gliederungen ist `gliederung_id` erforderlich.
Der Bericht verwendet die gespeicherte GuV-Hierarchie und ihre Vorzeichenwechsel.
Er zeigt direkte Beträge, Positionssummen und Monatsgewinn.

Eltern- und Unterpositionen dürfen nicht nochmals addiert werden.
Eröffnungen sind ausgeschlossen und separat ausgewiesen.
Fehlende oder mehrdeutige Erfolgskontenzuordnungen führen zu Fehlern.
Es gibt keinen zusätzlichen monatlichen Bilanzausgleich.

## Konten und Salden

### Kontoauszug

`kontoauszug_anzeigen` benötigt `firma_id`, `jahr` und `konto`.
Das Ergebnis trennt `eroeffnung`, `umsaetze`, `endsaldo` und `buchungszeilen`.
Eröffnungen (`BUCHUNG.Art=2`) bilden den Anfangssaldo und zählen nicht als Umsatz.
Stornierte Originale und vorzeichenbehaftete Gegenbuchungen bleiben erhalten.

Die Reihenfolge ist Datum, Belegnummer, Journalnummer, Position.
Summen und laufende Salden gelten für das volle Jahr, unabhängig von der Seite.
Ein negativer Saldo bedeutet Haben, ein positiver Soll.
`steuerschluessel` übernimmt `JOURNAL.Steuersatz`, auch `-`, Leertext und null.
Der Bericht ist kein Bankauszug oder Kassennachweis.

### Summen und Salden

`summen_und_salden_anzeigen` benötigt `firma_id` und `jahr`.
`konto_von`/`konto_bis` begrenzen die effektiven Hauptbuchkonten einschließlich.
Personenbuchungen zählen einmal im gespeicherten positiven `SammelKonto`, sonst im `Konto`.
Eröffnungen (`BUCHUNG.Art=2`) bleiben von Umsätzen getrennt.

Vortragskonten, Konten mit Aktivität und Nullsaldo sowie vorzeichenbehaftete Stornos bleiben enthalten.
Es gibt keinen Statusfilter.
Das Ergebnis enthält `konten`, `summen` und `anzahl_konten`.
Summen gelten für den vollständigen Kontenfilter vor `anzahl`/`versatz`, auch bei einer leeren Seite hinter dem Ergebnis.

Alle Beträge verwenden die SW-Währung des gespeicherten Geschäftsjahres.
`name` bleibt die gespeicherte Namensvorlage, ohne Platzhalterauflösung.
Die Liste benötigt keine Abschlussgliederung.
Ein Kontenfilter muss nicht ausgeglichen sein.

### Monatliche Kontenwerte

`konten_monatlich_anzeigen` benötigt `firma_id` und `jahr`.
Optional begrenzen `konto_von`/`konto_bis` die effektiven Hauptbuchkonten.
Der Bericht zeigt Kalendermonate innerhalb des gespeicherten Geschäftsjahres.
Ein abweichendes Geschäftsjahr muss nicht im Januar beginnen.

Positive Sammelkonten ersetzen Personenkonten genau einmal.
Eröffnungen bleiben von Bewegungen getrennt.
Endsalden kumulieren nur gespeicherte Werte ab Jahresbeginn.
Ein fehlender Anfangsvortrag wird nicht ergänzt.

`anzahl`/`versatz` blättern Konten, nicht deren Monate.
Die monatlichen `gesamtwerte` betreffen den vollständigen Kontenfilter.

### Debitoren- und Kreditorensalden

`debitoren_salden_anzeigen` und `kreditoren_salden_anzeigen` wählen Kunden- bzw. Lieferantenkonten aus den gespeicherten Adresszuordnungen.
Sie summieren Journal-Soll und -Haben im einschließlich gesetzten Datumsbereich.
Der Saldo ist Soll minus Haben.
Eröffnungen, alle Buchungsstatus und negative Stornos zählen mit.
Die Beträge sind weder reine Umsätze noch historische OP-Salden.

Konten mit mehreren Adressen zählen einmal.
Ein `adresse_id`-Filter wählt das gesamte zugeordnete Konto. Er teilt dessen Saldo nicht auf die Adresse auf.
Fehlende Kontozuordnungen liefern keine erfundenen Nullsalden.

FW-/SW-Währung stammen aus Buchung und Geschäftsjahr.
Unterschiedliche Währungspaare bleiben getrennt, auch in den Gesamtsummen.

### Kontenabstimmung

`kontenabstimmung_pruefen` benötigt `firma_id`, `jahr` und `stichtag`.
Es vergleicht Hauptbuch, Personenkonten und rekonstruierte OP-SW-Salden.
Nur gespeicherte Zuordnungen belegen die Verbindung.
Fehlende oder mehrdeutige Zuordnungen, unbekannte Historien und Währungsprobleme verhindern einen bestätigten Abgleich.

Forderungen und Verbindlichkeiten bleiben getrennt.
Differenzen sind Befunde. Sie belegen keine bestimmte Fehlerursache.
Die Verfügbarkeit von `kontenabstimmung_pruefen` und `berichtsnachweis_anzeigen` nach Leserechten steht in [Einrichtung](einrichtung.md).

### Kontenplan und Geschäftsjahreszähler

`kontenplan_anzeigen` liefert Stammdaten mit vollständigen Notizen, DATEV-/Währungs-/Sperrfeldern und datierten Steuerzuordnungen.
`konto_von`/`konto_bis` sind inklusive.
`Bezeichnung` ersetzt `#P#`. Die Vorlage bleibt erhalten.
Je Vorgabefeld gilt der jüngste nichtleere Wert. Bei gleichem Datum gilt die erste Alternative.

Vorgaben ersetzen keine gebuchten Steuerschlüssel.
Steuerprozente sind kein Geld. Fehlende Werte bleiben null.
Geschäftsjahres-OP-Zähler zählen auch ausgeglichene Belege, Gutschriften und Entwürfe, nicht nur unbezahlte Rechnungen.

## Kostenstellen

`kostenstellen_auswerten` verwendet `datum_von`, `datum_bis` und optional `kostenstelle`.
Der Kostenstellenfilter vergleicht exakt.
Gleiche Werte in `Kostenstelle1` und `Kostenstelle2` zählen pro Journalzeile einmal.
Bei zwei verschiedenen Kostenstellen erhält jede Gruppe die ganze Zeile.
**Kostenstellengruppen deshalb nicht addieren.**

`gesamtwerte` zählt jede passende Quellzeile einmal, unabhängig von der Seite.
FW-/SW-Währungspaare bleiben getrennt.
Leere Kostenstellen bilden eine eigene Gruppe.
Eröffnungen und Bewegungen stehen getrennt.
Der Bericht leitet keinen Anfangsbestand ab.

## Belegsuche und Verknüpfungen

### Bereichsübergreifende Suche

`belege_suchen` durchsucht Buchungen, Verkaufsbelege, Einkaufsbelege, Posten und Zahlungen gemeinsam.
Pflichtparameter sind `firma_id` und `suche`.
Die Suche ist wörtlich.
`datum_von`/`datum_bis` begrenzen das Belegdatum einschließlich.

Treffer sind gemeinsam nach Datum, Bereich und lokaler ID sortiert und paginiert.
Jeder Treffer enthält Herkunft und eine `navigation` mit Folgewerkzeug und Parametern.
Entwürfe bleiben enthalten.
Die Suche bildet keine bereichsübergreifenden Geldsummen.

### Gespeicherte Beziehungen

`belegverknuepfungen_anzeigen` benötigt `firma_id`, `bereich` und `datensatz_id`.
Mögliche Bereiche sind `buchung`, `verkauf`, `einkauf`, `posten` und `zahlung`.
Das Werkzeug zeigt unmittelbare eingehende und ausgehende gespeicherte Beziehungen:

- Beleg zu Posten
- Posten zu Buchung
- Zahlung zu Buchung
- Zahlungsposition zu Posten
- gespeicherte Vorbelegbeziehungen

Fehlende Ziele bleiben ausdrücklich unaufgelöst.
Die Navigation folgt keinen Betrags-, Namens- oder Referenzähnlichkeiten.
Zyklen werden nicht rekursiv verfolgt.
Weitere Schritte erfolgen über die ausgegebenen IDs.

## Datenqualität

`datenqualitaet_pruefen` prüft den vollständigen Bestand einer gewählten Firma.
Der Prüfungsumfang nennt Tabellen, Verknüpfungsfelder und Anzahl der Prüfungen.
Das Werkzeug prüft:

- fehlende gespeicherte Ziele
- den Journal-Soll-/Haben-Ausgleich je Buchung
- gespeicherte Zahlungs-/Minderungssummen gegen ihre Zuordnungen

FW und SW bleiben getrennt. Vorzeichenbehaftete Stornos bleiben erhalten.
Geldvergleiche verwenden kaufmännische Rundung auf 0,01 Währungseinheiten.
Fehlende oder ungültige Beträge sowie nicht vollständig auflösbare Zuordnungen bleiben unbekannt.

`anzahl`/`versatz` begrenzen nur die Befunde.
Gesamtzahlen gelten vor der Seiteneinteilung.
Das Werkzeug korrigiert nichts.
Es liefert keinen pauschalen Nachweis vollständiger oder steuerlich richtiger Buchführung.

## Offene Posten und Zahlungen

### Gespeicherte offene Posten

`offene_posten_auflisten` verwendet `seite` aus `forderungen`, `verbindlichkeiten`, `alle`.
Standardmäßig gilt `POSTEN.OffenFW <> 0`.
`mit_ausgeglichenen` nimmt geschlossene Posten auf.
Entwürfe sind ausgeschlossen. Historische null-Entwurfsflags gelten als Nichtentwurf.
Negative Gutschriften bleiben negativ.
Rechnungen sind kein Zahlungs-/Umsatznachweis.

`datum_von`/`datum_bis` filtern das Belegdatum.
Die Beträge bleiben die gespeicherten OP-Salden des Datenstands.
Für historische Salden dient `offene_posten_zum_stichtag_anzeigen`.

`offenen_posten_abrufen` benötigt `posten_id`.
Das Ergebnis enthält `posten`, `positionen`, `zuordnungen`, `zuordnungssummen` und `abgleich`.
Positionen und Zahlungen lassen sich unabhängig lesen:

- Positionen: `positionen_anzahl`/`positionen_versatz`
- Zahlungen: `zahlungen_anzahl`/`zahlungen_versatz`

Der Gesamtabgleich verwendet immer die vollständige Historie.
Abweichungen werden nicht korrigiert.

### Zahlungen und Zuordnungen

`zahlungen_auflisten` liefert jeden Zahlungskopf genau einmal, auch ohne Zuordnungen.
Optional filtern `adresse_id`, `datum_von` und `datum_bis`.
`suche` sucht wörtlich in `ReNr`, `BuText` und `Referenz`.
Nullverrechnungen und negative Zahlungen bleiben enthalten.
`Art` bleibt unverändert.

FW/SW und verschiedene Währungen dürfen nicht addiert werden.
Die lokale `_rowid` führt zu `zahlung_abrufen` mit derselben `firma_id`.

`zahlung_abrufen` benötigt `zahlung_id`.
Der Kopf gilt für die gesamte Zahlung, die Zuordnungen gelten für OP-Positionen.
Das Werkzeug verwendet nur gespeicherte Zahlungs-/Positions-/Posten-IDs, stets firmengebunden.
Es errät keine Betrags-/Belegnummernpaare.

Gemeinsame Nullverrechnungen beweisen weder eindeutige Rechnung-Gutschrift-Paare noch Banküberweisungen.
Negative Zahlungen, Erstattungen und Minderungen bleiben erhalten.

### Salden zum Stichtag und Altersklassen

Stichtagswerkzeuge verlangen `stichtag`.
Sie berechnen Belegbrutto abzüglich datierter Zahlungen/Minderungen bis zu diesem Tag.
Zukünftige Belege/Zahlungen und Entwürfe sind ausgeschlossen.

Fehlende Geldwerte, undatierte oder nicht abgeglichene Historien ergeben `offen_zum_stichtag_FW/SW = null`.
`teilberechnet_offen_FW/SW` zeigt nur die unvollständige Rechnung.
Unbekannte Salden werden gezählt und nicht als Null summiert.
Vollständige Filtersummen bleiben seitenunabhängig.

Die Fälligkeit folgt dem gespeicherten `Datum + TageNetto` in Kalendertagen.
Heutige Fristvorgaben, Rechts-/Feiertagsanpassungen oder Skontoannahmen fließen nicht ein.
Die Altersklassen sind nicht fällig, 1–30/31–60/61–90/über 90 Tage, Guthaben, ausgeglichene und unbekannte Werte.

Vor-Beleg-Zahlungen werden gekennzeichnet.
Heutige Mahnflags werden nicht zurückdatiert.
Datierte Hinweise liefern keinen vollständigen früheren Mahnzustand.
Historische Belegversionen und Löschprotokolle sind nicht enthalten.

## Steuern und weitere Stammdaten

### Steuerjournal

`steuerjournal_anzeigen` bewahrt Gegenpositionen, Statuswerte, nicht fällige Steuer, IST-Nachweise und getrennte FW-/SW-Währungen.
Nicht jede Zeile darf als Steuer summiert werden.

### Umsatzsteuer-Voranmeldung

`umsatzsteuer_voranmeldung_anzeigen` benötigt `firma_id`, `jahr` und genau `monat` oder `quartal`.
Eine gespeicherte UVA muss zu Firma und Zeiträumen passen.
Es gelten `Verfahren=ElsterAnmeldung` und `DatenArt=Umsatzsteuer-Voranmeldung`.

Gepackte `ELSTERMELDUNG.Kennzahlen` sind kein Jahreserklärungs-XML.
Bekannte Beträge werden aus Hundertsteln umgerechnet.
Flags und unbekannte Codes bleiben roh.
Bei mehreren Fassungen gilt `status=mehrdeutig`. Mit `meldung_id` lässt sich eine Fassung wählen.
`status=gespeichert` beweist keine Abgabe oder aktuelle rechtliche Richtigkeit.

Ohne gespeicherte Meldung liefert das Werkzeug ausschließlich `status=teilrekonstruktion` belegbarer fälliger Steuerkonten-/Bemessungswerte.
Eröffnungen und nicht fällige IST-Steuer sind ausgeschlossen.
Fehlende oder mehrdeutige Zuordnungen, Bemessungen und Währungen werden gemeldet.

Das Werkzeug liefert keine erfundene Kz83-Zahllast, Abgaberundung oder Umsatz-mal-Steuersatz-Schätzung.
Es verwendet keine Jahreserklärung als Ersatz.
Nicht zugeordnete neuere/XML-Meldungen werden nicht unterstützt.

### Kostenstellen, Zahlungsbedingungen und Währungen

Kostenstellen, Zahlungsbedingungen und Währungen bleiben auch bei Sperren sichtbar.
Notizen und Vorlagen werden weder gekürzt noch ausgefüllt.
Unbestätigte Skontoskalierung, Zahlungsarten sowie Kursrichtung/Faktorregeln bleiben offen.
Es gibt keine historischen Frist-/Kursversionen und keine abgeleiteten Währungsumrechnungen.

## Anlagen und Abschreibungen

`anlagen_auflisten` durchsucht ID, Inventarnummer, Bezeichnung, Standort, Seriennummer, Kostenstellenwert und Zusatzangaben wörtlich.
Die Liste enthält auch abgegangene und vollständig abgeschriebene Anlagen.

`anlage_abrufen` benötigt `anlage_id` und liefert `anlage` sowie seitenweise `bewegungen`.
`abschreibungsplan_anzeigen` filtert optional Anlage, `datum_von`/`datum_bis` und `nur_gebuchte`.

Zugänge, AfA, Sonder-AfA, Zuschreibungen und Abgänge stammen aus gespeicherten Bewegungen.
Anlagen-ID und Firma verbinden die Datensätze.
Numerischer Text `BuchwertNeu` wird als Geld umgerechnet.
Nutzungs-/Restdauer sind Monate, Kontenfelder sind Kontonummern.
Beide Tabellen enthalten keinen Währungscode. Für beliebige Datensätze wird keine Währung erfunden.

Zukünftige, ungebuchte und historische Zeilen bleiben standardmäßig erhalten.
`nur_gebuchte=true` wählt `Gebucht=1`, keinen unabhängig bestätigten Journalposten.
Der letzte künftige Planwert ist nicht der heutige Buchwert.

Das Werkzeug berechnet keine neue AfA und liefert keine Steuerbeurteilung.
Es liefert weder eine vollständige Methodencodeliste noch eine historische Stammdatenwiedergabe.

## Gespeicherte Anhänge

### Anhänge auflisten

`anhaenge_auflisten` benötigt `firma_id`.
`suche` filtert Metadaten wörtlich.
Die Liste nennt die Speicherart für `anhang_lesen`:

- `eintrag`: `ATTACHMENTITEM` mit firmengebundenen `ATTACHMENTCHUNK`-Zeilen.
- `altbestand`: BLOB `ATTACHMENT.Data`, ohne die separate Vorschau.
- `alias`: BLOB `ATTACHMENTALIAS.Data`.

### Speicherbytes lesen

`anhang_lesen` benötigt `firma_id` und `anhang_id`.
`speicher` ist standardmäßig `eintrag`.
`byteversatz` beginnt bei 0.
`bytelaenge` ist standardmäßig 65536, maximal 131072 Bytes.

`inhalt_base64` enthält nur den angefragten Bereich.
`naechster_byteversatz` setzt einen vollständigen lesbaren Byteabruf fort.
Große einzelne BLOBs werden inkrementell gelesen, nicht als Ganzes in SQL-Ergebnisse geladen.
Bei mehr als 500 überlappenden Chunks kann ein Abruf kürzer ausfallen. `abfrage_gekuerzt` zeigt dies an.

Das Werkzeug öffnet niemals gespeicherte Links, Dateipfade oder Netzwerkadressen.
Es entpackt keine komprimierten Inhalte und führt keine Dateien aus.
`Source`, `Source_id` und `Art` bleiben Rohwerte.
Ohne belegte Typcodes wird keine Zuordnung zu Buchungen angenommen.

Unbekannte Kompression, fehlende oder mehrdeutige Chunkpositionen und Größenabweichungen bleiben erkennbar.
Die Bedeutung des gespeicherten Größenfelds ist nicht verifiziert.
Die Ausgabe enthält rohe Speicherbytes. Sie bestätigt weder ein PDF noch die Dateiintegrität.
