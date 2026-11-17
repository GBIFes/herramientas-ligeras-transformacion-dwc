"""
taxa_excel.py
=============
Exporta los datos parseados a un libro de Excel (.xlsx).
"""

import os
import sys
import subprocess
from tkinter import messagebox
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

def export_to_excel(parent, fields, rows, default_filename="taxonomia_parseada.xlsx"):
    from tkinter import filedialog
    path = filedialog.asksaveasfilename(
        parent=parent,
        title="Guardar resultados en Excel",
        defaultextension=".xlsx",
        initialfile=default_filename,
        filetypes=[("Libro de Excel", "*.xlsx")]
    )
    if not path:
        return

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Taxonomia")
    ws.freeze_panes = "A2"

    for i, h in enumerate(fields, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(len(str(h)) + 3, 12), 35)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="289530")
    
    from openpyxl.cell import WriteOnlyCell
    header_cells = []
    for h in fields:
        c = WriteOnlyCell(ws, value=str(h))
        c.font = header_font
        c.fill = header_fill
        header_cells.append(c)
    ws.append(header_cells)

    for r in rows:
        ws.append([cell if cell != "" else None for cell in r])

    try:
        wb.save(path)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar el archivo Excel:\n{e}", parent=parent)
        return

    if messagebox.askyesno("Éxito", f"Archivo Excel creado correctamente:\n{path}\n\n¿Desea abrirlo ahora?", parent=parent):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass