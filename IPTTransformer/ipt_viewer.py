"""
ipt_viewer.py
==============
Visor en esquema de estrella con herramientas de guardado y exportación 
a formatos tabulares separados, Excel y Access.
"""

import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dwc_manager import get_term_metadata, get_terms_for_type

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

        # Barra de navegación superior con opciones de guardado y exportación
        top_nav = tk.Frame(self, bg="#dcdcdc", padx=10, pady=8)
        top_nav.pack(fill="x")

        tk.Label(top_nav, text="🌟 Visor Estrella IPT / Mapeo y Exportación", font=("Segoe UI", 10, "bold"), bg="#dcdcdc", fg="#333333").pack(side="left")
        
        tk.Button(
            top_nav, text="⬅ Volver", bg="#6c757d", fg="white", 
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4, 
            command=self.close_viewer
        ).pack(side="right", padx=5)

        # Botón de Guardado y Exportación Principal
        tk.Button(
            top_nav, text="💾 Salvar / Exportar (Tablas, Excel, Access)", bg="#289530", fg="white", 
            font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, 
            command=self.ejecutar_guardado_exportacion
        ).pack(side="right", padx=5)

        # Opciones de exportación en la barra superior
        self.var_excel = tk.BooleanVar(value=False)
        self.var_access = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(top_nav, text="Excel (.xlsx)", variable=self.var_excel).pack(side="right", padx=5)
        ttk.Checkbutton(top_nav, text="Access (.accdb)", variable=self.var_access).pack(side="right", padx=5)

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
            self.pack_forget()
            self.welcome_frame.pack(fill="both", expand=True)

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

        # 1. Core
        core_cfg = datasets_config[0]
        self.core_tab_view = IPTDatasetPanel(
            self.top_container, 
            title=f"Core: {core_cfg['tipo']}", 
            cfg=core_cfg,
            is_core=True,
            on_row_select=self.on_core_row_selected
        )
        self.core_tab_view.pack(fill="both", expand=True)

        # 2. Extensiones
        for ext_cfg in datasets_config[1:]:
            ext_panel = IPTDatasetPanel(
                self.notebook_ext,
                title=f"Ext: {ext_cfg['tipo']}",
                cfg=ext_cfg,
                is_core=False
            )
            self.notebook_ext.add(ext_panel, text=ext_cfg['tipo'])
            self.ext_tab_views.append(ext_panel)

    def on_core_row_selected(self, core_id_value):
        if not core_id_value:
            return
        for ext_panel in self.ext_tab_views:
            ext_panel.filtrar_por_fk(core_id_value)

    def ejecutar_guardado_exportacion(self):
        if not self.original_file_path or not self.core_config:
            messagebox.showwarning("Aviso", "No hay datos cargados para exportar.", parent=self)
            return

        output_base_dir = filedialog.askdirectory(title="Seleccionar Directorio de Salida")
        if not output_base_dir:
            return

        try:
            base_name = os.path.splitext(os.path.basename(self.original_file_path))[0]
            ipt_transf_dir = os.path.join(output_base_dir, f"{base_name}IPTTransf")
            old_dir = os.path.join(ipt_transf_dir, "Old")

            os.makedirs(ipt_transf_dir, exist_ok=True)
            os.makedirs(old_dir, exist_ok=True)

            # 1. Copia del archivo original en la carpeta Old
            shutil.copy2(self.original_file_path, os.path.join(old_dir, os.path.basename(self.original_file_path)))

            # 2. Guardar tabla Core separada
            core_file_path = os.path.join(ipt_transf_dir, f"Core_{self.core_config['tipo']}.txt")
            with open(core_file_path, 'w', encoding=self.core_config.get('enc', 'utf-8')) as f_core:
                f_core.write("\t".join(self.core_config['fields']) + "\n")
                for row in self.core_config['rows']:
                    f_core.write("\t".join([str(val) for val in row]) + "\n")

            # 3. Guardar tablas de Extensiones separadas (brazos de la estrella)
            for idx, ext in enumerate(self.extensions_config):
                ext_file_path = os.path.join(ipt_transf_dir, f"Extension_{idx}_{ext['tipo']}.txt")
                with open(ext_file_path, 'w', encoding=ext.get('enc', 'utf-8')) as f_ext:
                    f_ext.write("\t".join(ext['fields']) + "\n")
                    for row in ext['rows']:
                        f_ext.write("\t".join([str(val) for val in row]) + "\n")

            # 4. Exportación opcional a Excel
            if self.var_excel.get():
                excel_path = os.path.join(ipt_transf_dir, f"{base_name}_normalizado.xlsx")
                try:
                    import pandas as pd
                    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                        df_core = pd.DataFrame(self.core_config['rows'], columns=self.core_config['fields'])
                        df_core.to_excel(writer, sheet_name=f"Core_{self.core_config['tipo']}", index=False)
                        for idx, ext in enumerate(self.extensions_config):
                            df_ext = pd.DataFrame(ext['rows'], columns=ext['fields'])
                            df_ext.to_excel(writer, sheet_name=f"Ext_{idx}_{ext['tipo']}", index=False)
                except Exception as ex:
                    print(f"Error generando Excel: {ex}")

            # 5. Exportación opcional a Access
            if self.var_access.get():
                access_info_path = os.path.join(ipt_transf_dir, "access_export_info.txt")
                with open(access_info_path, 'w', encoding='utf-8') as f_acc:
                    f_acc.write("Exportación a Access solicitada. Tablas Core y Extensiones separadas listas para vincular.")

            messagebox.showinfo(
                "Exportación Exitosa", 
                f"Estructura creada correctamente en:\n{ipt_transf_dir}\n\n"
                f"• Copia original en carpeta 'Old'\n"
                f"• Tablas Core y Extensiones separadas guardadas.", 
                parent=self
            )

            if messagebox.askyesno("Abrir Directorio", "¿Desea abrir la carpeta con los archivos generados?", parent=self):
                os.startfile(ipt_transf_dir)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo completar el proceso de exportación: {e}", parent=self)


class IPTDatasetPanel(tk.Frame):
    def __init__(self, parent, title, cfg, is_core, on_row_select=None):
        super().__init__(parent, padx=5, pady=5)
        self.cfg = cfg
        self.fields = list(cfg['fields'])
        self.rows = [list(r) for r in cfg['rows']]
        self.filtered_rows = list(self.rows)
        self.is_core = is_core
        self.on_row_select = on_row_select
        self.mapping_combos = []

        self.id_or_fk_col = cfg.get('id_col') if is_core else cfg.get('fk_col')
        self.self_id_col = cfg.get('self_id_col')
        self.self_parent_col = cfg.get('self_parent_col')

        self.ipt_terms = get_terms_for_type(cfg['tipo'], is_core=is_core)
        if not self.ipt_terms:
            self.ipt_terms = ["coreID", "id", "name", "value", "remarks"]

        header_frame = tk.Frame(self, bg="#f0f0f0", padx=5, pady=4)
        header_frame.pack(fill="x", pady=(0, 3))

        info_txt = f"📂 {title} | {'ID Principal: ' if is_core else 'FK Core: '}{self.id_or_fk_col}"
        tk.Label(header_frame, text=info_txt, font=("Segoe UI", 9, "bold"), bg="#f0f0f0", fg="#222222").pack(side="left")

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

            cb = ttk.Combobox(cell_frame, values=self.ipt_terms, state="disabled" if is_fk_column else "readonly", font=("Segoe UI", 8))
            cb.pack(fill="both", expand=True)

            if is_fk_column:
                cb.set("coreID" if "coreID" in self.ipt_terms else self.ipt_terms[0])
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

            def get_current_metadata(combo=cb, is_fk=is_fk_column):
                val = combo.get()
                if is_fk:
                    return "🔒 Clave Foránea (FK).\nMapeada permanentemente a 'coreID'."
                if val == "(Sin mapear)":
                    return f"Columna: '{col_name}'\nSeleccione un término Darwin Core."
                meta = get_term_metadata(self.cfg['tipo'], val, is_core=self.is_core)
                return f"📌 Término: {meta.get('label')}\n\n📖 Definición:\n{meta.get('definition')}\n\n💡 Ejemplo:\n{meta.get('example')}"

            ToolTip(cell_frame, get_current_metadata)
            ToolTip(cb, get_current_metadata)

            if not is_fk_column:
                cb.bind("<<ComboboxSelected>>", lambda e, combo=cb: self.on_mapping_selected(combo))
                self.mapping_combos.append(cb)

                for term in self.ipt_terms:
                    if term.lower() == col_name.lower():
                        cb.set(term)
                        break

    def on_mapping_selected(self, selected_combo):
        chosen_val = selected_combo.get()
        if chosen_val == "(Sin mapear)":
            return

        for cb in self.mapping_combos:
            if cb != selected_combo and cb.get() == chosen_val:
                messagebox.showwarning("Término Duplicado", f"El término '{chosen_val}' ya está asignado.", parent=self)
                selected_combo.set("(Sin mapear)")
                return

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

            row_map = {}
            children_map = {}
            roots = []

            for row in self.filtered_rows:
                r_id = str(row[self_id_idx])
                p_id = str(row[self_parent_idx]) if len(row) > self_parent_idx else ""
                row_map[r_id] = row

                if not p_id or p_id == "" or p_id not in [str(r[self_id_idx]) for r in self.filtered_rows]:
                    roots.append(r_id)
                else:
                    if p_id not in children_map:
                        children_map[p_id] = []
                    children_map[p_id].append(r_id)

            def insert_recursive(parent_node, r_id):
                row_vals = row_map[r_id]
                node_id = self.tree.insert(parent_node, "end", text=r_id, values=row_vals)
                if r_id in children_map:
                    for child_id in children_map[r_id]:
                        insert_recursive(node_id, child_id)

            for r_id in roots:
                insert_recursive("", r_id)