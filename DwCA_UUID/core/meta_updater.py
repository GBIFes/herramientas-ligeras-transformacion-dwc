"""
meta_updater.py

Actualización de meta.xml para el
nuevo Darwin Core Archive transformado.

Modelo:

CORE

0 = id (UUID)
1 = idOld
2... = campos originales

EXTENSIONS

0 = coreid (UUID)
1 = coreidOld
2... = campos originales
"""

import xml.etree.ElementTree as ET

from .meta_parser import (
    MetaDefinition,
    ns,
    DWC_NAMESPACE
)

IDOLD_TERM = (
    "https://gbif.es/terms/idOld"
)

COREIDOLD_TERM = (
    "https://gbif.es/terms/coreidOld"
)


# --------------------------------------------------
# XML NAMESPACE
# --------------------------------------------------

def register_namespace():

    ET.register_namespace(
        "",
        DWC_NAMESPACE
    )


# --------------------------------------------------
# FIELD HELPERS
# --------------------------------------------------

def shift_field_indexes(
    parent_element
):
    """
    Desplaza índices+1 porque
    insertamos idOld/coreidOld
    en posición 1.
    """

    fields = parent_element.findall(
        ns("field")
    )

    for field in fields:

        current = int(
            field.attrib.get(
                "index",
                "0"
            )
        )

        field.set(
            "index",
            str(current + 1)
        )


def create_field(
    index,
    term
):
    """
    Crea un elemento field.
    """

    element = ET.Element(
        ns("field")
    )

    element.set(
        "index",
        str(index)
    )

    element.set(
        "term",
        term
    )

    return element


# --------------------------------------------------
# CORE UPDATE
# --------------------------------------------------

def update_core_definition(
    meta: MetaDefinition,
    new_core_file
):

    core_element = (
        meta.core.xml_element
    )

    files = core_element.find(
        ns("files")
    )

    location = files.find(
        ns("location")
    )

    location.text = (
        new_core_file
    )

    id_element = core_element.find(
        ns("id")
    )

    #
    # id siempre permanece en 0
    #

    id_element.set(
        "index",
        "0"
    )

    #
    # Mover índices de campos
    #

    shift_field_indexes(
        core_element
    )

    #
    # Insertar nuevo field
    # para idOld
    #

    new_field = create_field(
        1,
        IDOLD_TERM
    )

    fields = core_element.findall(
        ns("field")
    )

    if fields:

        first_field = fields[0]

        position = list(
            core_element
        ).index(
            first_field
        )

        core_element.insert(
            position,
            new_field
        )

    else:

        core_element.append(
            new_field
        )

    meta.core.file_name = (
        new_core_file
    )

    meta.core.id_index = 0


# --------------------------------------------------
# EXTENSIONS UPDATE
# --------------------------------------------------

def update_extensions(
    meta: MetaDefinition
):

    for extension in meta.extensions:

        element = (
            extension.xml_element
        )

        files = element.find(
            ns("files")
        )

        location = files.find(
            ns("location")
        )

        if extension.new_file_name:

            location.text = (
                extension.new_file_name
            )

        coreid = element.find(
            ns("coreid")
        )

        #
        # coreid siempre 0
        #

        coreid.set(
            "index",
            "0"
        )

        #
        # desplazar índices
        #

        shift_field_indexes(
            element
        )

        #
        # insertar coreidOld
        #

        new_field = create_field(
            1,
            COREIDOLD_TERM
        )

        fields = element.findall(
            ns("field")
        )

        if fields:

            first_field = fields[0]

            position = list(
                element
            ).index(
                first_field
            )

            element.insert(
                position,
                new_field
            )

        else:

            element.append(
                new_field
            )

        extension.file_name = (
            extension.new_file_name
        )

        extension.coreid_index = 0


# --------------------------------------------------
# UPDATE GLOBAL
# --------------------------------------------------

def update_meta(
    meta: MetaDefinition,
    new_core_file,
    new_id_index=None
):
    """
    new_id_index ya no se usa.
    Se mantiene por compatibilidad.
    """

    register_namespace()

    update_core_definition(
        meta,
        new_core_file
    )

    update_extensions(
        meta
    )

    return meta.tree


# --------------------------------------------------
# SAVE
# --------------------------------------------------

def save_meta(
    tree,
    output_file
):

    tree.write(
        output_file,
        encoding="utf-8",
        xml_declaration=True
    )