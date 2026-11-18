# mo-local-mcp

[![CI](https://github.com/realholgi/mo-local-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/realholgi/mo-local-mcp/actions/workflows/ci.yml) [![Version](https://img.shields.io/github/v/release/realholgi/mo-local-mcp)](https://github.com/realholgi/mo-local-mcp/releases/latest) [![Lizenz: MIT](https://img.shields.io/github/license/realholgi/mo-local-mcp)](LICENSE)

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

Installiere das fertige Paket aus [Release v1.1.0](https://github.com/realholgi/mo-local-mcp/releases/tag/v1.1.0). Ein Git-Checkout ist nicht nötig:

```sh
uv tool install --python 3.13 \
  "https://github.com/realholgi/mo-local-mcp/releases/download/v1.1.0/mo_local_mcp-1.1.0-py3-none-any.whl"
mo-schluessel-wiederherstellen
mo-local-mcp --datenbank /absoluter/pfad/entwicklungsstand.db
```

Prüfsummen, Quellcodeinstallation sowie andere Programm- und Schlüsselpfade erklärt die [Einrichtung](docs/einrichtung.md).

stdin/stdout dienen dem MCP-Protokoll, nicht einer interaktiven SQL-Konsole.
Meldungen gehen nach stderr.
Hilfe: `mo-local-mcp --hilfe` und `mo-schluessel-wiederherstellen --hilfe`.

Rufe im MCP zuerst `firmen_auflisten` auf und wähle eine Firma ausdrücklich aus.

## Beispiel

Mit synthetischen Beispieldaten könnte eine Anfrage im MCP-Client lauten:

> Vergleiche für Firma 101 die GuV 2028 mit dem Vorjahr.
> Erkläre die Veränderung des Jahresgewinns anhand der beteiligten Konten und Buchungen.

Die Firma und die vorhandenen Geschäftsjahre wählst du zuvor aus dem tatsächlichen Datenstand.

## Dokumentation

| Thema | Inhalt |
| --- | --- |
| [Einrichtung und Betrieb](docs/einrichtung.md) | Installation, Aktualisierung, Schlüssel, OMP, Leserechte und Schreibschutz |
| [MCP-Referenz](docs/referenz.md) | Kommandos, Parameter, Ergebnisformate, Fehlercodes, Ressourcen und Prompts |
| [Auswertungen](docs/auswertungen.md) | Fachliche Regeln und Grenzen für Berichte, Konten, OPs, Zahlungen, Steuern, Anlagen und Anhänge |
| [Entwicklung](docs/entwicklung.md) | Schlüsselprofile, Verschlüsselung, Schemaquellen, Tests und Releases |

Der Projektcode steht unter der [MIT-Lizenz](LICENSE).
