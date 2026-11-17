"""
taxa_viewer.py
==============
Visor tipo browser con celdas editables en línea (doble clic), filtrado por menú
contextual (clic derecho), ordenamiento alternante por DOBLE CLIC en cabeceras,
wrap inteligente de columnas, eliminación y renombrado de columnas, y controles
de selección sobre cada cabecera para asignar nombres de columnas GBIF (sin
duplicados). Exportación a Excel/Access bloqueada si hay columnas sin nombre o
con nombres duplicados.
"""

import textwrap
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from taxa_excel import export_to_excel
from taxa_access import export_to_access

# Nombres de columnas GBIF que describen la taxonomía (asignables una sola vez)
GBIF_FIELD_NAMES = [
    "gbif_matchType",
    "gbif_status",
    "gbif_usageKey",
    "gbif_scientificName",
    "gbif_genus",
    "gbif_family",
    "gbif_uri",
    "gbif_discrepancy",
    "gbif_taxonomy",
]

BLANK = "(en blanco)"
LINE_PX = 15          # píxeles por línea de texto en modo wrap
ROWH_BASE = 35        # alto base de fila sin wrap
CHAR_PX = 7           # ancho aproximado de un carácter en px


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

        # Orden alternante por columna: col_idx -> True (desc) / False (asc)
        self.sort_state = {}
        # Asignaciones de nombres GBIF: nombre_gbif -> col_idx
        self.name_assignments = {}
        # Comboboxes colocados sobre las cabeceras: col_idx -> Combobox
        self.header_combos = {}
        # Modo wrap de texto
        self.wrap_mode = tk.BooleanVar(value=False)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=ROWH_BASE, font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#f0f0f0")

        # --- Barra Superior ---
        top_bar = tk.Frame(self, bg="#e0e0e0", padx=10, pady=5)
        top_bar.pack(fill="x")

        self.lbl_info = tk.Label(
            top_bar,
            text="Resultados del Parseo y Contraste GBIF (Doble clic en celda: editar | en cabecera: ordenar)",
            font=("Segoe UI", 9, "bold"), bg="#e0e0e0", fg="#333333"
        )
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

        tk.Checkbutton(
            top_bar, text="↩ Ajustar texto (wrap)", variable=self.wrap_mode,
            command=self.alternar_wrap, bg="#e0e0e0", font=("Segoe UI", 9, "bold")
        ).pack(side="right", padx=10, pady=5)

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
        scroll_x = ttk.Scrollbar(table_container, orient="horizontal")
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.configure(xscrollcommand=self._on_xscroll)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        scroll_x.configure(command=self.tree.xview)
        self.tree.pack(side="left", fill="both", expand=True)

        # Eventos
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click_release)
        self.tree.bind("<B1-Motion>", lambda e: self.after_idle(self._place_header_controls))
        self.tree.bind("<Configure>", lambda e: self.after_idle(self._place_header_controls))

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
            command=self.exportar_excel
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            btns_frame, text="🗄️ Guardar / Generar Access (.accdb)", bg="#1f6fb2", fg="white",
            font=("Segoe UI", 9, "bold"), padx=10, pady=6, relief="flat",
            command=self.exportar_access
        ).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------
    def set_welcome(self, welcome):
        self.welcome_frame = welcome

    def close_viewer(self):
        if self.welcome_frame:
            self.pack_forget()
            self.welcome_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def load_data(self, fields, rows, output_filepath=""):
        self.fields = list(fields)
        self.rows = rows
        self.filtered_rows = list(rows)
        self.output_filepath = output_filepath
        self.current_filter = None
        self.sort_state = {}
        self.btn_clear_filter.pack_forget()

        if output_filepath:
            self.lbl_path.config(text=f"📁 Archivo guardado con éxito en: {output_filepath}")

        # Asignaciones iniciales de nombres GBIF presentes en las cabeceras
        self.name_assignments = {}
        for i, f in enumerate(self.fields):
            if f in GBIF_FIELD_NAMES and f not in self.name_assignments:
                self.name_assignments[f] = i

        self._reconstruir_columnas()

    def _reconstruir_columnas(self):
        self._destruir_header_controls()

        self.tree["columns"] = []
        col_ids = [f"col_{i}" for i in range(len(self.fields))]
        self.tree["columns"] = col_ids

        for i, col_name in enumerate(self.fields):
            col_id = col_ids[i]
            texto = col_name if col_name else "(sin nombre)"
            self.tree.heading(col_id, text=texto)
            w = max(len(str(col_name)) * CHAR_PX, 140)
            self.tree.column(col_id, width=w, minwidth=60, anchor="w", stretch=False)

        self._crear_header_controls()
        self._place_header_controls()
        self.actualizar_vista_tabla()

    # ------------------------------------------------------------------
    # Controles de selección sobre las cabeceras (nombres GBIF)
    # ------------------------------------------------------------------
    def _destruir_header_controls(self):
        for combo in self.header_combos.values():
            combo.destroy()
        self.header_combos = {}

    def _crear_header_controls(self):
        self._destruir_header_controls()
        for i in range(len(self.fields)):
            combo = ttk.Combobox(self.tree, state="readonly", font=("Segoe UI", 8))
            combo.bind("<<ComboboxSelected>>", lambda e, idx=i: self._on_asignar_nombre(idx, e))
            self.header_combos[i] = combo
        self._refrescar_header_controls()

    def _refrescar_header_controls(self):
        for i, combo in self.header_combos.items():
            if i >= len(self.fields):
                continue
            actual = self.fields[i]
            # Nombres disponibles: no asignados, o asignados a esta misma columna
            disponibles = [BLANK]
            for name in GBIF_FIELD_NAMES:
                col_asig = self.name_assignments.get(name)
                if col_asig is None or col_asig == i:
                    disponibles.append(name)
                elif name == actual:
                    disponibles.append(name)
            combo["values"] = disponibles
            combo.set(actual if actual else BLANK)

    def _on_asignar_nombre(self, col_idx, event=None):
        combo = self.header_combos.get(col_idx)
        if not combo:
            return
        eleccion = combo.get()
        nombre_anterior = self.fields[col_idx]

        if eleccion == BLANK or eleccion == "":
            # Dejar en blanco: libera el nombre GBIF que ocupara esta columna
            for name, idx in list(self.name_assignments.items()):
                if idx == col_idx:
                    del self.name_assignments[name]
            self.fields[col_idx] = ""
        else:
            # ¿Está ya asignado a otra columna?
            col_otra = self.name_assignments.get(eleccion)
            if col_otra is not None and col_otra != col_idx:
                messagebox.showwarning(
                    "Nombre en uso",
                    f"El nombre '{eleccion}' ya está asignado a otra columna.\n"
                    "Déjalo en blanco allí antes de usarlo aquí.",
                    parent=self
                )
                self._refrescar_header_controls()
                return
            # Liberar el nombre anterior de esta columna
            if nombre_anterior in GBIF_FIELD_NAMES and self.name_assignments.get(nombre_anterior) == col_idx:
                del self.name_assignments[nombre_anterior]
            # Liberar cualquier asignación previa del nuevo nombre a esta columna
            self.name_assignments[eleccion] = col_idx
            self.fields[col_idx] = eleccion

        self.tree.heading(f"col_{col_idx}", text=self.fields[col_idx] if self.fields[col_idx] else "(sin nombre)")
        self._refrescar_header_controls()
        self._place_header_controls()

    def _col_from_widget(self, widget):
        for idx, combo in self.header_combos.items():
            if combo is widget:
                return idx
        return None

    def _on_xscroll(self, first, last):
        # Redirigir a la scrollbar horizontal real
        for w in self.tree.master.winfo_children():
            if isinstance(w, ttk.Scrollbar) and w.cget("orient") == "horizontal":
                w.set(first, last)
                break
        self.after_idle(self._place_header_controls)

    def _total_width(self):
        total = 0
        for i in range(len(self.fields)):
            try:
                total += int(self.tree.column(f"col_{i}", "width"))
            except Exception:
                pass
        return total

    def _header_x(self, col_idx):
        offset = float(self.tree.xview()[0]) * self._total_width()
        x = 0
        for i in range(col_idx):
            try:
                x += int(self.tree.column(f"col_{i}", "width"))
            except Exception:
                pass
        return x - offset

    def _place_header_controls(self):
        if not self.fields:
            return
        try:
            header_h = 24
            for i, combo in self.header_combos.items():
                if i >= len(self.fields):
                    continue
                w = int(self.tree.column(f"col_{i}", "width"))
                x = self._header_x(i)
                combo.place(x=x + 2, y=1, width=max(w - 6, 40), height=header_h)
        except Exception:
            pass

    def _on_tree_click_release(self, event):
        # Tras redimensionar una cabecera con el ratón, reposicionar los controles
        region = self.tree.identify("region", event.x, event.y)
        if region in ("heading", "separator"):
            self.after_idle(self._place_header_controls)

    # ------------------------------------------------------------------
    # Wrap inteligente
    # ------------------------------------------------------------------
    def alternar_wrap(self):
        self.actualizar_vista_tabla()

    def _col_char_width(self, col_idx):
        try:
            w = int(self.tree.column(f"col_{col_idx}", "width"))
        except Exception:
            w = 140
        return max(w // CHAR_PX, 8)

    def _wrap_valor(self, valor, col_idx):
        s = str(valor)
        if not s:
            return s
        ancho = self._col_char_width(col_idx)
        lineas = []
        for parte in s.split("\n"):
            lineas.extend(textwrap.wrap(parte, width=ancho) or [""])
        return "\n".join(lineas)

    # ------------------------------------------------------------------
    # Orden alternante por doble clic en cabecera
    # ------------------------------------------------------------------
    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            column_id = self.tree.identify_column(event.x)
            try:
                col_idx = int(column_id.replace('#', '')) - 1
            except ValueError:
                return
            if 0 <= col_idx < len(self.fields):
                reverse = self.sort_state.get(col_idx, False)
                self.ordenar_columna(col_idx, self.fields[col_idx], reverse)
                self.sort_state[col_idx] = not reverse
        elif region == "cell":
            column_id = self.tree.identify_column(event.x)
            try:
                col_idx = int(column_id.replace('#', '')) - 1
            except ValueError:
                return
            item_id = self.tree.identify_row(event.y)
            if item_id and 0 <= col_idx < len(self.fields):
                self.editar_celda_en_linea(item_id, column_id, col_idx)

    def ordenar_columna(self, col_idx, col_name, reverse):
        try:
            self.filtered_rows.sort(key=lambda x: (x[col_idx] == "", str(x[col_idx]).lower()), reverse=reverse)
        except Exception:
            self.filtered_rows.sort(key=lambda x: str(x[col_idx]).lower(), reverse=reverse)

        self.actualizar_vista_tabla()
        col_id = f"col_{col_idx}"
        texto = col_name if col_name else "(sin nombre)"
        self.tree.heading(col_id, text=f"{texto} {'▼' if reverse else '▲'}")

    # ------------------------------------------------------------------
    # Menú contextual de cabecera: renombrar / eliminar columna
    # ------------------------------------------------------------------
    def _menu_cabecera(self, col_idx, event):
        col_name = self.fields[col_idx]
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"✏ Renombrar columna [{col_name or '(sin nombre)'}]...", command=lambda: self.renombrar_columna(col_idx))
        menu.add_command(label=f"🗑 Eliminar columna [{col_name or '(sin nombre)'}]", command=lambda: self.eliminar_columna(col_idx))
        menu.tk_popup(event.x_root, event.y_root)

    def renombrar_columna(self, col_idx):
        actual = self.fields[col_idx]
        nuevo = simpledialog.askstring(
            "Renombrar columna",
            f"Nuevo nombre para la columna '{actual or '(sin nombre)'}':",
            initialvalue=actual, parent=self
        )
        if nuevo is None:
            return
        nuevo = nuevo.strip()
        if nuevo == actual:
            return
        # Liberar asignación GBIF anterior si cambia el nombre
        if actual in GBIF_FIELD_NAMES and self.name_assignments.get(actual) == col_idx:
            del self.name_assignments[actual]
        if nuevo == "":
            self.fields[col_idx] = ""
        else:
            if nuevo in self.fields and self.fields.index(nuevo) != col_idx:
                messagebox.showerror("Nombre duplicado", f"El nombre '{nuevo}' ya existe en otra columna.", parent=self)
                return
            if nuevo in GBIF_FIELD_NAMES:
                self.name_assignments[nuevo] = col_idx
            self.fields[col_idx] = nuevo
        self.tree.heading(f"col_{col_idx}", text=self.fields[col_idx] if self.fields[col_idx] else "(sin nombre)")
        self._refrescar_header_controls()
        self._place_header_controls()

    def eliminar_columna(self, col_idx):
        col_name = self.fields[col_idx]
        if not messagebox.askyesno("Eliminar columna", f"¿Eliminar la columna '{col_name or '(sin nombre)'}'?\nLos datos de esa columna se perderán.", parent=self):
            return
        # Liberar nombre GBIF asignado a esta columna
        for name, idx in list(self.name_assignments.items()):
            if idx == col_idx:
                del self.name_assignments[name]
            elif idx > col_idx:
                self.name_assignments[name] = idx - 1
        del self.fields[col_idx]
        for r in self.rows:
            if col_idx < len(r):
                del r[col_idx]
        # Recalcular filtro activo si apuntaba a esta columna
        self.current_filter = None
        self.btn_clear_filter.pack_forget()
        self.filtered_rows = list(self.rows)
        self._reconstruir_columnas()

    # ------------------------------------------------------------------
    # Menú contextual de celda: filtrar / copiar
    # ------------------------------------------------------------------
    def on_right_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            column_id = self.tree.identify_column(event.x)
            try:
                col_idx = int(column_id.replace('#', '')) - 1
            except ValueError:
                return
            if 0 <= col_idx < len(self.fields):
                self._menu_cabecera(col_idx, event)
            return
        if region == "cell":
            column_id = self.tree.identify_column(event.x)
            try:
                col_idx = int(column_id.replace('#', '')) - 1
            except ValueError:
                return
            item_id = self.tree.identify_row(event.y)

            if item_id and 0 <= col_idx < len(self.fields):
                values = self.tree.item(item_id, "values")
                if col_idx >= len(values):
                    return
                val_celda = values[col_idx]
                col_name = self.fields[col_idx]

                menu = tk.Menu(self, tearoff=0)
                menu.add_command(label=f"Filtrar por [{col_name or '(sin nombre)'} = '{val_celda}']", command=lambda: self.aplicar_filtro(col_idx, val_celda, col_name))
                menu.add_command(label="Copiar valor de celda", command=lambda: self.copiar_valor(val_celda))
                menu.tk_popup(event.x_root, event.y_root)

    def aplicar_filtro(self, col_idx, val_filtro, col_name):
        if val_filtro != "":
            self.current_filter = (col_idx, val_filtro)
            self.filtered_rows = [
                r for r in self.rows
                if col_idx < len(r) and str(r[col_idx]) == str(val_filtro)
            ]
            self.actualizar_vista_tabla()
            self.btn_clear_filter.pack(side="right", padx=5, pady=5)
            self.lbl_info.config(text=f"Filtrado por [{col_name or '(sin nombre)'} = '{val_filtro}'] ({len(self.filtered_rows)} resultados)")

    def copiar_valor(self, valor):
        self.root.clipboard_clear()
        self.root.clipboard_append(str(valor))
        messagebox.showinfo("Copiado", f"Valor copiado al portapapeles:\n'{valor}'", parent=self)

    def limpiar_filtro(self):
        self.current_filter = None
        self.filtered_rows = list(self.rows)
        self.actualizar_vista_tabla()
        self.btn_clear_filter.pack_forget()
        self.lbl_info.config(text="Resultados del Parseo y Contraste GBIF (Doble clic en celda: editar | en cabecera: ordenar)")

    # ------------------------------------------------------------------
    # Edición en línea de celdas
    # ------------------------------------------------------------------
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
        self.active_entry.insert(0, current_val.replace("\n", " "))
        self.active_entry.select_range(0, tk.END)
        self.active_entry.focus()

        def guardar_cambio(event=None):
            if not self.active_entry or not self.active_entry.winfo_exists():
                return
            new_val = self.active_entry.get()
            self.active_entry.destroy()

            vals_list = list(self.tree.item(item_id, "values"))
            while len(vals_list) <= col_idx:
                vals_list.append("")
            vals_list[col_idx] = new_val
            self.tree.item(item_id, values=vals_list)

            children = self.tree.get_children()
            if item_id in children:
                row_tree_idx = children.index(item_id)
                if row_tree_idx < len(self.filtered_rows):
                    while len(self.filtered_rows[row_tree_idx]) <= col_idx:
                        self.filtered_rows[row_tree_idx].append("")
                    self.filtered_rows[row_tree_idx][col_idx] = new_val

        self.active_entry.bind("<Return>", guardar_cambio)
        self.active_entry.bind("<FocusOut>", lambda e: guardar_cambio())

    # ------------------------------------------------------------------
    # Enlace GBIF
    # ------------------------------------------------------------------
    def abrir_enlace_seleccionado(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Aviso", "Por favor, seleccione un registro de la tabla.", parent=self)
            return

        item_values = self.tree.item(selected_item[0], "values")
        if "gbif_uri" in self.fields:
            idx = self.fields.index("gbif_uri")
            if idx < len(item_values):
                uri = item_values[idx]
                if uri and str(uri).startswith("http"):
                    webbrowser.open(uri)
                    return

        messagebox.showinfo("Información", "El registro seleccionado no tiene un URI resolvible válido en GBIF.", parent=self)

    # ------------------------------------------------------------------
    # Validación de nombres y exportación
    # ------------------------------------------------------------------
    def _validar_nombres_columnas(self):
        """Devuelve None si todo es válido; si no, un mensaje de error."""
        sin_nombre = [i + 1 for i, f in enumerate(self.fields) if not str(f).strip()]
        if sin_nombre:
            return (
                "Hay columnas sin nombre (posiciones " + ", ".join(map(str, sin_nombre)) + ").\n"
                "Asigna un nombre (o déjalas con su nombre original) antes de guardar."
            )
        vistos = {}
        duplicados = []
        for f in self.fields:
            clave = str(f).strip()
            if clave in vistos:
                if clave not in duplicados:
                    duplicados.append(clave)
            else:
                vistos[clave] = True
        if duplicados:
            return "Hay nombres de columna duplicados:\n" + "\n".join(duplicados) + "\n\nNo se guardará nada hasta resolverlo."
        return None

    def _exportar(self, funcion):
        error = self._validar_nombres_columnas()
        if error:
            messagebox.showerror("Exportación bloqueada", error, parent=self)
            return
        funcion(self.root, self.fields, self.filtered_rows)

    def exportar_excel(self):
        self._exportar(export_to_excel)

    def exportar_access(self):
        self._exportar(export_to_access)

    # ------------------------------------------------------------------
    # Vista de tabla
    # ------------------------------------------------------------------
    def actualizar_vista_tabla(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        max_lineas = 1
        for row in self.filtered_rows:
            if self.wrap_mode.get():
                valores = []
                for i in range(len(self.fields)):
                    v = row[i] if i < len(row) else ""
                    v_wrapped = self._wrap_valor(v, i)
                    max_lineas = max(max_lineas, v_wrapped.count("\n") + 1)
                    valores.append(v_wrapped)
            else:
                valores = list(row)
            self.tree.insert("", "end", values=valores)

        nuevo_alto = ROWH_BASE if not self.wrap_mode.get() else max(ROWH_BASE, max_lineas * LINE_PX + 6)
        self.style.configure("Treeview", rowheight=nuevo_alto)