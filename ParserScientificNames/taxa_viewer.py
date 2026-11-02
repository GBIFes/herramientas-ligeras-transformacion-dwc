"""
taxa_viewer.py
==============
Visor tipo browser con celdas editables en línea (doble clic), filtrado por menú 
contextual (clic derecho), ordenamiento por cabeceras y exportación a Excel/Access.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from taxa_excel import export_to_excel
from taxa_access import export_to_access

class TaxaViewerFrame(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.fields = []
        self.rows = []
        self.welcome_frame = None
        self.output_filepath = ""
        self.filtered_rows = []
        self.current_filter = None
        self.active_entry = None

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=35, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#f0f0f0")

        # --- Barra Superior ---
        top_bar = tk.Frame(self, bg="#e0e0e0", padx=10, pady=5)
        top_bar.pack(fill="x")

        self.lbl_info = tk.Label(top_bar, text="Resultados del Parseo y Contraste GBIF (Doble clic en celda para editar)", font=("Segoe UI", 9, "bold"), bg="#e0e0e0", fg="#333333")
        self.lbl_info.pack(side="left", pady=5)

        tk.Button(
            top_bar, text="⬅ Volver / Nuevo Archivo", bg="#6c757d", fg="white", 
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4, 
            command=self.close_viewer
        ).pack(side="right", padx=5, pady=5)

        tk.Button(
            top_bar, text="🌐 Abrir Registro Web GBIF", bg="#289530", fg="white", 
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4, 
            command=self.abrir_enlace_seleccionado
        ).pack(side="right", padx=5, pady=5)

        self.btn_clear_filter = tk.Button(
            top_bar, text="🔄 Quitar Filtro", bg="#d9534f", fg="white", 
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4, 
            command=self.limpiar_filtro
        )

        # --- Tabla con Scroll Dual ---
        table_container = tk.Frame(self)
        table_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(table_container, show="headings")
        scroll_y = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        # Eventos: Doble clic para editar celda | Clic derecho para menú contextual
        self.tree.bind("<Double-1>", self.on_cell_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)

        # --- Panel Inferior ---
        bottom_bar = tk.Frame(self, bg="#f8f9fa", padx=10, pady=10, relief=tk.RIDGE, bd=1)
        bottom_bar.pack(fill="x", padx=10, pady=10)

        self.lbl_path = tk.Label(bottom_bar, text="Archivo generado: (ninguno)", font=("Segoe UI", 9, "italic"), bg="#f8f9fa", fg="#555555", anchor="w")
        self.lbl_path.pack(side="top", fill="x", pady=(0, 8))

        btns_frame = tk.Frame(bottom_bar, bg="#f8f9fa")
        btns_frame.pack(side="top", fill="x")

        tk.Button(
            btns_frame, text="📊 Guardar / Abrir en Excel (.xlsx)", bg="#217346", fg="white", 
            font=("Segoe UI", 9, "bold"), padx=10, pady=6, relief="flat",
            command=lambda: export_to_excel(self.root, self.fields, self.filtered_rows)
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            btns_frame, text="🗄️ Guardar / Generar Access (.accdb)", bg="#1f6fb2", fg="white", 
            font=("Segoe UI", 9, "bold"), padx=10, pady=6, relief="flat",
            command=lambda: export_to_access(self.root, self.fields, self.filtered_rows)
        ).pack(side="left", padx=5)

    def set_welcome(self, welcome):
        self.welcome_frame = welcome

    def close_viewer(self):
        if self.welcome_frame:
            self.pack_forget()
            self.welcome_frame.pack(fill="both", expand=True)

    def ordenar_columna(self, col_idx, col_name, reverse):
        try:
            self.filtered_rows.sort(key=lambda x: (x[col_idx] == "", str(x[col_idx]).lower()), reverse=reverse)
        except Exception:
            self.filtered_rows.sort(key=lambda x: str(x[col_idx]).lower(), reverse=reverse)

        self.actualizar_vista_tabla()
        col_id = f"col_{col_idx}"
        self.tree.heading(col_id, text=f"{col_name} {'▲' if reverse else '▼'}", command=lambda: self.ordenar_columna(col_idx, col_name, not reverse))

    def on_cell_double_click(self, event):
        """Permite editar el contenido de la celda en línea al hacer doble clic."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column_id = self.tree.identify_column(event.x)
            col_idx = int(column_id.replace('#', '')) - 1
            item_id = self.tree.identify_row(event.y)
            
            if item_id:
                self.editar_celda_en_linea(item_id, column_id, col_idx)

    def editar_celda_en_linea(self, item_id, column_id, col_idx):
        if self.active_entry and self.active_entry.winfo_exists():
            self.active_entry.destroy()

        try:
            bbox = self.tree.bbox(item_id, column_id)
            if not bbox:
                return
            x, y, w, h = bbox
        except Exception:
            return

        values = self.tree.item(item_id, "values")
        current_val = values[col_idx] if col_idx < len(values) else ""

        self.active_entry = tk.Entry(self.tree, font=("Segoe UI", 9))
        self.active_entry.place(x=x, y=y, width=w, height=h)
        self.active_entry.insert(0, current_val)
        self.active_entry.select_range(0, tk.END)
        self.active_entry.focus()

        def guardar_cambio(event=None):
            if not self.active_entry or not self.active_entry.winfo_exists():
                return
            new_val = self.active_entry.get()
            self.active_entry.destroy()

            # Actualizar valores en la fila del Treeview
            vals_list = list(self.tree.item(item_id, "values"))
            vals_list[col_idx] = new_val
            self.tree.item(item_id, values=vals_list)

            # Sincronizar con los datos internos
            children = self.tree.get_children()
            if item_id in children:
                row_tree_idx = children.index(item_id)
                if row_tree_idx < len(self.filtered_rows):
                    self.filtered_rows[row_tree_idx][col_idx] = new_val

        self.active_entry.bind("<Return>", guardar_cambio)
        self.active_entry.bind("<FocusOut>", lambda e: guardar_cambio())

    def on_right_click(self, event):
        """Menú contextual con clic derecho para filtrar por valor de celda."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column_id = self.tree.identify_column(event.x)
            col_idx = int(column_id.replace('#', '')) - 1
            item_id = self.tree.identify_row(event.y)
            
            if item_id:
                values = self.tree.item(item_id, "values")
                val_celda = values[col_idx]
                col_name = self.fields[col_idx]

                menu = tk.Menu(self, tearoff=0)
                menu.add_command(label=f"Filtrar por [{col_name} = '{val_celda}']", command=lambda: self.aplicar_filtro(col_idx, val_celda, col_name))
                menu.add_command(label="Copiar valor de celda", command=lambda: self.copiar_valor(val_celda))
                menu.tk_popup(event.x_root, event.y_root)

    def aplicar_filtro(self, col_idx, val_filtro, col_name):
        if val_filtro != "":
            self.current_filter = (col_idx, val_filtro)
            self.filtered_rows = [r for r in self.rows if str(r[col_idx]) == str(val_filtro)]
            self.actualizar_vista_tabla()
            self.btn_clear_filter.pack(side="right", padx=5, pady=5)
            self.lbl_info.config(text=f"Filtrado por [{col_name} = '{val_filtro}'] ({len(self.filtered_rows)} resultados)")

    def copiar_valor(self, valor):
        self.root.clipboard_clear()
        self.root.clipboard_append(str(valor))
        messagebox.showinfo("Copiado", f"Valor copiado al portapapeles:\n'{valor}'", parent=self)

    def limpiar_filtro(self):
        self.current_filter = None
        self.filtered_rows = list(self.rows)
        self.actualizar_vista_tabla()
        self.btn_clear_filter.pack_forget()
        self.lbl_info.config(text="Resultados del Parseo y Contraste GBIF (Doble clic en celda para editar)")

    def abrir_enlace_seleccionado(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Aviso", "Por favor, seleccione un registro de la tabla.", parent=self)
            return

        item_values = self.tree.item(selected_item[0], "values")
        if "gbif_uri" in self.fields:
            idx = self.fields.index("gbif_uri")
            uri = item_values[idx]
            if uri and str(uri).startswith("http"):
                webbrowser.open(uri)
                return

        messagebox.showinfo("Información", "El registro seleccionado no tiene un URI resolvible válido en GBIF.", parent=self)

    def load_data(self, fields, rows, output_filepath=""):
        self.fields = fields
        self.rows = rows
        self.filtered_rows = list(rows)
        self.output_filepath = output_filepath
        self.current_filter = None
        self.btn_clear_filter.pack_forget()

        if output_filepath:
            self.lbl_path.config(text=f"📁 Archivo guardado con éxito en: {output_filepath}")

        self.tree["columns"] = []
        col_ids = [f"col_{i}" for i in range(len(fields))]
        self.tree["columns"] = col_ids

        for i, col_name in enumerate(fields):
            col_id = col_ids[i]
            self.tree.heading(col_id, text=col_name, command=lambda idx=i, name=col_name: self.ordenar_columna(idx, name, False))
            w = max(len(str(col_name)) * 11, 140)
            self.tree.column(col_id, width=w, minwidth=80, anchor="w", stretch=False)

        self.actualizar_vista_tabla()

    def actualizar_vista_tabla(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in self.filtered_rows:
            self.tree.insert("", "end", values=row)