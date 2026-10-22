from pathlib import Path
import sqlite3

BASE_DIR = Path(
    r"C:\Users\Javier Estrada\Documents\GitHub\herramientas-ligeras-transformacion-dwc\EIDOS"
)

DB = BASE_DIR / "data" / "especies_legales.sqlite"

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    SELECT
        idioma,
        nombre
    FROM nombres_comunes
    WHERE taxonid = 11276
    ORDER BY idioma
    """
)

for fila in cur.fetchall():

    print(fila)

conn.close()