import json
import unittest

import test_business as fixtures
from mo_local_mcp.server import create_server
from mo_local_mcp.snapshot import snapshot_overview


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.BusinessTests(methodName="runTest")
        fixture.detail_updates = (
            ("ALTER TABLE BUCHUNG ADD COLUMN EingabeDatum", []),
            ("ALTER TABLE BUCHUNG ADD COLUMN DatumVerbucht", []),
            ("ALTER TABLE BESTELLUNG ADD COLUMN Datum", []),
            ("UPDATE BUCHUNG SET EingabeDatum='2027-07-02 12:00:00',DatumVerbucht='2027-07-03' WHERE _rowid=4", []),
            ("UPDATE ZAHLUNG SET Datum=NULL WHERE _rowid=4", []),
            ("UPDATE BUCHUNG SET EingabeDatum='2099-01-01 12:00:00',DatumVerbucht='2099-01-02' WHERE Firma_id=2", []),
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.reader = fixture.reader

    def test_actual_ranges_timestamps_and_empty_area_are_distinguished(self):
        result = snapshot_overview(self.reader, 1)
        areas = {row["bereich"]: row for row in result["zeitraeume"]}
        self.assertEqual(areas["buchungen"]["anzahl"], 3)
        self.assertEqual(areas["buchungen"]["erstes_belegdatum"], "2026-01-01")
        self.assertEqual(areas["buchungen"]["letztes_belegdatum"], "2027-07-01")
        self.assertEqual(areas["einkauf"]["anzahl"], 0)
        self.assertIsNone(areas["einkauf"]["letztes_belegdatum"])
        self.assertEqual(result["letzte_gespeicherte_erfassung"], "2027-07-02 12:00:00")
        self.assertEqual(result["letztes_gespeichertes_verbuchungsdatum"], "2027-07-03")
        self.assertEqual([row["_rowid"] for row in result["geschaeftsjahre"]], [10, 11])
        self.assertEqual(result["dateigroesse_bytes"], self.reader.database.path.stat().st_size)
        self.assertTrue(any("keine vollständige" in note for note in result["grenzen"]))

    def test_unknown_company_is_not_an_empty_complete_dataset(self):
        with self.assertRaisesRegex(ValueError, "Firma nicht gefunden"):
            snapshot_overview(self.reader, 999)

    def test_undated_rows_are_counted_separately(self):
        result = snapshot_overview(self.reader, 1)
        payments = next(row for row in result["zeitraeume"] if row["bereich"] == "zahlungen")
        self.assertEqual(payments["anzahl"], 3)
        self.assertEqual(payments["ohne_belegdatum"], 1)


class SnapshotMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_tool_enforces_scope_and_returns_german_data(self):
        fixture = SnapshotTests(methodName="runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        server = create_server(fixture.reader.database, firma_ids=[1])
        content = await server.call_tool("datenstand_anzeigen", {"firma_id": 1})
        result = json.loads(content[0].text)
        self.assertEqual(result["firma_id"], 1)
        self.assertIn("zeitraeume", result)
        self.assertNotIn("2099-01-01", json.dumps(result))
        denied = await server.call_tool("datenstand_anzeigen", {"firma_id": 2})
        self.assertTrue(denied.isError)
        self.assertIn("nicht freigegeben", denied.content[0].text)


if __name__ == "__main__":
    unittest.main()
