# Projektregeln

## Sprache

- Die Projektsprache ist Deutsch.
- Kommunikation, Dokumentation, Kommentare, Hilfetexte und Fehlermeldungen sind auf Deutsch zu verfassen.
- Auch die öffentlich angebotenen MCP-Kommandos, ihre Parameter und ihre Beschreibungen erhalten verständliche deutsche Bezeichnungen.
- Technisch vorgegebene Bezeichner des MCP-Protokolls, externer Bibliotheken und des bestehenden Datenbankschemas bleiben unverändert. Gespeicherte Datenbankwerte werden nicht übersetzt oder umbenannt.

## Dokumentationsstil

- Dokumentation folgt STE80 Lite. Die Sprache bleibt Deutsch.
- Schreibe kurze Sätze mit möglichst einem Gedanken pro Satz. Nutze aktive Verben und einfache Wörter.
- Verwende für denselben Begriff immer dieselbe Bezeichnung.
- Teile lange Sätze oder Sätze mit mehreren Aussagen. Vermeide Floskeln, Werbesprache und unnötige Wiederholungen.
- Überarbeite bestehende Texte gezielt. Erzwinge keine starren Wortgrenzen und keinen vollständigen ASD-STE100-Stil.
- Bewahre Fakten, Einschränkungen und den Grad der Gewissheit. Ändere keine Befehle, Pfade, URLs, Bezeichner, Zahlen oder Lizenztexte aus Stilgründen.
- Keine pauschalen Absicherungen, Haftungsfloskeln oder vorsorglichen Rechtfertigungen in der Dokumentation. Nenne konkrete technische Grenzen und notwendige Sicherheitshinweise direkt, einmal und an der passenden Stelle.

## Beispiele und Datenschutz

- Ausschließlich anonymisierte oder vollständig synthetische Beispieldaten verwenden, auch in Test-Fixtures und MCP-Aufrufbeispielen.
- Keine echten Personen- oder Firmennamen, Anschriften, Kontaktdaten, Bankverbindungen, Belegnummern, Inventarnummern oder sonstigen identifizierenden Daten in Beispiele übernehmen.
- Auch Kombinationen aus Beträgen, Datumsangaben und Kennungen dürfen keine echten Geschäftsvorgänge als vermeintlich anonyme Beispiele wiedergeben.
- Nachweise mit Echtdaten nicht als Beispieldaten in Dokumentation, Quellcode oder Test-Fixtures festhalten.
- Die Anonymisierung von Beispielen ist von fachlichen Datenabfragen zu unterscheiden: Angeforderte Datenbankauskünfte dürfen nicht durch erfundene Werte ersetzt werden.

## Datenbankzugriff

- Ursprungsdatenbanken ausschließlich lesend öffnen und niemals verändern, auch nicht für Tests oder Verifikationen.
- Die `beispiel.sdb` im Projektordner dient ausschließlich der Entwicklung. Sie ist keine festgelegte Produktionsdatenquelle.
