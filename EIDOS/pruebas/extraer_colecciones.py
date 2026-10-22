from pathlib import Path
import sqlite3
import requests

from bs4 import BeautifulSoup


TAXONID = 11276

BASE_DIR = Path(
    r"C:\Users\Javier Estrada\Documents\GitHub\herramientas-ligeras-transformacion-dwc\EIDOS"
)

DB = BASE_DIR / "data" / "especies_legales.sqlite"


url = (
    "https://iepnb.gob.es/"
    "areas-tematicas/"
    "especies-silvestres/"
    f"eidos/{TAXONID}"
)

r = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=60
)

soup = BeautifulSoup(
    r.text,
    "html.parser"
)

tablas = soup.find_all("table")

tabla = tablas[3]

filas = tabla.find_all("tr")

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    DELETE FROM colecciones_catalogos
    WHERE taxonid = ?
    """,
    (TAXONID,)
)

for fila in filas[1:]:

    columnas = [

        td.get_text(strip=True)

        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    if len(columnas) != 2:
        continue

    cur.execute(
        """
        INSERT INTO colecciones_catalogos(

            taxonid,
            coleccion_catalogo,
            nombre_catalogo

        )
        VALUES(
            ?, ?, ?
        )
        """,
        (
            TAXONID,
            columnas[0],
            columnas[1]
        )
    )

conn.commit()

conn.close()

print("Colecciones guardadas.")