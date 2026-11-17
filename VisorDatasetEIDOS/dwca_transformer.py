"""
dwca_transformer.py
===================
Transformador especializado y automatizado para la generación de Archivos Darwin Core (DwC-A)
a partir de datasets de EIDOS / MITECO (LESRPE y CEEI).
Integra de forma nativa:
- Sustitución automática de scientificName por el nombre completo con autoría de GBIF.
- Extracción y seguimiento dinámico de la jerarquía taxonómica completa vía taxa_gbif.
- Limpieza de prefijos descriptivos ("Género", "Especie", etc.).
- Restricción estricta MoF-Core y lógica territorial parametrizable.

Correcciones:
- La jerarquía taxonómica se toma de las claves gbif_kingdom ... gbif_subgenus
  que taxa_gbif ahora devuelve (antes no existían y esos campos salían vacíos).
- higherClassification en formato DwC: solo nombres de rango separados por " | ".
- El bloque de ascenso por padres se elimina de aquí: lo hace taxa_gbif.
- Se retira la "validación geométrica" hardcodeada de rangos: el linaje viene
  del backbone de GBIF, que es la fuente autoritativa.
"""

from __future__ import annotations
import time
import zipfile
import re
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import pandas as pd
import requests

from config import BASE_URL_API, codigo_idioma, crear_sesion_robusta

from taxa_parser import (
    n_gen, n_sub_gen, n_sp, n_cat_infra, n_infra, n_autor, n_autinfra,
    codigo_nombre_cientifico, rango_taxonomico_simple,
    n_hibrido_generico, n_hibrido_especifico, n_cultivar, limpiar_cache
)
from taxa_gbif import verificar_con_gbif, consultar_especie_gbif, limpiar_cache_gbif

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("DwCaTransformer")


SPANISH_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}


TERM_MAP = {
    "taxonID": "http://rs.tdwg.org/dwc/terms/taxonID",
    "verbatimIdentification": "http://rs.tdwg.org/dwc/terms/verbatimIdentification",
    "scientificName": "http://rs.tdwg.org/dwc/terms/scientificName",
    "license": "http://rs.tdwg.org/dwc/terms/license",
    "rightsHolder": "http://rs.tdwg.org/dwc/terms/rightsHolder",
    "institutionCode": "http://rs.tdwg.org/dwc/terms/institutionCode",
    "modified": "http://purl.org/dc/terms/modified",
    "higherClassification": "http://rs.tdwg.org/dwc/terms/higherClassification",
    "kingdom": "http://rs.tdwg.org/dwc/terms/kingdom",
    "phylum": "http://rs.tdwg.org/dwc/terms/phylum",
    "class": "http://rs.tdwg.org/dwc/terms/class",
    "order": "http://rs.tdwg.org/dwc/terms/order",
    "family": "http://rs.tdwg.org/dwc/terms/family",
    "genus": "http://rs.tdwg.org/dwc/terms/genus",
    "subgenus": "http://rs.tdwg.org/dwc/terms/subgenus",
    "genericName": "http://rs.tdwg.org/dwc/terms/genericName",
    "infragenericEpithet": "http://rs.tdwg.org/dwc/terms/infragenericEpithet",
    "specificEpithet": "http://rs.tdwg.org/dwc/terms/specificEpithet",
    "verbatimTaxonRank": "http://rs.tdwg.org/dwc/terms/verbatimTaxonRank",
    "infraspecificEpithet": "http://rs.tdwg.org/dwc/terms/infraspecificEpithet",
    "scientificNameAuthorship": "http://rs.tdwg.org/dwc/terms/scientificNameAuthorship",
    "taxonomicStatus": "http://rs.tdwg.org/dwc/terms/taxonomicStatus",
    "taxonRemarks": "http://rs.tdwg.org/dwc/terms/taxonRemarks",
    "nomenclaturalCode": "http://rs.tdwg.org/dwc/terms/nomenclaturalCode",
    "taxonKey": "http://rs.gbif.org/terms/1.0/taxonKey",
    "references": "http://purl.org/dc/terms/references",
}


def core_field_lines(df: pd.DataFrame) -> list[str]:
    lines = ['    <id name="taxonID" />']
    for i, col in enumerate(df.columns):
        term = TERM_MAP.get(col)
        if term:
            lines.append(f'    <field index="{i}" term="{term}" />')
    return lines


def _clean(v) -> str:
    s = "" if v is None else str(v).strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def limpiar_prefijo_taxonomico(texto: str) -> str:
    """Elimina prefijos descriptivos iniciales (Género, Especie, etc.) para aislar el nombre científico."""
    if not texto:
        return ""
    s = str(texto).strip()
    prefijos = ["género", "genero", "especie", "subespecie", "variedad", "forma", "taxón", "taxon"]
    palabras = s.split()
    while palabras and palabras[0].lower().strip(".:") in prefijos:
        palabras = palabras[1:]
    return " ".join(palabras).strip()


class DwCaTransformer:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = crear_sesion_robusta()

    def parse_norm_date(self, norma_str: str) -> str:
        if not norma_str or not isinstance(norma_str, str):
            return ""

        try:
            right_slash_idx = norma_str.rfind("/")
            left_comma_idx = norma_str.find(",")

            year = ""
            if right_slash_idx != -1 and left_comma_idx != -1 and right_slash_idx < left_comma_idx:
                year = norma_str[right_slash_idx + 1:left_comma_idx].strip()

            if not year or not year.isdigit() or len(year) != 4:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', norma_str)
                year = year_match.group(1) if year_match else ""

            day_val = 1
            month = "01"

            date_match = re.search(r'(\d{1,2})\s+de\s+([a-záéíóúñ]+)', norma_str, re.IGNORECASE)
            if date_match:
                d_val = int(date_match.group(1))
                day_val = d_val + 1
                m_str = date_match.group(2).lower()
                if m_str in SPANISH_MONTHS:
                    month = SPANISH_MONTHS[m_str]

            day_str = str(day_val).zfill(2)
            if year:
                return f"{year}-{month}-{day_str}"
        except Exception:
            pass

        return ""

    def calcular_presencia_territorial(self, row: pd.Series, default_national_scope: bool = False) -> tuple[int, int, int]:
        obs_pob = str(row.get("observacionespoblacion", "")).lower().strip()
        estado_legal = str(row.get("estadolegal", "")).lower()
        ambito = str(row.get("ambito", "")).lower()
        texto = f"{obs_pob} {estado_legal} {ambito}"

        if "excepto" in texto or "salvo" in texto or "excluyendo" in texto:
            if ("canarias" in texto and "baleares" in texto) or ("canarias y baleares" in texto):
                return 1, 0, 0
            elif "canarias" in texto:
                return 1, 0, 1
            elif "baleares" in texto:
                return 1, 1, 0

        has_peninsula = any(w in texto for w in [
            "península", "peninsular", "peninsula", "andalucía", "castilla", "extremadura",
            "galicia", "duero", "guadiana", "guadalquivir", "ebro", "sistema",
            "atlántico", "mediterráneo", "ríos", "estrecho", "ceuta", "melilla", "ibérica", "iberica"
        ])

        has_canarias = any(w in texto for w in [
            "canarias", "gran canaria", "tenerife", "lanzarote", "fuerteventura",
            "la palma", "la gomera", "el hierro"
        ])

        has_baleares = any(w in texto for w in [
            "baleares", "mallorca", "menorca", "ibiza", "formentera"
        ])

        mencion_explicita = has_peninsula or has_canarias or has_baleares

        if mencion_explicita:
            p = 1 if has_peninsula else 0
            c = 1 if has_canarias else 0
            b = 1 if has_baleares else 0
            return p, c, b

        if not obs_pob or obs_pob in ["nan", "none", ""] or obs_pob == "incluido":
            if default_national_scope:
                return 1, 1, 1
            return 1, 0, 0

        if "todas" in obs_pob or "nacional" in obs_pob:
            return 1, 1, 1

        p = 1 if default_national_scope else 1
        c = 1 if default_national_scope else 0
        b = 1 if default_national_scope else 0
        return p, c, b

    def fetch_vernacular_api(self, idtaxon, max_retries: int = 6) -> list[tuple[str, str]]:
        url = f"{BASE_URL_API}/v_nombrescomunes"

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params={"idtaxon": f"eq.{idtaxon}"},
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data or []:
                    idioma = str(
                        item.get("idioma")
                        or item.get("language")
                        or item.get("lenguaje")
                        or ""
                    ).strip()
                    nombre = str(
                        item.get("nombrecomun")
                        or item.get("nombre_comun")
                        or item.get("nombre")
                        or item.get("vernacularname")
                        or ""
                    ).strip()

                    if nombre and idioma.lower() not in ("idioma", "nombre", "language"):
                        results.append((idioma, nombre))
                return results
            except Exception as e:
                if attempt < max_retries:
                    wait = min(30, 2 ** attempt)
                    time.sleep(wait)
                else:
                    logger.error(f"Fallo definitivo al obtener nombres comunes de idtaxon={idtaxon}.")
        return []

    def transform_and_export(
        self,
        df: pd.DataFrame,
        base_name: str = "lesrpe_dwca",
        progress_callback=None,
        mof_prefix: str | None = None,
        vn_prefix: str | None = None,
        measurement_type: str | None = None,
        dataset_acronym: str | None = None,
        default_national_scope: bool = False,
        **kwargs
    ) -> Path:
        if df.empty:
            raise ValueError("El DataFrame suministrado está vacío.")

        limpiar_cache()
        limpiar_cache_gbif()

        resolved_mof_prefix = (
            dataset_acronym or
            mof_prefix or
            kwargs.get("dataset_acronym") or
            kwargs.get("mof_prefix") or
            "LESRPE"
        ).strip()

        resolved_vn_prefix = (
            dataset_acronym or
            vn_prefix or
            kwargs.get("dataset_acronym") or
            kwargs.get("vn_prefix") or
            "LESRPE"
        ).strip()

        resolved_measurement_type = (
            measurement_type or
            kwargs.get("measurement_type") or
            "Legal protection status"
        ).strip()

        manual_estado_legal = kwargs.get("estado_legal") or kwargs.get("manual_estado_legal") or kwargs.get("estadoLegal")

        def safe_progress(pct, msg):
            logger.info(f"[PROGRESO {pct}%] {msg}")
            if progress_callback:
                try:
                    try:
                        progress_callback(pct, msg)
                    except TypeError:
                        progress_callback(pct)
                except Exception as ex:
                    logger.error(f"Error en progress_callback: {ex}")

        safe_progress(5, "Iniciando validación, parseo y filtrado...")

        df_work = df.copy()

        if manual_estado_legal:
            df_work["estadolegal"] = manual_estado_legal

        name_check_cols = ['idnombre_aceptado', 'nombre_aceptado', 'idnombre_dat', 'nombre_en_dataset']
        existing_cols_to_check = [c for c in name_check_cols if c in df_work.columns]

        if existing_cols_to_check:
            for col in existing_cols_to_check:
                s_col = df_work[col].astype(str).str.strip().str.lower()
                valid_mask = s_col.notna() & (~s_col.isin(["nan", "none", "", "null", "nat"]))
                df_work = df_work[valid_mask].copy()

        if df_work.empty:
            raise ValueError("No quedan registros tras aplicar el filtro de exclusión de nombres vacíos.")

        sci_col_candidates = ['nombre_aceptado', 'scientificName', 'nombre']
        sci_target_col = next((c for c in sci_col_candidates if c in df_work.columns), None)

        if sci_target_col:
            def tiene_especie(val):
                if not val or not isinstance(val, str):
                    return False
                return " " in val.strip()

            mask_especie = df_work[sci_target_col].apply(tiene_especie)
            df_work = df_work[mask_especie].copy()

        if df_work.empty:
            raise ValueError("No quedan registros tras filtrar los taxones a nivel genérico.")

        if "idtaxon" not in df_work.columns and "id_taxon" in df_work.columns:
            df_work["idtaxon"] = df_work["id_taxon"]

        group_col = "idtaxon" if "idtaxon" in df_work.columns else df_work.columns[0]

        # ==========================================
        # 1. CONSTRUCCIÓN DE MEASUREMENTOFFACTS.CSV
        # ==========================================
        safe_progress(20, "Generando estados legales y distribución territorial [measurementOfFacts.csv]...")

        if "idvigente" in df_work.columns:
            mask_vig = df_work["idvigente"].astype(str).isin(["1", "1.0"])
        else:
            mask_vig = pd.Series(True, index=df_work.index)

        df_vigentes = df_work[mask_vig].copy()

        subset_dedup = [group_col, 'estadolegal', 'norma', 'observacionespoblacion']
        existing_subcols = [c for c in subset_dedup if c in df_vigentes.columns]
        if existing_subcols:
            df_vigentes = df_vigentes.drop_duplicates(subset=existing_subcols).copy()

        fact_records = []
        valid_taxon_ids_with_mof = set()
        n_mof = 1

        for _, row in df_vigentes.iterrows():
            estado_legal = str(row.get("estadolegal", row.get("estado_legal", ""))).strip()

            if "excluido" in estado_legal.lower():
                continue

            norma = str(row.get("norma", "")).strip()
            obs_pob = row.get("observacionespoblacion", row.get("observaciones_poblacion", ""))

            if not estado_legal and not norma and (not obs_pob or str(obs_pob).lower() in ["nan", "none", ""]):
                continue

            peninsula_val, canarias_val, baleares_val = self.calcular_presencia_territorial(row, default_national_scope=default_national_scope)

            if (peninsula_val + canarias_val + baleares_val) == 0:
                continue

            lower_el = estado_legal.lower()
            if "peligro" in lower_el:
                b = 3
            elif "vulnerable" in lower_el:
                b = 2
            elif "protección especial" in lower_el or "lesrpe" in lower_el:
                b = 1
            else:
                b = 1 if estado_legal else 0

            valor = b

            meas_value = estado_legal
            if obs_pob is not None:
                obs_str = str(obs_pob).strip()
                if obs_str and obs_str.lower() not in ["nan", "none", ""]:
                    meas_value = f"{estado_legal}. {obs_str}."

            id_t = row.get(group_col)
            if id_t is None or str(id_t).strip().lower() in ["nan", "none", ""]:
                continue

            valid_taxon_ids_with_mof.add(id_t)
            t_id = f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{str(id_t).strip()}"

            fecha_alta_raw = row.get("fecha_alta", "")
            if pd.notna(fecha_alta_raw) and str(fecha_alta_raw).strip() not in ["", "nan", "None"]:
                meas_date = str(fecha_alta_raw).strip()
            else:
                meas_date = self.parse_norm_date(norma)

            fact_records.append({
                "measurementID": f"{resolved_mof_prefix}-{id_t}-{n_mof}",
                "taxonID": t_id,
                "measurementType": resolved_measurement_type,
                "measurementValue": meas_value,
                "measurementMethod": norma,
                "measurementDeterminedDate": meas_date,
                "idevigente": "1",
                "Peninsula": peninsula_val,
                "Canarias": canarias_val,
                "Baleares": baleares_val,
                "fechaBaja": "",
                "valor": valor
            })
            n_mof += 1

        measurements_df = pd.DataFrame(fact_records)

        if measurements_df.empty:
            raise ValueError("No se han generado registros válidos en measurementOfFacts.csv tras aplicar los filtros.")

        # ==========================================
        # 2. CONSTRUCCIÓN DE TAXON.CSV (JERARQUÍA GBIF VÍA taxa_gbif)
        # ==========================================
        safe_progress(40, "Aplicando parseo taxonómico y contraste dinámico con GBIF...")

        grouped = (
            df_work[df_work[group_col].isin(valid_taxon_ids_with_mof)]
            .drop_duplicates(subset=[group_col], keep="first")
            .reset_index(drop=True)
        )

        safe_progress(50, "Construyendo metadatos taxonómicos normalizados [taxon.csv]...")

        taxon_records = []
        taxon_id_map = {}
        idx_t = 0
        total_taxa_taxon = len(grouped)

        for _, row in grouped.iterrows():
            idx_t += 1
            id_t = row.get(group_col)
            id_t_str = str(id_t) if id_t is not None else ""
            taxon_id = f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{id_t_str}"

            taxon_id_map[id_t] = taxon_id

            sci_name_raw = str(row.get("nombre_aceptado", row.get("scientificName", row.get("nombre", "")))).strip()
            verb_id_raw = str(row.get("verbatimIdentification", row.get("nombre_en_dataset", ""))).strip()

            scientific_name = sci_name_raw if (sci_name_raw and sci_name_raw.lower() not in ("nan", "none", "", "null")) else verb_id_raw
            verbatim_id = verb_id_raw if (verb_id_raw and verb_id_raw.lower() not in ("nan", "none", "", "null")) else sci_name_raw

            clean_sci = limpiar_prefijo_taxonomico(scientific_name)
            clean_verb = limpiar_prefijo_taxonomico(verbatim_id)

            gen_sci = n_gen(clean_sci)
            sp_sci = n_sp(clean_sci)
            gen_verb = n_gen(clean_verb)
            sp_verb = n_sp(clean_verb)

            mismo_taxon = (gen_sci and gen_verb and gen_sci.lower() == gen_verb.lower() and
                           sp_sci and sp_verb and sp_sci.lower() == sp_verb.lower())

            if mismo_taxon:
                base_name_for_parsing = verbatim_id if len(verbatim_id) >= len(scientific_name) else scientific_name
            else:
                base_name_for_parsing = scientific_name

            clean_text_for_parsing = limpiar_prefijo_taxonomico(base_name_for_parsing)

            # 1. Parseo local con taxa_parser
            p_gen = n_gen(clean_text_for_parsing)
            p_subgen = n_sub_gen(clean_text_for_parsing)
            p_sp = n_sp(clean_text_for_parsing)
            p_cat_infra = n_cat_infra(clean_text_for_parsing)
            p_infra = n_infra(clean_text_for_parsing)
            p_autor_sp = n_autor(clean_text_for_parsing)
            p_autor_infra = n_autinfra(clean_text_for_parsing)
            p_authorship_dwc = p_autor_infra if p_autor_infra else p_autor_sp
            p_codigo = codigo_nombre_cientifico(clean_text_for_parsing).replace("ICN", "ICBN")
            p_rango = rango_taxonomico_simple(clean_text_for_parsing)

            # 2. Contraste con GBIF (match + jerarquía completa vía taxa_gbif)
            gbif_res = verificar_con_gbif(p_gen, p_sp, p_infra, clean_text_for_parsing)
            usage_key = gbif_res.get("gbif_usageKey")
            gbif_sci_name = gbif_res.get("gbif_scientificName", "")

            if gbif_sci_name and not p_authorship_dwc:
                gbif_autor_test = n_autor(gbif_sci_name)
                if gbif_autor_test:
                    scientific_name = gbif_sci_name
                    p_authorship_dwc = gbif_autor_test

            if not mismo_taxon and gbif_sci_name:
                clean_text_for_parsing = gbif_sci_name
                p_gen = n_gen(clean_text_for_parsing) or p_gen
                p_sp = n_sp(clean_text_for_parsing) or p_sp
                p_authorship_dwc = n_autor(clean_text_for_parsing) or p_authorship_dwc

            # Jerarquía: claves gbif_* de taxa_gbif, con los valores locales
            # de EIDOS como respaldo.
            gbif_kingdom = _clean(gbif_res.get("gbif_kingdom") or row.get("reino", row.get("kingdom")))
            gbif_phylum = _clean(gbif_res.get("gbif_phylum") or row.get("filum", row.get("phylum")))
            gbif_class = _clean(gbif_res.get("gbif_class") or row.get("clase", row.get("class")))
            gbif_order = _clean(gbif_res.get("gbif_order") or row.get("orden", row.get("order")))
            gbif_family = _clean(gbif_res.get("gbif_family") or row.get("familia", row.get("family")))
            gbif_genus = _clean(gbif_res.get("gbif_genus") or row.get("genero", row.get("genus")) or p_gen)
            gbif_subgenus = _clean(gbif_res.get("gbif_subgenus") or p_subgen)

            # higherClassification en formato DwC: solo nombres, separados por " | "
            hierarchy_parts = [
                v for v in (gbif_kingdom, gbif_phylum, gbif_class, gbif_order,
                            gbif_family, gbif_genus, gbif_subgenus) if v
            ]
            higher_class = " | ".join(hierarchy_parts)

            tax_status = _clean(row.get("taxonomicStatus")) or gbif_res.get("gbif_status", "")
            nom_code = p_codigo if p_codigo != "Indeterminado" else "ICBN"
            gbif_link = f"https://www.gbif.org/species/{usage_key}" if usage_key else ""

            taxon_rec = {
                "taxonID": taxon_id,
                "verbatimIdentification": verbatim_id,
                "scientificName": scientific_name,
                "license": "CC-BY 4.0",
                "rightsHolder": "Ministerio para la Transición Ecológica y el Reto Demográfico",
                "institutionCode": "MITECO",
                "modified": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "higherClassification": higher_class,
                "kingdom": gbif_kingdom,
                "phylum": gbif_phylum,
                "class": gbif_class,
                "order": gbif_order,
                "family": gbif_family,
                "genus": gbif_genus,
                "subgenus": gbif_subgenus,
                "genericName": p_gen,
                "infragenericEpithet": "",
                "specificEpithet": p_sp,
                "verbatimTaxonRank": p_rango,
                "infraspecificEpithet": p_infra,
                "scientificNameAuthorship": p_authorship_dwc,
                "taxonomicStatus": tax_status,
                "taxonRemarks": gbif_res.get("gbif_discrepancy", ""),
                "nomenclaturalCode": nom_code,
                "taxonKey": usage_key,
                "references": gbif_link,
                "p_genus": p_gen,
                "p_subgenus": p_subgen,
                "p_specificEpithet": p_sp,
                "p_infraspecificRank": p_cat_infra,
                "p_infraspecificEpithet": p_infra,
                "p_scientificNameAuthorship": p_authorship_dwc,
                "p_nomenclaturalCode": nom_code,
                "p_taxonRank": p_rango,
                "gbif_genus": gbif_res.get("gbif_genus", ""),
                "gbif_family": gbif_res.get("gbif_family", ""),
                "gbif_status": gbif_res.get("gbif_status", ""),
                "gbif_matchType": gbif_res.get("gbif_matchType", ""),
                "gbif_discrepancy": gbif_res.get("gbif_discrepancy", ""),
            }

            taxon_records.append(taxon_rec)

        taxon_df = pd.DataFrame(taxon_records)

        # ==========================================
        # 3. VERNACULARNAME.CSV
        # ==========================================
        vernacular_records = []
        n_vn = 1
        total_taxa = len(taxon_id_map)
        completed_count = 0
        progress_lock = threading.Lock()

        safe_progress(65, f"Consultando v_nombrescomunes en la API para {total_taxa} taxones...")

        def fetch_task(id_t, t_id):
            names = self.fetch_vernacular_api(id_t, max_retries=3)
            return id_t, t_id, names

        max_workers = min(10, max(4, total_taxa // 15)) if total_taxa > 0 else 4

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_taxon = {executor.submit(fetch_task, id_t, t_id): id_t for id_t, t_id in taxon_id_map.items()}

            for future in as_completed(future_to_taxon):
                with progress_lock:
                    completed_count += 1
                    current_done = completed_count

                try:
                    id_t, t_id, api_names = future.result()

                    pct = 65 + int(25 * (current_done / total_taxa))
                    if current_done % max(1, (total_taxa // 20)) == 0 or current_done == total_taxa:
                        safe_progress(pct, f"Nombres vernáculos ({current_done}/{total_taxa})")

                    for idioma_raw, nombre in api_names:
                        lang_code = codigo_idioma(idioma_raw)

                        with progress_lock:
                            non_local_vn_id = n_vn
                            n_vn += 1

                        vernacular_records.append({
                            "vernacularNameID": f"{resolved_vn_prefix}-{id_t}-{non_local_vn_id}",
                            "taxonID": t_id,
                            "vernacularName": nombre,
                            "language": lang_code,
                            "countryCode": "ES"
                        })
                except Exception as ex:
                    logger.error(f"Error procesando nombres vernáculos: {ex}")

        vernacular_df = pd.DataFrame(vernacular_records)
        if not vernacular_df.empty:
            vernacular_df = vernacular_df.drop_duplicates(subset=["taxonID", "vernacularName"]).reset_index(drop=True)

        # ==========================================
        # 4. EXPORTACIÓN
        # ==========================================
        safe_progress(92, "Estructurando Core y Extensiones y empaquetando ZIP...")

        taxon_csv = self.output_dir / "taxon.csv"
        mof_csv = self.output_dir / "measurementOfFacts.csv"
        vn_csv = self.output_dir / "vernacularName.csv"

        taxon_df.to_csv(taxon_csv, index=False, sep="\t", encoding="utf-8")

        zip_files = [("taxon.csv", taxon_csv)]

        if not measurements_df.empty:
            measurements_df.to_csv(mof_csv, index=False, sep="\t", encoding="utf-8")
            zip_files.append(("measurementOfFacts.csv", mof_csv))

        if not vernacular_df.empty:
            vernacular_df.to_csv(vn_csv, index=False, sep="\t", encoding="utf-8")
            zip_files.append(("vernacularName.csv", vn_csv))

        zip_path = self.output_dir / f"{base_name}_dwca.zip"

        row_type_mof = "http://rs.gbif.org/terms/1.0/MeasurementOrFact"
        row_type_vn = "http://rs.gbif.org/terms/1.0/VernacularName"
        meta_lines = [
            '<archive xmlns="http://rs.tdwg.org/dwc/text/">',
            '  <core encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" ignoreHeaderLines="1">',
            '    <files><location>taxon.csv</location></files>',
        ]
        meta_lines.extend(core_field_lines(taxon_df))
        meta_lines.append("  </core>")

        if not measurements_df.empty:
            meta_lines += [
                f'  <extension encoding="UTF-8" rowType="{row_type_mof}" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" ignoreHeaderLines="1">',
                '    <files><location>measurementOfFacts.csv</location></files>',
                '    <id name="taxonID" />',
                '    <field index="0" term="http://rs.tdwg.org/dwc/terms/measurementID" />',
                '    <field index="1" term="http://rs.tdwg.org/dwc/terms/taxonID" />',
                '    <field index="2" term="http://rs.tdwg.org/dwc/terms/measurementType" />',
                '    <field index="3" term="http://rs.tdwg.org/dwc/terms/measurementValue" />',
                '    <field index="4" term="http://rs.tdwg.org/dwc/terms/measurementMethod" />',
                '    <field index="5" term="http://rs.tdwg.org/dwc/terms/measurementDeterminedDate" />',
                "  </extension>",
            ]
        if not vernacular_df.empty:
            meta_lines += [
                f'  <extension encoding="UTF-8" rowType="{row_type_vn}" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" ignoreHeaderLines="1">',
                '    <files><location>vernacularName.csv</location></files>',
                '    <id name="taxonID" />',
                '    <field index="0" term="http://rs.gbif.org/terms/1.0/vernacularNameID" />',
                '    <field index="1" term="http://rs.tdwg.org/dwc/terms/taxonID" />',
                '    <field index="2" term="http://rs.tdwg.org/dwc/terms/vernacularName" />',
                '    <field index="3" term="http://purl.org/dc/terms/language" />',
                '    <field index="4" term="http://rs.tdwg.org/dwc/terms/countryCode" />',
                "  </extension>",
            ]
        meta_lines.append("</archive>")

        meta_path = self.output_dir / "meta.xml"
        meta_path.write_text("\n".join(meta_lines), encoding="utf-8")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(meta_path, arcname="meta.xml")
            for arcname, filepath in zip_files:
                if filepath.exists():
                    zipf.write(filepath, arcname=arcname)

        safe_progress(100, "¡Exportación DwC-A completada con éxito!")

        return zip_path.resolve()