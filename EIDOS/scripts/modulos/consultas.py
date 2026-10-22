"""
consultas.py

Consultas reutilizables sobre la
base de datos EIDOS.
"""

from modulos.conexion import (
    conectar
)


# ==========================================================
# TAXÓN POR ID
# ==========================================================

def obtener_taxon(
    taxonid
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM especies
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    fila = cur.fetchone()

    conn.close()

    return fila


# ==========================================================
# NOMBRE CIENTÍFICO
# ==========================================================

def obtener_nombre(
    taxonid
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT nombre
        FROM especies
        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    fila = cur.fetchone()

    conn.close()

    if fila is None:
        return None

    return fila[0]


# ==========================================================
# BÚSQUEDA POR NOMBRE
# ==========================================================

def buscar_nombre(
    texto,
    limite=50
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            taxonid,
            nombre

        FROM especies

        WHERE
            UPPER(nombre)
            LIKE UPPER(?)

        ORDER BY nombre

        LIMIT ?
        """,
        (
            f"%{texto}%",
            limite
        )
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# TAXONES POR GRUPO
# ==========================================================

def taxones_por_grupo(
    grupo
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            taxonid,
            nombre

        FROM especies

        WHERE
            grupo_taxonomico = ?

        ORDER BY nombre
        """,
        (grupo,)
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# TAXONES POR ESTADO LEGAL
# ==========================================================

def taxones_por_estado_legal(
    estado
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT

            e.taxonid,
            e.nombre

        FROM especies e

        JOIN estado_legal l

            ON e.taxonid =
               l.taxonid

        WHERE
            l.estado_legal = ?

        ORDER BY e.nombre
        """,
        (estado,)
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# TAXONES POR CATEGORÍA UICN
# ==========================================================

def taxones_por_categoria(
    categoria
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT

            e.taxonid,
            e.nombre

        FROM especies e

        JOIN estado_conservacion c

            ON e.taxonid =
               c.taxonid

        WHERE

            c.aplicacion = ?

        ORDER BY e.nombre
        """,
        (categoria,)
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# NOMBRES COMUNES
# ==========================================================

def nombres_comunes(
    taxonid
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            idioma,
            nombre

        FROM nombres_comunes

        WHERE taxonid = ?

        ORDER BY idioma
        """,
        (taxonid,)
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# BIBLIOGRAFÍA
# ==========================================================

def bibliografia(
    taxonid
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            id_ref,
            referencia,
            url

        FROM bibliografia

        WHERE taxonid = ?

        ORDER BY id_ref
        """,
        (taxonid,)
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado