"""Abstimmung gespeicherter Sammelkontenzuordnungen mit Journal und historischen OPs."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from .business import _integer
from .errors import ParameterFehler
from .receivables import OP_AS_OF_SQL
from .statements import StatementReader, _money


def _date(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def reconcile_accounts(reader, company_id, year, as_of, limit=100, offset=0):
    """Firma/Jahr/Stichtag explizit; vollständige Summen, paginierte Befunde, nur SW-Vergleich."""
    for value, name, minimum in ((company_id, "firma_id", 1), (year, "jahr", 1),
                                 (limit, "anzahl", 1), (offset, "versatz", 0)):
        try:
            _integer(value, name, minimum)
        except ValueError as error:
            raise ParameterFehler(str(error)) from error
    if year > 9999 or limit > 500:
        raise ParameterFehler("jahr darf höchstens 9999 und anzahl höchstens 500 sein")
    if not _date(as_of):
        raise ParameterFehler("stichtag muss das Format JJJJ-MM-TT haben")
    source = StatementReader(reader.database)
    periods = source._rows(
        "SELECT _rowid,Von,Bis,Waehrung FROM WIRTSCHAFTSJAHR WHERE Firma_id=? ORDER BY Von,_rowid",
        [company_id],
    )
    candidates = [p for p in periods if isinstance(p["Von"], str) and p["Von"][:4] == str(year)]
    findings = []

    def finding(kind, reasons, **values):
        row = dict(pruefung=kind, **values)
        row["gruende"] = sorted(set(reasons))
        row["status"] = "nicht_abstimmbar" if reasons else (
            "abweichung" if row["differenz_sw"] != "0.00" else "abgestimmt")
        findings.append(row)

    if len(candidates) != 1:
        finding("Zeitraum", ["Wirtschaftsjahr fehlt oder Beginnjahr ist mehrdeutig."])
        period = None
    else:
        period = candidates[0]
        if not _date(period["Von"]) or not _date(period["Bis"]) or not period["Von"] <= as_of <= period["Bis"]:
            finding("Zeitraum", ["Stichtag liegt nicht in einem gültigen gespeicherten Wirtschaftsjahr."])
            period = None

    if period is not None:
        _reconcile(source, company_id, as_of, period, periods, finding)
    counts = Counter(row["status"] for row in findings)
    totals = []
    # Keine Addition verschiedener Seiten, FW- oder SW-Währungen; Befundseiten ändern Summen nicht.
    groups = defaultdict(list)
    for row in findings:
        if "seite" in row:
            groups[(row["pruefung"], row["seite"], row["waehrung_fw"], row["waehrung_sw"])].append(row)
    for key, rows in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        total: dict = dict(zip(("pruefung", "seite", "waehrung_fw", "waehrung_sw"), key))
        total["befunde"] = len(rows)
        total["nicht_abstimmbar"] = sum(row["status"] == "nicht_abstimmbar" for row in rows)
        for field in ("saldo_links_sw", "saldo_rechts_sw", "differenz_sw"):
            total[field] = (format(sum((Decimal(row[field]) for row in rows), Decimal(0)), ".2f")
                            if all(row.get(field) is not None for row in rows) else None)
        totals.append(total)
    page = findings[offset:offset + limit]
    truncated = offset + len(page) < len(findings)
    return {
        "firma_id": company_id, "jahr": year, "stichtag": as_of,
        "wirtschaftsjahr_id": period["_rowid"] if period else None,
        "status": ("nicht_abstimmbar" if counts["nicht_abstimmbar"] or not findings else
                   "abweichung" if counts["abweichung"] else "abgestimmt"),
        "entries": page, "total_entries": len(findings), "totals": totals,
        "status_anzahl": dict(counts), "truncated": truncated,
        "next_offset": offset + len(page) if truncated else None,
        "geld_einheit": "Währungseinheiten als Dezimalzeichenketten; bereits durch 100 geteilt",
        "basis": [
            "Hauptbuch = Journal mit positivem SammelKonto statt Konto, einschließlich direkter Sammelkontobuchungen; Personenkonten werden nicht doppelt gezählt.",
            "Personenkonten stammen aus aktuellen KF_Konto-/LF_Konto-Zuordnungen und expliziten POSTEN.PKonto-/Seitenwerten. Sammelkonten ausschließlich aus JOURNAL.SammelKonto im gewählten Jahr bis Stichtag.",
            "Journal enthält Eröffnungen, alle Statuswerte und vorzeichenbehaftete Stornos vom Jahresbeginn bis Stichtag. Saldo Soll minus Haben; OP-Verbindlichkeiten werden für diesen Vergleich negiert.",
            "OP-Rekonstruktion umfasst auch frühere Jahre und ausgeglichene Belege, nicht Entwürfe. Fehlende oder widersprüchliche Zahlungshistorie bleibt unbekannt. Kein historisches Änderungsprotokoll.",
            "OP-SW-Währung wird nur über genau ein gespeichertes Wirtschaftsjahr zum Belegdatum zugeordnet. Unterschiedliche FW-/SW-Währungen werden nicht verrechnet; gemischte FW je Konto sind nicht abstimmbar.",
            "Abgestimmt bedeutet nur rechnerische Übereinstimmung im belegten Umfang, keinen Nachweis vollständiger Buchführung oder richtiger Eröffnungen. Aktuelle Stammdaten belegen keine historischen Kontozuordnungen. Differenzen enthalten keine Ursachenzuschreibung.",
        ],
    }


def _reconcile(source, company_id, as_of, period, periods, finding):
    definitions = Counter(row["Nummer"] for row in source._rows(
        "SELECT Nummer FROM KONTO WHERE Firma_id=?", [company_id]))
    roles = defaultdict(set)
    role_issues = []
    for row in source._rows(
        "SELECT _rowid,KF_Konto,LF_Konto,KF_Status,LF_Status FROM ADRESSE WHERE Firma_id=? ORDER BY _rowid",
        [company_id],
    ):
        for prefix, side in (("KF", "receivable"), ("LF", "payable")):
            account = row[prefix + "_Konto"]
            if account is not None and account > 0:
                roles[account].add(side)
            elif row[prefix + "_Status"]:
                role_issues.append(f"Adresse {row['_rowid']}: {prefix}_Konto fehlt.")
    items = source._rows(OP_AS_OF_SQL +
        " SELECT _rowid,PKonto,side,Datum,Waehrung,open_as_of_SW,history_status,pre_document_allocations FROM items ORDER BY _rowid",
        [as_of, company_id])
    for row in items:
        if row["PKonto"] is not None and row["PKonto"] > 0:
            roles[row["PKonto"]].add(row["side"])
        else:
            role_issues.append(f"OP {row['_rowid']}: PKonto fehlt.")
    for row in source._rows(
        "SELECT _rowid,Datum FROM POSTEN WHERE Firma_id=? AND coalesce(Entwurf,0)=0 "
        "AND Art IN (0,1,2,3) ORDER BY _rowid", [company_id],
    ):
        if not _date(row["Datum"]):
            role_issues.append(f"OP {row['_rowid']}: Belegdatum fehlt oder ist ungültig; Stichtagszuordnung unbekannt.")
    for row in source._rows(
        "SELECT zp._rowid,z.Datum FROM ZAHLUNGSPOSITION zp "
        "JOIN POSTENPOSITION pp ON pp._rowid=zp.Postenposition_id AND pp.Firma_id=zp.Firma_id "
        "JOIN POSTEN p ON p._rowid=pp.Posten_id AND p.Firma_id=pp.Firma_id "
        "LEFT JOIN ZAHLUNG z ON z._rowid=zp.Zahlung_id AND z.Firma_id=zp.Firma_id "
        "WHERE zp.Firma_id=? AND p.Datum<=? AND coalesce(p.Entwurf,0)=0 AND p.Art IN (0,1,2,3) "
        "ORDER BY zp._rowid", [company_id, as_of],
    ):
        matches = [p for p in periods if _date(p["Von"]) and _date(p["Bis"])
                   and _date(row["Datum"]) and p["Von"] <= row["Datum"] <= p["Bis"]]
        if len(matches) != 1 or not matches[0]["Waehrung"] or matches[0]["Waehrung"] != period["Waehrung"]:
            role_issues.append(f"Zahlungszuordnung {row['_rowid']}: SW-Währung/Zahlungsperiode fehlt, ist mehrdeutig oder abweichend.")
    ledger = source._rows(
        "SELECT j._rowid,j.Konto,j.SammelKonto,j.BetragSoll,j.BetragHaben,"
        "b._rowid AS booking_id,b.Wj_id,b.Datum,b.Waehrung FROM JOURNAL j "
        "LEFT JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id "
        "WHERE j.Firma_id=? AND (b.Wj_id=? OR (b.Datum>=? AND b.Datum<=?) OR b._rowid IS NULL) ORDER BY j._rowid",
        [company_id, period["_rowid"], period["Von"], as_of])
    global_reasons = list(role_issues)
    if not period["Waehrung"]:
        global_reasons.append("SW-Währung des Wirtschaftsjahrs fehlt.")
    for other in periods:
        if (other["_rowid"] != period["_rowid"] and _date(other["Von"]) and _date(other["Bis"])
                and other["Von"] <= period["Bis"] and other["Bis"] >= period["Von"]):
            global_reasons.append("Gespeicherte Wirtschaftsjahre überlappen sich.")
    selected = []
    for row in ledger:
        if row["booking_id"] is None:
            global_reasons.append(f"Journalzeile {row['_rowid']}: firmengebundener Buchungskopf fehlt.")
        elif not _date(row["Datum"]) or not period["Von"] <= row["Datum"] <= period["Bis"]:
            global_reasons.append(f"Journalzeile {row['_rowid']}: Datum widerspricht Wirtschaftsjahr.")
        elif row["Datum"] <= as_of:
            if row["Wj_id"] != period["_rowid"]:
                global_reasons.append(f"Journalzeile {row['_rowid']}: abweichende Wirtschaftsjahrzuordnung.")
            else:
                selected.append(row)
    mappings = defaultdict(set)
    for row in selected:
        if row["SammelKonto"] is not None and row["SammelKonto"] > 0:
            mappings[row["Konto"]].add(row["SammelKonto"])
            if row["Konto"] not in roles:
                global_reasons.append(f"Konto {row['Konto']}: Sammelkontobuchung ohne belegte Personenkontenseite.")
    if not roles:
        finding("Abdeckung", global_reasons + ["Keine gespeicherten Personenkontenzuordnungen vorhanden."])
        return

    def amount(rows):
        return sum((Decimal(str(row["BetragSoll"] or 0)) - Decimal(str(row["BetragHaben"] or 0))
                    for row in rows), Decimal(0))

    def compare(kind, reasons, left, right, **values):
        finding(kind, reasons, saldo_links_sw=_money(left) if left is not None else None,
                saldo_rechts_sw=_money(right) if right is not None else None,
                differenz_sw=_money(left - right) if not reasons and left is not None and right is not None else None,
                **values)

    main_groups = defaultdict(set)
    for account, sides in sorted(roles.items()):
        rows = [row for row in selected if row["Konto"] == account]
        ops = [row for row in items if row["PKonto"] == account]
        currencies = {row["Waehrung"] or None for row in rows} | {row["Waehrung"] or None for row in ops}
        reasons = list(global_reasons)
        if len(sides) != 1:
            reasons.append("Personenkonto ist mehreren Seiten zugeordnet.")
        if definitions[account] != 1:
            reasons.append("Personenkontodefinition fehlt oder ist mehrdeutig.")
        targets = mappings[account]
        if len(targets) != 1 or any(not row["SammelKonto"] or row["SammelKonto"] <= 0 for row in rows):
            reasons.append("Sammelkontozuordnung fehlt oder ist uneinheitlich.")
        if len(currencies) != 1 or None in currencies:
            reasons.append("FW-Währung fehlt oder Konto enthält unterschiedliche FW-Währungen.")
        for side in sorted(sides):
            for currency in sorted(currencies or {None}, key=str):
                subset = [row for row in ops if row["side"] == side and (row["Waehrung"] or None) == currency]
                local = list(reasons)
                known = Decimal(0)
                unknown = 0
                for op in subset:
                    matches = [p for p in periods if _date(p["Von"]) and _date(p["Bis"]) and p["Von"] <= op["Datum"] <= p["Bis"]]
                    if len(matches) != 1 or not matches[0]["Waehrung"] or matches[0]["Waehrung"] != period["Waehrung"]:
                        local.append(f"OP {op['_rowid']}: SW-Währung/Belegperiode fehlt, ist mehrdeutig oder abweichend.")
                    if op["open_as_of_SW"] is None:
                        unknown += 1
                        history = "abweichend" if op["history_status"] == "mismatch" else "unbekannt"
                        local.append(f"OP {op['_rowid']}: historische Zahlungshistorie {history}; Saldo unbekannt.")
                    else:
                        known += Decimal(str(op["open_as_of_SW"]))
                    if op["pre_document_allocations"]:
                        local.append(f"OP {op['_rowid']}: Zahlungszuordnung vor Belegdatum.")
                values = dict(seite=side, konto=account, sammelkonten=sorted(targets),
                              waehrung_fw=currency, waehrung_sw=period["Waehrung"],
                              op_anzahl=len(subset), unbekannte_op_salden=unknown,
                              bekannte_op_summe_sw=_money(known))
                compare("Personenkonto_OP", local,
                        amount([row for row in rows if (row["Waehrung"] or None) == currency]),
                        None if unknown else known * (-1 if side == "payable" else 1), **values)
                for target in targets:
                    main_groups[(side, target, currency)].add(account)
    for (side, target, currency), accounts in sorted(main_groups.items(), key=lambda item: str(item[0])):
        rows = [row for row in selected if (row["SammelKonto"] if row["SammelKonto"] and row["SammelKonto"] > 0 else row["Konto"]) == target]
        reasons = list(global_reasons)
        if definitions[target] != 1 or target in roles:
            reasons.append("Sammelkontodefinition fehlt, ist mehrdeutig oder zugleich Personenkonto.")
        if {row["Waehrung"] or None for row in rows} != {currency} or currency is None:
            reasons.append("Sammelkonto enthält fehlende oder unterschiedliche FW-Währungen.")
        if any(other_side != side and other_target == target for other_side, other_target, _ in main_groups):
            reasons.append("Sammelkonto ist mehreren Personenkontenseiten zugeordnet.")
        if any(len(roles[account]) != 1 or mappings[account] != {target} or definitions[account] != 1
               for account in accounts):
            reasons.append("Zugeordnete Personenkonten sind nicht eindeutig definiert oder zugeordnet.")
        if any(row["Konto"] in accounts and row["SammelKonto"] != target for row in selected):
            reasons.append("Personenkontobuchungen ohne einheitliche Sammelkontozuordnung.")
        compare("Hauptbuch_Personenkonten", reasons,
                amount([row for row in rows if (row["Waehrung"] or None) == currency]),
                amount([row for row in selected if row["Konto"] in accounts and (row["Waehrung"] or None) == currency]),
                seite=side, konto=target, personenkonten=sorted(accounts),
                waehrung_fw=currency, waehrung_sw=period["Waehrung"])
