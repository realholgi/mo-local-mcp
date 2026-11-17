"""Firmenbezogene Stammdaten aus dem beobachteten, ausschließlich gelesenen Datenbankschema."""

from .business import _integer, _labels
from .master_catalog import MASTERS_CATALOG


def _search(columns):
    # instr behandelt %, _ und Rückstriche anders als LIKE als wörtliche Zeichen.
    return "(" + " OR ".join(
        f"instr(lower(coalesce(CAST({column} AS TEXT),'')),lower(?))>0"
        for column in columns
    ) + ")"


def list_cost_centers(reader, company_id, search="", limit=100, offset=0):
    """Unveränderte Kostenstellen mit Bezeichnungen für fehlende und unbekannte Sperrwerte auflisten."""
    _integer(company_id, "firma_id")
    result = reader._page(
        "SELECT _rowid,Firma_id,Name,Beschreibung,Bemerkung,Buchungssperre "
        "FROM KOSTENSTELLE WHERE Firma_id=? AND "
        + _search(("_rowid", "Name", "Beschreibung", "Bemerkung"))
        + " ORDER BY Name,_rowid",
        [company_id, *([search] * 4)], limit, offset,
    )
    return _labels(result, "Buchungssperre", {0: "Offen", 1: "Gesperrt", None: "Nicht angegeben"})


def list_payment_terms(reader, company_id, search="", limit=100, offset=0):
    """Unveränderte Zahlungsbedingungen ohne erfundene Wertelisten oder Skontoskalierung auflisten."""
    _integer(company_id, "firma_id")
    result = reader._page(
        "SELECT _rowid,Firma_id,Bezeichnung,Zahlungsart,TageNetto,ZBText,TageSkonto,"
        "ProzentSkonto,NichtMahnen,FakturaArt,Bankkonto_id,Gesperrt,Standard "
        "FROM ZAHLUNGSBEDINGUNG WHERE Firma_id=? AND "
        + _search(("_rowid", "Bezeichnung", "ZBText"))
        + " ORDER BY Bezeichnung,_rowid",
        [company_id, *([search] * 3)], limit, offset,
    )
    _labels(result, "NichtMahnen", {0: "Mahnen erlaubt", 1: "Nicht mahnen", None: "Nicht angegeben"})
    _labels(result, "Gesperrt", {0: "Offen", 1: "Gesperrt", None: "Nicht angegeben"})
    _labels(result, "Standard", {0: "Nein", 1: "Ja", None: "Nicht angegeben"})
    result["units"] = dict(MASTERS_CATALOG["ZAHLUNGSBEDINGUNG"]["units"])
    result["limitations"] = list(MASTERS_CATALOG["ZAHLUNGSBEDINGUNG"]["limitations"])
    return result


def list_currencies(reader, company_id, search="", limit=100, offset=0):
    """Währungsdefinitionen auflisten; Faktoren und Kurse niemals wie Geldbeträge skalieren."""
    _integer(company_id, "firma_id")
    result = reader._page(
        "SELECT _rowid,Firma_id,ISOCode,Name,Zeichen,Faktor,Kurs "
        "FROM WAEHRUNG WHERE Firma_id=? AND "
        + _search(("_rowid", "ISOCode", "Name", "Zeichen"))
        + " ORDER BY ISOCode,Name,_rowid",
        [company_id, *([search] * 4)], limit, offset,
    )
    result["units"] = dict(MASTERS_CATALOG["WAEHRUNG"]["units"])
    result["limitations"] = list(MASTERS_CATALOG["WAEHRUNG"]["limitations"])
    return result
