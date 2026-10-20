"""
inicializar_estructura.py

Valida y amplía la estructura SQLite utilizada por EIDOS.

Puede ejecutarse tantas veces como sea necesario.

Autor: Javier Estrada
"""

from pathlib import Path
import sqlite3

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DB = BASE_DIR / "data" / "especies_legales.sqlite"

print()
print("Base:")
print(DB)

# ==========================================================
# CONEXIÓN
# ==========================================================

conn = sqlite3.connect(DB)

cur = conn.cursor()


# ==========================================================
# UTILIDADES
# ==========================================================

def existe_columna(tabla, columna):

    cur.execute(
        f"PRAGMA table_info({tabla})"
    )

    columnas = [
        fila[1]
        for fila in cur.fetchall()
    ]

    return columna in columnas


def crear_columna(
    tabla,
    columna,
    tipo
):

    if existe_columna(
        tabla,
        columna
    ):
        return

    sql = (
        f"ALTER TABLE {tabla} "
        f"ADD COLUMN {columna} {tipo}"
    )

    cur.execute(sql)

    print(
        f"Columna creada: "
        f"{tabla}.{columna}"
    )


# ==========================================================
# AMPLIACIONES TABLA ESPECIES
# ==========================================================

crear_columna(
    "especies",
    "ambito",
    "TEXT"
)

crear_columna(
    "especies",
    "grupo_taxonomico",
    "TEXT"
)

crear_columna(
    "especies",
    "especie_epiteto",
    "TEXT"
)

crear_columna(
    "especies",
    "autor_taxon",
    "TEXT"
)

crear_columna(
    "especies",
    "fecha_enriquecimiento",
    "TEXT"
)


# ==========================================================
# NOMBRES COMUNES
# ==========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS nombres_comunes (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid REAL,

    idioma TEXT,

    nombre TEXT
)
""")


# ==========================================================
# ESTADO CONSERVACION
# ==========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS estado_conservacion (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid REAL,

    autoridad TEXT,

    aplicacion TEXT,

    conservacion TEXT,

    anio TEXT,

    criterios TEXT
)
""")


# ==========================================================
# ESTADO LEGAL
# ==========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS estado_legal (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid REAL,

    estado_legal TEXT,

    coleccion_catalogo TEXT,

    norma TEXT,

    ambito_aplicacion TEXT
)
""")


# ==========================================================
# COLECCIONES / CATÁLOGOS
# ==========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS colecciones_catalogos (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid REAL,

    coleccion_catalogo TEXT,

    nombre_catalogo TEXT
)
""")


# ==========================================================
# BIBLIOGRAFÍA
# ==========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS bibliografia (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    taxonid REAL,

    id_ref TEXT,

    referencia TEXT,

    url TEXT
)
""")


# ==========================================================
# CONTROL DE ENRIQUECIMIENTO
# ==========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS control_enriquecimiento (

    taxonid REAL PRIMARY KEY,

    fecha TEXT,

    generales INTEGER DEFAULT 0,

    nombres INTEGER DEFAULT 0,

    conservacion INTEGER DEFAULT 0,

    colecciones INTEGER DEFAULT 0,

    estado_legal INTEGER DEFAULT 0,

    bibliografia INTEGER DEFAULT 0,

    error TEXT
)
""")


# ==========================================================
# INFORMACIÓN
# ==========================================================

cur.execute("""
SELECT COUNT(*)
FROM especies
""")

total = cur.fetchone()[0]

print()
print(
    f"Taxones seleccionados: "
    f"{total:,}"
)

print()

cur.execute("""
SELECT COUNT(*)
FROM control_enriquecimiento
""")

procesados = cur.fetchone()[0]

print(
    f"Taxones enriquecidos: "
    f"{procesados:,}"
)

if total > 0:

    print()
    print(
        "La selección de taxones "
        "ya existe."
    )

    respuesta = input(
        "¿Desea sobreescribir la selección? (S/N): "
    )

    if respuesta.upper() == "S":

        print()
        print(
            "ATENCIÓN: aquí se llamaría "
            "al proceso de reconstrucción "
            "de la selección."
        )

# ==========================================================
# FINAL
# ==========================================================

conn.commit()
conn.close()

print()
print(
    "Estructura validada correctamente."
)