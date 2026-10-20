"""
visor_eidos.py

Visor principal de EIDOS Legal.

Autor: Javier Estrada
"""

import tkinter as tk
from tkinter import ttk

from db import (
    obtener_registros,
    obtener_taxon
)

from detalle import (
    mostrar_detalle
)

from acciones import (
    abrir_iepnb,
    copiar_uri,
    exportar_excel,
    exportar_csv,
    acerca
)

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

COLUMNAS_EXPORTACION = [
    "taxonid",
    "nombre",
    "origen",
    "es_no_nativa",
    "es_cites",
    "es_euring",
    "es_red_natura"
]

registros_actuales = []


# ==========================================================
# CARGA DE DATOS
# ==========================================================
def cargar_datos():

    global registros_actuales

    registros_actuales = obtener_registros(
        texto=txt_busqueda.get().strip(),
        no_nativa=var_no_nativa.get(),
        cites=var_cites.get(),
        euring=var_euring.get(),
        natura=var_natura.get()
    )

    print("Registros:", len(registros_actuales))

    tree.delete(*tree.get_children())

    for fila in registros_actuales:

        taxonid = fila[0]

        if taxonid is None:
            taxonid = ""

        else:
            try:
                taxonid = int(float(taxonid))
            except:
                pass

        tree.insert(
            "",
            "end",
            values=(
                taxonid,
                fila[1],
                fila[2],
                "✓" if fila[3] else "",
                "✓" if fila[4] else "",
                "✓" if fila[5] else "",
                "✓" if fila[6] else ""
            )
        )

    lbl_estado.config(
        text=f"Registros: {len(registros_actuales):,}"
    )
    
# ==========================================================
# DETALLE
# ==========================================================

def ver_detalle(event=None):

    item = tree.focus()

    if not item:
        return

    taxonid = tree.item(
        item
    )["values"][0]

    columnas, fila = obtener_taxon(
        taxonid
    )

    mostrar_detalle(
        root,
        columnas,
        fila
    )


# ==========================================================
# ABRIR IEPNB
# ==========================================================

def abrir_ficha():

    item = tree.focus()

    if not item:
        return

    taxonid = tree.item(
        item
    )["values"][0]

    abrir_iepnb(taxonid)


# ==========================================================
# COPIAR URI
# ==========================================================

def copiar_ficha():

    item = tree.focus()

    if not item:
        return

    taxonid = tree.item(
        item
    )["values"][0]

    copiar_uri(
        root,
        taxonid
    )


# ==========================================================
# EXPORTACIONES
# ==========================================================

def exportar_xlsx():

    exportar_excel(
        COLUMNAS_EXPORTACION,
        registros_actuales
    )


def exportar_csv_archivo():

    exportar_csv(
        COLUMNAS_EXPORTACION,
        registros_actuales
    )


# ==========================================================
# EVENTOS
# ==========================================================

def buscar_enter(event):

    cargar_datos()


# ==========================================================
# VENTANA PRINCIPAL
# ==========================================================

root = tk.Tk()

root.title(
    "EIDOS Legal"
)

root.geometry(
    "1400x850"
)

# ==========================================================
# VARIABLES DE FILTRO
# ==========================================================

var_no_nativa = tk.BooleanVar()
var_cites = tk.BooleanVar()
var_euring = tk.BooleanVar()
var_natura = tk.BooleanVar()

# ==========================================================
# FRAME SUPERIOR
# ==========================================================

frame_superior = ttk.Frame(root)

frame_superior.pack(
    fill="x",
    padx=10,
    pady=10
)

ttk.Label(
    frame_superior,
    text="Buscar:"
).pack(
    side="left"
)

txt_busqueda = ttk.Entry(
    frame_superior,
    width=50
)

txt_busqueda.pack(
    side="left",
    padx=5
)

txt_busqueda.bind(
    "<Return>",
    buscar_enter
)

ttk.Button(
    frame_superior,
    text="Buscar",
    command=cargar_datos
).pack(
    side="left",
    padx=5
)

ttk.Button(
    frame_superior,
    text="Abrir ficha IEPNB",
    command=abrir_ficha
).pack(
    side="left",
    padx=5
)

ttk.Button(
    frame_superior,
    text="Copiar URI",
    command=copiar_ficha
).pack(
    side="left",
    padx=5
)

# ==========================================================
# FILTROS
# ==========================================================

ttk.Checkbutton(
    frame_superior,
    text="No nativas",
    variable=var_no_nativa,
    command=cargar_datos
).pack(
    side="left",
    padx=15
)

ttk.Checkbutton(
    frame_superior,
    text="CITES",
    variable=var_cites,
    command=cargar_datos
).pack(
    side="left"
)

ttk.Checkbutton(
    frame_superior,
    text="EURING",
    variable=var_euring,
    command=cargar_datos
).pack(
    side="left"
)

ttk.Checkbutton(
    frame_superior,
    text="Red Natura",
    variable=var_natura,
    command=cargar_datos
).pack(
    side="left"
)

# ==========================================================
# TABLA
# ==========================================================

frame_tabla = ttk.Frame(root)

frame_tabla.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=10
)

columnas = (
    "TaxonID",
    "Nombre científico",
    "Origen",
    "No nativa",
    "CITES",
    "EURING",
    "Red Natura"
)

tree = ttk.Treeview(
    frame_tabla,
    columns=columnas,
    show="headings"
)

print("Columnas:", columnas)

scroll_y = ttk.Scrollbar(
    frame_tabla,
    orient="vertical",
    command=tree.yview
)

scroll_x = ttk.Scrollbar(
    frame_tabla,
    orient="horizontal",
    command=tree.xview
)

tree.configure(
    yscrollcommand=scroll_y.set,
    xscrollcommand=scroll_x.set
)

for col in columnas:

    tree.heading(
        col,
        text=col
    )

tree.column(
    "TaxonID",
    width=100,
    anchor="center"
)

tree.column(
    "Nombre científico",
    width=600
)

tree.column(
    "Origen",
    width=180
)

tree.column(
    "No nativa",
    width=90,
    anchor="center"
)

tree.column(
    "CITES",
    width=90,
    anchor="center"
)

tree.column(
    "EURING",
    width=90,
    anchor="center"
)

tree.column(
    "Red Natura",
    width=110,
    anchor="center"
)

tree.pack(
    side="left",
    fill="both",
    expand=True
)

scroll_y.pack(
    side="right",
    fill="y"
)

scroll_x.pack(
    side="bottom",
    fill="x"
)

tree.bind(
    "<Double-1>",
    ver_detalle
)

# ==========================================================
# PIE
# ==========================================================

frame_inferior = ttk.Frame(root)

frame_inferior.pack(
    fill="x",
    padx=10,
    pady=10
)

ttk.Button(
    frame_inferior,
    text="Exportar Excel",
    command=exportar_xlsx
).pack(
    side="left"
)

ttk.Button(
    frame_inferior,
    text="Exportar CSV",
    command=exportar_csv_archivo
).pack(
    side="left",
    padx=5
)

ttk.Button(
    frame_inferior,
    text="Acerca de",
    command=acerca
).pack(
    side="right"
)

lbl_estado = ttk.Label(
    frame_inferior,
    text=""
)

lbl_estado.pack(
    side="left",
    padx=20
)

# ==========================================================
# ARRANQUE
# ==========================================================

print("Treeview creado")

cargar_datos()

txt_busqueda.focus()

root.mainloop()