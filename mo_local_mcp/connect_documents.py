"""Lesende Connect-Belege mit lokalen Ersatz-IDs und gespeicherten OP-Salden.

Nicht rekonstruierbar: originale Connect-IDs/VersionKey, Artikel_ID einer
Belegposition (nur ArtikelNr gespeichert), FestschreibStatus/EtikettTag ohne
verifizierte Wertzuordnung. Diese Felder werden nicht erfunden. Ohne Datumsfilter
wird der gesamte Datenstand gelesen, nicht ein vermeintlich aktives Geschäftsjahr.
"""

METHODS = frozenset({
    "verkaufbelegList", "verkaufbelegGet", "einkaufbelegList",
    "offenePostenList", "offenePostenListDebitoren",
    "offenePostenListKreditoren", "offenePostenGet",
})

_SALE_TYPES = {"Angebot": 1, "AuftragsBestaetigung": 2, "Lieferschein": 3,
               "Rechnung": 4, "AbschlagsRechnung": 5, "KorrekturRechnung": 6,
               "ProformaRechnung": 7, "Storno": 8, "Kostenvoranschlag": 9}
_COMMON_FILTERS = {"DatumVon", "DatumBis", "Adresse_ID", "Suchtext", "Zahlungstatus"}
_OP_FILTERS = {"DatumVon", "DatumBis", "Adresse_ID", "NurOffene",
               "BelegNr", "Konto", "Text", "Waehrung"}


def _id(value, field):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{field} muss eine positive lokale ID sein")
    text = str(value)
    if not text.isascii() or not text.isdecimal() or int(text) <= 0:
        raise ValueError(f"{field} muss eine positive lokale ID sein")
    return int(text)


def _bool(value, field):
    if not isinstance(value, bool):
        raise ValueError(f"{field} muss ein Wahrheitswert sein")
    return value


def _enum(value, field, values):
    if type(value) is not int or value not in values:
        raise ValueError(f"{field} hat einen nicht unterstützten Wert")
    return value


def _mapped(row, mapping):
    return {target: row[source] for target, source in mapping.items() if source in row}


def _money(reader, row, fields):
    return {field: reader.money(row[field]) for field in fields if field in row}


def _payment_status(row):
    if not row.get("Posten_id"):
        return 0
    if row.get("linked_posten") is None or row.get("op_offen") is None:
        raise ValueError("Zahlungstatus ist ohne firmengebundenen Posten und gespeicherten Saldo nicht bestimmbar")
    if row["op_offen"] == 0:
        return 3
    if row.get("op_bezahlt") is None or row.get("op_minderung") is None:
        raise ValueError("Zahlungstatus ist ohne gespeicherte Zahlung und Minderung nicht bestimmbar")
    return 2 if row["op_bezahlt"] != 0 or row["op_minderung"] != 0 else 1


def _document_from(table):
    return (f" FROM {table} d LEFT JOIN ADRESSE a ON a._rowid=d.Adress_id AND a.Firma_id=d.Firma_id"
            " LEFT JOIN PROJEKT j ON j._rowid=d.Projekt_id AND j.Firma_id=d.Firma_id"
            " LEFT JOIN POSTEN p ON p._rowid=d.Posten_id AND p.Firma_id=d.Firma_id")


_DOCUMENT_SELECT = ("SELECT d.*, a._rowid AS linked_adresse, a.RA_Firma1 AS kunde_firma, "
                    "a.RA_Vorname AS kunde_vorname, a.RA_Nachname AS kunde_nachname, "
                    "j._rowid AS linked_projekt, j.ProjektNr AS projekt_nr, "
                    "p._rowid AS linked_posten, p.OffenFW AS op_offen, "
                    "p.BezahltFW AS op_bezahlt, p.MinderungFW AS op_minderung")


def _name(row):
    return row.get("kunde_firma") or " ".join(
        str(row[key]) for key in ("kunde_vorname", "kunde_nachname") if row.get(key)) or None


def _document_item(reader, row, sale):
    kind = "Verkaufbeleg" if sale else "Einkaufbeleg"
    item = {
        kind + "_ID": str(row["_rowid"]),
        "Adresse_ID": str(row["linked_adresse"]) if row["linked_adresse"] is not None else None,
        "AuftragNr" if sale else "BestellNr": row["AuftragsNr" if sale else "BestellNr"],
        kind + "Art": row["Art"], "Kunde": _name(row), "Datum": row["Datum"],
        "Lieferdatum": row["LieferDatum"],
        "Projekt_ID": str(row["linked_projekt"]) if row["linked_projekt"] is not None else None,
        "ProjektNr": row["projekt_nr"],
    }
    suffix = "SW" if sale else "FW"
    item.update(_money(reader, row, ("GesamtNetto" + suffix, "GesamtBrutto" + suffix)))
    return item


def _documents(reader, method, params, firma_id):
    sale = method.startswith("verkauf")
    kind = "Verkaufbeleg" if sale else "Einkaufbeleg"
    table = "AUFTRAG" if sale else "BESTELLUNG"
    if method.endswith("Get"):
        reader.require(params, {kind + "_ID"})
        row = reader.one(_DOCUMENT_SELECT + _document_from(table) + " WHERE d.Firma_id=? AND d._rowid=?",
                         (firma_id, _id(params.get(kind + "_ID"), kind + "_ID")))
        return {kind + "Item": _sale_detail(reader, row, firma_id)}
    reader.require(params, {kind + "Filter"})
    allowed = _COMMON_FILTERS | (set(_SALE_TYPES) if sale else set())
    filters = reader.filter(params, kind + "Filter", allowed)
    clauses, bindings = ["d.Firma_id=?"], [firma_id]
    reader.dates(filters, clauses, bindings, column="d.Datum")
    if "Adresse_ID" in filters:
        clauses.append("a._rowid=?")
        bindings.append(_id(filters["Adresse_ID"], "Adresse_ID"))
    if "Suchtext" in filters:
        reader.search(filters["Suchtext"], ["d.AuftragsNr" if sale else "d.BestellNr", "d.Betreff",
                      "d.Notizen", "a.RA_Firma1", "a.RA_Vorname", "a.RA_Nachname"], clauses, bindings)
    if sale:
        supplied = [key for key in _SALE_TYPES if key in filters]
        selected = [_SALE_TYPES[key] for key in supplied if _bool(filters[key], key)]
        if supplied:
            clauses.append("d.Art IN (" + ",".join("?" for _ in selected) + ")" if selected else "0")
            bindings.extend(selected)
    status = None
    if "Zahlungstatus" in filters:
        status = _enum(filters["Zahlungstatus"], "Zahlungstatus", range(4))
    rows = reader.rows(_DOCUMENT_SELECT + _document_from(table) + " WHERE " + " AND ".join(clauses)
                       + " ORDER BY d.Datum,d._rowid", bindings)
    if status is not None:
        rows = [row for row in rows if _payment_status(row) == status]
    return {kind + "Listitem": [_document_item(reader, row, sale) for row in rows]}


def _sale_detail(reader, row, firma_id):
    item = _document_item(reader, row, True)
    item.update(_mapped(row, {key: key for key in (
        "Betreff", "Anrede", "KopfText", "FussText", "Grussformel", "Notizen", "Bearbeiter",
        "Steuergebiet", "Waehrung", "Lieferart", "Rabatt", "RechnAnschrift", "LieferAnschrift",
        "SepaMandatReferenz", "Belegausgabe")}))
    item.update(_mapped(row, {"Referenz": "BestellNr", "Zahlungsbedingungen": "Zahlungsbedingung",
                            "SepaBankeinzug": "SepaBankEinzug", "Versandnummer": "VersandNummer",
                            "VersandURL": "VersandURL"}))
    for target, source in (("Entwurf", "Entwurf"), ("LaVerwenden", "LAVerwenden"),
                           ("BearbeiterAngeben", "BearbeiterAngeben")):
        if source in row:
            item[target] = None if row[source] is None else bool(row[source])
    item["Zahlungstatus"] = _payment_status(row)
    item["Posten_ID"] = str(row["linked_posten"]) if row["linked_posten"] is not None else None
    item.update(_money(reader, row, (base + suffix for base in (
        "GesamtNetto", "GesamtBrutto", "GesamtRabatt", "GesamtSteuer") for suffix in ("FW", "SW"))))
    for target, source in (("Ansprechpartner_ID", "Ansprechpartner_id"), ("VKPreisliste_ID", "Preisliste_id")):
        if row.get(source):
            table = "ANSPRECHPARTNER" if source == "Ansprechpartner_id" else "PREISLISTE"
            matches = reader.rows(f"SELECT _rowid FROM {table} WHERE Firma_id=? AND _rowid=?",
                                  (firma_id, row[source]))
            item[target] = str(matches[0]["_rowid"]) if matches else None
    positions = reader.rows("SELECT * FROM AUFTRAGSPOSITION WHERE Firma_id=? AND Auftrag_id=? ORDER BY Nummer,_rowid",
                            (firma_id, row["_rowid"]))
    items = []
    for position in positions:
        entry = _mapped(position, {key: key for key in ("PosNrManuell", "ArtikelNr", "Warengruppe", "Menge",
                         "Beschreibung", "Bezeichnung", "Einheit", "Kostenstelle", "Steuersatz")})
        entry.update(_mapped(position, {"VerkaufbelegPositionArt": "Art", "Ertragskonto": "EKonto",
                                      "GesamtGewicht": "Gewicht"}))
        for key in ("Nummer", "ArtikelArt", "Rabatt"):
            if key in position:
                entry[key] = None if position[key] is None else str(position[key])
        entry.update(_money(reader, position, (base + "FW" for base in (
            "EinzelPreisBrutto", "EinzelPreisNetto", "GesamtPreisBrutto", "GesamtPreisNetto"))))
        items.append(entry)
    item["VerkaufbelegPositionItemList"] = {"VerkaufbelegPositionItem": items}
    return item


_OP_FROM = (" FROM POSTEN p LEFT JOIN ADRESSE a ON a._rowid=p.Adress_id AND a.Firma_id=p.Firma_id")
_OP_SELECT = ("SELECT p.*, a._rowid AS linked_adresse, a.RA_Firma1 AS kunde_firma, "
              "a.RA_Vorname AS kunde_vorname, a.RA_Nachname AS kunde_nachname")


def _op_item(reader, row):
    return {"Posten_ID": str(row["_rowid"]),
            "Adresse_ID": str(row["linked_adresse"]) if row["linked_adresse"] is not None else None,
            "Postenart": row["Art"], "Datum": row["Datum"], "BelegNr": row["ReNr"],
            "Name": _name(row), "Konto": row["PKonto"],
            "Brutto": reader.money(row["GesamtBruttoFW"]),
            "Bezahlt": reader.money(row["BezahltFW"]), "Offen": reader.money(row["OffenFW"])}


def _open_items(reader, method, params, firma_id):
    if method == "offenePostenGet":
        reader.require(params, {"Posten_ID"})
        row = reader.one(_OP_SELECT + _OP_FROM + " WHERE p.Firma_id=? AND p._rowid=?",
                         (firma_id, _id(params.get("Posten_ID"), "Posten_ID")))
        item = _op_item(reader, row)
        item.update(_mapped(row, {"Zahlungsart": "Zahlungsart", "Waehrung": "Waehrung", "Text": "BuText"}))
        positions = reader.rows("SELECT * FROM POSTENPOSITION WHERE Firma_id=? AND Posten_id=? ORDER BY Position,_rowid",
                                (firma_id, row["_rowid"]))
        items = []
        for position in positions:
            entry = _mapped(position, {"Position": "Position", "Text": "BuText", "EA_Konto": "EKonto",
                                      "Kostenstelle1": "Kostenstelle1", "Kostenstelle2": "Kostenstelle2",
                                      "Steuersatz": "Steuersatz"})
            entry.update(_money(reader, position, (base + suffix for base in (
                "BetragBrutto", "BetragNetto", "BetragSteuer") for suffix in ("FW", "SW"))))
            items.append(entry)
        item["OffenePostenPositionItemList"] = {"OffenePostenPositionItem": items}
        return {"OffenePostenItem": item}
    reader.require(params, {"OffenePostenFilter", "offenePostenFilter"})
    if "OffenePostenFilter" in params and "offenePostenFilter" in params:
        raise ValueError("OffenePostenFilter darf nicht doppelt übergeben werden")
    key = "offenePostenFilter" if "offenePostenFilter" in params else "OffenePostenFilter"
    filters = reader.filter(params, key, _OP_FILTERS)
    clauses, bindings = ["p.Firma_id=?"], [firma_id]
    reader.dates(filters, clauses, bindings, column="p.Datum")
    if method.endswith("Debitoren"):
        clauses.append("p.Art IN (0,1)")
    elif method.endswith("Kreditoren"):
        clauses.append("p.Art IN (2,3)")
    if _bool(filters.get("NurOffene", True), "NurOffene"):
        clauses.append("p.OffenFW <> 0")
    if "Adresse_ID" in filters:
        clauses.append("a._rowid=?")
        bindings.append(_id(filters["Adresse_ID"], "Adresse_ID"))
    for key, column in (("BelegNr", "p.ReNr"), ("Text", "p.BuText"), ("Waehrung", "p.Waehrung")):
        if key in filters:
            reader.search(filters[key], [column], clauses, bindings)
    if "Konto" in filters:
        clauses.append("p.PKonto=?")
        bindings.append(_id(filters["Konto"], "Konto"))
    rows = reader.rows(_OP_SELECT + _OP_FROM + " WHERE " + " AND ".join(clauses) + " ORDER BY p.Datum,p._rowid", bindings)
    return {"OffenePostenListItem": [_op_item(reader, row) for row in rows]}


def handle(reader, method, params, firma_id) -> dict:
    """Liefert ausschließlich ReturnData; Hülle und Status erstellt der Dispatcher."""
    if method not in METHODS:
        raise ValueError("Nicht unterstützte Belegmethode")
    firma_id = reader.company(firma_id)
    if method.startswith("offenePosten"):
        return _open_items(reader, method, params, firma_id)
    return _documents(reader, method, params, firma_id)
