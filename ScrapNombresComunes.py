r"""
===============================================================================
ScrapNombresComunes.py
===============================================================================

Este script obtiene los nombres comunes de las especies del Inventario
Español del Patrimonio Natural y la Biodiversidad (IEPNB), a partir de los
EIDOS_ID contenidos en el archivo de entrada "Id.txt".

Genera un archivo CSV con:

    EIDOS_ID
    scientificName
    idioma
    pais
    nombre

Si una celda contiene varios nombres separados por comas o punto y coma,
se generan varias filas independientes (una por cada nombre). El archivo
de salida se guarda exactamente en la ruta indicada en OUTPUT_FILE.

El script escribe línea a línea en el CSV para que el fichero exista desde
el primer registro y no se pierdan datos si la ejecución se interrumpe.
===============================================================================
"""

import os
import re
import time
import csv
import requests
from bs4 import BeautifulSoup
import pandas as pd

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

BASE_URL = "https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/"

# Ruta absoluta del archivo de entrada (TAB-separated)
INPUT_FILE = r"C:/Users/Javier Estrada/Downloads/Id.txt"

# Ruta absoluta del archivo de salida (se creará en esta ubicación)
OUTPUT_FILE = r"C:/Users/Javier Estrada/Downloads/nomcomunes_resultado.csv"

# Diccionario idioma -> código país (ISO 3166-1 alpha-2)
IDIOMA_PAIS = {
    "Castellano": "ES",
    "Catalán": "ES",
    "Euskera": "ES",
    "Gallego": "ES",
    "Valenciano": "ES",
    "Mallorquín": "ES",
    "Altoaragonés": "ES",
    "Inglés": "GB",
    "Francés": "FR",
    "Portugués": "PT",
    "Italiano": "IT",
    "Alemán": "DE",
}

# Separadores que consideraremos para dividir nombres múltiples en una celda
SEPARADOR_NOMBRES_REGEX = re.compile(r'\s*[;,]\s*')  # coma o punto y coma, con espacios opcionales

# Pausa entre peticiones (segundos)
PAUSA_SEGUNDOS = 0.2

# Frecuencia de flush al disco (cada N escrituras)
FLUSH_EVERY = 50

# =============================================================================
# COMPROBACIONES PREVIAS
# =============================================================================

# Asegurarnos de que la carpeta de salida existe
output_dir = os.path.dirname(OUTPUT_FILE)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

# =============================================================================
# LEER ARCHIVO DE ENTRADA
# =============================================================================

print("\nLeyendo archivo de entrada...")
df = pd.read_csv(INPUT_FILE, sep="\t", dtype=str)
df.fillna("", inplace=True)
print(f"Especies encontradas en Id.txt: {len(df)}")

# =============================================================================
# SESIÓN HTTP
# =============================================================================

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

# =============================================================================
# FUNCIÓN DE SCRAPING
# =============================================================================

def extraer_nomcomunes(eidos_id):
    """
    Devuelve una lista de tuplas (idioma, nombre) tal como aparecen en la tabla.
    No realiza división de nombres múltiples aquí; eso se hace en el bucle principal.
    """
    url = BASE_URL + str(eidos_id)

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"   ✗ Error accediendo a {url}")
        print(f"     {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    tab = soup.find("div", id="nomcomunes")
    if tab is None:
        return []

    tabla = tab.find("table")
    if tabla is None:
        return []

    datos = []
    for fila in tabla.find_all("tr"):
        celdas = fila.find_all(["th", "td"])
        if len(celdas) < 2:
            continue

        idioma = celdas[0].get_text(" ", strip=True)
        nombre = celdas[1].get_text(" ", strip=True)

        # Ignorar la fila de cabecera
        if idioma.lower() == "idioma" and nombre.lower() == "nombre":
            continue

        if not idioma or not nombre:
            continue

        datos.append((idioma, nombre))

    return datos

# =============================================================================
# ABRIR ARCHIVO DE SALIDA Y ESCRIBIR CABECERA (ESCRITURA LÍNEA A LÍNEA)
# =============================================================================

# Usamos 'with' para asegurar cierre correcto incluso ante excepciones
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["EIDOS_ID", "scientificName", "idioma", "pais", "nombre"])

    idiomas_no_clasificados = set()
    registros_escritos = 0

    print("\n" + "="*80)
    print("INICIANDO SCRAPING")
    print("="*80)

    try:
        for idx, row in df.iterrows():
            # Aseguramos que EIDOS_ID y scientificName se traten como strings
            eidos_id = str(row.get("EIDOS_ID", "")).strip()
            scientific_name = str(row.get("scientificName", "")).strip()

            print(f"\nProcesando {idx+1}/{len(df)} → {eidos_id} - {scientific_name}")

            nomcomunes = extraer_nomcomunes(eidos_id)

            if not nomcomunes:
                print(f"   → No hay tabla de nombres comunes para {eidos_id}")
                time.sleep(PAUSA_SEGUNDOS)
                continue

            for idioma, nombre in nomcomunes:
                # Dividir nombres múltiples por coma o punto y coma
                nombres_separados = SEPARADOR_NOMBRES_REGEX.split(nombre)
                # Filtrar nombres vacíos y limpiar espacios
                nombres_separados = [n.strip() for n in nombres_separados if n and n.strip()]

                pais = IDIOMA_PAIS.get(idioma, "")
                if not pais:
                    idiomas_no_clasificados.add(idioma)
                    print(f"   ⚠ Idioma sin país asignado: {idioma}")

                for nombre_individual in nombres_separados:
                    print(f"   ✓ {idioma} [{pais}]: {nombre_individual}")

                    writer.writerow([
                        eidos_id,
                        scientific_name,
                        idioma,
                        pais,
                        nombre_individual
                    ])

                    registros_escritos += 1

                    # Flush periódico para asegurar que el archivo se actualiza en disco
                    if registros_escritos % FLUSH_EVERY == 0:
                        f.flush()
                        try:
                            os.fsync(f.fileno())
                        except Exception:
                            # os.fsync puede fallar en algunos entornos; no es crítico
                            pass

            # Pausa para no sobrecargar el servidor
            time.sleep(PAUSA_SEGUNDOS)

    except KeyboardInterrupt:
        print("\nEjecución interrumpida por el usuario. Cerrando archivo y saliendo...")
    except Exception as e:
        print("\nSe produjo un error inesperado durante el scraping:")
        print(e)
    finally:
        # 'with' se encargará de cerrar el archivo; aquí solo imprimimos resumen parcial
        print("\n" + "="*80)
        print("SCRAPING FINALIZADO (parcial o completo)")
        print("="*80)
        print(f"Especies procesadas (intentos): {len(df)}")
        print(f"Registros escritos hasta ahora: {registros_escritos}")
        print(f"Archivo generado en: {os.path.abspath(OUTPUT_FILE)}")

        if idiomas_no_clasificados:
            print("\nIdiomas sin país asignado:")
            for idioma in sorted(idiomas_no_clasificados):
                print(f"   - {idioma}")
        else:
            print("\nTodos los idiomas encontrados tienen país asignado.")

        print("\nProceso terminado.")
