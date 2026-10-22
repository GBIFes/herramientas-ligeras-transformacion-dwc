"""
analizar_normativa.py

Explota la información jurídica almacenada
en estado_legal para identificar:

- Estados legales distintos
- Normas más frecuentes
- Ámbitos de aplicación
- Colecciones jurídicas
- Número de especies por norma

Uso:

    python analizar_normativa.py
"""

from modulos.conexion import (
    conectar
)


# ==========================================================
# LISTADOS
# ==========================================================

def obtener_distintos(
    tabla,
    campo
):

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        f"""
        SELECT DISTINCT
            {campo}

        FROM {tabla}

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

def obtener_frecuencias_normas():

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            norma,

            COUNT(
                DISTINCT taxonid
            ) AS especies

        FROM estado_legal

        WHERE

            norma IS NOT NULL

            AND TRIM(norma) <> ''

        GROUP BY norma

        ORDER BY especies DESC
        """
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# FRECUENCIAS ESTADOS
# ==========================================================

def obtener_frecuencias_estados():

    conn = conectar()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT

            estado_legal,

            COUNT(
                DISTINCT taxonid
            )

        FROM estado_legal

        WHERE

            estado_legal IS NOT NULL

            AND TRIM(
                estado_legal
            ) <> ''

        GROUP BY estado_legal

        ORDER BY 2 DESC
        """
    )

    resultado = cur.fetchall()

    conn.close()

    return resultado


# ==========================================================
# MOSTRAR
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
            f"{total:>6} | {nombre}"
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    estados = obtener_distintos(
        "estado_legal",
        "estado_legal"
    )

    ambitos = obtener_distintos(
        "estado_legal",
        "ambito_aplicacion"
    )

    colecciones = obtener_distintos(
        "estado_legal",
        "coleccion_catalogo"
    )

    mostrar_lista(
        "ESTADOS LEGALES",
        estados
    )

    mostrar_lista(
        "ÁMBITOS DE APLICACIÓN",
        ambitos
    )

    mostrar_lista(
        "COLECCIONES JURÍDICAS",
        colecciones
    )

    mostrar_frecuencias(
        "ESPECIES POR ESTADO LEGAL",
        obtener_frecuencias_estados()
    )

    mostrar_frecuencias(
        "ESPECIES POR NORMA",
        obtener_frecuencias_normas()
    )


if __name__ == "__main__":

    main()