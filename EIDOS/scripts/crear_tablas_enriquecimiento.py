from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent

DB = BASE_DIR / "data" / "especies_legales.sqlite"

conn = sqlite3.connect(DB)

cur = conn.cursor()

# =========================================
# NOMBRES COMUNES
# =========================================

cur.execute("""
CREATE TABLE IF NOT EXISTS nombres_comunes(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid INTEGER,

    idioma TEXT,

    nombre TEXT
)
""")

# =========================================
# ESTADO CONSERVACION
# =========================================

cur.execute("""
CREATE TABLE IF NOT EXISTS estado_conservacion(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid INTEGER,

    autoridad TEXT,

    aplicacion TEXT,

    conservacion TEXT,

    anio TEXT,

    criterios TEXT
)
""")

# =========================================
# ESTADO LEGAL
# =========================================

cur.execute("""
CREATE TABLE IF NOT EXISTS estado_legal(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid INTEGER,

    estado_legal TEXT,

    coleccion_catalogo TEXT,

    norma TEXT,

    ambito_aplicacion TEXT
)
""")

# =========================================
# COLECCIONES
# =========================================

cur.execute("""
CREATE TABLE IF NOT EXISTS colecciones_catalogos(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid INTEGER,

    coleccion_catalogo TEXT,

    nombre_catalogo TEXT
)
""")

conn.commit()

conn.close()

print("Tablas creadas correctamente.")
