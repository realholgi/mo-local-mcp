"""Deutsche Fehlerantworten ohne Änderungen am MCP-Protokoll oder seinen Bibliotheken."""

import apsw
from pydantic import ValidationError

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from .errors import Abfragegrenze, DatenFehler, DatenstandGeaendert, ParameterFehler, RechteFehler


class DeutscherMCP(FastMCP):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kommando_parameter = {}

    @staticmethod
    def _fehler(code, text):
        return CallToolResult(
            isError=True,
            content=[TextContent(type='text', text=text)],
            structuredContent={'fehler': {'code': code, 'meldung': text}},
        )

    async def call_tool(self, name, arguments):
        if name not in self.kommando_parameter:
            return self._fehler('UNBEKANNTES_KOMMANDO', f'Unbekanntes MCP-Kommando: {name}')
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return self._fehler('UNGUELTIGE_PARAMETER', 'Ungültige Parameter: Ein Parameterobjekt wird erwartet')
        unbekannt = set(arguments) - self.kommando_parameter[name]
        if unbekannt:
            return self._fehler('UNBEKANNTE_PARAMETER', 'Unbekannte Parameter: ' + ', '.join(sorted(unbekannt)))
        try:
            return await super().call_tool(name, arguments)
        except ToolError as fehler:
            ursache = fehler
            # Nur SDK-Hüllen entfernen. Ursachen fachlicher Fehler sind keine
            # Ersatzklassifikation (etwa ein ValueError nach einem SQL-Fehler).
            gesehen = set()
            while isinstance(ursache, ToolError) and ursache.__cause__ is not None and id(ursache) not in gesehen:
                gesehen.add(id(ursache))
                ursache = ursache.__cause__
            details = None
            if isinstance(ursache, ValidationError):
                # Auch Werkzeugcode und Ausgabevalidierung können ValidationError
                # werfen. Nur tatsächlich ungültige Aufrufparameter sind Eingabefehler.
                werkzeug = self._tool_manager.get_tool(name)
                if werkzeug is not None:
                    try:
                        metadaten = werkzeug.fn_metadata
                        metadaten.arg_model.model_validate(metadaten.pre_parse_json(arguments))
                    except ValidationError as eingabefehler:
                        details = eingabefehler.errors(include_input=False)
            if details is not None:
                meldungen = []
                for eintrag in details:
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
                return self._fehler('UNGUELTIGE_PARAMETER', 'Ungültige Parameter: ' + '; '.join(meldungen))
            if isinstance(ursache, ParameterFehler):
                return self._fehler('UNGUELTIGE_PARAMETER', f'Ungültige Parameter: {ursache}')
            if isinstance(ursache, (RechteFehler, PermissionError, apsw.AuthError, apsw.ReadOnlyError)):
                return self._fehler('ZUGRIFF_VERWEIGERT', 'Zugriff verweigert: ' + str(ursache))
            if isinstance(ursache, DatenstandGeaendert):
                return self._fehler('DATENSTAND_GEAENDERT', str(ursache))
            if isinstance(ursache, (Abfragegrenze, apsw.InterruptError, apsw.TooBigError)):
                return self._fehler('ABFRAGEGRENZE', 'Abfragegrenze erreicht: Filter enger setzen oder weniger Daten anfordern')
            if isinstance(ursache, DatenFehler):
                return self._fehler('DATENBANKFEHLER', str(ursache))
            if isinstance(ursache, apsw.Error):
                return self._fehler('DATENBANKFEHLER', 'Datenbankabfrage fehlgeschlagen')
            return self._fehler('INTERNER_FEHLER', 'Abfrage fehlgeschlagen: Interner Fehler bei der Verarbeitung')

    async def list_tools(self):
        werkzeuge = await super().list_tools()
        for werkzeug in werkzeuge:
            werkzeug.inputSchema['additionalProperties'] = False
        return werkzeuge
