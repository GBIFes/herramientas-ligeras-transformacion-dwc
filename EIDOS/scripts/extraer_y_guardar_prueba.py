from pathlib import Path
import sqlite3
import requests

from bs4 import BeautifulSoup


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

TAXONID = 11276

BASE_DIR = Path(
    r"C:\Users\Javier Estrada\Documents\GitHub\herramientas-ligeras-transformacion-dwc\EIDOS"
)

DB = BASE_DIR / "data" / "especies_legales.sqlite"


# ==========================================================
# DESCARGAR HTML
# ==========================================================

url = (
    "https://iepnb.gob.es/"
    "areas-tematicas/"
    "especies-silvestres/"
    f"eidos/{TAXONID}"
)

print(url)

r = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=60
)

print("HTTP:", r.status_code)

soup = BeautifulSoup(
    r.text,
    "html.parser"
)

tablas = soup.find_all("table")

print("Tablas:", len(tablas))


# ==========================================================
# NOMBRES COMUNES
# ==========================================================

tabla = tablas[0]

filas = tabla.find_all("tr")

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    DELETE FROM nombres_comunes
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
        INSERT INTO nombres_comunes(
            taxonid,
            idioma,
            nombre
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

print("Nombres comunes guardados.")