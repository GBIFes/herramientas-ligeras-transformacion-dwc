"""
dwca_excel.py
Exporta un Darwin Core Archive a un libro de Excel (.xlsx):

    - hoja  core
    - una hoja por extensión
    - hoja  EML (resumen del eml.xml, ver dwca_eml_summary.py)

Cada hoja lleva cabecera con formato, primera fila inmovilizada y autofiltro.

Requisito:
    pip install openpyxl
"""

import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None

from dwca_loader import DwcaLoader
from dwca_eml_summary import build_summary, COLUMNS as EML_COLUMNS

MAX_ROWS = 1_048_575      # filas de datos por hoja (1 más para la cabecera)
MAX_COLS = 16_384
MAX_CELL_CHARS = 32_767
CHUNK = 2000
EML_WIDTHS = [8, 8, 60, 25, 40, 100]


class ExcelExportError(Exception):
    pass


# ---------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------
def _sheet_title(raw, used):
    """Nombre de hoja válido: máx. 31 caracteres, sin []:*?/\\ y único."""
    name = re.sub(r"[\[\]:*?/\\]", "_", str(raw or "").strip()) or "Hoja"
    name = name[:31]
    base, k = name, 2
    while name.lower() in used:
        suffix = f"_{k}"
        name = base[:31 - len(suffix)] + suffix
        k += 1
    used.add(name.lower())
    return name


class _Stats:
    def __init__(self):
        self.truncated = 0


def _clean(value, stats):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    s = ILLEGAL_CHARACTERS_RE.sub("", str(value))
    if len(s) > MAX_CELL_CHARS:
        s = s[:MAX_CELL_CHARS]
        stats.truncated += 1
    return s


def _write_sheet(wb, title, headers, rows, tick, stats, widths=None):
    ncols = len(headers)
    if ncols > MAX_COLS:
        raise ExcelExportError(f"La hoja '{title}' tiene {ncols} columnas; Excel admite {MAX_COLS}.")
    if len(rows) > MAX_ROWS:
        raise ExcelExportError(
            f"La hoja '{title}' tiene {len(rows)} filas; Excel admite {MAX_ROWS}. "
            "Exporta a Access para conjuntos de datos de este tamaño."
        )

    ws = wb.create_sheet(title)
    ws.freeze_panes = "A2"
    for i, h in enumerate(headers, start=1):
        if widths:
            w = widths[i - 1] if i - 1 < len(widths) else 20
        else:
            w = min(max(len(str(h)) + 2, 12), 40)
        ws.column_dimensions[get_column_letter(i)].width = w

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="289530")
    header_cells = []
    for h in headers:
        c = WriteOnlyCell(ws, value=str(h))
        c.font = header_font
        c.fill = header_fill
        header_cells.append(c)
    ws.append(header_cells)

    for k in range(0, len(rows), CHUNK):
        chunk = rows[k:k + CHUNK]
        for r in chunk:
            values = [_clean(r[i], stats) if i < len(r) else None for i in range(ncols)]
            ws.append(values)
        tick(len(chunk))

    ws.auto_filter.ref = f"A1:{get_column_letter(ncols)}{len(rows) + 1}"


def build_workbook(path, core_fields, core_rows, extensions, ext_data,
                   eml_rows=None, on_message=None, on_tick=None):
    """Crea el .xlsx. Devuelve la lista de advertencias."""
    on_message = on_message or (lambda m: None)
    on_tick = on_tick or (lambda n: None)
    stats = _Stats()
    warnings = []

    wb = Workbook(write_only=True)
    used = set()

    title = _sheet_title("core", used)
    on_message(f"Escribiendo hoja '{title}' ({len(core_rows)} filas)...")
    _write_sheet(wb, title, core_fields, core_rows, on_tick, stats)

    for name, fields in extensions:
        rows = [r for lst in ext_data.get(name, {}).values() for r in lst]
        title = _sheet_title(os.path.splitext(name)[0], used)
        on_message(f"Escribiendo hoja '{title}' ({len(rows)} filas)...")
        _write_sheet(wb, title, fields, rows, on_tick, stats)

    if eml_rows is not None:
        title = _sheet_title("EML", used)
        on_message("Escribiendo resumen del EML...")
        _write_sheet(wb, title, EML_COLUMNS, eml_rows, on_tick, stats, widths=EML_WIDTHS)

    on_message("Guardando libro de Excel...")
    try:
        wb.save(path)
    except PermissionError:
        raise ExcelExportError(
            "No se pudo guardar el archivo. ¿Está abierto en Excel? Ciérralo e inténtalo de nuevo."
        )

    if stats.truncated:
        warnings.append(
            f"{stats.truncated} celda(s) superaban los {MAX_CELL_CHARS} caracteres "
            "que admite Excel y se han recortado."
        )
    return warnings


# ---------------------------------------------------------------
# VENTANA DE PROGRESO
# ---------------------------------------------------------------
class _ProgressWindow(tk.Toplevel):
    def __init__(self, parent, total):
        super().__init__(parent)
        self.title("Exportando a Excel")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.lbl = tk.Label(self, text="Preparando...", width=60, anchor="w")
        self.lbl.pack(padx=15, pady=(15, 5))
        self.bar = ttk.Progressbar(self, maximum=max(total, 1), length=420)
        self.bar.pack(padx=15, pady=(0, 15))
        self.value = 0
        self.grab_set()
        self.update()

    def message(self, text):
        self.lbl.config(text=text)
        self.update()

    def advance(self, n):
        self.value += n
        self.bar["value"] = self.value
        self.update()


def _open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------
# FUNCIONES PÚBLICAS
# ---------------------------------------------------------------
def export_dwca_to_excel(parent, core_fields, core_rows, extensions, ext_data, eml_path=None):
    """Pide el destino y exporta datos ya cargados en memoria (+ EML si existe)."""
    if Workbook is None:
        messagebox.showerror(
            "Exportar a Excel",
            "Falta la librería openpyxl. Instálala con:\n\npip install openpyxl",
            parent=parent,
        )
        return

    path = filedialog.asksaveasfilename(
        parent=parent,
        title="Guardar libro de Excel",
        defaultextension=".xlsx",
        filetypes=[("Libro de Excel", "*.xlsx")],
    )
    if not path:
        return

    eml_rows = None
    if eml_path and os.path.exists(eml_path):
        try:
            eml_rows = build_summary(eml_path)
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning(
                "EML", f"No se pudo leer eml.xml; se exporta sin metadatos.\n{e}", parent=parent
            )

    total = len(core_rows) + sum(
        len(lst) for name, _ in extensions for lst in ext_data.get(name, {}).values()
    )
    if eml_rows is not None:
        total += len(eml_rows)

    progress = _ProgressWindow(parent, total)
    try:
        warnings = build_workbook(
            path, core_fields, core_rows, extensions, ext_data,
            eml_rows=eml_rows,
            on_message=progress.message, on_tick=progress.advance,
        )
    except Exception as e:  # noqa: BLE001
        progress.destroy()
        messagebox.showerror("Exportar a Excel", f"Error durante la exportación:\n{e}", parent=parent)
        return
    progress.destroy()

    msg = f"Libro de Excel creado correctamente:\n{path}"
    if warnings:
        msg += "\n\nAdvertencias:\n- " + "\n- ".join(warnings)
    msg += "\n\n¿Quieres abrirlo ahora en Excel?"
    if messagebox.askyesno("Exportar a Excel", msg, parent=parent):
        try:
            _open_file(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Exportar a Excel", f"No se pudo abrir el archivo:\n{e}", parent=parent)


def export_zip_to_excel(parent):
    """Pide un ZIP DwC-A, lo carga y lo exporta junto con su eml.xml."""
    if Workbook is None:
        messagebox.showerror(
            "Exportar a Excel",
            "Falta la librería openpyxl. Instálala con:\n\npip install openpyxl",
            parent=parent,
        )
        return

    zip_path = filedialog.askopenfilename(
        parent=parent,
        title="Seleccionar DwC-A (ZIP) para exportar a Excel",
        filetypes=[("DwC-A ZIP", "*.zip")],
    )
    if not zip_path:
        return

    try:
        parent.config(cursor="watch")
        parent.update()
        loader = DwcaLoader(zip_path)
        core_fields, core_rows, extensions, ext_data = loader.load()
        eml_path = os.path.join(loader.base, "eml.xml")
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Exportar a Excel", f"No se pudo leer el DwC-A:\n{e}", parent=parent)
        return
    finally:
        parent.config(cursor="")

    export_dwca_to_excel(parent, core_fields, core_rows, extensions, ext_data, eml_path)
