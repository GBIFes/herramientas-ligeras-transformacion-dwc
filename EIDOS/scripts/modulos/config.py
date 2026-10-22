"""
config.py

Configuración común del proyecto EIDOS.
"""

from pathlib import Path


# ==========================================================
# RUTAS
# ==========================================================

BASE_DIR = Path(
    __file__
).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"

DB = DATA_DIR / "especies_legales.sqlite"

LOG_DIR = BASE_DIR / "logs"


# ==========================================================
# RED
# ==========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64)"
    )
}

TIMEOUT = 60


# ==========================================================
# EIDOS
# ==========================================================

EIDOS_BASE_URL = (
    "https://iepnb.gob.es/"
    "areas-tematicas/"
    "especies-silvestres/"
    "eidos"
)