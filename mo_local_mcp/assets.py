"""Gespeicherte Anlagen und Abschreibungsbewegungen ohne Neuberechnung lesen."""

from .business import _currency_amounts, _dates, _integer
from .masters import _search


BASIS = [
    'Gespeicherte Anlagenstammdaten und Bewegungspläne; keine Neuberechnung von Abschreibungen oder steuerlicher Zulässigkeit.',
    'Zukünftige, ungebuchte, historische und Abgangsbewegungen bleiben ohne ausdrückliche Filter erhalten. Gebucht ist das gespeicherte Buchungskennzeichen, kein unabhängiger Abgleich mit der Finanzbuchhaltung.',
    'BuchwertNeu gehört zum jeweiligen Bewegungsdatum; der letzte zukünftige Planwert ist nicht der aktuelle Buchwert. Datumsfilter wählen Bewegungen aus, keine historischen Stammdatenstände.',
    'Geldwerte werden durch 100 geteilt, einschließlich numerischer Texte in BuchwertNeu. Prozentsätze, Monate, Kontonummern und IDs werden nicht skaliert.',
    'Keine der beiden Anlagentabellen speichert eine Währung. Es werden weder Währungsumrechnungen noch währungsübergreifende Summen abgeleitet.',
]


def list_assets(reader, company_id, search='', limit=100, offset=0):
    _integer(company_id, 'firma_id')
    columns = ('a._rowid', 'a.SD_InventarNr', 'a.SD_Bezeichnung', 'a.SD_Standort',
               'a.SD_SerienNr', 'a.SD_Kostenstelle', 'a.SD_Zusatzangaben')
    result = reader._page(
        'SELECT a.* FROM ANLAGE a WHERE a.Firma_id=? AND ' + _search(columns)
        + ' ORDER BY a.SD_InventarNr,a._rowid',
        [company_id, *([search] * len(columns))], limit, offset,
    )
    result['basis'] = list(BASIS)
    return _currency_amounts(result, 'ANLAGE')


def get_depreciation_schedule(reader, company_id, asset_id=None, date_from=None,
                              date_to=None, booked_only=False, limit=100, offset=0):
    _integer(company_id, 'firma_id')
    where, bindings = ['p.Firma_id=?'], [company_id]
    if asset_id is not None:
        _integer(asset_id, 'anlage_id')
        where.append('p.Anlage_id=?')
        bindings.append(asset_id)
    _dates(where, bindings, 'p.Datum', date_from, date_to)
    if booked_only:
        where.append('p.Gebucht=1')
    result = reader._page(
        'SELECT p.*,a.SD_InventarNr,a.SD_Bezeichnung,a.SD_KontoAnlage,a.SD_KontoAfa '
        'FROM ANLAGENPOSITION p JOIN ANLAGE a '
        'ON a._rowid=p.Anlage_id AND a.Firma_id=p.Firma_id WHERE '
        + ' AND '.join(where)
        + ' ORDER BY a.SD_InventarNr,a._rowid,p.Position,p._rowid',
        bindings, limit, offset,
    )
    result['basis'] = list(BASIS)
    return _currency_amounts(result, 'ANLAGENPOSITION')


def get_asset(reader, company_id, asset_id, limit=100, offset=0):
    _integer(company_id, 'firma_id')
    _integer(asset_id, 'anlage_id')
    header = reader.database.query(
        'SELECT * FROM ANLAGE WHERE Firma_id=? AND _rowid=?', [company_id, asset_id], 1,
    )
    if not header['rows']:
        if header['truncated']:
            raise ValueError('Anlagenkopf überschreitet die Ausgabegrenze; mit einer gezielten SQL-Abfrage weniger Spalten auswählen')
        raise ValueError('Anlage in dieser Firma nicht gefunden')
    return {
        'asset': _currency_amounts(header, 'ANLAGE'),
        'movements': get_depreciation_schedule(reader, company_id, asset_id, limit=limit, offset=offset),
        'basis': list(BASIS),
    }
