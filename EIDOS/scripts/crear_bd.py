import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

DB = DATA_DIR / "especies_legales.sqlite"

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS especies (

    taxonid INTEGER PRIMARY KEY,

    scientificnameid TEXT,

    nombre TEXT,

    reino TEXT,

    phylum TEXT,

    clase TEXT,

    orden_taxonomico TEXT,

    familia TEXT,

    genero TEXT,

    origen TEXT,

    citescode TEXT,

    euniscode TEXT,

    euringcode TEXT,

    rednaturacode TEXT,

    es_no_nativa INTEGER DEFAULT 0,

    es_cites INTEGER DEFAULT 0,

    es_euring INTEGER DEFAULT 0,

    es_red_natura INTEGER DEFAULT 0,

    fecha_descarga TEXT
)
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_nombre
ON especies(nombre)
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_taxonid
ON especies(taxonid)
""")

conn.commit()
conn.close()

print("Base creada correctamente.")