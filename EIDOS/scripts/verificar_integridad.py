"""
verificar_integridad.py

Comprueba la integridad de la base EIDOS.

Verifica:

- Taxones totales
- Taxones enriquecidos
- Taxones pendientes
- Registros huérfanos
- Registros duplicados

Uso:

    python verificar_integridad.py
"""

from modulos.conexion import (
    conectar
)


# ==========================================================
# CONTADOR
# ==========================================================

def contar(sql):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(sql)

    valor = cur.fetchone()[0]

    conn.close()

    return valor


# ==========================================================
# DUPLICADOS
# ==========================================================

def contar_duplicados(
    tabla
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM (

            SELECT
                taxonid

            FROM {tabla}

            GROUP BY taxonid

            HAVING COUNT(*) > 1

        )
        """
    )

    total = cur.fetchone()[0]

    conn.close()

    return total


# ==========================================================
# HUÉRFANOS
# ==========================================================

def contar_huerfanos(
    tabla
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT COUNT(*)

        FROM {tabla}

        WHERE taxonid NOT IN (

            SELECT taxonid
            FROM especies
            WHERE taxonid IS NOT NULL

        )
        """
    )

    total = cur.fetchone()[0]

    conn.close()

    return total


# ==========================================================
# INFORME
# ==========================================================

def main():

    total_taxones = contar(
        """
        SELECT COUNT(*)
        FROM especies
        WHERE taxonid IS NOT NULL
        """
    )

    enriquecidos = contar(
        """
        SELECT COUNT(*)
        FROM control_enriquecimiento
        WHERE
            generales = 1
            AND nombres = 1
            AND conservacion = 1
            AND colecciones = 1
            AND estado_legal = 1
            AND bibliografia = 1
        """
    )

    pendientes = (
        total_taxones -
        enriquecidos
    )

    print()
    print("=" * 60)
    print("EIDOS - INFORME DE INTEGRIDAD")
    print("=" * 60)

    print()
    print(
        f"Taxones totales: "
        f"{total_taxones:,}"
    )

    print(
        f"Enriquecidos: "
        f"{enriquecidos:,}"
    )

    print(
        f"Pendientes: "
        f"{pendientes:,}"
    )

    tablas = [

        "nombres_comunes",
        "estado_conservacion",
        "estado_legal",
        "colecciones_catalogos",
        "bibliografia"

    ]

    print()
    print("=" * 60)
    print("HUÉRFANOS")
    print("=" * 60)

    for tabla in tablas:

        print(
            f"{tabla}: "
            f"{contar_huerfanos(tabla):,}"
        )

    print()
    print("=" * 60)
    print("DUPLICADOS")
    print("=" * 60)

    for tabla in tablas:

        print(
            f"{tabla}: "
            f"{contar_duplicados(tabla):,}"
        )

    print()


if __name__ == "__main__":

    main()