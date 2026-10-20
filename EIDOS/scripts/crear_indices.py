from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent

DB = BASE_DIR / "data" / "especies_legales.sqlite"

conn = sqlite3.connect(DB)

cur = conn.cursor()

indices = [

    """
    CREATE INDEX IF NOT EXISTS
    idx_nc_taxonid

    ON nombres_comunes(taxonid)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_ec_taxonid

    ON estado_conservacion(taxonid)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_el_taxonid

    ON estado_legal(taxonid)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_cc_taxonid

    ON colecciones_catalogos(taxonid)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_bib_taxonid

    ON bibliografia(taxonid)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_ctrl_taxonid

    ON control_enriquecimiento(taxonid)
    """
]

for sql in indices:
    cur.execute(sql)

conn.commit()

conn.close()

print("Índices creados.")