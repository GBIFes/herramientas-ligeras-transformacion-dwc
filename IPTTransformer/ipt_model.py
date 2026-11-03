"""Operaciones de datos independientes de Tkinter, comprobables sin interfaz."""

from collections import defaultdict
from copy import deepcopy
from uuid import uuid4

UNMAPPED = "(Sin mapear)"


def split_dataset(headers, rows, id_col, selected_cols, extension_type):
    """Extrae columnas sin perder registros ni elegir arbitrariamente valores.

    Si las columnas restantes discrepan para un mismo ID se rechaza la
    operación: el usuario debe extraer también esas columnas variables.
    """
    headers, rows = list(headers), [list(r) for r in rows]
    if id_col not in headers:
        raise ValueError(f"No existe la columna ID '{id_col}'.")
    if not extension_type:
        raise ValueError("Seleccione un tipo de extensión.")
    if not selected_cols or len(set(selected_cols)) != len(selected_cols):
        raise ValueError("Seleccione columnas distintas para la extensión.")
    if id_col in selected_cols or any(c not in headers for c in selected_cols):
        raise ValueError("La clave principal no se puede extraer.")
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("Hay filas con un número incorrecto de columnas.")
    id_idx = headers.index(id_col)
    kept = [c for c in headers if c not in selected_cols]
    keep_indices = [headers.index(c) for c in kept]
    selected_indices = [headers.index(c) for c in selected_cols]
    core, by_id, extension_rows = [], {}, []
    record_col = "extensionRecordID"
    while record_col in headers:
        record_col = "_" + record_col
    for row in rows:
        identifier = str(row[id_idx])
        if not identifier.strip():
            raise ValueError("Hay IDs vacíos. Corríjalos antes de normalizar.")
        projected = [row[i] for i in keep_indices]
        if identifier in by_id and by_id[identifier] != projected:
            raise ValueError(
                f"El ID '{identifier}' conserva valores distintos en el Core. "
                "Mueva también las otras columnas variables a la extensión."
            )
        if identifier not in by_id:
            by_id[identifier] = projected
            core.append(projected)
        # Incluye también los IDs no duplicados y mantiene cada fila original.
        extension_rows.append(
            [identifier] + [row[i] for i in selected_indices] + [str(uuid4())]
        )
    extension = {
        "tipo": extension_type, "fk_col": id_col, "self_id_col": record_col,
        "self_parent_col": "", "fields": [id_col] + list(selected_cols) + [record_col],
        "rows": extension_rows, "is_hierarchical": False,
    }
    return kept, core, extension


def validate_dataset(cfg, is_core=False, core_ids=None):
    fields, rows = cfg.get("fields", []), cfg.get("rows", [])
    errors = []
    if not fields or len(set(f.casefold() for f in fields)) != len(fields):
        errors.append("Las cabeceras deben existir y ser únicas.")
    if any(len(row) != len(fields) for row in rows):
        errors.append("Hay filas de anchura incorrecta.")
        return errors
    key = cfg.get("id_col" if is_core else "fk_col")
    if key not in fields:
        errors.append(f"La columna de relación '{key}' no existe.")
        return errors
    index = fields.index(key)
    ids = [str(row[index]) for row in rows]
    if any(not value.strip() for value in ids):
        errors.append("Hay claves vacías.")
    if is_core and len(set(ids)) != len(ids):
        errors.append("El Core contiene IDs duplicados.")
    if not is_core and core_ids is not None:
        orphans = set(ids) - set(core_ids)
        if orphans:
            errors.append(f"Hay {len(orphans)} claves sin correspondencia en el Core.")
    mapping = cfg.get("mapping", {})
    targets = [v for v in mapping.values() if v and v != UNMAPPED]
    if len(set(targets)) != len(targets):
        errors.append("Un término está asignado a más de una columna.")
    output_fields = [mapping.get(f, f) if mapping.get(f) not in (None, "", UNMAPPED) else f for f in fields]
    if len(set(f.casefold() for f in output_fields)) != len(output_fields):
        errors.append("El mapeo produce cabeceras de salida duplicadas.")
    return errors


def mapped_dataset(cfg):
    result = deepcopy(cfg)
    mapping = cfg.get("mapping", {})
    result["fields"] = [
        mapping.get(f) if mapping.get(f) not in (None, "", UNMAPPED) else f
        for f in cfg["fields"]
    ]
    return result


def hierarchy_entries(rows, id_idx, parent_idx):
    """Orden iterativo (padre, índice de fila), sin ocultar ciclos ni IDs repetidos."""
    first = {}
    for index, row in enumerate(rows):
        identifier = str(row[id_idx])
        if identifier.strip():
            first.setdefault(identifier, index)
    children = defaultdict(list)
    roots = []
    for index, row in enumerate(rows):
        parent = first.get(str(row[parent_idx]))
        if parent is None or parent == index:
            roots.append(index)
        else:
            children[parent].append(index)
    seen, result = set(), []
    for root in roots + list(range(len(rows))):
        if root in seen:
            continue
        stack = [(None, root)]
        while stack:
            parent, index = stack.pop()
            if index in seen:
                continue
            seen.add(index)
            result.append((parent, index))
            stack.extend((index, child) for child in reversed(children[index]))
    return result
