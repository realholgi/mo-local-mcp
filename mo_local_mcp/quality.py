"""Gespeicherte Verknüpfungen und Beträge prüfen, ohne Daten zu korrigieren."""

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from .business import _integer
from .errors import ParameterFehler
from .statements import StatementReader, _money


_LINKS = {
    "AUFTRAG": (("Posten_id", "POSTEN", False),),
    "BESTELLUNG": (("Posten_id", "POSTEN", False),),
    "BUCHUNG": (),
    "JOURNAL": (("Buchung_id", "BUCHUNG", True),),
    "POSTEN": (("Buchung_id", "BUCHUNG", False), ("BuchungSR_id", "BUCHUNG", False)),
    "POSTENPOSITION": (("Posten_id", "POSTEN", True),),
    "ZAHLUNG": (("Buchung_id", "BUCHUNG", False), ("ValutaBuchung_id", "BUCHUNG", False)),
    "ZAHLUNGSPOSITION": (("Zahlung_id", "ZAHLUNG", True),
                         ("Postenposition_id", "POSTENPOSITION", True),
                         ("SteuerBuchung_id", "BUCHUNG", False)),
}
_ALLOCATION_FIELDS = ("BetragZahlFW", "BetragZahlSW", "BetragMindFW", "BetragMindSW")
_HEAD_FIELDS = {
    "POSTEN": ("BezahltFW", "BezahltSW", "MinderungFW", "MinderungSW"),
    "ZAHLUNG": ("GesamtZahlFW", "GesamtZahlSW", "GesamtMindFW", "GesamtMindSW"),
}
_FIELDS = {
    "AUFTRAG": (), "BESTELLUNG": (), "BUCHUNG": ("Waehrung",),
    "JOURNAL": ("BetragSoll", "BetragHaben", "BetragSollFW", "BetragHabenFW"),
    "POSTEN": ("Waehrung", *_HEAD_FIELDS["POSTEN"]),
    "POSTENPOSITION": (), "ZAHLUNG": ("Waehrung", *_HEAD_FIELDS["ZAHLUNG"]),
    "ZAHLUNGSPOSITION": _ALLOCATION_FIELDS,
}


def _amount(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _total(rows, field):
    total = Decimal(0)
    for row in rows:
        value = _amount(row[field])
        if value is None:
            return None
        total += value
    return total


def check_data_quality(reader, company_id, limit=100, offset=0):
    """Vollständigen Firmenbestand prüfen und nur die Mängelliste paginieren."""
    _integer(company_id, "firma_id")
    _integer(limit, "anzahl")
    _integer(offset, "versatz", 0)
    if limit > 500:
        raise ParameterFehler("anzahl darf höchstens 500 sein")
    source = StatementReader(reader.database)
    tables = {}
    for table, links in _LINKS.items():
        fields = ["_rowid", *(link[0] for link in links), *_FIELDS[table]]
        rows = source._rows(
            f"SELECT {','.join(fields)} FROM {table} WHERE Firma_id=? ORDER BY _rowid",
            [company_id],
        )
        tables[table] = {row["_rowid"]: row for row in rows}

    issues = []
    checks = Counter()

    def issue(category, table, row_id, field, status, **details):
        issues.append({"kategorie": category, "tabelle": table, "datensatz_id": row_id,
                       "feld": field, "status": status, **details})

    for table, links in _LINKS.items():
        for row_id, row in tables[table].items():
            for field, target, required in links:
                value = row[field]
                if not required and value in (None, 0):
                    continue
                checks["verknuepfungen"] += 1
                if value not in tables[target]:
                    issue("fehlende_verknuepfung", table, row_id, field, "mangel",
                          ziel_tabelle=target, ziel_id=value,
                          grund="Gespeichertes Ziel fehlt innerhalb dieser Firma.")

    journals = defaultdict(list)
    for row in tables["JOURNAL"].values():
        if row["Buchung_id"] in tables["BUCHUNG"]:
            journals[row["Buchung_id"]].append(row)
    for row_id in tables["BUCHUNG"]:
        rows = journals[row_id]
        for suffix, debit, credit in (("SW", "BetragSoll", "BetragHaben"),
                                      ("FW", "BetragSollFW", "BetragHabenFW")):
            checks["journal_soll_haben"] += 1
            soll, haben = _total(rows, debit), _total(rows, credit)
            if not rows or soll is None or haben is None:
                issue("journal_saldo", "BUCHUNG", row_id, suffix, "unbekannt",
                      soll=None if soll is None or not rows else _money(soll),
                      haben=None if haben is None or not rows else _money(haben),
                      differenz=None, grund="Journalzeilen fehlen oder enthalten unbekannte Beträge.")
            else:
                difference = Decimal(_money(soll)) - Decimal(_money(haben))
                if difference:
                    issue("journal_saldo", "BUCHUNG", row_id, suffix, "mangel",
                          soll=_money(soll), haben=_money(haben), differenz=format(difference, ".2f"))

    item_allocations = defaultdict(list)
    payment_allocations = defaultdict(list)
    incomplete_items = set()
    incomplete_payments = set()
    unassigned = 0
    for row in tables["ZAHLUNGSPOSITION"].values():
        payment = tables["ZAHLUNG"].get(row["Zahlung_id"])
        position = tables["POSTENPOSITION"].get(row["Postenposition_id"])
        item_id = position["Posten_id"] if position is not None else None
        item = tables["POSTEN"].get(item_id)
        if payment is not None:
            payment_allocations[row["Zahlung_id"]].append(row)
            if item is None:
                incomplete_payments.add(row["Zahlung_id"])
        if item is None:
            unassigned += 1
        elif payment is None:
            incomplete_items.add(item_id)
        else:
            item_allocations[item_id].append(row)

    for table, allocations, incomplete in (
        ("POSTEN", item_allocations, incomplete_items),
        ("ZAHLUNG", payment_allocations, incomplete_payments),
    ):
        for row_id, head in tables[table].items():
            rows = allocations[row_id]
            for field, allocated_field in zip(_HEAD_FIELDS[table], _ALLOCATION_FIELDS):
                checks["posten_abgleich" if table == "POSTEN" else "zahlung_abgleich"] += 1
                reason = None
                if row_id in incomplete or (table == "POSTEN" and unassigned):
                    reason = "Nicht alle Zuordnungen lassen sich innerhalb dieser Firma vollständig auflösen."
                if table == "ZAHLUNG" and field.endswith("FW") and reason is None:
                    for row in rows:
                        position = tables["POSTENPOSITION"].get(row["Postenposition_id"])
                        item = tables["POSTEN"].get(position["Posten_id"]) if position else None
                        if item is None or not head["Waehrung"] or head["Waehrung"] != item["Waehrung"]:
                            reason = "FW der Zahlung und FW des Postens sind nicht als gleiche Währung belegt."
                            break
                stored = _amount(head[field])
                total = None if reason else _total(rows, allocated_field)
                if stored is None or total is None:
                    issue("posten_abgleich" if table == "POSTEN" else "zahlung_abgleich",
                          table, row_id, field, "unbekannt",
                          kopf=None if stored is None else _money(stored),
                          zuordnungssumme=None if total is None else _money(total), differenz=None,
                          grund=reason or "Kopf oder Zuordnungen enthalten unbekannte Beträge.")
                else:
                    difference = Decimal(_money(stored)) - Decimal(_money(total))
                    if difference:
                        issue("posten_abgleich" if table == "POSTEN" else "zahlung_abgleich",
                              table, row_id, field, "mangel", kopf=_money(stored),
                              zuordnungssumme=_money(total), differenz=format(difference, ".2f"))

    issues.sort(key=lambda row: (row["kategorie"], row["tabelle"], int(row["datensatz_id"]), row["feld"]))
    counts = Counter(row["kategorie"] for row in issues)
    page = issues[offset:offset + limit]
    more = offset + len(page) < len(issues)
    return {
        "firma_id": company_id, "maengel": page, "gesamtanzahl": len(issues),
        "anzahl_nach_kategorie": {category: counts[category] for category in (
            "fehlende_verknuepfung", "journal_saldo", "posten_abgleich", "zahlung_abgleich")},
        "anzahl_nach_status": {status: sum(row["status"] == status for row in issues)
                               for status in ("mangel", "unbekannt")},
        "anzahl": len(page), "versatz": offset, "gekuerzt": more,
        "naechster_versatz": offset + len(page) if more else None,
        "pruefungsumfang": {
            "datensaetze": {table: len(rows) for table, rows in tables.items()},
            "pruefungen": dict(checks), "nicht_zuordenbare_zahlungspositionen": unassigned,
            "verknuepfungsfelder": {table: [link[0] for link in links] for table, links in _LINKS.items()},
        },
        "basis": [
            "Nur gespeicherte IDs innerhalb der gewählten Firma; keine Referenz- oder Betragsheuristik. Optionale IDs NULL/0 sind keine fehlenden Ziele.",
            "Vollständiger Firmenbestand einschließlich Entwürfen und ausgeglichenen Belegen. Seiten begrenzen nur die Mängelliste.",
            "Journal-Soll/Haben je BUCHUNG und FW/SW getrennt. BUCHUNG.Summe wird mangels gesicherter Soll/Haben-Semantik nicht verglichen.",
            "POSTEN-Kopfsummen gegen alle vollständig verknüpften Zahlungspositionen. Nicht zuordenbare Positionen machen den Postenabgleich unbekannt, da ihr Ziel nicht bestimmbar ist.",
            "ZAHLUNG-Kopfsummen gegen eigene Zuordnungen; FW nur bei belegter gleicher Posten-/Zahlungswährung. SW bleibt getrennt. Keine Währungsumrechnung.",
            "Geld in Währungseinheiten als Dezimalzeichenketten, gespeicherte Hundertstel durch 100. Vergleich nach kaufmännischer Rundung auf 0,01 Währungseinheiten; Vorzeichen bleiben erhalten.",
            "NULL und ungültige Beträge sind unbekannt, nicht null. Leere vollständige Zuordnungslisten ergeben null; fehlende Journalzeilen bleiben unbekannt.",
            "Keine Korrekturen. Keine Aussage über Vollständigkeit, steuerliche Richtigkeit oder die Qualität außerhalb dieses Prüfungsumfangs.",
        ],
    }
