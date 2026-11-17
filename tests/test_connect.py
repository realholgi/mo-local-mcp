import base64
from http.client import HTTPConnection
import json
import sqlite3
import threading
import unittest

from mo_local_mcp.connect import ConnectAdapter, ConnectReader, create_http_server


class SyntheticDatabase:
    """Nur synthetische In-Memory-Daten; dieselbe begrenzte Abfrageform wie OfficeDatabase."""

    def __init__(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.executescript("""
            CREATE TABLE FIRMA (_rowid INTEGER PRIMARY KEY, Name TEXT, Zusatz TEXT);
            INSERT INTO FIRMA VALUES (101, 'Synthetische Firma A', 'Test');
            INSERT INTO FIRMA VALUES (202, 'Synthetische Firma B', NULL);
        """)

    def query(self, sql, parameters=(), limit=100):
        cursor = self.connection.execute(sql, parameters)
        rows = cursor.fetchmany(limit + 1)
        return {"columns": [column[0] for column in cursor.description],
                "rows": rows[:limit], "truncated": len(rows) > limit}

    def close(self):
        self.connection.close()


class ConnectHTTPTests(unittest.TestCase):
    def setUp(self):
        self.database = SyntheticDatabase()
        self.server = create_http_server(self.database, "synthetisch", "testpasswort", port=0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.cleanup)
        self.authorization = "Basic " + base64.b64encode(b"synthetisch:testpasswort").decode()

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.database.close()

    def request(self, payload, headers=None, path="/monkeyOfficeConnectJSON", method="POST"):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, json.dumps(payload), headers={
                "Content-Type": "application/json", "Authorization": self.authorization,
                **(headers or {})})
            response = connection.getresponse()
            body = response.read()
            return response.status, dict(response.getheaders()), json.loads(body)
        finally:
            connection.close()

    def test_company_response_can_be_extracted_by_existing_python_client(self):
        code, headers, data = self.request({"firmaList": ""})
        self.assertEqual(code, 200)
        returned = data["firmaListResponse"]["ReturnData"]
        self.assertEqual(returned["ReturnStatus"]["Statuscode"], 0)
        companies = returned["FirmaListItem"]
        selected = next(item for item in companies if item["Bezeichnung"] == "Synthetische Firma B")
        self.assertEqual(selected["Firma_ID"], "202")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_no_auth_or_wrong_auth_cannot_read_companies(self):
        for value in ("", "Basic ungültig", "Bearer synthetisch", "Basic " + base64.b64encode(b"synthetisch:falsch").decode()):
            with self.subTest(value=value):
                code, headers, data = self.request({"firmaList": ""}, {"Authorization": value})
                self.assertEqual(code, 401)
                self.assertIn("WWW-Authenticate", headers)
                self.assertNotIn("firmaListResponse", data)

    def test_company_is_explicit_and_unknown_company_is_rejected(self):
        for identity in (None, "999", "101 OR 1=1", "-1"):
            with self.subTest(identity=identity):
                code, _, result = self.request({"firmaGet": ""}, {} if identity is None else {"mbl-ident": identity})
                self.assertEqual(code, 200)
                returned = result["firmaGetResponse"]["ReturnData"]
                self.assertEqual(returned["ReturnStatus"]["Statuscode"], 4)
                self.assertNotIn("FirmaItem", returned)

    def test_write_requests_are_denied_without_database_changes(self):
        before = self.database.connection.total_changes
        for method in ("buchungAdd", "buchungAddAttachment", "adresseDelete", "verkaufbelegWeiterleitung"):
            code, _, result = self.request({method: {}}, {"mbl-ident": "101"})
            self.assertEqual(code, 200)
            returned = result[method + "Response"]["ReturnData"]
            self.assertEqual(returned["ReturnStatus"]["Statuscode"], 2)
            self.assertNotIn("Insert_ID", returned["ReturnStatus"])
        self.assertEqual(self.database.connection.total_changes, before)

    def test_invalid_call_shapes_and_browser_requests_are_rejected(self):
        for payload in ({}, {"firmaList": "", "firmaGet": ""}, [], None):
            with self.subTest(payload=payload):
                self.assertEqual(self.request(payload)[0], 400)
        self.assertEqual(self.request({"firmaList": ""}, {"Origin": "https://example.invalid"})[0], 403)
        self.assertEqual(self.request({"firmaList": ""}, path="/anderer-pfad")[0], 404)

    def test_unknown_methods_and_parameters_return_errors_not_empty_success(self):
        _, _, data = self.request({"unbekanntList": ""})
        self.assertEqual(data["unbekanntListResponse"]["ReturnData"]["ReturnStatus"]["Statuscode"], 3)
        _, _, data = self.request({"firmaList": {"unbekannt": True}})
        self.assertEqual(data["firmaListResponse"]["ReturnData"]["ReturnStatus"]["Statuscode"], 4)

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("POST", "/monkeyOfficeConnectJSON",
                               '{"firmaList":"", "firmaList":{}}', headers={
                                   "Content-Type": "application/json", "Authorization": self.authorization})
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
        finally:
            connection.close()


class ConnectReaderTests(unittest.TestCase):
    def test_oversized_result_is_not_returned_as_complete(self):
        database = SyntheticDatabase()
        self.addCleanup(database.close)
        reader = ConnectReader(database)
        with self.assertRaisesRegex(ValueError, "Abfragegrenze"):
            reader.rows("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<501) SELECT i FROM n")

    def test_date_range_is_validated_and_search_is_bound(self):
        reader = ConnectReader(None)
        for filters in ({"DatumVon": "2028-02-30"}, {"DatumVon": "20280101"},
                        {"DatumVon": "2028-02-01", "DatumBis": "2028-01-01"}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                reader.dates(filters, [], [])
        clauses, bindings = [], []
        reader.search("%' OR 1=1--", ["Text"], clauses, bindings)
        self.assertNotIn("%'", clauses[0])
        self.assertEqual(bindings, ["%' OR 1=1--"])

    def test_database_errors_do_not_leak_sql_or_source_details(self):
        class BrokenDatabase:
            def query(self, *args, **kwargs):
                raise RuntimeError("vertraulicher Datenbankpfad und SQL")
        result = ConnectAdapter(BrokenDatabase()).call({"firmaList": ""})
        status = result["firmaListResponse"]["ReturnData"]["ReturnStatus"]
        self.assertEqual(status["Statuscode"], 1)
        self.assertNotIn("vertraulich", json.dumps(result))
