"""
dwca_transformer.py
===================
Transformador especializado en el Proceso LESRPE (MITECO).
Particiona y genera el estándar Darwin Core con los nombres exactos:
- taxon.csv (con taxonKey usando www.gbif.org/species)
- measurementOfFacts.csv (filtrando por idevigente == 1 y valor compuesto con observaciones)
- vernacularName.csv
"""

from __future__ import annotations
import zipfile
import re
import urllib.request
import json
from pathlib import Path
import pandas as pd
from config import IDIOMA_PAIS


SPANISH_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}


class DwCaTransformer:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_norm_date(self, norma_str: str) -> str:
        """
        Parsea la fecha de norma según las reglas de negocio LESRPE:
        - Año: subcadena entre el primer '/' empezando por la derecha y la primera ',' empezando por la izquierda.
        - Día y Mes: extraídos del fragmento posterior a la coma, buscando el día y el mes en letra.
        - Regla especial: al día obtenido se le suma 1.
        Retorna formato YYYY-MM-DD o cadena vacía si no es parseable.
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

    def query_gbif_species(self, scientific_name: str) -> dict:
        """
        Consulta la API pública de GBIF para obtener metadatos taxonómicos y taxonKey,
        utilizando www.gbif.org/species según requerimiento.
        """
        if not scientific_name or scientific_name.lower() in ["indet.", "nan", ""]:
            return {}

        try:
            url = f"https://api.gbif.org/v1/species/match?name={urllib.parse.quote(scientific_name)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'EidosDwCaBridge/1.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
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
        except Exception:
            pass
        return {}

    def transform_and_export(self, df: pd.DataFrame, base_name: str = "lesrpe_dwca") -> Path:
        """
        Ejecuta el proceso completo LESRPE:
        1. Construcción de taxon.csv (agrupado por taxonId, EIDOS + GBIF con /species/).
        2. Construcción de measurementOfFacts.csv (filtrando por idevigente == 1 y valor compuesto con observaciones).
        3. Construcción de vernacularName.csv.
        4. Empaquetado final en archivo ZIP.
        """
        if df.empty:
            raise ValueError("El DataFrame suministrado está vacío.")

        df_work = df.copy()

        if "idtaxon" not in df_work.columns and "id_taxon" in df_work.columns:
            df_work["idtaxon"] = df_work["id_taxon"]

        group_col = "idtaxon" if "idtaxon" in df_work.columns else df_work.columns[0]
        grouped = df_work.groupby(group_col).first().reset_index()

        # ==========================================
        # 1. CONSTRUCCIÓN DE TAXON.CSV (Agrupado por taxonId)
        # ==========================================
        taxon_records = []
        taxon_id_map = {}

        for _, row in grouped.iterrows():
            id_t = row.get(group_col)
            id_t_str = str(id_t) if id_t is not None else ""
            taxon_id = f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{id_t_str}"
            
            taxon_id_map[id_t] = taxon_id

            sci_name = str(row.get("nombre_aceptado", row.get("scientificName", row.get("nombre", "")))).strip()
            verb_id = str(row.get("nombre_en_dataset", row.get("verbatimIdentification", sci_name))).strip()

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
        fact_records = []
        n_mof = 1
        for _, row in df_work.iterrows():
            # Validación estricta: solo se crea registro si idvigente == 1 (o "1" / "1.0")
            ide_vigente_raw = row.get("idevigente", row.get("ide_vigente", ""))
            try:
                ide_vigente_val = float(ide_vigente_raw)
            except (ValueError, TypeError):
                ide_vigente_val = 0.0

            if ide_vigente_val != 1.0:
                continue

            estado_legal = str(row.get("estadolegal", row.get("estado_legal", ""))).strip()
            norma = str(row.get("norma", "")).strip()
            obs_pob = row.get("observacionespoblacion", row.get("observaciones_poblacion", ""))

            # Si todos los campos principales están en blanco, no se crea el registro
            if not estado_legal and not norma and (not obs_pob or str(obs_pob).lower() in ["nan", "none", ""]):
                continue

            # Construcción de measurementValue según la regla de observaciones de población
            meas_value = estado_legal
            if obs_pob is not None:
                obs_str = str(obs_pob).strip()
                if obs_str and obs_str.lower() not in ["nan", "none", ""]:
                    meas_value = f"{estado_legal}. {obs_str}."

            id_t = row.get(group_col)
            t_id = taxon_id_map.get(id_t, f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{id_t}")
            meas_date = self.parse_norm_date(norma)

            fact_records.append({
                "measurementID": f"LESRPEeMoF-{id_t}-{n_mof}",
                "taxonID": t_id,
                "measurementType": "Legal Protection Status",
                "measurementValue": meas_value,
                "measurementMethod": norma,
                "measurementDeterminedDate": meas_date
            })
            n_mof += 1

        measurements_df = pd.DataFrame(fact_records)

        # ==========================================
        # 3. CONSTRUCCIÓN DE VERNACULARNAME.CSV
        # ==========================================
        vernacular_records = []
        n_vn = 1
        
        keywords_vernaculas = ["comun", "vernaculo", "vernacular", "vulgar", "nombre_comun", "nombres_comunes"]
        name_cols = [c for c in df_work.columns if any(k in c.lower() for k in keywords_vernaculas)]

        for _, row in df_work.iterrows():
            id_t = row.get(group_col)
            t_id = taxon_id_map.get(id_t, f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{id_t}")
            
            cols_a_evaluar = name_cols if name_cols else [c for c in df_work.columns if "nombre" in c.lower() and c.lower() not in ["nombre_aceptado", "scientificname", "nombre"]]

            for col in cols_a_evaluar:
                val = str(row.get(col, "")).strip()
                if val and val.lower() not in ["nan", "none", ""]:
                    names = [n.strip() for n in re.split(r'[,;]', val) if n.strip()]
                    for name in names:
                        lang = "Castellano"
                        country_code = IDIOMA_PAIS.get(lang, "ES")
                        vernacular_records.append({
                            "vernacularNameID": f"LESRPEVn-{id_t}-{n_vn}",
                            "taxonId": t_id,
                            "vernacularName": name,
                            "language": "es",
                            "countryCode": country_code
                        })
                        n_vn += 1

        vernacular_df = pd.DataFrame(vernacular_records)
        if not vernacular_df.empty:
            vernacular_df = vernacular_df.drop_duplicates(subset=["taxonId", "vernacularName"]).reset_index(drop=True)

        # ==========================================
        # 4. EXPORTACIÓN A CSV Y EMPAQUETADO ZIP
        # ==========================================
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

        return zip_path.resolve()