"""
dwca_eml_summary.py
Genera un resumen tabular del eml.xml: una fila por cada nodo que tiene
texto o atributos, con las columnas

    orden      nº de aparición del nodo en el documento
    nivel      profundidad en el árbol (eml = 0)
    ruta       ruta completa, p. ej. eml/dataset/creator/organizationName
    etiqueta   nombre del nodo
    atributos  atributos en formato clave=valor; clave=valor
    texto      contenido de texto del nodo

Se usa desde dwca_access.py para crear la tabla 'eml_metadata', pero también
se puede usar solo:

    from dwca_eml_summary import build_summary, save_tsv
    rows = build_summary("eml.xml")
    save_tsv(rows, "resumen_eml.tsv")
"""

import csv
import xml.etree.ElementTree as ET

TABLE_NAME = "eml_metadata"

COLUMNS = ["orden", "nivel", "ruta", "etiqueta", "atributos", "texto"]
CAPTIONS = ["Orden", "Nivel", "Ruta", "Etiqueta", "Atributos", "Texto"]
TYPES = ["LONG", "LONG", "LONGTEXT", "TEXT(255)", "LONGTEXT", "LONGTEXT"]


def _strip_ns(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def build_summary(eml_path):
    """Devuelve la lista de filas (orden, nivel, ruta, etiqueta, atributos, texto)."""
    root = ET.parse(eml_path).getroot()

    rows = []
    counter = [0]

    def walk(el, path, level):
        counter[0] += 1
        tag = _strip_ns(el.tag)
        full = f"{path}/{tag}" if path else tag
        text = (el.text or "").strip()
        attrs = "; ".join(f"{_strip_ns(k)}={v}" for k, v in el.attrib.items())
        if text or attrs:
            rows.append((counter[0], level, full, tag, attrs, text))
        for child in el:
            walk(child, full, level + 1)

    walk(root, "", 0)
    return rows


def save_tsv(rows, path):
    """Guarda el resumen como TSV (mismo formato que el listado de ejemplo)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(COLUMNS)
        w.writerows(rows)
