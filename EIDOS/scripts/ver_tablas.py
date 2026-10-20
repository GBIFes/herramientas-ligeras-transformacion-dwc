from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent

DB = BASE_DIR / "data" / "especies_legales.sqlite"

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name
""")

for fila in cur.fetchall():

    print(fila[0])

conn.close()
