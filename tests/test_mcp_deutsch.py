import unittest

from mo_local_mcp.server import create_server


class DeutscheMCPFehlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Diese abgelehnten Aufrufe müssen vor jedem Datenbankzugriff scheitern.
        self.server = create_server(None)

    async def test_englische_kommandos_werden_nicht_weitergeleitet(self):
        ergebnis = await self.server.call_tool('list_companies', {})
        self.assertTrue(ergebnis.isError)
        self.assertIn('Unbekanntes MCP-Kommando', ergebnis.content[0].text)
        self.assertIn('list_companies', ergebnis.content[0].text)

    async def test_alte_parameter_werden_nicht_stillschweigend_ignoriert(self):
        ergebnis = await self.server.call_tool('firmen_auflisten', {'limit': 1})
        self.assertTrue(ergebnis.isError)
        self.assertIn('Unbekannte Parameter', ergebnis.content[0].text)
        self.assertIn('limit', ergebnis.content[0].text)

    async def test_sdk_validierungsfehler_sind_deutsch_und_benennen_das_feld(self):
        for parameter in ({}, {'firma_id': 'keine Ganzzahl'}):
            with self.subTest(parameter=parameter):
                ergebnis = await self.server.call_tool('kontenplan_anzeigen', parameter)
                self.assertTrue(ergebnis.isError)
                self.assertIn('firma_id', ergebnis.content[0].text)
                self.assertIn('Ungültige Parameter', ergebnis.content[0].text)
                self.assertNotIn('Field required', ergebnis.content[0].text)
                self.assertNotIn('Error executing tool', ergebnis.content[0].text)

    async def test_fachliche_fehler_bleiben_als_mcp_fehler_erkennbar(self):
        ergebnis = await self.server.call_tool('kontenplan_anzeigen', {'firma_id': -1})
        self.assertTrue(ergebnis.isError)
        self.assertIn('firma_id', ergebnis.content[0].text)
        self.assertIn('muss', ergebnis.content[0].text)
        self.assertNotIn('Error executing tool', ergebnis.content[0].text)


if __name__ == '__main__':
    unittest.main()
