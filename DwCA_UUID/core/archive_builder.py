"""
archive_builder.py

Funciones para:

- Construcción del ZIP final.
- Copia de recursos auxiliares.
- Creación de nombres de salida.
"""

from pathlib import Path

import shutil
import zipfile


# --------------------------------------------------
# NOMBRES DE SALIDA
# --------------------------------------------------

def build_output_zip_name(
    input_zip
):
    """
    Dataset.zip
        ->
    Dataset_UUID.zip
    """

    input_zip = Path(
        input_zip
    )

    return str(
        input_zip.with_name(
            f"{input_zip.stem}_UUID.zip"
        )
    )


# --------------------------------------------------
# COPIAS
# --------------------------------------------------

def copy_file(
    source,
    destination
):
    """
    Copia un archivo conservando
    metadatos.
    """

    destination = Path(
        destination
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(
        source,
        destination
    )


def copy_directory(
    source,
    destination
):
    """
    Copia un directorio completo.
    """

    shutil.copytree(
        source,
        destination
    )


# --------------------------------------------------
# RECURSOS AUXILIARES
# --------------------------------------------------

def copy_supporting_resources(
    source_dir,
    destination_dir,
    excluded_files
):
    """
    Copia todo aquello que no haya
    sido transformado.

    Ejemplos:

    eml.xml
    README.txt
    imágenes
    documentos

    excluyendo:

    meta.xml
    occurrence.txt
    multimedia.txt
    etc.
    """

    source_dir = Path(
        source_dir
    )

    destination_dir = Path(
        destination_dir
    )

    excluded = {

        str(item)
        .replace("\\", "/")
        .lower()

        for item
        in excluded_files

    }

    ignored_names = {

        "__macosx",
        ".ds_store",
        "thumbs.db"

    }

    for item in source_dir.rglob("*"):

        relative = str(
            item.relative_to(
                source_dir
            )
        ).replace(
            "\\",
            "/"
        )

        if (
            relative.lower()
            in excluded
        ):
            continue

        if (
            item.name.lower()
            in ignored_names
        ):
            continue

        destination = (
            destination_dir
            / relative
        )

        if item.is_dir():

            destination.mkdir(
                parents=True,
                exist_ok=True
            )

        else:

            destination.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            shutil.copy2(
                item,
                destination
            )


# --------------------------------------------------
# ZIP
# --------------------------------------------------

def create_zip(
    source_directory,
    output_zip
):
    """
    Genera ZIP final.

    Returns
    -------
    str
    """

    source_directory = Path(
        source_directory
    )

    output_zip = Path(
        output_zip
    )

    with zipfile.ZipFile(
        output_zip,
        "w",
        zipfile.ZIP_DEFLATED
    ) as archive:

        for file_path in source_directory.rglob("*"):

            if not file_path.is_file():
                continue

            relative_path = (
                file_path.relative_to(
                    source_directory
                )
            )

            archive.write(
                file_path,
                relative_path
            )

    return str(
        output_zip
    )


# --------------------------------------------------
# UTILIDAD
# --------------------------------------------------

def remove_if_exists(
    path
):
    """
    Elimina archivo si existe.
    """

    path = Path(path)

    if path.exists():

        path.unlink()