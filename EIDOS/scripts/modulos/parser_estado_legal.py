"""
parser_estado_legal.py

Extracción del estado legal.
Tabla EIDOS nº 5.
"""

def extraer_estado_legal(tablas):

    resultado = []

    if len(tablas) < 5:
        return resultado

    tabla = tablas[4]

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

        if len(columnas) != 4:
            continue

        resultado.append(

            {
                "estado_legal":
                    columnas[0],

                "coleccion_catalogo":
                    columnas[1],

                "norma":
                    columnas[2],

                "ambito_aplicacion":
                    columnas[3]
            }

        )

    return resultado