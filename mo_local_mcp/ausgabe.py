"""Deutsche MCP-Darstellung; gespeicherte Werte und technische Namen bleiben original."""


WERKZEUGNAMEN = {
    'database_info': 'datenbankinformationen',
    'list_tables': 'tabellen_auflisten',
    'describe_table': 'tabelle_beschreiben',
    'query': 'sql_abfragen',
    'business_schema': 'fachschema_anzeigen',
    'list_companies': 'firmen_auflisten',
    'list_fiscal_years': 'geschaeftsjahre_auflisten',
    'list_tax_rates': 'steuersaetze_auflisten',
    'list_accounts': 'kontenplan_anzeigen',
    'list_addresses': 'adressen_suchen',
    'list_sales_documents': 'verkaufsbelege_auflisten',
    'get_sales_document': 'verkaufsbeleg_abrufen',
    'list_bookings': 'buchungen_auflisten',
    'list_open_items': 'offene_posten_auflisten',
    'get_open_item': 'offenen_posten_abrufen',
    'get_payment': 'zahlung_abrufen',
    'get_financial_statements': 'bilanz_und_guv_anzeigen',
    'get_account_statement': 'kontoauszug_anzeigen',
    'get_open_items_as_of': 'offene_posten_zum_stichtag_anzeigen',
    'get_open_item_aging': 'offene_posten_altersstruktur_anzeigen',
    'get_tax_journal': 'steuerjournal_anzeigen',
    'get_vat_return': 'umsatzsteuer_voranmeldung_anzeigen',
    'list_cost_centers': 'kostenstellen_auflisten',
    'list_payment_terms': 'zahlungsbedingungen_auflisten',
    'list_currencies': 'waehrungen_auflisten',
    'list_assets': 'anlagen_auflisten',
    'get_asset': 'anlage_abrufen',
    'get_depreciation_schedule': 'abschreibungsplan_anzeigen',
}

SCHLUESSEL = {
    'account': 'konto', 'accounts': 'konten', 'active': 'aktiv',
    'actual_tax': 'tatsaechliche_steuer', 'aging_bucket': 'altersklasse',
    'allocation_totals': 'zuordnungssummen', 'allocations': 'zuordnungen',
    'amount': 'betrag', 'amounts': 'betraege', 'api_fields': 'api_felder',
    'api_structures': 'api_strukturen', 'as_of': 'stichtag', 'asset': 'anlage',
    'assets': 'aktiva', 'authority': 'aussagegrundlage', 'balance': 'saldo',
    'balance_sheet': 'bilanz', 'balance_sheet_balanced': 'bilanz_ausgeglichen',
    'balance_side': 'saldoseite', 'basis': 'grundlage', 'blocked': 'gesperrt',
    'booking_count': 'anzahl_buchungen', 'booking_id': 'buchung_id',
    'business': 'fachliche_beschreibung', 'business_output': 'fachliche_ausgabe',
    'bytes': 'groesse_bytes', 'caution': 'hinweis', 'caveats': 'einschraenkungen',
    'checks': 'pruefungen', 'closing_balance': 'endsaldo', 'code': 'kennzahl',
    'columns': 'spalten', 'company_id': 'firma_id', 'contra_account': 'gegenkonto',
    'credit': 'haben', 'currency': 'waehrung', 'cutoff': 'stichtag',
    'date': 'datum', 'date_from': 'datum_von', 'date_to': 'datum_bis',
    'days_overdue': 'tage_ueberfaellig', 'debit': 'soll', 'depth': 'tiefe',
    'derived_fields': 'abgeleitete_felder', 'differences': 'abweichungen',
    'document': 'beleg', 'document_number': 'belegnummer', 'due_date': 'faellig_am',
    'dunning_candidate': 'mahnkandidat', 'encryption': 'verschluesselung',
    'entries': 'buchungszeilen', 'entry_count': 'anzahl_zuordnungen', 'enums': 'wertelisten',
    'fields': 'felder', 'figure_count': 'anzahl_kennzahlen', 'figures': 'kennzahlen',
    'file': 'datei', 'financial_account': 'finanzkonto', 'fiscal_year': 'geschaeftsjahr',
    'fiscal_tax_mode': 'versteuerung_geschaeftsjahr', 'foreign_keys': 'fremdschluessel',
    'historical_limits': 'historische_grenzen', 'history_status': 'historienstatus',
    'ids': 'kennungen', 'inactive': 'inaktiv', 'indexes': 'indizes', 'item': 'posten',
    'item_count': 'anzahl_posten', 'item_id': 'posten_id', 'item_type': 'postenart',
    'item_reference': 'posten_belegnummer', 'item_date': 'posten_datum',
    'item_currency': 'posten_waehrung', 'item_position': 'posten_position',
    'joins': 'verknuepfungen', 'journal_balanced': 'journal_ausgeglichen',
    'journal_id': 'journal_id', 'journal_ids': 'journal_ids',
    'journal_rows': 'journalzeilen', 'journal_row_id': 'journalzeile_id',
    'journal_number': 'journalnummer', 'kind': 'art',
    'liabilities_and_equity': 'passiva', 'limitations': 'grenzen', 'limits': 'begrenzungen',
    'lines': 'zeilen', 'mapping_basis': 'zuordnungsgrundlage', 'matches': 'stimmt_ueberein',
    'meaning': 'bedeutung', 'method_codes': 'methodencodes',
    'modified_unix_ns': 'geaendert_unix_ns', 'money': 'geldbetraege',
    'money_fields': 'geldfelder', 'money_unit': 'geldeinheit',
    'movement_count': 'anzahl_bewegungen', 'movement_credit': 'bewegungen_haben',
    'movement_debit': 'bewegungen_soll', 'movements': 'bewegungen', 'name': 'name',
    'next_offset': 'naechster_versatz', 'non_due_rows_excluded': 'nicht_faellige_zeilen_ausgeschlossen',
    'nonzero_accounts_fully_mapped': 'konten_mit_betrag_vollstaendig_zugeordnet',
    'notes': 'anmerkungen', 'null_preserved': 'null_bleibt_erhalten', 'number': 'nummer',
    'objects': 'objekte', 'observed_dunning_level_as_of': 'belegte_mahnstufe_zum_stichtag',
    'op_document_count': 'anzahl_op_belege', 'op_payment_count': 'anzahl_op_zahlungen',
    'opening': 'eroeffnung', 'opening_count': 'anzahl_eroeffnungsbuchungen',
    'opening_credit': 'eroeffnung_haben', 'opening_debit': 'eroeffnung_soll',
    'opening_entry': 'eroeffnungsbuchung', 'opening_rows_excluded': 'eroeffnungszeilen_ausgeschlossen',
    'output_column': 'ausgabespalte', 'overdue': 'ueberfaellig', 'page_size': 'seitengroesse',
    'parent_id': 'uebergeordnete_position_id', 'payment': 'zahlung',
    'payment_date': 'zahlungsdatum', 'payment_reference': 'zahlungs_belegnummer',
    'payment_currency': 'zahlungswaehrung', 'payment_booking_id': 'zahlungsbuchung_id',
    'percent': 'prozentsatz', 'percentages': 'prozentsaetze', 'positions': 'positionen',
    'position': 'position', 'pre_document_allocations': 'zuordnungen_vor_belegdatum',
    'previous_amount': 'vorjahresbetrag', 'previous_fiscal_year': 'voriges_geschaeftsjahr',
    'previous_total': 'vorjahressumme', 'profit_and_loss': 'guv',
    'query_seconds': 'abfrage_sekunden', 'raw_column': 'ursprungsspalte',
    'raw_query_output': 'sql_rohausgabe', 'raw_value': 'rohwert', 'read_only': 'nur_lesend',
    'reason': 'begruendung', 'reconciliation': 'abgleich', 'reference': 'referenz',
    'report': 'meldung', 'report_rules': 'auswertungsregeln',
    'representation': 'darstellung', 'result_characters': 'ergebnis_zeichen',
    'rows': 'zeilen', 'schema': 'schema', 'sha256': 'sha256', 'side': 'seite',
    'snapshot': 'fester_datenstand', 'sort_number': 'sortiernummer', 'source': 'quelle',
    'sql': 'sql', 'status': 'status', 'storno': 'storno',
    'storage_observations': 'speicherbeobachtungen',
    'stored_units_per_currency_unit': 'gespeicherte_einheiten_je_waehrungseinheit',
    'stored_units_per_percent': 'gespeicherte_einheiten_je_prozent',
    'structure_id': 'gliederung_id', 'table': 'tabelle', 'tables': 'tabellen',
    'tax_code': 'steuerschluessel', 'tax_rows_included': 'steuerzeilen_enthalten',
    'tools': 'werkzeuge', 'total': 'summe', 'totals': 'summen',
    'total_entries': 'anzahl_buchungszeilen', 'truncated': 'gekuerzt',
    'turnovers': 'umsaetze', 'type': 'typ', 'unit': 'einheit', 'units': 'einheiten',
    'unknown_balance_count': 'anzahl_unbekannte_saldi', 'unknown_due_count': 'anzahl_unbekannte_faelligkeiten',
    'unmapped_tax_rows': 'nicht_zugeordnete_steuerzeilen', 'url': 'url',
    'uva_base': 'uva_bemessung', 'uva_tax': 'uva_steuer', 'valid_from': 'gueltig_ab',
    'version': 'version', 'view': 'sicht', 'FW_currency': 'FW_waehrung', 'SW_currency': 'SW_waehrung',
    'company': 'firma', 'coverage': 'abdeckung', 'issues': 'probleme', 'reports': 'meldungen',
    'text': 'text', 'undated_allocations': 'undatierte_zuordnungen',
    'missing_documented_columns': 'fehlende_dokumentierte_spalten',
    'missing_mapped_columns': 'fehlende_zugeordnete_spalten',
}

for englisch, deutsch in (
    ('paid_as_of_', 'bezahlt_zum_stichtag_'),
    ('reduction_as_of_', 'minderung_zum_stichtag_'),
    ('calculated_open_', 'teilberechnet_offen_'),
    ('open_as_of_', 'offen_zum_stichtag_'),
    ('open_', 'offen_'),
    ('paid_', 'bezahlt_'),
    ('reduced_', 'gemindert_'),
    ('past_paid_', 'bisher_bezahlt_'),
    ('past_reduced_', 'bisher_gemindert_'),
):
    for waehrung in ('FW', 'SW', 'FW/SW'):
        SCHLUESSEL[englisch + waehrung] = deutsch + waehrung

WERTE = {
    'side': {'receivable': 'forderungen', 'payable': 'verbindlichkeiten', 'all': 'alle'},
    'history_status': {'unknown': 'unbekannt', 'reconciled': 'abgeglichen', 'mismatch': 'abweichend'},
    'aging_bucket': {
        'unknown_balance': 'saldo_unbekannt', 'credit': 'guthaben', 'settled': 'ausgeglichen',
        'unknown_due_date': 'faelligkeit_unbekannt', 'not_due': 'nicht_faellig',
        '1_30': '1_bis_30_tage', '31_60': '31_bis_60_tage', '61_90': '61_bis_90_tage',
        'over_90': 'ueber_90_tage',
    },
    'status': {
        'stored': 'gespeichert', 'ambiguous': 'mehrdeutig',
        'partial_reconstruction': 'teilrekonstruktion', 'unsupported': 'nicht_unterstuetzt',
        'unknown': 'unbekannt', 'reconciled': 'abgeglichen', 'mismatch': 'abweichend',
    },
    'kind': {
        'assessment_base': 'bemessungsgrundlage', 'tax': 'steuer',
        'flag': 'kennzeichen', 'unknown': 'unbekannt',
    },
    'source': {'journal_reconstruction': 'journalrekonstruktion'},
}


def _schluessel(name):
    if not isinstance(name, str):
        return name
    if name.endswith('_label'):
        return _schluessel(name[:-6]) + '_bezeichnung'
    return SCHLUESSEL.get(name, name)


def _wert(feld, wert):
    # Nur bekannte abgeleitete Statusfelder übersetzen, niemals beliebige Belegtexte.
    if isinstance(wert, str):
        if feld == 'output_column':
            return _schluessel(wert)
        return WERTE.get(feld, {}).get(wert, wert)
    return wert


def deutsche_ausgabe(wert, *, rohe_spalten=False):
    """Übersetzt eigene Metadaten, nicht gespeicherte Zellen oder SQL-Benutzeraliase."""
    if isinstance(wert, list):
        return [deutsche_ausgabe(eintrag, rohe_spalten=rohe_spalten) for eintrag in wert]
    if not isinstance(wert, dict):
        return wert
    ergebnis = {}
    spalten = wert.get('columns')
    for feld, inhalt in wert.items():
        if feld == 'rows' and isinstance(spalten, list):
            # Rohdatenzellen bleiben unverändert. Nur eigene abgeleitete Enumspalten
            # dürfen übersetzte Werte erhalten; freie SQL-Abfragen sind ausgenommen.
            inhalt = [
                [zelle if rohe_spalten else _wert(spalte, zelle)
                 for spalte, zelle in zip(spalten, zeile)]
                for zeile in inhalt
            ]
        elif feld in ('columns', 'money_fields') and isinstance(inhalt, list):
            inhalt = list(inhalt) if rohe_spalten else [_schluessel(spalte) for spalte in inhalt]
        elif feld == 'tools':
            inhalt = [WERKZEUGNAMEN.get(name, name) for name in inhalt]
        else:
            inhalt = _wert(feld, deutsche_ausgabe(inhalt, rohe_spalten=rohe_spalten))
        ergebnis[_schluessel(feld)] = inhalt
    return ergebnis
