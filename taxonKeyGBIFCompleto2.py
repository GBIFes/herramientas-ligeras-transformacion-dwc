"""
==============================================================================
SCRIPT: Sincronización y Enriquecimiento Taxonómico con GBIF
==============================================================================
DESCRIPCIÓN:
  Este script en Python se conecta a una base de datos local de Microsoft Access,
  extrae nombres científicos de una tabla específica, consulta la API de GBIF 
  (Global Biodiversity Information Facility) para resolver su estatus taxonómico, 
  obtener identificadores (taxonKey) y datos de clasificación superior (reino, filum, 
  clase, género), y exporta un informe completo en formato CSV estructurado bajo 
  estándares de biodiversidad (Darwin Core).

ESTRUCTURA DEL CSV DE SALIDA (Delimitado por punto y coma ';'):
  - scientificName: Nombre científico original consultado.
  - verbatimIdentification: Identificación en texto original (verbatim).
  - taxonRank_original: Rango taxonómico original especificado en la tabla.
  - ScientificName_GBIF: Nombre científico devuelto por GBIF.
  - taxonRank_GBIF: Rango taxonómico según GBIF.
  - taxonomicStatus: Estatus taxonómico (ej. accepted, synonym).
  - acceptedNameUsage: Nombre científico aceptado si es un sinónimo.
  - acceptedNameUsageID: URI del nombre aceptado en GBIF.
  - nameAccordingTo: Fuente de la taxonomía (ej. GBIF Backbone Taxonomy).
  - nameAccordingToID: Identificador de la fuente de la taxonomía.
  - kingdom: Reino taxonómico (GBIF).
  - phylum: Filum/División taxonómica (GBIF).
  - class: Clase taxonómica (GBIF).
  - genus: Género taxonómico (GBIF).
  - source: URL de origen o repositorio local (ej. EIDOS).
  - taxonKey: Clave única del taxón en GBIF.
  - URI_nombre_buscado: Enlace directo al perfil del taxón en GBIF.
  - coincidencia: Resultado de la validación (1 = coincidencia exacta, -1 = difiere, -2 = sin resultados).

REQUISITOS / DEPENDENCIAS:
  - Python 3.x instalado.
  - Librerías de terceros: requests, pyodbc. 
    (Puedes instalarlas ejecutando: pip install requests pyodbc)
  - Controlador ODBC de Microsoft Access instalado en el sistema operativo.

CONFIGURACIÓN PREVIA (Sección CONFIGURACIÓN):
  1. DATABASE: Ajusta la ruta absoluta de tu archivo de Access (.accdb).
  2. TABLE: Indica el nombre de la tabla a consultar (ej. "LESRP").
  3. CAMPOS: Verifica que los nombres de las columnas coincidan con los de tu tabla.
  4. CSV_SALIDA: Define la ruta donde se guardará el archivo CSV resultante.

INSTRUCCIONES DE USO:
  1. Asegúrate de cerrar la base de datos en Access para evitar conflictos de bloqueo.
  2. Ejecuta el script desde tu terminal o entorno de desarrollo:
     python tu_script.py
  3. El script procesará los registros uno a uno mostrando el progreso en pantalla 
     y generará el archivo delimitado por punto y coma (;).
==============================================================================
"""
import pyodbc
import requests
import csv
import time

# ============================================================
# CONFIGURACIÓN
# ============================================================

DATABASE = "C:\\Users\\Javier Estrada\\Documents\\LESRP\\LESRPE.accdb"
TABLE = "LESRP"

CAMPO_NOMBRE = "NombreActualizado"
CAMPO_VERBATIM = "NombreActualizado"
CAMPO_RANGO = "RangoTaxonómico"
CAMPO_EIDOS = "EIDOS_ID"

CSV_SALIDA = r"C:\Users\Javier Estrada\Documents\LESRP\gbif_LESRPE.csv"

HEADERS = {"User-Agent": "Mozilla/5.0"}
PAUSA = 0.5

NAME_ACCORDING_TO = "GBIF Backbone Taxonomy"
NAME_ACCORDING_TO_ID = "http://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"

# ============================================================
# RESOLVER NOMBRE EN GBIF (SOLUCIÓN REAL)
# ============================================================

def resolver_gbif(nombre):
    url = f"https://api.gbif.org/v1/species/match?name={nombre}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    if "usageKey" not in data:
        return None

    # taxon aceptado
    acceptedKey = data.get("acceptedUsageKey", None)
    acceptedSci = data.get("acceptedScientificName", "")

    # taxon del nombre buscado (alternatives)
    buscadoKey = None
    buscadoSci = None
    buscadoRank = None

    if "alternatives" in data and data["alternatives"]:
        # 1) buscar coincidencia exacta
        for alt in data["alternatives"]:
            sci_alt = alt.get("scientificName", "").lower()
            if nombre.lower() in sci_alt:
                buscadoKey = alt.get("usageKey")
                buscadoSci = alt.get("scientificName")
                buscadoRank = alt.get("rank")
                break

        # 2) si no coincide, tomar el primero
        if not buscadoKey:
            alt = data["alternatives"][0]
            buscadoKey = alt.get("usageKey")
            buscadoSci = alt.get("scientificName")
            buscadoRank = alt.get("rank")

    return {
        "buscadoKey": buscadoKey,
        "buscadoScientificName": buscadoSci,
        "buscadoRank": buscadoRank,
        "acceptedKey": acceptedKey,
        "acceptedScientificName": acceptedSci,
        "taxonomicStatus": data.get("status", ""),
        "kingdom": data.get("kingdom", ""),
        "phylum": data.get("phylum", ""),
        "class": data.get("class", ""),
        "genus": data.get("genus", "")
    }

# ============================================================
# COMPARAR NOMBRES
# ============================================================

def comparar_nombres(buscado, encontrado):
    if not encontrado:
        return -2
    if buscado.lower().strip() == encontrado.lower().strip():
        return 1
    return -1

# ============================================================
# CONEXIÓN A ACCESS
# ============================================================

conn = pyodbc.connect(
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    rf"DBQ={DATABASE};"
)
cursor = conn.cursor()

cursor.execute(
    f"SELECT [{CAMPO_NOMBRE}], [{CAMPO_VERBATIM}], [{CAMPO_RANGO}], [{CAMPO_EIDOS}] FROM [{TABLE}]"
)
registros = cursor.fetchall()

# ============================================================
# CREAR CSV
# ============================================================

with open(CSV_SALIDA, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")

    writer.writerow([
        "scientificName",
        "verbatimIdentification",
        "taxonRank_original",
        "ScientificName_GBIF",
        "taxonRank_GBIF",
        "taxonomicStatus",
        "acceptedNameUsage",
        "acceptedNameUsageID",
        "nameAccordingTo",
        "nameAccordingToID",
        "kingdom",
        "phylum",
        "class",
        "genus",
        "source",
        "taxonKey",
        "URI_nombre_buscado",
        "coincidencia"
    ])

    for nombre, verbatim, rango_original, eidos_id in registros:

        if not nombre:
            continue

        nombre = str(nombre).strip()
        verbatim = str(verbatim).strip()
        rango_original = str(rango_original).strip()

        print("Buscando en GBIF:", nombre)

        try:
            datos = resolver_gbif(nombre)

            if not datos or not datos["buscadoKey"]:
                writer.writerow([
                    nombre, verbatim, rango_original,
                    "", "", "",
                    "", "",
                    NAME_ACCORDING_TO, NAME_ACCORDING_TO_ID,
                    "", "", "", "",
                    f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{eidos_id}",
                    "", "", -2
                ])
                continue

            # taxonKey del nombre buscado
            taxonKey = datos["buscadoKey"]
            sciName_gbif = datos["buscadoScientificName"]
            rango_gbif = datos["buscadoRank"]

            # taxonKey del aceptado
            acceptedKey = datos["acceptedKey"]
            acceptedSci = datos["acceptedScientificName"] or sciName_gbif

            taxonomicStatus = datos["taxonomicStatus"].replace("acepted", "accepted")

            # URIs correctas
            uri_buscado = f"https://www.gbif.org/species/{taxonKey}"
            acceptedNameUsageID = (
                f"https://www.gbif.org/species/{acceptedKey}"
                if acceptedKey else ""
            )

            coincidencia = comparar_nombres(nombre, sciName_gbif)

            source_url = f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{eidos_id}"

            writer.writerow([
                nombre,
                verbatim,
                rango_original,
                sciName_gbif,
                rango_gbif,
                taxonomicStatus,
                acceptedSci,
                acceptedNameUsageID,
                NAME_ACCORDING_TO,
                NAME_ACCORDING_TO_ID,
                datos["kingdom"],
                datos["phylum"],
                datos["class"],
                datos["genus"],
                source_url,
                taxonKey,
                uri_buscado,
                coincidencia
            ])

        except Exception as e:
            writer.writerow([
                nombre, verbatim, rango_original,
                "ERROR", "", "",
                "", "",
                NAME_ACCORDING_TO, NAME_ACCORDING_TO_ID,
                "", "", "", "",
                f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{eidos_id}",
                "", "", -2
            ])

        time.sleep(PAUSA)

print("\nProceso terminado.")
print("CSV generado:", CSV_SALIDA)