"""Vorhandene Zeiträume und gespeicherte Buchungszeitpunkte eines festen Datenstands."""

from datetime import datetime, timezone

from .business import _integer
from .errors import ParameterFehler
from .statements import StatementReader


AREAS = (
    ("buchungen", "BUCHUNG"), ("verkauf", "AUFTRAG"),
    ("einkauf", "BESTELLUNG"), ("posten", "POSTEN"), ("zahlungen", "ZAHLUNG"),
)


def snapshot_overview(reader, company_id):
    _integer(company_id, "firma_id")
    if not reader.database.query("SELECT _rowid FROM FIRMA WHERE _rowid=?", [company_id], 1)["rows"]:
        raise ParameterFehler("Firma nicht gefunden")
    source = StatementReader(reader.database)
    ranges = []
    for area, table in AREAS:
        row = source._rows(
            f"SELECT count(*) AS anzahl, min(Datum) AS erstes_belegdatum, "
            f"max(Datum) AS letztes_belegdatum, count(*)-count(Datum) AS ohne_belegdatum "
            f"FROM {table} WHERE Firma_id=?", [company_id],
        )[0]
        ranges.append({"bereich": area, **row})
    booking = source._rows(
        "SELECT max(EingabeDatum) AS letzte_gespeicherte_erfassung, "
        "max(DatumVerbucht) AS letztes_gespeichertes_verbuchungsdatum "
        "FROM BUCHUNG WHERE Firma_id=?", [company_id],
    )[0]
    years = source._rows(
        "SELECT _rowid,Bezeichnung,Von,Bis,Waehrung,Gesperrt FROM WIRTSCHAFTSJAHR "
        "WHERE Firma_id=? ORDER BY Von,_rowid", [company_id],
    )
    stat = reader.database.path.stat()
    return {
        "firma_id": company_id, "nur_lesend": True, "fester_datenstand": True,
        "quelle": str(reader.database.path), "dateigroesse_bytes": stat.st_size,
        "datei_geaendert_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "zeitraeume": ranges, "geschaeftsjahre": years, **booking,
        "grenzen": [
            "Die Dateiänderungszeit ist kein bestätigter Export-, Sicherungs- oder Synchronisationszeitpunkt.",
            "Belegdatum, gespeicherte Erfassung und gespeichertes Verbuchungsdatum haben unterschiedliche Bedeutungen.",
            "Die jüngste Buchung und vorhandene Geschäftsjahre belegen keine vollständige oder aktuelle Buchführung.",
            "Zähler enthalten gespeicherte Entwürfe, Stornos und ausgeglichene Posten. Keine Live-Verbindung.",
        ],
    }
