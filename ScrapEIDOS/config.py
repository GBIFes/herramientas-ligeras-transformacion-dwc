import os
import re
import csv
import platform
import subprocess
import webbrowser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd
import tkinter as tk

BASE_URL = "https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos"

IDIOMA_PAIS = {
    "Castellano": "ES", "Catalán": "ES", "Euskera": "ES", "Gallego": "ES",
    "Valenciano": "ES", "Mallorquín": "ES", "Altoaragonés": "ES", "Inglés": "GB",
    "Francés": "FR", "Portugués": "PT", "Italiano": "IT", "Alemán": "DE",
}

SEPARADOR_NOMBRES_REGEX = re.compile(r'\s*[;]\s*|\s*,\s+(?=[A-ZÁÉÍÓÚÑa-záéíóúñ])')

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
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

def detectar_codificacion(ruta):
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            with open(ruta, "r", encoding=enc) as f:
                f.read()
            return enc
        except:
            pass
    return "latin-1"

def detectar_dialect(ruta):
    encoding = detectar_codificacion(ruta)
    with open(ruta, "r", encoding=encoding, errors="ignore") as f:
        muestra = f.read(4096)
    posibles = [",", ";", "\t", "|"]
    try:
        dialect = csv.Sniffer().sniff(muestra, delimiters=posibles)
        return dialect
    except:
        conteos = {sep: muestra.count(sep) for sep in posibles}
        separador = max(conteos, key=conteos.get)
        class Dialect(csv.Dialect):
            delimiter = separador
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return Dialect

def abrir_archivo_sistema(ruta):
    try:
        if platform.system() == "Windows":
            os.startfile(ruta)
        elif platform.system() == "Darwin":
            subprocess.call(["open", ruta])
        else:
            subprocess.call(["xdg-open", ruta])
    except Exception as e:
        print(f"No se pudo abrir el archivo automáticamente: {e}")

def obtener_url_y_id_por_busqueda_texto(session, texto_busqueda):
    search_url = f"{BASE_URL}?search_api_fulltext={requests.utils.quote(texto_busqueda)}"
    try:
        resp = session.get(search_url, timeout=20)
        resp.raise_for_status()
    except:
        return None, ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a['href']
        if "/eidos/" in href:
            full_url = href if href.startswith("http") else "https://iepnb.gob.es" + href
            match = re.search(r'/eidos/(\d+)', full_url)
            eidos_id = match.group(1) if match else ""
            return full_url, eidos_id
    return None, ""