"""
analizar_taxonomia.py

Analiza la composición taxonómica
de la selección EIDOS.

Obtiene:

- Ámbitos
- Grupos taxonómicos
- Reinos
- Filos
- Clases
- Órdenes
- Familias
- Géneros

- Frecuencias
- Taxones sin enriquecer

Uso:

    python analizar_taxonomia.py
"""

from modulos.conexion import (
    conectar
)


# ==========================================================
# DISTINTOS
# ==========================================================

def obtener_distintos(campo):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT DISTINCT
            {campo}

        FROM especies

        WHERE

            {campo} IS NOT NULL

            AND TRIM({campo}) <> ''

        ORDER BY {campo}
        """
    )

    valores = [
        fila[0]
        for fila in cur.fetchall()
    ]

    conn.close()

    return valores


# ==========================================================
# FRECUENCIAS
# ==========================================================

def obtener_frecuencias(
    campo,
    limite=50
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT

            {campo},

            COUNT(*)

        FROM especies

        WHERE

            {campo} IS NOT NULL

            AND TRIM({campo}) <> ''

        GROUP BY {campo}

        ORDER BY 2 DESC

        LIMIT ?
        """,
        (limite,)
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# SIN ENRIQUECER
# ==========================================================

def taxones_sin_grupo():

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            taxonid,
            nombre

        FROM especies

        WHERE

            grupo_taxonomico IS NULL

            OR TRIM(
                grupo_taxonomico
            ) = ''

        ORDER BY taxonid

        LIMIT 25
        """
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# SALIDA
# ==========================================================

def mostrar_lista(
    titulo,
    valores
):

    print()
    print("=" * 80)
    print(titulo)
    print("=" * 80)

    for valor in valores:

        print(valor)

    print()

    print(
        f"Total: {len(valores)}"
    )


def mostrar_frecuencias(
    titulo,
    filas
):

    print()
    print("=" * 80)
    print(titulo)
    print("=" * 80)

    for nombre, total in filas:

        print(
            f"{total:>6} | "
            f"{nombre}"
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    mostrar_lista(
        "ÁMBITOS",
        obtener_distintos(
            "ambito"
        )
    )

    mostrar_lista(
        "GRUPOS TAXONÓMICOS",
        obtener_distintos(
            "grupo_taxonomico"
        )
    )

    mostrar_frecuencias(
        "CLASES MÁS FRECUENTES",
        obtener_frecuencias(
            "clase"
        )
    )

    mostrar_frecuencias(
        "ÓRDENES MÁS FRECUENTES",
        obtener_frecuencias(
            "orden_taxonomico"
        )
    )

    mostrar_frecuencias(
        "FAMILIAS MÁS FRECUENTES",
        obtener_frecuencias(
            "familia"
        )
    )

    mostrar_frecuencias(
        "GÉNEROS MÁS FRECUENTES",
        obtener_frecuencias(
            "genero"
        )
    )

    pendientes = (
        taxones_sin_grupo()
    )

    print()
    print("=" * 80)
    print("TAXONES SIN ENRIQUECER")
    print("=" * 80)

    for taxonid, nombre in pendientes:

        print(
            f"{int(taxonid)} | "
            f"{nombre}"
        )

    print()
    print(
        f"Mostrados: "
        f"{len(pendientes)}"
    )


if __name__ == "__main__":

    main()