"""
crear_bd.py

Crea la base de datos SQLite inicial
para el proyecto EIDOS.

Uso:

    python crear_bd.py
"""

from modulos.conexion import (
    conectar
)


# ==========================================================
# TABLA PRINCIPAL
# ==========================================================

SQL_ESPECIES = """
CREATE TABLE IF NOT EXISTS especies(

    taxonid REAL,

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

    es_no_nativa INTEGER,

    es_cites INTEGER,

    es_euring INTEGER,

    es_red_natura INTEGER,

    fecha_descarga TEXT,

    ambito TEXT,

    grupo_taxonomico TEXT,

    especie_epiteto TEXT,

    autor_taxon TEXT,

    fecha_enriquecimiento TEXT
)
"""


# ==========================================================
# CREACIÓN
# ==========================================================

def crear_tablas():

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        SQL_ESPECIES
    )

    conn.commit()

    conn.close()


# ==========================================================
# MAIN
# ==========================================================

def main():

    crear_tablas()

    print()

    print(
        "Tabla especies creada."
    )

    print()


if __name__ == "__main__":

    main()