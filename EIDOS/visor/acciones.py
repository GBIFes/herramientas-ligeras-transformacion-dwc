"""
acciones.py

Acciones auxiliares del visor EIDOS Legal.

Autor: Javier Estrada
"""

import webbrowser

import pandas as pd

from tkinter import filedialog
from tkinter import messagebox


# ==========================================================
# CONSTRUIR URI
# ==========================================================

def construir_uri(taxonid):

    taxonid = int(float(taxonid))

    return (
        "https://iepnb.gob.es/"
        "areas-tematicas/"
        "especies-silvestres/"
        f"eidos/{taxonid}"
    )


# ==========================================================
# ABRIR FICHA IEPNB
# ==========================================================

def abrir_iepnb(taxonid):

    url = construir_uri(taxonid)

    webbrowser.open(url)


# ==========================================================
# COPIAR URI
# ==========================================================

def copiar_uri(root, taxonid):

    url = construir_uri(taxonid)

    root.clipboard_clear()

    root.clipboard_append(url)

    root.update()

    messagebox.showinfo(
        "URI copiada",
        f"URI copiada al portapapeles:\n\n{url}"
    )


# ==========================================================
# EXPORTAR EXCEL
# ==========================================================

def exportar_excel(
    columnas,
    registros
):

    if not registros:

        messagebox.showwarning(
            "Sin datos",
            "No hay registros para exportar."
        )

        return

    archivo = filedialog.asksaveasfilename(

        title="Guardar Excel",

        defaultextension=".xlsx",

        filetypes=[
            (
                "Excel",
                "*.xlsx"
            )
        ],

        initialfile="eidos_legal.xlsx"
    )

    if not archivo:
        return

    try:

        df = pd.DataFrame(
            registros,
            columns=columnas
        )

        df.to_excel(
            archivo,
            index=False
        )

        messagebox.showinfo(
            "Exportación completada",
            (
                f"Archivo generado correctamente.\n\n"
                f"Registros exportados: {len(df):,}\n\n"
                f"Archivo:\n{archivo}"
            )
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


# ==========================================================
# EXPORTAR CSV
# ==========================================================

def exportar_csv(
    columnas,
    registros
):

    if not registros:

        messagebox.showwarning(
            "Sin datos",
            "No hay registros para exportar."
        )

        return

    archivo = filedialog.asksaveasfilename(

        title="Guardar CSV",

        defaultextension=".csv",

        filetypes=[
            (
                "CSV",
                "*.csv"
            )
        ],

        initialfile="eidos_legal.csv"
    )

    if not archivo:
        return

    try:

        df = pd.DataFrame(
            registros,
            columns=columnas
        )

        df.to_csv(
            archivo,
            index=False,
            encoding="utf-8-sig"
        )

        messagebox.showinfo(
            "Exportación completada",
            (
                f"Archivo generado correctamente.\n\n"
                f"Registros exportados: {len(df):,}\n\n"
                f"Archivo:\n{archivo}"
            )
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )


# ==========================================================
# ACERCA DE
# ==========================================================

def acerca():

    texto = """
EIDOS Legal

Visor de especies de interés normativo
basado en datos del IEPNB.

Actualmente incluye:

• Especies no nativas
• Especies CITES
• Especies EURING
• Especies Red Natura 2000

Funciones:

• Búsqueda por nombre
• Apertura de ficha IEPNB
• Copiar URI resolvible
• Exportación Excel
• Exportación CSV

Autor:
Javier Estrada
"""

    messagebox.showinfo(
        "Acerca de",
        texto
    )