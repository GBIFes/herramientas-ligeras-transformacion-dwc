"""
dwca_transformer.py
===================
Transformador especializado en el Proceso LESRPE (MITECO).
Particiona y genera el estándar Darwin Core completo con:
- Captura robusta y flexible de `dataset_acronym` para los prefijos de IDs.
- Uso dinámico de `measurement_type` seleccionado en la UI.
- Filtrado estricto de registros nulos y a nivel genérico (scientificName con espacios).
- Sincronización de parámetros de identificación en Core y Extensiones.
- Nombres comunes obtenidos de la vista `v_nombrescomunes` de la API EIDOS
  (en sustitución del scraping HTML de las fichas web).
- Paquete ZIP con `meta.xml`, requisito para un DwC-A válido.
"""

from __future__ import annotations
import zipfile
import re
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import pandas as pd
import requests

from config import BASE_URL_API, codigo_idioma, crear_sesion_robusta

# Configuración de logging para diagnóstico en tiempo real
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("DwCaTransformer")


SPANISH_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}


class DwCaTransformer:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = crear_sesion_robusta()

    def parse_norm_date(self, norma_str: str) -> str:
        """
        Parsea la fecha de norma según las reglas de negocio LESRPE.
        """
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

    def calcular_presencia_territorial(self, row: pd.Series) -> tuple[int, int, int]:
        """
        Aplica las reglas estrictas de distribución territorial y exclusiones.
        """
        obs_pob = str(row.get("observacionespoblacion", "")).lower().strip()
        estado_legal = str(row.get("estadolegal", "")).lower()
        ambito = str(row.get("ambito", "")).lower()
        texto = f"{obs_pob} {estado_legal} {ambito}"

        if not obs_pob or obs_pob in ["nan", "none", ""] or obs_pob == "incluido":
            return 1, 0, 0

        if ("todas" in obs_pob or "nacional" in obs_pob) and "excepto" not in texto:
            return 1, 1, 1

        if "excepto" in texto:
            if ("canarias" in texto and "baleares" in texto) or ("canarias y baleares" in texto):
                return 1, 0, 0
            elif "canarias" in texto and not any(isla in texto for isla in ["gran canaria", "tenerife", "lanzarote", "fuerteventura", "la palma", "la gomera", "el hierro"]):
                return 1, 0, 1
            elif "baleares" in texto and not any(isla in texto for isla in ["mallorca", "menorca", "ibiza", "formentera"]):
                return 1, 1, 0
            else:
                if any(isla in texto for isla in ["gran canaria", "tenerife", "lanzarote", "fuerteventura", "la palma", "la gomera", "el hierro"]):
                    return 0, 1, 0
                elif any(isla in texto for isla in ["mallorca", "menorca", "ibiza", "formentera"]):
                    return 0, 0, 1

        has_peninsula = any(w in texto for w in ["península", "peninsular", "andalucía", "castilla", "extremadura", "galicia", "duero", "guadiana", "guadalquivir", "ebro", "sistema", "atlántico", "mediterráneo", "ríos", "estrecho", "ceuta", "melilla"])
        has_canarias = "canarias" in texto or "gran canaria" in texto or "tenerife" in texto
        has_baleares = "baleares" in texto or "menorca" in texto or "mallorca" in texto or "ibiza" in texto

        if has_canarias and not has_peninsula and not has_baleares:
            return 0, 1, 0
        if has_baleares and not has_peninsula and not has_canarias:
            return 0, 0, 1
        if has_peninsula and not has_canarias and not has_baleares:
            return 1, 0, 0

        p = 1 if has_peninsula else 0
        c = 1 if has_canarias else 0
        b = 1 if has_baleares else 0

        if p == 0 and c == 0 and b == 0:
            p = 1

        return p, c, b

    def query_gbif_species(self, scientific_name: str) -> dict:
        """
        Consulta la API pública de GBIF con un timeout estricto de 2s para evitar bloqueos.
        """
        if not scientific_name or scientific_name.lower() in ["indet.", "nan", ""]:
            return {}

        try:
            url = f"https://api.gbif.org/v1/species/match?name={requests.utils.quote(scientific_name)}"
            req = requests.Request(
                "GET", url, headers={"User-Agent": "EidosDwCaBridge/2.0"}
            ).prepare()
            with self.session.send(req, timeout=2) as response:
                data = response.json()
                if data.get("matchType") in ["EXACT", "FUZZY"] and "usageKey" in data:
                    return {
                        "taxonKey": f"https://www.gbif.org/species/{data['usageKey']}",
                        "kingdom": data.get("kingdom", ""),
                        "class": data.get("class", ""),
                        "family": data.get("family", ""),
                        "genus": data.get("genus", ""),
                        "taxonomicStatus": data.get("status", "")
                    }
        except Exception as e:
            logger.warning(f"Advertencia: No se pudo consultar GBIF para '{scientific_name}' ({e}). Continuando...")
        return {}

    def fetch_vernacular_api(self, idtaxon, max_retries: int = 3) -> list[tuple[str, str]]:
        """
        Obtiene los nombres comunes de un taxón desde la vista `v_nombrescomunes`
        de la API EIDOS, con reintentos y timeout acotado.
        Devuelve una lista de tuplas (idioma, nombre).
        """
        url = f"{BASE_URL_API}/v_nombrescomunes"

        for attempt in range(max_retries):
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
                logger.warning(f"Intento {attempt + 1}/{max_retries} fallido (v_nombrescomunes, idtaxon={idtaxon}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Fallo definitivo al obtener nombres comunes de idtaxon={idtaxon} tras {max_retries} intentos.")
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
        **kwargs
    ) -> Path:
        """
        Ejecuta el proceso completo LESRPE aplicando filtros estrictos, sincronización y
        capturando explícitamente los parámetros de la UI (`dataset_acronym`, `measurement_type`, etc.).
        """
        if df.empty:
            raise ValueError("El DataFrame suministrado está vacío.")

        # Resolución robusta del acrónimo / prefijo desde cualquier variante enviada por la UI
        resolved_mof_prefix = (
            dataset_acronym or
            mof_prefix or
            kwargs.get("dataset_acronym") or
            kwargs.get("mof_prefix") or
            kwargs.get("prefix_mof") or
            kwargs.get("measurement_prefix") or
            kwargs.get("mof_id_prefix") or
            kwargs.get("prefix") or
            "LESRPE"
        ).strip()

        resolved_vn_prefix = (
            dataset_acronym or
            vn_prefix or
            kwargs.get("dataset_acronym") or
            kwargs.get("vn_prefix") or
            kwargs.get("prefix_vn") or
            kwargs.get("vernacular_prefix") or
            kwargs.get("vn_id_prefix") or
            kwargs.get("prefix") or
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

        safe_progress(5, "Iniciando validación, filtrado y sincronización de parámetros...")

        df_work = df.copy()

        if manual_estado_legal:
            df_work["estadolegal"] = manual_estado_legal

        # 1. Filtrado estricto para descartar registros con campos taxonómicos nulos o vacíos
        name_check_cols = ['idnombre_aceptado', 'nombre_aceptado', 'idnombre_dat', 'nombre_en_dataset']
        existing_cols_to_check = [c for c in name_check_cols if c in df_work.columns]

        if existing_cols_to_check:
            for col in existing_cols_to_check:
                s_col = df_work[col].astype(str).str.strip().str.lower()
                valid_mask = s_col.notna() & (~s_col.isin(["nan", "none", "", "null", "nat"]))
                df_work = df_work[valid_mask].copy()

        if df_work.empty:
            raise ValueError("No quedan registros tras aplicar el filtro de exclusión de nombres/identificadores vacíos.")

        # 2. FILTRO ESTRUCTURAL: Descartar registros a nivel genérico (scientificName sin espacios)
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
            raise ValueError("No quedan registros tras filtrar los taxones a nivel genérico (se requiere especie con epíteto).")

        if "idtaxon" not in df_work.columns and "id_taxon" in df_work.columns:
            df_work["idtaxon"] = df_work["id_taxon"]

        group_col = "idtaxon" if "idtaxon" in df_work.columns else df_work.columns[0]
        grouped = df_work.groupby(group_col).first().reset_index()

        # ==========================================
        # 1. CONSTRUCCIÓN DE TAXON.CSV (CORE)
        # ==========================================
        total_taxa_taxon = len(grouped)
        safe_progress(20, f"Construyendo metadatos taxonómicos (0/{total_taxa_taxon}) [taxon.csv]...")

        taxon_records = []
        taxon_id_map = {}
        idx_t = 0

        for _, row in grouped.iterrows():
            idx_t += 1
            id_t = row.get(group_col)
            id_t_str = str(id_t) if id_t is not None else ""
            taxon_id = f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{id_t_str}"

            taxon_id_map[id_t] = taxon_id

            sci_name = str(row.get("nombre_aceptado", row.get("scientificName", row.get("nombre", "")))).strip()
            verb_id = str(row.get("nombre_en_dataset", row.get("verbatimIdentification", sci_name))).strip()

            if idx_t % max(1, (total_taxa_taxon // 10)) == 0 or idx_t == total_taxa_taxon:
                pct_taxon = 20 + int(15 * (idx_t / total_taxa_taxon))
                safe_progress(pct_taxon, f"Procesando taxón ({idx_t}/{total_taxa_taxon}): {sci_name[:30]}")

            dominio = str(row.get("dominio", ""))
            reino = str(row.get("reino", row.get("kingdom", "")))
            filum = str(row.get("filum", row.get("phylum", "")))
            clase = str(row.get("clase", row.get("class", "")))
            familia = str(row.get("familia", row.get("family", "")))
            subfamilia = str(row.get("subfamilia", ""))
            genero = str(row.get("genero", row.get("genus", "")))
            especie = str(row.get("especie", ""))

            higher_class = (
                f"DOMAIN:{dominio} | KINGDOM:{reino} | PHYLLUM:{filum} | "
                f"CLASS:{clase} | FAMILY:{familia} | SUBFAMILY:{subfamilia} | "
                f"GENUS:{genero} | SPECIES:{especie}"
            )

            taxon_rec = {
                "taxonID": taxon_id,
                "verbatimIdentification": verb_id,
                "scientificName": sci_name,
                "license": "CC-BY 4.0",
                "rightsHolder": "Ministerio para la Transición Ecológica y el Reto Demográfico",
                "institutionCode": "MITECO",
                "modified": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "higherClassification": higher_class,
                "kingdom": reino,
                "class": clase,
                "family": familia,
                "genus": genero,
                "subgenus": str(row.get("subgenus", "")),
                "genericName": str(row.get("genericName", "")),
                "infragenericEpithet": str(row.get("infragenericEpithet", "")),
                "specificEpithet": str(row.get("specificEpithet", "")),
                "verbatimTaxonRank": str(row.get("verbatimTaxonRank", "")),
                "infraspecificEpithet": str(row.get("infraspecificEpithet", "")),
                "scientificNameAuthorship": str(row.get("scientificNameAuthoship", row.get("scientificNameAuthorship", ""))),
                "taxonomicStatus": str(row.get("taxonomicStatus", "")),
                "taxonRemarks": str(row.get("taxonRemarks", "")),
                "nomenclaturalCode": str(row.get("nomenclaturalCode", "")),
                "taxonKey": ""
            }

            if sci_name:
                gbif_data = self.query_gbif_species(sci_name)
                if gbif_data:
                    taxon_rec["taxonKey"] = gbif_data.get("taxonKey", "")
                    if not taxon_rec["kingdom"] and gbif_data.get("kingdom"):
                        taxon_rec["kingdom"] = gbif_data["kingdom"]
                    if not taxon_rec["class"] and gbif_data.get("class"):
                        taxon_rec["class"] = gbif_data["class"]
                    if not taxon_rec["family"] and gbif_data.get("family"):
                        taxon_rec["family"] = gbif_data["family"]
                    if not taxon_rec["genus"] and gbif_data.get("genus"):
                        taxon_rec["genus"] = gbif_data["genus"]
                    if not taxon_rec["taxonomicStatus"] and gbif_data.get("taxonomicStatus"):
                        taxon_rec["taxonomicStatus"] = gbif_data["taxonomicStatus"]

            taxon_records.append(taxon_rec)

        taxon_df = pd.DataFrame(taxon_records)

        # ==========================================
        # 2. CONSTRUCCIÓN DE MEASUREMENTOFFACTS.CSV (EXTENSIÓN 1)
        # ==========================================
        safe_progress(40, "Generando estados legales y distribución territorial sincronizados (measurementOfFacts.csv)...")

        valid_taxon_ids = set(taxon_id_map.keys())
        df_vigentes = df_work[
            df_work["idvigente"].astype(str).isin(["1", "1.0"]) &
            df_work[group_col].isin(valid_taxon_ids)
        ].copy()

        subset_dedup = [group_col, 'estadolegal', 'norma', 'observacionespoblacion']
        existing_subcols = [c for c in subset_dedup if c in df_vigentes.columns]
        if existing_subcols:
            df_vigentes = df_vigentes.drop_duplicates(subset=existing_subcols).copy()

        fact_records = []
        n_mof = 1
        for _, row in df_vigentes.iterrows():
            estado_legal = str(row.get("estadolegal", row.get("estado_legal", ""))).strip()
            norma = str(row.get("norma", "")).strip()
            obs_pob = row.get("observacionespoblacion", row.get("observaciones_poblacion", ""))

            if not estado_legal and not norma and (not obs_pob or str(obs_pob).lower() in ["nan", "none", ""]):
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

            peninsula_val, canarias_val, baleares_val = self.calcular_presencia_territorial(row)

            meas_value = estado_legal
            if obs_pob is not None:
                obs_str = str(obs_pob).strip()
                if obs_str and obs_str.lower() not in ["nan", "none", ""]:
                    meas_value = f"{estado_legal}. {obs_str}."

            id_t = row.get(group_col)
            t_id = taxon_id_map.get(id_t, f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{id_t}")

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

        # ==========================================
        # 3. NOMBRES VERNÁCULOS DESDE LA API (VERNACULARNAME.CSV)
        # ==========================================
        vernacular_records = []
        n_vn = 1
        total_taxa = len(taxon_id_map)
        completed_count = 0
        progress_lock = threading.Lock()

        safe_progress(50, f"Consultando v_nombrescomunes en la API para {total_taxa} taxones...")

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

                    pct = 50 + int(40 * (current_done / total_taxa))
                    if current_done % max(1, (total_taxa // 20)) == 0 or current_done == total_taxa:
                        safe_progress(pct, f"Nombres vernáculos vía API ({current_done}/{total_taxa}): ID {id_t}")

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
                    logger.error(f"Error procesando futuro en hilo para taxón: {ex}")

        vernacular_df = pd.DataFrame(vernacular_records)
        if not vernacular_df.empty:
            vernacular_df = vernacular_df.drop_duplicates(subset=["taxonID", "vernacularName"]).reset_index(drop=True)

        # ==========================================
        # 4. EXPORTACIÓN A CSV Y EMPAQUETADO ZIP
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

        # meta.xml: obligatorio para que el ZIP sea un DwC-A válido
        row_type_mof = "http://rs.gbif.org/terms/1.0/MeasurementOrFact"
        row_type_vn = "http://rs.gbif.org/terms/1.0/VernacularName"
        meta_lines = [
            '<archive xmlns="http://rs.tdwg.org/dwc/text/">',
            '  <core encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" ignoreHeaderLines="1">',
            '    <files><location>taxon.csv</location></files>',
            '    <id name="taxonID" />',
            '    <field index="0" term="http://rs.tdwg.org/dwc/terms/taxonID" />',
            '    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName" />',
            '    <field index="3" term="http://rs.tdwg.org/dwc/terms/license" />',
            '    <field index="4" term="http://rs.tdwg.org/dwc/terms/rightsHolder" />',
            '    <field index="5" term="http://rs.tdwg.org/dwc/terms/institutionCode" />',
            '    <field index="6" term="http://purl.org/dc/terms/modified" />',
            '    <field index="7" term="http://rs.tdwg.org/dwc/terms/higherClassification" />',
            '    <field index="8" term="http://rs.tdwg.org/dwc/terms/kingdom" />',
            '    <field index="9" term="http://rs.tdwg.org/dwc/terms/class" />',
            '    <field index="10" term="http://rs.tdwg.org/dwc/terms/family" />',
            '    <field index="11" term="http://rs.tdwg.org/dwc/terms/genus" />',
            '    <field index="12" term="http://rs.tdwg.org/dwc/terms/subgenus" />',
            '    <field index="16" term="http://rs.tdwg.org/dwc/terms/specificEpithet" />',
            '    <field index="18" term="http://rs.tdwg.org/dwc/terms/infraspecificEpithet" />',
            '    <field index="19" term="http://rs.tdwg.org/dwc/terms/scientificNameAuthorship" />',
            '    <field index="20" term="http://rs.tdwg.org/dwc/terms/taxonomicStatus" />',
            "  </core>",
        ]
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