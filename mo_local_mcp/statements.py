"""MonKey-Finanzberichte und Kontoauszüge aus gespeicherten Daten rekonstruieren."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .business import _integer


ZERO = Decimal(0)


def _money(minor_units):
    return format((minor_units / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


class StatementReader:
    def __init__(self, database):
        self.database = database

    def _rows(self, sql, bindings):
        """Vollständige Berichtsgrundlagen ohne unbemerkte Abfragekürzung abrufen."""
        rows = []
        offset = 0
        while True:
            result = self.database.query(sql + f" LIMIT -1 OFFSET {offset}", bindings, 500)
            rows.extend(dict(zip(result["columns"], row)) for row in result["rows"])
            if not result["truncated"]:
                return rows
            if not result["rows"]:
                raise ValueError("Eine Berichtsquellzeile überschreitet die Ausgabegrenze der Abfrage")
            offset += len(result["rows"])

    def _fiscal_year(self, company_id, year):
        rows = self._rows(
            "SELECT _rowid, Bezeichnung, Von, Bis, Waehrung, Gesperrt FROM WIRTSCHAFTSJAHR "
            "WHERE Firma_id=? AND substr(Von,1,4)=? ORDER BY Von, _rowid",
            [company_id, str(year)],
        )
        if len(rows) != 1:
            raise ValueError("Für diese Firma wird genau ein Wirtschaftsjahr mit Beginn im angefragten Jahr erwartet")
        return rows[0]

    def account_statement(self, company_id, year, account, limit=100, offset=0):
        _integer(company_id, "firma_id")
        _integer(year, "jahr")
        _integer(account, "konto", 0)
        _integer(limit, "anzahl")
        _integer(offset, "versatz", 0)
        if year > 9999 or limit > 500:
            raise ValueError("jahr darf höchstens 9999 und anzahl höchstens 500 sein")
        period = self._fiscal_year(company_id, year)
        definitions = self._rows(
            "SELECT Nummer, Bezeichnung FROM KONTO WHERE Firma_id=? AND Nummer=? ORDER BY Nummer",
            [company_id, account],
        )
        if len(definitions) != 1:
            raise ValueError("Genau eine Kontendefinition in dieser Firma erwartet")
        ledger = (
            "SELECT b.Datum AS date, b.BelegNr AS document_number, j.Text AS text, "
            "j.GegenKonto AS contra_account, j.Nummer AS journal_number, j.Steuersatz AS tax_code, "
            "j.NummerLong AS sort_number, j.Position AS position, "
            "b._rowid AS booking_id, j._rowid AS journal_row_id, j.Storno AS storno, "
            "CASE WHEN b.Art=2 THEN 1 ELSE 0 END AS opening_entry, "
            "coalesce(j.BetragSoll,0) AS debit, coalesce(j.BetragHaben,0) AS credit "
            "FROM JOURNAL j JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id "
            "WHERE b.Firma_id=? AND b.Wj_id=? AND b.Datum>=? AND b.Datum<=? "
            "AND (j.Konto=? OR j.SammelKonto=?)"
        )
        bindings = [company_id, period["_rowid"], period["Von"], period["Bis"], account, account]
        result = self.database.query(
            "WITH ledger AS (" + ledger + ") SELECT "
            "coalesce(sum(opening_entry),0) AS opening_count, "
            "coalesce(sum(CASE WHEN opening_entry=1 THEN debit ELSE 0 END),0) AS opening_debit, "
            "coalesce(sum(CASE WHEN opening_entry=1 THEN credit ELSE 0 END),0) AS opening_credit, "
            "count(*)-coalesce(sum(opening_entry),0) AS movement_count, "
            "coalesce(sum(CASE WHEN opening_entry=0 THEN debit ELSE 0 END),0) AS movement_debit, "
            "coalesce(sum(CASE WHEN opening_entry=0 THEN credit ELSE 0 END),0) AS movement_credit "
            "FROM ledger", bindings, 1,
        )
        totals = dict(zip(result["columns"], result["rows"][0]))
        opening_balance = Decimal(str(totals["opening_debit"])) - Decimal(str(totals["opening_credit"]))
        closing_balance = opening_balance + Decimal(str(totals["movement_debit"])) - Decimal(str(totals["movement_credit"]))
        # LIMIT/OFFSET steht außerhalb der Fensterberechnung, damit spätere Seiten
        # den laufenden Jahressaldo einschließlich des Netto-Eröffnungswerts behalten.
        result = self.database.query(
            "WITH ledger AS (" + ledger + "), movements AS "
            "(SELECT * FROM ledger WHERE opening_entry=0) "
            "SELECT date, document_number, text, contra_account, journal_number, "
            "booking_id, journal_row_id, storno, tax_code, debit, credit, "
            "? + sum(debit-credit) OVER (ORDER BY date, document_number, sort_number, position, journal_row_id "
            "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance "
            "FROM movements ORDER BY date, document_number, sort_number, position, journal_row_id "
            "LIMIT -1 OFFSET ?",
            [*bindings, str(opening_balance), offset], limit,
        )
        if result["truncated"] and not result["rows"]:
            raise ValueError("Eine Kontoauszugszeile überschreitet die Ausgabegrenze der Abfrage")
        entries = []
        for values in result["rows"]:
            entry = dict(zip(result["columns"], values))
            balance = Decimal(str(entry["balance"]))
            for field in ("debit", "credit", "balance"):
                entry[field] = _money(Decimal(str(entry[field])))
            entry["balance_side"] = "H" if balance < 0 else "S" if balance > 0 else ""
            entries.append(entry)
        return {
            "company_id": company_id, "fiscal_year": period,
            "account": {"number": account, "name": definitions[0]["Bezeichnung"]},
            "currency": period["Waehrung"],
            "money_unit": "Währungseinheiten als Dezimalzeichenketten; bereits durch 100 geteilt",
            "opening": {
                "entries": totals["opening_count"],
                "debit": _money(Decimal(str(totals["opening_debit"]))),
                "credit": _money(Decimal(str(totals["opening_credit"]))),
                "balance": _money(opening_balance),
            },
            "turnovers": {
                "debit": _money(Decimal(str(totals["movement_debit"]))),
                "credit": _money(Decimal(str(totals["movement_credit"]))),
            },
            "closing_balance": _money(closing_balance),
            "total_entries": totals["movement_count"],
            "entries": entries, "truncated": result["truncated"],
            "next_offset": offset + len(entries) if result["truncated"] else None,
            "basis": "Alle Perioden und Statuswerte; Eröffnungsbuchungen mit Art=2 werden gesondert summiert und aus den Umsätzen ausgeschlossen. Reihenfolge nach Datum, Beleg und Journal. Sammelkonten enthalten passende SammelKonto-Zeilen genau einmal.",
            "caveats": [
                "Vorzeichenbehaftete Soll-/Habenbeträge erhalten Storno- und Umkehrbuchungen; nicht entfernen oder erneut negieren.",
                "Der Saldo ist Soll minus Haben: negativ bedeutet H, positiv bedeutet S.",
                "Eröffnungssummen, Umsätze und Schlusssaldo umfassen das gesamte Wirtschaftsjahr, nicht nur diese Seite.",
                "Rekonstruktion aus einem festen Datenbankstand, kein Bankauszug und kein Nachweis des tatsächlichen Bargeldbestands.",
            ],
        }

    def _layout(self, company_id, structure_id):
        structures = self._rows(
            "SELECT _rowid FROM KONTOSTRUKTUR WHERE Firma_id=? ORDER BY _rowid", [company_id]
        )
        ids = [row["_rowid"] for row in structures]
        if structure_id is None:
            if len(ids) != 1:
                raise ValueError(f"gliederung_id ausdrücklich aus den Gliederungen dieser Firma wählen: {ids}")
            structure_id = ids[0]
        elif structure_id not in ids:
            raise ValueError("Berichtsgliederung in dieser Firma nicht gefunden")
        positions = self._rows(
            "SELECT ItemId, ParentId, VzWechsel, Bezeichnung, Kontoliste, Struktur "
            "FROM STRUKTURPOSITION WHERE Firma_id=? AND Ks_id=? ORDER BY ItemId",
            [company_id, structure_id],
        )
        nodes = {}
        children = defaultdict(list)
        assignments = defaultdict(lambda: defaultdict(list))
        for row in positions:
            item_id = row["ItemId"]
            side = row["Struktur"]
            if item_id in nodes or side not in {"A", "P", "G", "B"}:
                raise ValueError("Nicht unterstützte oder doppelte Gliederungsposition")
            accounts = []
            for token in (row["Kontoliste"] or "").split(","):
                token = token.strip()
                if token:
                    if not token.isdecimal():
                        raise ValueError(f"Nicht unterstützter Kontenlistenausdruck in Berichtsposition {item_id}")
                    accounts.append(int(token))
            if side == "B" and accounts:
                raise ValueError("Die Jahresergebnisposition darf nicht zusätzlich Konten auflisten")
            nodes[item_id] = row
            children[row["ParentId"]].append(item_id)
            for account in accounts:
                assignments[account][side].append(item_id)
        roots = {}
        for side in ("A", "P", "G"):
            matches = [i for i in children[0] if nodes[i]["Struktur"] == side]
            if len(matches) != 1:
                raise ValueError("Eine vollständige Bilanz-/GuV-Gliederung mit je einer Wurzel A, P und G ist erforderlich")
            roots[side] = matches[0]
        visited = set()

        def validate(item_id, parent_side):
            if item_id in visited:
                raise ValueError("Zyklische Berichtshierarchie")
            visited.add(item_id)
            node = nodes[item_id]
            if node["Struktur"] not in ({"P", "B"} if parent_side == "P" else {parent_side}):
                raise ValueError("Nicht unterstützte Mischung von Berichtsabschnitten")
            for child in children[item_id]:
                validate(child, parent_side)

        for side, root in roots.items():
            validate(root, side)
        if len(visited) != len(nodes):
            raise ValueError("In der Berichtshierarchie fehlen übergeordnete Positionen oder es gibt nicht unterstützte Wurzeln")
        if sum(node["Struktur"] == "B" for node in nodes.values()) != 1:
            raise ValueError("Genau eine eingebettete Jahresergebnisposition ist erforderlich")
        return structure_id, nodes, children, assignments, roots

    def _balances(self, company_id, period):
        # Personenkontobuchungen fließen in ihr gespeichertes Sammelkonto ein.
        # Das Personenkonto nicht zusätzlich addieren: Sonst würden Forderungen/Verbindlichkeiten verdoppelt.
        return self._rows(
            "SELECT CASE WHEN j.SammelKonto>0 THEN j.SammelKonto ELSE j.Konto END AS account, "
            "k.Bezeichnung AS name, k.Typ AS type, "
            "sum(coalesce(j.BetragSoll,0)) AS debit, sum(coalesce(j.BetragHaben,0)) AS credit "
            "FROM JOURNAL j JOIN BUCHUNG b ON b._rowid=j.Buchung_id AND b.Firma_id=j.Firma_id "
            "LEFT JOIN KONTO k ON k.Firma_id=j.Firma_id AND "
            "k.Nummer=CASE WHEN j.SammelKonto>0 THEN j.SammelKonto ELSE j.Konto END "
            "WHERE b.Firma_id=? AND b.Wj_id=? AND b.Datum>=? AND b.Datum<=? "
            "GROUP BY account, k.Bezeichnung, k.Typ ORDER BY account",
            [company_id, period["_rowid"], period["Von"], period["Bis"]],
        )

    def _calculate(self, company_id, period, nodes, children, assignments, roots):
        own = defaultdict(lambda: ZERO)
        accounts = defaultdict(dict)
        journal_difference = ZERO
        controls = ZERO
        for row in self._balances(company_id, period):
            balance = Decimal(str(row["debit"])) - Decimal(str(row["credit"]))
            journal_difference += balance
            if balance == 0:
                continue
            account = row["account"]
            if row["type"] is None:
                raise ValueError(f"Für Konto {account} fehlt die Kontendefinition dieser Firma")
            candidates = assignments.get(account, {})
            if candidates.get("G") and (candidates.get("A") or candidates.get("P")):
                raise ValueError(f"Konto {account} ist mehrdeutig Bilanz und GuV zugeordnet")
            if candidates.get("G"):
                selected = candidates["G"]
            elif candidates.get("A") and candidates.get("P"):
                # Nur tatsächlich beidseitig gelistete Konten wechseln nach Saldovorzeichen die Seite.
                selected = candidates["A" if balance > 0 else "P"]
            else:
                selected = candidates.get("A", candidates.get("P", []))
            if len(selected) != 1:
                if not selected and str(row["type"]).startswith("3"):
                    controls += balance
                    continue
                raise ValueError(f"Für Konto {account} mit Saldo ungleich null fehlt die Berichtszuordnung oder sie ist mehrdeutig")
            item_id = selected[0]
            node = nodes[item_id]
            signed = -balance if node["Struktur"] == "P" else balance
            if node["VzWechsel"]:
                signed = -signed
            own[item_id] += signed
            accounts[item_id][account] = {"name": row["name"], "amount": signed}
        if _money(journal_difference) != "0.00" or _money(controls) != "0.00":
            raise ValueError("Journal oder ausgeschlossene Vortragskonten sind nicht ausgeglichen")
        totals = {}

        def total(item_id):
            if item_id not in totals:
                totals[item_id] = own[item_id] + sum((total(child) for child in children[item_id]), ZERO)
            return totals[item_id]

        annual_result = total(roots["G"])
        for item_id, node in nodes.items():
            if node["Struktur"] == "B":
                own[item_id] = -annual_result if node["VzWechsel"] else annual_result
        for root in (roots["A"], roots["P"]):
            total(root)
        if _money(totals[roots["A"]]) != _money(totals[roots["P"]]):
            raise ValueError("Die rekonstruierte Bilanz ist nicht ausgeglichen; Berichtsgliederung prüfen")
        return totals, accounts, annual_result

    def financial_statements(self, company_id, year, structure_id=None, include_previous_year=True):
        _integer(company_id, "firma_id")
        _integer(year, "jahr")
        if not 1 <= year <= 9999:
            raise ValueError("jahr muss zwischen 1 und 9999 liegen")
        if structure_id is not None:
            _integer(structure_id, "gliederung_id")
        period = self._fiscal_year(company_id, year)
        structure_id, nodes, children, assignments, roots = self._layout(company_id, structure_id)
        current = self._calculate(company_id, period, nodes, children, assignments, roots)
        previous_period = None
        previous = None
        if include_previous_year:
            previous_end = (date.fromisoformat(period["Von"]) - timedelta(days=1)).isoformat()
            matches = self._rows(
                "SELECT _rowid, Bezeichnung, Von, Bis, Waehrung, Gesperrt FROM WIRTSCHAFTSJAHR "
                "WHERE Firma_id=? AND Bis=? ORDER BY Von, _rowid", [company_id, previous_end]
            )
            if len(matches) > 1:
                raise ValueError("Das vorangehende Wirtschaftsjahr ist nicht eindeutig")
            if matches:
                previous_period = matches[0]
                if previous_period["Waehrung"] != period["Waehrung"]:
                    raise ValueError("Wirtschaftsjahre mit unterschiedlichen Berichtswährungen können nicht verglichen werden")
                previous = self._calculate(company_id, previous_period, nodes, children, assignments, roots)

        def section(side):
            lines = []
            visible = {}

            def has_values(item_id):
                if item_id not in visible:
                    own_values = bool(current[1].get(item_id)) or (
                        previous is not None and bool(previous[1].get(item_id))
                    )
                    visible[item_id] = (
                        current[0][item_id] != 0
                        or (previous is not None and previous[0][item_id] != 0)
                        or own_values
                        or any(has_values(child) for child in children[item_id])
                    )
                return visible[item_id]


            def append(item_id, depth):
                amount = current[0][item_id]
                prior = previous[0][item_id] if previous is not None else None
                if not has_values(item_id) and item_id != roots[side]:
                    return
                account_rows = []
                now_accounts = current[1].get(item_id, {})
                old_accounts = previous[1].get(item_id, {}) if previous is not None else {}
                for account in sorted(now_accounts.keys() | old_accounts.keys()):
                    now = now_accounts.get(account)
                    old = old_accounts.get(account)
                    account_rows.append({
                        "account": account,
                        "name": (now or old)["name"],
                        "amount": _money(now["amount"] if now else ZERO),
                        "previous_amount": _money(old["amount"] if old else ZERO) if previous else None,
                    })
                node = nodes[item_id]
                lines.append({
                    "item_id": item_id, "parent_id": node["ParentId"], "depth": depth,
                    "name": node["Bezeichnung"], "amount": _money(amount),
                    "previous_amount": _money(prior) if prior is not None else None,
                    "accounts": account_rows,
                })
                for child in children[item_id]:
                    append(child, depth + 1)

            append(roots[side], 0)
            return {"total": _money(current[0][roots[side]]),
                    "previous_total": _money(previous[0][roots[side]]) if previous else None,
                    "lines": lines}

        return {
            "company_id": company_id, "fiscal_year": period, "previous_fiscal_year": previous_period,
            "structure_id": structure_id, "currency": period["Waehrung"],
            "money_unit": "Währungseinheiten als Dezimalzeichenketten; bereits durch 100 geteilt",
            "basis": "Gespeicherte Hierarchie und Kontenlisten aus STRUKTURPOSITION sowie JOURNAL-Buchungen des Wirtschaftsjahres, alle Perioden und Buchungsstatuswerte; einschließlich gebuchter Eröffnungswerte, ohne Vorjahressalden erneut zu addieren",
            "balance_sheet": {"assets": section("A"), "liabilities_and_equity": section("P")},
            "profit_and_loss": section("G"),
            "checks": {"journal_balanced": True, "balance_sheet_balanced": True,
                       "nonzero_accounts_fully_mapped": True},
            "caveats": [
                "Rekonstruktion, kein aufgestellter oder eingereichter Jahresabschluss und keine steuerliche Gewinnermittlung.",
                "Die gespeicherte Gliederung bestimmt Zuordnung und Vorzeichen der Steuerkonten; Sollsalden können Verbindlichkeiten mindern.",
                "Personenkonten verwenden ihr gespeichertes SammelKonto; negatives Eigenkapital wird nicht automatisch umgegliedert.",
                "Positionssummen enthalten Unterpositionen und direkt zugeordnete Konten: Über- und untergeordnete Summen nicht addieren.",
                "Auch der Vorjahresvergleich verwendet die derzeit gespeicherte Gliederung; eine historische Gliederungsversion ist nicht verfügbar.",
            ],
        }
