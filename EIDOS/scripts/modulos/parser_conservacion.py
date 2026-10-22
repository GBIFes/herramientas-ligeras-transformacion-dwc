"""
parser_conservacion.py

Extracción de estado de conservación.
Tabla EIDOS nº 3.
"""

def extraer_conservacion(tablas):

    resultado = []

    if len(tablas) < 3:
        return resultado

    tabla = tablas[2]

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

        if len(columnas) != 5:
            continue

        resultado.append(

            {
                "autoridad": columnas[0],
                "aplicacion": columnas[1],
                "conservacion": columnas[2],
                "anio": columnas[3],
                "criterios": columnas[4]
            }

        )

    return resultado