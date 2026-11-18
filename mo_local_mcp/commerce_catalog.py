"""Fachzuordnungen für Einkauf, Artikel und Projekte ohne Datenbankzugriff."""

PURCHASE_TYPES = {
    101: "Bestellanfrage", 102: "Bestellung", 103: "Wareneingang",
    104: "Eingangsrechnung", 105: "Lieferantengutschrift", 106: "Rücksendung",
    107: "Stornierung",
}
ARTICLE_TYPES = {1: "Artikel", 2: "Leistung"}
ARTICLE_STATUSES = {0: "Verkauf und Einkauf", 1: "Einkauf", 2: "Verkauf", 3: "kein Status"}
PROJECT_STATUSES = {
    0: "", 1: "Akquise", 2: "Beauftragt", 3: "Vorbereitung",
    4: "In Arbeit", 5: "Abrechnen", 6: "Abgeschlossen",
}

COMMERCE_MONEY_FIELDS = {
    "BESTELLUNG": {
        base + suffix
        for base in ("PosGesamtNetto", "GesamtRabatt", "GesamtNetto", "GesamtSteuer", "GesamtBrutto")
        for suffix in ("FW", "SW")
    },
    "BESTELLPOSITION": {
        base + suffix
        for base in ("EinzelPreisNetto", "EinzelPreisBrutto", "GesamtPreisNetto", "GesamtPreisBrutto")
        for suffix in ("FW", "SW")
    } | {"PreisProStkEK", "PreisProStkVK", "PreisEKNetto", "PreisEKBrutto"},
    "ARTIKEL": {"PreisProStkEK", "PreisProStkVK"} | {
        base + suffix
        for base in ("EKPreis", "EKAufwBetrag", "EKGesamt", "VKMargeBetrag", "VKGesamt")
        for suffix in ("Netto", "Steuer", "Brutto")
    },
}

_REFERENCE = "https://github.com/tkaufmann/monkeyoffice-api-docs/blob/main/docs/v22.1.1/endpoints/"
_BASIS = "Connect-Begriffe aus der Referenz v22.1.1; lokale Spaltenzuordnung aus dem Datenbankmetadatenschema abgeleitet, nicht gegen eine laufende Connect-API verifiziert. IDs sind lokale _rowid-Werte."

COMMERCE_CATALOG = {
    "BESTELLUNG": {
        "meaning": "Firmenbezogene Einkaufsbelege einschließlich Entwürfen",
        "mapping_basis": _BASIS,
        "reference": _REFERENCE + "einkaufsbelege.md",
        "api_structures": ["EinkaufbelegArt", "EinkaufbelegItem"],
        "api_fields": {"EinkaufbelegArt": "Art", "Einkaufbeleg_ID": "_rowid", "Adresse_ID": "Adress_id", "BestellNr": "BestellNr"},
        "tools": ["list_purchase_documents", "get_purchase_document"],
        "enums": {"Art": PURCHASE_TYPES},
        "fields": {"Entwurf": "Gespeichertes Entwurfskennzeichen; Liste schließt ungleich 0 standardmäßig aus, NULL bleibt erhalten", "Waehrung": "Gespeicherte Belegwährung für FW-Beträge", "Kurs": "Unveränderter Kurs", "Rabatt": "Unveränderter Rabattwert", "Buchung_Status": "Unveränderter lokaler Statuscode; kein abgeleiteter Zahlungsstatus"},
        "joins": ["BESTELLPOSITION.Bestell_id = BESTELLUNG._rowid UND gleiche Firma_id"],
        "units": {"money": "Hundertstel werden durch 100 geteilt; FW und SW bleiben getrennt", "Kurs/Rabatt": "Unveränderte Speicherwerte"},
        "limitations": ["Nur die Referenzcodes 101 bis 107 erhalten Art-Bezeichnungen. Andere lokale Codes bleiben unverändert und filterbar.", "Eine Eingangsrechnung beweist weder einen offenen Posten noch eine ausstehende Zahlung. SW wird nicht mit einer erfundenen Währung versehen."],
    },
    "BESTELLPOSITION": {
        "meaning": "Firmenbezogene Positionen eines Einkaufsbelegs",
        "mapping_basis": _BASIS,
        "reference": _REFERENCE + "einkaufsbelege.md",
        "api_structures": ["EinkaufbelegPositionArt"],
        "api_fields": {"EinkaufbelegPositionArt": "Art"},
        "tools": ["get_purchase_document"],
        "fields": {"Bestell_id": "Lokale ID des Einkaufsbelegs", "Menge": "Unveränderte Menge", "MengeNichtLieferbar": "Unveränderte nicht lieferbare Menge", "Rabatt": "Unveränderter Rabattwert", "SortNr": "Gespeicherte Sortierung vor Nummer und _rowid"},
        "joins": ["BESTELLPOSITION.Bestell_id = BESTELLUNG._rowid UND gleiche Firma_id"],
        "units": {"money": "Geldbeträge geteilt durch 100, ohne Rundung auf zwei Nachkommastellen", "Menge/Gewicht/Rabatt": "Unveränderte Speicherwerte"},
    },
    "ARTIKEL": {
        "meaning": "Firmenbezogene Artikel und Leistungen, auch gesperrte Stammsätze",
        "mapping_basis": _BASIS,
        "reference": _REFERENCE + "artikel-und-leistungen.md",
        "api_structures": ["Artikelart", "Artikelstatus", "ArtikelItem"],
        "api_fields": {"ArtikelArt": "Art", "ArtikelNr": "ArtikelNr", "Warengruppe": "Warengruppe"},
        "tools": ["list_articles"],
        "enums": {"Art": ARTICLE_TYPES, "Status": ARTICLE_STATUSES},
        "fields": {"Lagerartikel": "Gespeichertes Lagerartikelkennzeichen; kein verfügbarer Lagerbestand", "Warengruppe": "Gespeicherter Gruppenname; Gruppenfilter vergleicht exakt gemäß Spaltenkollation", "Gesperrt": "Gespeicherte Sperre; kein impliziter Ausschluss"},
        "units": {"money": "Preis- und Betragsfelder geteilt durch 100; zusätzliche Preisnachkommastellen bleiben erhalten", "Mengen/Gewichte/Prozente": "Unveränderte Speicherwerte"},
        "limitations": ["Die Tabelle enthält keine Währung. Artikelpreise erhalten daher weder EUR noch eine andere angenommene Währung.", "nur_lagerartikel wählt Lagerartikel=1, nicht einen berechneten positiven Lagerbestand.", "Art 1/2 und Status 0 bis 3 sind aus der Connect-Referenz abgeleitete lokale Zuordnungen; unbekannte Codes und NULL bleiben erhalten."],
    },
    "PROJEKT": {
        "meaning": "Firmenbezogene Projektstammdaten aller Statuswerte",
        "mapping_basis": _BASIS,
        "reference": _REFERENCE + "projekte.md",
        "api_structures": ["ProjektStatus", "ProjektItem"],
        "api_fields": {"ProjektNr": "ProjektNr", "ProjektStatus": "Status", "DatumVon": "DatumStart", "DatumBis": "DatumEnde"},
        "tools": ["list_projects"],
        "enums": {"Status": PROJECT_STATUSES},
        "fields": {"DatumStart": "Gespeicherter Projektbeginn", "DatumEnde": "Gespeichertes Projektende"},
        "limitations": ["Statusbezeichnungen sind aus der Connect-Referenz abgeleitet. Unbekannte Codes und NULL bleiben erhalten."],
    },
}
