"""
obtener_ficha.py

Descarga una ficha EIDOS y devuelve
el objeto BeautifulSoup listo para ser procesado.
"""

import requests

from bs4 import BeautifulSoup

from modulos.config import (
    EIDOS_BASE_URL,
    HEADERS,
    TIMEOUT
)


# ==========================================================
# URL
# ==========================================================

def construir_url(taxonid):

    return (
        f"{EIDOS_BASE_URL}/"
        f"{int(float(taxonid))}"
    )


# ==========================================================
# DESCARGA
# ==========================================================

def descargar_html(taxonid):

    url = construir_url(
        taxonid
    )

    respuesta = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    respuesta.raise_for_status()

    return respuesta.text


# ==========================================================
# SOUP
# ==========================================================

def obtener_soup(taxonid):

    html = descargar_html(
        taxonid
    )

    return BeautifulSoup(
        html,
        "html.parser"
    )


# ==========================================================
# TABLAS
# ==========================================================

def obtener_tablas(taxonid):

    soup = obtener_soup(
        taxonid
    )

    return soup.find_all(
        "table"
    )


# ==========================================================
# TEXTO COMPLETO
# ==========================================================

def obtener_texto(taxonid):

    soup = obtener_soup(
        taxonid
    )

    return soup.get_text(
        "\n",
        strip=True
    )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    taxonid = 11276

    print(
        construir_url(
            taxonid
        )
    )

    tablas = obtener_tablas(
        taxonid
    )

    print()

    print(
        "Tablas encontradas:",
        len(tablas)
    )