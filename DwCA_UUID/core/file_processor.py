"""
file_processor.py

Procesamiento de archivos individuales.
"""

from pathlib import Path
import csv

from .encoding_utils import (
    detect_file_format
)

from .uuid_utils import (
    build_uuid,
    find_available_uuid_column
)


def build_output_filename(
    input_file
):
    """
    archivo.csv
        ->
    archivo_UUID.csv
    """

    input_file = Path(
        input_file
    )

    return str(
        input_file.with_name(
            f"{input_file.stem}_UUID"
            f"{input_file.suffix}"
        )
    )


def process_single_file(
    input_file,
    deterministic=False
):
    """
    Añade una columna UUID.

    Returns
    -------
    str
        Ruta del archivo generado.
    """

    (
        encoding,
        delimiter
    ) = detect_file_format(
        input_file
    )

    output_file = (
        build_output_filename(
            input_file
        )
    )

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
                "El archivo está vacío."
            )

        uuid_column = (
            find_available_uuid_column(
                header
            )
        )

        header.append(
            uuid_column
        )

        writer.writerow(
            header
        )

        for row in reader:

            if not row:
                continue

            value = (
                row[0]
                if len(row) > 0
                else ""
            )

            row.append(
                build_uuid(
                    value=value,
                    deterministic=
                    deterministic
                )
            )

            writer.writerow(
                row
            )

    return output_file