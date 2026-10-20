"""
db.py

Acceso a la base SQLite de EIDOS Legal.

Autor: Javier Estrada
"""

from pathlib import Path
import sqlite3


# ==========================================================
# BASE DE DATOS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DB = BASE_DIR / "data" / "especies_legales.sqlite"


# ==========================================================
# CONEXIÓN
# ==========================================================

def conectar():
    return sqlite3.connect(DB)


# ==========================================================
# URI IEPNB
# ==========================================================

def construir_uri(taxonid):

    if taxonid is None:
        return ""

    return (
        "https://iepnb.gob.es/"
        "areas-tematicas/"
        "especies-silvestres/"
        f"eidos/{int(float(taxonid))}"
    )


# ==========================================================
# OBTENER REGISTROS
# ==========================================================

def obtener_registros(
    texto="",
    no_nativa=False,
    cites=False,
    euring=False,
    natura=False
):

    conn = conectar()

    sql = """
    SELECT
        taxonid,
        nombre,
        origen,
        es_no_nativa,
        es_cites,
        es_euring,
        es_red_natura
    FROM especies
    """

    condiciones = []
    parametros = []

    if texto:

        condiciones.append(
            "UPPER(nombre) LIKE UPPER(?)"
        )

        parametros.append(
            f"%{texto}%"
        )

    if no_nativa:
        condiciones.append(
            "es_no_nativa = 1"
        )

    if cites:
        condiciones.append(
            "es_cites = 1"
        )

    if euring:
        condiciones.append(
            "es_euring = 1"
        )

    if natura:
        condiciones.append(
            "es_red_natura = 1"
        )

    if condiciones:

        sql += " WHERE "

        sql += " AND ".join(
            condiciones
        )

    sql += """
    ORDER BY nombre
    """

    cur = conn.cursor()

    cur.execute(
        sql,
        parametros
    )

    registros = cur.fetchall()

    conn.close()

    return registros


# ==========================================================
# DETALLE DE UN TAXÓN
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
        (
            taxonid,
        )
    )

    fila = cur.fetchone()

    if fila is None:

        conn.close()

        return [], None

    columnas = [
        c[0]
        for c in cur.description
    ]

    conn.close()

    return columnas, fila


# ==========================================================
# ESTADÍSTICAS
# ==========================================================

def obtener_estadisticas():

    conn = conectar()

    cur = conn.cursor()

    resultado = {}

    consultas = {

        "total":
        """
        SELECT COUNT(*)
        FROM especies
        """,

        "no_nativas":
        """
        SELECT COUNT(*)
        FROM especies
        WHERE es_no_nativa = 1
        """,

        "cites":
        """
        SELECT COUNT(*)
        FROM especies
        WHERE es_cites = 1
        """,

        "euring":
        """
        SELECT COUNT(*)
        FROM especies
        WHERE es_euring = 1
        """,

        "red_natura":
        """
        SELECT COUNT(*)
        FROM especies
        WHERE es_red_natura = 1
        """
    }

    for clave, sql in consultas.items():

        cur.execute(sql)

        resultado[clave] = (
            cur.fetchone()[0]
        )

    conn.close()

    return resultado