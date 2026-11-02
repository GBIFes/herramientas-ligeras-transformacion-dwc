"""
ipt_loader.py
=============
Inspección y carga robusta de archivos Core y Extensiones para DwC-A / IPT.
"""

import os
import csv

def detect_encoding_and_delimiter(filepath):
    encoding_to_try = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']
    content = None
    used_encoding = 'utf-8'

    for enc in encoding_to_try:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read(2048)
                used_encoding = enc
                break
        except Exception:
            continue

    if content is None:
        return '\t', 'utf-8'

    lines = content.splitlines()
    first_line = lines[0] if lines else ""
    
    counts = {
        ';': first_line.count(';'),
        '\t': first_line.count('\t'),
        ',': first_line.count(',')
    }
    
    delimiter = max(counts, key=counts.get)
    if counts[delimiter] == 0:
        delimiter = '\t'

    return delimiter, used_encoding

def inspect_file_headers(filepath):
    delim, enc = detect_encoding_and_delimiter(filepath)
    try:
        with open(filepath, encoding=enc, errors="replace") as f:
            r = csv.reader(f, delimiter=delim)
            first_line = next(r, None)
            if first_line:
                return [col.strip() for col in first_line], delim, enc
    except Exception:
        pass
    return [], '\t', 'utf-8'

def load_file_data(filepath):
    headers, delim, enc = inspect_file_headers(filepath)
    rows = []
    try:
        with open(filepath, encoding=enc, errors="replace") as f:
            r = csv.reader(f, delimiter=delim)
            header_row = next(r, None)
            for row in r:
                if not row:
                    continue
                if len(row) < len(headers):
                    row += [""] * (len(headers) - len(row))
                rows.append(row)
    except Exception:
        pass
    return headers, rows, enc, delim