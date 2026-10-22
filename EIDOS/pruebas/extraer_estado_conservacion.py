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

tablas = soup.find_all(
    "table"
)

# ==========================================================
# TABLA 3
# ESTADO CONSERVACION
# ==========================================================

tabla = tablas[2]

filas = tabla.find_all(
    "tr"
)

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    DELETE
    FROM estado_conservacion
    WHERE taxonid = ?
    """,
    (TAXONID,)
)

for fila in filas[1:]:

    columnas = [

        td.get_text(
            strip=True
        )
        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    if len(columnas) != 5:
        continue

    autoridad = columnas[0]
    aplicacion = columnas[1]
    conservacion = columnas[2]
    anio = columnas[3]
    criterios = columnas[4]

    cur.execute(
        """
        INSERT INTO estado_conservacion(

            taxonid,
            autoridad,
            aplicacion,
            conservacion,
            anio,
            criterios

        )
        VALUES(
            ?, ?, ?, ?, ?, ?
        )
        """,
        (
            TAXONID,
            autoridad,
            aplicacion,
            conservacion,
            anio,
            criterios
        )
    )

conn.commit()

conn.close()

print(
    "Estado de conservación guardado."
)