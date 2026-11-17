"""
taxa_gbif.py
============
Módulo de consulta, contraste y verificación con la API de GBIF (Species Match).
Manejo seguro de URIs y claves taxonómicas.
Incluye: caché por sesión, reintentos ante 429/5xx, contraste de género y
epíteto, y construcción de la jerarquía taxonómica completa (gbif_taxonomy).

NOTA IMPORTANTE: el endpoint /species/match NO incluye la clasificación
(kingdom, phylum, class, order, family, genus, subgenus) en su respuesta.
La jerarquía se obtiene con una segunda consulta a /species/{usageKey}.
"""

import time

import requests

_gbif_cache = {}        # caché de /species/match, por nombre
_species_cache = {}     # caché de /species/{usageKey}, por clave
_session = requests.Session()

_CATS_TAXONOMIA = ("kingdom", "phylum", "class", "order", "family", "genus", "subgenus")

MATCH_URL = "https://api.gbif.org/v1/species/match"
SPECIES_URL = "https://api.gbif.org/v1/species/{key}"


def limpiar_cache_gbif():
    _gbif_cache.clear()
    _species_cache.clear()


def construir_taxonomia_gbif(data):
    """Devuelve la jerarquía taxonómica en formato 'cat: valor | cat: valor'."""
    if not data:
        return ""
    return " | ".join(f"{cat}: {data.get(cat) or ''}" for cat in _CATS_TAXONOMIA)


def _get_json(url, params=None):
    """GET con reintentos ante 429/5xx y errores de red. Devuelve dict o None."""
    for intento in range(3):
        try:
            response = _session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            if response.status_code in (429, 500, 502, 503):
                time.sleep(1.5 * (intento + 1))  # espera y reintenta
                continue
            return None
        except Exception:
            time.sleep(1.0)
    return None


def consultar_gbif(nombre_cientifico):
    clave = str(nombre_cientifico).strip()
    if clave in _gbif_cache:
        return _gbif_cache[clave]

    params = {
        'name': clave,
        'strict': 'false',
        'verbose': 'true'
    }

    data = _get_json(MATCH_URL, params=params)
    _gbif_cache[clave] = data
    return data


def consultar_especie_gbif(usage_key):
    """Devuelve el registro completo de /species/{usageKey} (con clasificación)."""
    if usage_key is None:
        return None
    clave = str(usage_key)
    if not clave.isdigit():
        return None
    if clave in _species_cache:
        return _species_cache[clave]

    data = _get_json(SPECIES_URL.format(key=clave))
    _species_cache[clave] = data
    return data


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
            "gbif_discrepancy": "Ausente o no encontrado en GBIF",
            "gbif_taxonomy": ""
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

    # La clasificación completa viene de /species/{usageKey}, no del match.
    taxonomy = ""
    if usage_key_str:
        especie = consultar_especie_gbif(usage_key_str)
        if especie:
            taxonomy = construir_taxonomia_gbif(especie)
            # Completar género/familia si el match no los trajo
            if not gbif_genus:
                gbif_genus = especie.get("genus", "") or ""
            if not gbif_family:
                gbif_family = especie.get("family", "") or ""

    discrepancias = []
    if match_type == "FUZZY":
        discrepancias.append("Coincidencia difusa (Fuzzy en GBIF)")

    if gbif_genus and gen and gbif_genus.lower() != gen.lower():
        discrepancias.append(f"Discrepancia de género (Local: '{gen}' vs GBIF: '{gbif_genus}')")

    # Contraste del epíteto específico con el nombre devuelto por GBIF
    sp_gbif = ""
    if gbif_sci_name:
        trozos = gbif_sci_name.split()
        if len(trozos) >= 2 and trozos[1][:1].islower():
            sp_gbif = trozos[1].rstrip(")×")

    if sp and sp_gbif and sp_gbif.lower() != sp.lower():
        discrepancias.append(f"Discrepancia de epíteto (Local: '{sp}' vs GBIF: '{sp_gbif}')")

    discrepancy_str = "; ".join(discrepancias) if discrepancias else "Sin discrepancias"

    return {
        "gbif_matchType": match_type,
        "gbif_status": status,
        "gbif_usageKey": usage_key_str,
        "gbif_scientificName": gbif_sci_name,
        "gbif_genus": gbif_genus,
        "gbif_family": gbif_family,
        "gbif_uri": gbif_uri,
        "gbif_discrepancy": discrepancy_str,
        "gbif_taxonomy": taxonomy
    }