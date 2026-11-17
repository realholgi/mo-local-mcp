"""Steuernachweise aus dem MonKey-Datenbankstand nur lesen; keine ELSTER-Abgabe."""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from .business import _dates, _integer, _packed_strings


# Deutsche UVA-Bemessungs-/Steuerfelder aus ELSTERMELDUNG. Unbekannte Codes bleiben unverändert.
_BASE_CODES = {'81', '86', '35', '77', '76', '41', '44', '49', '43', '48',
               '91', '89', '93', '95', '94', '46', '73', '84', '42', '60', '21', '45'}
_TAX_CODES = {'87', '36', '80', '90', '98', '96', '47', '74', '85', '66', '61',
              '62', '67', '63', '59', '64', '65', '69', '39', '83'}
_FLAGS = {'10', '22', '29', '26', '50', '37'}
_MONEY_COLUMNS = {'BetragSoll', 'BetragHaben', 'BetragSollFW', 'BetragHabenFW',
                  'IV_BetragSoll', 'IV_BetragHaben', 'BetragBemSoll', 'BetragBemHaben'}


def _money(value):
    return format(Decimal(str(value)) / 100, '.2f') if value is not None else None


def _records(page):
    return [dict(zip(page['columns'], row)) for row in page['rows']]


def _all(reader, sql, bindings):
    rows, offset = [], 0
    while True:
        page = reader._page(sql, bindings, 500, offset)
        rows.extend(_records(page))
        if page['next_offset'] is None:
            if page['truncated']:
                raise ValueError('Eine Steuerquellzeile überschreitet die Ausgabegrenze der Abfrage')
            return rows
        offset = page['next_offset']


_JOURNAL = '''SELECT j._rowid,j.Firma_id,j.Buchung_id,b.Datum,b.Art,b.Status,
 b.Waehrung AS FW_currency,w.Waehrung AS SW_currency,w.Versteuerung AS fiscal_tax_mode,
 j.Position,j.Konto,j.GegenKonto,j.Steuersatz,j.Steuer_id,j.Storno,j.Versteuerung,
 j.SteuerStatus,j.BetragSoll,j.BetragHaben,j.BetragSollFW,j.BetragHabenFW,
 j.IV_Steuersatz,j.IV_BetragSoll,j.IV_BetragHaben,j.IV_Konto,j.IV_KontoUStE,
 j.BetragBemSoll,j.BetragBemHaben,j.DatumVerbucht,
 j.OSS_ISO_LK,j.OSS_Prozent,j.OSS_Typ
 FROM JOURNAL j JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id
 LEFT JOIN WIRTSCHAFTSJAHR w ON w._rowid=b.Wj_id AND w.Firma_id=b.Firma_id'''


def get_tax_journal(reader, company_id, date_from=None, date_to=None, limit=100, offset=0):
    """Journalnachweise aller Perioden einschließlich direkter Steuerbuchungen und Umkehrungen."""
    _integer(company_id, 'firma_id')
    where, bindings = ['j.Firma_id=?'], [company_id]
    _dates(where, bindings, 'b.Datum', date_from, date_to)
    result = reader._page(_JOURNAL + ' WHERE ' + ' AND '.join(where)
                          + ' ORDER BY b.Datum,j.Buchung_id,j.Position,j._rowid', bindings, limit, offset)
    indices = [i for i, name in enumerate(result['columns']) if name in _MONEY_COLUMNS]
    for row in result['rows']:
        for i in indices:
            row[i] = _money(row[i])
    result['money'] = {'columns': [result['columns'][i] for i in indices],
                       'stored_units_per_currency_unit': 100, 'representation': 'Dezimalzeichenkette'}
    result['authority'] = 'Gespeichertes Journal; Buchungsdatum, nicht DatumVerbucht. Alle Statuswerte bleiben erhalten.'
    result['limitations'] = ['Nicht jede Zeile ist steuerpflichtig: Gegenkonten und Aufwands-/Ertragszeilen dürfen nicht zu Steuerkontenzeilen addiert werden.',
                              'Versteuerung, SteuerStatus und versteuerung_geschaeftsjahr sind Rohwerte; der beobachtete Wirtschaftsjahresmodus 2 bedeutet IST.',
                              'IV-Beträge sind gespeicherte Bemessungsbeträge der Istversteuerung in SW, keine zusätzliche Steuer.',
                              'Stornovorzeichen sind bereits gespeichert; nicht erneut umkehren.']
    return result


def _period(year, month, quarter):
    _integer(year, 'jahr')
    if year > 9999 or (month is None) == (quarter is None):
        raise ValueError('Genau einen monat oder ein quartal und ein jahr bis 9999 angeben')
    if month is not None:
        _integer(month, 'monat')
        if month > 12:
            raise ValueError('monat muss zwischen 1 und 12 liegen')
        first = last = month
    else:
        _integer(quarter, 'quartal')
        if quarter > 4:
            raise ValueError('quartal muss zwischen 1 und 4 liegen')
        first, last = 3 * quarter - 2, 3 * quarter
    return date(year, first, 1).isoformat(), date(year, last, monthrange(year, last)[1]).isoformat()


def _stored_values(value):
    if value is None:
        raise ValueError('Gespeicherte Kennzahlen fehlen')
    if value.lstrip().startswith('<'):
        # STEUERERKLAERUNG verwendet jährlich ein anderes XML-Schema. Keine UVA-Zuordnung erraten.
        ElementTree.fromstring(value)
        raise ValueError('Das XML-Kennzahlenschema ist für die UVA nicht nachgewiesen')
    items = _packed_strings(value)
    if len(items) % 2:
        raise ValueError('Abwechselnde UVA-Kennzahl-/Wertfelder erwartet')
    result, seen = [], set()
    for code, raw in zip(items[::2], items[1::2]):
        if not code or code in seen:
            raise ValueError('Fehlende oder doppelte UVA-Kennzahl')
        seen.add(code)
        kind = 'assessment_base' if code in _BASE_CODES else 'tax' if code in _TAX_CODES else 'flag' if code in _FLAGS else 'unknown'
        amount = None
        if kind in ('assessment_base', 'tax'):
            try:
                number = Decimal(raw)
                if not number.is_finite():
                    raise InvalidOperation
                amount = _money(number)
            except (InvalidOperation, ValueError):
                raise ValueError('Ungültiger gespeicherter UVA-Geldwert') from None
        result.append({'code': code, 'raw_value': raw, 'kind': kind, 'amount': amount,
                       'authority': 'ELSTERMELDUNG.Kennzahlen; gespeicherte Meldung, nicht neu berechnet'})
    return result


def get_vat_return(reader, company_id, year, month=None, quarter=None, report_id=None,
                   limit=100, offset=0):
    """Eine nachgewiesene deutsche UVA lesen oder unterstützte Journalfelder rekonstruieren.

    Mehrere gespeicherte Fassungen erfordern meldung_id. Die Rekonstruktion bleibt
    ausdrücklich unvollständig und ist weder abgegebene Erklärung noch geschätzte Zahllast.
    """
    _integer(company_id, 'firma_id')
    _integer(offset, 'versatz', 0)
    _integer(limit, 'anzahl')
    if limit > 500:
        raise ValueError('anzahl darf höchstens 500 sein')
    if report_id is not None:
        _integer(report_id, 'meldung_id')
    start, end = _period(year, month, quarter)
    reports = _all(reader, '''SELECT _rowid,Firma_id,Verfahren,DatenArt,Vorgang,Jahr,
        Zeitraum,ZeitraumCode,DatumVon,DatumBis,Berechnungsart,Status,Land,SSS,Meldung_id,Kennzahlen
        FROM ELSTERMELDUNG WHERE Firma_id=? AND DatenArt=? AND Verfahren=?
        AND substr(DatumVon,1,10)=? AND substr(DatumBis,1,10)=? ORDER BY _rowid''',
        [company_id, 'Umsatzsteuer-Voranmeldung', 'ElsterAnmeldung', start, end])
    if report_id is not None:
        reports = [r for r in reports if r['_rowid'] == report_id]
        if not reports:
            raise ValueError('meldung_id bezeichnet nicht diese Firma und diesen UVA-Zeitraum')
    result = {'company_id': company_id, 'date_from': start, 'date_to': end,
              'source': 'ELSTERMELDUNG' if reports else 'journal_reconstruction',
              'limitations': ['Gespeicherte Meldungswerte belegen weder eine Übermittlung noch aktuelle steuerrechtliche Richtigkeit.',
                              'Eine jährliche STEUERERKLAERUNG ersetzt keine Voranmeldung.',
                              'ELSTERMELDUNG_NT ist im untersuchten Datenbankstand leer; das TaxReport-Schema ist nicht zugeordnet.']}
    if len(reports) > 1:
        result.update(status='ambiguous', reports=[{k: v for k, v in r.items() if k != 'Kennzahlen'} for r in reports],
                      figures=[], next_offset=None)
        return result
    if reports:
        report = reports[0]
        result['report'] = {k: v for k, v in report.items() if k != 'Kennzahlen'}
        if str(report['Jahr']) != str(year) or report['Land'] != 1:
            result.update(status='unsupported', figures=[], next_offset=None,
                          issues=['Die gespeicherte Zeitraumidentität enthält ein widersprüchliches Jahr oder ein nicht unterstütztes Land'])
            return result
        try:
            figures = _stored_values(report['Kennzahlen'])
        except (ValueError, ElementTree.ParseError) as error:
            result.update(status='unsupported', figures=[], next_offset=None, issues=[str(error)])
            return result
        result['status'] = 'stored'
        result['limitations'].append('Bekannte Geldfelder sind in Hundertsteln gespeichert; Kennzeichen und unbekannte Werte bleiben unskaliert. Keine Rundung für die Abgabe.')
    else:
        modern = reader.database.query(
            '''SELECT _rowid,Method,DataType,Process,DateFrom,DateTo,Status,Report_id
            FROM ELSTERMELDUNG_NT WHERE Firma_id=? AND substr(DateFrom,1,10)=?
            AND substr(DateTo,1,10)=? ORDER BY _rowid''', [company_id, start, end], 500)
        if modern['rows'] or modern['truncated']:
            result.update(status='unsupported', source='ELSTERMELDUNG_NT',
                          reports=modern, figures=[], next_offset=None,
                          issues=['Identität und Schema des neueren TaxReport sind nicht nachgewiesen; keine ersatzweise Rekonstruktion'])
            return result
        figures, issues, coverage = _reconstruct(reader, company_id, start, end)
        result.update(status='partial_reconstruction', issues=issues, coverage=coverage)
        result['limitations'].extend(['Nur eindeutige aktuelle Steuerkontenzuordnungen dieser Firma werden rekonstruiert; historische Zuordnungsänderungen sind nicht nachweisbar.',
                                     'Keine Steuerberechnung durch Multiplikation von Ertrags-/Aufwandszeilen mit einem Steuersatz; weder Abrechnungskennzahl 83 noch Abgaberundung werden erzeugt.'])
    result['figures'] = figures[offset:offset + limit]
    result['next_offset'] = offset + limit if offset + limit < len(figures) else None
    result['figure_count'] = len(figures)
    return result


def _reconstruct(reader, company_id, start, end):
    rates = _all(reader, '''SELECT _rowid,Name,Typ,KontoSteuer1,KontoSteuer2,KontoSteuerNF,
        UVASteuer1,UVASteuer2,UVABemessung1,UVABemessung2,OSS
        FROM STEUERSATZ WHERE Firma_id=? ORDER BY _rowid''', [company_id])
    accounts, non_due = {}, set()
    for rate in rates:
        if rate['KontoSteuerNF']:
            non_due.add(rate['KontoSteuerNF'])
        for slot in (1, 2):
            account = rate[f'KontoSteuer{slot}']
            if account:
                accounts.setdefault(account, []).append((rate, rate[f'UVASteuer{slot}'], rate[f'UVABemessung{slot}']))
    rows = _all(reader, _JOURNAL + ' WHERE j.Firma_id=? AND b.Datum>=? AND b.Datum<=? ORDER BY j._rowid', [company_id, start, end])
    totals, issues = {}, []
    coverage = {'journal_rows': len(rows), 'tax_rows_included': 0, 'non_due_rows_excluded': 0,
                'opening_rows_excluded': 0, 'unmapped_tax_rows': 0}

    def add(code, kind, value, row, actual_tax=None):
        if code not in (_BASE_CODES if kind == 'assessment_base' else _TAX_CODES):
            issues.append({'journal_id': row['_rowid'], 'reason': 'Nicht unterstützte UVA-Kennzahl oder Kennzahlenart', 'code': code})
            return
        key = (code, kind, row['SW_currency'])
        item = totals.setdefault(key, {'total': Decimal(0), 'ids': [], 'actual_tax': None})
        item['total'] += value
        if actual_tax is not None:
            item['actual_tax'] = (item['actual_tax'] or Decimal(0)) + actual_tax
        item['ids'].append(row['_rowid'])

    for row in rows:
        if row['Art'] == 2:
            coverage['opening_rows_excluded'] += 1
            continue
        if row['Konto'] in non_due and row['Konto'] not in accounts:
            coverage['non_due_rows_excluded'] += 1
            continue
        candidates = accounts.get(row['Konto'], [])
        iv_code = row['IV_Steuersatz']
        if iv_code and iv_code != '-':
            candidates = [c for c in candidates if c[0]['Name'].casefold() == iv_code.casefold()]
        if not candidates:
            if row['Steuersatz'] not in (None, '', '-') or iv_code not in (None, '', '-'):
                coverage['unmapped_tax_rows'] += 1
                issues.append({'journal_id': row['_rowid'], 'reason': 'Zeile mit Steuercode nicht als Steuer verwendet: keine Zuordnung zu einem fälligen Steuerkonto'})
            continue
        signatures = {(c[0]['Typ'], c[1] or '', c[2] or '', bool(c[0]['OSS'])) for c in candidates}
        if len(signatures) != 1:
            issues.append({'journal_id': row['_rowid'], 'reason': 'Mehrdeutige Steuerkontenzuordnung'})
            continue
        typ, code, base_code, oss = signatures.pop()
        if typ not in (1, 2) or oss or row['SW_currency'] is None or row['BetragSoll'] is None or row['BetragHaben'] is None:
            issues.append({'journal_id': row['_rowid'], 'reason': 'Nicht unterstützter Steuertyp, OSS, Währung oder fehlender Betrag'})
            continue
        tax = Decimal(str(row['BetragHaben'])) - Decimal(str(row['BetragSoll']))
        if typ == 2:
            tax = -tax
        coverage['tax_rows_included'] += 1
        # IV-Haben/-Soll einer Zahlung enthält die tatsächliche Bemessungsgrundlage;
        # Rechnungsbuchungen auf KontoSteuerNF sind ausdrücklich keine fällige Steuer.
        if iv_code not in (None, '', '-'):
            base = None if row['IV_BetragHaben'] is None or row['IV_BetragSoll'] is None else Decimal(str(row['IV_BetragHaben'])) - Decimal(str(row['IV_BetragSoll']))
            if typ == 2 and base is not None:
                base = -base
        else:
            # BetragBem* enthält bei beobachteten erzeugten Steuerzeilen eine Bemessung ohne Vorzeichen.
            # Die Richtung folgt dem Steuerkontensaldo einschließlich Erstattungen.
            raw = None if row['BetragBemSoll'] is None or row['BetragBemHaben'] is None else Decimal(str(row['BetragBemSoll'])) - Decimal(str(row['BetragBemHaben']))
            base = abs(raw) * (1 if tax > 0 else -1) if raw and tax else None
        if code in _BASE_CODES:
            if base is None:
                issues.append({'journal_id': row['_rowid'], 'reason': 'Nachgewiesene Bemessungsgrundlage für direkte Steuerbuchung fehlt', 'code': code, 'actual_tax': _money(tax)})
            else:
                add(code, 'assessment_base', base, row, actual_tax=tax)
        elif code:
            add(code, 'tax', tax, row)
        else:
            issues.append({'journal_id': row['_rowid'], 'reason': 'Dem Steuerkonto ist keine UVA-Kennzahl zugeordnet', 'actual_tax': _money(tax)})
        if base_code:
            if base is None:
                issues.append({'journal_id': row['_rowid'], 'reason': 'Bemessungsgrundlage fehlt', 'code': base_code})
            else:
                add(base_code, 'assessment_base', base, row)
    figures = [{'code': code, 'kind': kind, 'currency': currency, 'amount': _money(item['total']),
                'actual_tax': _money(item['actual_tax']),
                'journal_ids': item['ids'], 'authority': 'Teilrekonstruktion aus tatsächlichen Steuerkontenbeträgen und gespeicherten Bemessungsfeldern'}
               for (code, kind, currency), item in sorted(totals.items())]
    return figures, issues, coverage
