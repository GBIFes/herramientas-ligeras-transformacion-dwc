"""
estadisticas_bd.py

Estadísticas generales de la base EIDOS.

Uso:

    python estadisticas_bd.py
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
# RESUMEN
# ==========================================================

def resumen():

    total_especies = contar(
        """
        SELECT COUNT(*)
        FROM especies
        """
    )

    nombres = contar(
        """
        SELECT COUNT(*)
        FROM nombres_comunes
        """
    )

    conservacion = contar(
        """
        SELECT COUNT(*)
        FROM estado_conservacion
        """
    )

    legal = contar(
        """
        SELECT COUNT(*)
        FROM estado_legal
        """
    )

    colecciones = contar(
        """
        SELECT COUNT(*)
        FROM colecciones_catalogos
        """
    )

    bibliografia = contar(
        """
        SELECT COUNT(*)
        FROM bibliografia
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

    return {
        "especies": total_especies,
        "nombres": nombres,
        "conservacion": conservacion,
        "legal": legal,
        "colecciones": colecciones,
        "bibliografia": bibliografia,
        "enriquecidos": enriquecidos
    }


# ==========================================================
# MAIN
# ==========================================================

def main():

    datos = resumen()

    print()
    print("=" * 60)
    print("EIDOS - ESTADÍSTICAS")
    print("=" * 60)

    print()

    print(
        f"Especies: "
        f"{datos['especies']:,}"
    )

    print(
        f"Nombres comunes: "
        f"{datos['nombres']:,}"
    )

    print(
        f"Estados conservación: "
        f"{datos['conservacion']:,}"
    )

    print(
        f"Estados legales: "
        f"{datos['legal']:,}"
    )

    print(
        f"Colecciones: "
        f"{datos['colecciones']:,}"
    )

    print(
        f"Bibliografía: "
        f"{datos['bibliografia']:,}"
    )

    print(
        f"Taxones enriquecidos: "
        f"{datos['enriquecidos']:,}"
    )

    print()


if __name__ == "__main__":

    main()