"""
detalle.py

Ventana de detalle de un taxón EIDOS.

Autor: Javier Estrada
"""

import tkinter as tk
from tkinter import ttk
import webbrowser

from db import construir_uri


def mostrar_detalle(parent, columnas, fila):
    """
    Muestra una ventana con todos los datos
    de un registro de la tabla especies.
    """

    if fila is None:
        return

    taxonid = int(float(fila[0]))

    uri = construir_uri(taxonid)

    # =====================================================
    # VENTANA
    # =====================================================

    ventana = tk.Toplevel(parent)

    ventana.title(
        f"EIDOS - Taxón {taxonid}"
    )

    ventana.geometry(
        "1000x700"
    )

    ventana.minsize(
        800,
        500
    )

    # =====================================================
    # CABECERA
    # =====================================================

    frame_cabecera = ttk.Frame(
        ventana
    )

    frame_cabecera.pack(
        fill="x",
        padx=10,
        pady=10
    )

    ttk.Label(
        frame_cabecera,
        text=f"TaxonID: {taxonid}"
    ).pack(
        side="left"
    )

    ttk.Button(
        frame_cabecera,
        text="Abrir ficha IEPNB",
        command=lambda: webbrowser.open(uri)
    ).pack(
        side="right"
    )

    # =====================================================
    # URI
    # =====================================================

    frame_uri = ttk.LabelFrame(
        ventana,
        text="URI resolvible"
    )

    frame_uri.pack(
        fill="x",
        padx=10,
        pady=5
    )

    txt_uri = tk.Text(
        frame_uri,
        height=2
    )

    txt_uri.pack(
        fill="x",
        padx=5,
        pady=5
    )

    txt_uri.insert(
        "1.0",
        uri
    )

    txt_uri.config(
        state="disabled"
    )

    # =====================================================
    # TABLA DE DATOS
    # =====================================================

    frame_tabla = ttk.Frame(
        ventana
    )

    frame_tabla.pack(
        fill="both",
        expand=True,
        padx=10,
        pady=10
    )

    tree = ttk.Treeview(
        frame_tabla,
        columns=(
            "campo",
            "valor"
        ),
        show="headings"
    )

    tree.heading(
        "campo",
        text="Campo"
    )

    tree.heading(
        "valor",
        text="Valor"
    )

    tree.column(
        "campo",
        width=250,
        anchor="w"
    )

    tree.column(
        "valor",
        width=650,
        anchor="w"
    )

    scroll_y = ttk.Scrollbar(
        frame_tabla,
        orient="vertical",
        command=tree.yview
    )

    tree.configure(
        yscrollcommand=scroll_y.set
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

    # =====================================================
    # PRIMER REGISTRO: URI
    # =====================================================

    tree.insert(
        "",
        "end",
        values=(
            "URI",
            uri
        )
    )

    # =====================================================
    # RESTO DE CAMPOS
    # =====================================================

    for campo, valor in zip(
        columnas,
        fila
    ):

        if valor is None:
            valor = ""

        tree.insert(
            "",
            "end",
            values=(
                campo,
                str(valor)
            )
        )

    # =====================================================
    # PIE
    # =====================================================

    ttk.Label(
        ventana,
        text=(
            "Doble clic en la tabla principal "
            "para abrir un taxón."
        )
    ).pack(
        fill="x",
        padx=10,
        pady=5
    )
