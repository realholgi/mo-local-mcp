"""Lesender Connect-HTTP-Adapter für einen festen lokalen MonKey-Datenstand."""

import base64
import binascii
from datetime import date
from decimal import Decimal
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys

from .database import OfficeDatabase
from .kommandozeile import DeutscherArgumentParser
from . import connect_bookings, connect_documents, connect_masters


MAX_REQUEST = 100_000
MAX_RESPONSE = 1_000_000
DEFAULT_KEY = Path.home() / "Library/Application Support/mo-local-mcp/database.key"
MODULES = (connect_bookings, connect_documents, connect_masters)


class ConnectReader:
    """Begrenzte Abfragen und gemeinsame Prüfungen für die Connect-Fachmodule."""

    def __init__(self, database):
        self.database = database

    def rows(self, sql, parameters=()):
        result = self.database.query(sql, parameters, limit=500)
        if result["truncated"]:
            raise ValueError("Ergebnis überschreitet die Abfragegrenze; Filter enger setzen")
        return [dict(zip(result["columns"], row)) for row in result["rows"]]

    def one(self, sql, parameters=()):
        rows = self.rows(sql, parameters)
        if len(rows) != 1:
            raise ValueError("Datensatz fehlt oder ist nicht eindeutig")
        return rows[0]

    def columns(self, table):
        return frozenset(row["name"] for row in self.rows(
            "SELECT name FROM pragma_table_xinfo(?)", [table]))

    def company(self, firma_id):
        if isinstance(firma_id, bool) or not isinstance(firma_id, (str, int)):
            raise ValueError("Firma über mbl-ident ausdrücklich auswählen")
        value = str(firma_id)
        if not value.isascii() or not value.isdecimal() or int(value) <= 0:
            raise ValueError("mbl-ident muss eine lokale Firma_ID aus firmaList enthalten")
        firma_id = int(value)
        self.one("SELECT _rowid FROM FIRMA WHERE _rowid = ?", [firma_id])
        return firma_id

    @staticmethod
    def require(params, allowed):
        if not isinstance(params, dict):
            raise ValueError("Ein Parameterobjekt wird erwartet")
        unknown = params.keys() - set(allowed)
        if unknown:
            raise ValueError("Unbekannte Parameter: " + ", ".join(sorted(unknown)))

    def filter(self, params, key, allowed):
        self.require(params, {key})
        value = params.get(key, {})
        self.require(value, allowed)
        return value

    @staticmethod
    def dates(filters, clauses, bindings, column="Datum"):
        parsed = {}
        for key, operator in (("DatumVon", ">="), ("DatumBis", "<=")):
            value = filters.get(key)
            if value is None or value == "":
                continue
            if not isinstance(value, str):
                raise ValueError(f"{key} muss ein ISO-Datum YYYY-MM-DD sein")
            try:
                parsed[key] = date.fromisoformat(value)
            except ValueError:
                raise ValueError(f"{key} muss ein ISO-Datum YYYY-MM-DD sein") from None
            if parsed[key].isoformat() != value:
                raise ValueError(f"{key} muss ein ISO-Datum YYYY-MM-DD sein")
            clauses.append(f"{column} {operator} ?")
            bindings.append(value)
        if parsed.get("DatumVon", date.min) > parsed.get("DatumBis", date.max):
            raise ValueError("DatumVon darf nicht nach DatumBis liegen")

    @staticmethod
    def search(value, columns, clauses, bindings):
        if value is None or value == "":
            return
        if not isinstance(value, str):
            raise ValueError("Suchtext muss eine Zeichenkette sein")
        clauses.append("(" + " OR ".join(
            f"instr(lower(COALESCE({column}, '')), lower(?)) > 0"
            for column in columns) + ")")
        bindings.extend([value] * len(columns))

    @staticmethod
    def money(value):
        if value is None:
            return None
        return format(Decimal(str(value)) / 100, "f")


def status(code, message):
    """Dokumentiertes Statusformat plus Meldung für den Uhlhorn-Client."""
    return {"Statuscode": code, "StatustextItem": [{"Statustext": message}], "Meldung": message}


class ConnectAdapter:
    def __init__(self, database):
        self.reader = ConnectReader(database)

    def call(self, payload, firma_id=None):
        if not isinstance(payload, dict) or len(payload) != 1:
            raise ValueError("Genau einen Connect-Aufruf als JSON-Objekt senden")
        method, params = next(iter(payload.items()))
        module = next((module for module in MODULES if method in module.METHODS), None)
        if module is None:
            writing = any(word in method for word in (
                "Add", "Modify", "Delete", "Create", "Weiterleitung", "Preview", "Print"))
            code = 2 if writing else 3
            message = ("Schreibende oder ausführende Aufrufe sind gesperrt" if writing
                       else "Funktion unbekannt; nur dokumentierte lokale Leseaufrufe verfügbar")
            data = {"ReturnStatus": status(code, message)}
        else:
            try:
                if params == "":
                    params = {}
                if not isinstance(params, dict):
                    raise ValueError("Ein Parameterobjekt oder eine leere Zeichenkette wird erwartet")
                company = None if method == "firmaList" else self.reader.company(firma_id)
                data = module.handle(self.reader, method, params, company)
                data["ReturnStatus"] = status(0, "OK")
            except ValueError as error:
                data = {"ReturnStatus": status(4, str(error))}
            except Exception:
                # Keine SQL-Texte, Datenbankinhalte oder Geheimnisse über Fehler offenlegen.
                data = {"ReturnStatus": status(1, "Abfrage des festen Datenbankstands fehlgeschlagen")}
        result = {method + "Response": {"ReturnData": data}}
        try:
            encoded = json.dumps(result, ensure_ascii=True, allow_nan=False)
        except (ValueError, TypeError):
            return {method + "Response": {"ReturnData": {"ReturnStatus": status(
                1, "Abfrage enthält nicht als JSON darstellbare Werte")}}}
        if len(encoded) > MAX_RESPONSE:
            result = {method + "Response": {"ReturnData": {"ReturnStatus": status(
                1, "Antwort überschreitet die Ausgabegrenze; Filter enger setzen")}}}
        return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Doppelte JSON-Schlüssel sind nicht zulässig")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nichtendliche Zahlen sind nicht zulässig")


def create_http_server(database, username, password, port=8084):
    """Nur Loopback; Basic Auth und keine Browser-/CORS-Freigabe."""
    if not username or not password or ":" in username:
        raise ValueError("Benutzername ohne Doppelpunkt und nichtleeres Passwort erforderlich")
    expected = (username + ":" + password).encode("utf-8")
    adapter = ConnectAdapter(database)

    class Handler(BaseHTTPRequestHandler):
        server_version = "mo-local-connect"
        sys_version = ""
        timeout = 5

        def log_message(self, format, *args):
            # Keine Nutzdaten, Zugangsdaten oder URLs protokollieren.
            pass

        def reply(self, code, data, authenticate=False):
            body = json.dumps(data, ensure_ascii=True, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if authenticate:
                self.send_header("WWW-Authenticate", 'Basic realm="Lokaler MonKey-Datenstand", charset="UTF-8"')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/monkeyOfficeConnectJSON":
                self.reply(404, {"fehler": "Unbekannter Endpunkt"})
                return
            if self.headers.get("Origin") is not None:
                self.reply(403, {"fehler": "Browserzugriffe sind nicht freigegeben"})
                return
            authorization = self.headers.get("Authorization", "")
            try:
                scheme, token = authorization.split(" ", 1)
                supplied = base64.b64decode(token, validate=True) if scheme.lower() == "basic" else b""
            except (ValueError, binascii.Error):
                supplied = b""
            if not hmac.compare_digest(supplied, expected):
                self.reply(401, {"fehler": "Anmeldung erforderlich"}, authenticate=True)
                return
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
                self.reply(400, {"fehler": "Genau eine Content-Length erforderlich"})
                return
            try:
                length = int(lengths[0])
            except ValueError:
                length = -1
            if not 0 < length <= MAX_REQUEST:
                self.reply(413, {"fehler": "Ungültige oder zu große Anfrage"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"fehler": "Content-Type application/json erforderlich"})
                return
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("Unvollständige Anfrage")
                payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                     parse_constant=_reject_constant)
                identities = self.headers.get_all("mbl-ident", [])
                if len(identities) > 1:
                    raise ValueError("Genau einen mbl-ident-Header senden")
                result = adapter.call(payload, identities[0] if identities else None)
            except (ValueError, UnicodeError, RecursionError):
                self.reply(400, {"fehler": "Ungültige JSON-Anfrage oder Firmenauswahl"})
                return
            self.reply(200, result)

    return HTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = DeutscherArgumentParser(description=__doc__)
    parser.add_argument("--datenbank", type=Path, required=True, metavar="DATEI",
                        help="Geschlossener, konsistenter verschlüsselter Datenbankstand")
    parser.add_argument("--schluesseldatei", type=Path, default=DEFAULT_KEY, metavar="DATEI",
                        help="Private Datei mit dem Datenbankschlüssel")
    parser.add_argument("--benutzer", default=os.environ.get("MO_CONNECT_BENUTZER"),
                        help="HTTP-Benutzername; alternativ MO_CONNECT_BENUTZER")
    parser.add_argument("--passwortdatei", type=Path, metavar="DATEI",
                        help="Private UTF-8-Passwortdatei; alternativ MO_CONNECT_PASSWORT")
    parser.add_argument("--port", type=int, default=8084, help="Lokaler HTTP-Port (Standard: 8084)")
    args = parser.parse_args()
    database = None
    server = None
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("Port muss zwischen 1 und 65535 liegen")
        if args.passwortdatei:
            if args.passwortdatei.stat().st_mode & 0o077:
                raise ValueError("Passwortdatei muss privat sein (Dateirechte 600)")
            password = args.passwortdatei.read_text(encoding="utf-8").removesuffix("\n").removesuffix("\r")
        else:
            password = os.environ.get("MO_CONNECT_PASSWORT", "")
        if not args.benutzer or not password:
            raise ValueError("HTTP-Benutzer und Passwort ausdrücklich konfigurieren")
        database = OfficeDatabase(args.datenbank, args.schluesseldatei)
        server = create_http_server(database, args.benutzer, password, args.port)
        print(f"Lesender Connect-Adapter: http://127.0.0.1:{args.port}/monkeyOfficeConnectJSON", file=sys.stderr)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"Connect-Adapter kann nicht ausgeführt werden: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if server is not None:
            server.server_close()
        if database is not None:
            database.close()


if __name__ == "__main__":
    main()
