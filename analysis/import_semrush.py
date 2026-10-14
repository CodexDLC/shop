"""Import saved Semrush MCP reports without further API requests."""
import csv
import io
import json
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parent / 'data'
payload = json.loads((root / 'semrush_de_raw.json').read_text(encoding='utf-8'))
metrics = {}
for report in payload['reports']:
    for row in csv.DictReader(io.StringIO(report['data']), delimiter=';'):
        metrics[row['Keyword'].casefold()] = row
with sqlite3.connect(root / 'queries.sqlite3') as db:
    db.execute('''CREATE TABLE IF NOT EXISTS keyword_metrics (
        phrase TEXT NOT NULL, database_code TEXT NOT NULL, retrieved_at TEXT NOT NULL,
        status TEXT NOT NULL, volume INTEGER, difficulty REAL, cpc REAL,
        ad_competition REAL, trend TEXT, source TEXT NOT NULL,
        PRIMARY KEY(phrase, database_code, retrieved_at))''')
    output = []
    for (phrase,) in db.execute('SELECT phrase FROM suggestions ORDER BY phrase').fetchall():
        row = metrics.get(phrase.casefold())
        values = (phrase, payload['database'], payload['retrieved_at'],
                  'available' if row else 'no_data',
                  int(row['Search Volume']) if row else None,
                  float(row['Keyword Difficulty Index']) if row else None,
                  float(row['CPC']) if row else None,
                  float(row['Competition']) if row else None,
                  row['Trends'] if row else None, payload['source'])
        db.execute('INSERT OR REPLACE INTO keyword_metrics VALUES (?,?,?,?,?,?,?,?,?,?)', values)
        output.append(values)
    output.sort(key=lambda r: (r[4] is None, -(r[4] or 0), r[0]))
    target = root / 'keywords_de_metrics.csv'
    with target.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(['query', 'database', 'retrieved_at_utc', 'status',
                         'monthly_searches_estimate', 'seo_difficulty', 'cpc',
                         'advertising_competition', 'trend', 'source'])
        for values in output:
            writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for v in values])
    available = sum(r[3] == 'available' for r in output)
    positive = sum(r[4] is not None and r[4] > 0 for r in output)
    print(f'Total: {len(output)}; available: {available}; positive: {positive}; no data: {len(output)-available}')
    print(target)
