"""Belegsuche und unmittelbare, ausschließlich gespeicherte ID-Verknüpfungen."""

from .business import _dates, _integer
from .commerce import _bounds
from .masters import _search
from .errors import ParameterFehler


# Die Tabellen, Spalten und Vorbelegbeziehungen sind im lokalen Schema bestätigt.
_AREAS = {
    "buchung": ("BUCHUNG", "buchung_abrufen", "buchung_id"),
    "verkauf": ("AUFTRAG", "verkaufsbeleg_abrufen", "beleg_id"),
    "einkauf": ("BESTELLUNG", "einkaufsbeleg_abrufen", "beleg_id"),
    "posten": ("POSTEN", "offenen_posten_abrufen", "posten_id"),
    "zahlung": ("ZAHLUNG", "zahlung_abrufen", "zahlung_id"),
}
_SEARCH_FIELDS = {
    "buchung": ("BelegNr", "Text", "Referenz"),
    "verkauf": ("AuftragsNr", "Betreff", "BestellNr"),
    "einkauf": ("BestellNr", "Betreff", "LieferNr"),
    "posten": ("ReNr", "BuText", "Referenz"),
    "zahlung": ("ReNr", "BuText", "Referenz"),
}


def _navigation(company_id, area, record_id):
    _, tool, parameter = _AREAS[area]
    return {"werkzeug": tool, "parameter": {"firma_id": company_id, parameter: record_id}}


def _page(reader, sql, bindings, limit, offset, key):
    result = reader._page(sql, bindings, limit, offset)
    return {
        key: [dict(zip(result["columns"], row)) for row in result["rows"]],
        "anzahl": len(result["rows"]),
        "versatz": offset,
        "gekuerzt": result["truncated"],
        "naechster_versatz": result["next_offset"],
    }


def search_documents(reader, company_id, search, date_from=None, date_to=None,
                     limit=100, offset=0):
    """Fünf Bereiche gemeinsam nach Datum, Bereich und lokaler ID paginieren.

    Entwürfe bleiben sichtbar. Ein Treffer belegt keine offene Zahlung. Beträge
    werden weder bereichsübergreifend noch über verschiedene Währungen summiert.
    """
    _bounds(company_id, limit, offset)
    if not isinstance(search, str):
        raise ParameterFehler("suche muss eine Zeichenkette sein")
    branches, bindings = [], []
    for area, (table, _, _) in _AREAS.items():
        number, text, reference = _SEARCH_FIELDS[area]
        draft = "Entwurf" if area in ("verkauf", "einkauf", "posten") else "NULL"
        where, values = ["Firma_id=?", _search((number, text, reference))], [company_id, *([search] * 3)]
        _dates(where, values, "Datum", date_from, date_to)
        branches.append(
            f"SELECT '{area}' AS bereich,_rowid AS id,Datum AS datum,"
            f"{number} AS belegnummer,{text} AS text,{reference} AS referenz,"
            f"Waehrung AS waehrung,{draft} AS entwurf FROM {table} WHERE "
            + " AND ".join(where)
        )
        bindings.extend(values)
    result = _page(reader, " UNION ALL ".join(branches) + " ORDER BY datum,bereich,id",
                   bindings, limit, offset, "treffer")
    for row in result["treffer"]:
        row["navigation"] = _navigation(company_id, row["bereich"], row["id"])
    result["hinweise"] = [
        "Entwürfe sind enthalten; entwurf enthält den gespeicherten Wert, NULL bedeutet nicht angegeben.",
        "Ein Treffer ist kein Nachweis einer offenen Zahlung. Es werden keine Beträge summiert.",
    ]
    return result


def _edge_sql():
    branches = []
    for area, column, target in (
        ("verkauf", "Posten_id", "posten"),
        ("einkauf", "Posten_id", "posten"),
        ("posten", "Buchung_id", "buchung"),
        ("posten", "BuchungSR_id", "buchung"),
        ("zahlung", "Buchung_id", "buchung"),
        ("zahlung", "ValutaBuchung_id", "buchung"),
    ):
        table = _AREAS[area][0]
        branches.append(
            f"SELECT '{table}.{column}' AS beziehung,_rowid AS beziehungs_id,"
            f"'{area}' AS quelle_bereich,_rowid AS quelle_id,'{target}' AS ziel_bereich,"
            f"{column} AS ziel_id,NULL AS zahlungsposition_id,NULL AS postenposition_id "
            f"FROM {table} WHERE Firma_id=?1 AND {column} IS NOT NULL AND {column}<>0 "
            f"AND ((?2='{area}' AND _rowid=?3) OR (?2='{target}' AND {column}=?3))"
        )
    for table, column, area in (
        ("AUFTRAG_VORBELEG", "Auftrag_id", "verkauf"),
        ("BESTELL_VORBELEG", "Bestell_id", "einkauf"),
    ):
        # Gleiche Vorbelegkante kann mehrfach gespeichert sein. Ihre kleinste
        # lokale Beziehungs-ID benennt sie eindeutig, ohne Doppelzählung.
        branches.append(
            f"SELECT '{table}',min(_rowid),'{area}',{column},'{area}',Vorbeleg_id,NULL,NULL "
            f"FROM {table} WHERE Firma_id=?1 AND {column} IS NOT NULL AND {column}<>0 "
            f"AND Vorbeleg_id IS NOT NULL AND Vorbeleg_id<>0 AND ?2='{area}' "
            f"AND ({column}=?3 OR Vorbeleg_id=?3) GROUP BY {column},Vorbeleg_id"
        )
    branches.append(
        "SELECT 'ZAHLUNGSPOSITION.Postenposition_id',zp._rowid,'zahlung',zp.Zahlung_id,"
        "'posten',pp.Posten_id,zp._rowid,zp.Postenposition_id "
        "FROM ZAHLUNGSPOSITION zp LEFT JOIN POSTENPOSITION pp "
        "ON pp.Firma_id=zp.Firma_id AND pp._rowid=zp.Postenposition_id "
        "WHERE zp.Firma_id=?1 AND zp.Zahlung_id IS NOT NULL AND zp.Zahlung_id<>0 "
        "AND zp.Postenposition_id IS NOT NULL AND zp.Postenposition_id<>0 "
        "AND (pp._rowid IS NULL OR (pp.Posten_id IS NOT NULL AND pp.Posten_id<>0)) "
        "AND ((?2='zahlung' AND zp.Zahlung_id=?3) OR (?2='posten' AND pp.Posten_id=?3))"
    )
    return " UNION ALL ".join(branches)


_EDGE_SQL = _edge_sql()


def _exists_sql(area_column, id_column):
    # Primärschlüsselabfragen statt einer Abfrage je Ergebniszeile im Client.
    return "CASE " + " ".join(
        f"WHEN {area_column}='{area}' THEN EXISTS(SELECT 1 FROM {table} n "
        f"WHERE n.Firma_id=?1 AND n._rowid={id_column})"
        for area, (table, _, _) in _AREAS.items()
    ) + " ELSE 0 END"


_LINK_SQL = (
    "WITH kanten AS (" + _EDGE_SQL + ") SELECT kanten.*,"
    + _exists_sql("quelle_bereich", "quelle_id") + " AS quelle_gefunden,"
    + _exists_sql("ziel_bereich", "ziel_id") + " AS ziel_gefunden "
    "FROM kanten ORDER BY quelle_bereich,quelle_id,ziel_bereich,ziel_id,beziehung,beziehungs_id"
)


def document_links(reader, company_id, area, record_id, limit=100, offset=0):
    """Unmittelbare eingehende und ausgehende Kanten, ohne rekursive Traversierung.

    Zahlungsverknüpfungen benennen jede gespeicherte Zahlungsposition mit ihrer
    Postenposition. Verschiedene Positionen sind verschiedene Kanten, auch wenn
    sie dieselben Köpfe verbinden. Fehlende oder fremde Ziele bleiben unaufgelöst.
    """
    _bounds(company_id, limit, offset)
    _integer(record_id, "datensatz_id")
    if not isinstance(area, str) or area not in _AREAS:
        raise ParameterFehler("bereich muss buchung, verkauf, einkauf, posten oder zahlung sein")
    table = _AREAS[area][0]
    header = reader.database.query(
        f"SELECT _rowid FROM {table} WHERE Firma_id=? AND _rowid=?", [company_id, record_id], 1,
    )
    if not header["rows"]:
        raise ParameterFehler("Datensatz in dieser Firma nicht gefunden")
    result = _page(reader, _LINK_SQL, [company_id, area, record_id], limit, offset, "verknuepfungen")
    for edge in result["verknuepfungen"]:
        outgoing = edge["quelle_bereich"] == area and edge["quelle_id"] == record_id
        incoming = edge["ziel_bereich"] == area and edge["ziel_id"] == record_id
        edge["richtung"] = "beidseitig" if outgoing and incoming else "ausgehend" if outgoing else "eingehend"
        edge["status"] = (
            "aufgelöst" if edge["quelle_gefunden"] and edge["ziel_gefunden"]
            else "Verknüpfung nicht auflösbar"
        )
        for side in ("quelle", "ziel"):
            edge[f"{side}_navigation"] = (
                _navigation(company_id, edge[f"{side}_bereich"], edge[f"{side}_id"])
                if edge.pop(f"{side}_gefunden") else None
            )
    result["hinweise"] = [
        "Nur unmittelbare gespeicherte ID-Beziehungen derselben Firma; keine rekursive Traversierung.",
        "Fehlende und fremde Datensätze werden nicht unterschieden; ihre Inhalte werden nicht ausgegeben.",
        "Mehrere Zahlungspositionen können dieselben Köpfe verbinden; ihre IDs unterscheiden die Kanten.",
    ]
    return result
