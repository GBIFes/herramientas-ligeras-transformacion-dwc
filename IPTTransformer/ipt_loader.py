"""Lectura tabular consistente, sin sustitución silenciosa de caracteres."""

import csv
import io
from collections import Counter
from itertools import islice


def detectar_delimitador(sample_text):
    """Respeta campos entrecomillados antes de recurrir a la primera fila."""
    try:
        return csv.Sniffer().sniff(sample_text, delimiters="\t,;").delimiter
    except csv.Error:
        first = sample_text.splitlines()[0] if sample_text.splitlines() else ""
        counts = {d: len(next(csv.reader([first], delimiter=d))) for d in "\t,;"}
        return max(counts, key=counts.get)


def _decode(file_path):
    with open(file_path, "rb") as source:
        raw = source.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo descodificar el fichero.")


def _read(file_path, limit=None):
    text = _decode(file_path)
    if not text.strip():
        raise ValueError("El archivo está vacío.")
    delimiter = detectar_delimitador(text[:65536])
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        headers = [h.strip() for h in next(reader)]
        if not headers or any(not h for h in headers):
            raise ValueError("Hay cabeceras vacías. Asigne un nombre a cada columna.")
        duplicates = [h for h, n in Counter(h.casefold() for h in headers).items() if n > 1]
        if duplicates:
            raise ValueError("Cabeceras duplicadas: " + ", ".join(duplicates))
        rows = []
        iterator = reader if limit is None else islice(reader, limit)
        for row in iterator:
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) != len(headers):
                raise ValueError(
                    f"Línea {reader.line_num}: se esperaban {len(headers)} "
                    f"columnas y se encontraron {len(row)}."
                )
            rows.append(row)
        return headers, rows
    except csv.Error as exc:
        raise ValueError(f"CSV no válido cerca de la línea {reader.line_num}: {exc}") from exc


def inspect_file_headers(file_path, num_lines=5):
    """Devuelve cabeceras y una vista previa de registros lógicos completos."""
    return _read(file_path, max(0, num_lines - 1))


def load_file_data(file_path):
    return _read(file_path)
