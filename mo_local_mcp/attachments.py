"""Nur gespeicherte Anhangsbytes lesen; Links und Kompression niemals ausführen."""

import base64

from .business import _integer
from .errors import Abfragegrenze, ParameterFehler
from .masters import _search


MAX_BYTES = 128 * 1024
BASIS = [
    'Nur lokale Datenbankinhalte. Linkwerte werden weder geöffnet noch als Dateipfad gelesen.',
    'Source, Source_id und Art sind Rohwerte. Eine Zuordnung zu Buchungen wird nicht angenommen.',
    'Ausgabe enthält rohe Speicherbytes, kein bestätigtes Dateiformat. Kompression wird nicht entpackt.',
    'Chunkreihenfolge: Position, _rowid. Die Positionsbasis und die Bedeutung von Groesse sind nicht verifiziert. Auch passende Größen beweisen keine Dateiintegrität.',
]


_LIST = """
SELECT 'item' AS Speicher,'ATTACHMENTITEM' AS Herkunftstabelle,
       a._rowid,a.Firma_id,a.Name,a.Art,a.Source,a.Source_id,a.Link,
       a.Groesse,a.Compressed,a.Hinzugefuegt,a.Notizen,a.Bezeichnung,
       a.Gesperrt,a.ParentDate,a.Email_Anhang,a.Vorlage,a.ERechnung,
       a.EmbeddedFileNames,
       (SELECT coalesce(sum(length(c.Chunk)),0) FROM ATTACHMENTCHUNK c
        WHERE c.Firma_id=a.Firma_id AND c.AttachmentItem_id=a._rowid) AS Gespeicherte_Bytes,
       (SELECT count(*) FROM ATTACHMENTCHUNK c
        WHERE c.Firma_id=a.Firma_id AND c.AttachmentItem_id=a._rowid) AS Chunks,
       NULL AS Zuordnungen,
       CASE WHEN coalesce(a.Link,'')='' THEN 'Kein Link' ELSE 'Nicht geöffnet' END AS Linkstatus
FROM ATTACHMENTITEM a WHERE a.Firma_id=?
UNION ALL
SELECT 'legacy','ATTACHMENT',a._rowid,a.Firma_id,a.Name,NULL,a.Source,a.Source_id,
       NULL,NULL,NULL,NULL,a.Comment,NULL,NULL,NULL,NULL,NULL,NULL,NULL,
       length(a.Data),NULL,NULL,'Kein Link'
FROM ATTACHMENT a WHERE a.Firma_id=?
UNION ALL
SELECT 'alias','ATTACHMENTALIAS',a._rowid,a.Firma_id,a.Name,a.Art,NULL,NULL,
       NULL,a.Groesse,NULL,a.Hinzugefuegt,a.Notizen,NULL,NULL,NULL,NULL,NULL,NULL,NULL,
       length(a.Data),NULL,
       (SELECT count(*) FROM ATTACHMENTALIAS_ART r
        WHERE r.Firma_id=a.Firma_id AND r.AttachmentAlias_id=a._rowid),'Kein Link'
FROM ATTACHMENTALIAS a WHERE a.Firma_id=?
"""


def list_attachments(reader, company_id, search='', limit=100, offset=0):
    """Alle drei Speicherarten ohne BLOBs oder aufgelöste Links auflisten."""
    _integer(company_id, 'firma_id')
    _integer(offset, 'versatz', 0)
    if not isinstance(search, str):
        raise ParameterFehler('suche muss Text sein')
    columns = ('_rowid', 'Name', 'Bezeichnung', 'Notizen', 'Source', 'Source_id', 'Link')
    sql = 'SELECT * FROM (' + _LIST + ') WHERE ' + _search(columns)
    bindings = [company_id] * 3 + [search] * len(columns)
    total = reader.database.query('SELECT count(*) FROM (' + sql + ')', bindings, 1)
    result = reader._page(sql + ' ORDER BY Speicher,_rowid', bindings, limit, offset)
    result['gesamtzahl'] = total['rows'][0][0]
    result['basis'] = list(BASIS)
    return result


def _one(database, sql, bindings):
    result = database.query(sql, bindings, 1)
    if result['truncated']:
        raise Abfragegrenze('Anhangsmetadaten überschreiten die Ausgabegrenze')
    return dict(zip(result['columns'], result['rows'][0])) if result['rows'] else {}



def read_attachment(reader, company_id, attachment_id, storage='item', offset=0, length=65536):
    """Einen begrenzten Bytebereich ohne Dateizugriff oder Entpacken zurückgeben."""
    _integer(company_id, 'firma_id')
    _integer(attachment_id, 'anhang_id')
    _integer(offset, 'byteversatz', 0)
    _integer(length, 'bytelaenge')
    if length > MAX_BYTES:
        raise Abfragegrenze('bytelaenge darf höchstens 131072 betragen')
    if not isinstance(storage, str) or storage not in {'item', 'legacy', 'alias'}:
        raise ParameterFehler('speicher muss item, legacy oder alias sein')
    database = reader.database
    table = {'item': 'ATTACHMENTITEM', 'legacy': 'ATTACHMENT', 'alias': 'ATTACHMENTALIAS'}[storage]
    fields = {
        'item': 'Name,Groesse,Compressed,Link',
        'legacy': 'Name,NULL AS Groesse,NULL AS Compressed,NULL AS Link',
        'alias': 'Name,Groesse,NULL AS Compressed,NULL AS Link',
    }[storage]
    header = _one(database, f'SELECT {fields} FROM {table} WHERE Firma_id=? AND _rowid=?',
                  [company_id, attachment_id])
    if not header:
        raise ParameterFehler('Anhang in dieser Firma nicht gefunden')
    issues = []
    metadata = {}
    if storage == 'item':
        metadata = _one(database, '''SELECT count(*) AS Anzahl,
            coalesce(sum(length(Chunk)),0) AS Bytes,
            count(DISTINCT Position) AS Positionen,min(Position) AS Erste,max(Position) AS Letzte,
            coalesce(sum(CASE WHEN typeof(Position)!='integer' OR Position<0 THEN 1 ELSE 0 END),0) AS Ungueltige_Positionen,
            coalesce(sum(CASE WHEN typeof(Chunk)!='blob' THEN 1 ELSE 0 END),0) AS Ungueltige_BLOBs
            FROM ATTACHMENTCHUNK WHERE Firma_id=? AND AttachmentItem_id=?''',
            [company_id, attachment_id])
        total = int(metadata['Bytes'])
        if not metadata['Anzahl']:
            issues.append('Keine gespeicherten Chunks')
        if metadata['Ungueltige_Positionen']:
            issues.append('Fehlende oder ungültige Chunkpositionen')
        if metadata['Anzahl'] != metadata['Positionen']:
            issues.append('Fehlende oder mehrdeutige Chunkpositionen')
        if metadata['Ungueltige_BLOBs']:
            issues.append('Fehlende oder nicht-binäre Chunkinhalte')
        if not metadata['Ungueltige_Positionen'] and metadata['Anzahl']:
            if int(metadata['Letzte']) - int(metadata['Erste']) + 1 != metadata['Positionen']:
                issues.append('Lücken in den Chunkpositionen')
            if int(metadata['Erste']) > 1:
                issues.append('Möglicherweise fehlender Anfang: erste Chunkposition größer als 1')
        # Das Fenster enthält nur Längen. Erst überlappende Bytebereiche werden gelesen.
        result = database.query('''WITH laengen AS MATERIALIZED (
            SELECT _rowid,Position,coalesce(length(Chunk),0) AS n,typeof(Chunk) AS typ
            FROM ATTACHMENTCHUNK WHERE Firma_id=? AND AttachmentItem_id=?
        ), teile AS (
            SELECT _rowid,Position,n,typ,
                   coalesce(sum(n) OVER (
                       ORDER BY Position,_rowid ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) AS start
            FROM laengen
        ) SELECT _rowid,start,n FROM teile
          WHERE start<? AND start+n>? AND typ='blob'
          ORDER BY Position,_rowid''',
            [company_id, attachment_id, offset + length, offset], 500)
        parts = []
        for row_id, start, size in result['rows']:
            start, size = int(start), int(size)
            first = max(offset, start)
            amount = min(start + size, offset + length) - first
            parts.append(database.read_blob('ATTACHMENTCHUNK', 'Chunk', company_id,
                                            int(row_id), first - start, amount))
        data = b''.join(parts)
        limited = result['truncated']
    else:
        metadata = _one(database, f'''SELECT length(Data) AS Bytes,typeof(Data) AS Typ
            FROM {table} WHERE Firma_id=? AND _rowid=?''', [company_id, attachment_id])
        total = int(metadata['Bytes'] or 0)
        if metadata['Typ'] != 'blob':
            issues.append('Fehlender oder nicht-binärer Anhangsinhalt')
            data = b''
        else:
            amount = min(length, max(0, total - offset))
            data = database.read_blob(table, 'Data', company_id, attachment_id, offset, amount) if amount else b''
        limited = False
    if header['Groesse'] is not None and str(header['Groesse']) != str(total):
        issues.append('Groesse weicht von der gespeicherten Bytelänge ab; Größeneinheit nicht verifiziert')
    compression = header['Compressed']
    if storage == 'item' and compression != 0:
        issues.append('Kompression unbekannt oder gesetzt; ausschließlich rohe Speicherbytes')
    if len(data) != min(length, max(0, total - offset)) and not limited:
        issues.append('Bytebereich nicht vollständig lesbar')
    # Bei beschädigten Nicht-BLOB-Teilen ist kein verlässlicher Fortsetzungsversatz ableitbar.
    unreadable = bool(metadata.get('Ungueltige_BLOBs', 0)) or metadata.get('Typ', 'blob') != 'blob'
    next_offset = offset + len(data) if data and offset + len(data) < total and not unreadable else None
    return {
        'speicher': storage, 'herkunftstabelle': table, 'firma_id': company_id,
        'anhang_id': attachment_id, 'name': header['Name'],
        'linkstatus': 'Nicht geöffnet' if header['Link'] else 'Kein Link',
        'compressed_roh': compression, 'format': 'Rohe gespeicherte Bytes; Dateiformat nicht geprüft',
        'gespeicherte_bytes': total, 'groesse_roh': header['Groesse'],
        'byteversatz': offset, 'angeforderte_bytes': length, 'gelieferte_bytes': len(data),
        'inhalt_base64': base64.b64encode(data).decode('ascii'),
        'weitere_bytes': offset + len(data) < total, 'naechster_byteversatz': next_offset,
        'abfrage_gekuerzt': limited, 'chunkmetadaten': metadata,
        'status': 'Auffälligkeiten' if issues else 'Speicherbytes gelesen; Integrität nicht bestätigt',
        'auffaelligkeiten': issues, 'basis': list(BASIS),
    }
