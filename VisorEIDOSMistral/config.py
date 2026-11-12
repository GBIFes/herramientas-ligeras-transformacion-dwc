"""
config.py
=========
Configuraciones globales y sesiones robustas para la interacción con EIDOS.
"""

import os
import platform
import subprocess

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# API REST oficial del IEPNB
BASE_URL_API = "https://pro.iepnb.gob.es/api/especie"

# Portal web de consulta (fichas de taxón)
BASE_URL = "https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos"

REQUEST_TIMEOUT = 120

# Endpoints por categoría (sintaxis PostgREST) usados por matrix_fetcher.py
CATEGORY_ENDPOINTS = {
    "LESRPE": "v_estadolegal?iddataset=eq.12",
    "CEEA_EN": "v_estadolegal?iddataset=eq.12&estadolegal=ilike.*En peligro*",
    "CEEA_VU": "v_estadolegal?iddataset=eq.12&estadolegal=ilike.*Vulnerable*",
    "Invasoras UE": "v_estadolegal?iddataset=eq.38",
}

# Mapeo de idioma (nombre en EIDOS) -> código ISO 639-1
IDIOMA_CODIGO = {
    "castellano": "es", "español": "es", "espanol": "es",
    "catalán": "ca", "catalan": "ca", "valenciano": "ca", "mallorquín": "ca",
    "euskera": "eu", "vasco": "eu",
    "gallego": "gl", "galego": "gl",
    "inglés": "en", "english": "en",
    "francés": "fr", "francais": "fr",
    "portugués": "pt", "portugues": "pt",
    "italiano": "it",
    "alemán": "de", "aleman": "de",
    "altoaragonés": "es",
}


def codigo_idioma(idioma_raw: str) -> str:
    """Traduce el nombre de idioma de EIDOS a código ISO 639-1."""
    texto = (idioma_raw or "").strip().lower()
    for nombre, codigo in IDIOMA_CODIGO.items():
        if nombre in texto:
            return codigo
    return "es"


def crear_sesion_robusta():
    """Crea una sesión HTTP con reintentos automáticos y cabeceras estándar."""
    session = requests.Session()
    retries = Retry(
        total=4,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session


def abrir_archivo_sistema(ruta):
    """Abre un archivo con la aplicación predeterminada del sistema."""
    try:
        if platform.system() == "Windows":
            os.startfile(ruta)
        elif platform.system() == "Darwin":
            subprocess.call(["open", ruta])
        else:
            subprocess.call(["xdg-open", ruta])
    except Exception as e:
        print(f"No se pudo abrir el archivo automáticamente: {e}")