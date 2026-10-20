"""
meta_parser.py

Lectura y representación de meta.xml
de Darwin Core Archive.

Responsabilidades:

- Leer meta.xml
- Identificar Core
- Identificar Extensions
- Obtener índices de id/coreid
- Conservar referencias XML para actualización posterior
"""

from dataclasses import dataclass
from dataclasses import field

from pathlib import Path

import xml.etree.ElementTree as ET


# --------------------------------------------------
# CONSTANTES XML
# --------------------------------------------------

DWC_NAMESPACE = (
    "http://rs.tdwg.org/dwc/text/"
)


def ns(tag):
    """
    Construye una etiqueta XML
    con namespace Darwin Core.
    """

    return (
        f"{{{DWC_NAMESPACE}}}{tag}"
    )


# --------------------------------------------------
# CORE
# --------------------------------------------------

@dataclass
class CoreDefinition:

    file_name: str

    id_index: int

    fields_terminated_by: str = "\\t"

    lines_terminated_by: str = "\\n"

    fields_enclosed_by: str = ""

    ignore_header_lines: int = 1

    xml_element: object = None


# --------------------------------------------------
# EXTENSION
# --------------------------------------------------

@dataclass
class ExtensionDefinition:

    file_name: str

    coreid_index: int

    fields_terminated_by: str = "\\t"

    lines_terminated_by: str = "\\n"

    fields_enclosed_by: str = ""

    ignore_header_lines: int = 1

    xml_element: object = None

    #
    # Información generada
    # durante la transformación
    #

    new_file_name: str = ""

    new_coreid_index: int = None


# --------------------------------------------------
# META
# --------------------------------------------------

@dataclass
class MetaDefinition:

    tree: ET.ElementTree

    root: ET.Element

    core: CoreDefinition

    extensions: list = field(
        default_factory=list
    )


# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------

def get_node_text(
    node,
    default=""
):
    """
    Devuelve texto de nodo.
    """

    if node is None:
        return default

    if node.text is None:
        return default

    return node.text.strip()


def get_node_attribute(
    node,
    attribute_name,
    default=None
):
    """
    Devuelve atributo XML.
    """

    if node is None:
        return default

    return node.attrib.get(
        attribute_name,
        default
    )


def get_location_text(
    parent_element
):
    """
    Obtiene:

    <files>
        <location>
    """

    files = parent_element.find(
        ns("files")
    )

    if files is None:
        raise ValueError(
            "No existe elemento files."
        )

    location = files.find(
        ns("location")
    )

    if location is None:
        raise ValueError(
            "No existe location."
        )

    return get_node_text(
        location
    )


# --------------------------------------------------
# CORE READER
# --------------------------------------------------

def read_core(
    core_element
):

    id_element = core_element.find(
        ns("id")
    )

    if id_element is None:

        raise ValueError(
            "No existe elemento id "
            "en Core."
        )

    return CoreDefinition(

        file_name=
        get_location_text(
            core_element
        ),

        id_index=int(
            get_node_attribute(
                id_element,
                "index",
                0
            )
        ),

        fields_terminated_by=
        core_element.attrib.get(
            "fieldsTerminatedBy",
            "\\t"
        ),

        lines_terminated_by=
        core_element.attrib.get(
            "linesTerminatedBy",
            "\\n"
        ),

        fields_enclosed_by=
        core_element.attrib.get(
            "fieldsEnclosedBy",
            ""
        ),

        ignore_header_lines=int(
            core_element.attrib.get(
                "ignoreHeaderLines",
                1
            )
        ),

        xml_element=core_element
    )


# --------------------------------------------------
# EXTENSION READER
# --------------------------------------------------

def read_extension(
    extension_element
):

    coreid = (
        extension_element.find(
            ns("coreid")
        )
    )

    if coreid is None:

        raise ValueError(
            "No existe coreid "
            "en Extension."
        )

    return ExtensionDefinition(

        file_name=
        get_location_text(
            extension_element
        ),

        coreid_index=int(
            get_node_attribute(
                coreid,
                "index",
                0
            )
        ),

        fields_terminated_by=
        extension_element.attrib.get(
            "fieldsTerminatedBy",
            "\\t"
        ),

        lines_terminated_by=
        extension_element.attrib.get(
            "linesTerminatedBy",
            "\\n"
        ),

        fields_enclosed_by=
        extension_element.attrib.get(
            "fieldsEnclosedBy",
            ""
        ),

        ignore_header_lines=int(
            extension_element.attrib.get(
                "ignoreHeaderLines",
                1
            )
        ),

        xml_element=
        extension_element
    )


# --------------------------------------------------
# PARSER
# --------------------------------------------------

def parse_meta(
    meta_xml_path
):
    """
    Lee meta.xml y devuelve
    un objeto MetaDefinition.

    Parameters
    ----------
    meta_xml_path : str | Path

    Returns
    -------
    MetaDefinition
    """

    meta_xml_path = Path(
        meta_xml_path
    )

    if not meta_xml_path.exists():

        raise FileNotFoundError(
            f"No existe: "
            f"{meta_xml_path}"
        )

    tree = ET.parse(
        meta_xml_path
    )

    root = tree.getroot()

    core_element = root.find(
        ns("core")
    )

    if core_element is None:

        raise ValueError(
            "No se encontró "
            "el elemento core."
        )

    core = read_core(
        core_element
    )

    extensions = []

    for extension in root.findall(
        ns("extension")
    ):

        extensions.append(
            read_extension(
                extension
            )
        )

    return MetaDefinition(

        tree=tree,

        root=root,

        core=core,

        extensions=
        extensions
    )