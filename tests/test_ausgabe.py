import unittest

from mo_local_mcp.ausgabe import deutsche_ausgabe


class DeutscheAusgabeTests(unittest.TestCase):
    def test_gespeicherte_werte_und_binaerdaten_bleiben_unveraendert(self):
        quelle = {
            'columns': ['Name', 'Text', 'BuchwertNeu', 'Waehrung', 'history_status', 'side'],
            'rows': [['unknown', 'receivable', '123.45', 'EUR', 'reconciled', 'receivable'],
                     ['Musterfirma', {'base64': 'AA=='}, None, 'USD', 'mismatch', 'payable']],
            'next_offset': 2, 'truncated': True,
            'money': {'columns': ['BuchwertNeu'], 'unit': 'Währungseinheiten'},
        }
        ergebnis = deutsche_ausgabe(quelle)
        self.assertEqual(ergebnis['spalten'], ['Name', 'Text', 'BuchwertNeu', 'Waehrung', 'historienstatus', 'seite'])
        self.assertEqual(ergebnis['zeilen'], [
            ['unknown', 'receivable', '123.45', 'EUR', 'abgeglichen', 'forderungen'],
            ['Musterfirma', {'base64': 'AA=='}, None, 'USD', 'abweichend', 'verbindlichkeiten'],
        ])
        self.assertEqual(ergebnis['naechster_versatz'], 2)
        self.assertTrue(ergebnis['gekuerzt'])
        self.assertEqual(ergebnis['geldbetraege']['spalten'], ['BuchwertNeu'])
        self.assertEqual(quelle['rows'][0][-2:], ['reconciled', 'receivable'])
        self.assertEqual(quelle['columns'][-2:], ['history_status', 'side'])

    def test_sql_benutzeraliase_und_zugehoerige_werte_bleiben_original(self):
        quelle = {
            'columns': ['history_status', 'side', 'status', 'due_date'],
            'rows': [['reconciled', 'receivable', 'stored', '2028-02-01']],
            'truncated': False,
        }
        ergebnis = deutsche_ausgabe(quelle, rohe_spalten=True)
        self.assertEqual(ergebnis['spalten'], quelle['columns'])
        self.assertEqual(ergebnis['zeilen'], quelle['rows'])

    def test_abgeleitete_geldspalten_und_metadaten_sind_einheitlich_deutsch(self):
        quelle = {
            'columns': ['open_as_of_FW', 'aging_bucket', 'Art_label'],
            'rows': [['123.45', 'not_due', 'DebitorRechnung']],
            'money': {'columns': ['open_as_of_FW']},
            'totals': {'columns': ['open_FW', 'aging_bucket'], 'rows': [['123.45', 'over_90']]},
            'basis': ['Nur synthetische Beispieldaten.'],
        }
        ergebnis = deutsche_ausgabe(quelle)
        self.assertEqual(ergebnis['spalten'], ['offen_zum_stichtag_FW', 'altersklasse', 'Art_bezeichnung'])
        self.assertEqual(ergebnis['zeilen'][0], ['123.45', 'nicht_faellig', 'DebitorRechnung'])
        self.assertEqual(ergebnis['geldbetraege']['spalten'], ['offen_zum_stichtag_FW'])
        self.assertEqual(ergebnis['summen']['zeilen'][0], ['123.45', 'ueber_90_tage'])

    def test_kennzahlenarten_und_herkunft_werden_nur_im_fachkontext_uebersetzt(self):
        ergebnis = deutsche_ausgabe({
            'status': 'stored', 'source': 'journal_reconstruction',
            'figures': [{'kind': 'assessment_base', 'code': '81', 'amount': '123.45'}],
            'report': {'Name': 'stored', 'Text': 'assessment_base'},
        })
        self.assertEqual(ergebnis['status'], 'gespeichert')
        self.assertEqual(ergebnis['quelle'], 'journalrekonstruktion')
        self.assertEqual(ergebnis['kennzahlen'][0], {'art': 'bemessungsgrundlage', 'kennzahl': '81', 'betrag': '123.45'})
        self.assertEqual(ergebnis['meldung'], {'Name': 'stored', 'Text': 'assessment_base'})

    def test_prozent_metadaten_verweisen_auf_die_tatsaechliche_ausgabespalte(self):
        ergebnis = deutsche_ausgabe({
            'columns': ['Prozent', 'percent'], 'rows': [[1900, '19.00']],
            'percentages': {'raw_column': 'Prozent', 'output_column': 'percent'},
        })
        metadaten = ergebnis['prozentsaetze']
        rohwert = ergebnis['zeilen'][0][ergebnis['spalten'].index(metadaten['ursprungsspalte'])]
        prozentsatz = ergebnis['zeilen'][0][ergebnis['spalten'].index(metadaten['ausgabespalte'])]
        self.assertEqual((rohwert, prozentsatz), (1900, '19.00'))

    def test_neue_details_und_hauptbuchsalden_werden_uebersetzt(self):
        tabelle = {
            'columns': ['_rowid', 'Status', 'Steuersatz', 'Summe', 'SO_Bemerkung'],
            'rows': [[1, 987, '', '-12.34', 'unknown']],
        }
        ergebnis = deutsche_ausgabe({
            'booking': tabelle, 'address': tabelle, 'journal_rows': tabelle,
            'total_accounts': 1,
            'accounts': [{
                'account': 1400, 'name': 'Vorlage #P#',
                'opening': {'debit': '10.00', 'credit': '0.00', 'balance': '10.00'},
                'turnovers': {'debit': '0.00', 'credit': '12.34'},
                'closing_balance': '-2.34', 'balance_side': 'H',
            }],
            'totals': {'closing_balance': '-2.34'},
            'tools': ['list_payments', 'get_booking', 'get_address', 'get_trial_balance'],
        })
        for schluessel in ('buchung', 'adresse', 'journalzeilen'):
            self.assertEqual(ergebnis[schluessel]['spalten'], tabelle['columns'])
            self.assertEqual(ergebnis[schluessel]['zeilen'], tabelle['rows'])
        self.assertEqual(ergebnis['anzahl_konten'], 1)
        self.assertEqual(ergebnis['konten'][0], {
            'konto': 1400, 'name': 'Vorlage #P#',
            'eroeffnung': {'soll': '10.00', 'haben': '0.00', 'saldo': '10.00'},
            'umsaetze': {'soll': '0.00', 'haben': '12.34'},
            'endsaldo': '-2.34', 'saldoseite': 'H',
        })
        self.assertEqual(ergebnis['summen'], {'endsaldo': '-2.34'})
        self.assertEqual(ergebnis['werkzeuge'], [
            'zahlungen_auflisten', 'buchung_abrufen', 'adresse_abrufen',
            'summen_und_salden_anzeigen',
        ])


if __name__ == '__main__':
    unittest.main()
