from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.decrepit.ciphers.modes import OFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from mo_local_mcp.business import BusinessReader
from mo_local_mcp.database import OfficeDatabase


def records(result):
    return [dict(zip(result["columns"], row)) for row in result["rows"]]


class BusinessTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        path, key_path = root / "office.db", root / "test.key"
        key = b"domain-test-key!"
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA page_size=1024")
        connection.executescript("""
            CREATE TABLE FIRMA (_rowid INTEGER PRIMARY KEY, Name, Zusatz, Ort);
            INSERT INTO FIRMA VALUES (1,'Musterfirma Eins','',''), (2,'Musterfirma Zwei','','');
            CREATE TABLE ADRESSE (_rowid INTEGER PRIMARY KEY, Firma_id, KZ_AdressNr, KZ_Matchcode, KZ_Kategorie,
                RA_Firma1, RA_Vorname, RA_Nachname, RA_Ort, RA_Email, KF_Status, LF_Status);
            INSERT INTO ADRESSE VALUES
                (10,1,'A10','Beide','','Beide Rollen','','','','',1,1),
                (11,1,'A11','Inaktiv','','Inaktiver Kunde','','','','',2,0),
                (12,1,'A12','Gesperrt','','Gesperrter Kunde','','','','',3,0),
                (13,1,'A13','Keine','','Keine Rolle','','','','',0,0),
                (14,1,'A14','Wörtlich%','','Wörtlich%','','','','',1,0),
                (15,2,'A15','Geheim','','Andere Firma','','','','',1,0);
            CREATE TABLE AUFTRAG (_rowid INTEGER PRIMARY KEY, Firma_id, Art, Entwurf, AuftragsNr, Datum,
                Adress_id, Posten_id, Betreff, Waehrung, GesamtNettoFW, GesamtSteuerFW, GesamtBruttoFW,
                GesamtNettoSW, GesamtBruttoSW, BestellNr);
            INSERT INTO AUFTRAG VALUES
                (100,1,4,0,'RG1','2026-01-01',10,1,'Rechnung','EUR',100,19,119,100,119,''),
                (101,1,4,1,'ENTWURF','2026-01-02',10,0,'Entwurf','EUR',200,38,238,200,238,''),
                (102,1,8,0,'ST1','2026-01-03',10,2,'Storno','EUR',-100,-19,-119,-100,-119,''),
                (103,2,4,0,'GEHEIM','2026-01-01',15,3,'Andere Firma','EUR',1,0,1,1,1,''),
                (104,1,99,0,'NEU','2026-01-04',10,0,'Unbekannte Art','EUR',1,0,1,1,1,'');
            CREATE TABLE AUFTRAGSPOSITION (_rowid INTEGER PRIMARY KEY, Firma_id, Auftrag_id, Nummer, Art,
                Bezeichnung, EKonto);
            INSERT INTO AUFTRAGSPOSITION VALUES
                (5,1,100,2,3,'Text',0), (6,1,100,1,1,'Produkt',8400),
                (7,2,100,3,1,'Position anderer Firma',8400);
            CREATE TABLE BUCHUNG (_rowid INTEGER PRIMARY KEY, Firma_id, Datum, BelegNr, Text,
                KontoSoll, KontoHaben, Waehrung, Summe, SummeFW, Status, Referenz, Bemerkung);
            INSERT INTO BUCHUNG VALUES
                (1,1,'2026-01-01','B1','Aufgeteilte Buchung',0,0,'EUR',100,100,3,'',''),
                (2,1,'2026-01-02','B2','Nur Buchungskopf',1234,0,'EUR',50,50,1,'',''),
                (3,2,'2026-01-01','B3','Andere Firma',0,0,'EUR',99,99,1,'','');
            CREATE TABLE JOURNAL (_rowid INTEGER PRIMARY KEY, Firma_id, Buchung_id, Konto,
                BetragSoll, BetragHaben, BetragSollFW, BetragHabenFW);
            INSERT INTO JOURNAL VALUES
                (1,1,1,1234,100,0,100,0), (2,1,1,1234,0,100,0,100),
                (3,2,2,1234,50,0,50,0), (4,2,3,1234,99,0,99,0);
            CREATE TABLE POSTEN (_rowid INTEGER PRIMARY KEY, Firma_id, Art, Adress_id, ReNr, Datum,
                PKonto, BuText, Waehrung, GesamtBruttoFW, BezahltFW, MinderungFW, OffenFW,
                GesamtBruttoSW, BezahltSW, MinderungSW, OffenSW, Entwurf);
            INSERT INTO POSTEN VALUES
                (1,1,0,10,'R1','2026-01-01',10000,'Rechnung','EUR',119,19,0,100,119,19,0,100,NULL),
                (2,1,1,10,'C1','2026-01-02',10000,'Gutschrift','EUR',-50,0,0,-50,-50,0,0,-50,0),
                (3,2,0,15,'R2','2026-01-01',10000,'Andere Firma','EUR',99,0,0,99,99,0,0,99,0),
                (4,1,0,10,'BEZAHLT','2026-01-01',10000,'Ausgeglichen','EUR',10,10,0,0,10,10,0,0,0),
                (5,1,2,10,'P1','2026-01-03',70000,'Verbindlichkeit','USD',40,0,0,40,38,0,0,38,0),
                (6,1,0,10,'ENTWURF','2026-01-01',10000,'Entwurf','EUR',90,0,0,90,90,0,0,90,1);
            CREATE TABLE POSTENPOSITION (_rowid INTEGER PRIMARY KEY, Firma_id, Posten_id, Position, BuText, EKonto);
            CREATE TABLE WAEHRUNG (_rowid INTEGER PRIMARY KEY, Firma_id, Name, ISOCode, Kurs, Zeichen, Faktor);
        """)
        connection.executescript("""
            ALTER TABLE AUFTRAGSPOSITION ADD COLUMN EinzelPreisNettoFW REAL;
            ALTER TABLE AUFTRAGSPOSITION ADD COLUMN GesamtPreisNettoFW REAL;
            ALTER TABLE AUFTRAGSPOSITION ADD COLUMN Menge REAL;
            ALTER TABLE AUFTRAGSPOSITION ADD COLUMN Rabatt REAL;
            UPDATE AUFTRAGSPOSITION SET EinzelPreisNettoFW=123.45, GesamtPreisNettoFW=-1,
                Menge=2.5, Rabatt=10 WHERE _rowid=6;
            UPDATE BUCHUNG SET Summe=765432.0, SummeFW=765432.0 WHERE _rowid=1;
        """)
        connection.executescript("""
            CREATE TABLE KONTO (_rowid INTEGER PRIMARY KEY,Firma_id,Nummer,Bezeichnung,Typ,
                Steuertyp,Bemerkung,Buchungssperre,DATEVKonto,DATEVAutomatik,Kennzeichen,
                Waehrung,UStIDNummer,ZMKonto,KoStPflicht);
            INSERT INTO KONTO VALUES
                (1,1,10,'Lizenz','1100140',4,'',0,0,0,'','EUR','',0,0),
                (2,1,1200,'Bank','1110110',0,'',0,1200,0,'','EUR','',0,0),
                (3,1,4920,'Telefon','2110160',4,'Vollständige Notizen',0,0,0,'','EUR','',0,1),
                (4,1,8400,'Erlöse #P# USt','2100100',3,'',0,8400,1,'','EUR','',0,0),
                (5,1,10000,'Kunde 100%','4000000',0,'Unbebucht und gesperrt',1,0,0,'','EUR','',0,0),
                (6,2,4920,'Geheime andere Firma','2110160',4,'',0,0,0,'','EUR','',0,0),
                (7,3,10,'Beschädigte Einstellungen','1100140',4,'',0,0,0,'000001000099defekt','EUR','',0,0);
            CREATE TABLE STEUERSATZ (_rowid INTEGER PRIMARY KEY,Firma_id,Name,Prozent,
                Beschreibung,Typ DEFAULT 1,Berechnung DEFAULT 0,KontoSteuer1,KontoSteuer2,KontoSteuerNF,
                UVASteuer1,UVASteuer2,UVABemessung1,UVABemessung2,NASteuerProzent,NASteuerKonto,
                NANettoProzent,NANettoKonto,Datev,Buchungssperre DEFAULT 0,SSS_Steuersatz,OSS DEFAULT 0);
            INSERT INTO STEUERSATZ(Firma_id,Name,Prozent) VALUES (1,'USt19 (§13b)',1900),(2,'USt19 (§13b)',700);
            INSERT INTO STEUERSATZ(Firma_id,Name,Prozent,Beschreibung,Berechnung,Buchungssperre,OSS) VALUES
                (1,'OSS',NULL,'Nicht angegeben 100% wörtlich',0,0,1),
                (1,'Nullsatz',0,'Ausdrückliche Null',0,0,0),
                (1,'Gesperrt19',1900,'Vollständige Warnung',1,1,0);
            ALTER TABLE BUCHUNG ADD COLUMN Wj_id;
            UPDATE BUCHUNG SET Wj_id=10;
            CREATE TABLE WIRTSCHAFTSJAHR (_rowid INTEGER PRIMARY KEY,Firma_id,Bezeichnung,Von,Bis,Waehrung,Gesperrt,
                P01_Gesperrt DEFAULT 0,P02_Gesperrt DEFAULT 0,P03_Gesperrt DEFAULT 0,P04_Gesperrt DEFAULT 0,
                P05_Gesperrt DEFAULT 0,P06_Gesperrt DEFAULT 0,P07_Gesperrt DEFAULT 0,P08_Gesperrt DEFAULT 0,
                P09_Gesperrt DEFAULT 0,P10_Gesperrt DEFAULT 0,P11_Gesperrt DEFAULT 0,P12_Gesperrt DEFAULT 0,
                SaldoVortrag DEFAULT 0,Versteuerung,SSS DEFAULT 0,SSS_Prozentsatz1,SSS_Prozentsatz2);
            INSERT INTO WIRTSCHAFTSJAHR(_rowid,Firma_id,Bezeichnung,Von,Bis,Waehrung,Gesperrt,P01_Gesperrt,Versteuerung) VALUES
                (10,1,'2025/26','2025-07-01','2026-06-30','EUR',1,1,2),
                (11,1,'2026/27','2026-07-01','2027-06-30','EUR',0,0,99),
                (20,2,'Andere Firma','2025-07-01','2026-06-30','EUR',1,0,2);
            CREATE TABLE ZAHLUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datum);
            INSERT INTO ZAHLUNG VALUES (1,1,'2025-07-01'),(2,1,'2026-06-30'),
                (3,2,'2026-01-01'),(4,1,'2025-06-30');
            CREATE TABLE KONTOSTRUKTUR (_rowid INTEGER PRIMARY KEY,Firma_id);
            CREATE TABLE STRUKTURPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Ks_id,ItemId,ParentId,
                Bezeichnung,Ebene,Kontoliste,Struktur,VzWechsel);
            CREATE TABLE ZAHLUNGSPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Zahlung_id,Position,Postenposition_id,
                ZBuText,MBuText,MKonto,BetragZahlFW,BetragZahlSW,BetragMindFW,BetragMindSW,SteuerBuchung_id,BetragValutaAG);
            CREATE TABLE KOSTENSTELLE (_rowid INTEGER PRIMARY KEY,Firma_id,Name,Beschreibung,Bemerkung,Buchungssperre);
            CREATE TABLE ZAHLUNGSBEDINGUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Bezeichnung,Zahlungsart,TageNetto,ZBText,
                TageSkonto,ProzentSkonto,NichtMahnen,FakturaArt,Bankkonto_id,Gesperrt,Standard);
            CREATE TABLE ELSTERMELDUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Verfahren,DatenArt,Jahr,ZeitraumCode,
                DatumVon,DatumBis,Kennzahlen,Berechnungsart,Status,Land,Meldung_id);
            CREATE TABLE ELSTERMELDUNG_NT (_rowid INTEGER PRIMARY KEY,Firma_id,Method,DataType,Process,TaxReport,
                DateFrom,DateTo,CalculationMethod,Report_id);
            CREATE TABLE STEUERERKLAERUNG (_rowid INTEGER PRIMARY KEY,Firma_id,Datenart,DatumVon,DatumBis,Jahr,
                Kennzahlen,Berechnungsart,Verfahren,Meldung_id);
            CREATE TABLE ANLAGE (_rowid INTEGER PRIMARY KEY,Firma_id);
            CREATE TABLE ANLAGENPOSITION (_rowid INTEGER PRIMARY KEY,Firma_id,Anlage_id);
        """)

        def packed(values):
            return f"{len(values):06d}" + "".join(f"{len(value):06d}{value}" for value in values)

        for row_id, versions in (
            (3, [["1999-01-01","VSt7","66","",""], ["2021-01-01","VSt19","","","320"],
                 ["2021-01-01","VSt7","","",""]]),
            (4, [["2021-01-01","USt19 (§13b)","46","","846"]]),
            (2, [["2020-07-01","","98","",""], ["2021-01-01","","-","",""]]),
        ):
            connection.execute("UPDATE KONTO SET Kennzeichen=? WHERE _rowid=?",
                               (packed([packed(version) for version in versions]), row_id))
        connection.commit()
        connection.close()
        plain = path.read_bytes()
        encrypted = bytearray()
        for start in range(0, len(plain), 1024):
            encoder = Cipher(algorithms.AES(key), OFB((start // 1024 + 1).to_bytes(16, "little"))).encryptor()
            encrypted.extend(encoder.update(plain[start:start + 1024]) + encoder.finalize())
        encrypted[16:24] = plain[16:24]
        path.write_bytes(encrypted)
        database = OfficeDatabase(path, key_path)
        self.addCleanup(database.close)
        self.reader = BusinessReader(database)

    def test_fiscal_years_count_company_scoped_records_within_noncalendar_period(self):
        first = self.reader.fiscal_years(1,limit=1)
        period = records(first)[0]
        self.assertEqual((period["booking_count"],period["op_document_count"],period["op_payment_count"]),(2,5,2))
        self.assertEqual(period["Versteuerung_label"],"IST")
        self.assertEqual((period["Gesperrt"],period["P01_Gesperrt"]),(1,1))
        last = self.reader.fiscal_years(1,limit=1,offset=first["next_offset"])
        empty = records(last)[0]
        self.assertEqual((empty["booking_count"],empty["op_document_count"],empty["op_payment_count"]),(0,0,0))
        self.assertEqual(empty["Versteuerung_label"],"Unbekannt")
        self.assertIsNone(last["next_offset"])

    def test_tax_rates_preserve_unset_zero_locked_and_company_scoped_percentages(self):
        rows = {row["Name"]:row for row in records(self.reader.tax_rates(1))}
        self.assertIsNone(rows["OSS"]["percent"])
        self.assertEqual(rows["Nullsatz"]["percent"],"0.00")
        self.assertEqual(rows["USt19 (§13b)"]["percent"],"19.00")
        self.assertEqual(rows["USt19 (§13b)"]["Prozent"],1900)
        self.assertEqual(rows["Gesperrt19"]["Buchungssperre"],1)
        self.assertEqual(rows["Gesperrt19"]["Berechnung_label"],"i.H.")
        self.assertEqual(rows["Nullsatz"]["Berechnung_label"],"v.H.")
        self.assertEqual(records(self.reader.tax_rates(1,search="%"))[0]["Name"],"OSS")
        self.assertEqual(self.reader.tax_rates(1,search="' OR 1=1 --")["rows"],[])
        first = self.reader.tax_rates(1,limit=2)
        last = self.reader.tax_rates(1,limit=2,offset=first["next_offset"])
        self.assertEqual([row["Name"] for row in records(first)+records(last)],["Gesperrt19","Nullsatz","OSS","USt19 (§13b)"])
        self.assertIsNone(last["next_offset"])

    def test_schema_explains_local_units_and_reports_missing_documented_columns(self):
        tables = self.reader.schema()["tables"]
        self.assertEqual(tables["STEUERSATZ"]["percentages"]["stored_units_per_percent"],100)
        self.assertEqual(tables["STEUERSATZ"]["enums"]["Berechnung"],{0:"v.H.",1:"i.H."})
        self.assertEqual(tables["KONTO"]["enums"]["Steuertyp"][4],"VSt")
        self.assertNotIn("api_fields",tables["KONTO"])
        self.assertEqual(tables["WIRTSCHAFTSJAHR"]["missing_documented_columns"],[])
        self.assertEqual(tables["STRUKTURPOSITION"]["enums"]["Struktur"]["B"],"Eingebundenes Jahresergebnis")
        self.assertIn("Steuersatz",tables["JOURNAL"]["missing_documented_columns"])
        self.assertIn("SD_InventarNr",tables["ANLAGE"]["missing_documented_columns"])
        self.assertIn("BuchwertNeu",tables["ANLAGENPOSITION"]["missing_documented_columns"])

    def test_accounts_include_locked_unbooked_and_company_scoped_pagination(self):
        first = self.reader.accounts(1,limit=2)
        second = self.reader.accounts(1,limit=2,offset=first["next_offset"])
        last = self.reader.accounts(1,limit=2,offset=second["next_offset"])
        rows = records(first) + records(second) + records(last)
        self.assertEqual([row["Nummer"] for row in rows],[10,1200,4920,8400,10000])
        self.assertEqual(rows[0]["Nummer_formatiert"],"0010")
        self.assertEqual(rows[-1]["Buchungssperre"],1)
        self.assertIsNone(last["next_offset"])

    def test_accounts_resolve_inherited_tax_defaults_and_unicode_name_rates(self):
        rows = records(self.reader.accounts(1,account_from=4920,account_to=8400))
        self.assertEqual(rows[0]["Steuersatz"],"VSt19")
        self.assertEqual(rows[0]["Steuertyp_label"],"VSt")
        self.assertEqual(rows[0]["UVA_Kennzeichen"],"66")
        self.assertEqual(rows[0]["Steuerzuordnungen"][1]["uva_base"],"")
        self.assertEqual(rows[1]["Bezeichnung"],"Erlöse 19% USt")
        self.assertEqual(rows[1]["Bezeichnung_Vorlage"],"Erlöse #P# USt")
        self.assertEqual(rows[1]["UVA_Kennzeichen"],"46")
        bank = records(self.reader.accounts(1,account_from=1200,account_to=1200))[0]
        self.assertEqual(bank["UVA_Kennzeichen"],"-")
        self.assertEqual(bank["Steuersatz"],"-")

    def test_accounts_search_is_literal_and_includes_notes_and_numbers(self):
        self.assertEqual(records(self.reader.accounts(1,search="%"))[0]["Nummer"],10000)
        self.assertEqual(records(self.reader.accounts(1,search="vollständige NOTIZEN"))[0]["Nummer"],4920)
        self.assertEqual(records(self.reader.accounts(1,search="4920"))[0]["Bezeichnung"],"Telefon")
        self.assertEqual(self.reader.accounts(1,search="' OR 1=1 --")["rows"],[])
        self.assertEqual(self.reader.accounts(1,search="Geheim")["rows"],[])

    def test_accounts_reject_invalid_ranges_and_corrupt_settings(self):
        for arguments in ({"company_id":True},{"company_id":1,"account_from":-1},
                          {"company_id":1,"account_from":10,"account_to":0}):
            with self.assertRaises(ValueError):
                self.reader.accounts(**arguments)
        with self.assertRaisesRegex(ValueError,"Abgeschnittene"):
            self.reader.accounts(3)

    def test_money_units_precision_and_raw_query_contract(self):
        booking = records(self.reader.bookings(1, account=1234))[0]
        self.assertEqual(booking["Summe"], "7654.32")
        self.assertEqual(booking["SummeFW"], "7654.32")
        self.assertEqual(booking["KontoSoll"], 0)
        raw = self.reader.database.query("SELECT Summe FROM BUCHUNG WHERE _rowid=1")
        self.assertEqual(raw["rows"], [[765432.0]])
        detail = self.reader.sales_document(1,100)
        self.assertEqual(records(detail["document"])[0]["GesamtBruttoFW"], "1.19")
        positions = records(detail["positions"])
        self.assertEqual(positions[0]["EinzelPreisNettoFW"], "1.2345")
        self.assertEqual(positions[0]["GesamtPreisNettoFW"], "-0.01")
        self.assertEqual(positions[0]["Menge"], 2.5)
        self.assertEqual(positions[0]["Rabatt"], 10)
        self.assertIsNone(positions[1]["EinzelPreisNettoFW"])
        opened = self.reader.open_items(1)
        self.assertEqual(records(opened)[0]["BezahltFW"], "0.19")
        self.assertEqual(records(opened)[0]["MinderungFW"], "0.00")
        self.assertEqual(opened["money"]["stored_units_per_currency_unit"],100)
        self.assertIn("OffenFW",opened["money"]["columns"])
        self.assertNotIn("Art",opened["money"]["columns"])
        schema = self.reader.schema("BUCHUNG")
        self.assertEqual(schema["amounts"]["stored_units_per_currency_unit"],100)
        self.assertEqual(schema["tables"]["BUCHUNG"]["money_fields"],["Summe","SummeFW"])

    def test_addresses_include_inactive_and_blocked_and_dual_roles(self):
        result = records(self.reader.addresses(1, role="customer"))
        self.assertEqual([r["_rowid"] for r in result], [10,11,12,14])
        self.assertEqual([r["KF_Status_label"] for r in result], ["Aktiv","Inaktiv","Gesperrt","Aktiv"])
        self.assertEqual([r["_rowid"] for r in records(self.reader.addresses(1, role="supplier"))], [10])
        self.assertEqual([r["_rowid"] for r in records(self.reader.addresses(1, role="customer", status="blocked"))], [12])
        self.assertEqual([r["_rowid"] for r in records(self.reader.addresses(1, search="%"))], [14])
        self.assertEqual(self.reader.addresses(1, search="' OR 1=1 --")["rows"], [])

    def test_document_types_drafts_dates_and_pagination(self):
        result = records(self.reader.sales_documents(1, document_type=4))
        self.assertEqual([r["_rowid"] for r in result], [100])
        self.assertEqual(result[0]["Art_label"], "Rechnung")
        self.assertEqual(result[0]["GesamtBruttoFW"], "1.19")
        drafts = records(self.reader.sales_documents(1, document_type=4, include_drafts=True))
        self.assertEqual([r["_rowid"] for r in drafts], [100,101])
        same_day = records(self.reader.sales_documents(1, date_from="2026-01-03", date_to="2026-01-03"))
        self.assertEqual([(r["_rowid"],r["Art_label"]) for r in same_day], [(102,"Storno")])
        first = self.reader.sales_documents(1, limit=2)
        self.assertTrue(first["truncated"])
        rest = self.reader.sales_documents(1, limit=2, offset=first["next_offset"])
        self.assertEqual([r["_rowid"] for r in records(first)+records(rest)], [100,102,104])
        self.assertIsNone(rest["next_offset"])
        self.assertEqual(records(rest)[0]["Art_label"], "Unbekannt")

    def test_document_positions_order_and_company_isolation(self):
        result = self.reader.sales_document(1,100,position_limit=1)
        self.assertEqual(records(result["positions"])[0]["Bezeichnung"], "Produkt")
        next_page = self.reader.sales_document(1,100,position_offset=result["positions"]["next_offset"])
        self.assertEqual([(r["Bezeichnung"],r["Art_label"]) for r in records(next_page["positions"])], [("Text","Textposition")])
        with self.assertRaisesRegex(ValueError,"nicht gefunden"):
            self.reader.sales_document(1,103)

    def test_account_filter_includes_splits_not_cross_company_rows(self):
        result = records(self.reader.bookings(1, account=1234))
        self.assertEqual([r["_rowid"] for r in result], [1])
        self.assertEqual(result[0]["Status"],3)
        self.assertNotIn("Status_label", result[0])

    def test_open_items_keep_negative_credits_and_legacy_null_draft(self):
        result = records(self.reader.open_items(1))
        self.assertEqual([(r["_rowid"],r["OffenFW"]) for r in result], [(1,"1.00"),(2,"-0.50")])
        payable = records(self.reader.open_items(1,side="payable"))
        self.assertEqual([(r["_rowid"],r["OffenFW"],r["OffenSW"]) for r in payable], [(5,"0.40","0.38")])
        self.assertEqual(self.reader.open_items(1,address_id=15)["rows"],[])

    def test_metadata_states_mapping_and_id_limitations(self):
        schema = self.reader.schema("auftrag")
        self.assertEqual(schema["reference"]["version"],"23.2.0 / 07.07.26")
        self.assertIn("abgeleitet",schema["mapping_basis"])
        self.assertIn("nicht zugesichert",schema["ids"])
        self.assertEqual(schema["tables"]["AUFTRAG"]["missing_mapped_columns"],[])
        self.assertEqual(schema["tables"]["AUFTRAG"]["enums"]["Art"][4],"Rechnung")
        with self.assertRaises(ValueError):
            self.reader.schema("unknown")

    def test_invalid_company_date_and_enum_filters(self):
        for company in [0,-1,True,"1"]:
            with self.subTest(company=company),self.assertRaises(ValueError):
                self.reader.sales_documents(company)
        for args in [{"date_from":"2026-02-30"},{"date_from":"20260101"},
                     {"date_from":"2026-02-01","date_to":"2026-01-01"},{"document_type":99},{"offset":-1}]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                self.reader.sales_documents(1,**args)
        with self.assertRaises(ValueError):
            self.reader.addresses(1,status="active")
        with self.assertRaises(ValueError):
            self.reader.open_items(1,side="invalid")


if __name__ == "__main__":
    unittest.main()
