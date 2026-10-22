"""
control.py

Funciones para controlar el progreso
del enriquecimiento de taxones.
"""

from datetime import datetime

from modulos.conexion import (
    conectar
)


# ==========================================================
# FECHA
# ==========================================================

def ahora():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ==========================================================
# ASEGURAR REGISTRO
# ==========================================================

def asegurar_taxon(taxonid):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE
        INTO control_enriquecimiento(

            taxonid,
            fecha

        )
        VALUES(
            ?, ?
        )
        """,
        (
            taxonid,
            ahora()
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# MARCAR GENERALES
# ==========================================================

def marcar_generales(taxonid):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            generales = 1,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# MARCAR NOMBRES
# ==========================================================

def marcar_nombres(taxonid):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            nombres = 1,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# MARCAR CONSERVACIÓN
# ==========================================================

def marcar_conservacion(taxonid):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            conservacion = 1,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# MARCAR COLECCIONES
# ==========================================================

def marcar_colecciones(taxonid):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            colecciones = 1,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()
# ==========================================================
# MARCAR ESTADO LEGAL
# ==========================================================

def marcar_estado_legal(taxonid):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            estado_legal = 1,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# MARCAR BIBLIOGRAFÍA
# ==========================================================

def marcar_bibliografia(taxonid):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            bibliografia = 1,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# REGISTRAR ERROR
# ==========================================================

def registrar_error(
    taxonid,
    mensaje
):

    asegurar_taxon(
        taxonid
    )

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE control_enriquecimiento
        SET

            error = ?,

            fecha = ?

        WHERE taxonid = ?
        """,
        (
            str(mensaje),
            ahora(),
            taxonid
        )
    )

    conn.commit()

    conn.close()


# ==========================================================
# COMPLETADO
# ==========================================================

def completado(taxonid):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            generales,
            nombres,
            conservacion,
            colecciones,
            estado_legal,
            bibliografia

        FROM control_enriquecimiento

        WHERE taxonid = ?
        """,
        (taxonid,)
    )

    fila = cur.fetchone()

    conn.close()

    if fila is None:
        return False

    return all(
        valor == 1
        for valor in fila
    )


# ==========================================================
# PENDIENTES
# ==========================================================

def pendientes():

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            taxonid
        FROM especies

        WHERE taxonid NOT IN (

            SELECT taxonid
            FROM control_enriquecimiento

            WHERE

                generales = 1
                AND nombres = 1
                AND conservacion = 1
                AND colecciones = 1
                AND estado_legal = 1
                AND bibliografia = 1
        )
        """
    )

    resultado = [
        fila[0]
        for fila in cur.fetchall()
    ]

    conn.close()

    return resultado