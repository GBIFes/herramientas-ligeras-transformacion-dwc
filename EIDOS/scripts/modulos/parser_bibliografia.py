"""
parser_bibliografia.py

Extracción de bibliografía.
Tabla EIDOS nº 6.
"""

import re


def extraer_bibliografia(tablas):

    resultado = []

    if len(tablas) < 6:
        return resultado

    tabla = tablas[5]

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

        if len(columnas) < 3:
            continue

        id_ref = columnas[0]

        referencia = columnas[1]

        url_texto = columnas[2]

        urls = re.findall(
            r"https?://[^\s\"<>]+",
            url_texto
        )

        url = ""

        if urls:
            url = urls[0]

        resultado.append(

            {
                "id_ref":
                    id_ref,

                "referencia":
                    referencia,

                "url":
                    url
            }

        )

    return resultado