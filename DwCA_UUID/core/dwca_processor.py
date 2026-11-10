"""
dwca_processor.py

Procesamiento de Darwin Core Archive (compatible con y sin meta.xml / eml.xml,
así como UUIDs deterministas mediante concatenación con guiones (-) y secuencia n+1).
"""

from dataclasses import dataclass
from pathlib import Path
import csv
import shutil
import tempfile
import zipfile
import uuid

from .encoding_utils import detect_file_format
from .uuid_utils import normalize_identifier
from .meta_parser import parse_meta
from .meta_updater import update_meta, save_meta
from .archive_builder import (
    copy_supporting_resources,
    create_zip
)


@dataclass
class TransformationResult:
    output_zip: str
    records_core: int
    records_extensions: int


class UUIDMap:

    def __init__(self):
        self.mapping = {}

    def add(self, original_id, uuid_value):
        self.mapping[normalize_identifier(original_id)] = uuid_value

    def get(self, original_id):
        return self.mapping.get(normalize_identifier(original_id), "")


class DummyCore:
    def __init__(self, file_name, id_index=0):
        self.file_name = file_name
        self.id_index = id_index


class DummyExtension:
    def __init__(self, file_name, coreid_index=0):
        self.file_name = file_name
        self.coreid_index = coreid_index
        self.new_file_name = file_name


class DummyMeta:
    def __init__(self, core, extensions):
        self.core = core
        self.extensions = extensions


def build_work_folders():
    extract_dir = tempfile.mkdtemp(prefix="dwca_extract_")
    output_dir = tempfile.mkdtemp(prefix="dwca_output_")
    return extract_dir, output_dir


def cleanup_folders(*folders):
    for folder in folders:
        if folder:
            shutil.rmtree(folder, ignore_errors=True)


def ensure_parent_folder(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def extract_dwca(zip_file, extract_dir):
    with zipfile.ZipFile(zip_file, "r") as archive:
        archive.extractall(extract_dir)


def detect_dwca_structure(extract_dir):
    """
    Detecta la estructura de la estrella de Darwin Core si no existe meta.xml.
    Busca archivos CSV, TSV o TXT en la carpeta extraída.
    """
    extract_path = Path(extract_dir)
    tabular_files = []
    for ext in ("*.csv", "*.tsv", "*.txt", "*.CSV", "*.TSV", "*.TXT"):
        tabular_files.extend(list(extract_path.glob(ext)))

    if not tabular_files:
        raise ValueError("No se encontraron archivos tabulares (CSV, TSV, TXT) en el archivo ZIP.")

    tabular_files.sort(key=lambda f: f.stat().st_size, reverse=True)

    core_file = tabular_files[0].name
    extension_files = [f.name for f in tabular_files[1:]]

    encoding, delimiter = detect_file_format(extract_path / core_file)
    id_index = 0
    with open(extract_path / core_file, "r", encoding=encoding, errors="ignore") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
            for idx, col in enumerate(header):
                if col.lower() in ["id", "occurrenceid", "taxonid", "catalognumber", "eventid"]:
                    id_index = idx
                    break
        except StopIteration:
            pass

    core_obj = DummyCore(core_file, id_index=id_index)
    extensions_obj = []
    for ext_file in extension_files:
        ext_id_index = 0
        with open(extract_path / ext_file, "r", encoding=encoding, errors="ignore") as f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                header = next(reader)
                for idx, col in enumerate(header):
                    if col.lower() in ["coreid", "id", "occurrenceid", "taxonid"]:
                        ext_id_index = idx
                        break
            except StopIteration:
                pass
        extensions_obj.append(DummyExtension(ext_file, coreid_index=ext_id_index))

    return DummyMeta(core=core_obj, extensions=extensions_obj)


def generate_deterministic_uuid(row_data, selected_columns, header, prefix, seed_val, current_seq):
    """
    Construye el texto combinando [Prefijo]-[Semilla]-[Col1]-[Col2]-[Col3] separados por guiones (-).
    Omite los campos vacíos y sus guiones correspondientes. Si no hay datos, usa n+1 (secuencia).
    Retorna el UUID v5, el texto de auditoría (UUID_textual) y el contador de secuencia actualizado.
    """
    parts = []

    if prefix:
        parts.append(str(prefix))
    if seed_val:
        parts.append(str(seed_val))

    for col in selected_columns:
        if col in header:
            idx = header.index(col)
            if idx < len(row_data):
                val = str(row_data[idx]).strip()
                if val:
                    parts.append(val)

    if not parts:
        parts.append(f"seq_{current_seq}")
        current_seq += 1

    uuid_textual = "-".join(parts)
    uuid_val = str(uuid.uuid5(uuid.NAMESPACE_DNS, uuid_textual))

    return uuid_val, uuid_textual, current_seq


# --------------------------------------------------
# PROCESAMIENTO DE CORE
# --------------------------------------------------

def process_core_file(input_file, output_file, id_index, deterministic=False, det_params=None):
    encoding, delimiter = detect_file_format(input_file)
    ensure_parent_folder(output_file)

    uuid_map = UUIDMap()
    records = 0

    prefix = ""
    seed_val = "1"
    selected_cols = []
    target_table = ""

    if det_params:
        target_table = det_params.get("target_table", "")
        prefix = det_params.get("prefix", "")
        seed_val = det_params.get("seed", "1")
        selected_cols = det_params.get("cols", [])

    # Verificar si esta tabla es la seleccionada para determinismo (o si aplica por defecto al Core)
    apply_det = deterministic
    if deterministic and target_table and input_file.name != target_table:
        apply_det = False  # Si se eligió otra tabla específica en la UI, esta va aleatoria o normal

    with open(input_file, "r", encoding=encoding, errors="ignore", newline="") as infile, \
         open(output_file, "w", encoding=encoding, newline="") as outfile:

        reader = csv.reader(infile, delimiter=delimiter)
        writer = csv.writer(outfile, delimiter=delimiter, lineterminator="\n")

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Archivo Core vacío: {input_file}")

        new_header = []
        for pos, field in enumerate(header):
            if pos == id_index:
                new_header.append(field)
                new_header.append(f"{field}Old")
            else:
                new_header.append(field)

        new_header.append("UUID_textual")
        writer.writerow(new_header)

        # Inicializar semilla numérica para n+1
        try:
            current_seq = int(seed_val) if seed_val.isdigit() else 1
        except ValueError:
            current_seq = 1

        for row in reader:
            if not row:
                continue
            while len(row) < len(header):
                row.append("")

            old_id = normalize_identifier(row[id_index])

            if apply_det:
                uuid_value, uuid_textual, current_seq = generate_deterministic_uuid(
                    row, selected_cols, header, prefix, seed_val, current_seq
                )
            else:
                uuid_value = str(uuid.uuid4())
                uuid_textual = "ALEATORIO"

            uuid_map.add(old_id, uuid_value)

            new_row = []
            for pos, value in enumerate(row):
                if pos == id_index:
                    new_row.append(uuid_value)
                    new_row.append(value)
                else:
                    new_row.append(value)

            new_row.append(uuid_textual)
            writer.writerow(new_row)
            records += 1

    return uuid_map, records


# --------------------------------------------------
# PROCESAMIENTO DE EXTENSIONES
# --------------------------------------------------

def process_extension_file(input_file, output_file, coreid_index, uuid_map, deterministic=False, det_params=None):
    encoding, delimiter = detect_file_format(input_file)
    ensure_parent_folder(output_file)
    records = 0

    prefix = ""
    seed_val = "1"
    selected_cols = []
    target_table = ""

    if det_params:
        target_table = det_params.get("target_table", "")
        prefix = det_params.get("prefix", "")
        seed_val = det_params.get("seed", "1")
        selected_cols = det_params.get("cols", [])

    apply_det = deterministic
    if deterministic and target_table and input_file.name != target_table:
        apply_det = False

    with open(input_file, "r", encoding=encoding, errors="ignore", newline="") as infile, \
         open(output_file, "w", encoding=encoding, newline="") as outfile:

        reader = csv.reader(infile, delimiter=delimiter)
        writer = csv.writer(outfile, delimiter=delimiter, lineterminator="\n")

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Extensión vacía: {input_file}")

        new_header = []
        for pos, field in enumerate(header):
            if pos == coreid_index:
                new_header.append(field)
                new_header.append(f"{field}Old")
            else:
                new_header.append(field)

        new_header.append("UUID_textual")
        writer.writerow(new_header)

        try:
            current_seq = int(seed_val) if seed_val.isdigit() else 1
        except ValueError:
            current_seq = 1

        for row in reader:
            if not row:
                continue
            while len(row) < len(header):
                row.append("")

            old_coreid = normalize_identifier(row[coreid_index])
            uuid_value = uuid_map.get(old_coreid)

            if not uuid_value:
                # Si no encuentra el mapeo del coreid, genera uno propio o aleatorio de respaldo
                if apply_det:
                    uuid_value, _, current_seq = generate_deterministic_uuid(
                        row, selected_cols, header, prefix, seed_val, current_seq
                    )
                else:
                    uuid_value = str(uuid.uuid4())

            uuid_textual = "PROPAGADO_DEL_CORE"

            new_row = []
            for pos, value in enumerate(row):
                if pos == coreid_index:
                    new_row.append(uuid_value)
                    new_row.append(value)
                else:
                    new_row.append(value)

            new_row.append(uuid_textual)
            writer.writerow(new_row)
            records += 1

    return records


# --------------------------------------------------
# PROCESO PRINCIPAL DE DWCA
# --------------------------------------------------

def process_dwca(dwca_zip_file, deterministic=False, det_params=None, custom_output_path=None):
    extract_dir, output_dir = build_work_folders()

    try:
        extract_dwca(dwca_zip_file, extract_dir)

        meta_file = Path(extract_dir) / "meta.xml"
        has_xml = meta_file.exists()

        if has_xml:
            meta = parse_meta(meta_file)
        else:
            meta = detect_dwca_structure(extract_dir)

        core_input = Path(extract_dir) / meta.core.file_name
        output_name = meta.core.file_name
        core_output = Path(output_dir) / output_name

        uuid_map, records_core = process_core_file(
            core_input,
            core_output,
            meta.core.id_index,
            deterministic,
            det_params
        )

        records_extensions = 0
        for extension in meta.extensions:
            extension_input = Path(extract_dir) / extension.file_name
            extension_output = Path(output_dir) / extension.file_name

            ext_records = process_extension_file(
                extension_input,
                extension_output,
                extension.coreid_index,
                uuid_map,
                deterministic,
                det_params
            )
            records_extensions += ext_records
            extension.new_file_name = extension.file_name

        if has_xml:
            updated_tree = update_meta(meta, output_name, 0)
            save_meta(updated_tree, Path(output_dir) / "meta.xml")

        excluded_files = [meta.core.file_name, "meta.xml", "eml.xml"]
        for ext in meta.extensions:
            excluded_files.append(ext.file_name)

        copy_supporting_resources(extract_dir, output_dir, excluded_files)

        if custom_output_path:
            output_zip = custom_output_path
        else:
            output_zip = build_output_zip_name(dwca_zip_file)

        create_zip(output_dir, output_zip)

        return TransformationResult(
            output_zip=output_zip,
            records_core=records_core,
            records_extensions=records_extensions
        )

    finally:
        cleanup_folders(extract_dir, output_dir)