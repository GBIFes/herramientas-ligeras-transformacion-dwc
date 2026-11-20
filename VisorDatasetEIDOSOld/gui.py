"""
gui.py
======

EIDOS Multivisor - Interfaz gráfica con ventana modal de configuración para DwCa,
incorporando selección y escritura libre de measurementType y acrónimos de numeración.
"""

from __future__ import annotations

import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from data_explorer import DataExplorer
from exporter import Exporter
from dwca_bridge import DwCaBridge


CHECK_OFF = "☐"
CHECK_ON = "☑"

EIDOS_WEB = (
    "https://iepnb.gob.es/"
    "areas-tematicas/"
    "especies-silvestres/"
    "eidos/"
)


class ProgressWindow:
    def __init__(self, parent, title="Procesando..."):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("450x150")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()

        self.top.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 225
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 75
        self.top.geometry(f"+{x}+{y}")

        self.label_var = tk.StringVar(value="Preparando operación...")
        ttk.Label(self.top, textvariable=self.label_var, font=("Segoe UI", 10)).pack(pady=(20, 10), padx=20, anchor="w")

        self.progress = ttk.Progressbar(self.top, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10, padx=20)

    def update_progress(self, current, total, text=""):
        if total > 0:
            self.progress["maximum"] = total
            self.progress["value"] = current
            pct = int((current / total) * 100)
            if not text:
                text = f"Progreso: {current}/{total} ({pct}%)"
        self.label_var.set(text)
        self.top.update_idletasks()

    def close(self):
        try:
            self.top.grab_release()
            self.top.destroy()
        except Exception:
            pass


class DwCaConfigModal:
    """Ventana emergente para configurar los parámetros de exportación Darwin Core."""
    def __init__(self, parent):
        self.top = tk.Toplevel(parent)
        self.top.title("Configuración de Exportación DwCa")
        self.top.geometry("520x340")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()

        self.result = None

        # Controles
        ttk.Label(self.top, text="Configurar Parámetros del Paquete Darwin Core", font=("Segoe UI", 11, "bold")).pack(pady=(15, 10))

        form_frame = ttk.Frame(self.top, padding=15)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # 1. measurementType
        ttk.Label(form_frame, text="measurementType:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.mtype_combo = ttk.Combobox(form_frame, values=[
            "Legal protection status",
            "Legal consideration as exotic or invasive species"
        ], width=60)
        self.mtype_combo.pack(anchor="w", pady=(0, 10))
        self.mtype_combo.set("Legal protection status")

        # 2. Motivo / Acrónimo de Numeración
        ttk.Label(form_frame, text="Motivo / Acrónimo para Numeración (ID):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.acronym_combo = ttk.Combobox(form_frame, values=[
            "LESRPE",
            "CEEI"
        ], width=60)
        self.acronym_combo.pack(anchor="w", pady=(0, 15))
        self.acronym_combo.set("LESRPE")

        # Botones
        btn_frame = ttk.Frame(self.top)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Aceptar y Exportar", command=self.on_accept).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=self.top.destroy).pack(side=tk.LEFT, padx=5)

    def on_accept(self):
        self.result = {
            "measurement_type": self.mtype_combo.get().strip(),
            "dataset_acronym": self.acronym_combo.get().strip()
        }
        self.top.destroy()


class RecordDetailWindow:
    def __init__(self, parent, record_dict: dict, title="Detalle del Registro"):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("750x650")
        self.top.transient(parent)

        container = ttk.Frame(self.top)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(scrollable_frame, text="Atributos y Valores del Registro", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

        for key, val in record_dict.items():
            row_frame = ttk.Frame(scrollable_frame, padding=2)
            row_frame.pack(fill=tk.X, expand=True, pady=2)

            lbl_key = ttk.Label(row_frame, text=f"{key}:", font=("Segoe UI", 9, "bold"), width=28, anchor="e")
            lbl_key.pack(side=tk.LEFT, padx=(0, 5))

            val_str = "" if val is None else str(val)
            lbl_val = ttk.Label(row_frame, text=val_str, font=("Segoe UI", 9), wraplength=450, justify="left")
            lbl_val.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_close = ttk.Button(scrollable_frame, text="Cerrar", command=self.top.destroy)
        btn_close.pack(pady=15)


class EidosTabManager:
    def __init__(self, notebook, title, view_name):
        self.view_name = view_name
        self.explorer = DataExplorer(view_name)
        
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text=title)

        self.selected_datasets = set()
        self.dataset_nodes = {}
        self.group_nodes = []
        self.current_df = None
        self.unfiltered_df = None
        self.catalog_loaded = False

        self.build_tab_ui()

    def build_tab_ui(self):
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self.panel_left = ttk.Frame(paned, width=320)
        self.panel_right = ttk.Frame(paned)

        paned.add(self.panel_left, weight=1)
        paned.add(self.panel_right, weight=5)

        ttk.Label(self.panel_left, text=f"Datasets ({self.view_name})").pack(anchor="w", padx=5, pady=5)
        
        container = ttk.Frame(self.panel_left)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.dataset_tree = ttk.Treeview(container, show="tree")
        vsb = ttk.Scrollbar(container, orient="vertical", command=self.dataset_tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.dataset_tree.xview)
        self.dataset_tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.dataset_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        root_node = self.dataset_tree.insert("", "end", text="Catálogo", open=True)
        self.node_nacional = self.dataset_tree.insert(root_node, "end", text="Nacional", open=True)
        self.node_internacional = self.dataset_tree.insert(root_node, "end", text="Internacional", open=True)
        self.node_autonomico = self.dataset_tree.insert(root_node, "end", text="Autonómico", open=True)
        self.node_general = self.dataset_tree.insert(root_node, "end", text="General / Otros", open=True)

        self.group_nodes = [self.node_nacional, self.node_internacional, self.node_autonomico, self.node_general]

        right_container = ttk.Frame(self.panel_right)
        right_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.tree = ttk.Treeview(right_container, show="headings")
        r_vsb = ttk.Scrollbar(right_container, orient="vertical", command=self.tree.yview)
        r_hsb = ttk.Scrollbar(right_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=r_vsb.set, xscroll=r_hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        r_vsb.grid(row=0, column=1, sticky="ns")
        r_hsb.grid(row=1, column=0, sticky="ew")
        
        right_container.rowconfigure(0, weight=1)
        right_container.columnconfigure(0, weight=1)


class EidosGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EIDOS Multivisor Avanzado")
        self.root.geometry("1700x950")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(10, 6))

        self.search_var = tk.StringVar()
        self.filter_column_var = tk.StringVar(value="Todas")
        self.status_var = tk.StringVar(value="Listo.")

        self.build_layout()
        self.root.after(200, self.check_and_load_active_tab)

    def build_layout(self):
        self.build_toolbar()
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.tabs = {}
        views_def = [
            ("Legal y Protección", "v_estadolegal"),
            ("Taxonomía", "v_taxonomia"),
            ("Nombres Comunes", "v_nombrescomunes"),
            ("Distribución y Hábitat", "v_ubicacion"),
            ("Plinian Core (Descriptiva)", "v_atributos_pliniancore"),
            ("Multimedia e Imágenes", "v_imagenes"),
            ("Estado de Conservación", "v_estadoconservacion"),
            ("Referencias Bibliográficas", "v_referencias_bibliograficas")
        ]

        for title, view_name in views_def:
            tab_obj = EidosTabManager(self.notebook, title, view_name)
            tab_obj.dataset_tree.bind("<Double-1>", lambda e, t=tab_obj: self.handle_tree_double_click(t))
            tab_obj.tree.bind("<Double-1>", lambda e, t=tab_obj: self.open_record_detail(t))
            self.tabs[view_name] = tab_obj

        self.build_statusbar()

    def build_toolbar(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.X, padx=5, pady=5)

        self.btn_refresh = ttk.Button(frame, text="Actualizar / Refresh", command=self.refresh_active_tab)
        self.btn_refresh.pack(side=tk.LEFT, padx=3)

        self.btn_ficha = ttk.Button(frame, text="Abrir ficha EIDOS (Web)", command=lambda: self.open_selected_record_web(self.get_active_tab()))
        self.btn_ficha.pack(side=tk.LEFT, padx=3)

        self.btn_export = ttk.Button(frame, text="Exportar vista actual", command=self.export_current)
        self.btn_export.pack(side=tk.LEFT, padx=3)

        self.btn_matrix = ttk.Button(frame, text="Matriz Nacional", command=self.build_matrix)
        self.btn_dwca_view = ttk.Button(frame, text="Exportar a DwCa", command=self.export_to_dwca)

        ttk.Label(frame, text="Columna:").pack(side=tk.LEFT, padx=(15, 2))
        self.filter_combo = ttk.Combobox(frame, textvariable=self.filter_column_var, state="readonly", width=16)
        self.filter_combo.pack(side=tk.LEFT, padx=2)

        ttk.Label(frame, text="Filtro:").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Entry(frame, textvariable=self.search_var, width=22).pack(side=tk.LEFT, padx=2)

        self.btn_filter_action = ttk.Button(frame, text="Filtrar", command=self.execute_filter)
        self.btn_filter_action.pack(side=tk.LEFT, padx=4)

    def build_statusbar(self):
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        ttk.Label(status_frame, textvariable=self.status_var, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def get_active_tab(self) -> EidosTabManager:
        try:
            current_tab_text = self.notebook.tab(self.notebook.select(), "text")
            for tab in self.tabs.values():
                if self.notebook.tab(tab.frame, "text") == current_tab_text:
                    return tab
        except Exception:
            pass
        return list(self.tabs.values())[0]

    def check_and_load_active_tab(self):
        tab = self.get_active_tab()
        if not tab.catalog_loaded:
            progress_win = ProgressWindow(self.root, title=f"Catálogo - {tab.view_name}")
            def task():
                self.status_var.set(f"Cargando catálogo para {tab.view_name}...")
                progress_win.update_progress(0, 1, text=f"Cargando catálogo de {tab.view_name}...")
                tab.explorer.load_catalog()
                tree_data = tab.explorer.datasets_tree()
                tab.catalog_loaded = True
                self.root.after(0, lambda: self.populate_tree(tab, tree_data))
                self.root.after(0, lambda: progress_win.close())
                self.root.after(0, lambda: self.status_var.set(f"Catálogo de {tab.view_name} listo."))
            threading.Thread(target=task, daemon=True).start()
        else:
            self.setup_filter_columns()
            if tab.current_df is not None:
                self.refresh_table(tab)

    def refresh_active_tab(self):
        tab = self.get_active_tab()
        tab.catalog_loaded = False
        tab.explorer.catalog_df = pd.DataFrame()
        self.check_and_load_active_tab()

    def populate_tree(self, tab: EidosTabManager, tree_data):
        tab.dataset_nodes.clear()
        groups = {
            "Nacional": tab.node_nacional,
            "Internacional": tab.node_internacional,
            "Autonómico": tab.node_autonomico,
            "General": tab.node_general,
            "Otros": tab.node_general
        }

        for parent in groups.values():
            for child in tab.dataset_tree.get_children(parent):
                tab.dataset_tree.delete(child)

        for ambito, datasets in tree_data.items():
            parent = groups.get(ambito, tab.node_general)
            for ds in datasets:
                ds_id = int(ds["iddataset"])
                ds_name = ds["dataset"]
                node = tab.dataset_tree.insert(parent, "end", text=f"{CHECK_OFF} {ds_id} - {ds_name}")
                tab.dataset_nodes[node] = ds_id

    def handle_tree_double_click(self, tab: EidosTabManager):
        item = tab.dataset_tree.focus()
        if not item:
            return

        if item in tab.group_nodes:
            children = tab.dataset_tree.get_children(item)
            if not children:
                return
            
            all_on = all(tab.dataset_tree.item(child, "text").startswith(CHECK_ON) for child in children)
            target_symbol = CHECK_OFF if all_on else CHECK_ON

            for child in children:
                ds_id = tab.dataset_nodes.get(child)
                if ds_id is not None:
                    text = tab.dataset_tree.item(child, "text")
                    if target_symbol == CHECK_ON and text.startswith(CHECK_OFF):
                        text = text.replace(CHECK_OFF, CHECK_ON, 1)
                        tab.selected_datasets.add(ds_id)
                    elif target_symbol == CHECK_OFF and text.startswith(CHECK_ON):
                        text = text.replace(CHECK_ON, CHECK_OFF, 1)
                        tab.selected_datasets.discard(ds_id)
                    tab.dataset_tree.item(child, text=text)

            self.auto_update_selected_datasets(tab)

        elif item in tab.dataset_nodes:
            ds_id = tab.dataset_nodes[item]
            text = tab.dataset_tree.item(item, "text")

            if text.startswith(CHECK_OFF):
                text = text.replace(CHECK_OFF, CHECK_ON, 1)
                tab.selected_datasets.add(ds_id)
            else:
                text = text.replace(CHECK_ON, CHECK_OFF, 1)
                tab.selected_datasets.discard(ds_id)

            tab.dataset_tree.item(item, text=text)
            self.auto_update_selected_datasets(tab)

    def auto_update_selected_datasets(self, tab: EidosTabManager):
        if not tab.selected_datasets:
            tab.unfiltered_df = None
            tab.current_df = None
            self.refresh_table(tab)
            self.status_var.set("Sin datasets seleccionados.")
            return

        total = len(tab.selected_datasets)
        progress_win = ProgressWindow(self.root, title=f"Cargando Datasets - {tab.view_name}")

        def task():
            import concurrent.futures
            frames = []
            completed = 0

            max_workers = min(10, total)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(lambda ds: tab.explorer.load_datasets([ds]), sorted(tab.selected_datasets))
                for df in results:
                    completed += 1
                    pct = int((completed / total) * 100)
                    self.root.after(0, lambda c=completed, t=total, p=pct: progress_win.update_progress(
                        c, t, text=f"Descargando datasets... {c}/{t} completados ({p}%)"
                    ))
                    if df is not None and not df.empty:
                        frames.append(df)

            if frames:
                df_all = pd.concat(frames, ignore_index=True)
            else:
                df_all = pd.DataFrame()

            def finish():
                tab.unfiltered_df = df_all.copy()
                if self.btn_filter_action.cget("text") == "Mostrar todos":
                    query = self.search_var.get().strip()
                    col = self.filter_column_var.get()
                    try:
                        if col == "Todas" or not col:
                            mask = False
                            for c in df_all.columns:
                                mask = mask | df_all[c].astype(str).str.contains(query, case=False, na=False)
                            tab.current_df = df_all[mask].copy()
                        else:
                            mask = df_all[col].astype(str).str.contains(query, case=False, na=False)
                            tab.current_df = df_all[mask].copy()
                    except Exception:
                        tab.current_df = df_all.copy()
                else:
                    tab.current_df = df_all.copy()

                progress_win.close()
                self.setup_filter_columns()
                self.refresh_table(tab)
                self.status_var.set(f"Carga completa: {len(tab.current_df):,} registros mostrados.")

            self.root.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    def setup_filter_columns(self):
        tab = self.get_active_tab()
        if tab.current_df is not None:
            cols = ["Todas"] + list(tab.current_df.columns)
            self.filter_combo["values"] = cols

    def execute_filter(self):
        tab = self.get_active_tab()
        if tab.unfiltered_df is None:
            return

        if self.btn_filter_action.cget("text") == "Mostrar todos":
            tab.current_df = tab.unfiltered_df.copy()
            self.search_var.set("")
            self.filter_column_var.set("Todas")
            self.btn_filter_action.config(text="Filtrar")
            self.refresh_table(tab)
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Aviso", "Introduzca texto para filtrar.")
            return

        col = self.filter_column_var.get()
        df = tab.unfiltered_df

        try:
            if col == "Todas" or not col:
                mask = False
                for c in df.columns:
                    mask = mask | df[c].astype(str).str.contains(query, case=False, na=False)
                result = df[mask]
            else:
                mask = df[col].astype(str).str.contains(query, case=False, na=False)
                result = df[mask]

            tab.current_df = result.copy()
            self.btn_filter_action.config(text="Mostrar todos")
            self.refresh_table(tab)
        except Exception as ex:
            messagebox.showerror("Error", f"Error al filtrar: {ex}")

    def sort_column(self, tab: EidosTabManager, col, reverse):
        if tab.current_df is None:
            return
        try:
            tab.current_df = tab.current_df.sort_values(by=col, ascending=not reverse, na_position='last')
            self.refresh_table(tab)
            tab.tree.heading(col, text=col, command=lambda: self.sort_column(tab, col, not reverse))
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo ordenar: {ex}")

    def refresh_table(self, tab: EidosTabManager):
        if tab.current_df is None:
            tab.tree.delete(*tab.tree.get_children())
            tab.tree["columns"] = []
            return

        tab.tree.delete(*tab.tree.get_children())
        columns = list(tab.current_df.columns)
        tab.tree["columns"] = columns

        for col in columns:
            tab.tree.heading(col, text=col, command=lambda c=col: self.sort_column(tab, c, False))
            tab.tree.column(col, width=200, minwidth=120, stretch=False)

        for _, row in tab.current_df.head(5000).iterrows():
            tab.tree.insert("", tk.END, values=list(row))

        self.status_var.set(f"{len(tab.current_df):,} registros mostrados.")

    def on_tab_changed(self, event):
        self.check_and_load_active_tab()
        tab = self.get_active_tab()
        self.setup_filter_columns()
        
        if tab.view_name == "v_estadolegal":
            self.btn_matrix.pack(side=tk.LEFT, padx=3)
            self.btn_dwca_view.pack(side=tk.LEFT, padx=3)
        else:
            self.btn_matrix.pack_forget()
            self.btn_dwca_view.pack_forget()

    def build_matrix(self):
        tab = self.get_active_tab()
        progress_win = ProgressWindow(self.root, title="Construyendo Matriz Nacional")
        def task():
            self.status_var.set("Construyendo matriz nacional...")
            progress_win.update_progress(0, 1, text="Procesando datos para matriz nacional...")
            df = tab.explorer.national_matrix()
            tab.unfiltered_df = df.copy()
            tab.current_df = df.copy()
            self.root.after(0, lambda: progress_win.close())
            self.root.after(0, self.setup_filter_columns)
            self.root.after(0, lambda: self.refresh_table(tab))
            self.root.after(0, lambda: self.status_var.set("Matriz nacional generada."))
        threading.Thread(target=task, daemon=True).start()

    def export_to_dwca(self):
        tab = self.get_active_tab()
        if tab.current_df is None or tab.current_df.empty:
            messagebox.showwarning("Aviso", "No hay datos cargados en esta vista para exportar a DwCa.")
            return

        # 1. Abrir ventana de configuración modal
        config_modal = DwCaConfigModal(self.root)
        self.root.wait_window(config_modal.top)

        if not config_modal.result:
            return  # Cancelado por el usuario

        config = config_modal.result

        directory = filedialog.askdirectory(title="Seleccione directorio para guardar el paquete DwCa")
        if not directory:
            return

        progress_win = ProgressWindow(self.root, title="Exportando a Darwin Core")
        def task():
            self.status_var.set("Generando paquete Darwin Core (DwCa)...")
            progress_win.update_progress(0, 1, text="Estructurando Core y Extensiones...")
            
            try:
                bridge = DwCaBridge(directory)
                zip_path = bridge.export_dwca_package(
                    tab.current_df, 
                    f"eidos_{tab.view_name}",
                    measurement_type=config["measurement_type"],
                    dataset_acronym=config["dataset_acronym"]
                )
                
                self.root.after(0, lambda: progress_win.close())
                self.root.after(0, lambda: messagebox.showinfo(
                    "Exportación Exitosa", 
                    f"El paquete DwCa se ha guardado correctamente en:\n\n{zip_path}"
                ))
                self.root.after(0, lambda: self.status_var.set(f"Paquete DwCa guardado en: {zip_path.parent}"))
            except Exception as ex:
                err_msg = str(ex)
                self.root.after(0, lambda: progress_win.close())
                self.root.after(0, lambda err=err_msg: messagebox.showerror("Error", f"Error al generar el paquete DwCa:\n{err}"))

        threading.Thread(target=task, daemon=True).start()

    def open_record_detail(self, tab: EidosTabManager):
        if tab.current_df is None:
            return
        selected = tab.tree.focus()
        if not selected:
            return
        values = tab.tree.item(selected, "values")
        columns = list(tab.current_df.columns)
        
        record_dict = {columns[i]: values[i] for i in range(min(len(columns), len(values)))}
        RecordDetailWindow(self.root, record_dict, title=f"Detalle de Registro - {tab.view_name}")

    def open_selected_record_web(self, tab: EidosTabManager):
        if tab.current_df is None:
            return
        selected = tab.tree.focus()
        if not selected:
            return
        values = tab.tree.item(selected, "values")
        columns = list(tab.current_df.columns)
        
        if "idtaxon" not in columns:
            messagebox.showwarning("Aviso", "Esta tabla no contiene idtaxon.")
            return
        
        idx = columns.index("idtaxon")
        url = EIDOS_WEB + str(values[idx])
        try:
            webbrowser.open_new_tab(url)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def export_current(self):
        tab = self.get_active_tab()
        if tab.current_df is None:
            messagebox.showwarning("Aviso", "No hay datos cargados en esta pestaña.")
            return

        directory = filedialog.askdirectory(title="Seleccione directorio de exportación")
        if not directory:
            return

        progress_win = ProgressWindow(self.root, title="Exportando datos")
        def task():
            self.status_var.set("Exportando datos...")
            progress_win.update_progress(0, 1, text="Generando ficheros de exportación...")
            exporter = Exporter(directory)
            exporter.export_all_and_open(tab.current_df, f"eidos_{tab.view_name}")
            self.root.after(0, lambda: progress_win.close())
            self.root.after(0, lambda: messagebox.showinfo("Exportación", "Archivos generados con éxito."))
        threading.Thread(target=task, daemon=True).start()

    def on_close(self):
        try:
            self.root.destroy()
        except Exception:
            pass