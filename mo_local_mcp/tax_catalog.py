"""Aus dem Datenbankstand abgeleitete Steuermetadaten; keine bestätigten Connect-Zuordnungen."""

TAX_CATALOG = {
    'ELSTERMELDUNG': {
        'meaning': 'Gespeicherte Steuermeldungen; deutsche UVA-Datensätze liegen hier, nicht bei den Jahreserklärungen',
        'mapping_basis': 'Nur lesend untersuchtes Quellschema und dekodierte Meldungsdatensätze; aus dem Datenbankstand abgeleitet, keine bestätigte Connect-Zuordnung',
        'tools': ['get_vat_return'],
        'fields': {'Firma_id': 'Zugehörige Firma', 'Verfahren': 'Beobachtete UVA-Identität: ElsterAnmeldung',
                   'DatenArt': 'Beobachtete UVA-Identität: Umsatzsteuer-Voranmeldung',
                   'Jahr': 'Jahr, wird mit dem angefragten Jahr abgeglichen', 'ZeitraumCode': 'Unveränderter Zeitraumcode; ältere JJMM- und neuere MM-Formate kommen vor',
                   'DatumVon': 'Exakter Beginn des Zeitraums einschließlich dieses Tages', 'DatumBis': 'Exaktes Ende des Zeitraums einschließlich dieses Tages',
                   'Kennzahlen': 'Gepackte Liste abwechselnder Kennzahl-/Wertzeichenketten mit sechsstelligen Zeichenzählern, kein XML',
                   'Berechnungsart': 'Unveränderte Berechnungs-/Versionseinstellung der Meldung; IST/SOLL wird nicht abgeleitet',
                   'Status': 'Unveränderter Meldungsstatus, kein Übermittlungsnachweis', 'Land': 'Deutsche Meldungen verwenden den Ländercode 1',
                   'Meldung_id': 'Unveränderter gespeicherter Übermittlungsverweis'},
        'notes': ['Mehrere Meldungen desselben exakten Zeitraums erfordern eine ausdrückliche meldung_id; die neueste gilt nicht automatisch als endgültig.',
                  'Unbekannte Kennzahlen und Kennzeichen behalten ihre Rohwerte; gespeicherte Beträge werden nicht aus aktuellen Buchungen neu berechnet.'],
    },
    'ELSTERMELDUNG_NT': {
        'meaning': 'Neuerer Steuermeldungscontainer, im untersuchten Datenbankstand leer',
        'mapping_basis': 'Nur das Datenbankschema; TaxReport-Serialisierung und Meldungsidentität sind nicht nachgewiesen',
        'tools': ['get_vat_return'],
        'fields': {'Firma_id': 'Zugehörige Firma', 'Method': 'Unveränderte Methode', 'DataType': 'Unveränderte Datenart',
                   'Process': 'Unverändertes Verfahren', 'TaxReport': 'Nicht zugeordnete serialisierte Meldung',
                   'DateFrom': 'Gespeicherter Zeitraumstart', 'DateTo': 'Gespeichertes Zeitraumende',
                   'CalculationMethod': 'Unveränderte Berechnungseinstellung', 'Report_id': 'Unveränderter Meldungsverweis'},
        'notes': ['Passende neuere Datensätze verhindern eine ersatzweise Rekonstruktion, statt stillschweigend übergangen zu werden.'],
    },
    'STEUERERKLAERUNG': {
        'meaning': 'Gespeicherte Erklärungen einschließlich jährlicher Umsatzsteuererklärung; nicht automatisch eine Voranmeldung',
        'mapping_basis': 'Nur lesend untersuchtes Quellschema und XML-Strukturen; aus dem Datenbankstand abgeleitet, keine bestätigte Connect-Zuordnung',
        'fields': {'Firma_id': 'Zugehörige Firma', 'Datenart': 'Erklärungsidentität', 'DatumVon': 'Zeitraumstart',
                   'DatumBis': 'Zeitraumende', 'Jahr': 'Jahr', 'Kennzahlen': 'Beobachtetes XML mit Knoten description/content/row/field',
                   'Berechnungsart': 'Unveränderte Einstellung', 'Verfahren': 'Unverändertes Verfahren', 'Meldung_id': 'Unveränderter Übermittlungsverweis'},
        'notes': ['Das XML einer Jahreserklärung ersetzt keine UVA; die Feldidentität ist unterschiedlich.'],
    },
}
