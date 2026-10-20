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

tablas = soup.find_all("table")

# ==========================================================
# TABLA 5
# ESTADO LEGAL
# ==========================================================

tabla = tablas[4]

filas = tabla.find_all("tr")

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    DELETE
    FROM estado_legal
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

    if len(columnas) != 4:
        continue

    estado_legal = columnas[0]
    coleccion_catalogo = columnas[1]
    norma = columnas[2]
    ambito_aplicacion = columnas[3]

    cur.execute(
        """
        INSERT INTO estado_legal(

            taxonid,
            estado_legal,
            coleccion_catalogo,
            norma,
            ambito_aplicacion

        )
        VALUES(
            ?, ?, ?, ?, ?
        )
        """,
        (
            TAXONID,
            estado_legal,
            coleccion_catalogo,
            norma,
            ambito_aplicacion
        )
    )

conn.commit()

conn.close()

print(
    "Estado legal guardado."
)