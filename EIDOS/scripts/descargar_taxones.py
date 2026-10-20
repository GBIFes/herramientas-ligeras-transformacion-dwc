"""
descargar_taxones.py

Descarga de EIDOS los taxones con interés normativo:

- Especies no nativas
- Especies con código CITES
- Especies con código EURING
- Especies con código Red Natura 2000

y los almacena en SQLite.

Autor: Javier Estrada
"""

from pathlib import Path
from datetime import datetime
import sqlite3

import pandas as pd
import requests


# ==========================================================
# Rutas
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB = DATA_DIR / "especies_legales.sqlite"

print(f"\nBase de datos destino:\n{DB}\n")


# ==========================================================
# URL EIDOS
# ==========================================================

URL = (
    "https://iepnb.gob.es/api/especie/v_taxonomia"
    "?select="
    "taxonid,"
    "scientificnameid,"
    "name,"
    "kingdom,"
    "phylum,"
    "class,"
    "ordertaxonomic,"
    "family,"
    "genus,"
    "origen,"
    "citescode,"
    "euniscode,"
    "euringcode,"
    "rednaturacode"
)

print("Descargando datos de EIDOS...")

respuesta = requests.get(
    URL,
    headers={"Accept": "application/json"},
    timeout=300
)

respuesta.raise_for_status()

datos = respuesta.json()

df = pd.DataFrame(datos)
# Convertir taxonid a entero

df["taxonid"] = (
    pd.to_numeric(
        df["taxonid"],
        errors="coerce"
    )
    .astype("Int64")
)

print(f"Registros recibidos: {len(df):,}")


# ==========================================================
# Filtrado
# ==========================================================

filtro = (
    (df["origen"] == "Especie no nativa") |
    (df["citescode"].notna()) |
    (df["euringcode"].notna()) |
    (df["rednaturacode"].notna())
)

df = df[filtro].copy()

print(f"Registros seleccionados: {len(df):,}")


# ==========================================================
# Campos calculados
# ==========================================================

df["es_no_nativa"] = (
    df["origen"] == "Especie no nativa"
).astype(int)

df["es_cites"] = (
    df["citescode"].notna()
).astype(int)

df["es_euring"] = (
    df["euringcode"].notna()
).astype(int)

df["es_red_natura"] = (
    df["rednaturacode"].notna()
).astype(int)

df["fecha_descarga"] = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)


# ==========================================================
# Renombrado campos
# ==========================================================

df.rename(
    columns={
        "name": "nombre",
        "kingdom": "reino",
        "class": "clase",
        "family": "familia",
        "genus": "genero",
        "ordertaxonomic": "orden_taxonomico"
    },
    inplace=True
)

df["uri"] = (
    "https://iepnb.gob.es/areas-tematicas/"
    "especies-silvestres/eidos/"
    + df["taxonid"].astype(str)
)


# ==========================================================
# Guardado SQLite
# ==========================================================

conn = sqlite3.connect(DB)

df.to_sql(
    "especies",
    conn,
    if_exists="replace",
    index=False
)

conn.commit()

cur = conn.cursor()

cur.execute(
    "CREATE INDEX IF NOT EXISTS idx_taxonid ON especies(taxonid)"
)

cur.execute(
    "CREATE INDEX IF NOT EXISTS idx_nombre ON especies(nombre)"
)

conn.commit()

cur.execute(
    "SELECT COUNT(*) FROM especies"
)

total = cur.fetchone()[0]

conn.close()


print("\nCarga terminada correctamente.")
print(f"Taxones almacenados: {total:,}")
print(f"SQLite: {DB}")