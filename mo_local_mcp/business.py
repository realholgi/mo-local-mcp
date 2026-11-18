"""Connect-dokumentierte Fachbegriffe im beobachteten lokalen Datenbankschema.

Dies sind Abfragen eines Datenbankstands, keine Connect-Aufrufe oder -Nachbildung.
"""

from datetime import date
from decimal import Decimal

from .errors import Abfragegrenze, DatenFehler, ParameterFehler
from .master_catalog import MASTERS_CATALOG
from .tax_catalog import TAX_CATALOG
from .asset_catalog import ASSET_CATALOG, ASSET_MONEY_FIELDS
from .commerce_catalog import COMMERCE_CATALOG, COMMERCE_MONEY_FIELDS


REFERENCE = {
    "version": "23.2.0 / 07.07.26",
    "url": "https://www.monkey-office.de/download/current/mac/MonKey_Office_Connect.dmg",
    "file": "Entwicklerdokumente/Monkey Office Connect JSON-API Hilfe.html",
    "sha256": "de3836cb7a582ac84118b121088496f663829de9b2c3f030a57a20fe8d706406",
}
SALES_TYPES = {1: "Angebot", 2: "Auftragsbestätigung", 3: "Lieferschein", 4: "Rechnung",
               5: "Abschlagsrechnung", 6: "Korrekturrechnung", 7: "Proforma-Rechnung",
               8: "Storno", 9: "Kostenvoranschlag"}
POSITION_TYPES = {1: "Stammartikel", 2: "Manueller Artikel", 3: "Textposition", 4: "Zwischensumme",
                  5: "Seitenumbruch", 6: "Kommentar", 7: "Alternativer Stammartikel",
                  8: "Alternativer manueller Artikel"}
ADDRESS_STATUSES = {0: "Kein Kunde/Lieferant", 1: "Aktiv", 2: "Inaktiv", 3: "Gesperrt"}
OPEN_ITEM_TYPES = {0: "DebitorRechnung", 1: "DebitorGutschrift", 2: "KreditorRechnung", 3: "KreditorGutschrift"}
ACCOUNT_TAX_TYPES = {0: "-", 3: "USt", 4: "VSt", 5: "USt/VSt"}
FISCAL_TAX_MODES = {2: "IST"}
TAX_RATE_TYPES = {1: "USt", 2: "VSt"}
TAX_CALCULATIONS = {0: "v.H.", 1: "i.H."}

MONEY_CONVENTION = {
    "stored_units_per_currency_unit": 100,
    "business_output": "Dezimalzeichenketten in Währungseinheiten; gespeicherter Betrag geteilt durch 100",
    "raw_query_output": "Unveränderte Speicherwerte; Geldbeträge durch 100 teilen",
    "basis": "Vom Datenbankinhaber bestätigte Speicherung von Geldbeträgen in Hundertsteln der Währungseinheit",
    "caution": "FW/SW und Währungen getrennt halten; nur Einheitenskalierung, keine Währungsumrechnung",
}
MONEY_FIELDS = {
    "AUFTRAG": {
        base + suffix
        for base in ("PosGesamtNetto", "GesamtRabatt", "GesamtNetto", "GesamtSteuer", "GesamtBrutto")
        for suffix in ("FW", "SW")
    },
    "AUFTRAGSPOSITION": {
        base + suffix
        for base in ("EinzelPreisNetto", "EinzelPreisBrutto", "GesamtPreisNetto", "GesamtPreisBrutto")
        for suffix in ("FW", "SW")
    } | {"PreisProStkEK", "PreisProStkVK", "PreisEKNetto", "PreisEKBrutto"},
    "BUCHUNG": {"Summe", "SummeFW"},
    "POSTEN": {
        base + suffix
        for base in ("GesamtBrutto", "GesamtNetto", "GesamtSteuer", "Bezahlt", "Minderung", "Offen")
        for suffix in ("FW", "SW")
    },
    "POSTENPOSITION": {
        base + suffix
        for base in ("BetragBrutto", "BetragNetto", "BetragSteuer")
        for suffix in ("FW", "SW")
    },
    "JOURNAL": {"BetragSoll", "BetragHaben", "BetragSollFW", "BetragHabenFW", "Betrag", "BetragFW",
                "IV_BetragSoll", "IV_BetragHaben", "BetragBemSoll", "BetragBemHaben"},
    "ZAHLUNG": {base + suffix for base in ("GesamtZahl", "GesamtMind") for suffix in ("FW", "SW")} | {"GesamtValutaAG"},
    "ZAHLUNGSPOSITION": {base + suffix for base in ("BetragZahl", "BetragMind") for suffix in ("FW", "SW")} | {"BetragValutaAG"},
}
MONEY_FIELDS.update(ASSET_MONEY_FIELDS)
MONEY_FIELDS.update(COMMERCE_MONEY_FIELDS)

PAYMENT_ALLOCATION_FROM = (
    "FROM ZAHLUNGSPOSITION zp "
    "JOIN ZAHLUNG z ON z._rowid=zp.Zahlung_id AND z.Firma_id=zp.Firma_id "
    "JOIN POSTENPOSITION pp ON pp._rowid=zp.Postenposition_id AND pp.Firma_id=zp.Firma_id "
    "JOIN POSTEN p ON p._rowid=pp.Posten_id AND p.Firma_id=pp.Firma_id "
)

CATALOG = {
    "FIRMA": {
        "meaning": "Firma/Mandant; kein Kunde des Adressbuchs",
        "api_structures": ["FirmaListItem", "FirmaItem"],
        "api_fields": {"Firma_ID": "_rowid", "Bezeichnung": "Name", "Zusatz": "Zusatz"},
        "tools": ["list_companies", "get_company", "list_fiscal_years"],
        "notes": ["Das Firmendetail liefert alle Originalspalten des Firmenstamms. Geschäftsjahre stehen getrennt in WIRTSCHAFTSJAHR."],
    },
    "KONTO": {
        "meaning": "Firmenbezogener Kontenstamm einschließlich unbebuchter, gesperrter und Personenkonten",
        "mapping_basis": "Datenbankstand und Kontenplan-PDF; keine verifizierte Connect-Zuordnung",
        "tools": ["list_accounts", "get_account_statement", "get_financial_statements", "get_trial_balance"],
        "fields": {"_rowid": "Lokale ID", "Firma_id": "Zugehörige Firma", "Nummer": "Kontonummer",
                   "Bezeichnung": "Namensvorlage; #P# verwendet den firmenbezogenen Steuerprozentsatz", "Typ": "Unveränderte Klassifikation; Präfix 3 bezeichnet Vortragssteuerung",
                   "Steuertyp": "Steuerkategorie des Kontos", "Bemerkung": "Vollständige Notizen", "Buchungssperre": "Buchungssperre, kein Ausschluss aus der Liste",
                   "DATEVKonto": "DATEV-Konto", "DATEVAutomatik": "Kennzeichen für DATEV-Automatikkonto",
                   "Kennzeichen": "Verschachtelte Listen mit sechsstelligen Zeichenanzahlen, nicht UTF-8-Bytelängen",
                   "Waehrung": "Währung", "UStIDNummer": "Umsatzsteuer-ID", "ZMKonto": "Einstellung zur Zusammenfassenden Meldung",
                   "KoStPflicht": "Kostenstellenpflicht"},
        "enums": {"Steuertyp": ACCOUNT_TAX_TYPES},
        "joins": ["JOURNAL.Firma_id = KONTO.Firma_id AND JOURNAL.Konto = KONTO.Nummer",
                  "Finanzberichte ersetzen Konto durch SammelKonto, wenn > 0",
                  "Dekodierter Steuername = STEUERSATZ.Name AND KONTO.Firma_id = STEUERSATZ.Firma_id"],
        "derived_fields": {"Nummer_formatiert": "Mindestens vier Stellen", "Bezeichnung_Vorlage": "Ursprüngliche Bezeichnung",
                           "Steuersatz": "Neuestes nicht leeres Steuerschlüsselfeld; bei gleichem Datum erste gespeicherte Alternative",
                           "UVA_Kennzeichen": "Jedes UVA-Feld unabhängig auflösen, anschließend mit Leerzeichen verbinden",
                           "Steuerzuordnungen": "Datierte Datensätze mit gueltig_ab/steuerschluessel/uva_bemessung/uva_steuer, neueste zuerst"},
        "notes": ["Gepackte Datensätze: Datum, Steuerschlüssel, zwei UVA-Felder; weiterer Meldeschlüssel nur im unveränderten Kennzeichen.",
                  "Leere Felder erben frühere Werte; '-' ist ausdrücklich gesetzt. Vorgaben sind nicht die tatsächlich gebuchten JOURNAL.Steuersatz-Werte.",
                  "Namen ersetzen Platzhalter durch STEUERSATZ.Prozent / 100 mit %. Notizen bleiben auch bei gekürzter PDF-Darstellung vollständig."],
    },
    "STEUERSATZ": {
        "meaning": "Firmenbezogene Steuerdefinitionen einschließlich gesperrter und OSS-Schlüssel",
        "mapping_basis": "Datenbankstand und bereitgestelltes Bildschirmfoto der Steuersätze; keine verifizierte Connect-Zuordnung",
        "tools": ["list_tax_rates", "list_accounts"],
        "fields": {"_rowid": "Lokale ID", "Firma_id": "Zugehörige Firma", "Name": "Name des Steuerschlüssels", "Beschreibung": "Vollständige Beschreibung/Warnungen",
                   "Typ": "Steuerkategorie", "Prozent": "Unveränderte Hundertstel eines Prozentpunkts; null ist nicht angegeben",
                   "Berechnung": "Berechnungsgrundlage", "Buchungssperre": "Buchungssperre", "OSS": "OSS-Kennzeichen", "Datev": "DATEV-Schlüssel",
                   "KontoSteuer1": "Erstes Steuerkonto", "KontoSteuer2": "Zweites Steuerkonto", "KontoSteuerNF": "Konto für nicht fällige Steuer",
                   "UVASteuer1": "Erste UVA-Steuerkennzahl", "UVASteuer2": "Zweite UVA-Steuerkennzahl",
                   "UVABemessung1": "Erste UVA-Bemessungskennzahl", "UVABemessung2": "Zweite UVA-Bemessungskennzahl",
                   "NASteuerProzent": "Unveränderte Einstellung für nicht abziehbare Steuer", "NASteuerKonto": "Konto für nicht abziehbare Steuer",
                   "NANettoProzent": "Unveränderte Einstellung für nicht abziehbaren Nettobetrag", "NANettoKonto": "Konto für nicht abziehbaren Nettobetrag",
                   "SSS_Steuersatz": "Unveränderte Saldosteuersatzeinstellung"},
        "enums": {"Typ": TAX_RATE_TYPES, "Berechnung": TAX_CALCULATIONS},
        "percentages": {"stored_units_per_percent": 100, "raw_column": "Prozent", "output_column": "percent",
                        "unit": "Prozent, kein Geldbetrag", "null_preserved": True},
        "joins": ["Steuerkontofelder verweisen auf KONTO.Nummer mit übereinstimmender Firma_id",
                  "JOURNAL.Steuersatz ist eine Schlüsselzeichenkette; Steuer_id=0 kann mit gültigem Schlüssel vorkommen"],
        "notes": ["Prozent bleibt unverändert; percent ist eine Dezimalzeichenkette. Andere Prozenteinstellungen bleiben unverändert.",
                  "Null bleibt nicht angegeben, auch wenn die Anwendung 0.00 anzeigt; keine Steuerbefreiung wird abgeleitet.",
                  "KONTO.Steuertyp 3/4/5 unterscheidet sich von Typ 1/2 dieser Tabelle."],
    },
    "WIRTSCHAFTSJAHR": {
        "meaning": "Firmenbezogene Geschäftsjahre, Sperren, Währung und Versteuerungsart",
        "mapping_basis": "Datenbankstand und bereitgestelltes Bildschirmfoto der Geschäftsjahre; nur beobachtete Versteuerungsart 2 beschriftet",
        "tools": ["list_fiscal_years", "get_account_statement", "get_financial_statements", "get_trial_balance"],
        "fields": {"_rowid": "Lokale Geschäftsjahr-ID", "Firma_id": "Zugehörige Firma", "Bezeichnung": "Bezeichnung, nicht zwingend Kalenderjahr",
                   "Von": "Beginn einschließlich", "Bis": "Ende einschließlich", "Waehrung": "Währung", "Gesperrt": "Ganzjährige Sperre",
                   **{f"P{month:02d}_Gesperrt": "Sperre der Monatsperiode" for month in range(1, 13)},
                   "SaldoVortrag": "Saldovortragskennzeichen", "Versteuerung": "Versteuerungsart", "SSS": "Saldosteuersatzkennzeichen",
                   "SSS_Prozentsatz1": "Unveränderte Saldosteuersatzeinstellung 1", "SSS_Prozentsatz2": "Unveränderte Saldosteuersatzeinstellung 2"},
        "enums": {"Versteuerung": FISCAL_TAX_MODES, "Gesperrt": {0: "Offen", 1: "Gesperrt"}},
        "joins": ["BUCHUNG.Wj_id = WIRTSCHAFTSJAHR._rowid AND BUCHUNG.Firma_id = WIRTSCHAFTSJAHR.Firma_id",
                  "POSTEN-/ZAHLUNG-Zähler berücksichtigen Firma_id und Datum BETWEEN Von AND Bis"],
        "derived_fields": {"booking_count": "Alle zugeordneten Buchungsköpfe einschließlich Eröffnungen und Stornos",
                           "op_document_count": "Alle datierten POSTEN einschließlich Gutschriften, ausgeglichener Datensätze und Entwürfe; keine Anzahl offener Rechnungen",
                           "op_payment_count": "Alle datierten ZAHLUNG-Datensätze, keine Zahlungsaufträge"},
        "notes": ["Das Berichtsjahr wählt genau eine Periode, deren Von in diesem Jahr beginnt; Berichte begrenzen auch Buchungsdaten auf Von/Bis.",
                  "Sperren werden gelesen, nicht geändert; nicht verifizierte Versteuerungsarten bleiben unbekannt."],
    },
    "KONTOSTRUKTUR": {
        "meaning": "Firmenbezogene Gliederung von Bilanz und Gewinn- und Verlustrechnung",
        "mapping_basis": "Rekonstruktion aus dem Datenbankstand mit Abgleich gegen Berichts-PDFs; keine verifizierte Connect-Zuordnung",
        "tools": ["get_financial_statements"],
        "fields": {"_rowid": "Gliederungs-ID", "Firma_id": "Zugehörige Firma"},
        "joins": ["STRUKTURPOSITION.Ks_id = KONTOSTRUKTUR._rowid AND STRUKTURPOSITION.Firma_id = KONTOSTRUKTUR.Firma_id"],
        "notes": ["Mehrere Gliederungen erfordern eine ausdrückliche gliederung_id. Historische Gliederungsversionen sind nicht verfügbar.",
                  "Die Rekonstruktion ist kein eingereichter oder steuerlich angepasster Jahresabschluss."],
    },
    "STRUKTURPOSITION": {
        "meaning": "Berichtshierarchie, ausdrückliche Kontenzuordnungen und Darstellungsvorzeichen",
        "mapping_basis": "Rekonstruktion aus dem Datenbankstand mit Abgleich gegen Berichts-PDFs; keine verifizierte Connect-Zuordnung",
        "tools": ["get_financial_statements"],
        "fields": {"_rowid": "Zeilen-ID", "Firma_id": "Zugehörige Firma", "Ks_id": "Gliederungs-ID", "ItemId": "Knoten-ID innerhalb der Gliederung",
                   "ParentId": "Übergeordnete ItemId; 0 ist die Wurzel", "Bezeichnung": "Bezeichnung", "Ebene": "Ebene; Hierarchie folgt ParentId",
                   "Kontoliste": "Kommagetrennte ausdrückliche Kontonummern; nicht unterstützte Ausdrücke führen zum Fehler",
                   "Struktur": "Berichtsabschnitt", "VzWechsel": "Vorzeichen des berechneten Knotens umkehren"},
        "enums": {"Struktur": {"A": "Aktiva", "P": "Passiva/Eigenkapital", "G": "Gewinn und Verlust", "B": "Eingebundenes Jahresergebnis"}},
        "joins": ["ParentId verweist auf ItemId innerhalb Firma_id/Ks_id", "Kontoliste verweist auf KONTO.Nummer derselben Firma"],
        "notes": ["Genau eine A/P/G-Wurzel und ein B-Knoten; fehlende Eltern, Zyklen oder nicht unterstützte gemischte Abschnitte führen zum Fehler.",
                  "Summen umfassen eigene Konten und Kinder; G liefert B genau einmal.",
                  "Doppelt unter A/P gelistete Konten wechseln nach Saldovorzeichen; einfach gelistete bleiben zugeordnet, auch bei Steuersollsalden.",
                  "P kehrt Soll minus Haben um; VzWechsel wendet anschließend die gespeicherte Umkehrung an.",
                  "Nicht zugeordnete/mehrdeutige Konten mit Nichtnullsaldo, Journalungleichgewicht, unausgeglichene ausgeschlossene Steuerkonten oder Bilanzabweichungen führen zum Fehler.",
                  "Ein fehlendes unmittelbar vorangehendes Geschäftsjahr ergibt null, keine erfundene Null."],
    },
    "ZAHLUNG": {
        "meaning": "Gespeicherte OP-Zahlungen, keine Zahlungsaufträge",
        "mapping_basis": "ID-Verknüpfungen und Zahlungs-/Gutschrift-/Minderungsabgleich im Datenbankstand; keine verifizierte Connect-Zahlungszuordnung",
        "tools": ["list_fiscal_years", "list_payments", "get_payment", "get_open_item"],
        "fields": {"_rowid": "Zahlungs-/Ausgleichs-ID", "Firma_id": "Zugehörige Firma", "Datum": "Gespeichertes Zahlungsdatum",
                   "Art": "Unveränderte Zahlungsart, nicht POSTEN.Art", "Adress_id": "Adress-ID", "Buchung_id": "Buchungs-ID; bei Ausgleichen ist 0 möglich",
                   "PKonto": "Personenkonto", "FKonto": "Finanzkonto", "ReNr": "Referenz, niemals Verknüpfungsschlüssel für Zuordnungen",
                   "BuText": "Buchungstext", "Referenz": "Gespeicherte Referenz", "Waehrung": "Zahlungswährung", "Kurs": "Gespeicherter Kurs, nicht neu berechnet",
                   "Zahlungsart": "Unveränderte Zahlungsarteinstellung", "Notizen": "Vollständige Notizen", "ValutaBuchung_id": "Referenz der Bewertungsbuchung",
                   "GesamtZahlFW": "Vollständige vorzeichenbehaftete Zahlungssumme FW", "GesamtZahlSW": "Vollständige vorzeichenbehaftete Zahlungssumme SW",
                   "GesamtMindFW": "Vollständige Minderungssumme FW", "GesamtMindSW": "Vollständige Minderungssumme SW",
                   "GesamtValutaAG": "Gespeicherter Bewertungsbetrag", "Anonymisiert": "Anonymisierungskennzeichen"},
        "joins": ["ZAHLUNGSPOSITION.Zahlung_id = ZAHLUNG._rowid AND ZAHLUNGSPOSITION.Firma_id = ZAHLUNG.Firma_id",
                  "Geschäftsjahrzähler berücksichtigen Firma und Datum BETWEEN Von AND Bis"],
        "notes": ["Kopfsummen gehören zur gesamten Zahlung, nicht zu jeder verknüpften Rechnung.",
                  "Ausgleiche mit Gesamtsumme null können mehrere Rechnungen und Gutschriften verbinden; daraus folgen weder eindeutige Rechnung-Gutschrift-Paare noch eine Banküberweisung.",
                  "Zahlungs-Art bleibt unverändert; POSTEN.Art-Bezeichnungen gelten nur für zugehörige OP-Datensätze."],
    },
    "ZAHLUNGSPOSITION": {
        "meaning": "Vorzeichenbehaftete Zahlungs- und/oder Minderungszuordnung zu einer OP-Buchungsposition",
        "mapping_basis": "Verifizierte Verknüpfungen im Datenbankstand; keine verifizierte Connect-Zuordnung",
        "tools": ["get_open_item", "get_payment"],
        "fields": {"_rowid": "Zuordnungs-ID", "Firma_id": "Zugehörige Firma", "Zahlung_id": "Zahlungs-ID", "Position": "Reihenfolge der Zahlungsposition",
                   "Postenposition_id": "OP-Positions-ID, keine OP-Kopf-ID", "ZBuText": "Zahlungstext", "MBuText": "Minderungstext",
                   "MKonto": "Minderungskonto, etwa gespeichertes Skontokonto", "SteuerBuchung_id": "Referenz der Steuerbuchung",
                   "BetragZahlFW": "Vorzeichenbehafteter zugeordneter Zahlbetrag FW", "BetragZahlSW": "Vorzeichenbehafteter zugeordneter Zahlbetrag SW",
                   "BetragMindFW": "Zugeordnete Minderung FW", "BetragMindSW": "Zugeordnete Minderung SW",
                   "BetragValutaAG": "Gespeicherter zugeordneter Bewertungsbetrag"},
        "joins": ["ZAHLUNGSPOSITION.Postenposition_id = POSTENPOSITION._rowid AND beide Firma_id stimmen überein",
                  "POSTENPOSITION.Posten_id = POSTEN._rowid AND beide Firma_id stimmen überein",
                  "ZAHLUNGSPOSITION.Zahlung_id = ZAHLUNG._rowid AND beide Firma_id stimmen überein"],
        "notes": ["Kein Abgleich anhand Rechnungsreferenz oder Betrag. Ein auf mehrere OP-Positionen verteilter Zahlungseingang bleibt in mehreren Zuordnungszeilen, nicht als doppelte Zahlungssummen.",
                  "Negative Zuordnungen, Rückzahlungen, Gutschriften und Ausgleiche mit Gesamtsumme null erhalten; keine Vorzeichenumkehr oder Auslassung von Nullen.",
                  "FW/SW sowie Posten- und Zahlungswährungen bleiben getrennt; keine abgeleitete Währungsumrechnung.",
                  "OP-Zuordnungssummen und Differenzen zu gespeicherten Zahlungen/Minderungen umfassen unabhängig von der Seiteneinteilung alle verknüpften Zeilen."],
    },
    "ADRESSE": {
        "meaning": "Adressbucheintrag; kann zugleich Kunde und Lieferant sein",
        "tools": ["list_addresses", "get_address"],
        "api_structures": ["AdresseItem", "AdresseStatus"],
        "api_fields": {"Adresse_ID": "_rowid", "AdressNr": "KZ_AdressNr", "Matchcode": "KZ_Matchcode",
                       "Kategorie": "KZ_Kategorie", "KundenStatus": "KF_Status", "LieferantenStatus": "LF_Status"},
        "enums": {"KF_Status": ADDRESS_STATUSES, "LF_Status": ADDRESS_STATUSES},
        "notes": ["Connect -1 (ist Kunde/Lieferant) und -2 (ohne Statusfilter) sind Filterauswahlen, keine gespeicherten Statusbezeichnungen."],
    },
    "AUFTRAG": {
        "meaning": "Verkaufsbelegkopf einschließlich Rechnungen, Angeboten, Stornos und Entwürfen",
        "api_structures": ["VerkaufbelegItem", "VerkaufbelegArt"],
        "api_fields": {"Verkaufbeleg_ID": "_rowid", "Adresse_ID": "Adress_id", "AuftragNr": "AuftragsNr",
                       "VerkaufbelegArt": "Art", "Entwurf": "Entwurf", "Posten_ID": "Posten_id", "Referenz": "BestellNr"},
        "enums": {"Art": SALES_TYPES},
        "joins": ["AUFTRAG.Adress_id = ADRESSE._rowid AND AUFTRAG.Firma_id = ADRESSE.Firma_id",
                  "AUFTRAG.Posten_id = POSTEN._rowid AND AUFTRAG.Firma_id = POSTEN.Firma_id"],
        "notes": ["Art=4 bedeutet Rechnung, nicht zwingend unbezahlt oder unstorniert. Ein Storno ist ein eigener Datensatz mit Art=8.",
                  "Entwurf ist das gespeicherte Entwurfskennzeichen; VerkaufbelegStatus 1/2/3 ist ein API-Filter, nicht AUFTRAG.Art."],
    },
    "AUFTRAGSPOSITION": {
        "meaning": "Geordnete Verkaufsbelegpositionen einschließlich nicht finanzieller Text- und Gliederungspositionen",
        "api_structures": ["VerkaufbelegPositionItem", "VerkaufbelegPositionArt"],
        "api_fields": {"Nummer": "Nummer", "VerkaufbelegPositionArt": "Art", "Ertragskonto": "EKonto"},
        "enums": {"Art": POSITION_TYPES},
        "joins": ["AUFTRAGSPOSITION.Auftrag_id = AUFTRAG._rowid AND AUFTRAGSPOSITION.Firma_id = AUFTRAG.Firma_id"],
    },
    "BUCHUNG": {
        "meaning": "Buchungskopf, nicht zwingend eine einzelne Journalzeile",
        "api_structures": ["BuchungItem", "BuchungListItem"],
        "api_fields": {"Buchung_ID": "_rowid", "Datum": "Datum", "Text": "Text", "Notizen": "Bemerkung",
                       "Summe": "Summe", "SummeFW": "SummeFW"},
        "notes": ["Connect kennzeichnet BuchungStatus/Status als veraltet. Gespeicherter Status=3 kommt ebenfalls vor; keine Festschreibungsbezeichnungen werden abgeleitet.",
                  "Kontenfilter verwenden JOURNAL.Konto, um aufgeteilte Buchungen einzuschließen.",
                  "Soll-/Habenkonten erfordern auf der gewählten Seite einen Betrag ungleich null, auch negative Stornos.",
                  "Kostenstellenfilter vergleichen Kostenstelle1/2 exakt. Mehrere Journalfilter können verschiedene Zeilen desselben Buchungskopfs treffen."],
        "fields": {"Wj_id": "Geschäftsjahr-ID", "Firma_id": "Zugehörige Firma", "Datum": "Buchungsdatum",
                   "Art": "2 ist eine Eröffnungsbuchung; andere Werte werden nicht aus API-Filtern abgeleitet"},
        "enums": {"Art": {2: "Eröffnungsbuchung"}},
        "joins": ["BUCHUNG.Wj_id = WIRTSCHAFTSJAHR._rowid AND BUCHUNG.Firma_id = WIRTSCHAFTSJAHR.Firma_id"],
        "tools": ["list_bookings", "get_booking", "get_account_statement", "get_financial_statements", "list_fiscal_years", "get_trial_balance"],
        "report_rules": ["Art=2 liefert den Anfangssaldo, wird aber aus den Umsätzen ausgeschlossen.",
                         "Kontoauszug sortiert nach Datum, BelegNr, JOURNAL.NummerLong, Position, Journalzeilen-ID.",
                         "Konten- und Finanzberichte umfassen alle Statuswerte und Perioden.",
                         "Die Summen- und Saldenliste zeigt das Hauptbuch mit effektiven Sammelkonten sowie getrennten Eröffnungen und Umsätzen."],
    },
    "JOURNAL": {
        "meaning": "Soll-/Haben-Journalzeilen zu Buchungen",
        "api_structures": ["BuchungJournalItem"],
        "api_fields": {"Konto": "Konto", "BetragSoll": "BetragSoll", "BetragHaben": "BetragHaben",
                       "FW_Soll": "BetragSollFW", "FW_Haben": "BetragHabenFW"},
        "joins": ["JOURNAL.Buchung_id = BUCHUNG._rowid AND JOURNAL.Firma_id = BUCHUNG.Firma_id"],
        "fields": {"Firma_id": "Zugehörige Firma", "Buchung_id": "Kopf-ID", "Konto": "Kontonummer",
                   "SammelKonto": "Sammelkonto; >0 ersetzt Personenkonto in Finanzberichten",
                   "GegenKonto": "Gegenkonto", "Steuersatz": "Tatsächlich gebuchter Schlüssel; '-', leer und null erhalten",
                   "Steuer_id": "Kann bei gültigem Steuersatz 0 sein", "Storno": "Vorzeichenbehaftete Beträge nicht erneut umkehren",
                   "Nummer": "Kennung", "NummerLong": "Sortiernummer", "Position": "Position",
                   "BetragSoll": "Vorzeichenbehaftetes Soll in Hundertsteln", "BetragHaben": "Vorzeichenbehaftetes Haben in Hundertsteln",
                   "IV_Steuersatz": "Gespeicherter Istversteuerungsschlüssel", "IV_BetragSoll": "Gespeicherte Istversteuerungsbemessung SW Soll",
                   "IV_BetragHaben": "Gespeicherte Istversteuerungsbemessung SW Haben", "IV_Konto": "Istversteuerungs-Bemessungskonto",
                   "IV_KontoUStE": "Gespeichertes Steuerzuordnungskonto der Jahreserklärung", "BetragBemSoll": "Gespeicherte Bemessung Soll",
                   "BetragBemHaben": "Gespeicherte Bemessung Haben", "Versteuerung": "Unverändertes Versteuerungskennzeichen",
                   "SteuerStatus": "Unveränderter Steuerstatus", "DatumVerbucht": "Gespeichertes Verbuchungsdatum, nicht zwingend Buchungs-Datum"},
        "tools": ["list_bookings", "get_booking", "get_account_statement", "get_financial_statements", "get_tax_journal", "get_vat_return", "get_trial_balance"],
        "report_rules": ["Originale und vorzeichenbehaftete Gegenbuchungen erhalten; Soll minus Haben ergibt den Saldo (negativ H, positiv S).",
                         "Kontensuche berücksichtigt Konto ODER SammelKonto einmal; Finanzberichte ersetzen Personenkonten, zählen sie nie doppelt.",
                         "Jahressummen und laufende Salden werden vor der Seiteneinteilung berechnet.",
                         "Die Summen- und Saldenliste ordnet Personenbuchungen dem positiven SammelKonto zu und summiert SW im Hauptbuch, getrennt nach Eröffnung und Umsatz."],
    },
    "POSTEN": {
        "meaning": "Forderungs-/Verbindlichkeitsposten einschließlich ausgeglichener Datensätze und Gutschriften",
        "api_structures": ["OffenePostenItem", "OffenePostenArt"],
        "api_fields": {"Posten_ID": "_rowid", "Adresse_ID": "Adress_id", "Postenart": "Art",
                       "BelegNr": "ReNr", "Konto": "PKonto", "Text": "BuText"},
        "enums": {"Art": OPEN_ITEM_TYPES},
        "joins": ["POSTEN.Adress_id = ADRESSE._rowid AND POSTEN.Firma_id = ADRESSE.Firma_id"],
        "tools": ["list_open_items", "get_open_item", "get_payment", "get_open_items_as_of", "get_open_item_aging"],
        "fields": {"_rowid": "OP-Posten-ID", "Buchung_id": "Gespeicherte Buchungsreferenz", "Entwurf": "Entwurfskennzeichen; altes null gilt nicht als Entwurf",
                   "BezahltFW": "Gespeicherter vorzeichenbehafteter Zahlbetrag FW", "BezahltSW": "Gespeicherter vorzeichenbehafteter Zahlbetrag SW",
                   "MinderungFW": "Gespeicherte Minderung FW", "MinderungSW": "Gespeicherte Minderung SW",
                   "OffenFW": "Gespeicherter Restbetrag FW", "OffenSW": "Gespeicherter Restbetrag SW",
                   "TageNetto": "Belegbezogene Nettofrist in Kalendertagen, keine rückwirkende Stammdatenvorgabe",
                   "NichtMahnen": "Aktuelles Mahnausschlusskennzeichen", "Mahnstufe": "Aktuelle Mahnstufe des Datenbankstands",
                   **{f"DatumMahnung{level}": "Gespeichertes Mahndatum; nur Daten <= Stichtag sind historische Nachweise" for level in range(1,5)}},
        "derived_fields": {
            "open_as_of_FW/SW": "Aktuelles Brutto minus vorzeichenbehaftete datierte Zahlungen/Minderungen <= Stichtag; null bei nicht abgestimmter/unbekannter Historie",
            "calculated_open_FW/SW": "Ausdrücklich vorläufige Arithmetik vor Prüfung der Historie",
            "history_status": "Vollständige gespeicherte Zahlungs-/Minderungssummen stimmen mit Verknüpfungen überein, weichen ab oder sind unbekannt",
            "due_date": "Belegdatum plus gespeicherte TageNetto in Kalendertagen; keine rechtliche oder Wochenendverschiebung",
            "aging_bucket": "Fälligkeitsgruppe: nicht fällig, 1–30, 31–60, 61–90, über 90 Tage, Guthaben, ausgeglichen, unbekanntes Fälligkeitsdatum oder unbekannter Saldo",
            "observed_dunning_level_as_of": "Höchste datierte Mahnstufe <= Stichtag, kein vollständiger historischer Mahnzustand",
        },
        "notes": ["Die Standardliste wählt OffenFW <> 0 einschließlich negativer Guthaben. Die Option zum Einbeziehen ausgeglichener Posten listet auch geschlossene Posten.",
                  "FW- und SW-Beträge bleiben getrennt; Fachwerkzeuge teilen Geldbeträge durch 100, die SQL-Abfrage nicht.",
                  "NULL Entwurf ist kein Entwurf. Die bestehende Bestandsliste leitet keine Fälligkeiten ab; Stichtagswerkzeuge bieten ein separates Kalendertagemodell.",
                  "Das OP-Detailwerkzeug liest ausdrücklich ausgeglichene Posten und Entwürfe; Positionen und Zahlungszuordnungen haben unabhängige Seiteneinteilung.",
                  "Der Abgleich vergleicht alle historischen Zuordnungen mit gespeichertem Bezahlt/Minderung in FW/SW; Differenzen werden nicht verborgen, null bedeutet nicht angegeben.",
                  "Die Zahlung über Zahlung_id im Zahlungsdetailwerkzeug abrufen, um alle gemeinsam ausgeglichenen Rechnungen und Gutschriften zu sehen; keine eindeutige Paarung wird abgeleitet."],
        "historical_limits": ["Historische Belegversionen oder gelöschte Zahlungen sind aus diesem Datenbankstand nicht wiederherstellbar.",
                              "Aktuelle NichtMahnen/Mahnstufe werden nicht rückdatiert; datierte Mahnnachweise werden separat gemeldet.",
                              "Summen über den vollständigen Filter gruppieren nach Seite/Währung/Fälligkeitsgruppe und zählen unbekannte Salden, statt null als Zahl zu erfinden."],
    },
    "POSTENPOSITION": {
        "meaning": "Buchhalterische und steuerliche Aufteilung eines Forderungs-/Verbindlichkeitspostens",
        "api_structures": ["OffenePostenPositionItem"],
        "api_fields": {"Position": "Position", "Text": "BuText", "EA_Konto": "EKonto"},
        "joins": ["POSTENPOSITION.Posten_id = POSTEN._rowid AND POSTENPOSITION.Firma_id = POSTEN.Firma_id"],
        "tools": ["get_open_item", "get_payment"],
        "fields": {"_rowid": "OP-Positions-ID für Zahlungszuordnungen", "Posten_id": "OP-Kopf-ID",
                   "Firma_id": "Zugehörige Firma", "Steuersatz": "Gespeicherter Steuerschlüssel; nicht aus Kontenvorgaben abgeleitet"},
    },
    "WAEHRUNG": {
        "meaning": "Firmenbezogene Währungsdefinitionen",
        "api_structures": ["WaehrungListItem"],
        "api_fields": {"Name": "Name", "Isocode": "ISOCode", "Kurs": "Kurs"},
    },
}
CATALOG.update(MASTERS_CATALOG)
CATALOG.update(TAX_CATALOG)
CATALOG.update(ASSET_CATALOG)
CATALOG.update(COMMERCE_CATALOG)


def _currency_amounts(result, table, extra_fields=()):
    fields = MONEY_FIELDS[table].union(extra_fields)
    indices = [i for i, column in enumerate(result["columns"]) if column in fields]
    for row in result["rows"]:
        for index in indices:
            if row[index] is not None:
                amount = Decimal(str(row[index])) / 100
                text = format(amount, "f")
                whole, _, fraction = text.partition(".")
                row[index] = whole + "." + fraction.rstrip("0").ljust(2, "0")
    result["money"] = {
        "columns": [result["columns"][i] for i in indices],
        "unit": "Währungseinheiten",
        "representation": "Dezimalzeichenkette",
        "stored_units_per_currency_unit": 100,
    }
    return result


def _integer(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ParameterFehler(f"{name} muss eine ganze Zahl >= {minimum} sein")


def _dates(where, bindings, column, date_from, date_to):
    for name, value in (("datum_von", date_from), ("datum_bis", date_to)):
        if value is not None:
            try:
                valid = isinstance(value, str) and date.fromisoformat(value).isoformat() == value
            except ValueError:
                valid = False
            if not valid:
                raise ParameterFehler(f"{name} muss ein gültiges Datum im Format JJJJ-MM-TT sein")
    if date_from and date_to and date_from > date_to:
        raise ParameterFehler("datum_von darf nicht nach datum_bis liegen")
    for value, operator in ((date_from, ">="), (date_to, "<=")):
        if value is not None:
            where.append(f"{column} {operator} ?")
            bindings.append(value)


def _labels(result, column, labels):
    index = result["columns"].index(column)
    result["columns"].append(column + "_label")
    for row in result["rows"]:
        row.append(labels.get(row[index], "Unbekannt"))
    return result


def _packed_strings(value):
    """MonKeys Zeichenkettenlisten mit sechsstelligen Zeichenanzahlen statt UTF-8-Bytelängen dekodieren."""
    if not value:
        return []
    position = 0

    def size():
        nonlocal position
        prefix = value[position:position + 6]
        if len(prefix) != 6 or not prefix.isascii() or not prefix.isdigit():
            raise DatenFehler("Ungültige gepackte Kontensteuereinstellungen")
        position += 6
        return int(prefix)

    count = size()
    items = []
    for _ in range(count):
        length = size()
        item = value[position:position + length]
        if len(item) != length:
            raise DatenFehler("Abgeschnittene gepackte Kontensteuereinstellungen")
        items.append(item)
        position += length
    if position != len(value):
        raise DatenFehler("Nachgestellte Daten in gepackten Kontensteuereinstellungen")
    return items


class BusinessReader:
    def __init__(self, database):
        self.database = database

    def schema(self, table=None):
        names = [table.upper()] if table is not None else list(CATALOG)
        if any(name not in CATALOG for name in names):
            raise ParameterFehler("Keine fachliche Zuordnung für diese Tabelle; für das Rohschema die Tabellenbeschreibung verwenden")
        tables = {}
        for name in names:
            description = self.database.describe(name)
            columns = {r[1] for r in description["columns"]["rows"]}
            tables[name] = dict(
                CATALOG[name],
                missing_mapped_columns=sorted(set(CATALOG[name].get("api_fields", {}).values()) - columns),
                missing_documented_columns=sorted(set(CATALOG[name].get("fields", {})) - columns),
            )
            tables[name]["money_fields"] = sorted(MONEY_FIELDS.get(name, set()) & columns)
        return {
            "reference": REFERENCE,
            "mapping_basis": "Connect-API-Bedeutungen sind bei vorhandenen api_strukturen/api_felder dokumentiert; lokale Zuordnungen sind abgeleitet und gegen die Struktur des Datenbankstands geprüft. Andere Einträge nennen ihre Grundlage aus Datenbankstand, Oberfläche oder PDF ausdrücklich. Kein Abgleich mit einer laufenden Connect-API.",
            "ids": "Alle Werkzeug-IDs sind lokale ganzzahlige _rowid-Werte; eine Übereinstimmung mit undurchsichtigen Connect-API-Zeichenketten-IDs wird nicht zugesichert.",
            "amounts": MONEY_CONVENTION,
            "tables": tables,
        }

    def _page(self, sql, bindings, limit, offset):
        _integer(offset, "versatz", 0)
        result = self.database.query(sql + " LIMIT -1 OFFSET ?", [*bindings, offset], limit)
        result["next_offset"] = offset + len(result["rows"]) if result["truncated"] and result["rows"] else None
        return result

    def companies(self, limit=100, offset=0):
        return self._page("SELECT _rowid, Name, Zusatz, Ort FROM FIRMA ORDER BY _rowid", [], limit, offset)

    def company(self, company_id):
        _integer(company_id, "firma_id")
        result = self.database.query("SELECT * FROM FIRMA WHERE _rowid=?", [company_id], 1)
        if not result["rows"]:
            if result["truncated"]:
                raise Abfragegrenze("Firmendatensatz überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
            raise ParameterFehler("Firma nicht gefunden")
        return {"company": result}

    def fiscal_years(self, company_id, limit=100, offset=0):
        _integer(company_id, "firma_id")
        result = self._page(
            "SELECT w._rowid,w.Firma_id,w.Bezeichnung,w.Von,w.Bis,w.Waehrung,w.Gesperrt,"
            + ",".join(f"w.P{month:02d}_Gesperrt" for month in range(1, 13))
            + ",w.SaldoVortrag,w.Versteuerung,w.SSS,w.SSS_Prozentsatz1,w.SSS_Prozentsatz2,"
            "(SELECT count(*) FROM BUCHUNG b WHERE b.Firma_id=w.Firma_id AND b.Wj_id=w._rowid) AS booking_count,"
            "(SELECT count(*) FROM POSTEN p WHERE p.Firma_id=w.Firma_id AND p.Datum BETWEEN w.Von AND w.Bis) AS op_document_count,"
            "(SELECT count(*) FROM ZAHLUNG z WHERE z.Firma_id=w.Firma_id AND z.Datum BETWEEN w.Von AND w.Bis) AS op_payment_count "
            "FROM WIRTSCHAFTSJAHR w WHERE w.Firma_id=? ORDER BY w.Von,w._rowid",
            [company_id], limit, offset,
        )
        _labels(result, "Gesperrt", {0: "Offen", 1: "Gesperrt"})
        return _labels(result, "Versteuerung", FISCAL_TAX_MODES)

    def tax_rates(self, company_id, search="", limit=100, offset=0):
        _integer(company_id, "firma_id")
        result = self._page(
            "SELECT _rowid,Firma_id,Name,Beschreibung,Typ,Prozent,Berechnung,"
            "KontoSteuer1,KontoSteuer2,KontoSteuerNF,UVASteuer1,UVASteuer2,UVABemessung1,UVABemessung2,"
            "NASteuerProzent,NASteuerKonto,NANettoProzent,NANettoKonto,Datev,Buchungssperre,SSS_Steuersatz,OSS "
            "FROM STEUERSATZ WHERE Firma_id=? AND "
            "instr(lower(coalesce(Name,'') || ' ' || coalesce(Beschreibung,'')),lower(?))>0 ORDER BY Name,_rowid",
            [company_id, search], limit, offset,
        )
        index = result["columns"].index("Prozent")
        result["columns"].append("percent")
        for row in result["rows"]:
            value = row[index]
            row.append(format(Decimal(str(value)) / 100, ".2f") if value is not None else None)
        result["percentages"] = CATALOG["STEUERSATZ"]["percentages"]
        _labels(result, "Typ", TAX_RATE_TYPES)
        return _labels(result, "Berechnung", TAX_CALCULATIONS)

    def accounts(self, company_id, search="", account_from=None, account_to=None, limit=100, offset=0):
        _integer(company_id, "firma_id")
        where, bindings = ["Firma_id=?"], [company_id]
        for value, operator in ((account_from, ">="), (account_to, "<=")):
            if value is not None:
                _integer(value, "Kontengrenze", 0)
                where.append("Nummer" + operator + "?")
                bindings.append(value)
        if account_from is not None and account_to is not None and account_from > account_to:
            raise ParameterFehler("konto_von darf konto_bis nicht überschreiten")
        where.append("instr(lower(CAST(Nummer AS TEXT) || ' ' || coalesce(Bezeichnung,'') || ' ' || coalesce(Bemerkung,'')),lower(?))>0")
        bindings.append(search)
        result = self._page(
            "SELECT _rowid,Firma_id,Nummer,Bezeichnung,Typ,Steuertyp,Bemerkung,Buchungssperre,"
            "DATEVKonto,DATEVAutomatik,Kennzeichen,Waehrung,UStIDNummer,ZMKonto,KoStPflicht "
            "FROM KONTO WHERE " + " AND ".join(where) + " ORDER BY Nummer,_rowid",
            bindings, limit, offset,
        )
        columns = result["columns"]
        number_index, name_index, settings_index = (columns.index(name) for name in ("Nummer", "Bezeichnung", "Kennzeichen"))
        columns.extend(["Nummer_formatiert", "Bezeichnung_Vorlage", "Steuersatz", "UVA_Kennzeichen", "Steuerzuordnungen"])
        needed_rates = set()
        for row in result["rows"]:
            versions = [_packed_strings(value) for value in _packed_strings(row[settings_index])]
            if any(len(version) != 5 for version in versions):
                raise DatenFehler("Fünf Felder je Kontensteuerzuordnung erwartet")
            for version in versions:
                try:
                    date.fromisoformat(version[0])
                except ValueError:
                    raise DatenFehler("Ungültiges Datum in einer Kontensteuerzuordnung") from None
            versions.sort(key=lambda version: version[0], reverse=True)
            # Neuester nicht leerer Wert je Feld; bei gleichem Datum bleibt die erste gespeicherte
            # Alternative wie im gedruckten Kontenplan. "-" ist ein ausdrücklicher Schlüssel.
            effective = ["", "", ""]
            for version in versions:
                for index, value in enumerate(version[1:4]):
                    if value and not effective[index]:
                        effective[index] = value
            code = effective[0] or "-"
            row.extend([
                str(row[number_index]).zfill(4), row[name_index], code,
                " ".join(value for value in effective[1:] if value),
                [{"valid_from": version[0], "tax_code": version[1],
                  "uva_base": version[2], "uva_tax": version[3]} for version in versions],
            ])
            if "#P#" in (row[name_index] or ""):
                needed_rates.add(code)
        if needed_rates:
            rates = self.database.query(
                "SELECT Name,Prozent FROM STEUERSATZ WHERE Firma_id=? AND Name IN ("
                + ",".join("?" for _ in needed_rates) + ")",
                [company_id, *sorted(needed_rates)], 500,
            )
            percentages = dict(rates["rows"])
            if rates["truncated"] or len(percentages) != len(rates["rows"]) or set(percentages) != needed_rates:
                raise DatenFehler("Genau ein firmenbezogener Prozentsatz je Platzhalter im Kontennamen erwartet")
            code_index = columns.index("Steuersatz")
            for row in result["rows"]:
                if "#P#" in (row[name_index] or ""):
                    percentage = format((Decimal(str(percentages[row[code_index]])) / 100).normalize(), "f")
                    row[name_index] = row[name_index].replace("#P#", percentage + "%")
        result["basis"] = "Gespeicherter Kontenstamm einschließlich unbebuchter und gesperrter Konten. Datierte Steuerzuordnungen erben frühere nicht leere Felder; Vorgaben sind nicht die tatsächlich gebuchten Journalsteuerschlüssel."
        return _labels(result, "Steuertyp", ACCOUNT_TAX_TYPES)

    def addresses(self, company_id, search="", role="all", status="all", limit=100, offset=0):
        _integer(company_id, "firma_id")
        if role not in {"all", "customer", "supplier"} or status not in {"all", "active", "inactive", "blocked"}:
            raise ParameterFehler("Ungültige Adressrolle oder ungültiger Adressstatus")
        if role == "all" and status != "all":
            raise ParameterFehler("Bei Statusfilterung die Rolle Kunde oder Lieferant wählen")
        where, bindings = ["Firma_id = ?"], [company_id]
        if role != "all":
            column = "KF_Status" if role == "customer" else "LF_Status"
            if status == "all":
                where.append(column + " IN (1, 2, 3)")
            else:
                where.append(column + " = ?")
                bindings.append({"active": 1, "inactive": 2, "blocked": 3}[status])
        where.append("instr(lower(coalesce(KZ_AdressNr,'') || ' ' || coalesce(KZ_Matchcode,'') || ' ' || coalesce(RA_Firma1,'') || ' ' || coalesce(RA_Vorname,'') || ' ' || coalesce(RA_Nachname,'')), lower(?)) > 0")
        bindings.append(search)
        result = self._page("SELECT _rowid, Firma_id, KZ_AdressNr, KZ_Matchcode, RA_Firma1, RA_Vorname, RA_Nachname, RA_Ort, RA_Email, KF_Status, LF_Status FROM ADRESSE WHERE " + " AND ".join(where) + " ORDER BY _rowid", bindings, limit, offset)
        _labels(result, "KF_Status", ADDRESS_STATUSES)
        return _labels(result, "LF_Status", ADDRESS_STATUSES)

    def address(self, company_id, address_id):
        _integer(company_id, "firma_id")
        _integer(address_id, "adresse_id")
        header = self.database.query("SELECT * FROM ADRESSE WHERE Firma_id=? AND _rowid=?", [company_id, address_id], 1)
        if not header["rows"]:
            if header["truncated"]:
                raise Abfragegrenze("Adressdatensatz überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
            raise ParameterFehler("Adresse in dieser Firma nicht gefunden")
        _labels(header, "KF_Status", ADDRESS_STATUSES)
        return {"address": _labels(header, "LF_Status", ADDRESS_STATUSES)}

    def sales_documents(self, company_id, document_type=None, address_id=None, date_from=None, date_to=None, include_drafts=False, limit=100, offset=0, search=""):
        _integer(company_id, "firma_id")
        where, bindings = ["Firma_id = ?"], [company_id]
        if document_type is not None:
            _integer(document_type, "belegart")
            if document_type not in SALES_TYPES:
                raise ParameterFehler("belegart muss ein Connect-VerkaufbelegArt-Schlüssel von 1 bis 9 sein")
            where.append("Art = ?")
            bindings.append(document_type)
        if address_id is not None:
            _integer(address_id, "adresse_id")
            where.append("Adress_id = ?")
            bindings.append(address_id)
        if not include_drafts:
            where.append("coalesce(Entwurf,0) = 0")
        _dates(where, bindings, "Datum", date_from, date_to)
        if search:
            where.append("instr(lower(coalesce(AuftragsNr,'') || ' ' || coalesce(BestellNr,'') || ' ' || coalesce(Betreff,'')),lower(?))>0")
            bindings.append(search)
        result = self._page("SELECT _rowid, Firma_id, Art, Entwurf, AuftragsNr, Datum, Adress_id, Posten_id, Betreff, Waehrung, GesamtNettoFW, GesamtSteuerFW, GesamtBruttoFW, GesamtNettoSW, GesamtBruttoSW FROM AUFTRAG WHERE " + " AND ".join(where) + " ORDER BY Datum, _rowid", bindings, limit, offset)
        return _currency_amounts(_labels(result, "Art", SALES_TYPES), "AUFTRAG")

    def sales_document(self, company_id, document_id, position_limit=100, position_offset=0):
        _integer(company_id, "firma_id")
        _integer(document_id, "beleg_id")
        header = self.database.query("SELECT * FROM AUFTRAG WHERE Firma_id=? AND _rowid=?", [company_id, document_id], 1)
        if not header["rows"]:
            if header["truncated"]:
                raise Abfragegrenze("Verkaufsbeleg überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
            raise ParameterFehler("Verkaufsbeleg in dieser Firma nicht gefunden")
        _labels(header, "Art", SALES_TYPES)
        positions = self._page("SELECT * FROM AUFTRAGSPOSITION WHERE Firma_id=? AND Auftrag_id=? ORDER BY Nummer, _rowid", [company_id, document_id], position_limit, position_offset)
        _labels(positions, "Art", POSITION_TYPES)
        return {
            "document": _currency_amounts(header, "AUFTRAG"),
            "positions": _currency_amounts(positions, "AUFTRAGSPOSITION"),
        }

    def bookings(self, company_id, date_from=None, date_to=None, account=None, search="", limit=100, offset=0,
                 document_number="", debit_account=None, credit_account=None, cost_center=None):
        _integer(company_id, "firma_id")
        where, bindings = ["b.Firma_id = ?"], [company_id]
        _dates(where, bindings, "b.Datum", date_from, date_to)
        for value, name, side in (
            (account, "konto", None), (debit_account, "konto_soll", "BetragSoll"),
            (credit_account, "konto_haben", "BetragHaben"),
        ):
            if value is not None:
                _integer(value, name, 0)
                side_clause = "" if side is None else f" AND j.{side}<>0"
                where.append(
                    "EXISTS (SELECT 1 FROM JOURNAL j WHERE j.Firma_id=b.Firma_id "
                    f"AND j.Buchung_id=b._rowid AND j.Konto=?{side_clause})"
                )
                bindings.append(value)
        if cost_center is not None:
            where.append(
                "EXISTS (SELECT 1 FROM JOURNAL j WHERE j.Firma_id=b.Firma_id "
                "AND j.Buchung_id=b._rowid AND (j.Kostenstelle1=? OR j.Kostenstelle2=?))"
            )
            bindings.extend((cost_center, cost_center))
        if document_number:
            where.append("instr(lower(coalesce(b.BelegNr,'')),lower(?))>0")
            bindings.append(document_number)
        where.append("instr(lower(coalesce(b.BelegNr,'') || ' ' || coalesce(b.Text,'') || ' ' || coalesce(b.Referenz,'')), lower(?)) > 0")
        bindings.append(search)
        result = self._page("SELECT b._rowid, b.Firma_id, b.Datum, b.BelegNr, b.Text, b.KontoSoll, b.KontoHaben, b.Waehrung, b.Summe, b.SummeFW, b.Status FROM BUCHUNG b WHERE " + " AND ".join(where) + " ORDER BY b.Datum, b._rowid", bindings, limit, offset)
        return _currency_amounts(result, "BUCHUNG")

    def booking(self, company_id, booking_id, journal_limit=100, journal_offset=0):
        _integer(company_id, "firma_id")
        _integer(booking_id, "buchung_id")
        header = self.database.query("SELECT * FROM BUCHUNG WHERE Firma_id=? AND _rowid=?", [company_id, booking_id], 1)
        if not header["rows"]:
            if header["truncated"]:
                raise Abfragegrenze("Buchungskopf überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
            raise ParameterFehler("Buchung in dieser Firma nicht gefunden")
        journal = self._page(
            "SELECT * FROM JOURNAL WHERE Firma_id=? AND Buchung_id=? ORDER BY NummerLong,Position,_rowid",
            [company_id, booking_id], journal_limit, journal_offset,
        )
        if journal["truncated"] and not journal["rows"]:
            raise Abfragegrenze("Buchungsjournalzeile überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
        return {
            "booking": _currency_amounts(header, "BUCHUNG"),
            "journal_rows": _currency_amounts(journal, "JOURNAL"),
        }

    def _payment_allocations(self, company_id, column, value, limit, offset):
        # column wählen ausschließlich die beiden internen Aufrufer, niemals ein MCP-Parameter.
        result = self._page(
            "SELECT zp.*,z.Datum AS payment_date,z.ReNr AS payment_reference,"
            "z.Waehrung AS payment_currency,z.Buchung_id AS payment_booking_id,z.FKonto AS financial_account,"
            "p._rowid AS item_id,p.Art AS item_type,p.ReNr AS item_reference,p.Datum AS item_date,"
            "p.Waehrung AS item_currency,pp.Position AS item_position "
            + PAYMENT_ALLOCATION_FROM + "WHERE zp.Firma_id=? AND " + column + "=? "
            "ORDER BY z.Datum,z._rowid,zp.Position,zp._rowid",
            [company_id, value], limit, offset,
        )
        return _currency_amounts(_labels(result, "item_type", OPEN_ITEM_TYPES), "ZAHLUNGSPOSITION")

    def open_item(self, company_id, item_id, position_limit=100, position_offset=0,
                  payment_limit=100, payment_offset=0):
        _integer(company_id, "firma_id")
        _integer(item_id, "posten_id")
        header = self.database.query("SELECT * FROM POSTEN WHERE Firma_id=? AND _rowid=?", [company_id, item_id], 1)
        if not header["rows"]:
            if header["truncated"]:
                raise Abfragegrenze("OP-Kopf überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
            raise ParameterFehler("Offener Posten in dieser Firma nicht gefunden")
        item = dict(zip(header["columns"], header["rows"][0]))
        positions = self._page(
            "SELECT * FROM POSTENPOSITION WHERE Firma_id=? AND Posten_id=? ORDER BY Position,_rowid",
            [company_id, item_id], position_limit, position_offset,
        )
        allocations = self._payment_allocations(company_id, "p._rowid", item_id, payment_limit, payment_offset)
        totals = self.database.query(
            "SELECT count(*) AS entry_count,"
            "coalesce(sum(zp.BetragZahlFW),0) AS BetragZahlFW,coalesce(sum(zp.BetragZahlSW),0) AS BetragZahlSW,"
            "coalesce(sum(zp.BetragMindFW),0) AS BetragMindFW,coalesce(sum(zp.BetragMindSW),0) AS BetragMindSW "
            + PAYMENT_ALLOCATION_FROM + "WHERE zp.Firma_id=? AND p._rowid=?",
            [company_id, item_id], 1,
        )
        recorded = dict(zip(totals["columns"], totals["rows"][0]))
        fields = ["BezahltFW", "BezahltSW", "MinderungFW", "MinderungSW"]
        allocated_fields = ["BetragZahlFW", "BetragZahlSW", "BetragMindFW", "BetragMindSW"]
        differences = [
            None if item[field] is None else Decimal(str(item[field])) - Decimal(str(recorded[allocated]))
            for field, allocated in zip(fields, allocated_fields)
        ]
        matches = None if any(value is None for value in differences) else all(value == 0 for value in differences)
        return {
            "item": _currency_amounts(_labels(header, "Art", OPEN_ITEM_TYPES), "POSTEN"),
            "positions": _currency_amounts(positions, "POSTENPOSITION"),
            "allocations": allocations,
            "allocation_totals": _currency_amounts(totals, "ZAHLUNGSPOSITION"),
            "reconciliation": {
                "matches": matches,
                "differences": _currency_amounts({"columns": fields, "rows": [differences]}, "POSTEN"),
                "basis": "Gespeicherte Zahlungs-/Minderungssummen minus alle verknüpften Zuordnungen, nicht nur diese Seite. Null ist nicht angegeben.",
            },
            "basis": [
                "Nur ausdrückliche Zahlungs-/Positions-/Posten-ID-Verknüpfungen derselben Firma; kein Abgleich anhand Referenznummern oder Beträgen.",
                "Vorzeichenbehaftete Zuordnungen umfassen negative Zahlungen und Gutschriften. Zahlungssummen können mehrere Posten betreffen.",
                "Zahlung_id im Zahlungsdetailwerkzeug verfolgen, um Rechnungen/Gutschriften derselben Zahlung zu sehen; gemeinsame Zugehörigkeit ist keine eindeutige Rechnung-Gutschrift-Paarung.",
                "FW/SW-Werte sowie Posten- und Zahlungswährungen bleiben getrennt; keine Wechselkurse werden abgeleitet.",
                "Enthält ausgeglichene Posten und ausdrücklich angeforderte Entwürfe. Historie des Datenbankstands, kein rekonstruierter Stichtagssaldo.",
            ],
        }

    def payments(self, company_id, address_id=None, date_from=None, date_to=None,
                 search="", limit=100, offset=0):
        _integer(company_id, "firma_id")
        where, bindings = ["Firma_id=?"], [company_id]
        if address_id is not None:
            _integer(address_id, "adresse_id")
            where.append("Adress_id=?")
            bindings.append(address_id)
        _dates(where, bindings, "Datum", date_from, date_to)
        where.append("instr(lower(coalesce(ReNr,'') || ' ' || coalesce(BuText,'') || ' ' || coalesce(Referenz,'')),lower(?))>0")
        bindings.append(search)
        result = self._page(
            "SELECT _rowid,Firma_id,Datum,Art,Adress_id,Buchung_id,PKonto,FKonto,ReNr,BuText,Referenz,"
            "Waehrung,GesamtZahlFW,GesamtZahlSW,GesamtMindFW,GesamtMindSW FROM ZAHLUNG WHERE "
            + " AND ".join(where) + " ORDER BY Datum,_rowid",
            bindings, limit, offset,
        )
        return _currency_amounts(result, "ZAHLUNG")

    def payment(self, company_id, payment_id, limit=100, offset=0):
        _integer(company_id, "firma_id")
        _integer(payment_id, "zahlung_id")
        header = self.database.query("SELECT * FROM ZAHLUNG WHERE Firma_id=? AND _rowid=?", [company_id, payment_id], 1)
        if not header["rows"]:
            if header["truncated"]:
                raise Abfragegrenze("Zahlungskopf überschreitet das Ausgabelimit; mit einer SQL-Abfrage weniger Spalten auswählen")
            raise ParameterFehler("Zahlung in dieser Firma nicht gefunden")
        return {
            "payment": _currency_amounts(header, "ZAHLUNG"),
            "allocations": self._payment_allocations(company_id, "z._rowid", payment_id, limit, offset),
            "basis": [
                "Kopfbeträge sind vollständige Zahlungssummen, kein jeder verknüpften Rechnung zurechenbarer Betrag.",
                "Alle verknüpften Rechnungen und Gutschriften werden über IDs derselben Firma angezeigt; negative Zuordnungen und Ausgleiche mit Gesamtsumme null bleiben erhalten.",
                "Ein gemeinsamer Ausgleich belegt weder eine eindeutige Rechnung-Gutschrift-Paarung noch eine Banküberweisung.",
                "Zuordnungsbeträge in FW/SW sowie Posten- und Zahlungswährungen bleiben getrennt; keine Währungsumrechnung.",
            ],
        }

    def open_items(self, company_id, side="receivable", address_id=None, limit=100, offset=0, include_settled=False,
                   date_from=None, date_to=None):
        _integer(company_id, "firma_id")
        if side not in {"receivable", "payable", "all"}:
            raise ParameterFehler("seite muss Forderungen, Verbindlichkeiten oder alle auswählen")
        if not isinstance(include_settled, bool):
            raise ParameterFehler("ausgeglichene_einbeziehen muss ein Wahrheitswert sein")
        where, bindings = ["Firma_id = ?", "coalesce(Entwurf,0) = 0"], [company_id]
        if not include_settled:
            where.append("OffenFW <> 0")
        if side != "all":
            where.append("Art IN (0,1)" if side == "receivable" else "Art IN (2,3)")
        if address_id is not None:
            _integer(address_id, "adresse_id")
            where.append("Adress_id = ?")
            bindings.append(address_id)
        _dates(where, bindings, "Datum", date_from, date_to)
        result = self._page("SELECT _rowid, Firma_id, Art, Adress_id, ReNr, Datum, PKonto, BuText, Waehrung, GesamtBruttoFW, BezahltFW, MinderungFW, OffenFW, GesamtBruttoSW, BezahltSW, MinderungSW, OffenSW FROM POSTEN WHERE " + " AND ".join(where) + " ORDER BY Datum, _rowid", bindings, limit, offset)
        return _currency_amounts(_labels(result, "Art", OPEN_ITEM_TYPES), "POSTEN")
