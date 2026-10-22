"""
enriquecer_taxon.py

Orquestador de enriquecimiento
de un único taxón EIDOS.

Ejemplo:

    python enriquecer_taxon.py 11276
"""

import sys
import sqlite3

from modulos.config import DB

from modulos.obtener_ficha import (
    obtener_soup,
    obtener_tablas
)

from modulos.parser_generales import (
    extraer_generales
)

from modulos.parser_nombres import (
    extraer_nombres
)

from modulos.parser_conservacion import (
    extraer_conservacion
)

from modulos.parser_colecciones import (
    extraer_colecciones
)

from modulos.parser_estado_legal import (
    extraer_estado_legal
)

from modulos.parser_bibliografia import (
    extraer_bibliografia
)

from modulos.control import (
    marcar_generales,
    marcar_nombres,
    marcar_conservacion,
    marcar_colecciones,
    marcar_estado_legal,
    marcar_bibliografia,
    registrar_error
)


# ==========================================================
# SQLITE
# ==========================================================

def conectar():

    return sqlite3.connect(DB)


# ==========================================================
# GENERALES
# ==========================================================

def guardar_generales(
    taxonid,
    datos
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE especies
        SET

            ambito = ?,

            grupo_taxonomico = ?,

            reino = COALESCE(?, reino),

            phylum = COALESCE(?, phylum),

            clase = COALESCE(?, clase),

            orden_taxonomico =
                COALESCE(
                    ?,
                    orden_taxonomico
                ),

            familia =
                COALESCE(
                    ?,
                    familia
                ),

            genero =
                COALESCE(
                    ?,
                    genero
                ),

            especie_epiteto = ?,

            autor_taxon = ?,

            fecha_enriquecimiento =
                datetime('now')

        WHERE taxonid = ?
        """,
        (
            datos["ambito"],
            datos["grupo_taxonomico"],

            datos["reino"],
            datos["filo"],
            datos["clase"],
            datos["orden"],
            datos["familia"],
            datos["genero"],

            datos["especie"],
            datos["autor"],

            taxonid
        )
    )

    conn.commit()

    conn.close()

    marcar_generales(
        taxonid
    )
# ==========================================================
# NOMBRES COMUNES
# ==========================================================

def guardar_nombres(
    taxonid,
    datos
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE
        FROM nombres_comunes
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    for fila in datos:

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
                taxonid,
                fila["idioma"],
                fila["nombre"]
            )
        )

    conn.commit()

    conn.close()

    marcar_nombres(
        taxonid
    )


# ==========================================================
# CONSERVACIÓN
# ==========================================================

def guardar_conservacion(
    taxonid,
    datos
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE
        FROM estado_conservacion
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    for fila in datos:

        cur.execute(
            """
            INSERT INTO
            estado_conservacion(

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
                taxonid,

                fila["autoridad"],
                fila["aplicacion"],
                fila["conservacion"],
                fila["anio"],
                fila["criterios"]
            )
        )

    conn.commit()

    conn.close()

    marcar_conservacion(
        taxonid
    )
# ==========================================================
# COLECCIONES
# ==========================================================

def guardar_colecciones(
    taxonid,
    datos
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE
        FROM colecciones_catalogos
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    for fila in datos:

        cur.execute(
            """
            INSERT INTO
            colecciones_catalogos(

                taxonid,
                coleccion_catalogo,
                nombre_catalogo

            )
            VALUES(
                ?, ?, ?
            )
            """,
            (
                taxonid,
                fila["coleccion_catalogo"],
                fila["nombre_catalogo"]
            )
        )

    conn.commit()

    conn.close()

    marcar_colecciones(
        taxonid
    )


# ==========================================================
# ESTADO LEGAL
# ==========================================================

def guardar_estado_legal(
    taxonid,
    datos
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE
        FROM estado_legal
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    for fila in datos:

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
                taxonid,

                fila["estado_legal"],

                fila["coleccion_catalogo"],

                fila["norma"],

                fila["ambito_aplicacion"]
            )
        )

    conn.commit()

    conn.close()

    marcar_estado_legal(
        taxonid
    )
# ==========================================================
# BIBLIOGRAFÍA
# ==========================================================

def guardar_bibliografia(
    taxonid,
    datos
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE
        FROM bibliografia
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    for fila in datos:

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
                taxonid,

                fila["id_ref"],
                fila["referencia"],
                fila["url"]
            )
        )

    conn.commit()

    conn.close()

    marcar_bibliografia(
        taxonid
    )


# ==========================================================
# ENRIQUECER TAXÓN
# ==========================================================

def enriquecer_taxon(
    taxonid
):

    try:

        soup = obtener_soup(
            taxonid
        )

        tablas = obtener_tablas(
            taxonid
        )

        guardar_generales(
            taxonid,
            extraer_generales(
                soup
            )
        )

        guardar_nombres(
            taxonid,
            extraer_nombres(
                tablas
            )
        )

        guardar_conservacion(
            taxonid,
            extraer_conservacion(
                tablas
            )
        )

        guardar_colecciones(
            taxonid,
            extraer_colecciones(
                tablas
            )
        )

        guardar_estado_legal(
            taxonid,
            extraer_estado_legal(
                tablas
            )
        )

        guardar_bibliografia(
            taxonid,
            extraer_bibliografia(
                tablas
            )
        )

        print(
            f"OK {taxonid}"
        )

    except Exception as e:

        registrar_error(
            taxonid,
            str(e)
        )

        print(
            f"ERROR {taxonid}: {e}"
        )


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "Uso:"
        )

        print(
            "python enriquecer_taxon.py 11276"
        )

        raise SystemExit

    enriquecer_taxon(
        float(sys.argv[1])
    )
