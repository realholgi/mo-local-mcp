# mo-local-mcp

Lokaler MCP-Server für verschlüsselte MonKey-Office-Datenbankstände auf macOS.
Er liest ausschließlich und entschlüsselt Seiten im Arbeitsspeicher.
Es entsteht keine unverschlüsselte Datenbankdatei.

Der MCP bietet Belegsuche, Buchungsdetails, Bilanz/GuV, Kontenabstimmung, offene Posten,
Steuerauswertungen, Anlagen und gespeicherte Anhänge.
Kommandos und eigene Meldungen sind Deutsch. Gespeicherte Daten bleiben unverändert.

## Schnellstart

Du benötigst macOS, Python ab 3.13 und [uv](https://docs.astral.sh/uv/).
**Verwende nur einen geschlossenen, ruhenden und konsistenten Datenbankstand, keine aktive MonKey-Datei.**
Die `beispiel.sdb` dient nur der Entwicklung.

Führe im Projektordner aus:

```sh
uv sync --frozen
uv run mo-schluessel-wiederherstellen
uv run mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db
```

Andere Programm- und Schlüsselpfade erklärt die [Einrichtung](docs/einrichtung.md).

stdin/stdout dienen dem MCP-Protokoll, nicht einer interaktiven SQL-Konsole.
Meldungen gehen nach stderr.
Hilfe: `uv run mo-local-mcp --hilfe` und `uv run mo-schluessel-wiederherstellen --hilfe`.

Rufe im MCP zuerst `firmen_auflisten` auf und wähle eine Firma ausdrücklich aus.

## Dokumentation

| Thema | Inhalt |
| --- | --- |
| [Einrichtung und Betrieb](docs/einrichtung.md) | Installation, Aktualisierung, Schlüssel, OMP, Leserechte und Schreibschutz |
| [MCP-Referenz](docs/referenz.md) | Kommandos, Parameter, Ergebnisformate, Fehlercodes, Ressourcen und Prompts |
| [Auswertungen](docs/auswertungen.md) | Fachliche Regeln und Grenzen für Berichte, Konten, OPs, Zahlungen, Steuern, Anlagen und Anhänge |
| [Entwicklung](docs/entwicklung.md) | Schlüsselprofile, Verschlüsselung, Schemaquellen, Tests und Releases |

Der Projektcode steht unter der [MIT-Lizenz](LICENSE).
