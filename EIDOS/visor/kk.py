from pathlib import Path
import sqlite3

DB = Path(
    r"C:\Users\Javier Estrada\Documents\GitHub\herramientas-ligeras-transformacion-dwc\EIDOS\data\especies_legales.sqlite"
)

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    "PRAGMA table_info(especies)"
)

for fila in cur.fetchall():
    print(fila)

conn.close()