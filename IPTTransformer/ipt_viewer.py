"""
ipt_viewer.py
==============
Visor en esquema de estrella con herramientas de inspección estructural,
mapeo dinámico, doble clic en cabeceras para reestructuración/análisis
y exportación a formatos tabulares, Excel y Access.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dwc_manager import get_term_metadata, get_terms_for_type
from ipt_dialogs import MultiRecordSplitterDialog
from ipt_export import export_project, open_directory
from ipt_model import UNMAPPED, hierarchy_entries

class ToolTip:
    def __init__(self, widget, text_func):
        self.widget = widget
        self.text_func = text_func
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(300, self.showtip)

    def unschedule(self):
        id_val = self.id
        self.id = None
        if id_val:
            self.widget.after_cancel(id_val)

    def showtip(self, event=None):
        text = self.text_func()
        if not text or self.tipwindow:
            return
        
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            tw, text=text, justify=tk.LEFT,
            background="#fff8dc", fg="#111111", relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9), padx=8, pady=6
        )
        label.pack(fill="both", expand=True)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


class IPTViewerWindow(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.welcome_frame = None
        self.datasets = []
        self.original_file_path = None
        self.core_config = None
        self.extensions_config = []

        # Barra de navegación superior
        top_nav = tk.Frame(self, bg="#dcdcdc", padx=10, pady=8)
        top_nav.pack(fill="x")

        tk.Label(top_nav, text="🌟 Visor Estrella IPT / Mapeo y Análisis Relacional", font=("Segoe UI", 10, "bold"), bg="#dcdcdc", fg="#333333").pack(side="left")
        
        tk.Button(
            top_nav, text="⬅ Volver", bg="#6c757d", fg="white", 
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4, 
            command=self.close_viewer
        ).pack(side="right", padx=5)

        # Botón de Guardado y Exportación Principal
        tk.Button(
            top_nav, text="Guardar / Exportar (TSV, Excel)", bg="#289530", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, 
            command=self.ejecutar_guardado_exportacion
        ).pack(side="right", padx=5)

        # Opciones de exportación en la barra superior
        self.var_excel = tk.BooleanVar(value=False)
        self.var_access = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(top_nav, text="Excel (.xlsx)", variable=self.var_excel).pack(side="right", padx=5)
        # Access no estaba implementado aquí: se evita anunciar una salida ficticia.

        self.paned_window = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.paned_window.pack(fill="both", expand=True, padx=5, pady=5)

        self.top_container = tk.Frame(self.paned_window, relief=tk.RIDGE, bd=1)
        self.paned_window.add(self.top_container, weight=1)

        self.bottom_container = tk.Frame(self.paned_window, relief=tk.RIDGE, bd=1)
        self.paned_window.add(self.bottom_container, weight=1)

        self.notebook_ext = ttk.Notebook(self.bottom_container)
        self.notebook_ext.pack(fill="both", expand=True)

        self.core_tab_view = None
        self.ext_tab_views = []

    def set_welcome(self, welcome):
        self.welcome_frame = welcome

    def close_viewer(self):
        if self.welcome_frame:
            if not messagebox.askyesno(
                "Volver a la carga", "Los cambios no exportados se perderán. ¿Desea volver?",
                parent=self
            ):
                return
            self.welcome_frame.pack(fill="both", expand=True)
            self.destroy()

    def load_datasets(self, datasets_config, original_path, core_cfg, ext_cfgs):
        self.datasets = datasets_config
        self.original_file_path = original_path
        self.core_config = core_cfg
        self.extensions_config = ext_cfgs
        
        for widget in self.top_container.winfo_children():
            widget.destroy()
        for tab in self.notebook_ext.winfo_children():
            tab.destroy()
        self.ext_tab_views = []

        if not datasets_config:
            return

        # 1. Panel Core
        core_cfg = datasets_config[0]
        self.core_tab_view = IPTDatasetPanel(
            self.top_container, 
            title=f"Core: {core_cfg['tipo']}", 
            cfg=core_cfg,
            is_core=True,
            on_row_select=self.on_core_row_selected,
            on_structure_change=self.on_dataset_structure_changed
        )
        self.core_tab_view.pack(fill="both", expand=True)

        # 2. Paneles de Extensiones
        for ext_cfg in datasets_config[1:]:
            ext_panel = IPTDatasetPanel(
                self.notebook_ext,
                title=f"Ext: {ext_cfg['tipo']}",
                cfg=ext_cfg,
                is_core=False,
                on_structure_change=self.on_dataset_structure_changed
            )
            self.notebook_ext.add(ext_panel, text=ext_cfg['tipo'])
            self.ext_tab_views.append(ext_panel)

    def on_core_row_selected(self, core_id_value):
        if not core_id_value:
            return
        for ext_panel in self.ext_tab_views:
            ext_panel.filtrar_por_fk(core_id_value)

    def on_dataset_structure_changed(self, new_extension):
        """Callback invocado si la reestructuración desde el título crea una nueva extensión."""
        # Una extensión DwC debe apuntar al Core, no a otra extensión.
        core_ids = set()
        if self.core_config:
            i = self.core_config["fields"].index(self.core_config["id_col"])
            core_ids = {str(row[i]) for row in self.core_config["rows"]}
        if new_extension:
            fk_idx = new_extension["fields"].index(new_extension["fk_col"])
            if any(str(row[fk_idx]) not in core_ids for row in new_extension["rows"]):
                raise ValueError("La extensión nueva no está vinculada al Core.")
        if new_extension and new_extension not in self.extensions_config:
            self.extensions_config.append(new_extension)
            ext_panel = IPTDatasetPanel(
                self.notebook_ext,
                title=f"Ext: {new_extension['tipo']}",
                cfg=new_extension,
                is_core=False,
                on_structure_change=self.on_dataset_structure_changed
            )
            self.notebook_ext.add(ext_panel, text=new_extension['tipo'])
            self.ext_tab_views.append(ext_panel)

    def ejecutar_guardado_exportacion(self):
        if not self.original_file_path or not self.core_config:
            messagebox.showwarning("Aviso", "No hay datos cargados para exportar.", parent=self)
            return

        output_base_dir = filedialog.askdirectory(title="Seleccionar Directorio de Salida")
        if not output_base_dir:
            return

        try:
            ipt_transf_dir = export_project(
                output_base_dir, self.original_file_path, self.core_config,
                self.extensions_config, excel=self.var_excel.get()
            )

            messagebox.showinfo(
                "Exportación Exitosa", 
                f"Estructura creada correctamente en:\n{ipt_transf_dir}\n\n"
                f"• Copia original en carpeta 'Old'\n"
                "• Tablas y mapeos guardados (project.json).\n"
                "No es un DwC-A completo: no incluye meta.xml ni eml.xml.",
                parent=self
            )

            if messagebox.askyesno("Abrir Directorio", "¿Desea abrir la carpeta con los archivos generados?", parent=self):
                try:
                    open_directory(ipt_transf_dir)
                except OSError as exc:
                    messagebox.showwarning("Abrir carpeta", str(exc), parent=self)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo completar el proceso de exportación: {e}", parent=self)


class IPTDatasetPanel(tk.Frame):
    def __init__(self, parent, title, cfg, is_core, on_row_select=None, on_structure_change=None):
        super().__init__(parent, padx=5, pady=5)
        self.cfg = cfg
        self.title = title
        self.fields = list(cfg['fields'])
        self.rows = [list(r) for r in cfg['rows']]
        self.filtered_rows = list(self.rows)
        self.is_core = is_core
        self.on_row_select = on_row_select
        self.on_structure_change = on_structure_change
        self.mapping_combos = []

        self.id_or_fk_col = cfg.get('id_col') if is_core else cfg.get('fk_col')
        self.self_id_col = cfg.get('self_id_col')
        self.self_parent_col = cfg.get('self_parent_col')

        self.ipt_terms = get_terms_for_type(cfg['tipo'], is_core=is_core)
        if not self.ipt_terms:
            self.ipt_terms = ["coreID", "id", "name", "value", "remarks"]

        header_frame = tk.Frame(self, bg="#e9ecef", padx=5, pady=4)
        header_frame.pack(fill="x", pady=(0, 3))

        info_txt = f"📂 {title} | {'ID Principal: ' if is_core else 'FK Core: '}{self.id_or_fk_col}  (💡 Doble clic aquí para Analizar/Reestructurar)"
        
        self.lbl_title = tk.Label(header_frame, text=info_txt, font=("Segoe UI", 9, "bold"), bg="#e9ecef", fg="#1f6fb2", cursor="hand2")
        self.lbl_title.pack(side="left")

        # Vincular doble clic en el título y en el marco de la cabecera
        self.lbl_title.bind("<Double-Button-1>", lambda e: self.disparar_analizador_desde_panel())
        header_frame.bind("<Double-Button-1>", lambda e: self.disparar_analizador_desde_panel())

        ToolTip(self.lbl_title, lambda: "Haga DOBLE CLIC sobre este título para abrir el Asistente de Análisis de Tablas y Reestructuración.")

        if not is_core:
            tk.Button(
                header_frame, text="🔄 Ver Todos", bg="#d9534f", fg="white", 
                font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2,
                command=self.quitar_filtro_fk
            ).pack(side="right")

        table_main_frame = tk.Frame(self)
        table_main_frame.pack(fill="both", expand=True)

        scroll_x = ttk.Scrollbar(table_main_frame, orient="horizontal", command=self.on_horizontal_scroll)
        scroll_x.pack(side="bottom", fill="x")

        self.canvas_mapping = tk.Canvas(table_main_frame, height=36, bg="#e8e8e8", highlightthickness=0)
        self.canvas_mapping.pack(side="top", fill="x")

        self.mapping_inner_frame = tk.Frame(self.canvas_mapping, bg="#e8e8e8")
        self.canvas_mapping.create_window((0, 0), window=self.mapping_inner_frame, anchor="nw")

        tree_container = tk.Frame(table_main_frame)
        tree_container.pack(side="top", fill="both", expand=True)

        self.is_hierarchical = not is_core and bool(self.self_id_col and self.self_parent_col)
        tree_show_mode = "tree headings" if self.is_hierarchical else "headings"

        self.tree = ttk.Treeview(tree_container, show=tree_show_mode, xscrollcommand=scroll_x.set)
        scroll_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        scroll_y.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        if is_core:
            self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.setup_columns_and_mappings()
        self.actualizar_vista_tabla()

        self.mapping_inner_frame.update_idletasks()
        self.canvas_mapping.config(scrollregion=self.canvas_mapping.bbox("all"))

    def disparar_analizador_desde_panel(self):
        """Abre el asistente de análisis estructural al hacer doble clic en el título del panel."""
        if not self.is_core:
            messagebox.showinfo(
                "Normalización", "La extracción se realiza desde el Core. "
                "Reestructurar extensiones requiere definir su relación con el Core.",
                parent=self
            )
            return
        dialog = MultiRecordSplitterDialog(
            self.winfo_toplevel(), 
            self.fields, 
            self.rows, 
            self.id_or_fk_col, 
            dataset_name=self.cfg['tipo']
        )
        self.winfo_toplevel().wait_window(dialog)

        if getattr(dialog, "changed", False):
            self.fields = list(dialog.headers)
            self.cfg["fields"] = list(self.fields)
            self.cfg["mapping"] = {
                field: term for field, term in self.cfg.get("mapping", {}).items()
                if field in self.fields
            }
            for widget in self.mapping_inner_frame.winfo_children():
                widget.destroy()
            self.mapping_combos = []
            self.setup_columns_and_mappings()
            self.actualizar_filas(dialog.clean_rows)
            self.mapping_inner_frame.update_idletasks()
            self.canvas_mapping.config(scrollregion=self.canvas_mapping.bbox("all"))

        if hasattr(dialog, "extracted_datasets") and dialog.extracted_datasets:
            for new_ext in dialog.extracted_datasets:
                if self.on_structure_change:
                    self.on_structure_change(new_ext)

    def actualizar_filas(self, nuevas_filas):
        self.rows = [list(r) for r in nuevas_filas]
        self.cfg["rows"] = [list(r) for r in self.rows]
        self.filtered_rows = list(self.rows)
        self.actualizar_vista_tabla()

    def on_horizontal_scroll(self, *args):
        self.tree.xview(*args)
        self.canvas_mapping.xview(*args)

    def setup_columns_and_mappings(self):
        self.col_ids = [f"col_{i}" for i in range(len(self.fields))]
        self.tree["columns"] = self.col_ids

        for i, col_name in enumerate(self.fields):
            col_id = self.col_ids[i]
            w = max(len(str(col_name)) * 12, 160)
            
            self.tree.heading(col_id, text=col_name, command=lambda idx=i, name=col_name: self.ordenar_columna(idx, name, False))
            self.tree.column(col_id, width=w, minwidth=120, anchor="w", stretch=False)

            cell_frame = tk.Frame(self.mapping_inner_frame, bg="#e8e8e8", width=w, height=32)
            cell_frame.pack_propagate(False)
            cell_frame.pack(side="left", padx=1, pady=2)

            is_fk_column = (not self.is_core and col_name.lower() == str(self.id_or_fk_col).lower())

            cb = ttk.Combobox(cell_frame, values=[UNMAPPED] + self.ipt_terms, state="disabled" if is_fk_column else "readonly", font=("Segoe UI", 8))
            cb.pack(fill="both", expand=True)

            if is_fk_column:
                cb.set("coreID")
            else:
                cb.set("(Sin mapear)")

            def on_enter(e, f_cell=cell_frame):
                f_cell.config(bg="#bde4ff")

            def on_leave(e, f_cell=cell_frame):
                f_cell.config(bg="#e8e8e8")

            cell_frame.bind("<Enter>", on_enter)
            cell_frame.bind("<Leave>", on_leave)
            cb.bind("<Enter>", on_enter)
            cb.bind("<Leave>", on_leave)

            def get_current_metadata(combo=cb, is_fk=is_fk_column, source_col=col_name):
                val = combo.get()
                if is_fk:
                    return "🔒 Clave Foránea (FK).\nMapeada permanentemente a 'coreID'."
                if val == "(Sin mapear)":
                    return f"Columna: '{source_col}'\nSeleccione un término Darwin Core."
                meta = get_term_metadata(self.cfg['tipo'], val, is_core=self.is_core)
                return f"📌 Término: {meta.get('label')}\n\n📖 Definición:\n{meta.get('definition')}\n\n💡 Ejemplo:\n{meta.get('example')}"

            ToolTip(cell_frame, get_current_metadata)
            ToolTip(cb, get_current_metadata)

            self.mapping_combos.append(cb)
            if not is_fk_column:
                cb.bind("<<ComboboxSelected>>", lambda e, combo=cb: self.on_mapping_selected(combo))

                for term in self.ipt_terms:
                    if term.lower() == col_name.lower():
                        cb.set(term)
                        break
                cb.set(self.cfg.get("mapping", {}).get(col_name, cb.get()))
        self.persist_mapping()

    def persist_mapping(self):
        self.cfg["mapping"] = {
            field: combo.get() for field, combo in zip(self.fields, self.mapping_combos)
        }

    def on_mapping_selected(self, selected_combo):
        chosen_val = selected_combo.get()
        if chosen_val == "(Sin mapear)":
            self.persist_mapping()
            return

        for cb in self.mapping_combos:
            if cb != selected_combo and cb.get() == chosen_val:
                messagebox.showwarning("Término Duplicado", f"El término '{chosen_val}' ya está asignado.", parent=self)
                selected_combo.set("(Sin mapear)")
                self.persist_mapping()
                return
        self.persist_mapping()

    def ordenar_columna(self, col_idx, col_name, reverse):
        try:
            self.filtered_rows.sort(key=lambda x: (x[col_idx] == "", str(x[col_idx]).lower()), reverse=reverse)
        except Exception:
            self.filtered_rows.sort(key=lambda x: str(x[col_idx]).lower(), reverse=reverse)

        self.actualizar_vista_tabla()
        col_id = self.col_ids[col_idx]
        self.tree.heading(col_id, text=f"{col_name} {'▲' if reverse else '▼'}", command=lambda: self.ordenar_columna(col_idx, col_name, not reverse))

    def on_tree_select(self, event):
        if not self.is_core or not self.on_row_select:
            return
        selected_items = self.tree.selection()
        if not selected_items:
            return
        item_values = self.tree.item(selected_items[0], "values")
        try:
            id_col_idx = self.fields.index(self.id_or_fk_col)
            core_id_val = item_values[id_col_idx]
            self.on_row_select(core_id_val)
        except ValueError:
            if item_values:
                self.on_row_select(item_values[0])

    def filtrar_por_fk(self, core_id_val):
        try:
            fk_col_idx = self.fields.index(self.id_or_fk_col)
        except ValueError:
            fk_col_idx = 0
        self.filtered_rows = [r for r in self.rows if str(r[fk_col_idx]) == str(core_id_val)]
        self.actualizar_vista_tabla()

    def quitar_filtro_fk(self):
        self.filtered_rows = list(self.rows)
        self.actualizar_vista_tabla()

    def actualizar_vista_tabla(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.is_hierarchical:
            for row in self.filtered_rows:
                self.tree.insert("", "end", values=row)
        else:
            try:
                self_id_idx = self.fields.index(self.self_id_col)
                self_parent_idx = self.fields.index(self.self_parent_col)
            except ValueError:
                for row in self.filtered_rows:
                    self.tree.insert("", "end", values=row)
                return

            nodes = {}
            for parent, index in hierarchy_entries(
                self.filtered_rows, self_id_idx, self_parent_idx
            ):
                row = self.filtered_rows[index]
                nodes[index] = self.tree.insert(
                    nodes.get(parent, ""), "end",
                    text=str(row[self_id_idx]), values=row
                )
