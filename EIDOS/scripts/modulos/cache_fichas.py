"""
cache_fichas.py

Gestión de caché local de fichas EIDOS.

Permite:

- Guardar HTML descargado
- Recuperar HTML local
- Comprobar existencia
- Evitar descargas repetidas
"""

from pathlib import Path

from modulos.config import (
    BASE_DIR
)


# ==========================================================
# DIRECTORIO
# ==========================================================

CACHE_DIR = (
    BASE_DIR /
    "data" /
    "cache"
)

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================================
# RUTA HTML
# ==========================================================

def ruta_html(
    taxonid
):

    return (
        CACHE_DIR /
        f"{int(float(taxonid))}.html"
    )


# ==========================================================
# EXISTE
# ==========================================================

def existe_html(
    taxonid
):

    return ruta_html(
        taxonid
    ).exists()


# ==========================================================
# GUARDAR
# ==========================================================

def guardar_html(
    taxonid,
    html
):

    fichero = ruta_html(
        taxonid
    )

    fichero.write_text(
        html,
        encoding="utf-8"
    )

    return fichero


# ==========================================================
# LEER
# ==========================================================

def leer_html(
    taxonid
):

    fichero = ruta_html(
        taxonid
    )

    if not fichero.exists():

        return None

    return fichero.read_text(
        encoding="utf-8"
    )


# ==========================================================
# ELIMINAR
# ==========================================================

def eliminar_html(
    taxonid
):

    fichero = ruta_html(
        taxonid
    )

    if fichero.exists():

        fichero.unlink()


# ==========================================================
# CONTADOR
# ==========================================================

def total_cache():

    return len(
        list(
            CACHE_DIR.glob(
                "*.html"
            )
        )
    )


# ==========================================================
# LIMPIEZA COMPLETA
# ==========================================================

def vaciar_cache():

    total = 0

    for fichero in CACHE_DIR.glob(
        "*.html"
    ):

        fichero.unlink()

        total += 1

    return total