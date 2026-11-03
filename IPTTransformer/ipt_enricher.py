"""
ipt_enricher.py
===============
Motor de enriquecimiento taxonómico recursivo mediante la API de GBIF.
Procesa los registros de entrada para resolver estatus, sinónimos en cadena
y clasificación superior (Reino, Filum, Clase, Género).
"""

import requests
import time
from collections import deque

HEADERS = {"User-Agent": "Mozilla/5.0 (IPT-Transformer-Enricher/2.0)"}
PAUSA = 0.4

NAME_ACCORDING_TO = "GBIF Backbone Taxonomy"
NAME_ACCORDING_TO_ID = "http://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"

def resolver_gbif_recursivo(nombre_inicial):
    """
    Consulta la API de GBIF de forma recursiva/en red para resolver sinónimos
    en cadena, alternativas y taxonomía superior (Reino, Filum, Clase, Género).
    """
    cola_procesamiento = deque([nombre_inicial])
    visitados = set()
    resultados_acumulados = []

    while cola_procesamiento:
        nombre_actual = cola_procesamiento.popleft()
        
        if nombre_actual.lower() in visitados:
            continue
        visitados.add(nombre_actual.lower())

        url = f"https://api.gbif.org/v1/species/match?name={nombre_actual}"
        try:
            r = requests.get(url, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  [Error API GBIF para '{nombre_actual}']: {e}")
            continue

        if "usageKey" not in data:
            continue

        acceptedKey = data.get("acceptedUsageKey", None)
        acceptedSci = data.get("acceptedScientificName", "")
        
        buscadoKey = data.get("usageKey")
        buscadoSci = data.get("scientificName")
        buscadoRank = data.get("rank")

        # Tratamiento recursivo de alternativas
        if "alternatives" in data and data["alternatives"]:
            for alt in data["alternatives"]:
                sci_alt = alt.get("scientificName", "")
                alt_key = alt.get("usageKey")
                if nombre_inicial.lower() in sci_alt.lower() and alt_key not in [res.get("buscadoKey") for res in resultados_acumulados]:
                    buscadoKey = alt_key
                    buscadoSci = sci_alt
                    buscadoRank = alt.get("rank")
                    break

        nodo_info = {
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
        
        resultados_acumulados.append(nodo_info)

        # Si hay un taxón aceptado distinto, se añade a la cola recursiva
        if acceptedSci and acceptedSci.lower() != buscadoSci.lower():
            if acceptedSci.lower() not in visitados:
                cola_procesamiento.append(acceptedSci)

    return resultados_acumulados

def comparar_nombres(buscado, encontrado):
    if not encontrado:
        return -2
    if buscado.lower().strip() == encontrado.lower().strip():
        return 1
    return -1

def enriquecer_dataset_core(core_rows, headers, col_nombre_idx, callback_progreso=None):
    """
    Toma las filas del Core cargado, localiza la columna del nombre científico,
    ejecuta la consulta recursiva a GBIF y retorna:
      - core_enriquecido_rows: filas actualizadas o mantenidas para el Core.
      - ext_fields: cabeceras de la extensión de Identificaciones.
      - extension_identification_rows: filas estructuradas para la extensión de Identificaciones (sinonimia).
    """
    core_enriquecido_rows = list(core_rows)
    extension_identification_rows = []

    ext_fields = [
        "taxonKey", "ScientificName_GBIF", "taxonRank_GBIF", 
        "taxonomicStatus", "acceptedNameUsage", "acceptedNameUsageID", 
        "nameAccordingTo", "nameAccordingToID", "URI_nombre_buscado", "coincidencia"
    ]

    total = len(core_rows)
    for idx_row, row in enumerate(core_rows):
        if callback_progreso:
            callback_progreso(idx_row + 1, total)

        if len(row) <= col_nombre_idx:
            continue

        nombre = str(row[col_nombre_idx]).strip()
        if not nombre:
            continue

        try:
            nodos = resolver_gbif_recursivo(nombre)
            if not nodos:
                continue

            for datos in nodos:
                taxonKey = datos["buscadoKey"]
                sciName_gbif = datos["buscadoScientificName"]
                rango_gbif = datos["buscadoRank"]
                acceptedKey = datos["acceptedKey"]
                acceptedSci = datos["acceptedScientificName"] or sciName_gbif
                taxonomicStatus = datos["taxonomicStatus"].replace("acepted", "accepted")
                
                uri_buscado = f"https://www.gbif.org/species/{taxonKey}" if taxonKey else ""
                acceptedNameUsageID = f"https://www.gbif.org/species/{acceptedKey}" if acceptedKey else ""
                coincidencia = comparar_nombres(nombre, sciName_gbif)

                # Construir la fila para la Extensión de Identificación (DwC Extension)
                ext_row = [
                    str(taxonKey) if taxonKey else "",
                    sciName_gbif,
                    rango_gbif,
                    taxonomicStatus,
                    acceptedSci,
                    acceptedNameUsageID,
                    NAME_ACCORDING_TO,
                    NAME_ACCORDING_TO_ID,
                    uri_buscado,
                    coincidencia
                ]
                extension_identification_rows.append(ext_row)

        except Exception as e:
            print(f"Error enriqueciendo '{nombre}': {e}")

        time.sleep(PAUSA)

    return core_enriquecido_rows, ext_fields, extension_identification_rows