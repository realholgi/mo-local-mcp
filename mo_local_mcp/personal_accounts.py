"""Journalbasierte Personenkontensalden ohne Ableitung historischer offener Posten."""

from collections import defaultdict
from decimal import Decimal

from .business import _dates, _integer
from .errors import ParameterFehler
from .statements import StatementReader, _money


def list_personal_balances(reader, company_id, side="customer", date_from=None,
                           date_to=None, address_id=None, limit=100, offset=0):
    """Konten einmal je gebuchtem FW-/SW-Währungspaar summieren, Adressen nur zuordnen."""
    _integer(company_id, "firma_id")
    _integer(limit, "anzahl")
    _integer(offset, "versatz", 0)
    if limit > 500:
        raise ParameterFehler("anzahl darf höchstens 500 sein")
    if side not in {"customer", "supplier"}:
        raise ParameterFehler("seite muss customer oder supplier sein")
    if address_id is not None:
        _integer(address_id, "adresse_id")
    prefix = "KF" if side == "customer" else "LF"
    where, bindings = ["j.Firma_id=?"], [company_id]
    _dates(where, bindings, "b.Datum", date_from, date_to)
    source = StatementReader(reader.database)
    addresses = source._rows(
        "SELECT a._rowid AS adresse_id, a.KZ_AdressNr AS adressnummer, "
        "a.KZ_Matchcode AS suchbegriff, a.RA_Firma1 AS name, "
        "a.RA_Vorname AS vorname, a.RA_Nachname AS nachname, "
        f"a.{prefix}_Status AS status, a.{prefix}_Waehrung AS stammwaehrung, "
        f"a.{prefix}_Konto AS konto FROM ADRESSE a WHERE a.Firma_id=? "
        f"AND (coalesce(a.{prefix}_Status,0)<>0 OR a.{prefix}_Konto>0) "
        "ORDER BY a._rowid", [company_id],
    )
    selected = [row for row in addresses if address_id is None or row["adresse_id"] == address_id]
    accounts = {row["konto"] for row in selected if row["konto"] is not None and row["konto"] > 0}
    by_account = defaultdict(list)
    for row in addresses:
        if row["konto"] in accounts:
            by_account[row["konto"]].append({key: value for key, value in row.items() if key != "konto"})

    # EXISTS statt Adress-JOIN: mehrere Adressen dürfen Journalbeträge nicht vervielfachen.
    address_filter = " AND a._rowid=?" if address_id is not None else ""
    where.append(
        f"EXISTS (SELECT 1 FROM ADRESSE a WHERE a.Firma_id=j.Firma_id "
        f"AND a.{prefix}_Konto=j.Konto AND a.{prefix}_Konto>0{address_filter})"
    )
    if address_id is not None:
        bindings.append(address_id)
    grouped = source._rows(
        "SELECT j.Konto AS konto, nullif(b.Waehrung,'') AS waehrung_fw, "
        "nullif(w.Waehrung,'') AS waehrung_sw, count(*) AS journalzeilen, "
        "sum(CASE WHEN b.Art=2 THEN 1 ELSE 0 END) AS eroeffnungszeilen, "
        "CASE WHEN nullif(w.Waehrung,'') IS NOT NULL THEN sum(coalesce(j.BetragSoll,0)) END AS soll_sw, "
        "CASE WHEN nullif(w.Waehrung,'') IS NOT NULL THEN sum(coalesce(j.BetragHaben,0)) END AS haben_sw, "
        "CASE WHEN nullif(b.Waehrung,'') IS NOT NULL THEN sum(coalesce(j.BetragSollFW,0)) END AS soll_fw, "
        "CASE WHEN nullif(b.Waehrung,'') IS NOT NULL THEN sum(coalesce(j.BetragHabenFW,0)) END AS haben_fw "
        "FROM JOURNAL j JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id "
        "LEFT JOIN WIRTSCHAFTSJAHR w ON w._rowid=b.Wj_id AND w.Firma_id=b.Firma_id "
        "WHERE " + " AND ".join(where) + " GROUP BY j.Konto, nullif(b.Waehrung,''), "
        "nullif(w.Waehrung,'') ORDER BY j.Konto, waehrung_fw, waehrung_sw", bindings,
    )
    entries = []
    totals = {}
    booked_accounts = set()
    for row in grouped:
        booked_accounts.add(row["konto"])
        row["adressen"] = by_account[row["konto"]]
        row["kontozuordnung"] = "vorhanden"
        key = (row["waehrung_fw"], row["waehrung_sw"])
        total = totals.setdefault(key, {
            "waehrung_fw": key[0], "waehrung_sw": key[1], "journalzeilen": 0,
            "eroeffnungszeilen": 0,
            "soll_sw": Decimal(0) if key[1] is not None else None,
            "haben_sw": Decimal(0) if key[1] is not None else None,
            "soll_fw": Decimal(0) if key[0] is not None else None,
            "haben_fw": Decimal(0) if key[0] is not None else None,
        })
        for field in ("journalzeilen", "eroeffnungszeilen"):
            total[field] += row[field]
        for field in ("soll_sw", "haben_sw", "soll_fw", "haben_fw"):
            if row[field] is not None:
                row[field] = Decimal(str(row[field]))
                total[field] += row[field]
        entries.append(row)
    for account in sorted(accounts - booked_accounts):
        entries.append({
            "konto": account, "adressen": by_account[account], "kontozuordnung": "vorhanden",
            "waehrung_fw": None, "waehrung_sw": None, "journalzeilen": 0,
            "eroeffnungszeilen": 0, "soll_sw": Decimal(0), "haben_sw": Decimal(0),
            "soll_fw": Decimal(0), "haben_fw": Decimal(0),
        })
    entries.sort(key=lambda row: (row["konto"], row["waehrung_fw"] or "", row["waehrung_sw"] or ""))
    for row in selected:
        if row["konto"] is None or row["konto"] <= 0:
            entries.append({
                "konto": None, "adressen": [{key: value for key, value in row.items() if key != "konto"}],
                "kontozuordnung": "fehlt", "waehrung_fw": None, "waehrung_sw": None,
                "journalzeilen": 0, "eroeffnungszeilen": 0,
                "soll_sw": None, "haben_sw": None, "soll_fw": None, "haben_fw": None,
            })
    total_rows = list(totals.values())
    for row in [*entries, *total_rows]:
        for currency in ("sw", "fw"):
            debit, credit = row[f"soll_{currency}"], row[f"haben_{currency}"]
            row[f"saldo_{currency}"] = None if debit is None else debit - credit
            for field in (f"soll_{currency}", f"haben_{currency}", f"saldo_{currency}"):
                if row[field] is not None:
                    row[field] = _money(row[field])
    page = entries[offset:offset + limit]
    truncated = offset + len(page) < len(entries)
    return {
        "firma_id": company_id, "seite": "Debitoren" if side == "customer" else "Kreditoren",
        "datum_von": date_from, "datum_bis": date_to, "adresse_id": address_id,
        "entries": page, "total_entries": len(entries), "totals": total_rows,
        "truncated": truncated, "next_offset": offset + len(page) if truncated else None,
        "geld_einheit": "Währungseinheiten als Dezimalzeichenketten; bereits durch 100 geteilt",
        "basis": (
            "Tatsächliche Journal-Soll-/Habenbeträge im inklusiven Datumsbereich; Saldo = Soll minus Haben. "
            "Alle Buchungsstatus und vorzeichenbehafteten Stornos bleiben enthalten. "
            "Eröffnungen (Art=2) sind enthalten und werden nicht als Umsatz bezeichnet. "
            "Gruppierung nach Personenkonto, Buchungswährung (FW) und Wirtschaftsjahreswährung (SW). "
            "Konten stammen ausschließlich aus den aktuellen KF_Konto-/LF_Konto-Adresszuordnungen. "
            "Summen umfassen alle gefilterten Journalzeilen vor der Seiteneinteilung."
        ),
        "hinweise": [
            "Kein historischer OP-Saldo und keine Aussage zu offenen oder fälligen Rechnungen.",
            ("Gemeinsame Konten werden einmal gezählt. Ein Adressfilter wählt das gesamte zugeordnete Konto; "
             "eine Aufteilung auf einzelne Adressen ist aus dem Journal nicht belegt."),
            ("Stammwährungen stehen nur bei den Adressen. Fehlt eine gebuchte Währung, bleiben die zugehörigen "
             "Beträge unbekannt (null). Unterschiedliche FW-/SW-Währungspaare werden nie addiert oder umgerechnet."),
            ("Unbebuchte zugeordnete Konten haben Nullbeträge und keine gebuchte Währung. "
             "Ohne Kontozuordnung sind Beträge unbekannt und fließen nicht in Summen ein."),
            ("Inaktive, gesperrte und sonstige gespeicherte Rollenstatus bleiben sichtbar. "
             "Adressen ohne Rolle und ohne zugeordnetes Konto bleiben ausgeschlossen."),
            "Leere Soll-/Habenfelder werden wie in den Kontoauszügen als null Währungseinheiten behandelt.",
        ],
    }
