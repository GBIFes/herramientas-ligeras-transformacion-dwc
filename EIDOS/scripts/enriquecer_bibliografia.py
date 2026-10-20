from pathlib import Path
import sqlite3
import requests
import re

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
# DESCARGA
# ==========================================================

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

tablas = soup.find_all(
    "table"
)

tabla = tablas[5]

filas = tabla.find_all(
    "tr"
)

# ==========================================================
# SQLITE
# ==========================================================

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    DELETE
    FROM bibliografia
    WHERE taxonid = ?
    """,
    (TAXONID,)
)

# ==========================================================
# EXTRACCIÓN
# ==========================================================

for fila in filas[1:]:

    columnas = [

        td.get_text(
            strip=True
        )

        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    if len(columnas) < 3:
        continue

    id_ref = columnas[0]

    referencia = columnas[1]

    url_texto = columnas[2]

    # ----------------------------------------
    # extraer URL real
    # ----------------------------------------

    urls = re.findall(
        r"https?://[^\s\"<>]+",
        url_texto
    )

    url_ref = ""

    if urls:
        url_ref = urls[0]

    cur.execute(
        """
        INSERT INTO bibliografia(

            taxonid,
            id_ref,
            referencia,
            url

        )
        VALUES(
            ?, ?, ?, ?
        )
        """,
        (
            TAXONID,
            id_ref,
            referencia,
            url_ref
        )
    )

conn.commit()

conn.close()

print(
    "Bibliografía guardada."
)