"""
taxa_loader.py
==============
Procesa archivos aplicando el parseo taxonómico y contraste con GBIF.
Oculta y excluye automáticamente las columnas que no contengan ningún dato.
"""

import os
import csv
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from taxa_parser import (
    n_gen, n_sub_gen, n_sp, n_cat_infra, n_infra, n_autor, n_autinfra,
    codigo_nombre_cientifico, rango_taxonomico_simple,
    n_hibrido_generico, n_hibrido_especifico, n_cultivar, limpiar_cache
)
from taxa_gbif import verificar_con_gbif

def detect_encoding_and_delimiter(filepath):
    encoding_to_try = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']
    content = None
    used_encoding = 'utf-8'

    for enc in encoding_to_try:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read(2048)
                used_encoding = enc
                break
        except Exception:
            continue

    if content is None:
        return '\t', 'utf-8'

    lines = content.splitlines()
    first_line = lines[0] if lines else ""
    
    counts = {
        ';': first_line.count(';'),
        '\t': first_line.count('\t'),
        ',': first_line.count(',')
    }
    
    delimiter = max(counts, key=counts.get)
    if counts[delimiter] == 0:
        delimiter = '\t'

    return delimiter, used_encoding

def inspect_file_headers(filepath):
    delim, enc = detect_encoding_and_delimiter(filepath)
    try:
        with open(filepath, encoding=enc, errors="replace") as f:
            r = csv.reader(f, delimiter=delim)
            first_line = next(r, None)
            if first_line:
                return [col.strip() for col in first_line], delim, enc
    except Exception:
        pass
    return [], '\t', 'utf-8'

def process_taxa_file(filepath, target_col_name, output_filepath=None, progress_callback=None):
    limpiar_cache()
    headers, delim, enc = inspect_file_headers(filepath)
    if not headers or target_col_name not in headers:
        raise ValueError(f"No se encontró la columna '{target_col_name}' en el archivo.")

    if not output_filepath:
        dir_name = os.path.dirname(filepath)
        base_name, ext = os.path.splitext(os.path.basename(filepath))
        output_filepath = os.path.join(dir_name, f"{base_name}_ParserAutores{ext}")

    col_idx = headers.index(target_col_name)

    total_rows = 0
    with open(filepath, encoding=enc, errors="replace") as f:
        total_rows = sum(1 for line in f) - 1
    if total_rows < 1:
        total_rows = 1

    candidate_extra_fields = [
        "p_genus", "p_subgenus", "p_specificEpithet", "p_infraspecificRank", "p_infraspecificEpithet",
        "p_scientificNameAuthorship", "p_authorSpecies", "p_authorInfra",
        "p_nomenclaturalCode", "p_taxonRank", "p_hybridGeneric", "p_hybridSpecific", "p_cultivarName",
        "gbif_matchType", "gbif_status", "gbif_usageKey", "gbif_scientificName", "gbif_family", "gbif_uri", "gbif_discrepancy"
    ]

    raw_processed_rows = []
    current_row = 0

    with open(filepath, encoding=enc, errors="replace") as f:
        r = csv.reader(f, delimiter=delim)
        header_row = next(r, None)
        
        for row in r:
            if not row:
                continue
            if len(row) < len(headers):
                row += [""] * (len(headers) - len(row))
            
            nombre_cientifico = row[col_idx]
            
            gen = n_gen(nombre_cientifico)
            subgen = n_sub_gen(nombre_cientifico)
            sp = n_sp(nombre_cientifico)
            cat_infra = n_cat_infra(nombre_cientifico)
            infra = n_infra(nombre_cientifico)
            autor_sp = n_autor(nombre_cientifico)
            autor_infra = n_autinfra(nombre_cientifico)
            authorship_dwc = autor_infra if autor_infra else autor_sp
            codigo = codigo_nombre_cientifico(nombre_cientifico)
            rango = rango_taxonomico_simple(nombre_cientifico)
            hib_gen_val = n_hibrido_generico(nombre_cientifico)
            hib_esp_val = n_hibrido_especifico(nombre_cientifico)
            cult_val = n_cultivar(nombre_cientifico)

            gbif_res = verificar_con_gbif(gen, sp, infra, nombre_cientifico)

            extra_vals = [
                gen, subgen, sp, cat_infra, infra,
                authorship_dwc, autor_sp, autor_infra,
                codigo, rango, hib_gen_val, hib_esp_val, cult_val,
                gbif_res["gbif_matchType"],
                gbif_res["gbif_status"],
                gbif_res["gbif_usageKey"],
                gbif_res["gbif_scientificName"],
                gbif_res["gbif_family"],
                gbif_res["gbif_uri"],
                gbif_res["gbif_discrepancy"]
            ]

            raw_processed_rows.append((row, extra_vals))

            current_row += 1
            if progress_callback:
                progress_callback(current_row, total_rows)

    # Filtrar únicamente las columnas extra que tengan AL MENOS UN dato distinto de vacío
    extra_columns_transposed = list(zip(*[item[1] for item in raw_processed_rows])) if raw_processed_rows else [[]]*len(candidate_extra_fields)
    
    active_extra_fields = []
    active_extra_indices = []
    
    for i, col_data in enumerate(extra_columns_transposed):
        if any(val != "" and val is not None for val in col_data):
            active_extra_fields.append(candidate_extra_fields[i])
            active_extra_indices.append(i)

    final_headers = list(headers) + active_extra_fields

    final_rows = []
    for orig_row, extra_vals in raw_processed_rows:
        filtered_extra = [extra_vals[i] for i in active_extra_indices]
        final_rows.append(orig_row + filtered_extra)

    # Guardar en utf-8-sig
    with open(output_filepath, 'w', encoding='utf-8-sig', errors='replace', newline='') as f:
        writer = csv.writer(f, delimiter=delim)
        writer.writerow(final_headers)
        writer.writerows(final_rows)

    return final_headers, final_rows