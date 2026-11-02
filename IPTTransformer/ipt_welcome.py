"""
ipt_welcome.py
==============
Pantalla inicial con asistente de normalización, configuración de Core y Extensiones,
y paso de los datasets estructurados hacia el visor en estrella.
"""

import os
import shutil
import uuid
from collections import Counter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from ipt_loader import inspect_file_headers, load_file_data
from dwc_manager import verify_and_initialize_dictionary, update_dictionary_from_source, get_core_types, get_extension_types

class MultiRecordSplitterDialog(tk.Toplevel):
    """Asistente iterativo con doble panel explícito para normalización en estrella."""
    def __init__(self, parent, headers, rows, id_col, dataset_name="Core"):
        super().__init__(parent)
        self.title(f"Asistente de Normalización DwC-A ({dataset_name})")
        self.geometry("1000x650")
        self.grab_set()

        self.headers = list(headers)
        self.rows = rows
        self.id_col = id_col
        
        self.id_idx = 0
        for idx, h in enumerate(self.headers):
            if h.lower() == id_col.lower():
                self.id_idx = idx
                break

        self.extracted_datasets = [] 
        self.current_core_headers = [h for h in self.headers if h.lower() != self.id_col.lower()]
        self.current_ext_headers = []
        self.clean_rows = list(rows)

        self.duplicate_rows = self.filter_only_duplicates(rows, self.id_idx)

        if not self.duplicate_rows:
            messagebox.showinfo("Sin Duplicados", f"No se encontraron registros duplicados en '{dataset_name}'.", parent=self)
            self.destroy()
            return

        self.varying_cols = self.detect_varying_columns(self.duplicate_rows, self.headers)

        tk.Label(
            self, 
            text=f"🔍 Análisis de Registros Múltiples para: '{dataset_name}' (ID: {id_col})", 
            font=("Segoe UI", 11, "bold"), fg="#1f6fb2"
        ).pack(anchor="w", padx=15, pady=(15, 5))

        tk.Label(
            self, 
            text="Seleccione los campos del panel izquierdo (Core) y muévalos al panel derecho (Extensión) para segregarlos.\n"
                 "Los campos marcados como [VARIABLE] contienen múltiples valores por ID.",
            font=("Segoe UI", 9), fg="#444444"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        top_config_frame = tk.Frame(self, bg="#f8f9fa", padx=10, pady=8, relief=tk.GROOVE, bd=1)
        top_config_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(top_config_frame, text="Destino:", font=("Segoe UI", 8, "bold"), bg="#f8f9fa").pack(side="left", padx=5)
        self.dest_var = tk.StringVar(value="Nueva Rama de Estrella (Extensión)")
        ttk.Radiobutton(top_config_frame, text="Rama de Estrella", variable=self.dest_var, value="Nueva Rama de Estrella (Extensión)").pack(side="left", padx=5)
        ttk.Radiobutton(top_config_frame, text="Jerárquica (Padre/Hijo)", variable=self.dest_var, value="Subdivisión Jerárquica (Misma tabla - Padre/Hijo)").pack(side="left", padx=5)

        tk.Label(top_config_frame, text=" | Tipo Extensión:", font=("Segoe UI", 8, "bold"), bg="#f8f9fa").pack(side="left", padx=10)
        ext_types = get_extension_types()
        self.combo_ext_type = ttk.Combobox(top_config_frame, values=ext_types, state="readonly", width=22)
        if ext_types: self.combo_ext_type.set("EMoF" if "EMoF" in ext_types else ext_types[0])
        self.combo_ext_type.pack(side="left", padx=5)

        panels_frame = tk.Frame(self)
        panels_frame.pack(fill="both", expand=True, padx=15, pady=10)

        left_box_frame = tk.LabelFrame(panels_frame, text=" 📂 Campos en Tabla Core (Disponibles) ", font=("Segoe UI", 9, "bold"), padx=8, pady=8)
        left_box_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.lb_core = tk.Listbox(left_box_frame, selectmode=tk.MULTIPLE, font=("Segoe UI", 9), exportselection=False)
        sc_core = ttk.Scrollbar(left_box_frame, orient="vertical", command=self.lb_core.yview)
        self.lb_core.configure(yscrollcommand=sc_core.set)
        sc_core.pack(side="right", fill="y")
        self.lb_core.pack(side="left", fill="both", expand=True)

        middle_btns_frame = tk.Frame(panels_frame, padx=10)
        middle_btns_frame.pack(side="left", fill="y")
        
        tk.Button(
            middle_btns_frame, text=" ➡️ \nMover", command=self.mover_a_extension, 
            bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold"), width=8, pady=5
        ).pack(pady=40)

        tk.Button(
            middle_btns_frame, text=" ⬅️ \nRegresar", command=self.mover_a_core, 
            bg="#6c757d", fg="white", font=("Segoe UI", 9, "bold"), width=8, pady=5
        ).pack(pady=5)

        right_box_frame = tk.LabelFrame(panels_frame, text=" 🚀 Campos hacia Nueva Extensión (Rama) ", font=("Segoe UI", 9, "bold"), padx=8, pady=8)
        right_box_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.lb_ext = tk.Listbox(right_box_frame, selectmode=tk.MULTIPLE, font=("Segoe UI", 9), exportselection=False)
        sc_ext = ttk.Scrollbar(right_box_frame, orient="vertical", command=self.lb_ext.yview)
        self.lb_ext.configure(yscrollcommand=sc_ext.set)
        sc_ext.pack(side="right", fill="y")
        self.lb_ext.pack(side="left", fill="both", expand=True)

        self.poblar_listas_dobles()

        action_frame = tk.Frame(self, padx=15, pady=5)
        action_frame.pack(fill="x")

        tk.Button(
            action_frame, text="⚡ Ejecutar Segregación y Salvar Rama", 
            command=self.ejecutar_segregacion, bg="#4CAF50", fg="white", 
            font=("Segoe UI", 10, "bold")
        ).pack(side="left", padx=5)

        tk.Button(
            action_frame, text="✅ Finalizar Asistente", 
            command=self.destroy, bg="#1f6fb2", fg="white", 
            font=("Segoe UI", 10, "bold")
        ).pack(side="right", padx=5)

    def filter_only_duplicates(self, rows, id_idx):
        id_values = [str(r[id_idx]) for r in rows if len(r) > id_idx]
        counts = Counter(id_values)
        return [r for r in rows if len(r) > id_idx and counts[str(r[id_idx])] > 1]

    def detect_varying_columns(self, duplicate_rows, headers):
        id_to_rows = {}
        for r in duplicate_rows:
            cid = str(r[self.id_idx])
            id_to_rows.setdefault(cid, []).append(r)

        varying = set()
        for cid, group in id_to_rows.items():
            for idx, h in enumerate(headers):
                vals = set(str(row[idx]) for row in group if len(row) > idx)
                if len(vals) > 1:
                    varying.add(h)
        return varying

    def poblar_listas_dobles(self):
        self.lb_core.delete(0, tk.END)
        for h in self.current_core_headers:
            display_text = f"⚠️ [VARIABLE] {h}" if h in self.varying_cols else f"   {h}"
            self.lb_core.insert(tk.END, display_text)

        self.lb_ext.delete(0, tk.END)
        for h in self.current_ext_headers:
            display_text = f"⚠️ [VARIABLE] {h}" if h in self.varying_cols else f"   {h}"
            self.lb_ext.insert(tk.END, display_text)

    def mover_a_extension(self):
        selected_indices = self.lb_core.curselection()
        if not selected_indices:
            return
        items_to_move = []
        for idx in selected_indices:
            raw_text = self.lb_core.get(idx)
            clean_name = raw_text.replace("⚠️ [VARIABLE]", "").replace("   ", "").strip()
            items_to_move.append(clean_name)

        for name in items_to_move:
            if name in self.current_core_headers:
                self.current_core_headers.remove(name)
            if name not in self.current_ext_headers:
                self.current_ext_headers.append(name)
        self.poblar_listas_dobles()

    def mover_a_core(self):
        selected_indices = self.lb_ext.curselection()
        if not selected_indices:
            return
        items_to_move = []
        for idx in selected_indices:
            raw_text = self.lb_ext.get(idx)
            clean_name = raw_text.replace("⚠️ [VARIABLE]", "").replace("   ", "").strip()
            items_to_move.append(clean_name)

        for name in items_to_move:
            if name in self.current_ext_headers:
                self.current_ext_headers.remove(name)
            if name not in self.current_core_headers:
                self.current_core_headers.append(name)
        self.poblar_listas_dobles()

    def ejecutar_segregacion(self):
        if not self.current_ext_headers:
            messagebox.showwarning("Aviso", "No ha seleccionado ninguna columna para la extensión en el panel derecho.", parent=self)
            return

        selected_cols = list(self.current_ext_headers)
        dest = self.dest_var.get()
        ext_type = self.combo_ext_type.get()

        if "Estrella" in dest:
            ext_id_col = f"{ext_type.lower()}ID" if ext_type else "recordID"
            ext_fields = [self.id_col] + selected_cols + [ext_id_col]
            
            ext_rows = []
            for r in self.duplicate_rows:
                c_id = str(r[self.id_idx])
                row_dict = {self.headers[i]: r[i] for i in range(len(self.headers)) if i < len(r)}
                ext_row = [c_id] + [row_dict.get(col, "") for col in selected_cols] + [str(uuid.uuid4())[:8]]
                ext_rows.append(ext_row)

            self.extracted_datasets.append({
                "tipo": ext_type,
                "fk_col": self.id_col,
                "self_id_col": ext_id_col,
                "self_parent_col": "",
                "fields": ext_fields,
                "rows": ext_rows,
                "is_hierarchical": False
            })
            messagebox.showinfo("Rama Salvada", f"Se ha salvado y creado la rama independiente '{ext_type}'.", parent=self)
        else:
            self_id_col = "subRecordID"
            self_parent_col = "parentRecordID"
            ext_fields = [self.id_col] + selected_cols + [self_id_col, self_parent_col]

            ext_rows = []
            for r in self.duplicate_rows:
                c_id = str(r[self.id_idx])
                row_dict = {self.headers[i]: r[i] for i in range(len(self.headers)) if i < len(r)}
                ext_row = [c_id] + [row_dict.get(col, "") for col in selected_cols] + [str(uuid.uuid4())[:8], ""]
                ext_rows.append(ext_row)

            self.extracted_datasets.append({
                "tipo": ext_type,
                "fk_col": self.id_col,
                "self_id_col": self_id_col,
                "self_parent_col": self_parent_col,
                "fields": ext_fields,
                "rows": ext_rows,
                "is_hierarchical": True
            })
            messagebox.showinfo("Rama Salvada", f"Se ha salvado y creado la extensión jerárquica '{ext_type}' (Padre-Hijo).", parent=self)

        self.current_ext_headers = []
        self.process_clean_core()
        
        self.duplicate_rows = self.filter_only_duplicates(self.rows, self.id_idx)
        self.varying_cols = self.detect_varying_columns(self.duplicate_rows, self.headers)
        self.poblar_listas_dobles()

        if not self.duplicate_rows:
            messagebox.showinfo("Normalización Completa", "¡Ya no quedan registros duplicados en esta tabla!", parent=self)
            self.destroy()

    def process_clean_core(self):
        unique_map = {}
        for r in self.rows:
            if len(r) <= self.id_idx:
                continue
            cid = str(r[self.id_idx])
            if cid not in unique_map:
                unique_map[cid] = list(r)
        self.clean_rows = list(unique_map.values())


class IPTWelcomeFrame(tk.Frame):
    def __init__(self, root, viewer):
        super().__init__(root)
        self.root = root
        self.viewer = viewer

        self.core_data = None  
        self.extensions_data = []  
        self.original_file_path = None  

        verify_and_initialize_dictionary(self.root)

        header_frame = tk.Frame(self)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))

        tk.Label(header_frame, text="IPT-Transformer - Estructuración Darwin Core Archive", font=("Segoe UI", 14, "bold"), fg="#1f6fb2").pack(side="left")
        
        tk.Button(
            header_frame, text="🔄 Sincronizar Diccionario DwC", bg="#17a2b8", fg="white", 
            font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=4,
            command=lambda: update_dictionary_from_source(self.root)
        ).pack(side="right")

        # Panel Core
        frame_core = tk.LabelFrame(self, text=" 1. Archivo Core (Estrella - Centro) ", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        frame_core.pack(fill="x", padx=15, pady=5)

        f_c1 = tk.Frame(frame_core)
        f_c1.pack(fill="x", pady=2)
        tk.Button(f_c1, text="📁 Seleccionar Core", command=self.cargar_core, bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.lbl_core = tk.Label(f_c1, text="(ningún archivo Core seleccionado)", font=("Segoe UI", 9, "italic"), fg="#666666")
        self.lbl_core.pack(side="left", padx=10)

        self.lbl_core_info = tk.Label(frame_core, text="Tipo: No definido | ID Core: No definido", font=("Segoe UI", 8), fg="#333333")
        self.lbl_core_info.pack(anchor="w", pady=(4, 0))

        # Panel Extensiones
        frame_ext = tk.LabelFrame(self, text=" 2. Extensiones (Brazos de la Estrella - Opcional) ", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        frame_ext.pack(fill="x", padx=15, pady=5)

        f_e1 = tk.Frame(frame_ext)
        f_e1.pack(fill="x", pady=2)
        tk.Button(f_e1, text="➕ Agregar Extensión", command=self.agregar_extension, bg="#4CAF50", fg="white", font=("Segoe UI", 9, "bold")).pack(side="left")
        
        self.listbox_ext = tk.Listbox(frame_ext, height=4, font=("Segoe UI", 9))
        self.listbox_ext.pack(fill="x", pady=(5, 0))

        # Botón Lanzar Visor Estrella
        action_bar = tk.Frame(self, padx=15, pady=20)
        action_bar.pack(fill="x")

        self.btn_run = tk.Button(action_bar, text="🚀 Generar Visor en Estrella y Guardar/Exportar", command=self.lanzar_visor, bg="#CCCCCC", fg="white", font=("Segoe UI", 11, "bold"), state=tk.DISABLED)
        self.btn_run.pack(fill="x", ipady=5)

    def cargar_core(self):
        f = filedialog.askopenfilename(title="Seleccionar archivo Core", filetypes=[("Archivos CSV/TXT", "*.csv *.tsv *.txt"), ("Todos", "*.*")])
        if not f:
            return

        self.original_file_path = f
        headers, _, _ = inspect_file_headers(f)
        if not headers:
            messagebox.showerror("Error", "No se pudieron leer las cabeceras del archivo.", parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Configurar Archivo Core")
        dialog.geometry("400x240")
        dialog.grab_set()

        core_types = get_core_types()

        tk.Label(dialog, text="Seleccione el Tipo de Core:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=5)
        combo_tipo = ttk.Combobox(dialog, values=core_types, state="readonly", width=35)
        if core_types: combo_tipo.set(core_types[0])
        combo_tipo.pack(padx=10, pady=2)

        tk.Label(dialog, text="Columna ID Principal (Core ID):", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=5)
        combo_id = ttk.Combobox(dialog, values=headers, state="readonly", width=35)
        if headers: combo_id.set(headers[0])
        combo_id.pack(padx=10, pady=2)

        def guardar_config():
            tipo = combo_tipo.get()
            id_col = combo_id.get()
            headers_c, rows_c, enc, delim = load_file_data(f)

            try:
                id_idx = 0
                for idx, h in enumerate(headers_c):
                    if h.lower() == id_col.lower():
                        id_idx = idx
                        break

                id_values = [str(r[id_idx]) for r in rows_c if len(r) > id_idx]
                counts = Counter(id_values)
                duplicates = {val: cnt for val, cnt in counts.items() if cnt > 1}

                if duplicates:
                    splitter = MultiRecordSplitterDialog(dialog, headers_c, rows_c, id_col, dataset_name=tipo)
                    dialog.wait_window(splitter)

                    rows_c = splitter.clean_rows
                    for ext in splitter.extracted_datasets:
                        self.extensions_data.append(ext)
                        self.listbox_ext.insert(tk.END, f"{ext['tipo']} (Normalizada - ID: {id_col})")
            except Exception as e:
                print(f"Aviso en validación de unicidad: {e}")

            self.core_data = {
                "tipo": tipo, "id_col": id_col, 
                "fields": headers_c, "rows": rows_c, "enc": enc, "delim": delim
            }
            self.lbl_core.config(text=os.path.basename(f), fg="#000000")
            self.lbl_core_info.config(text=f"Tipo: {tipo} | ID Core: {id_col}")
            dialog.destroy()
            self.verificar_estado()

        tk.Button(dialog, text="Aceptar y Analizar", command=guardar_config, bg="#289530", fg="white", font=("Segoe UI", 9, "bold")).pack(pady=10)

    def agregar_extension(self):
        if not self.core_data:
            messagebox.showwarning("Aviso", "Primero debe configurar el archivo Core.", parent=self.root)
            return

        f = filedialog.askopenfilename(title="Seleccionar archivo de Extensión", filetypes=[("Archivos CSV/TXT", "*.csv *.tsv *.txt"), ("Todos", "*.*")])
        if not f:
            return

        headers, _, _ = inspect_file_headers(f)
        if not headers:
            messagebox.showerror("Error", "No se pudieron leer las cabeceras.", parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Configurar Extensión DwC-A")
        dialog.geometry("420x360")
        dialog.grab_set()

        ext_types = get_extension_types()

        tk.Label(dialog, text="Tipo de Extensión oficial:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=5)
        combo_ext_type = ttk.Combobox(dialog, values=ext_types, state="readonly", width=38)
        if ext_types: combo_ext_type.set(ext_types[0])
        combo_ext_type.pack(padx=10, pady=2)

        tk.Label(dialog, text="Clave Foránea hacia el Core (FK):", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=5)
        combo_fk = ttk.Combobox(dialog, values=headers, state="readonly", width=38)
        if headers: combo_fk.set(headers[0])
        combo_fk.pack(padx=10, pady=2)

        tk.Label(dialog, text="ID propio [Opcional]:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        combo_self_id = ttk.Combobox(dialog, values=["(Crear automáticamente si no existe)"] + headers, state="readonly", width=38)
        combo_self_id.set("(Crear automáticamente si no existe)")
        combo_self_id.pack(padx=10, pady=2)

        tk.Label(dialog, text="ID de Padre [Opcional]:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(5, 2))
        combo_self_parent = ttk.Combobox(dialog, values=["(Ninguno / Crear si no existe)"] + headers, state="readonly", width=38)
        combo_self_parent.set("(Ninguno / Crear si no existe)")
        combo_self_parent.pack(padx=10, pady=2)

        def guardar_ext():
            tipo = combo_ext_type.get().strip()
            fk_col = combo_fk.get()
            self_id = combo_self_id.get()
            self_parent = combo_self_parent.get()
            
            s_id = None if self_id == "(Crear automáticamente si no existe)" else self_id
            s_parent = None if self_parent == "(Ninguno / Crear si no existe)" else self_parent

            if s_id and s_parent and s_id == s_parent:
                messagebox.showerror("Error de Configuración", "El ID propio y el ID de padre no pueden ser la misma columna.", parent=dialog)
                return

            headers_e, rows_e, enc, delim = load_file_data(f)
            self.extensions_data.append({
                "tipo": tipo, "fk_col": fk_col,
                "self_id_col": s_id, "self_parent_col": s_parent,
                "fields": headers_e, "rows": rows_e, "enc": enc, "delim": delim
            })
            
            self.listbox_ext.insert(tk.END, f"{tipo} (FK: {fk_col})")
            dialog.destroy()
            self.verificar_estado()

        tk.Button(dialog, text="Aceptar", command=guardar_ext, bg="#289530", fg="white", font=("Segoe UI", 9, "bold")).pack(pady=15)

    def verificar_estado(self):
        if self.core_data:
            self.btn_run.config(state=tk.NORMAL, bg="#289530")

    def lanzar_visor(self):
        if not self.core_data:
            return

        datasets = []
        datasets.append({
            "tipo": self.core_data['tipo'],
            "id_col": self.core_data['id_col'],
            "fields": self.core_data['fields'],
            "rows": self.core_data['rows'],
            "is_hierarchical": False
        })

        for ext in self.extensions_data:
            datasets.append({
                "tipo": ext['tipo'],
                "fk_col": ext['fk_col'],
                "self_id_col": ext.get('self_id_col'),
                "self_parent_col": ext.get('self_parent_col'),
                "fields": ext['fields'],
                "rows": ext['rows'],
                "is_hierarchical": ext.get('is_hierarchical', False)
            })

        self.pack_forget()
        self.viewer.load_datasets(datasets, self.original_file_path, self.core_data, self.extensions_data)
        self.viewer.pack(fill="both", expand=True)