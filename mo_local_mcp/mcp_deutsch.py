"""Deutsche Fehlerantworten ohne Änderungen am MCP-Protokoll oder seinen Bibliotheken."""

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, TextContent


class DeutscherMCP(FastMCP):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kommando_parameter = {}

    @staticmethod
    def _fehler(text):
        return CallToolResult(isError=True, content=[TextContent(type='text', text=text)])

    async def call_tool(self, name, arguments):
        if name not in self.kommando_parameter:
            return self._fehler(f'Unbekanntes MCP-Kommando: {name}')
        unbekannt = set(arguments) - self.kommando_parameter[name]
        if unbekannt:
            return self._fehler('Unbekannte Parameter: ' + ', '.join(sorted(unbekannt)))
        try:
            return await super().call_tool(name, arguments)
        except ToolError as fehler:
            ursache = fehler.__cause__
            # Die SDK-Validierung stellt strukturierte Fehler bereit. Ihre Felder
            # bleiben erhalten, ohne englische Bibliothekstexte oder Eingabewerte auszugeben.
            details = getattr(ursache, 'errors', None)
            if callable(details):
                meldungen = []
                for eintrag in details():
                    feld = '.'.join(str(teil) for teil in eintrag['loc'])
                    art = eintrag['type']
                    beschreibung = {
                        'missing': 'Pflichtfeld fehlt',
                        'int_type': 'Ganzzahl erforderlich',
                        'int_parsing': 'Ganzzahl erforderlich',
                        'int_from_float': 'Ganzzahl ohne Nachkommastellen erforderlich',
                        'string_type': 'Zeichenkette erforderlich',
                        'bool_type': 'Wahrheitswert erforderlich',
                        'bool_parsing': 'Wahrheitswert erforderlich',
                        'list_type': 'Liste erforderlich',
                        'dict_type': 'Wörterbuch erforderlich',
                    }.get(art, f'Ungültiger Wert ({art})')
                    if art == 'literal_error':
                        erwartet = eintrag.get('ctx', {}).get('expected', '').replace(' or ', ' oder ')
                        beschreibung = f'Zulässige Werte: {erwartet}'
                    meldungen.append(f'{feld}: {beschreibung}')
                return self._fehler('Ungültige Parameter: ' + '; '.join(meldungen))
            return self._fehler(f'Abfrage fehlgeschlagen: {ursache if ursache is not None else fehler}')

    async def list_tools(self):
        werkzeuge = await super().list_tools()
        for werkzeug in werkzeuge:
            werkzeug.inputSchema['additionalProperties'] = False
        return werkzeuge
