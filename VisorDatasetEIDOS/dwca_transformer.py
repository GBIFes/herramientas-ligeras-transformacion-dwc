"""
dwca_transformer.py
===================
Transformador especializado en el Proceso LESRPE (MITECO).
Particiona y genera el estándar Darwin Core completo con:
- taxon.csv (con taxonKey usando www.gbif.org/species, con timeout protegido y progreso detallado)
- measurementOfFacts.csv (Filtrado estricto idvigente == 1, columnas binarias 
  Peninsula, Canarias y Baleares [1/0], con soporte para estados legales personalizados)
- vernacularName.csv (Scraping web multihilo con redundancia, reintentos y control de hilos)
"""

from __future__ import annotations
import zipfile
import re
import urllib.request
import json
import logging
from html.parser import HTMLParser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import pandas as pd
from config import IDIOMA_PAIS

# Configuración de logging para diagnóstico en tiempo real
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("DwCaTransformer")


SPANISH_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}


class EidosHtmlParser(HTMLParser):
    """
    Parser HTML nativo para extraer los nombres comunes y sus idiomas
    desde la tabla de la pestaña 'nomcomunes' en la web de EIDOS.
    """
    def __init__(self):
        super().__init__()
        self.in_nomcomunes = False
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.rows = []
        self.capture_data = False
        self.current_data = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_id = attrs_dict.get("id", "")
        tag_class = attrs_dict.get("class", "")

        if tag_id == "nomcomunes" or "nomcomunes" in tag_class:
            self.in_nomcomunes = True

        if self.in_nomcomunes and tag == "table":
            self.in_table = True

        if self.in_table and tag == "tr":
            self.in_row = True
            self.current_row = []

        if self.in_row and tag in ["th", "td"]:
            self.in_cell = True
            self.capture_data = True
            self.current_data = ""

    def handle_endtag(self, tag):
        if self.in_cell and tag in ["th", "td"]:
            self.in_cell = False
            self.capture_data = False
            self.current_row.append(self.current_data.strip())

        if self.in_row and tag == "tr":
            self.in_row = False
            if len(self.current_row) >= 2:
                self.rows.append(self.current_row)

        if self.in_table and tag == "table":
            self.in_table = False
            self.in_nomcomunes = False

    def handle_data(self, data):
        if self.capture_data:
            self.current_data += data


class DwCaTransformer:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
            url = f"https://api.gbif.org/v1/species/match?name={urllib.parse.quote(scientific_name)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'EidosDwCaBridge/2.0'})
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
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

    def scrape_with_redundancy(self, taxon_id_url: str, max_retries: int = 3) -> list[tuple[str, str]]:
        """
        Realiza scraping web de la ficha oficial con reintentos obligatorios (redundancia) y timeout acotado.
        """
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(taxon_id_url, headers={'User-Agent': 'EidosDwCaBridge/2.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    html_content = response.read().decode('utf-8', errors='ignore')
                    parser = EidosHtmlParser()
                    parser.feed(html_content)
                    
                    results = []
                    for row in parser.rows:
                        if len(row) >= 2:
                            idioma = row[0].strip()
                            nombre = row[1].strip()
                            if idioma.lower() not in ["idioma", "nombre"] and nombre:
                                results.append((idioma, nombre))
                    return results
            except Exception as e:
                logger.warning(f"Intento {attempt + 1}/{max_retries} fallido para {taxon_id_url}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Fallo definitivo al scrapear {taxon_id_url} tras {max_retries} intentos.")
        return []

    def transform_and_export(self, df: pd.DataFrame, base_name: str = "lesrpe_dwca", progress_callback=None, **kwargs) -> Path:
        """
        Ejecuta el proceso completo LESRPE con control de hilos seguro, trazas de diagnóstico y reporte de progreso fluído.
        """
        if df.empty:
            raise ValueError("El DataFrame suministrado está vacío.")

        def safe_progress(pct, msg):
            logger.info(f"[PROGRESO {pct}%] {msg}")
            if progress_callback:
                try:
                    # Soporta callbacks que acepten (pct, msg) o solo (pct)
                    try:
                        progress_callback(pct, msg)
                    except TypeError:
                        progress_callback(pct)
                except Exception as ex:
                    logger.error(f"Error en progress_callback: {ex}")

        safe_progress(5, "Iniciando validación y filtrado de datos de entrada...")

        df_work = df.copy()

        name_check_cols = ['idnombre_aceptado', 'nombre_aceptado', 'idnombre_dat', 'nombre_en_dataset']
        existing_cols_to_check = [c for c in name_check_cols if c in df_work.columns]
        
        if existing_cols_to_check:
            for col in existing_cols_to_check:
                s_col = df_work[col].astype(str).str.strip().str.lower()
                valid_mask = s_col.notna() & (~s_col.isin(["nan", "none", "", "null", "nat"]))
                df_work = df_work[valid_mask].copy()

        if df_work.empty:
            raise ValueError("No quedan registros tras aplicar el filtro de exclusión de nombres/identificadores vacíos.")

        if "idtaxon" not in df_work.columns and "id_taxon" in df_work.columns:
            df_work["idtaxon"] = df_work["id_taxon"]

        group_col = "idtaxon" if "idtaxon" in df_work.columns else df_work.columns[0]
        grouped = df_work.groupby(group_col).first().reset_index()

        # ==========================================
        # 1. CONSTRUCCIÓN DE TAXON.CSV (CON PROGRESO ACTIVO)
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
        # 2. CONSTRUCCIÓN DE MEASUREMENTOFFACTS.CSV
        # ==========================================
        safe_progress(40, "Generando estados legales y distribución territorial (measurementOfFacts.csv)...")
        
        df_vigentes = df_work[df_work["idvigente"].astype(str).isin(["1", "1.0"])].copy()

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
                "measurementID": f"LESRPEeMoF-{id_t}-{n_mof}",
                "taxonID": t_id,
                "measurementType": "Legal Protection Status",
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
        # 3. SCRAPING MULTIHILO SEGURO CON LOGS
        # ==========================================
        vernacular_records = []
        n_vn = 1
        total_taxa = len(taxon_id_map)
        completed_count = 0
        progress_lock = threading.Lock()

        safe_progress(50, f"Iniciando scraping web multihilo para {total_taxa} taxones (redundancia activa)...")

        def fetch_task(id_t, t_id):
            names = self.scrape_with_redundancy(t_id, max_retries=3)
            return id_t, t_id, names

        max_workers = min(10, max(4, total_taxa // 15)) if total_taxa > 0 else 4
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_taxon = {executor.submit(fetch_task, id_t, t_id): id_t for id_t, t_id in taxon_id_map.items()}
            
            for future in as_completed(future_to_taxon):
                with progress_lock:
                    completed_count += 1
                    current_done = completed_count
                
                try:
                    id_t, t_id, web_names = future.result()
                    
                    pct = 50 + int(40 * (current_done / total_taxa))
                    if current_done % max(1, (total_taxa // 20)) == 0 or current_done == total_taxa:
                        safe_progress(pct, f"Scraping nombres vernáculos ({current_done}/{total_taxa}): ID {id_t}")

                    for idioma_raw, nombre in web_names:
                        lang_lower = idioma_raw.lower()
                        lang_code = "es"
                        if "catalán" in lang_lower or "catalan" in lang_lower:
                            lang_code = "ca"
                        elif "euskera" in lang_lower or "vasco" in lang_lower:
                            lang_code = "eu"
                        elif "inglés" in lang_lower or "english" in lang_lower:
                            lang_code = "en"
                        elif "gallego" in lang_lower or "galego" in lang_lower:
                            lang_code = "gl"

                        with progress_lock:
                            non_local_vn_id = n_vn
                            n_vn += 1

                        vernacular_records.append({
                            "vernacularNameID": f"LESRPEVn-{id_t}-{non_local_vn_id}",
                            "taxonId": t_id,
                            "vernacularName": nombre,
                            "language": lang_code,
                            "countryCode": "ES"
                        })
                except Exception as ex:
                    logger.error(f"Error procesando futuro en hilo para taxón: {ex}")

        vernacular_df = pd.DataFrame(vernacular_records)
        if not vernacular_df.empty:
            vernacular_df = vernacular_df.drop_duplicates(subset=["taxonId", "vernacularName"]).reset_index(drop=True)

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
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for arcname, filepath in zip_files:
                if filepath.exists():
                    zipf.write(filepath, arcname=arcname)

        safe_progress(100, "¡Exportación DwC-A completada con éxito!")

        return zip_path.resolve()