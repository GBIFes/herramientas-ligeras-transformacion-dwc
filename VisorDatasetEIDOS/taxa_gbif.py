"""
taxa_gbif.py
============
Módulo de consulta, contraste y verificación taxonómica unificada:
- Usa GBIF v1 (/species/match) para obtener el usageKey, la autoría y la URI oficial.
- Delega de forma homogénea para TODOS los taxones la resolución de la jerarquía
  taxonómica (kingdom a subgenus) a ChecklistBank / Catalogue of Life (dataset 3LR),
  garantizando consistencia total y evitando los desplazamientos de rango del
  antiguo Backbone de GBIF.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

_gbif_cache = {}          # caché de /species/match, por nombre
_species_cache = {}       # caché de /species/{usageKey}, por clave
_cb_cache = {}            # caché de ChecklistBank (COL 3LR), por nombre
_cache_lock = threading.Lock()
_session = requests.Session()

_CATS_TAXONOMIA = ("kingdom", "phylum", "class", "order", "family", "genus", "subgenus")

MATCH_URL = "https://api.gbif.org/v1/species/match"
SPECIES_URL = "https://api.gbif.org/v1/species/{key}"
CHECKLISTBANK_SEARCH_URL = "https://api.checklistbank.org/dataset/3LR/nameusage/search"

MAX_INTENTOS_JSON = 3


def limpiar_cache_gbif():
    with _cache_lock:
        _gbif_cache.clear()
        _species_cache.clear()
        _cb_cache.clear()


def construir_taxonomia_gbif(data):
    """Jerarquía en formato DwC: nombres de rango separados por ' | ', sin vacíos."""
    if not data:
        return ""
    partes = []
    for cat in _CATS_TAXONOMIA:
        valor = str(data.get(cat) or "").strip()
        if valor:
            partes.append(valor)
    return " | ".join(partes)


def _rangos_de(data):
    """Extrae los siete rangos de un nodo GBIF como dict de cadenas."""
    return {cat: str((data or {}).get(cat) or "").strip() for cat in _CATS_TAXONOMIA}


def _get_json(url, params=None):
    """GET con reintentos acotados ante 429/5xx y errores de red. dict o None."""
    for intento in range(MAX_INTENTOS_JSON):
        try:
            response = _session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (intento + 1))
                continue
            return None
        except Exception:
            time.sleep(1.0 * (intento + 1))
    return None


def consultar_gbif(nombre_cientifico):
    """Consulta /species/match en GBIF. Los fallos transitorios (None) no se cachean."""
    clave = str(nombre_cientifico).strip()
    with _cache_lock:
        if clave in _gbif_cache:
            return _gbif_cache[clave]

    params = {'name': clave, 'strict': 'false', 'verbose': 'true'}
    data = _get_json(MATCH_URL, params=params)
    if data is not None:
        with _cache_lock:
            _gbif_cache[clave] = data
    return data


def consultar_especie_gbif(usage_key):
    """Registro completo de /species/{usageKey} en GBIF."""
    if usage_key is None:
        return None
    clave = str(usage_key)
    if not clave.isdigit():
        return None
    with _cache_lock:
        if clave in _species_cache:
            return _species_cache[clave]

    data = _get_json(SPECIES_URL.format(key=clave))
    if data is not None:
        with _cache_lock:
            _species_cache[clave] = data
    return data


def _buscar_en_checklistbank(nombre: str, rank: str | None = None) -> dict:
    """
    Consulta Catalogue of Life (dataset 3LR) en ChecklistBank y devuelve el dict
    de rangos (_CATS_TAXONOMIA) extraído de su clasificación moderna.
    """
    clave_busqueda = str(nombre).strip()
    if not clave_busqueda:
        return {}

    cache_key = f"{clave_busqueda.lower()}|{rank or ''}"
    with _cache_lock:
        if cache_key in _cb_cache:
            return _cb_cache[cache_key]

    base_params = {"q": clave_busqueda, "limit": 5}
    if rank:
        base_params["rank"] = rank

    # 1. Priorizar taxones aceptados
    params_acc = dict(base_params, status="accepted")
    data = _get_json(CHECKLISTBANK_SEARCH_URL, params=params_acc)

    # 2. Si no hay resultado aceptado directo (p. ej. sinónimo), buscar sin filtro de estado
    if not data or not data.get("result"):
        data = _get_json(CHECKLISTBANK_SEARCH_URL, params=base_params)

    rangos = {}
    if data and data.get("result"):
        # Buscar coincidencia exacta de nombre científico/canónico primero
        mejor = None
        objetivo = clave_busqueda.lower()
        for item in data["result"]:
            usage = item.get("usage") or {}
            cand_name = str(usage.get("name") or usage.get("label") or "").lower().strip()
            # Comparar sin autoría
            cand_clean = " ".join(cand_name.split()[:2]) if not rank else cand_name.split()[0]
            if cand_clean == objetivo and item.get("classification"):
                mejor = item
                break

        if not mejor:
            for item in data["result"]:
                if item.get("classification"):
                    mejor = item
                    break

        if mejor:
            rangos = {cat: "" for cat in _CATS_TAXONOMIA}
            for nodo in mejor.get("classification", []):
                rango_nodo = str(nodo.get("rank") or "").lower().strip()
                nombre_nodo = str(nodo.get("name") or "").strip()
                if rango_nodo in rangos and nombre_nodo:
                    rangos[rango_nodo] = nombre_nodo

            # Añadir el propio taxón si es género o subgénero y no vino en classification
            usage = mejor.get("usage") or {}
            u_rank = str(usage.get("rank") or "").lower().strip()
            u_name = str(usage.get("name") or "").strip()
            if u_rank in rangos and u_name and not rangos[u_rank]:
                rangos[u_rank] = u_name

    if data is not None:
        with _cache_lock:
            _cb_cache[cache_key] = rangos

    return rangos


def resolver_jerarquia_unificada(nombre_canonico: str, genero_ancla: str, data_gbif: dict, locales: dict | None = None):
    """
    Resuelve la jerarquía taxonómica de forma homogénea para todos los taxones:
    1. Consulta ChecklistBank (Catalogue of Life 3LR) por especie/taxón.
    2. Si faltan rangos superiores o no hubo match de especie, consulta el género
       ancla en ChecklistBank (3LR) para garantizar el linaje completo.
    3. Solo si ChecklistBank no tuviera el taxón, recurre al Backbone de GBIF
       y finalmente a los datos locales de EIDOS.
    """
    locales = locales or {}
    conflictos = []
    rangos = {cat: "" for cat in _CATS_TAXONOMIA}

    # Paso 1: Consulta directa a ChecklistBank (COL 3LR) por nombre
    cb_especie = _buscar_en_checklistbank(nombre_canonico)
    for cat in _CATS_TAXONOMIA:
        if cb_especie.get(cat):
            rangos[cat] = cb_especie[cat]

    # Paso 2: Completar desde el género ancla en ChecklistBank (COL 3LR)
    gen_limpio = str(genero_ancla or "").strip().split()[0] if genero_ancla else ""
    if gen_limpio and not all(rangos[c] for c in ("kingdom", "phylum", "class", "order", "family", "genus")):
        cb_genero = _buscar_en_checklistbank(gen_limpio, rank="genus")
        for cat in ("kingdom", "phylum", "class", "order", "family", "genus"):
            if not rangos[cat] and cb_genero.get(cat):
                rangos[cat] = cb_genero[cat]

    # Paso 3: Respaldo con el nodo de GBIF v1 si ChecklistBank no cubrió algo
    gbif_rangos = _rangos_de(data_gbif)
    usage_key = (data_gbif or {}).get("usageKey")
    if usage_key is not None and str(usage_key).isdigit():
        nodo_gbif = consultar_especie_gbif(str(usage_key))
        for cat, val in _rangos_de(nodo_gbif).items():
            if not gbif_rangos[cat]:
                gbif_rangos[cat] = val

    for cat in _CATS_TAXONOMIA:
        if not rangos[cat] and gbif_rangos.get(cat):
            rangos[cat] = gbif_rangos[cat]

    # Paso 4: Respaldo final con los campos locales de EIDOS y registro de conflictos
    for cat in _CATS_TAXONOMIA:
        val_local = str(locales.get(cat) or "").strip()
        if not rangos[cat] and val_local:
            rangos[cat] = val_local
        elif rangos[cat] and val_local and rangos[cat].lower() != val_local.lower():
            conflictos.append(
                f"Discrepancia de {cat} (Local: '{val_local}' vs COL/GBIF: '{rangos[cat]}'; se usa COL/GBIF)"
            )

    return rangos, conflictos


def verificar_con_gbif(gen, sp, infra, nombre_original, locales=None):
    """
    Contrasta un nombre con GBIF v1 para obtener usageKey, autoría y URI,
    y resuelve toda su jerarquía taxonómica de forma consistente vía ChecklistBank (COL).
    """
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
        # Aunque no haya match en GBIF v1, intentamos resolver jerarquía en ChecklistBank
        genero_ancla = gen or (locales or {}).get("genus", "")
        rangos, conflictos = resolver_jerarquia_unificada(nombre_original, genero_ancla, {}, locales=locales)
        taxonomy = construir_taxonomia_gbif(rangos)

        return {
            "gbif_matchType": "NONE",
            "gbif_status": "AUSENTE",
            "gbif_usageKey": "",
            "gbif_scientificName": "",
            "gbif_kingdom": rangos["kingdom"],
            "gbif_phylum": rangos["phylum"],
            "gbif_class": rangos["class"],
            "gbif_order": rangos["order"],
            "gbif_family": rangos["family"],
            "gbif_genus": rangos["genus"],
            "gbif_subgenus": rangos["subgenus"],
            "gbif_uri": "",
            "gbif_discrepancy": "Ausente o no encontrado en GBIF",
            "gbif_taxonomy": taxonomy
        }

    match_type = data.get("matchType", "")
    status = data.get("status", "")
    usage_key = data.get("usageKey", None)
    gbif_sci_name = data.get("scientificName", "")
    gbif_canonical = data.get("canonicalName", "") or nombre_a_buscar

    if usage_key is not None and str(usage_key).isdigit():
        gbif_uri = f"https://www.gbif.org/species/{usage_key}"
        usage_key_str = str(usage_key)
    else:
        gbif_uri = ""
        usage_key_str = ""

    genero_ancla = data.get("genus") or gen or (locales or {}).get("genus", "")
    rangos, conflictos = resolver_jerarquia_unificada(
        gbif_canonical, genero_ancla, data, locales=locales
    )

    gbif_genus = rangos["genus"]
    gbif_family = rangos["family"]
    taxonomy = construir_taxonomia_gbif(rangos)

    discrepancias = []
    if match_type == "FUZZY":
        discrepancias.append("Coincidencia difusa (Fuzzy en GBIF)")

    if gbif_genus and gen and gbif_genus.lower() != gen.lower():
        discrepancias.append(f"Discrepancia de género (Local: '{gen}' vs COL/GBIF: '{gbif_genus}')")

    sp_gbif = ""
    if gbif_sci_name:
        trozos = gbif_sci_name.split()
        if len(trozos) >= 2 and trozos[1][:1].islower():
            sp_gbif = trozos[1].rstrip(")×")

    if sp and sp_gbif and sp_gbif.lower() != sp.lower():
        discrepancias.append(f"Discrepancia de epíteto (Local: '{sp}' vs GBIF: '{sp_gbif}')")

    discrepancias.extend(conflictos)

    faltantes = [cat for cat in _CATS_TAXONOMIA if cat != "subgenus" and not rangos[cat]]
    if faltantes:
        discrepancias.append(f"Jerarquía incompleta (faltan: {', '.join(faltantes)})")

    discrepancy_str = "; ".join(discrepancias) if discrepancias else "Sin discrepancias"

    return {
        "gbif_matchType": match_type,
        "gbif_status": status,
        "gbif_usageKey": usage_key_str,
        "gbif_scientificName": gbif_sci_name,
        "gbif_kingdom": rangos["kingdom"],
        "gbif_phylum": rangos["phylum"],
        "gbif_class": rangos["class"],
        "gbif_order": rangos["order"],
        "gbif_family": rangos["family"],
        "gbif_genus": rangos["genus"],
        "gbif_subgenus": rangos["subgenus"],
        "gbif_uri": gbif_uri,
        "gbif_discrepancy": discrepancy_str,
        "gbif_taxonomy": taxonomy
    }


def verificar_lote(nombres_limpios, max_workers: int = 6, progress_callback=None, locales_por_nombre=None) -> dict:
    """
    Verifica en paralelo una lista de nombres ya limpios.
    locales_por_nombre (opcional): {nombre_limpio: dict de rangos locales}.
    Devuelve {nombre_limpio: ficha de verificar_con_gbif}.
    """
    resultados: dict[str, dict] = {}
    unicos = [n for n in dict.fromkeys(nombres_limpios) if n]
    locales_por_nombre = locales_por_nombre or {}

    if not unicos:
        return resultados

    total = len(unicos)
    completados = 0

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = {}
        for n in unicos:
            gen, sp, infra, original = _dividir_nombre(n)
            futures[executor.submit(
                verificar_con_gbif, gen, sp, infra, original, locales_por_nombre.get(n)
            )] = n

        for fut in as_completed(futures):
            nombre = futures[fut]
            try:
                resultados[nombre] = fut.result()
            except Exception as ex:
                resultados[nombre] = {
                    "gbif_matchType": "ERROR",
                    "gbif_status": "",
                    "gbif_usageKey": "",
                    "gbif_scientificName": "",
                    "gbif_kingdom": "",
                    "gbif_phylum": "",
                    "gbif_class": "",
                    "gbif_order": "",
                    "gbif_family": "",
                    "gbif_genus": "",
                    "gbif_subgenus": "",
                    "gbif_uri": "",
                    "gbif_discrepancy": f"Error de verificación: {ex}",
                    "gbif_taxonomy": ""
                }
            completados += 1
            if progress_callback:
                try:
                    progress_callback(completados, total)
                except Exception:
                    pass

    return resultados


def _dividir_nombre(nombre_limpio: str) -> tuple[str, str, str, str]:
    """Divide un nombre limpio en (gen, sp, infra, original) para verificar_con_gbif."""
    from taxa_parser import n_gen, n_sp, n_infra
    return (n_gen(nombre_limpio), n_sp(nombre_limpio), n_infra(nombre_limpio), nombre_limpio)