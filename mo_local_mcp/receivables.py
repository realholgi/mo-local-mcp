"""Stichtagsbezogene OP-Rekonstruktion und Altersstruktur aus Belegen und Zuordnungen."""

from datetime import date

from .business import OPEN_ITEM_TYPES, _currency_amounts, _integer, _labels


DERIVED_MONEY = {
    prefix + suffix
    for prefix in ('paid_as_of_', 'reduction_as_of_', 'calculated_open_', 'open_as_of_')
    for suffix in ('FW', 'SW')
} | {'open_FW', 'open_SW'}

# Die Gültigkeit wird anhand der gesamten gespeicherten Zuordnungshistorie geprüft,
# nicht nur vor dem Stichtag. Ein Restbetrag im Belegkopf erhält kein geschätztes Datum.
OP_AS_OF_SQL = """
WITH params AS (SELECT ? AS cutoff, ? AS company),
allocations AS (
    SELECT pp.Posten_id,
        sum(coalesce(zp.BetragZahlFW,0)) AS paid_FW,
        sum(coalesce(zp.BetragZahlSW,0)) AS paid_SW,
        sum(coalesce(zp.BetragMindFW,0)) AS reduced_FW,
        sum(coalesce(zp.BetragMindSW,0)) AS reduced_SW,
        sum(CASE WHEN z.Datum<=v.cutoff THEN coalesce(zp.BetragZahlFW,0) ELSE 0 END) AS past_paid_FW,
        sum(CASE WHEN z.Datum<=v.cutoff THEN coalesce(zp.BetragZahlSW,0) ELSE 0 END) AS past_paid_SW,
        sum(CASE WHEN z.Datum<=v.cutoff THEN coalesce(zp.BetragMindFW,0) ELSE 0 END) AS past_reduced_FW,
        sum(CASE WHEN z.Datum<=v.cutoff THEN coalesce(zp.BetragMindSW,0) ELSE 0 END) AS past_reduced_SW,
        sum(CASE WHEN date(z.Datum) IS NULL OR zp.BetragZahlFW IS NULL OR zp.BetragZahlSW IS NULL
                      OR zp.BetragMindFW IS NULL OR zp.BetragMindSW IS NULL THEN 1 ELSE 0 END) AS undated_allocations,
        sum(CASE WHEN z.Datum<p.Datum AND z.Datum<=v.cutoff THEN 1 ELSE 0 END) AS pre_document_allocations
    FROM ZAHLUNGSPOSITION zp
    JOIN ZAHLUNG z ON z._rowid=zp.Zahlung_id AND z.Firma_id=zp.Firma_id
    JOIN POSTENPOSITION pp ON pp._rowid=zp.Postenposition_id AND pp.Firma_id=zp.Firma_id
    JOIN POSTEN p ON p._rowid=pp.Posten_id AND p.Firma_id=pp.Firma_id
    CROSS JOIN params v
    WHERE zp.Firma_id=v.company
    GROUP BY pp.Posten_id
),
source AS (
    SELECT p._rowid,p.Firma_id,p.Art,p.Adress_id,p.ReNr,p.Datum,p.PKonto,p.BuText,p.Waehrung,
        p.GesamtBruttoFW,p.GesamtBruttoSW,p.BezahltFW,p.BezahltSW,
        p.MinderungFW,p.MinderungSW,p.OffenFW,p.OffenSW,
        p.TageNetto,p.NichtMahnen,p.Mahnstufe,p.DatumMahnung1,p.DatumMahnung2,p.DatumMahnung3,p.DatumMahnung4,
        CASE WHEN p.Art IN (0,1) THEN 'receivable' ELSE 'payable' END AS side,
        coalesce(a.past_paid_FW,0) AS paid_as_of_FW,coalesce(a.past_paid_SW,0) AS paid_as_of_SW,
        coalesce(a.past_reduced_FW,0) AS reduction_as_of_FW,coalesce(a.past_reduced_SW,0) AS reduction_as_of_SW,
        p.GesamtBruttoFW-coalesce(a.past_paid_FW,0)-coalesce(a.past_reduced_FW,0) AS calculated_open_FW,
        p.GesamtBruttoSW-coalesce(a.past_paid_SW,0)-coalesce(a.past_reduced_SW,0) AS calculated_open_SW,
        coalesce(a.pre_document_allocations,0) AS pre_document_allocations,
        CASE WHEN coalesce(a.undated_allocations,0)>0 OR p.BezahltFW IS NULL OR p.BezahltSW IS NULL
                  OR p.GesamtBruttoFW IS NULL OR p.GesamtBruttoSW IS NULL
                  OR p.MinderungFW IS NULL OR p.MinderungSW IS NULL THEN 'unknown'
             WHEN p.BezahltFW=coalesce(a.paid_FW,0) AND p.BezahltSW=coalesce(a.paid_SW,0)
                  AND p.MinderungFW=coalesce(a.reduced_FW,0) AND p.MinderungSW=coalesce(a.reduced_SW,0)
             THEN 'reconciled' ELSE 'mismatch' END AS history_status,
        CASE WHEN p.TageNetto>=0 AND p.TageNetto=CAST(p.TageNetto AS INTEGER)
             THEN date(p.Datum,'+' || CAST(p.TageNetto AS INTEGER) || ' days') END AS due_date,
        max(CASE WHEN date(p.DatumMahnung1)<=v.cutoff THEN 1 ELSE 0 END,
            CASE WHEN date(p.DatumMahnung2)<=v.cutoff THEN 2 ELSE 0 END,
            CASE WHEN date(p.DatumMahnung3)<=v.cutoff THEN 3 ELSE 0 END,
            CASE WHEN date(p.DatumMahnung4)<=v.cutoff THEN 4 ELSE 0 END) AS observed_dunning_level_as_of,
        v.cutoff
    FROM POSTEN p CROSS JOIN params v
    LEFT JOIN allocations a ON a.Posten_id=p._rowid
    WHERE p.Firma_id=v.company AND p.Datum<=v.cutoff AND coalesce(p.Entwurf,0)=0 AND p.Art IN (0,1,2,3)
),
valued AS (
    SELECT *,CASE WHEN history_status='reconciled' THEN calculated_open_FW END AS open_as_of_FW,
        CASE WHEN history_status='reconciled' THEN calculated_open_SW END AS open_as_of_SW
    FROM source
),
aged AS (
    SELECT *,CASE WHEN open_as_of_FW>0 AND due_date IS NOT NULL
                  THEN max(0,CAST(julianday(cutoff)-julianday(due_date) AS INTEGER)) END AS days_overdue,
        CASE WHEN open_as_of_FW>0 AND due_date<cutoff THEN 1
             WHEN open_as_of_FW IS NULL OR (open_as_of_FW>0 AND due_date IS NULL) THEN NULL ELSE 0 END AS overdue
    FROM valued
),
items AS (
    SELECT *,CASE WHEN open_as_of_FW IS NULL THEN 'unknown_balance'
                  WHEN open_as_of_FW<0 THEN 'credit'
                  WHEN open_as_of_FW=0 THEN 'settled'
                  WHEN due_date IS NULL THEN 'unknown_due_date'
                  WHEN days_overdue=0 THEN 'not_due'
                  WHEN days_overdue<=30 THEN '1_30'
                  WHEN days_overdue<=60 THEN '31_60'
                  WHEN days_overdue<=90 THEN '61_90' ELSE 'over_90' END AS aging_bucket,
        CASE WHEN NichtMahnen=1 THEN 0 WHEN NichtMahnen=0 AND open_as_of_FW>0 AND overdue=1 THEN 1
             WHEN NichtMahnen=0 AND overdue=0 THEN 0 ELSE NULL END AS dunning_candidate
    FROM aged
)
"""

BASIS = [
    'Rekonstruktion aus aktuellen Belegbruttobeträgen und datierten, vorzeichenbehafteten Zahlungs-/Minderungszuordnungen; kein historisches Änderungsprotokoll.',
    'Nur Belege bis einschließlich Stichtag; Entwürfe ausgeschlossen. Spätere Zahlungen werden nicht abgezogen. Gutschriften bleiben negativ.',
    'Der Stichtagssaldo bleibt unbekannt (null), wenn Gesamtzahlungen/-minderungen der vollständigen Historie nicht übereinstimmen oder Zuordnungsdaten fehlen; der rechnerische Restbetrag ist dann ausdrücklich unvollständig.',
    'Summen umfassen den gesamten Filter, gruppiert nach Seite und Belegwährung; unbekannte Salden werden gezählt, nicht durch erfundene Nullbeträge ersetzt. FW und SW bleiben getrennt.',
    'Die Fälligkeit ergibt sich aus dem gespeicherten Belegdatum plus TageNetto Kalendertagen, nicht aus aktuellen Zahlungsbedingungsstammdaten; keine gesetzliche oder Wochenendanpassung und keine Feststellung rechtlichen Verzugs.',
    'Mahnstufe und NichtMahnen sind aktuelle Werte des Datenbankstands. Die beobachtete Mahnstufe zum Stichtag berücksichtigt nur datierte Mahnnachweise, keinen vollständigen historischen Mahnzustand.',
    'Mahnkandidaten sind positive, überfällige Rechnungen ohne NichtMahnen-Kennzeichen; Gutschriften sind keine überfälligen Rechnungen. Zuordnungen vor dem Belegdatum werden gekennzeichnet, nicht umgeschrieben.',
]


def _filters(company_id, as_of, side, address_id, include_settled, overdue_only):
    _integer(company_id, 'firma_id')
    if not isinstance(as_of, str) or date.fromisoformat(as_of).isoformat()!=as_of:
        raise ValueError('stichtag muss das Format JJJJ-MM-TT haben')
    if side not in {'receivable','payable','all'}:
        raise ValueError('seite muss Forderungen, Verbindlichkeiten oder alle auswählen')
    if not isinstance(include_settled,bool) or not isinstance(overdue_only,bool):
        raise ValueError('mit_ausgeglichenen und nur_ueberfaellige müssen Wahrheitswerte sein')
    where, bindings = [], [as_of,company_id]
    if side!='all':
        where.append('side=?')
        bindings.append(side)
    if address_id is not None:
        _integer(address_id,'adresse_id')
        where.append('Adress_id=?')
        bindings.append(address_id)
    if not include_settled:
        where.append('(open_as_of_FW IS NULL OR open_as_of_FW<>0)')
    if overdue_only:
        where.append('overdue=1')
    return (' WHERE '+' AND '.join(where) if where else ''),bindings


def _totals(reader, where, bindings):
    # Seitenweise lesen, damit große Firmen-/Währungsbestände keine Summengruppen
    # an der zugrunde liegenden Grenze von 500 Zeilen oder der Ausgabegrenze verlieren.
    rows=[]
    offset=0
    sql=(OP_AS_OF_SQL+'SELECT side,Waehrung,aging_bucket,count(*) AS item_count,'
         'sum(open_as_of_FW) AS open_FW,sum(open_as_of_SW) AS open_SW,'
         'sum(CASE WHEN open_as_of_FW IS NULL OR open_as_of_SW IS NULL THEN 1 ELSE 0 END) AS unknown_balance_count,'
         'sum(CASE WHEN due_date IS NULL THEN 1 ELSE 0 END) AS unknown_due_count '
         'FROM items'+where+' GROUP BY side,Waehrung,aging_bucket ORDER BY side,Waehrung,aging_bucket')
    while True:
        page=reader._page(sql,bindings,500,offset)
        if page['truncated'] and not page['rows']:
            raise ValueError('Eine historische OP-Summenzeile überschreitet die Ausgabegrenze')
        rows.extend(page['rows'])
        if page['next_offset'] is None:
            return _currency_amounts({'columns':page['columns'],'rows':rows,'truncated':False},'POSTEN',DERIVED_MONEY)
        offset=page['next_offset']


def get_open_items_as_of(reader, company_id, as_of, side='receivable', address_id=None,
                         include_settled=False, overdue_only=False, limit=100, offset=0):
    where,bindings=_filters(company_id,as_of,side,address_id,include_settled,overdue_only)
    result=reader._page(OP_AS_OF_SQL+'SELECT * FROM items'+where+
                        ' ORDER BY due_date IS NULL,due_date,Datum,_rowid',bindings,limit,offset)
    if result['truncated'] and not result['rows']:
        raise ValueError('Eine historische OP-Zeile überschreitet die Ausgabegrenze')
    result=_currency_amounts(_labels(result,'Art',OPEN_ITEM_TYPES),'POSTEN',DERIVED_MONEY)
    result.update(as_of=as_of,totals=_totals(reader,where,bindings),basis=BASIS)
    return result


def get_open_item_aging(reader, company_id, as_of, side='receivable', address_id=None):
    where,bindings=_filters(company_id,as_of,side,address_id,False,False)
    result=_totals(reader,where,bindings)
    result.update(as_of=as_of,basis=BASIS)
    return result
