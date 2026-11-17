"""Connect-Stammdaten und ausdrücklich lokale, lesende kustus-Erweiterungen.

Alle IDs bezeichnen lokale Zeilen, keine ursprünglichen Connect-IDs. Die Methoden
kostenstellenList, buchungKontoList, debitorList und kreditorList sind keine
Hersteller-API: offizielle Konten/Kostenstellen werden über vorgabenGet angeboten,
Debitoren-/Kreditorenbelege über debitorenRechnungList/kreditorenRechnungList.
"""

METHODS = frozenset({
    'firmaList', 'firmaGet', 'adresseList', 'adresseGet', 'artikelList',
    'projektList', 'kostenstellenList', 'buchungKontoList', 'debitorList', 'kreditorList',
})
EXTENSIONS = frozenset({'kostenstellenList', 'buchungKontoList', 'debitorList', 'kreditorList'})

_ADDRESS_LIST = {
    'Adresse_ID': '_rowid', 'Matchcode': 'KZ_Matchcode', 'AdressNr': 'KZ_AdressNr',
    'Kategorie': 'KZ_Kategorie', 'KundenStatus': 'KF_Status', 'LieferantenStatus': 'LF_Status',
    **{name: name for name in ('RA_Firma1', 'RA_Vorname', 'RA_Nachname', 'RA_Plz',
                               'RA_Ort', 'RA_Strasse', 'RA_StrasseNr')},
}
_ADDRESS_DETAIL = {
    **_ADDRESS_LIST,
    **{name: name for name in (
        'RA_Firma2', 'RA_Anrede', 'RA_Zusatz', 'RA_Geschlecht', 'RA_Land', 'RA_LandISO',
        'RA_PostfachPlz', 'RA_PostfachNr', 'RA_PfVerwenden', 'RA_Telefon1', 'RA_Telefon2',
        'RA_Telefon3', 'RA_Telefax', 'RA_Email', 'RA_Internet', 'LA_Firma1', 'LA_Firma2',
        'LA_LaVerwenden', 'LA_Anrede', 'LA_Vorname', 'LA_Nachname', 'LA_Zusatz',
        'LA_Strasse', 'LA_StrasseNr', 'LA_Plz', 'LA_Ort', 'LA_Land', 'LA_PostfachPlz',
        'LA_PostfachNr', 'LA_PfVerwenden', 'LA_Telefon', 'LA_Telefax', 'LA_Email',
        'LA_Lieferart', 'KF_Konto', 'KF_Sammelkonto', 'KF_Waehrung', 'KF_FinanzKonto',
        'KF_Preisangabe', 'KF_KoSt1', 'KF_KoSt2', 'KF_ExterneNr', 'KF_Lieferstopp',
        'KF_Rabatt', 'LF_Konto', 'LF_Sammelkonto', 'LF_Waehrung', 'LF_FinanzKonto',
        'LF_Preisangabe', 'LF_KoSt1', 'LF_KoSt2', 'LF_ExterneNr', 'LF_Bestellstopp',
        'LF_Rabatt', 'Mail_Preferred')},
    'KF_Zahlungsbedingungen': 'KF_Zahlungsbedingung', 'KF_Ertragkonto': 'KF_ErtrKonto',
    'LF_Zahlungsbedingungen': 'LF_Zahlungsbedingung', 'LF_Aufwandkonto': 'LF_AufwKonto',
    'Steuergebiet': 'SO_Steuergebiet', 'UStID': 'SO_UStID', 'Belegsprache': 'SO_Belegsprache',
    'Briefanrede': 'SO_BriefAnrede', 'Briefgruss': 'SO_BriefGruss', 'Notizen': 'SO_Bemerkung',
    'Belegausgabe': 'ER_Ausgabetyp', 'ERechnungProfil': 'ER_Ausgabeprofil',
    'LeitwegID': 'RA_XRLeitwegID',
}
_ADDRESS_SEARCH = ('KZ_AdressNr', 'KZ_Matchcode', 'RA_Firma1', 'RA_Firma2',
                   'RA_Vorname', 'RA_Nachname', 'RA_Ort', 'RA_Plz')
_COMPANY_FIELDS = (
    'Name', 'Zusatz', 'Geschaeftsfuehrer', 'Strasse', 'Plz', 'Ort', 'Telefon',
    'Telefax', 'Email', 'Internet', 'UStPflicht', 'UStIDNummer', 'Kontenplan', 'GEArt',
    'FALand', 'FANummer', 'FAName', 'FAZusatz', 'FAStrasse', 'FAPlz', 'FAOrt',
    'FABundesland', 'FASteuernummer', 'FATelefon', 'FATelefax', 'FABankName',
    'FABankIBAN', 'FABankBIC', 'FAMemo', 'SBName', 'SBZusatz', 'SBStrasse', 'SBPlz',
    'SBOrt', 'SBTelefon', 'SBTelefax', 'SBEmail', 'SBBankName', 'SBBankIBAN',
    'SBBankBIC', 'SBMemo', 'FALandLSt', 'FANummerLSt', 'FANameLSt', 'FAZusatzLSt',
    'FAStrasseLSt', 'FAPlzLSt', 'FAOrtLSt', 'FABundeslandLSt', 'FASteuernummerLSt',
    'FATelefonLSt', 'FATelefaxLSt', 'FABankNameLSt', 'FABankIBANLSt', 'FABankBICLSt',
    'FAMemoLSt',
)


def _id(value, name):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(name + ' muss eine positive lokale ID sein')
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError(name + ' muss eine positive lokale ID sein')
    result = int(value)
    if not 0 < result <= 9223372036854775807:
        raise ValueError(name + ' muss eine positive lokale ID sein')
    return result


def _select(reader, table, mapping):
    # Nur belegte Felder auswählen; fehlende Spalten werden nicht mit Fantasiewerten ergänzt.
    columns = reader.columns(table)
    fields = {key: value for key, value in mapping.items() if value in columns}
    if not fields:
        raise ValueError('Keine abbildbaren Spalten in ' + table)
    return ', '.join('"' + value + '" AS "' + key + '"' for key, value in fields.items())


def _items(reader, table, mapping, clauses, bindings, order='_rowid'):
    sql = 'SELECT ' + _select(reader, table, mapping) + ' FROM ' + table
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    result = reader.rows(sql + ' ORDER BY ' + order, bindings)
    for row in result:
        for key in row:
            if key.endswith('_ID') and row[key] is not None:
                row[key] = str(row[key])
    return result


def _text(reader, filters, key, columns, clauses, bindings):
    if key in filters:
        if not isinstance(filters[key], str):
            raise ValueError(key + ' muss eine Zeichenkette sein')
        reader.search(filters[key], columns, clauses, bindings)


def _role(filters, key, column, clauses, bindings):
    if key not in filters:
        return
    value = filters[key]
    if type(value) is not int or value not in {-2, -1, 0, 1, 2, 3}:
        raise ValueError(key + ' muss -2, -1 oder 0 bis 3 sein')
    if value == -1:
        clauses.append(column + ' IN (1,2,3)')
    elif value != -2:
        clauses.append(column + ' = ?')
        bindings.append(value)


def _extension(data, basis):
    return {**data, 'LokaleLeseerweiterung': True, 'Basis': basis}


def _parties(reader, method, params, firma_id):
    debit = method == 'debitorList'
    prefix = 'Debitor' if debit else 'Kreditor'
    key = prefix + 'Filter'
    reader.require(params, {key})
    filters = reader.filter(params, key, {'DatumVon', 'DatumBis', 'Adresse_ID'})
    clauses, bindings = ['Firma_id = ?', ('KF_Status' if debit else 'LF_Status') + ' IN (1,2,3)'], [firma_id]
    address_id = None
    if 'Adresse_ID' in filters:
        address_id = _id(filters['Adresse_ID'], 'Adresse_ID')
        clauses.append('_rowid = ?')
        bindings.append(address_id)
    mapping = {**_ADDRESS_LIST, 'Konto': 'KF_Konto' if debit else 'LF_Konto'}
    parties = _items(reader, 'ADRESSE', mapping, clauses, bindings)
    where, values = ['p.Firma_id = ?', 'p.Art IN (' + ('0,1' if debit else '2,3') + ')',
                     'coalesce(p.Entwurf,0) = 0'], [firma_id]
    reader.dates(filters, where, values, column='p.Datum')
    if address_id is not None:
        where.append('p.Adress_id = ?')
        values.append(address_id)
    # POSTEN.Adress_id ist die eindeutige Zuordnung, nicht das möglicherweise geteilte PKonto.
    totals = reader.rows('''SELECT p.Adress_id, p.Waehrung,
        CASE WHEN count(p.OffenFW) = count(*) THEN sum(p.OffenFW) END AS SaldoFW,
        CASE WHEN count(p.OffenSW) = count(*) THEN sum(p.OffenSW) END AS SaldoSW,
        count(*) AS Beleganzahl FROM POSTEN p
        JOIN ADRESSE a ON a._rowid = p.Adress_id AND a.Firma_id = p.Firma_id
        WHERE ''' + ' AND '.join(where) + ' GROUP BY p.Adress_id,p.Waehrung ORDER BY p.Adress_id,p.Waehrung', values)
    grouped = {}
    for row in totals:
        grouped.setdefault(str(row['Adress_id']), []).append({
            'Waehrung': row['Waehrung'], 'SaldoFW': reader.money(row['SaldoFW']),
            'SaldoSW': reader.money(row['SaldoSW']), 'Beleganzahl': row['Beleganzahl'],
        })
    for row in parties:
        row['Salden'] = grouped.get(row['Adresse_ID'], [])
    return _extension({prefix + 'ListItem': parties},
        'Aktuell gespeicherte OP-Restbeträge der Rechnungen und vorzeichenbehafteten Gutschriften; '
        'Entwürfe ausgeschlossen. DatumVon/DatumBis filtern das Belegdatum, nicht den Zahlungsstand. '
        'Kein historischer Stichtagssaldo. Waehrung bezeichnet FW; SW bleibt separat. '
        'Fehlende Restbeträge ergeben null; keine Belege ergeben eine leere Saldenliste.')


def handle(reader, method, params, firma_id):
    """ReturnData für die unterstützte Methode aus dem unveränderten Datenstand liefern."""
    if method not in METHODS:
        raise ValueError('Unbekannte Stammdatenmethode: ' + method)
    if method == 'firmaList':
        reader.require(params, set())
        return {'FirmaListItem': _items(reader, 'FIRMA', {
            'Firma_ID': '_rowid', 'Bezeichnung': 'Name', 'Zusatz': 'Zusatz'}, [], [])}
    firma_id = reader.company(firma_id)
    if method == 'firmaGet':
        reader.require(params, set())
        mapping = {'Firma_' + name: name for name in _COMPANY_FIELDS}
        mapping.update({'Firma_RegisterGericht': 'Registergericht', 'Firma_RegisterNummer': 'Registernummer'})
        mapping.update({'Firma_LG' + suffix: 'Lg' + suffix for suffix in (
            'Name', 'Zusatz', 'Verwalter', 'Strasse', 'Plz', 'Ort', 'Telefon', 'Telefax', 'Email')})
        return {'FirmaItem': _items(reader, 'FIRMA', mapping, ['_rowid = ?'], [firma_id])[0]}
    if method in {'debitorList', 'kreditorList'}:
        return _parties(reader, method, params, firma_id)
    if method == 'adresseGet':
        reader.require(params, {'Adresse_ID'})
        address_id = _id(params.get('Adresse_ID'), 'Adresse_ID')
        rows = _items(reader, 'ADRESSE', _ADDRESS_DETAIL,
                      ['Firma_id = ?', '_rowid = ?'], [firma_id, address_id])
        if not rows:
            raise ValueError('Adresse in dieser Firma nicht gefunden')
        return {'AdresseItem': rows[0]}
    clauses, bindings = ['Firma_id = ?'], [firma_id]
    if method == 'adresseList':
        reader.require(params, {'AdresseFilter'})
        filters = reader.filter(params, 'AdresseFilter', {'Suchtext', 'Matchcode', 'KundenStatus', 'LieferantenStatus'})
        _text(reader, filters, 'Suchtext', _ADDRESS_SEARCH, clauses, bindings)
        _text(reader, filters, 'Matchcode', ('KZ_Matchcode',), clauses, bindings)
        _role(filters, 'KundenStatus', 'KF_Status', clauses, bindings)
        _role(filters, 'LieferantenStatus', 'LF_Status', clauses, bindings)
        return {'AdresseListItem': _items(reader, 'ADRESSE', _ADDRESS_LIST, clauses, bindings)}
    if method == 'artikelList':
        reader.require(params, {'ArtikelFilter'})
        filters = reader.filter(params, 'ArtikelFilter', {'Suchtext', 'Artikelart', 'nurLagerArtikel', 'Warengruppe'})
        _text(reader, filters, 'Suchtext', ('ArtikelNr', 'Matchcode', 'Bezeichnung', 'Beschreibung'), clauses, bindings)
        _text(reader, filters, 'Warengruppe', ('Warengruppe',), clauses, bindings)
        if 'Artikelart' in filters:
            if type(filters['Artikelart']) is not int or filters['Artikelart'] not in {1, 2}:
                raise ValueError('Artikelart muss 1 oder 2 sein')
            clauses.append('Art = ?')
            bindings.append(filters['Artikelart'])
        if 'nurLagerArtikel' in filters:
            if type(filters['nurLagerArtikel']) is not bool:
                raise ValueError('nurLagerArtikel muss ein boolescher Wert sein')
            if filters['nurLagerArtikel']:
                clauses.append('Lagerartikel = 1')
        return {'ArtikelListItem': _items(reader, 'ARTIKEL', {
            'Artikel_ID': '_rowid', 'Matchcode': 'Matchcode', 'ArtikelArt': 'Art',
            'ArtikelNr': 'ArtikelNr', 'Warengruppe': 'Warengruppe', 'Bezeichnung': 'Bezeichnung',
        }, clauses, bindings)}
    if method == 'projektList':
        reader.require(params, {'ProjektFilter'})
        filters = reader.filter(params, 'ProjektFilter', {'Suchtext'})
        _text(reader, filters, 'Suchtext', ('ProjektNr', 'Bezeichnung', 'Beschreibung'), clauses, bindings)
        return {'ProjektListItem': _items(reader, 'PROJEKT', {
            'Projekt_ID': '_rowid', 'ProjektNr': 'ProjektNr', 'Bezeichnung': 'Bezeichnung',
            'DatumVon': 'DatumStart', 'DatumBis': 'DatumEnde', 'ProjektStatus': 'Status',
        }, clauses, bindings)}
    if method == 'kostenstellenList':
        reader.require(params, set())
        return _extension({'KostenstelleListItem': _items(reader, 'KOSTENSTELLE', {
            'Kostenstelle_ID': '_rowid', **{name: name for name in (
                'Name', 'Beschreibung', 'Bemerkung', 'Buchungssperre')},
        }, clauses, bindings)}, 'Gespeicherte Kostenstellen einschließlich Buchungssperren; lokale Leseerweiterung.')
    reader.require(params, {'BuchungKontoFilter'})
    filters = reader.filter(params, 'BuchungKontoFilter', {'Suchtext', 'KontoVon', 'KontoBis'})
    _text(reader, filters, 'Suchtext', ('Nummer', 'Bezeichnung', 'Bemerkung'), clauses, bindings)
    for key, operator in (('KontoVon', '>='), ('KontoBis', '<=')):
        if key in filters:
            if type(filters[key]) is not int or not 0 <= filters[key] <= 9223372036854775807:
                raise ValueError(key + ' muss eine nicht negative Kontonummer sein')
            clauses.append('Nummer ' + operator + ' ?')
            bindings.append(filters[key])
    if 'KontoVon' in filters and 'KontoBis' in filters and filters['KontoVon'] > filters['KontoBis']:
        raise ValueError('KontoVon darf nicht nach KontoBis liegen')
    return _extension({'BuchungKontoListItem': _items(reader, 'KONTO', {
        'Konto_ID': '_rowid', **{name: name for name in (
            'Nummer', 'Bezeichnung', 'Typ', 'Steuertyp', 'Bemerkung', 'Buchungssperre', 'Waehrung')},
    }, clauses, bindings, 'Nummer,_rowid')},
        'Gespeicherter Kontenstamm einschließlich unbebuchter Konten; keine geschätzten Salden. Lokale Leseerweiterung.')
