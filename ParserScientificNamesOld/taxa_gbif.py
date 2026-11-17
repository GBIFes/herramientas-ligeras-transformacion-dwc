"""
taxa_gbif.py
============
Módulo de consulta, contraste y verificación con la API de GBIF (Species Match).
Manejo seguro de URIs y claves taxonómicas.
"""

import requests

def consultar_gbif(nombre_cientifico):
    url = "https://api.gbif.org/v1/species/match"
    params = {
        'name': nombre_cientifico,
        'strict': 'false',
        'verbose': 'true'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    
    return None

def verificar_con_gbif(gen, sp, infra, nombre_original):
    nombre_a_buscar = f"{gen} {sp}".strip()
    if infra:
        nombre_a_buscar = f"{nombre_a_buscar} {infra}"
    if not nombre_a_buscar:
        nombre_a_buscar = nombre_original

    data = consultar_gbif(nombre_a_buscar)
    
    if not data or data.get("matchType") == "NONE":
        if nombre_a_buscar != f"{gen} {sp}".strip() and gen and sp:
            nombre_a_buscar = f"{gen} {sp}".strip()
            data = consultar_gbif(nombre_a_buscar)

    if not data or data.get("matchType") == "NONE":
        return {
            "gbif_matchType": "NONE",
            "gbif_status": "AUSENTE",
            "gbif_usageKey": "",
            "gbif_scientificName": "",
            "gbif_genus": "",
            "gbif_family": "",
            "gbif_uri": "",
            "gbif_discrepancy": "Ausente o no encontrado en GBIF"
        }

    match_type = data.get("matchType", "")
    status = data.get("status", "")
    usage_key = data.get("usageKey", None)
    gbif_sci_name = data.get("scientificName", "")
    gbif_genus = data.get("genus", "")
    gbif_family = data.get("family", "")
    
    # Asegurar conversión segura a cadena y evitar errores si usageKey es nulo o inválido
    if usage_key is not None and str(usage_key).isdigit():
        gbif_uri = f"https://www.gbif.org/species/{usage_key}"
        usage_key_str = str(usage_key)
    else:
        gbif_uri = ""
        usage_key_str = ""

    discrepancias = []
    if match_type == "FUZZY":
        discrepancias.append("Coincidencia difusa (Fuzzy en GBIF)")
    
    if gbif_genus and gen and gbif_genus.lower() != gen.lower():
        discrepancias.append(f"Discrepancia de género (Local: '{gen}' vs GBIF: '{gbif_genus}')")
        
    discrepancy_str = "; ".join(discrepancias) if discrepancias else "Sin discrepancias"

    return {
        "gbif_matchType": match_type,
        "gbif_status": status,
        "gbif_usageKey": usage_key_str,
        "gbif_scientificName": gbif_sci_name,
        "gbif_genus": gbif_genus,
        "gbif_family": gbif_family,
        "gbif_uri": gbif_uri,
        "gbif_discrepancy": discrepancy_str
    }