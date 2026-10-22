"""
parser_generales.py

Extracción de:

- Ámbito
- Grupo taxonómico
- Reino
- Filo
- Clase
- Orden
- Familia
- Género
- Especie
- Autor
"""

def extraer_generales(soup):

    texto = soup.get_text(
        "\n",
        strip=True
    )

    lineas = [
        linea.strip()
        for linea in texto.splitlines()
        if linea.strip()
    ]

    resultado = {

        "ambito": None,
        "grupo_taxonomico": None,

        "reino": None,
        "filo": None,
        "clase": None,
        "orden": None,
        "familia": None,
        "genero": None,
        "especie": None,
        "autor": None
    }

    # =====================================================
    # ÁMBITO Y GRUPO
    # =====================================================

    for i, linea in enumerate(lineas):

        if linea == "Ámbito:":

            if i + 1 < len(lineas):

                resultado["ambito"] = (
                    lineas[i + 1]
                )

        elif linea == "Grupo Taxonómico":

            if i + 1 < len(lineas):

                resultado[
                    "grupo_taxonomico"
                ] = (
                    lineas[i + 1]
                )

    # =====================================================
    # TAXONOMÍA
    # =====================================================

    for li in soup.find_all("li"):

        texto_li = li.get_text(
            " ",
            strip=True
        )

        if texto_li.startswith(
            "Reino:"
        ):

            resultado["reino"] = (
                texto_li
                .replace(
                    "Reino:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "División o Filo:"
        ):

            resultado["filo"] = (
                texto_li
                .replace(
                    "División o Filo:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Filo:"
        ):

            resultado["filo"] = (
                texto_li
                .replace(
                    "Filo:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Clase:"
        ):

            resultado["clase"] = (
                texto_li
                .replace(
                    "Clase:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Orden:"
        ):

            resultado["orden"] = (
                texto_li
                .replace(
                    "Orden:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Familia:"
        ):

            resultado["familia"] = (
                texto_li
                .replace(
                    "Familia:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Género:"
        ):

            resultado["genero"] = (
                texto_li
                .replace(
                    "Género:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Especie:"
        ):

            resultado["especie"] = (
                texto_li
                .replace(
                    "Especie:",
                    ""
                )
                .strip()
            )

        elif texto_li.startswith(
            "Autor:"
        ):

            resultado["autor"] = (
                texto_li
                .replace(
                    "Autor:",
                    ""
                )
                .strip()
            )

    return resultado