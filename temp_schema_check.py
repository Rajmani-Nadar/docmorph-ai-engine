import sqlite3
import json
conn = sqlite3.connect('docmorph.db')
tables = ['users', 'jobs', 'downloads', 'uploaded_files', 'extraction_results']
result = {}
for t in tables:
    try:
        cols = conn.execute(f'PRAGMA table_info({t});').fetchall()
        result[t] = cols
    except Exception as e:
        result[t] = str(e)
conn.close()
print(json.dumps(result, default=str, indent=2))
