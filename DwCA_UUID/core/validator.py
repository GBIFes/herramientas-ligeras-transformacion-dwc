"""
validator.py

Validación previa de Darwin Core Archive.
"""

from pathlib import Path

from .meta_parser import MetaDefinition
from .encoding_utils import (
    detect_file_format
)


class ValidationError(Exception):
    """
    Error de validación.
    """
    pass


def validate_meta_exists(
    extract_directory
):
    """
    Comprueba existencia de meta.xml.
    """

    meta_file = (
        Path(extract_directory)
        / "meta.xml"
    )

    if not meta_file.exists():

        raise ValidationError(
            "No existe meta.xml"
        )


def validate_core_exists(
    extract_directory,
    meta
):
    """
    Comprueba existencia del Core.
    """

    core_file = (
        Path(extract_directory)
        / meta.core.file_name
    )

    if not core_file.exists():

        raise ValidationError(
            f"No existe el archivo Core: "
            f"{meta.core.file_name}"
        )

    return core_file


def validate_extensions_exist(
    extract_directory,
    meta
):
    """
    Comprueba que existan todas
    las extensiones declaradas.
    """

    for extension in meta.extensions:

        ext_file = (
            Path(extract_directory)
            / extension.file_name
        )

        if not ext_file.exists():

            raise ValidationError(
                f"No existe la extensión: "
                f"{extension.file_name}"
            )


def validate_core_indexes(
    extract_directory,
    meta
):
    """
    Comprueba índice ID.
    """

    core_file = (
        Path(extract_directory)
        / meta.core.file_name
    )

    (
        encoding,
        delimiter
    ) = detect_file_format(
        core_file
    )

    with open(
        core_file,
        "r",
        encoding=encoding,
        errors="ignore",
        newline=""
    ) as f:

        first_line = f.readline()

    columns = first_line.rstrip(
        "\r\n"
    ).split(
        delimiter
    )

    max_index = (
        len(columns) - 1
    )

    if meta.core.id_index > max_index:

        raise ValidationError(
            "Índice ID fuera de rango "
            "en el archivo Core."
        )


def validate_extension_indexes(
    extract_directory,
    meta
):
    """
    Comprueba índices coreid.
    """

    for extension in meta.extensions:

        ext_file = (
            Path(extract_directory)
            / extension.file_name
        )

        (
            encoding,
            delimiter
        ) = detect_file_format(
            ext_file
        )

        with open(
            ext_file,
            "r",
            encoding=encoding,
            errors="ignore",
            newline=""
        ) as f:

            first_line = (
                f.readline()
            )

        columns = (
            first_line
            .rstrip("\r\n")
            .split(delimiter)
        )

        max_index = (
            len(columns) - 1
        )

        if (
            extension.coreid_index
            > max_index
        ):

            raise ValidationError(
                f"coreid index fuera "
                f"de rango en "
                f"{extension.file_name}"
            )


def validate_core_not_empty(
    extract_directory,
    meta
):
    """
    Verifica que el Core
    tenga datos.
    """

    core_file = (
        Path(extract_directory)
        / meta.core.file_name
    )

    (
        encoding,
        delimiter
    ) = detect_file_format(
        core_file
    )

    rows = 0

    with open(
        core_file,
        "r",
        encoding=encoding,
        errors="ignore",
        newline=""
    ) as f:

        next(f, None)

        for line in f:

            if line.strip():

                rows += 1

                break

    if rows == 0:

        raise ValidationError(
            "El archivo Core no "
            "contiene registros."
        )


def validate_dwca(
    extract_directory,
    meta: MetaDefinition
):
    """
    Validación completa.
    """

    validate_meta_exists(
        extract_directory
    )

    validate_core_exists(
        extract_directory,
        meta
    )

    validate_extensions_exist(
        extract_directory,
        meta
    )

    validate_core_indexes(
        extract_directory,
        meta
    )

    validate_extension_indexes(
        extract_directory,
        meta
    )

    validate_core_not_empty(
        extract_directory,
        meta
    )

    return True