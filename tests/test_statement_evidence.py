import json
import unittest
from decimal import Decimal

import test_statements as fixtures
from test_statements import position

from mo_local_mcp.errors import ParameterFehler
from mo_local_mcp.server import create_server


class StatementEvidenceTests(unittest.TestCase):
    reader = fixtures.StatementTests.reader

    def evidence_reader(self, extra_sql=""):
        return self.reader("""
            ALTER TABLE BUCHUNG ADD COLUMN Art INTEGER;
            UPDATE BUCHUNG SET Art=1;
            ALTER TABLE JOURNAL ADD COLUMN _rowid INTEGER;
            UPDATE JOURNAL SET _rowid=rowid;
        """ + extra_sql)

    def test_deviations_cover_sections_positions_accounts_and_negative_basis(self):
        report = self.reader().financial_statements(1, 2025)
        self.assertTrue(report['comparison']['comparable'])
        self.assertTrue(report['comparison']['period_comparable'])
        profit = report['profit_and_loss']
        self.assertEqual((profit['absolute_change'], profit['percentage_change']), ('8.00', '66.67'))
        expenses = position(profit, 22)
        self.assertEqual((expenses['absolute_change'], expenses['percentage_change']), ('-2.00', '-25.00'))
        self.assertEqual(expenses['accounts'][0]['percentage_change'], '-25.00')
        assets = report['balance_sheet']['assets']
        self.assertEqual((assets['absolute_change'], assets['percentage_change']), ('6.00', '66.67'))
        result = position(report['balance_sheet']['liabilities_and_equity'], 13)
        self.assertEqual(result['absolute_change'], '8.00')

    def test_zero_basis_is_explicit_and_not_divided(self):
        report = self.reader().financial_statements(1, 2025)
        group = position(report['profit_and_loss'], 23)
        self.assertEqual((group['absolute_change'], group['percentage_change'], group['percentage_basis']),
                         ('0.00', '0.00', 'both_zero'))
        expense = position(report['profit_and_loss'], 24)
        self.assertEqual((expense['absolute_change'], expense['percentage_change'], expense['percentage_basis']),
                         ('-1.00', None, 'zero_previous'))

    def test_noncomparability_keeps_values_and_never_numeric_changes(self):
        for sql, reason in (
            ("UPDATE WIRTSCHAFTSJAHR SET Waehrung='USD' WHERE _rowid=1;", 'different_or_missing_currency'),
            ("UPDATE WIRTSCHAFTSJAHR SET Waehrung=NULL WHERE _rowid=1;", 'different_or_missing_currency'),
            ("UPDATE WIRTSCHAFTSJAHR SET Von='2024-01-02' WHERE _rowid=1; UPDATE BUCHUNG SET Datum='2024-01-02' WHERE _rowid=1;", 'different_period'),
        ):
            with self.subTest(reason=reason, sql=sql):
                report = self.reader(sql).financial_statements(1, 2025)
                self.assertEqual(report['comparison']['reason'], reason)
                profit = report['profit_and_loss']
                self.assertEqual(profit['previous_total'], '12.00')
                self.assertIsNone(profit['absolute_change'])
                self.assertIsNone(profit['percentage_change'])
                for row in profit['lines']:
                    self.assertIsNone(row['absolute_change'])
                    for account in row['accounts']:
                        self.assertIsNone(account['absolute_change'])

    def test_missing_or_disabled_previous_year_has_null_differences(self):
        reader = self.reader()
        for year, enabled, reason in ((2024, True, 'missing_previous_year'), (2025, False, 'disabled')):
            report = reader.financial_statements(1, year, include_previous_year=enabled)
            self.assertEqual(report['comparison']['reason'], reason)
            self.assertIsNone(report['profit_and_loss']['absolute_change'])
            self.assertIsNone(report['profit_and_loss']['percentage_change'])

    def test_noncalendar_years_compare_by_calendar_boundaries(self):
        reader = self.reader("""
            UPDATE WIRTSCHAFTSJAHR SET Von='2024-07-01',Bis='2025-06-30' WHERE _rowid=1;
            UPDATE WIRTSCHAFTSJAHR SET Von='2025-07-01',Bis='2026-06-30' WHERE _rowid=2;
            UPDATE BUCHUNG SET Datum='2024-07-01' WHERE _rowid=1;
            UPDATE BUCHUNG SET Datum='2025-07-01' WHERE _rowid=2;
        """)
        self.assertTrue(reader.financial_statements(1, 2025)['comparison']['comparable'])

    def test_every_visible_position_reconciles_to_unique_journal_contributions(self):
        reader = self.evidence_reader()
        report = reader.financial_statements(1, 2025)
        sections = [report['profit_and_loss'], *report['balance_sheet'].values()]
        for section in sections:
            for row in section['lines']:
                with self.subTest(item_id=row['item_id']):
                    evidence = reader.statement_evidence(1, 2025, 1, row['item_id'])
                    self.assertEqual(evidence['position_amount'], row['amount'])
                    self.assertEqual(evidence['contribution'], row['amount'])
                    self.assertEqual(sum((Decimal(entry['contribution']) for entry in evidence['entries']), Decimal(0)),
                                     Decimal(row['amount']))
                    ids = [entry['journal_row_id'] for entry in evidence['entries']]
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertEqual({entry['booking_id'] for entry in evidence['entries']}, {2})

    def test_result_position_explains_calculated_transfer_not_fake_booking(self):
        reader = self.evidence_reader()
        evidence = reader.statement_evidence(1, 2025, 1, 11)
        self.assertEqual(evidence['contribution'], '4.00')
        transferred = [row for row in evidence['entries'] if row['result_position_id'] is not None]
        self.assertEqual({row['result_position_id'] for row in transferred}, {13})
        self.assertTrue(all(row['position_path'][:3] == [11, 13, 20] for row in transferred))
        self.assertEqual(sum((Decimal(row['contribution']) for row in transferred), Decimal(0)), Decimal('20.00'))
        self.assertEqual(reader.statement_evidence(1, 2025, 1, 13, 8400)['contribution'], '30.00')

    def test_result_and_source_signs_are_multiplied_without_ancestor_sign_inheritance(self):
        reader = self.evidence_reader("""
            UPDATE STRUKTURPOSITION SET VzWechsel=1 WHERE Firma_id=1 AND ItemId IN (11,13);
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid)
                VALUES (1,2,400,0,0,400,1000),(1,2,880,0,400,0,1001);
        """)
        evidence = reader.statement_evidence(1, 2025, 1, 13, 8400)
        self.assertEqual(evidence['contribution'], '-30.00')
        self.assertEqual(evidence['entries'][0]['factor'], 1)
        self.assertEqual(evidence['entries'][0]['source_item_id'], 21)

    def test_collective_account_filter_uses_effective_account_and_side_selection(self):
        reader = self.evidence_reader("""
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid)
                VALUES (1,2,1400,1400,100,0,1000),(1,2,880,0,0,100,1001);
        """)
        evidence = reader.statement_evidence(1, 2025, 1, 3, 1400)
        self.assertEqual(evidence['contribution'], '11.00')
        self.assertEqual(len(evidence['entries']), 2)
        self.assertEqual({row['original_account'] for row in evidence['entries']}, {10001, 1400})
        self.assertEqual(reader.statement_evidence(1, 2025, 1, 3, 10001)['entries'], [])
        self.assertEqual(reader.statement_evidence(1, 2025, 1, 12, 1400)['contribution'], '0.00')
        switched = self.evidence_reader("""
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid)
                VALUES (1,2,10001,1400,0,2000,1000),(1,2,880,0,2000,0,1001);
        """)
        liability = switched.statement_evidence(1, 2025, 1, 12, 1400)
        self.assertEqual(liability['contribution'], '10.00')
        self.assertEqual({row['factor'] for row in liability['entries']}, {-1})
        self.assertEqual(switched.statement_evidence(1, 2025, 1, 3)['entries'], [])

    def test_openings_storno_and_pagination_preserve_full_sums(self):
        reader = self.evidence_reader("""
            UPDATE BUCHUNG SET Art=2 WHERE _rowid=2;
            INSERT INTO BUCHUNG (_rowid,Firma_id,Wj_id,Datum,Status,Art) VALUES (10,1,2,'2025-03-01',99,1);
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid)
                VALUES (1,10,400,0,100,0,1000),(1,10,400,0,-100,0,1001);
        """)
        first = reader.statement_evidence(1, 2025, 1, 2, limit=1)
        second = reader.statement_evidence(1, 2025, 1, 2, limit=1, offset=first['next_offset'])
        third = reader.statement_evidence(1, 2025, 1, 2, limit=1, offset=second['next_offset'])
        self.assertEqual(first['opening_contribution'], '5.00')
        self.assertEqual(first['movement_contribution'], '0.00')
        self.assertEqual(first['contribution'], second['contribution'])
        self.assertEqual(first['accounts'], third['accounts'])
        self.assertEqual(first['total_entries'], 3)
        self.assertEqual(third['entries'][0]['debit'], '-1.00')
        self.assertEqual(third['entries'][0]['booking_status'], 99)
        self.assertIsNone(third['next_offset'])
        self.assertFalse(third['truncated'])
        beyond = reader.statement_evidence(1, 2025, 1, 2, offset=99)
        self.assertEqual(beyond['entries'], [])
        self.assertEqual(beyond['contribution'], '5.00')

    def test_more_than_query_page_is_complete_before_pagination(self):
        reader = self.evidence_reader("""
            WITH RECURSIVE n(x) AS (VALUES(1000) UNION ALL SELECT x+1 FROM n WHERE x<1501)
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid)
                SELECT 1,2,400,0,1,1,x FROM n;
        """)
        first = reader.statement_evidence(1, 2025, 1, 2, limit=500)
        last = reader.statement_evidence(1, 2025, 1, 2, limit=500, offset=first['next_offset'])
        self.assertEqual(first['total_entries'], 503)
        self.assertEqual(len(last['entries']), 3)
        self.assertEqual(last['contribution'], '5.00')
        self.assertEqual(len({row['journal_row_id'] for row in first['entries'] + last['entries']}), 503)

    def test_evidence_excludes_wrong_firm_year_and_date_and_controls(self):
        reader = self.evidence_reader("""
            INSERT INTO BUCHUNG (_rowid,Firma_id,Wj_id,Datum,Status,Art) VALUES
                (10,1,1,'2025-06-01',2,1),(11,1,2,'2024-12-31',2,1),(12,1,2,'2026-01-01',2,1);
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid) VALUES
                (1,10,400,0,99999,0,1000),(1,11,400,0,99999,0,1001),
                (1,12,400,0,99999,0,1002),(2,2,400,0,99999,0,1003);
        """)
        self.assertEqual(reader.statement_evidence(1, 2025, 1, 2)['contribution'], '5.00')
        self.assertEqual(reader.statement_evidence(1, 2025, 1, 1, 9000)['entries'], [])

    def test_evidence_validates_selection_and_pagination(self):
        reader = self.evidence_reader()
        for arguments in ({'limit': 0}, {'limit': 501}, {'offset': -1}, {'account': True}):
            with self.subTest(arguments=arguments), self.assertRaises(ParameterFehler):
                reader.statement_evidence(1, 2025, 1, 2, **arguments)
        with self.assertRaises(ParameterFehler):
            reader.statement_evidence(1, 2025, 1, 999)
        with self.assertRaises(ValueError):
            reader.statement_evidence(1, 2025, 2, 1)
        with self.assertRaises(ParameterFehler):
            reader.statement_evidence(1, 2025, 1, 2, account=9999)


class StatementEvidenceMCPTests(unittest.IsolatedAsyncioTestCase):
    reader = fixtures.StatementTests.reader
    evidence_reader = StatementEvidenceTests.evidence_reader

    async def test_german_mcp_reports_and_journal_evidence(self):
        reader = self.evidence_reader()
        server = create_server(reader.database)
        result = await server.call_tool('berichtsnachweis_anzeigen', {
            'firma_id': 1, 'jahr': 2025, 'gliederung_id': 1, 'position_id': 13,
            'konto': 8400, 'anzahl': 1,
        })
        evidence = json.loads(result[0].text)
        self.assertEqual(evidence['beitrag'], '30.00')
        self.assertEqual(evidence['buchungszeilen'][0]['buchung_id'], 2)
        self.assertEqual(evidence['buchungszeilen'][0]['beitrag'], '30.00')
        self.assertEqual(evidence['buchungszeilen'][0]['ergebnisposition_id'], 13)
        result = await server.call_tool('bilanz_und_guv_anzeigen', {'firma_id': 1, 'jahr': 2025})
        report = json.loads(result[0].text)
        self.assertTrue(report['vorjahresvergleich']['vergleichbar'])
        # Die echten deutschen Feldnamen müssen an der MCP-Grenze erscheinen.
        sections = [value for value in report.values() if isinstance(value, dict) and 'abweichung_absolut' in value]
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]['abweichung_absolut'], '8.00')
        self.assertEqual(sections[0]['abweichung_prozent'], '66.67')

    async def test_german_mcp_reports_concrete_consistency_error(self):
        reader = self.evidence_reader("""
            INSERT INTO JOURNAL (Firma_id,Buchung_id,Konto,SammelKonto,BetragSoll,BetragHaben,_rowid)
                VALUES (1,2,400,0,1,0,1000);
        """)
        result = await create_server(reader.database).call_tool('berichtsnachweis_anzeigen', {
            'firma_id': 1, 'jahr': 2025, 'gliederung_id': 1, 'position_id': 2,
        })
        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent['fehler']['code'], 'DATENBANKFEHLER')
        self.assertIn('nicht ausgeglichen', result.structuredContent['fehler']['meldung'])
