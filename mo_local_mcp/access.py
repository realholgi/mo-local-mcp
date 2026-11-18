"""Startseitige Leserechte für genau einen lokalen MCP-Prozess."""

from .business import _integer
from .errors import RechteFehler


# Dieser Modus bietet nur Metadaten und definierte Auswertungen an, keine Detailköpfe.
AGGREGATE_TOOLS = frozenset({
    "datenbankinformationen", "tabellen_auflisten", "tabelle_beschreiben",
    "fachschema_anzeigen", "firmen_auflisten", "geschaeftsjahre_auflisten",
    "datenstand_anzeigen", "datenqualitaet_pruefen", "kostenstellen_auswerten",
    "konten_monatlich_anzeigen", "guv_monatlich_anzeigen",
    "summen_und_salden_anzeigen", "bilanz_und_guv_anzeigen",
})


class ReadAccess:
    def __init__(self, company_ids=None, allow_sql=False, allow_master_data=True):
        if not isinstance(allow_sql, bool) or not isinstance(allow_master_data, bool):
            raise ValueError("Leserechte müssen Wahrheitswerte sein")
        if company_ids is not None:
            company_ids = frozenset(company_ids)
            for company_id in company_ids:
                _integer(company_id, "firma_id")
        self.company_ids = company_ids
        self.allow_master_data = allow_master_data
        # Freies SQL kann weder Zeilen- noch Stammdatenrechte zuverlässig erzwingen.
        self.allow_sql = allow_sql and company_ids is None and allow_master_data

    def tool_allowed(self, name):
        if name == "sql_abfragen":
            return self.allow_sql
        return self.allow_master_data or name in AGGREGATE_TOOLS

    def require_company(self, company_id):
        _integer(company_id, "firma_id")
        if self.company_ids is not None and company_id not in self.company_ids:
            raise RechteFehler("Firma ist für diesen MCP-Prozess nicht freigegeben")

    def companies(self, reader, limit, offset):
        columns = "_rowid,Name,Zusatz,Ort" if self.allow_master_data else "_rowid"
        clause, bindings = "", []
        if self.company_ids is not None:
            bindings = sorted(self.company_ids)
            clause = " WHERE _rowid IN (" + ",".join("?" for _ in bindings) + ")" if bindings else " WHERE 0"
        return reader._page("SELECT " + columns + " FROM FIRMA" + clause + " ORDER BY _rowid", bindings, limit, offset)

    def describe(self):
        return {
            "firma_ids": sorted(self.company_ids) if self.company_ids is not None else None,
            "alle_firmen": self.company_ids is None,
            "sql_erlaubt": self.allow_sql,
            "sensible_stammdaten_erlaubt": self.allow_master_data,
            "grundlage": "Startoptionen dieses lokalen MCP-Prozesses; keine Änderung an Datenbankrechten.",
            "grenzen": (
                "Ohne sensible Stammdaten bleiben nur Metadaten und definierte Auswertungen verfügbar. "
                "Konten-, Gliederungs- und Kostenstellenbezeichnungen in Auswertungen werden nicht anonymisiert."
            ),
        }
