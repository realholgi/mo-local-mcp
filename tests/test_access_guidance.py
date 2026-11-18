"""Synthetische MCP-Prüfungen für Leserechte, Ressourcen und Analyse-Prompts."""

import json
import unittest
from typing import Any

import test_business as fixtures
from mo_local_mcp.access import ReadAccess
from mo_local_mcp.server import create_server


class AccessGuidanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = fixtures.BusinessTests(methodName="runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.database = fixture.reader.database

    async def payload(self, server, name, arguments):
        result = await server.call_tool(name, arguments)
        return json.loads(result[0].text)

    async def test_company_restriction_filters_before_pagination_and_blocks_details(self):
        server = create_server(self.database, firma_ids=[2])
        table = await self.payload(server, "firmen_auflisten", {"anzahl": 1})
        self.assertEqual([row[0] for row in table["zeilen"]], [2])
        self.assertIsNone(table["naechster_versatz"])
        result = await server.call_tool("firma_abrufen", {"firma_id": 1})
        self.assertTrue(result.isError)
        self.assertIn("nicht freigegeben", result.content[0].text)
        self.assertEqual(result.structuredContent["fehler"]["code"], "ZUGRIFF_VERWEIGERT")
        for name, arguments in (
            ("berichtsnachweis_anzeigen", {"firma_id": 1, "jahr": 2025, "gliederung_id": 1, "position_id": 1}),
            ("kontenabstimmung_pruefen", {"firma_id": 1, "jahr": 2025, "stichtag": "2025-12-31"}),
        ):
            result = await server.call_tool(name, arguments)
            self.assertEqual(result.structuredContent["fehler"]["code"], "ZUGRIFF_VERWEIGERT")
        self.assertNotIn("Musterfirma Eins", result.content[0].text)
        self.assertEqual((await self.payload(server, "firma_abrufen", {"firma_id": 2}))["firma"]["zeilen"][0][0], 2)
        empty = create_server(self.database, firma_ids=[])
        self.assertEqual((await self.payload(empty, "firmen_auflisten", {}))["zeilen"], [])

    async def test_free_sql_cannot_bypass_company_or_master_data_restrictions(self):
        configurations: tuple[dict[str, Any], ...] = (
            {}, {"firma_ids": [1], "sql_erlaubt": True}, {"sql_erlaubt": False},
            {"sensible_stammdaten_erlaubt": False, "sql_erlaubt": True},
        )
        for kwargs in configurations:
            with self.subTest(kwargs=kwargs):
                server = create_server(self.database, **kwargs)
                names = {tool.name for tool in await server.list_tools()}
                self.assertNotIn("sql_abfragen", names)
                result = await server.call_tool("sql_abfragen", {"sql": "SELECT * FROM FIRMA"})
                self.assertTrue(result.isError)
                self.assertNotIn("Musterfirma", result.content[0].text)
        server = create_server(self.database, sql_erlaubt=True)
        result = await self.payload(server, "sql_abfragen", {"sql": "SELECT Name FROM FIRMA WHERE _rowid=?", "parameter": [1]})
        self.assertEqual(result["zeilen"], [["Musterfirma Eins"]])

    async def test_master_data_mode_exposes_only_ids_and_defined_reports(self):
        server = create_server(self.database, firma_ids=[1], sensible_stammdaten_erlaubt=False)
        table = await self.payload(server, "firmen_auflisten", {})
        self.assertEqual(table["spalten"], ["_rowid"])
        self.assertEqual(table["zeilen"], [[1]])
        names = {tool.name for tool in await server.list_tools()}
        for name in ("firma_abrufen", "adresse_abrufen", "adressen_suchen", "buchung_abrufen", "belege_suchen", "anhang_lesen", "debitoren_salden_anzeigen", "berichtsnachweis_anzeigen", "kontenabstimmung_pruefen"):
            with self.subTest(name=name):
                self.assertNotIn(name, names)
                self.assertTrue((await server.call_tool(name, {"firma_id": 1})).isError)
        self.assertIn("guv_monatlich_anzeigen", names)
        self.assertIn("datenqualitaet_pruefen", names)

    async def test_schema_resources_preserve_units_and_german_tool_navigation(self):
        server = create_server(self.database)
        resource = list(await server.read_resource("monkey://fachschema/BUCHUNG"))[0]
        result = json.loads(resource.content)
        self.assertEqual(result["betraege"]["gespeicherte_einheiten_je_waehrungseinheit"], 100)
        self.assertIn("buchung_abrufen", result["tabellen"]["BUCHUNG"]["werkzeuge"])
        full = json.loads(list(await server.read_resource("monkey://fachschema"))[0].content)
        self.assertIn("AUFTRAG", full["tabellen"])
        self.assertNotIn("Musterfirma Eins", json.dumps(full))

    async def test_access_resource_reflects_actual_sql_and_company_restrictions(self):
        server = create_server(self.database, firma_ids=[2])
        resource = list(await server.read_resource("monkey://zugriff"))[0]
        data = json.loads(resource.content)
        self.assertEqual(data["firma_ids"], [2])
        self.assertFalse(data["sql_erlaubt"])
        self.assertFalse(data["alle_firmen"])

    async def test_analysis_prompts_validate_scope_and_never_ask_for_writes(self):
        server = create_server(self.database, firma_ids=[1])
        annual = await server.get_prompt("jahresabschluss_pruefen", {"firma_id": "1", "jahr": "2026"})
        text = annual.messages[0].content.text
        self.assertIn("Geschäftsjahresbeginn 2026", text)
        self.assertIn("datenqualitaet_pruefen", text)
        self.assertIn("kein Live-Connect", text)
        receivables = await server.get_prompt("forderungen_erklaeren", {"firma_id": "1", "stichtag": "2026-01-31"})
        self.assertIn("2026-01-31", receivables.messages[0].content.text)
        for name, arguments in (
            ("jahresabschluss_pruefen", {"firma_id": "2", "jahr": "2026"}),
            ("jahresabschluss_pruefen", {"firma_id": "1", "jahr": "10000"}),
            ("forderungen_erklaeren", {"firma_id": "1", "stichtag": "2026-02-30"}),
        ):
            with self.subTest(name=name, arguments=arguments), self.assertRaises(ValueError):
                await server.get_prompt(name, arguments)
        restricted = create_server(self.database, sensible_stammdaten_erlaubt=False)
        self.assertNotIn("forderungen_erklaeren", {prompt.name for prompt in await restricted.list_prompts()})

    def test_invalid_company_configuration_is_rejected(self):
        for ids in ([0], [-1], [True], ["1"]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                ReadAccess(ids)


if __name__ == "__main__":
    unittest.main()
