"""Lesende Connect-Buchungen; unbekannte lokale Statuscodes bleiben ausdrücklich roh."""

METHODS = frozenset({
    "buchungList", "buchungGet", "buchungFilterTemplate", "buchungTemplate", "steuersatzList",
})
_FILTERS = frozenset({
    "DatumVon", "DatumBis", "FestschreibStatus", "Suchtext", "BelegNr",
    "Konto", "KontoSoll", "KontoHaben", "Kostenstelle",
})


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} muss eine ganze Zahl ab {minimum} sein")
    return value


def _text(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} muss eine Zeichenkette sein")
    return value


def _booking(reader, row):
    return {
        "Buchung_ID": str(row["_rowid"]), "Datum": row["Datum"],
        "Text": row["Text"], "Status": None, "LokalStatus": row["Status"],
        "Summe": reader.money(row["Summe"]), "SummeFW": reader.money(row["SummeFW"]),
        "BelegNr": row["BelegNr"],
    }


def _list(reader, params, firma_id):
    reader.require(params, {"BuchungFilter"})
    filters = reader.filter(params, "BuchungFilter", _FILTERS)
    clauses, bindings = ["b.Firma_id=?"], [firma_id]
    reader.dates(filters, clauses, bindings, column="b.Datum")
    status = _integer(filters.get("FestschreibStatus", 4), "FestschreibStatus", 1)
    if status not in (1, 2, 4):
        raise ValueError("FestschreibStatus muss 1, 2 oder 4 sein")
    if status != 4:
        raise ValueError("FestschreibStatus 1/2 ist im lokalen Schema nicht verifiziert; nur 4 (Alle) ist verfügbar")
    for name, columns in (
        ("Suchtext", ["b.Text", "b.BelegNr", "b.Referenz"]),
        ("BelegNr", ["b.BelegNr"]),
    ):
        if name in filters:
            reader.search(_text(filters[name], name), columns, clauses, bindings)
    for name, side in (("Konto", None), ("KontoSoll", "BetragSoll"), ("KontoHaben", "BetragHaben")):
        if name not in filters:
            continue
        account = _integer(filters[name], name)
        if account == 0:
            continue
        side_clause = "" if side is None else f" AND j.{side}<>0"
        clauses.append(
            "EXISTS (SELECT 1 FROM JOURNAL j WHERE j.Firma_id=b.Firma_id "
            f"AND j.Buchung_id=b._rowid AND j.Konto=?{side_clause})"
        )
        bindings.append(account)
    if "Kostenstelle" in filters:
        cost = _text(filters["Kostenstelle"], "Kostenstelle")
        if cost:
            clauses.append(
                "EXISTS (SELECT 1 FROM JOURNAL j WHERE j.Firma_id=b.Firma_id "
                "AND j.Buchung_id=b._rowid AND (j.Kostenstelle1=? OR j.Kostenstelle2=?))"
            )
            bindings.extend((cost, cost))
    rows = reader.rows(
        "SELECT b.* FROM BUCHUNG b WHERE " + " AND ".join(clauses) + " ORDER BY b.Datum,b._rowid",
        bindings,
    )
    return {"BuchungListItem": [_booking(reader, row) for row in rows]}


def _get(reader, params, firma_id):
    reader.require(params, {"Buchung_ID"})
    identifier = _text(params.get("Buchung_ID"), "Buchung_ID")
    if not identifier.isascii() or not identifier.isdecimal() or int(identifier) < 1:
        raise ValueError("Buchung_ID muss eine positive lokale Datensatz-ID sein")
    identifier = int(identifier)
    row = reader.one("SELECT * FROM BUCHUNG WHERE Firma_id=? AND _rowid=?", (firma_id, identifier))
    item = _booking(reader, row)
    item.update({
        name: row[column] for name, column in (
            ("EingabeDatum", "EingabeDatum"), ("Referenz", "Referenz"), ("Notizen", "Bemerkung"),
            ("KontoSoll", "KontoSoll"), ("KontoHaben", "KontoHaben"), ("Waehrung", "Waehrung"),
            ("Steuersatz", "Steuersatz"),
        )
    })
    item["Kurs"] = None if row["Kurs"] is None else str(row["Kurs"])
    item["FestschreibStatus"] = None
    journals = reader.rows(
        "SELECT j.*,k.Bezeichnung AS Kontobezeichnung FROM JOURNAL j "
        "LEFT JOIN KONTO k ON k.Firma_id=j.Firma_id AND k.Nummer=j.Konto "
        "WHERE j.Firma_id=? AND j.Buchung_id=? ORDER BY j.NummerLong,j.Position,j._rowid",
        (firma_id, identifier),
    )
    entries = []
    for journal in journals:
        entry = {name: journal[column] for name, column in (
            ("Journalnummer", "NummerLong"), ("Konto", "Konto"), ("Kontobezeichnung", "Kontobezeichnung"),
            ("Steuersatz", "Steuersatz"), ("Text", "Text"),
            ("Kostenstelle1", "Kostenstelle1"), ("Kostenstelle2", "Kostenstelle2"),
        )}
        entry.update({name: reader.money(journal[column]) for name, column in (
            ("BetragSoll", "BetragSoll"), ("BetragHaben", "BetragHaben"),
            ("FW_Soll", "BetragSollFW"), ("FW_Haben", "BetragHabenFW"),
        )})
        # Storno ist eine lokale Zusatzinformation, niemals ein weiterer Vorzeichenfaktor.
        entry["LokalStorno"] = journal["Storno"]
        entry["OSS_Daten"] = {"OSSDatenItem": {
            "Isocode": journal["OSS_ISO_LK"],
            "Steuersatz": None, "Typ": journal["OSS_Typ"],
        }}
        entry["LokalOSSProzent"] = journal["OSS_Prozent"]
        entries.append(entry)
    item["BuchungJournalItemList"] = {"BuchungJournalItem": entries}
    return {"BuchungItem": item}


def handle(reader, method, params, firma_id) -> dict:
    if method not in METHODS:
        raise ValueError("Unbekannte Buchungsmethode")
    firma_id = reader.company(firma_id)
    if method == "buchungList":
        return _list(reader, params, firma_id)
    if method == "buchungGet":
        return _get(reader, params, firma_id)
    if method == "steuersatzList":
        reader.require(params, set())
        rows = reader.rows("SELECT * FROM STEUERSATZ WHERE Firma_id=? ORDER BY Name,_rowid", (firma_id,))
        return {"SteuersatzListItem": [{
            "Name": row["Name"], "Beschreibung": row["Beschreibung"],
            "Steuersatz": reader.money(row["Prozent"]),
            "Gesperrt": None if row["Buchungssperre"] is None else bool(row["Buchungssperre"]),
            "OSS_Steuersatz": None if row["OSS"] is None else bool(row["OSS"]),
        } for row in rows]}
    if method == "buchungFilterTemplate":
        reader.require(params, set())
        return {"BuchungFilter": {
            "DatumVon": "", "DatumBis": "", "FestschreibStatus": 4, "Suchtext": "",
            "BelegNr": "", "Konto": 0, "KontoSoll": 0, "KontoHaben": 0,
        }}
    reader.require(params, {"PositionenAnzahl"})
    count = _integer(params.get("PositionenAnzahl", 1), "PositionenAnzahl", 1)
    if count > 500:
        raise ValueError("PositionenAnzahl darf höchstens 500 sein")
    return {"BuchungAddItem": {
        "Datum": "", "Text": "", "BelegNr": "", "Referenz": "", "Notizen": "",
        "Waehrung": "", "Kurs": "", "BuchungPositionItemList": {"BuchungPositionAddItem": [{
            "Betrag": "0.00", "KontoSoll": 0, "KontoHaben": 0, "Kostenstelle1": "",
            "Kostenstelle2": "", "Steuersatz": "", "Text": "", "BuchungBetragBasis": 0,
            "OSS_Daten": {"OSSDatenItem": {"Isocode": "", "Steuersatz": "", "Typ": 1}},
        } for _ in range(count)]},
    }}
