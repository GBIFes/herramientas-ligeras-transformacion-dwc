"""
conexion.py

Funciones comunes de acceso a SQLite.
"""

import sqlite3

from modulos.config import DB


# ==========================================================
# CONEXIÓN
# ==========================================================

def conectar():

    return sqlite3.connect(DB)


# ==========================================================
# CURSOR
# ==========================================================

def obtener_cursor():

    conn = conectar()

    cur = conn.cursor()

    return conn, cur


# ==========================================================
# COMMIT Y CIERRE
# ==========================================================

def cerrar(
    conn,
    commit=True
):

    if commit:
        conn.commit()

    conn.close()


# ==========================================================
# EXISTE TABLA
# ==========================================================

def existe_tabla(nombre_tabla):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (nombre_tabla,)
    )

    existe = (
        cur.fetchone()[0] > 0
    )

    conn.close()

    return existe


# ==========================================================
# EXISTE COLUMNA
# ==========================================================

def existe_columna(
    tabla,
    columna
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"PRAGMA table_info({tabla})"
    )

    columnas = [
        fila[1]
        for fila in cur.fetchall()
    ]

    conn.close()

    return columna in columnas


# ==========================================================
# OBTENER TAXON
# ==========================================================

def obtener_taxon(taxonid):

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
# LISTA DE TAXONES
# ==========================================================

def obtener_taxones(
    limite=None
):

    conn = conectar()

    cur = conn.cursor()

    sql = """
    SELECT taxonid
    FROM especies
    WHERE taxonid IS NOT NULL
    ORDER BY taxonid
    """

    if limite is not None:

        sql += f"\nLIMIT {int(limite)}"

    cur.execute(sql)

    resultado = [
        fila[0]
        for fila in cur.fetchall()
    ]

    conn.close()

    return resultado