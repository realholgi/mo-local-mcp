"""Kostenstellen und Monatsberichte aus dem ruhenden Journalbestand."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from .business import _dates, _integer
from .errors import DatenFehler, ParameterFehler
from .statements import ZERO, StatementReader, _money


_BASIS = (
    "Gespeicherter Datenstand einschließlich aller Statuswerte und negativer Stornos. "
    "Keine Aussage über aktuelle oder künftige Vollständigkeit. "
    "Geldwerte sind Währungseinheiten als Dezimalzeichenketten; bereits durch 100 geteilt."
)


def _reader(reader):
    return reader if isinstance(reader, StatementReader) else StatementReader(reader.database)


def _page(company_id, limit, offset):
    _integer(company_id, "firma_id")
    _integer(limit, "anzahl")
    _integer(offset, "versatz", 0)
    if limit > 500:
        raise ParameterFehler("anzahl darf höchstens 500 sein")


def _amounts(values, closing=True):
    opening_debit, opening_credit, debit, credit = values
    return {
        "eroeffnung": {"soll": _money(opening_debit), "haben": _money(opening_credit),
                       "saldo": _money(opening_debit - opening_credit)},
        "bewegungen": {"soll": _money(debit), "haben": _money(credit), "saldo": _money(debit - credit)},
        "endsaldo": _money(opening_debit - opening_credit + debit - credit) if closing else None,
    }


def _zeros():
    return [ZERO, ZERO, ZERO, ZERO]


def _add(target, values):
    for index, value in enumerate(values):
        target[index] += value


def cost_center_report(reader, company_id, date_from=None, date_to=None, cost_center=None, limit=100, offset=0):
    """Journalzeilen je gespeicherter Kostenstelle und tatsächlichem FW-/SW-Paar."""
    _page(company_id, limit, offset)
    if cost_center is not None and (not isinstance(cost_center, str) or not cost_center):
        raise ParameterFehler("kostenstelle muss eine nicht leere Zeichenkette sein")
    where = ["j.Firma_id=?"]
    bindings = [company_id]
    _dates(where, bindings, "b.Datum", date_from, date_to)
    rows = _reader(reader)._rows(
        "SELECT j.Kostenstelle1, j.Kostenstelle2, j.BetragSoll, j.BetragHaben, "
        "j.BetragSollFW, j.BetragHabenFW, b.Art, b.Waehrung AS fw, w.Waehrung AS sw "
        "FROM JOURNAL j JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id "
        "LEFT JOIN WIRTSCHAFTSJAHR w ON w._rowid=b.Wj_id AND w.Firma_id=b.Firma_id WHERE "
        + " AND ".join(where) + " ORDER BY j._rowid", bindings,
    )
    groups = defaultdict(lambda: {"sw": _zeros(), "fw": _zeros(), "zeilen": 0})
    totals = defaultdict(lambda: {"sw": _zeros(), "fw": _zeros(), "zeilen": 0})
    for row in rows:
        centers = {value for value in (row["Kostenstelle1"], row["Kostenstelle2"]) if value not in (None, "")}
        if not centers:
            centers = {None}
        if cost_center is not None:
            centers &= {cost_center}
        if not centers:
            continue
        values = {}
        for unit, fields in (("sw", ("BetragSoll", "BetragHaben")), ("fw", ("BetragSollFW", "BetragHabenFW"))):
            pair = [Decimal(str(row[field] or 0)) for field in fields]
            values[unit] = pair + [ZERO, ZERO] if row["Art"] == 2 else [ZERO, ZERO] + pair
        # Gesamtwerte direkt aus den Quellzeilen, niemals aus Kostenstellensummen bilden.
        for group in [totals[(row["fw"], row["sw"])], *(groups[(center, row["fw"], row["sw"])] for center in centers)]:
            group["zeilen"] += 1
            for unit in ("sw", "fw"):
                _add(group[unit], values[unit])

    def result(key, group, center=False):
        fw, sw = key[-2:]
        return {
            **({"kostenstelle": key[0]} if center else {}),
            "fw_waehrung": fw, "sw_waehrung": sw,
            "waehrungen_bekannt": bool(fw and sw), "journalzeilen": group["zeilen"],
            "sw": _amounts(group["sw"], False), "fw": _amounts(group["fw"], False),
        }

    ordered = sorted(groups, key=lambda key: tuple((value is not None, str(value)) for value in key))
    selected = ordered[offset:offset + limit]
    more = offset + len(selected) < len(ordered)
    return {
        "firma_id": company_id, "datum_von": date_from, "datum_bis": date_to,
        "kostenstellen": [result(key, groups[key], True) for key in selected],
        "gesamtwerte": [result(key, totals[key]) for key in sorted(totals, key=lambda key: str(key))],
        "anzahl_gesamt": len(ordered), "gekuerzt": more,
        "naechster_versatz": offset + len(selected) if more else None,
        "grundlage": _BASIS + " Eröffnungen Art=2 getrennt. Keine Stammdaten- oder Namensauflösung. "
        "Zwei verschiedene Kostenstellen erhalten jeweils die ganze Zeile; Kostenstellengruppen dürfen daher nicht addiert werden. "
        "Gleiche Kostenstellen in beiden Feldern zählen nur einmal. Gesamtwerte deduplizieren Journalzeilen vor der Seiteneinteilung "
        "innerhalb des Kostenstellenfilters. Leere Kostenstellen stehen unter null. Fehlende Währungen bleiben unbekannt; "
        "gleichartige unbekannte Paare sind keine nachgewiesene gemeinsame Währung. Keine Endsalden ohne Anfangsbestand.",
    }


def _monthly_source(reader, company_id, year, account_from=None, account_to=None):
    _integer(company_id, "firma_id")
    _integer(year, "jahr")
    if year > 9999:
        raise ParameterFehler("jahr darf höchstens 9999 sein")
    bounds = []
    extra = ""
    effective = "CASE WHEN j.SammelKonto>0 THEN j.SammelKonto ELSE j.Konto END"
    for value, name, operator in ((account_from, "konto_von", ">="), (account_to, "konto_bis", "<=")):
        if value is not None:
            _integer(value, name, 0)
            extra += f" AND ({effective}){operator}?"
            bounds.append(value)
    if account_from is not None and account_to is not None and account_from > account_to:
        raise ParameterFehler("konto_von darf konto_bis nicht überschreiten")
    statement = _reader(reader)
    period = statement._fiscal_year(company_id, year)
    start, end = date.fromisoformat(period["Von"]), date.fromisoformat(period["Bis"])
    if start > end:
        raise DatenFehler("Das gespeicherte Wirtschaftsjahr hat einen ungültigen Zeitraum")
    months = []
    current = start.replace(day=1)
    while current <= end:
        months.append(current.strftime("%Y-%m"))
        if current.year == 9999 and current.month == 12:
            break
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    rows = statement._rows(
        f"SELECT {effective} AS konto, substr(b.Datum,1,7) AS monat, "
        "sum(CASE WHEN b.Art=2 THEN coalesce(j.BetragSoll,0) ELSE 0 END) AS es, "
        "sum(CASE WHEN b.Art=2 THEN coalesce(j.BetragHaben,0) ELSE 0 END) AS eh, "
        "sum(CASE WHEN b.Art=2 THEN 0 ELSE coalesce(j.BetragSoll,0) END) AS bs, "
        "sum(CASE WHEN b.Art=2 THEN 0 ELSE coalesce(j.BetragHaben,0) END) AS bh "
        "FROM JOURNAL j JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id "
        "WHERE b.Firma_id=? AND b.Wj_id=? AND b.Datum>=? AND b.Datum<=?" + extra
        + f" GROUP BY {effective}, substr(b.Datum,1,7) ORDER BY konto, monat",
        [company_id, period["_rowid"], period["Von"], period["Bis"], *bounds],
    )
    definitions = defaultdict(list)
    for row in statement._rows("SELECT Nummer, Bezeichnung, Typ FROM KONTO WHERE Firma_id=? ORDER BY Nummer", [company_id]):
        definitions[row["Nummer"]].append(row)
    return statement, period, months, rows, definitions


def monthly_accounts(reader, company_id, year, account_from=None, account_to=None, limit=100, offset=0):
    """Monatliche Hauptbuchbewegungen im gespeicherten Wirtschaftsjahr."""
    _page(company_id, limit, offset)
    _, period, months, rows, definitions = _monthly_source(reader, company_id, year, account_from, account_to)
    accounts = defaultdict(dict)
    totals = {month: _zeros() for month in months}
    for row in rows:
        if len(definitions[row["konto"]]) != 1:
            raise DatenFehler(f"Für Konto {row['konto']} wird genau eine Kontendefinition dieser Firma erwartet")
        values = [Decimal(str(row[field])) for field in ("es", "eh", "bs", "bh")]
        accounts[row["konto"]][row["monat"]] = values
        _add(totals[row["monat"]], values)

    def monthly(values):
        cumulative = ZERO
        output = []
        for month in months:
            amounts = values.get(month, _zeros())
            cumulative += amounts[0] - amounts[1] + amounts[2] - amounts[3]
            output.append({"monat": month, **_amounts(amounts, False),
                           "endsaldo": _money(cumulative) if period["Waehrung"] else None})
        return output

    ordered = sorted(accounts)
    selected = ordered[offset:offset + limit]
    more = offset + len(selected) < len(ordered)
    return {
        "firma_id": company_id, "wirtschaftsjahr": period, "sw_waehrung": period["Waehrung"],
        "konten": [{"konto": account, "bezeichnung": definitions[account][0]["Bezeichnung"],
                    "monate": monthly(accounts[account])} for account in selected],
        "gesamtwerte": monthly(totals), "anzahl_gesamt": len(ordered), "gekuerzt": more,
        "naechster_versatz": offset + len(selected) if more else None,
        "grundlage": _BASIS + " Kalendermonate innerhalb des gespeicherten Wirtschaftsjahres, nicht zwingend Januar bis Dezember. "
        "SW aus dem Wirtschaftsjahr; unbekannte Währung verhindert eindeutige Endsalden. "
        "Endsalden kumulieren nur gespeicherte Eröffnungen Art=2 und Bewegungen ab Wirtschaftsjahresbeginn; kein erfundener Anfangsvortrag. "
        "Positive Sammelkonten ersetzen Personenkonten je Zeile genau einmal. Gesamtsummen gelten vor der Seiteneinteilung.",
    }


def monthly_profit_and_loss(reader, company_id, year, structure_id=None):
    """GuV-Bewegungen monatlich auf die gespeicherte Hierarchie verdichten."""
    if structure_id is not None:
        _integer(structure_id, "gliederung_id")
    statement, period, months, rows, definitions = _monthly_source(reader, company_id, year)
    structure_id, nodes, children, assignments, roots = statement._layout(company_id, structure_id)
    own = defaultdict(lambda: defaultdict(lambda: ZERO))
    excluded = {month: _zeros() for month in months}
    for row in rows:
        account = row["konto"]
        values = [Decimal(str(row[field])) for field in ("es", "eh", "bs", "bh")]
        _add(excluded[row["monat"]], values[:2] + [ZERO, ZERO])
        if values[2] == 0 and values[3] == 0:
            continue
        if len(definitions[account]) != 1:
            raise DatenFehler(f"Für Konto {account} wird genau eine Kontendefinition dieser Firma erwartet")
        definition = definitions[account][0]
        candidates = assignments.get(account, {})
        profit_items = candidates.get("G", [])
        is_profit = str(definition["Typ"]).startswith("2")
        if not is_profit:
            if profit_items:
                raise DatenFehler(f"Konto {account} ist kein Erfolgskonto, aber der GuV zugeordnet")
            if definition["Typ"] is None:
                raise DatenFehler(f"Für Konto {account} fehlt der Kontotyp")
            continue
        if len(profit_items) != 1 or candidates.get("A") or candidates.get("P"):
            raise DatenFehler(f"Für Erfolgskonto {account} fehlt die eindeutige GuV-Zuordnung")
        item = profit_items[0]
        balance = values[2] - values[3]
        own[row["monat"]][item] += -balance if nodes[item]["VzWechsel"] else balance

    def report(month):
        totals = {}
        lines = []

        def rollup(item):
            totals[item] = own[month][item] + sum((rollup(child) for child in children[item]), ZERO)
            return totals[item]

        total = rollup(roots["G"])

        def emit(item, level):
            node = nodes[item]
            lines.append({"position_id": item, "eltern_id": node["ParentId"], "ebene": level,
                          "bezeichnung": node["Bezeichnung"], "vorzeichenwechsel": node["VzWechsel"],
                          "direktbetrag": _money(own[month][item]), "betrag": _money(totals[item])})
            for child in children[item]:
                emit(child, level + 1)

        emit(roots["G"], 0)
        return {"monat": month, "positionen": lines, "gewinn": _money(total)}

    monthly = [report(month) for month in months]
    return {
        "firma_id": company_id, "wirtschaftsjahr": period, "sw_waehrung": period["Waehrung"],
        "gliederung_id": structure_id, "monate": monthly,
        "jahresbewegungsgewinn": _money(sum((own[month][item] for month in months for item in own[month]), ZERO)),
        "ausgeschlossene_eroeffnungen": [{"monat": month, **_amounts(excluded[month], False)} for month in months],
        "grundlage": _BASIS + " Ausschließlich SW-Bewegungen; Art=2 ist ausgeschlossen und separat ausgewiesen. "
        "Erfolgskonten beginnen im gespeicherten Kontotyp mit 2. Bilanz- und Vortragskonten sind keine GuV. "
        "Vorzeichenwechsel wirkt wie im Jahresbericht auf die direkt zugeordneten Konten. Eltern summieren direkte Beträge und Kinder; "
        "Hierarchiepositionen dürfen nicht nochmals addiert werden. Kein monatlicher Bilanzausgleich wird vorausgesetzt. "
        "Unbekannte SW-Währung bleibt unbekannt; Beträge sind dann keiner nachgewiesenen Währung zugeordnet.",
    }
