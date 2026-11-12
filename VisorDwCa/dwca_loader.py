"""
dwca_loader.py
==============
Cargador robusto de Darwin Core Archive con detección automática
de delimitadores (; , \t) y codificación compatible con Windows (UTF-8 / CP1252).
"""

import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
import csv


def strip_ns(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def short(term):
    return term.rsplit("/", 1)[-1] if term else ""


def safe_open(filepath):
    """
    Abre un archivo probando primero en UTF-8 (con y sin BOM) y si falla,
    recurre a la codificación nativa de Windows (cp1252 / ISO-8859-1).
    No deja descriptores de archivo abiertos.
    """
    for enc in ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1"):
        try:
            with open(filepath, "r", encoding=enc, newline="") as f:
                f.readline()  # Prueba de lectura
            return open(filepath, "r", encoding=enc, newline="")
        except UnicodeDecodeError:
            continue
    # Si todo falla, abrir por defecto reemplazando errores
    return open(filepath, "r", encoding="utf-8", errors="replace", newline="")


def detect_delimiter(filepath):
    """
    Detecta si el archivo usa ';', '\t' o ',' como separador,
    muestreando varias líneas y con csv.Sniffer como respaldo.
    """
    try:
        with safe_open(filepath) as f:
            sample = "".join(f.readline() for _ in range(20))
    except Exception:
        return "\t"

    counts = {d: sample.count(d) for d in (";", "\t", ",")}
    best = max(counts, key=counts.get)
    if counts[best] > 0:
        return best

    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        pass

    # Comprobaciones secundarias
    if ";" in sample:
        return ";"
    if "\t" in sample:
        return "\t"
    if "," in sample:
        return ","
    return "\t"


def inspect_txt_headers(folder_path):
    """
    Inspecciona los archivos de texto, detecta su codificación y separador,
    y devuelve las cabeceras limpias para el esquema en estrella.
    """
    headers = {}
    for fname in os.listdir(folder_path):
        if fname.lower().endswith((".txt", ".csv")):
            fpath = os.path.join(folder_path, fname)
            delim = detect_delimiter(fpath)
            try:
                with safe_open(fpath) as f:
                    r = csv.reader(f, delimiter=delim)
                    first_line = next(r, None)
                    if first_line:
                        headers[fname] = [col.strip() for col in first_line]
            except Exception:
                continue
    return headers


class DwcaLoader:
    def __init__(self, path):
        self.path = path
        self.base = None
        self.core_id_index = 0

    def load(self, manual_schema=None):
        if self.path.lower().endswith(".zip"):
            # Directorio temporal único por ZIP: nunca mezcla restos de otro archivo
            zip_name = os.path.splitext(os.path.basename(self.path))[0]
            temp = os.path.join(os.path.dirname(self.path), f"_dwca_temp_{zip_name}")
            if os.path.exists(temp):
                shutil.rmtree(temp, ignore_errors=True)
            os.makedirs(temp)
            with zipfile.ZipFile(self.path, "r") as z:
                z.extractall(temp)
            self.base = temp
        else:
            self.base = os.path.dirname(self.path) if os.path.isfile(self.path) else self.path

        if manual_schema:
            return self._parse_manual_schema(manual_schema)

        meta_path = os.path.join(self.base, "meta.xml")
        if not os.path.exists(meta_path):
            raise FileNotFoundError("No se encontró meta.xml.")

        meta = ET.parse(meta_path).getroot()
        return self._parse_meta(meta)

    def _parse_manual_schema(self, schema):
        core_fname = schema['core_file']
        core_path = os.path.join(self.base, core_fname)

        core_fields = []
        core_rows = []

        if os.path.exists(core_path):
            delim = detect_delimiter(core_path)
            with safe_open(core_path) as f:
                r = csv.reader(f, delimiter=delim)
                headers = next(r, None)
                if headers:
                    core_fields = [h.strip() for h in headers]
                    for row in r:
                        if len(row) < len(core_fields):
                            row += [""] * (len(core_fields) - len(row))
                        core_rows.append(row)

        core_id_col_name = schema.get('core_id_col', 'id')
        self.core_id_index = core_fields.index(core_id_col_name) if core_id_col_name in core_fields else 0

        extensions = []
        ext_data = {}

        for ext_conf in schema.get('extensions', []):
            ext_fname = ext_conf['file']
            ext_path = os.path.join(self.base, ext_fname)
            if not os.path.exists(ext_path):
                continue

            delim = detect_delimiter(ext_path)
            with safe_open(ext_path) as f:
                r = csv.reader(f, delimiter=delim)
                headers = next(r, None)
                if not headers:
                    continue
                fields = [h.strip() for h in headers]

                fk_col = ext_conf.get('fk_col')
                fk_idx = fields.index(fk_col) if fk_col and fk_col in fields else 0

                rows = {}
                for row in r:
                    if len(row) < len(fields):
                        row += [""] * (len(fields) - len(row))
                    cid = str(row[fk_idx]).strip() if fk_idx < len(row) else ""
                    rows.setdefault(cid, []).append(row)

                extensions.append((ext_fname, fields))
                ext_data[ext_fname] = rows

        return core_fields, core_rows, extensions, ext_data

    def _resolve(self, location):
        location = location.strip()
        if os.path.isabs(location):
            return location
        return os.path.join(self.base, location)

    def _find_core(self, root):
        for child in root.iter():
            if strip_ns(child.tag) == "core":
                return child
        return None

    def _find_extensions(self, root):
        result = []
        for child in root.iter():
            if strip_ns(child.tag) == "extension":
                result.append(child)
        return result

    def _parse_meta(self, meta):
        core = self._find_core(meta)
        if core is None:
            raise ValueError("meta.xml no contiene <core>")

        loc_nodes = [n for n in core.iter() if strip_ns(n.tag) == "location"]
        core_file_path = loc_nodes[-1].text if loc_nodes else ""
        core_file = self._resolve(core_file_path) if core_file_path else ""

        core_fields = []
        core_rows = []

        if core_file and os.path.exists(core_file):
            id_elem = None
            for n in core.iter():
                if strip_ns(n.tag) == "id":
                    id_elem = n
                    break
            core_id_index = int(id_elem.get("index")) if id_elem is not None and id_elem.get("index") is not None else 0
            self.core_id_index = core_id_index

            fields_raw = [n for n in core.iter() if strip_ns(n.tag) == "field"]
            fields_raw_sorted = sorted(fields_raw, key=lambda f: int(f.get("index")) if f.get("index") is not None else 0)
            max_index = max([core_id_index] + [int(f.get("index")) for f in fields_raw_sorted if f.get("index") is not None], default=0)

            index_to_term = {core_id_index: "id"}
            for f in fields_raw_sorted:
                idx = int(f.get("index"))
                index_to_term[idx] = short(f.get("term"))

            core_fields = [index_to_term.get(i, f"col_{i}") for i in range(max_index + 1)]

            delim = detect_delimiter(core_file)
            with safe_open(core_file) as f:
                r = csv.reader(f, delimiter=delim)
                next(r, None)
                for row in r:
                    if len(row) < len(core_fields):
                        row += [""] * (len(core_fields) - len(row))
                    core_rows.append(row)

        extensions = []
        ext_data = {}

        for ext in self._find_extensions(meta):
            loc_nodes = [n for n in ext.iter() if strip_ns(n.tag) == "location"]
            if not loc_nodes:
                continue
            fname_rel = loc_nodes[-1].text
            fname = self._resolve(fname_rel)

            if not os.path.exists(fname):
                continue

            fields_raw_ext = [n for n in ext.iter() if strip_ns(n.tag) == "field"]
            fields_raw_ext_sorted = sorted(fields_raw_ext, key=lambda f: int(f.get("index")) if f.get("index") is not None else 0)
            max_idx_ext = max([int(f.get("index")) for f in fields_raw_ext_sorted if f.get("index") is not None], default=0)

            coreid_elem = None
            for n in ext.iter():
                if strip_ns(n.tag) == "coreid":
                    coreid_elem = n
                    break
            cid_index = int(coreid_elem.get("index")) if coreid_elem is not None and coreid_elem.get("index") is not None else 0

            index_to_term_ext = {cid_index: "id"}
            for f in fields_raw_ext_sorted:
                idx = int(f.get("index"))
                index_to_term_ext[idx] = short(f.get("term"))

            fields = [index_to_term_ext.get(i, f"col_{i}") for i in range(max_idx_ext + 1)]

            rows = {}
            delim = detect_delimiter(fname)
            with safe_open(fname) as f:
                r = csv.reader(f, delimiter=delim)
                next(r, None)
                for row in r:
                    if len(row) < len(fields):
                        row += [""] * (len(fields) - len(row))
                    cid = str(row[cid_index]).strip() if cid_index < len(row) else ""
                    rows.setdefault(cid, []).append(row)

            tab_name = os.path.basename(fname)
            extensions.append((tab_name, fields))
            ext_data[tab_name] = rows

        return core_fields, core_rows, extensions, ext_data