"""
parser_colecciones.py

Extracción de colecciones y catálogos.
Tabla EIDOS nº 4.
"""

def extraer_colecciones(tablas):

    resultado = []

    if len(tablas) < 4:
        return resultado

    tabla = tablas[3]

    filas = tabla.find_all(
        "tr"
    )

    for fila in filas[1:]:

        columnas = [

            td.get_text(
                strip=True
            )

            for td in fila.find_all(
                ["td", "th"]
            )
        ]

        if len(columnas) != 2:
            continue

        resultado.append(

            {
                "coleccion_catalogo":
                    columnas[0],

                "nombre_catalogo":
                    columnas[1]
            }

        )

    return resultado