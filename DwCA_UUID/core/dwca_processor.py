"""
dwca_processor.py

Procesamiento de Darwin Core Archive.

Modelo:

CORE

id          <- UUID
idOld       <- identificador anterior

EXTENSIONES

coreid      <- UUID
coreidOld   <- identificador anterior
"""

from dataclasses import dataclass
from pathlib import Path

import csv
import shutil
import tempfile
import zipfile

from .encoding_utils import (
    detect_file_format
)

from .uuid_utils import (
    build_uuid,
    normalize_identifier
)

from .meta_parser import (
    parse_meta
)

from .meta_updater import (
    update_meta,
    save_meta
)

from .validator import (
    validate_dwca
)

from .archive_builder import (
    build_output_zip_name,
    copy_supporting_resources,
    create_zip
)


# --------------------------------------------------
# RESULTADO
# --------------------------------------------------

@dataclass
class TransformationResult:

    output_zip: str

    records_core: int

    records_extensions: int


# --------------------------------------------------
# UUID MAP
# --------------------------------------------------

class UUIDMap:

    def __init__(self):

        self.mapping = {}

    def add(
        self,
        original_id,
        uuid_value
    ):

        self.mapping[
            normalize_identifier(
                original_id
            )
        ] = uuid_value

    def get(
        self,
        original_id
    ):

        return self.mapping.get(
            normalize_identifier(
                original_id
            ),
            ""
        )


# --------------------------------------------------
# TEMPORALES
# --------------------------------------------------

def build_work_folders():

    extract_dir = tempfile.mkdtemp(
        prefix="dwca_extract_"
    )

    output_dir = tempfile.mkdtemp(
        prefix="dwca_output_"
    )

    return (
        extract_dir,
        output_dir
    )


def cleanup_folders(
    *folders
):

    for folder in folders:

        if folder:

            shutil.rmtree(
                folder,
                ignore_errors=True
            )


def ensure_parent_folder(
    path
):

    Path(path).parent.mkdir(
        parents=True,
        exist_ok=True
    )


# --------------------------------------------------
# ZIP
# --------------------------------------------------

def extract_dwca(
    zip_file,
    extract_dir
):

    with zipfile.ZipFile(
        zip_file,
        "r"
    ) as archive:

        archive.extractall(
            extract_dir
        )


# --------------------------------------------------
# NOMBRES
# --------------------------------------------------

def build_uuid_filename(
    file_name
):

    return str(
        Path(file_name)
    )
# --------------------------------------------------
# CORE
# --------------------------------------------------

def process_core_file(
    input_file,
    output_file,
    id_index,
    deterministic=False
):

    encoding, delimiter = (
        detect_file_format(
            input_file
        )
    )

    ensure_parent_folder(
        output_file
    )

    uuid_map = UUIDMap()

    records = 0

    with open(
        input_file,
        "r",
        encoding=encoding,
        errors="ignore",
        newline=""
    ) as infile, open(
        output_file,
        "w",
        encoding=encoding,
        newline=""
    ) as outfile:

        reader = csv.reader(
            infile,
            delimiter=delimiter
        )

        writer = csv.writer(
            outfile,
            delimiter=delimiter,
            lineterminator="\n"
        )

        try:

            header = next(
                reader
            )

        except StopIteration:

            raise ValueError(
                f"Archivo Core vacío: "
                f"{input_file}"
            )

        if id_index >= len(header):

            raise ValueError(
                "Índice id fuera de rango."
            )

        new_header = []

        for pos, field in enumerate(
            header
        ):

            if pos == id_index:

                #
                # id = UUID
                #

                new_header.append(
                    field
                )

                #
                # nuevo campo
                #

                new_header.append(
                    "idOld"
                )

            else:

                new_header.append(
                    field
                )

        writer.writerow(
            new_header
        )

        for row in reader:

            if not row:
                continue

            while len(row) < len(header):

                row.append("")

            old_id = (
                normalize_identifier(
                    row[id_index]
                )
            )

            uuid_value = (
                build_uuid(
                    old_id,
                    deterministic
                )
            )

            uuid_map.add(
                old_id,
                uuid_value
            )

            new_row = []

            for pos, value in enumerate(
                row
            ):

                if pos == id_index:

                    #
                    # UUID nuevo
                    #

                    new_row.append(
                        uuid_value
                    )

                    #
                    # ID antiguo
                    #

                    new_row.append(
                        value
                    )

                else:

                    new_row.append(
                        value
                    )

            writer.writerow(
                new_row
            )

            records += 1

    return (
        uuid_map,
        records
    )


# --------------------------------------------------
# EXTENSIONES
# --------------------------------------------------

def process_extension_file(
    input_file,
    output_file,
    coreid_index,
    uuid_map
):

    encoding, delimiter = (
        detect_file_format(
            input_file
        )
    )

    ensure_parent_folder(
        output_file
    )

    records = 0

    with open(
        input_file,
        "r",
        encoding=encoding,
        errors="ignore",
        newline=""
    ) as infile, open(
        output_file,
        "w",
        encoding=encoding,
        newline=""
    ) as outfile:

        reader = csv.reader(
            infile,
            delimiter=delimiter
        )

        writer = csv.writer(
            outfile,
            delimiter=delimiter,
            lineterminator="\n"
        )

        try:

            header = next(
                reader
            )

        except StopIteration:

            raise ValueError(
                f"Extensión vacía: "
                f"{input_file}"
            )

        if coreid_index >= len(header):

            raise ValueError(
                "Índice coreid "
                "fuera de rango."
            )

        new_header = []

        for pos, field in enumerate(
            header
        ):

            if pos == coreid_index:

                #
                # coreid = UUID
                #

                new_header.append(
                    field
                )

                #
                # coreidOld
                #

                new_header.append(
                    "coreidOld"
                )

            else:

                new_header.append(
                    field
                )

        writer.writerow(
            new_header
        )
        for row in reader:

            if not row:
                continue

            while len(row) < len(header):

                row.append("")

            old_coreid = (
                normalize_identifier(
                    row[coreid_index]
                )
            )

            uuid_value = (
                uuid_map.get(
                    old_coreid
                )
            )

            new_row = []

            for pos, value in enumerate(
                row
            ):

                if pos == coreid_index:

                    #
                    # UUID nuevo
                    #

                    new_row.append(
                        uuid_value
                    )

                    #
                    # valor original
                    #

                    new_row.append(
                        value
                    )

                else:

                    new_row.append(
                        value
                    )

            writer.writerow(
                new_row
            )

            records += 1

    return records


# --------------------------------------------------
# AUXILIARES
# --------------------------------------------------

def collect_original_files(
    meta
):

    files = [
        meta.core.file_name,
        "meta.xml"
    ]

    for extension in meta.extensions:

        files.append(
            extension.file_name
        )

    return files


# --------------------------------------------------
# CORE OUTPUT
# --------------------------------------------------

def get_core_input_file(
    extract_dir,
    meta
):

    return (
        Path(extract_dir)
        / meta.core.file_name
    )

def get_core_output_file(
    output_dir,
    meta
):

    output_name = (
        meta.core.file_name
    )

    output_file = (
        Path(output_dir)
        / output_name
    )

    return (
        output_name,
        output_file
    )

    output_file = (
        Path(output_dir)
        / output_name
    )

    return (
        output_name,
        output_file
    )


# --------------------------------------------------
# EXTENSION OUTPUT
# --------------------------------------------------

def get_extension_output_file(
    output_dir,
    extension
):

    output_name = (
        extension.file_name
    )

    output_file = (
        Path(output_dir)
        / output_name
    )

    return (
        output_name,
        output_file
    )

# --------------------------------------------------
# PROCESO PRINCIPAL
# --------------------------------------------------

def process_dwca(
    dwca_zip_file,
    deterministic=False
):
    """
    Procesa un Darwin Core Archive completo.

    Parameters
    ----------
    dwca_zip_file : str

    deterministic : bool

    Returns
    -------
    TransformationResult
    """

    (
        extract_dir,
        output_dir
    ) = build_work_folders()

    try:

        # ------------------------------------------
        # EXTRAER ZIP
        # ------------------------------------------

        extract_dwca(
            dwca_zip_file,
            extract_dir
        )

        # ------------------------------------------
        # LEER META.XML
        # ------------------------------------------

        meta_file = (
            Path(extract_dir)
            / "meta.xml"
        )

        if not meta_file.exists():

            raise FileNotFoundError(
                "No se encontró meta.xml"
            )

        meta = parse_meta(
            meta_file
        )

        # ------------------------------------------
        # VALIDAR
        # ------------------------------------------

        validate_dwca(
            extract_dir,
            meta
        )

        # ------------------------------------------
        # CORE
        # ------------------------------------------

        core_input = (
            get_core_input_file(
                extract_dir,
                meta
            )
        )

        (
            core_output_name,
            core_output
        ) = get_core_output_file(
            output_dir,
            meta
        )

        (
            uuid_map,
            records_core
        ) = process_core_file(
            core_input,
            core_output,
            meta.core.id_index,
            deterministic
        )

        # ------------------------------------------
        # EXTENSIONES
        # ------------------------------------------

        records_extensions = 0

        for extension in meta.extensions:

            extension_input = (
                Path(extract_dir)
                / extension.file_name
            )

            (
                extension_output_name,
                extension_output
            ) = get_extension_output_file(
                output_dir,
                extension
            )

            ext_records = (
                process_extension_file(
                    extension_input,
                    extension_output,
                    extension.coreid_index,
                    uuid_map
                )
            )

            records_extensions += (
                ext_records
            )

            extension.new_file_name = (
                extension_output_name
            )

        # ------------------------------------------
        # NUEVO META.XML
        # ------------------------------------------

        updated_tree = update_meta(
            meta,
            core_output_name,
            0
        )

        save_meta(
            updated_tree,
            Path(output_dir)
            / "meta.xml"
        )

        # ------------------------------------------
        # RECURSOS AUXILIARES
        # ------------------------------------------

        excluded_files = (
            collect_original_files(
                meta
            )
        )

        copy_supporting_resources(
            extract_dir,
            output_dir,
            excluded_files
        )

        # ------------------------------------------
        # ZIP FINAL
        # ------------------------------------------

        output_zip = (
            build_output_zip_name(
                dwca_zip_file
            )
        )

        create_zip(
            output_dir,
            output_zip
        )

        # ------------------------------------------
        # RESULTADO
        # ------------------------------------------

        return TransformationResult(
            output_zip=output_zip,
            records_core=records_core,
            records_extensions=records_extensions
        )

    finally:

        cleanup_folders(
            extract_dir,
            output_dir
        )