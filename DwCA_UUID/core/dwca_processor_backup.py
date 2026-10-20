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
# TEMP
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

    file_name = Path(
        file_name
    )

    return str(
        file_name.with_name(
            f"{file_name.stem}_UUID"
            f"{file_name.suffix}"
        )
    )
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
# TEMP
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

    file_name = Path(
        file_name
    )

    return str(
        file_name.with_name(
            f"{file_name.stem}_UUID"
            f"{file_name.suffix}"
        )
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

        header = next(reader)

        new_header = []

        for pos, field in enumerate(
            header
        ):

            if pos == id_index:

                new_header.append(
                    field
                )

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

            new_uuid = (
                build_uuid(
                    old_id,
                    deterministic
                )
            )

            uuid_map.add(
                old_id,
                new_uuid
            )

            new_row = []

            for pos, value in enumerate(
                row
            ):

                if pos == id_index:

                    new_row.append(
                        new_uuid
                    )

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
# EXTENSIONS
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

        header = next(reader)

        new_header = []

        for pos, field in enumerate(
            header
        ):

            if pos == coreid_index:

                new_header.append(
                    field
                )

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

                    new_row.append(
                        uuid_value
                    )

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
