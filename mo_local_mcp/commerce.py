"""Einkaufsbelege, Artikel und Projekte eines ruhenden Datenbankstands lesen."""

from .business import POSITION_TYPES, _currency_amounts, _dates, _integer, _labels
from .commerce_catalog import (
    ARTICLE_STATUSES, ARTICLE_TYPES, COMMERCE_CATALOG, PROJECT_STATUSES, PURCHASE_TYPES,
)
from .masters import _search


def _bounds(company_id, limit, offset):
    _integer(company_id, "firma_id")
    _integer(limit, "anzahl")
    _integer(offset, "versatz", 0)
    if limit > 500:
        raise ValueError("anzahl darf höchstens 500 sein")


def _boolean(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} muss ein boolescher Wert sein")


def _basis(result, table):
    entry = COMMERCE_CATALOG[table]
    result["basis"] = entry["mapping_basis"]
    result["limitations"] = list(entry.get("limitations", []))
    if "units" in entry:
        result["units"] = dict(entry["units"])
    return result


def list_purchase_documents(reader, company_id, document_type=None, address_id=None,
                            date_from=None, date_to=None, include_drafts=False,
                            search="", limit=100, offset=0):
    _bounds(company_id, limit, offset)
    _boolean(include_drafts, "mit_entwuerfen")
    where, bindings = ["Firma_id=?"], [company_id]
    if document_type is not None:
        _integer(document_type, "belegart", 0)
        where.append("Art=?")
        bindings.append(document_type)
    if address_id is not None:
        _integer(address_id, "adresse_id")
        where.append("Adress_id=?")
        bindings.append(address_id)
    if not include_drafts:
        where.append("coalesce(Entwurf,0)=0")
    _dates(where, bindings, "Datum", date_from, date_to)
    columns = ("BestellNr", "LieferNr", "Betreff", "RechnAnschrift", "LieferAnschrift", "Notizen")
    where.append(_search(columns))
    bindings.extend([search] * len(columns))
    result = reader._page(
        "SELECT _rowid,Firma_id,Art,Entwurf,BestellNr,Datum,LieferDatum,Adress_id,"
        "Posten_id,Projekt_id,Betreff,Waehrung,Kurs,Gedruckt,Buchung_Status,"
        "GesamtNettoFW,GesamtSteuerFW,GesamtBruttoFW,GesamtNettoSW,"
        "GesamtSteuerSW,GesamtBruttoSW FROM BESTELLUNG WHERE "
        + " AND ".join(where) + " ORDER BY Datum,_rowid", bindings, limit, offset,
    )
    _labels(result, "Art", {**PURCHASE_TYPES, None: "Nicht angegeben"})
    return _basis(_currency_amounts(result, "BESTELLUNG"), "BESTELLUNG")


def get_purchase_document(reader, company_id, document_id, position_limit=100, position_offset=0):
    _bounds(company_id, position_limit, position_offset)
    _integer(document_id, "beleg_id")
    header = reader.database.query(
        "SELECT * FROM BESTELLUNG WHERE Firma_id=? AND _rowid=?", [company_id, document_id], 1,
    )
    if not header["rows"]:
        if header["truncated"]:
            raise ValueError("Einkaufsbeleg überschreitet die Ausgabegrenze; mit einer gezielten SQL-Abfrage weniger Spalten auswählen")
        raise ValueError("Einkaufsbeleg in dieser Firma nicht gefunden")
    positions = reader._page(
        "SELECT * FROM BESTELLPOSITION WHERE Firma_id=? AND Bestell_id=? "
        "ORDER BY SortNr,Nummer,_rowid", [company_id, document_id], position_limit, position_offset,
    )
    _labels(header, "Art", {**PURCHASE_TYPES, None: "Nicht angegeben"})
    _labels(positions, "Art", {**POSITION_TYPES, None: "Nicht angegeben"})
    return {
        "document": _basis(_currency_amounts(header, "BESTELLUNG"), "BESTELLUNG"),
        "positions": _basis(_currency_amounts(positions, "BESTELLPOSITION"), "BESTELLPOSITION"),
    }


def list_articles(reader, company_id, search="", article_type=None, stock_only=False,
                  group=None, limit=100, offset=0):
    _bounds(company_id, limit, offset)
    _boolean(stock_only, "nur_lagerartikel")
    where, bindings = ["Firma_id=?"], [company_id]
    if article_type is not None:
        _integer(article_type, "artikelart", 0)
        where.append("Art=?")
        bindings.append(article_type)
    if stock_only:
        where.append("Lagerartikel=1")
    if group is not None:
        if not isinstance(group, str):
            raise ValueError("warengruppe muss eine Zeichenkette sein")
        where.append("Warengruppe=?")
        bindings.append(group)
    columns = ("ArtikelNr", "Bezeichnung", "Beschreibung", "Matchcode", "EANCode", "Hersteller", "HerstellerNr", "Warengruppe")
    where.append(_search(columns))
    bindings.extend([search] * len(columns))
    result = reader._page(
        "SELECT * FROM ARTIKEL WHERE " + " AND ".join(where) + " ORDER BY ArtikelNr,_rowid",
        bindings, limit, offset,
    )
    _labels(result, "Art", {**ARTICLE_TYPES, None: "Nicht angegeben"})
    _labels(result, "Status", {**ARTICLE_STATUSES, None: "Nicht angegeben"})
    return _basis(_currency_amounts(result, "ARTIKEL"), "ARTIKEL")


def list_projects(reader, company_id, search="", limit=100, offset=0):
    _bounds(company_id, limit, offset)
    columns = ("ProjektNr", "Bezeichnung", "Beschreibung", "Bearbeiter", "Notizen")
    result = reader._page(
        "SELECT * FROM PROJEKT WHERE Firma_id=? AND " + _search(columns)
        + " ORDER BY ProjektNr,_rowid", [company_id, *([search] * len(columns))], limit, offset,
    )
    _labels(result, "Status", {**PROJECT_STATUSES, None: "Nicht angegeben"})
    return _basis(result, "PROJEKT")
