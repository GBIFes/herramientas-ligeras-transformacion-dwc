"""
ipt_welcome.py
==============
Ventana de bienvenida y carga inicial de datasets DwC-A, con soporte
para la subida y configuración de ficheros Core y múltiples ramas (extensiones).
"""

import os
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from ipt_loader import inspect_file_headers, load_file_data
from dwc_manager import get_core_types, get_extension_types
from ipt_analyzer import IPTDatasetAnalyzer
from ipt_dialogs import MultiRecordSplitterDialog
from ipt_viewer import IPTViewerWindow
from ipt_model import validate_dataset

class IPTWelcomeWindow(tk.Frame):
    """Pantalla inicial para la selección, inspección y carga del Core y sus Ramas."""
    def __init__(self, root):
        super().__init__(root, padx=20, pady=20)
        self.root = root
        self.core_file_path = None
        self.core_headers = []
        self.core_rows = []
        self.external_extensions = [] # Lista para almacenar las ramas subidas

        # Título principal
        tk.Label(
            self, text="🌟 IPT-Transformer | Normalización y Mapeo Relacional", 
            font=("Segoe UI", 14, "bold"), fg="#1f6fb2"
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(
            self, text="Configure el Core y opcionalmente añada ficheros de ramas (extensiones) para construir la estrella DwC-A.",
            font=("Segoe UI", 10), fg="#444444"
        ).pack(anchor="w", pady=(0, 15))

        # --- SECCIÓN 1: CONFIGURACIÓN DEL CORE ---
        core_frame = tk.LabelFrame(self, text=" 📂 Fichero Core (Tabla Principal) ", font=("Segoe UI", 10, "bold"), padx=15, pady=12)
        core_frame.pack(fill="x", pady=5)

        file_box = tk.Frame(core_frame)
        file_box.pack(fill="x", pady=5)
        
        self.lbl_core_file = tk.Label(file_box, text="Ningún archivo Core seleccionado", font=("Segoe UI", 9, "italic"), fg="#777777")
        self.lbl_core_file.pack(side="left", padx=(0, 10))

        tk.Button(
            file_box, text="📁 Examinar Core...", bg="#f0f0f0", fg="#333333",
            font=("Segoe UI", 9, "bold"), relief="groove", padx=8, pady=3,
            command=self.examinar_core
        ).pack(side="left")

        params_box = tk.Frame(core_frame)
        params_box.pack(fill="x", pady=5)

        tk.Label(params_box, text="Tipo de Core:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
        core_types = get_core_types()
        self.combo_core_type = ttk.Combobox(params_box, values=core_types, state="readonly", width=18)
        if core_types:
            self.combo_core_type.set("Taxon" if "Taxon" in core_types else core_types[0])
        self.combo_core_type.pack(side="left", padx=(0, 15))

        tk.Label(params_box, text="Columna ID Principal:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
        self.combo_id_col = ttk.Combobox(params_box, values=[], state="readonly", width=20)
        self.combo_id_col.pack(side="left")

        # --- SECCIÓN 2: GESTIÓN DE RAMAS / EXTENSIONES ---
        ext_frame = tk.LabelFrame(self, text=" 🌿 Ramas / Extensiones Opcionales ", font=("Segoe UI", 10, "bold"), padx=15, pady=12)
        ext_frame.pack(fill="x", pady=10)

        ext_top = tk.Frame(ext_frame)
        ext_top.pack(fill="x", pady=5)

        tk.Label(ext_top, text="Tipo de Extensión:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
        ext_types = get_extension_types()
        self.combo_ext_type = ttk.Combobox(ext_top, values=ext_types, state="readonly", width=18)
        if ext_types:
            self.combo_ext_type.set("EMoF" if "EMoF" in ext_types else ext_types[0])
        self.combo_ext_type.pack(side="left", padx=(0, 15))

        tk.Button(
            ext_top, text="➕ Cargar Fichero de Rama...", bg="#e2e6ea", fg="#333333",
            font=("Segoe UI", 9, "bold"), relief="groove", padx=8, pady=3,
            command=self.añadir_rama_externa
        ).pack(side="left")

        # Lista visual de ramas añadidas
        self.lb_ramas = tk.Listbox(ext_frame, height=4, font=("Segoe UI", 9))
        self.lb_ramas.pack(fill="x", pady=5)

        # --- BOTÓN DE ACCESO AL VISOR ---
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=15)

        self.btn_cargar = tk.Button(
            btn_frame, text="🚀 Cargar Estrella Completa (Core y Ramas)", bg="#28a745", fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=8,
            state="disabled", command=self.procesar_y_lanzar
        )
        self.btn_cargar.pack(side="left")

    def examinar_core(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo Core",
            filetypes=[("Archivos Tabulares / Texto", "*.txt *.csv *.tsv"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        try:
            headers, preview = inspect_file_headers(path)
            self.core_file_path = path
            self.core_headers, self.core_rows = headers, preview
            self.lbl_core_file.config(text=os.path.basename(path), fg="#28a745")
            self.combo_id_col["values"] = self.core_headers
            self.combo_id_col.set("")
            if self.core_headers:
                preferred = {"Taxon": "taxonID", "Event": "eventID",
                             "Occurrence": "occurrenceID",
                             "MaterialSample": "materialSampleID"}.get(self.combo_core_type.get())
                for h in self.core_headers:
                    if h.casefold() == str(preferred).casefold():
                        self.combo_id_col.set(h)
                        break
                if not self.combo_id_col.get():
                    for h in self.core_headers:
                        if h.casefold().endswith("id"):
                            self.combo_id_col.set(h)
                            break
                if not self.combo_id_col.get():
                    self.combo_id_col.set(self.core_headers[0])

            self.btn_cargar.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error de Lectura", f"No se pudo inspeccionar el Core:\n{e}", parent=self)

    def añadir_rama_externa(self):
        if not self.core_file_path:
            messagebox.showwarning("Core requerido", "Cargue primero el fichero Core.", parent=self)
            return
        path = filedialog.askopenfilename(
            title="Seleccionar archivo de extensión (Rama)",
            filetypes=[("Archivos Tabulares / Texto", "*.txt *.csv *.tsv"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        ext_type = self.combo_ext_type.get()
        if not ext_type:
            messagebox.showwarning("Aviso", "Seleccione un tipo de extensión válido.", parent=self)
            return

        try:
            ext_headers, ext_rows = load_file_data(path)
            if not ext_headers:
                raise ValueError("El fichero de rama está vacío o no tiene cabeceras.")

            # Inferir columna de relación FK basándose en el Core ID
            candidates = [self.combo_id_col.get(), "coreID"]
            fk_col = next((h for c in candidates for h in ext_headers
                           if h.casefold() == c.casefold()), None)
            if fk_col is None:
                fk_col = simpledialog.askstring(
                    "Columna de relación",
                    "Escriba la cabecera que contiene los IDs del Core:\n"
                    + ", ".join(ext_headers), parent=self
                )
                if fk_col is None:
                    return
                if fk_col not in ext_headers:
                    raise ValueError("La columna de relación indicada no existe.")
            self_id_col = f"{ext_type.lower()}ID"

            ext_config = {
                "tipo": ext_type,
                "fk_col": fk_col,
                "self_id_col": self_id_col,
                "self_parent_col": "",
                "fields": ext_headers,
                "rows": ext_rows,
                "is_hierarchical": False
            }
            ext_config["source_path"] = path

            self.external_extensions.append(ext_config)
            self.lb_ramas.insert(tk.END, f"🌿 Rama [{ext_type}] -> {os.path.basename(path)} ({len(ext_rows)} registros)")
            messagebox.showinfo("Rama Añadida", f"Se ha incorporado correctamente la rama '{ext_type}'.", parent=self)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el fichero de rama:\n{e}", parent=self)

    def procesar_y_lanzar(self):
        if not self.core_file_path:
            return

        core_type = self.combo_core_type.get()
        id_col = self.combo_id_col.get()

        if not id_col:
            messagebox.showwarning("Aviso", "Debe seleccionar una columna para el ID principal del Core.", parent=self)
            return

        try:
            headers, rows = load_file_data(self.core_file_path)
            analyzer = IPTDatasetAnalyzer(headers, rows, id_col)
            duplicados = analyzer.filtrar_duplicados()

            generated_exts = []

            # Si hay duplicados en el Core, ofrecemos segregación automática
            if duplicados:
                respuesta = messagebox.askyesno(
                    "IDs Duplicados en Core",
                    f"Se han detectado registros duplicados en la columna '{id_col}' del Core.\n\n"
                    "¿Desea abrir el asistente de normalización para extraer ramas adicionales automáticamente?",
                    parent=self
                )
                if respuesta:
                    dialog = MultiRecordSplitterDialog(self.root, headers, rows, id_col, dataset_name=core_type)
                    self.root.wait_window(dialog)
                    if hasattr(dialog, "clean_rows") and dialog.clean_rows:
                        rows = dialog.clean_rows
                        headers = dialog.headers
                    
                    if hasattr(dialog, "extracted_datasets") and dialog.extracted_datasets:
                        generated_exts = dialog.extracted_datasets

            # Combinar ramas subidas por fichero + ramas generadas por asistente
            all_extensions = self.external_extensions + generated_exts
            errors = validate_dataset(
                {"fields": headers, "rows": rows, "id_col": id_col}, is_core=True
            )
            if errors:
                messagebox.showerror("Core no válido", "\n".join(errors), parent=self)
                return
            core_ids = {str(row[headers.index(id_col)]) for row in rows}
            for extension in all_extensions:
                errors = validate_dataset(extension, core_ids=core_ids)
                if errors:
                    raise ValueError(f"Extensión {extension['tipo']}: " + "\n".join(errors))

            self.abrir_visor(headers, rows, core_type, id_col, all_extensions)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo procesar el dataset:\n{e}", parent=self)

    def abrir_visor(self, headers, rows, core_type, id_col, ext_configs):
        core_config = {
            "tipo": core_type,
            "id_col": id_col,
            "fields": headers,
            "rows": rows
        }

        datasets_config = [core_config] + ext_configs

        self.pack_forget()
        viewer = IPTViewerWindow(self.root)
        viewer.set_welcome(self)
        viewer.load_datasets(datasets_config, self.core_file_path, core_config, ext_configs)
        viewer.pack(fill="both", expand=True)
