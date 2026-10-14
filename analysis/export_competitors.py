"""Export saved Semrush reports; no network requests."""
import csv
import io
import json
from pathlib import Path

root = Path(__file__).resolve().parent / 'data'
p = json.loads((root / 'competitors_de_raw.json').read_text(encoding='utf-8'))
for section, name, keys in [('serps', 'competitor_serps_de.csv', ['query']),
                            ('competitors', 'competitor_keywords_de.csv', ['target', 'brand'])]:
    rows = []
    for item in p[section]:
        result = item['result']
        report = result.get('value', {}).get('structuredContent', {})
        if result['status'] != 'fulfilled' or not report.get('data'):
            continue
        for row in csv.DictReader(io.StringIO(report['data']), delimiter=';'):
            rows.append({**{k:item[k] for k in keys}, **row,
                         'database':'de', 'retrieved_at_utc':p['retrieved_at'], 'source':'Semrush MCP'})
    with (root / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=';')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for k,v in row.items()})
    print(name, len(rows))
