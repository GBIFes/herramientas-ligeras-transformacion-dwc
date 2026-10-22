"""
analizar_conservacion.py

Analiza los estados de conservación
almacenados en SQLite.

Obtiene:

- Autoridades distintas
- Categorías distintas
- Ámbitos distintos
- Distribución de categorías
- Distribución por autoridad
- Distribución por ámbito

Uso:

    python analizar_conservacion.py
"""

from modulos.conexion import (
    conectar
)


# ==========================================================
# DISTINTOS
# ==========================================================

def obtener_distintos(
    campo
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT DISTINCT
            {campo}

        FROM estado_conservacion

        WHERE

            {campo} IS NOT NULL

            AND TRIM({campo}) <> ''

        ORDER BY {campo}
        """
    )

    resultado = [
        fila[0]
        for fila in cur.fetchall()
    ]

    conn.close()

    return resultado


# ==========================================================
# FRECUENCIAS
# ==========================================================

def obtener_frecuencias(
    campo
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT

            {campo},

            COUNT(
                DISTINCT taxonid
            )

        FROM estado_conservacion

        WHERE

            {campo} IS NOT NULL

            AND TRIM({campo}) <> ''

        GROUP BY {campo}

        ORDER BY 2 DESC
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

    for valor, total in filas:

        print(
            f"{total:>6} | {valor}"
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    mostrar_lista(
        "AUTORIDADES",
        obtener_distintos(
            "autoridad"
        )
    )

    mostrar_lista(
        "CATEGORÍAS",
        obtener_distintos(
            "aplicacion"
        )
    )

    mostrar_lista(
        "ÁMBITOS",
        obtener_distintos(
            "conservacion"
        )
    )

    mostrar_frecuencias(
        "ESPECIES POR AUTORIDAD",
        obtener_frecuencias(
            "autoridad"
        )
    )

    mostrar_frecuencias(
        "ESPECIES POR CATEGORÍA",
        obtener_frecuencias(
            "aplicacion"
        )
    )

    mostrar_frecuencias(
        "ESPECIES POR ÁMBITO",
        obtener_frecuencias(
            "conservacion"
        )
    )


if __name__ == "__main__":

    main()