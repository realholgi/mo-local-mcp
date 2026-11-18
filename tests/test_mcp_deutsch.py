import unittest

import apsw
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel

import test_database as fixtures
from mo_local_mcp.business import _packed_strings
from mo_local_mcp.errors import Abfragegrenze, DatenFehler, ParameterFehler, RechteFehler
from mo_local_mcp.mcp_deutsch import DeutscherMCP
from mo_local_mcp.server import create_server


class DeutscheMCPFehlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Diese abgelehnten Aufrufe müssen vor jedem Datenbankzugriff scheitern.
        self.server = create_server(None)

    def assert_fehler(self, ergebnis, code):
        self.assertTrue(ergebnis.isError)
        self.assertEqual(ergebnis.structuredContent['fehler']['code'], code)
        self.assertEqual(ergebnis.structuredContent['fehler']['meldung'], ergebnis.content[0].text)

    async def test_englische_kommandos_werden_nicht_weitergeleitet(self):
        ergebnis = await self.server.call_tool('list_companies', {})
        self.assertTrue(ergebnis.isError)
        self.assertIn('Unbekanntes MCP-Kommando', ergebnis.content[0].text)
        self.assertIn('list_companies', ergebnis.content[0].text)
        self.assert_fehler(ergebnis, 'UNBEKANNTES_KOMMANDO')

    async def test_alte_parameter_werden_nicht_stillschweigend_ignoriert(self):
        ergebnis = await self.server.call_tool('firmen_auflisten', {'limit': 1})
        self.assertTrue(ergebnis.isError)
        self.assertIn('Unbekannte Parameter', ergebnis.content[0].text)
        self.assertIn('limit', ergebnis.content[0].text)
        self.assert_fehler(ergebnis, 'UNBEKANNTE_PARAMETER')

    async def test_sdk_validierungsfehler_sind_deutsch_und_benennen_das_feld(self):
        for parameter in ({}, {'firma_id': 'keine Ganzzahl'}):
            with self.subTest(parameter=parameter):
                ergebnis = await self.server.call_tool('kontenplan_anzeigen', parameter)
                self.assertTrue(ergebnis.isError)
                self.assertIn('firma_id', ergebnis.content[0].text)
                self.assertIn('Ungültige Parameter', ergebnis.content[0].text)
                self.assertNotIn('Field required', ergebnis.content[0].text)
                self.assertNotIn('Error executing tool', ergebnis.content[0].text)
                self.assert_fehler(ergebnis, 'UNGUELTIGE_PARAMETER')

    async def test_fachliche_fehler_bleiben_als_mcp_fehler_erkennbar(self):
        ergebnis = await self.server.call_tool('kontenplan_anzeigen', {'firma_id': -1})
        self.assertTrue(ergebnis.isError)
        self.assertIn('firma_id', ergebnis.content[0].text)
        self.assertIn('muss', ergebnis.content[0].text)
        self.assertNotIn('Error executing tool', ergebnis.content[0].text)
        self.assert_fehler(ergebnis, 'UNGUELTIGE_PARAMETER')

    async def test_neue_kommandos_verlangen_deutsche_pflichtparameter(self):
        for kommando, pflichtfelder in (
            ('zahlungen_auflisten', {'firma_id': 1}),
            ('adresse_abrufen', {'firma_id': 1, 'adresse_id': 10}),
            ('buchung_abrufen', {'firma_id': 1, 'buchung_id': 1}),
            ('summen_und_salden_anzeigen', {'firma_id': 1, 'jahr': 2025}),
            ('firma_abrufen', {'firma_id': 1}),
            ('einkaufsbelege_auflisten', {'firma_id': 1}),
            ('einkaufsbeleg_abrufen', {'firma_id': 1, 'beleg_id': 100}),
            ('artikel_auflisten', {'firma_id': 1}),
            ('projekte_auflisten', {'firma_id': 1}),
            ('debitoren_salden_anzeigen', {'firma_id': 1}),
            ('kreditoren_salden_anzeigen', {'firma_id': 1}),
            ('datenstand_anzeigen', {'firma_id': 1}),
            ('belege_suchen', {'firma_id': 1, 'suche': 'Synthetisch'}),
            ('belegverknuepfungen_anzeigen', {'firma_id': 1, 'bereich': 'buchung', 'datensatz_id': 1}),
            ('datenqualitaet_pruefen', {'firma_id': 1}),
            ('kostenstellen_auswerten', {'firma_id': 1}),
            ('konten_monatlich_anzeigen', {'firma_id': 1, 'jahr': 2025}),
            ('guv_monatlich_anzeigen', {'firma_id': 1, 'jahr': 2025}),
            ('anhaenge_auflisten', {'firma_id': 1}),
            ('anhang_lesen', {'firma_id': 1, 'anhang_id': 1}),
        ):
            for feld in pflichtfelder:
                with self.subTest(kommando=kommando, feld=feld):
                    parameter = {k: v for k, v in pflichtfelder.items() if k != feld}
                    ergebnis = await self.server.call_tool(kommando, parameter)
                    self.assertTrue(ergebnis.isError)
                    self.assertIn('Ungültige Parameter', ergebnis.content[0].text)
                    self.assertIn(feld, ergebnis.content[0].text)
                    self.assertNotIn('Field required', ergebnis.content[0].text)
            for englisch in ('company_id', 'limit'):
                with self.subTest(kommando=kommando, englisch=englisch):
                    ergebnis = await self.server.call_tool(kommando, {**pflichtfelder, englisch: 1})
                    self.assertTrue(ergebnis.isError)
                    self.assertIn('Unbekannte Parameter', ergebnis.content[0].text)
                    self.assertIn(englisch, ergebnis.content[0].text)

    async def test_leere_parameter_und_parameterobjekt(self):
        ergebnis = await self.server.call_tool('kontenplan_anzeigen', None)
        self.assert_fehler(ergebnis, 'UNGUELTIGE_PARAMETER')
        ergebnis = await self.server.call_tool('kontenplan_anzeigen', [])
        self.assert_fehler(ergebnis, 'UNGUELTIGE_PARAMETER')

    async def test_rechte_fehler_ueber_den_sdk_aufruf(self):
        server = create_server(None, firma_ids=[1])
        ergebnis = await server.call_tool('kontenplan_anzeigen', {'firma_id': 2})
        self.assert_fehler(ergebnis, 'ZUGRIFF_VERWEIGERT')
        self.assertIn('nicht freigegeben', ergebnis.content[0].text)

    async def test_datenbankfehler_und_grenzen_ueber_echte_abfragen(self):
        fixture = fixtures.DatabaseTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        server = create_server(fixture.database, sql_erlaubt=True)
        for sql, code in (
            ('SELECT * FROM fehlende_tabelle', 'DATENBANKFEHLER'),
            ('SELECT zeroblob(1000001)', 'ABFRAGEGRENZE'),
            ('SELECT 1' + ' ' * 100000, 'ABFRAGEGRENZE'),
            ('SELECT * FROM pragma_journal_mode', 'ZUGRIFF_VERWEIGERT'),
        ):
            with self.subTest(code=code, sql=sql[:50]):
                ergebnis = await server.call_tool('sql_abfragen', {'sql': sql})
                self.assert_fehler(ergebnis, code)
        fixture.path.write_bytes(fixture.original)
        ergebnis = await server.call_tool('sql_abfragen', {'sql': 'SELECT 1'})
        self.assert_fehler(ergebnis, 'DATENSTAND_GEAENDERT')

    async def test_sdk_huellen_werden_nur_bis_zur_expliziten_ursache_entfernt(self):
        for ursache, code in (
            (ParameterFehler('jahr ist ungültig'), 'UNGUELTIGE_PARAMETER'),
            (RechteFehler('Firma ist gesperrt'), 'ZUGRIFF_VERWEIGERT'),
            (Abfragegrenze('Zu viele Bytes'), 'ABFRAGEGRENZE'),
            (apsw.InterruptError('interrupted'), 'ABFRAGEGRENZE'),
            (DatenFehler('Ungültige gespeicherte Kontenzuordnung'), 'DATENBANKFEHLER'),
            (ValueError('Ungültige Parameter'), 'INTERNER_FEHLER'),
            (RuntimeError('privates internes Detail'), 'INTERNER_FEHLER'),
        ):
            server = self._server_mit_fehler(ursache)
            ergebnis = await server.call_tool('testfehler', {})
            self.assert_fehler(ergebnis, code)
            self.assertNotIn('SDK-Hülle', ergebnis.content[0].text)
            self.assertNotIn('privates internes Detail', ergebnis.content[0].text)
            if isinstance(ursache, DatenFehler):
                self.assertEqual(ergebnis.content[0].text, str(ursache))

    async def test_gespeicherte_rohdatenfehler_behalten_den_konkreten_text(self):
        server = DeutscherMCP('Fehlertest')

        @server.tool(name='kontensteuer')
        def kontensteuer():
            return _packed_strings('defekter synthetischer Speicherwert')

        server.kommando_parameter['kontensteuer'] = set()
        ergebnis = await server.call_tool('kontensteuer', {})
        self.assert_fehler(ergebnis, 'DATENBANKFEHLER')
        self.assertEqual(ergebnis.content[0].text, 'Ungültige gepackte Kontensteuereinstellungen')
        self.assertIsInstance(DatenFehler('Datenfehler'), ValueError)

    @staticmethod
    def _server_mit_fehler(ursache):
        server = DeutscherMCP('Fehlertest')

        @server.tool(name='testfehler')
        def testfehler():
            try:
                raise ursache
            except Exception as fehler:
                raise ToolError('SDK-Hülle') from fehler

        server.kommando_parameter['testfehler'] = set()
        return server

    async def test_validierungsfehler_im_werkzeug_sind_keine_parameterfehler(self):
        class InternesModell(BaseModel):
            zahl: int

        server = DeutscherMCP('Fehlertest')

        @server.tool(name='intern')
        def intern(zahl: int):
            return InternesModell.model_validate({'zahl': 'interner Fehler'})

        server.kommando_parameter['intern'] = {'zahl'}
        ergebnis = await server.call_tool('intern', {'zahl': 1})
        self.assert_fehler(ergebnis, 'INTERNER_FEHLER')
        ergebnis = await server.call_tool('intern', {'zahl': 'falsch'})
        self.assert_fehler(ergebnis, 'UNGUELTIGE_PARAMETER')

    async def test_ausgabevalidierung_ist_kein_parameterfehler(self):
        server = DeutscherMCP('Fehlertest')

        @server.tool(name='ausgabe')
        def ausgabe() -> int:
            return 'keine Ganzzahl'

        server.kommando_parameter['ausgabe'] = set()
        ergebnis = await server.call_tool('ausgabe', {})
        self.assert_fehler(ergebnis, 'INTERNER_FEHLER')

    async def test_ungueltiger_stichtag_ist_ein_parameterfehler(self):
        ergebnis = await self.server.call_tool(
            'offene_posten_zum_stichtag_anzeigen', {'firma_id': 1, 'stichtag': 'kein Datum'},
        )
        self.assert_fehler(ergebnis, 'UNGUELTIGE_PARAMETER')
        self.assertIn('stichtag', ergebnis.content[0].text)


if __name__ == '__main__':
    unittest.main()
