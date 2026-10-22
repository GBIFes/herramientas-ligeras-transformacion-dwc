"""
parser_nombres.py

Extracción de nombres comunes.
Tabla EIDOS nº 1.
"""

def extraer_nombres(tablas):

    resultado = []

    if len(tablas) < 1:
        return resultado

    tabla = tablas[0]

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
                "idioma": columnas[0],
                "nombre": columnas[1]
            }

        )

    return resultado