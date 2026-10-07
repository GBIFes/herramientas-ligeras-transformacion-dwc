"""
MÓDULO: Extracción masiva de información taxonómica desde fichas EIDOS y volcado a CSV

Este script automatiza la lectura de URLs almacenadas en una tabla Access y extrae de cada
una de ellas todos los datos taxonómicos disponibles en las fichas EIDOS del MITECO,
generando un archivo CSV estructurado con los resultados.

FUNCIONAMIENTO GENERAL:
1. Conexión a la base de datos Access (.accdb) mediante pyodbc.
2. Lectura del campo 'source' de la tabla indicada (por defecto: taxon), donde cada registro
   contiene una URL directa a una ficha EIDOS.
3. Para cada URL válida:
      - Descarga de la página HTML con requests y cabecera User-Agent realista.
      - Parseo del documento con BeautifulSoup.
      - Extracción del nombre científico desde <h1><span>.
      - Obtención del nombre común, ámbito, origen e identificador desde los bloques
        <span class="subtitle"> y <div class="font-especial">.
      - Identificación del grupo taxonómico desde el contenedor
        <div class="wrapper-tags-especie-eidos">.
      - Lectura completa de la taxonomía (Reino, Filo, Clase, Orden, Familia, Género,
        Especie, Autor) desde la sección <div id="inf_taxonomica">.
4. Normalización básica del texto mediante la función auxiliar 'limpiar'.
5. Escritura de cada ficha en un archivo CSV con delimitador ';', incluyendo:
      - URL
      - Nombre científico
      - Nombre común
      - Ámbito
      - Origen
      - Identificador
      - Grupo taxonómico
      - Taxonomía completa (8 niveles)
6. Registro en consola del progreso y captura de errores por ficha sin detener el proceso.
7. Pausa configurable entre solicitudes para evitar saturación del servidor.

Este script permite generar un dataset taxonómico completo y homogéneo a partir de las
fichas EIDOS, útil para validación, auditoría, integración en flujos DwC/GBIF o análisis
taxonómico avanzado.
"""


import pyodbc
import requests
from bs4 import BeautifulSoup
import csv
import time

# ============================================================
# CONFIGURACIÓN (Rellena estos valores)
# ============================================================

DATABASE = r"C:\Users\Javier Estrada\Documents\Database2.accdb"          # Ruta de la base de datos Access
TABLE = "taxon"                            # Nombre de la tabla
CAMPO_URL = "source"                        # Campo donde está la URL de EIDOS
CSV_SALIDA = r"C:\Users\Javier Estrada\Documents\LESRP\resultado_eidos.csv"        # Archivo CSV de salida


PAUSA = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def limpiar(elemento):
    if elemento is None:
        return ""
    return " ".join(elemento.get_text(strip=True).split())


def extraer_datos_ficha(url):
    """Extrae todos los datos de una ficha EIDOS usando la URL directa."""
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # -------------------------------
    # NOMBRE CIENTÍFICO Y COMÚN
    # -------------------------------
    h1 = soup.find("h1")
    if not h1:
        raise Exception("La página no contiene <h1>. No es una ficha EIDOS.")

    nombre_cientifico = limpiar(h1.find("span"))

    subtitles = h1.find_all("span", class_="subtitle")

    nombre_comun = ""
    ambito = ""
    origen = ""
    identificador = ""

    for s in subtitles:
        texto = s.get_text(" ", strip=True).lower()

        if "nombre" in texto:
            nombre_comun = limpiar(s.find("div"))

        if "ámbito" in texto:
            divs = s.find_all("div", class_="font-especial")
            if len(divs) >= 3:
                ambito = limpiar(divs[0])
                origen = limpiar(divs[1])
                identificador = limpiar(divs[2])

    # -------------------------------
    # GRUPO TAXONÓMICO
    # -------------------------------
    grupo_taxonomico = ""
    grupo_div = soup.find("div", class_="wrapper-tags-especie-eidos")
    if grupo_div:
        grupo_span = grupo_div.find("span", class_="bold")
        grupo_taxonomico = limpiar(grupo_span)

    # -------------------------------
    # TAXONOMÍA COMPLETA
    # -------------------------------
    taxonomia = {
        "Reino": "",
        "Filo": "",
        "Clase": "",
        "Orden": "",
        "Familia": "",
        "Género": "",
        "Especie": "",
        "Autor": ""
    }

    tax_div = soup.find("div", id="inf_taxonomica")
    if tax_div:
        for li in tax_div.find_all("li"):
            texto = li.get_text(" ", strip=True)
            if ":" in texto:
                clave, valor = texto.split(":", 1)
                clave = clave.strip().replace("División o Filo", "Filo")
                valor = valor.strip()
                if clave in taxonomia:
                    taxonomia[clave] = valor

    return {
        "nombre_cientifico": nombre_cientifico,
        "nombre_comun": nombre_comun,
        "ambito": ambito,
        "origen": origen,
        "identificador": identificador,
        "grupo_taxonomico": grupo_taxonomico,
        **taxonomia
    }


# ============================================================
# CONEXIÓN A ACCESS
# ============================================================

conn = pyodbc.connect(
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    rf"DBQ={DATABASE};"
)
cursor = conn.cursor()

cursor.execute(f"SELECT [{CAMPO_URL}] FROM [{TABLE}]")
registros = cursor.fetchall()

# ============================================================
# CREAR CSV
# ============================================================

with open(CSV_SALIDA, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")

    writer.writerow([
        "URL",
        "Nombre científico",
        "Nombre común",
        "Ámbito",
        "Origen",
        "Identificador",
        "Grupo taxonómico",
        "Reino",
        "Filo",
        "Clase",
        "Orden",
        "Familia",
        "Género",
        "Especie",
        "Autor"
    ])

    # ========================================================
    # RECORRER REGISTROS
    # ========================================================

    for (url,) in registros:

        if not url or not str(url).strip():
            continue

        print(f"Abriendo ficha: {url}")

        try:
            datos = extraer_datos_ficha(url)

            writer.writerow([
                url,
                datos["nombre_cientifico"],
                datos["nombre_comun"],
                datos["ambito"],
                datos["origen"],
                datos["identificador"],
                datos["grupo_taxonomico"],
                datos["Reino"],
                datos["Filo"],
                datos["Clase"],
                datos["Orden"],
                datos["Familia"],
                datos["Género"],
                datos["Especie"],
                datos["Autor"]
            ])

        except Exception as e:
            print(f"   ERROR: {e}")

        time.sleep(PAUSA)

print("\nProceso terminado.")
print(f"CSV generado en: {CSV_SALIDA}")
