"""Consumer-sichtbare Connect-Verträge mit ausschließlich synthetischen Daten."""

from decimal import Decimal
import sqlite3
import unittest

from mo_local_mcp.connect import ConnectReader
from mo_local_mcp.connect_bookings import handle


class SQLiteDatabase:
    """OfficeDatabase.query-Vertrag, ohne verschlüsselte Ursprungsdateien."""

    def __init__(self):
        self.connection = sqlite3.connect(":memory:")

    def query(self, sql, parameters=(), limit=100):
        cursor = self.connection.execute(sql, parameters)
        rows = cursor.fetchmany(limit + 1)
        return {"columns": [column[0] for column in cursor.description],
                "rows": rows[:limit], "truncated": len(rows) > limit}


class ConnectBookingTests(unittest.TestCase):
    def setUp(self):
        self.database = SQLiteDatabase()
        self.addCleanup(self.database.connection.close)
        self.reader = ConnectReader(self.database)
        self.database.connection.executescript('''
            CREATE TABLE FIRMA (_rowid INTEGER PRIMARY KEY);
            INSERT INTO FIRMA VALUES (1),(2);
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum,Text,Status,
                Summe,SummeFW,BelegNr,EingabeDatum,Referenz,Bemerkung,KontoSoll,KontoHaben,
                Waehrung,Kurs,Steuersatz);
            INSERT INTO BUCHUNG VALUES
                (1,1,'2025-02-01','Beratung 100%_','3',11900,12500,'RE%_1',
                 '2025-02-02 10:00:00','REF-A','Notiz',0,1200,'USD',0.952,'USt19'),
                (2,1,'2025-02-02','Storno',2,-11900,-12500,'ST1',
                 NULL,NULL,NULL,1200,8400,'USD',0.952,'USt19'),
                (3,1,'2025-03-01','Unbekannt',NULL,NULL,NULL,NULL,
                 NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
                (99,2,'2025-02-01','Geheim',1,99999,99999,'RE%_1',
                 NULL,NULL,NULL,9999,1200,'EUR',1,NULL);
            CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY,Firma_id,Buchung_id,Position,
                NummerLong,Konto,Steuersatz,Text,BetragSoll,BetragHaben,BetragSollFW,
                BetragHabenFW,Storno,Kostenstelle1,Kostenstelle2,OSS_ISO_LK,OSS_Prozent,OSS_Typ);
            INSERT INTO JOURNAL VALUES
                (10,1,1,1,100,8400,'USt19','Netto',10000,0,10500,0,0,'Projekt A','',NULL,NULL,NULL),
                (11,1,1,2,100,1776,'USt19','Steuer',1900,NULL,2000,NULL,0,'','Team B','FR',2000,1),
                (12,1,1,3,100,1200,'-','Bank',0,11900,0,12500,0,NULL,NULL,NULL,NULL,NULL),
                (20,1,2,1,101,8400,'USt19','Gegenbuchung',-11900,0,-12500,0,1,'Projekt A','',NULL,NULL,NULL),
                (21,1,2,2,101,1200,NULL,'Bank',0,-11900,0,-12500,1,NULL,NULL,NULL,NULL,NULL),
                (90,2,1,1,999,9999,'GEHEIM','Falsche Firma',99999,0,99999,0,0,'Geheim','',NULL,NULL,NULL),
                (91,1,99,1,999,8888,'GEHEIM','Fremder Kopf',99999,0,99999,0,0,'Geheim','',NULL,NULL,NULL);
            CREATE TABLE KONTO (_rowid INTEGER PRIMARY KEY,Firma_id,Nummer,Bezeichnung);
            INSERT INTO KONTO VALUES
                (1,1,8400,'Erlöse'),(2,1,1200,'Bank'),(3,1,1776,'Umsatzsteuer'),
                (99,2,8400,'Geheimes Konto');
            CREATE TABLE STEUERSATZ (_rowid INTEGER PRIMARY KEY,Firma_id,Name,Beschreibung,
                Prozent,Buchungssperre,OSS);
            INSERT INTO STEUERSATZ VALUES
                (1,1,'USt19','Regelsatz',1900,0,0),
                (2,1,'OSS','Frankreich',2000,1,1),
                (3,1,'Unbekannt',NULL,NULL,NULL,NULL),
                (99,2,'Geheim','Nicht ausgeben',9999,0,0);
        ''')

    def call(self, method, params=None, firma_id=1):
        return handle(self.reader, method, {} if params is None else params, firma_id)

    def listed(self, filters):
        return self.call('buchungList', {'BuchungFilter': filters})['BuchungListItem']

    def test_list_consumer_keys_money_null_and_company(self):
        rows = self.listed({})
        self.assertEqual([row['Buchung_ID'] for row in rows], ['1', '2', '3'])
        self.assertEqual(Decimal(rows[0]['Summe']), Decimal('119.00'))
        self.assertEqual(Decimal(rows[0]['SummeFW']), Decimal('125.00'))
        self.assertIsNone(rows[2]['Summe'])
        self.assertIsNone(rows[0]['Status'])
        self.assertEqual(rows[0]['LokalStatus'], '3')

    def test_all_real_list_filters_are_applied(self):
        cases = [
            ({'DatumVon': '2025-02-01', 'DatumBis': '2025-02-01'}, ['1']),
            ({'Suchtext': 'ref-a'}, ['1']),
            ({'Suchtext': '100%_'}, ['1']),
            ({'BelegNr': '%_'}, ['1']),
            ({'Konto': 1776}, ['1']),
            ({'KontoSoll': 8400}, ['1', '2']),
            ({'KontoHaben': 1200}, ['1', '2']),
            ({'KontoHaben': 8400}, []),
            ({'Kostenstelle': 'Team B'}, ['1']),
            ({'Kostenstelle': 'Projekt A', 'DatumBis': '2025-02-01'}, ['1']),
            ({'Konto': 9999}, []),
            ({'Kostenstelle': 'Geheim'}, []),
            ({'BelegNr': "' OR 1=1 --"}, []),
        ]
        for filters, expected in cases:
            with self.subTest(filters=filters):
                self.assertEqual([row['Buchung_ID'] for row in self.listed(filters)], expected)

    def test_unverified_status_filter_fails_explicitly(self):
        self.assertEqual(len(self.listed({'FestschreibStatus': 4})), 3)
        for status in (1, 2):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'nicht verifiziert'):
                self.listed({'FestschreibStatus': status})

    def test_detail_consumer_journal_shape_currency_and_company(self):
        item = self.call('buchungGet', {'Buchung_ID': '1'})['BuchungItem']
        self.assertEqual(item['Notizen'], 'Notiz')
        self.assertEqual(item['Kurs'], '0.952')
        self.assertEqual(item['Waehrung'], 'USD')
        self.assertIsNone(item['FestschreibStatus'])
        self.assertNotIn('AttachmentIDList', item)
        journal = item['BuchungJournalItemList']['BuchungJournalItem']
        self.assertEqual(len(journal), 3)
        self.assertEqual(journal[0]['Kontobezeichnung'], 'Erlöse')
        self.assertEqual(journal[0]['Journalnummer'], 100)
        self.assertEqual(Decimal(journal[0]['BetragSoll']), Decimal('100.00'))
        self.assertEqual(Decimal(journal[0]['FW_Soll']), Decimal('105.00'))
        self.assertIsNone(journal[1]['BetragHaben'])
        self.assertEqual(journal[2]['Steuersatz'], '-')
        oss = journal[1]['OSS_Daten']['OSSDatenItem']
        self.assertEqual((oss['Isocode'], oss['Typ']), ('FR', 1))
        self.assertIsNone(oss['Steuersatz'])
        self.assertEqual(journal[1]['LokalOSSProzent'], 2000)

    def test_storno_signs_and_missing_values_are_preserved(self):
        item = self.call('buchungGet', {'Buchung_ID': '2'})['BuchungItem']
        journal = item['BuchungJournalItemList']['BuchungJournalItem']
        self.assertEqual(Decimal(item['Summe']), Decimal(-119))
        self.assertEqual(Decimal(journal[0]['BetragSoll']), Decimal(-119))
        self.assertEqual(Decimal(journal[0]['FW_Soll']), Decimal(-125))
        self.assertEqual(journal[0]['LokalStorno'], 1)
        self.assertIsNone(journal[1]['Steuersatz'])

    def test_get_rejects_other_company_and_invalid_identifiers(self):
        for identifier in ('99', '0', '-1', '1 OR 1=1', 1, None):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.call('buchungGet', {'Buchung_ID': identifier})
        self.assertEqual(self.call('buchungGet', {'Buchung_ID': '99'}, 2)['BuchungItem']['Text'], 'Geheim')
        with self.assertRaises(ValueError):
            self.call('buchungList', firma_id=9)

    def test_tax_consumer_keys_percent_scale_and_company(self):
        rows = {row['Name']: row for row in self.call('steuersatzList')['SteuersatzListItem']}
        self.assertEqual(set(rows), {'USt19', 'OSS', 'Unbekannt'})
        self.assertEqual(Decimal(rows['USt19']['Steuersatz']), Decimal(19))
        self.assertTrue(rows['OSS']['Gesperrt'])
        self.assertTrue(rows['OSS']['OSS_Steuersatz'])
        self.assertIsNone(rows['Unbekannt']['Steuersatz'])
        self.assertIsNone(rows['Unbekannt']['Gesperrt'])

    def test_templates_have_documented_nesting_and_independent_positions(self):
        filters = self.call('buchungFilterTemplate')['BuchungFilter']
        self.assertEqual(len(self.listed(filters)), 3)
        item = self.call('buchungTemplate', {'PositionenAnzahl': 2})['BuchungAddItem']
        positions = item['BuchungPositionItemList']['BuchungPositionAddItem']
        self.assertEqual(len(positions), 2)
        positions[0]['Text'] = 'Nur eins'
        self.assertEqual(positions[1]['Text'], '')
        self.assertEqual(len(self.call('buchungTemplate')['BuchungAddItem']['BuchungPositionItemList']['BuchungPositionAddItem']), 1)

    def test_unknown_filters_and_malformed_values_do_not_succeed(self):
        for filters in ({'Ignorieren': 1}, {'Konto': True}, {'Konto': '8400'},
                        {'KontoSoll': -1}, {'Suchtext': None}, {'Kostenstelle': 1},
                        {'FestschreibStatus': 3}, {'FestschreibStatus': True},
                        {'DatumVon': '2025-02-30'},
                        {'DatumVon': '2025-03-01', 'DatumBis': '2025-02-01'}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                self.listed(filters)
        for method in ('buchungFilterTemplate', 'steuersatzList', 'buchungGet'):
            with self.subTest(method=method), self.assertRaises(ValueError):
                self.call(method, {'Unbekannt': 'x'})
        for count in (0, -1, True, 501, '2'):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.call('buchungTemplate', {'PositionenAnzahl': count})

    def test_query_limit_is_error_not_silent_partial_list(self):
        self.database.connection.executemany(
            'INSERT INTO BUCHUNG (_rowid,Firma_id,Datum) VALUES (?,1,?)',
            ((identifier, '2025-04-01') for identifier in range(1000, 1501)),
        )
        with self.assertRaisesRegex(ValueError, 'Abfragegrenze'):
            self.listed({})
