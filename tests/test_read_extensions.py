import json
import unittest

import test_business as fixtures

from mo_local_mcp.server import create_server


def make_fixture(owner):
    fixture = fixtures.BusinessTests(methodName="runTest")
    fixture.detail_updates = (
        ("ALTER TABLE FIRMA ADD COLUMN FASteuernummer", []),
        ("UPDATE FIRMA SET FASteuernummer='SYNTHETISCH-101' WHERE _rowid=1", []),
        ("ALTER TABLE JOURNAL ADD COLUMN Kostenstelle1", []),
        ("ALTER TABLE JOURNAL ADD COLUMN Kostenstelle2", []),
        ("UPDATE JOURNAL SET Kostenstelle2='Bereich%_A' WHERE _rowid IN (1,2)", []),
        ("UPDATE JOURNAL SET Kostenstelle1='Fremd' WHERE _rowid=3", []),
        ("UPDATE AUFTRAG SET BestellNr='Referenz%_A' WHERE _rowid IN (100,103)", []),
        ("UPDATE BUCHUNG SET BelegNr='SYNTH%_A' WHERE _rowid=4", []),
    )
    owner.addCleanup(fixture.doCleanups)
    fixture.setUp()
    return fixture.reader


class ReadExtensionTests(unittest.TestCase):
    def setUp(self):
        self.reader = make_fixture(self)

    def test_company_detail_selects_exact_company_and_preserves_original_fields(self):
        company = fixtures.records(self.reader.company(1)["company"])[0]
        self.assertEqual(company["_rowid"], 1)
        self.assertEqual(company["FASteuernummer"], "SYNTHETISCH-101")
        with self.assertRaisesRegex(ValueError, "nicht gefunden"):
            self.reader.company(999)
        with self.assertRaisesRegex(ValueError, "firma_id"):
            self.reader.company(True)

    def test_booking_filters_use_journal_sides_including_negative_reversals(self):
        def ids(**filters):
            return [row["_rowid"] for row in fixtures.records(self.reader.bookings(1, **filters))]
        self.assertEqual(ids(debit_account=1234, credit_account=1234), [1])
        self.assertEqual(ids(debit_account=8400), [4])
        self.assertEqual(ids(credit_account=1200, document_number="%_"), [4])
        self.assertEqual(ids(debit_account=1200), [])
        self.assertEqual(ids(credit_account=1776), [])
        self.assertEqual(ids(account=1234, cost_center="Bereich%_A"), [1])
        self.assertEqual(ids(cost_center="Fremd"), [])
        self.assertEqual(ids(cost_center="%_"), [])
        self.assertEqual(ids(document_number="' OR 1=1 --"), [])
        for filters in ({"debit_account": -1}, {"credit_account": True}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                self.reader.bookings(1, **filters)

    def test_sales_search_is_literal_company_scoped_and_combines_with_filters(self):
        rows = fixtures.records(self.reader.sales_documents(1, search="%_"))
        self.assertEqual([row["_rowid"] for row in rows], [100])
        self.assertEqual(rows[0]["GesamtBruttoFW"], "1.19")
        self.assertEqual(self.reader.sales_documents(1, search="%_", document_type=8)["rows"], [])
        self.assertEqual(self.reader.sales_documents(1, search="' OR 1=1 --")["rows"], [])
        self.assertEqual([row["_rowid"] for row in fixtures.records(
            self.reader.sales_documents(1, search="entwurf", include_drafts=True))], [101])

    def test_open_item_dates_filter_document_dates_not_historical_balances(self):
        rows = fixtures.records(self.reader.open_items(1, date_from="2026-01-02", date_to="2026-01-02"))
        self.assertEqual([(row["_rowid"], row["OffenFW"]) for row in rows], [(2, "-0.50")])
        with self.assertRaisesRegex(ValueError, "datum_von"):
            self.reader.open_items(1, date_from="2026-02-30")
        with self.assertRaisesRegex(ValueError, "datum_von"):
            self.reader.open_items(1, date_from="2026-02-01", date_to="2026-01-01")


class ReadExtensionMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.server = create_server(make_fixture(self).database)

    async def test_company_and_extended_filters_return_actual_german_mcp_results(self):
        for command, parameters, key, expected_ids in (
            ("firma_abrufen", {"firma_id": 1}, "firma", [1]),
            ("buchungen_auflisten", {"firma_id": 1, "konto_soll": 8400, "belegnummer": "%_"}, None, [4]),
            ("buchungen_auflisten", {"firma_id": 1, "kostenstelle": "Bereich%_A"}, None, [1]),
            ("verkaufsbelege_auflisten", {"firma_id": 1, "suche": "%_"}, None, [100]),
            ("offene_posten_auflisten", {"firma_id": 1, "datum_von": "2026-01-02", "datum_bis": "2026-01-02"}, None, [2]),
        ):
            with self.subTest(command=command, parameters=parameters):
                content = await self.server.call_tool(command, parameters)
                structured = json.loads(content[0].text)
                table = structured[key] if key else structured
                index = table["spalten"].index("_rowid")
                self.assertEqual([row[index] for row in table["zeilen"]], expected_ids)


if __name__ == "__main__":
    unittest.main()
