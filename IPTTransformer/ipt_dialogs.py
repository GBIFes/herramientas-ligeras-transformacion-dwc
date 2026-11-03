"""
ipt_dialogs.py
==============
Diálogos y asistentes interactivos para la configuración de Cores, Extensiones
y el asistente de normalización inteligente con soporte de IPTDatasetAnalyzer.
"""

import tkinter as tk
from tkinter import messagebox, ttk
from dwc_manager import get_extension_types
from ipt_analyzer import IPTDatasetAnalyzer
from ipt_model import split_dataset

class MultiRecordSplitterDialog(tk.Toplevel):
    """Asistente iterativo con doble panel explícito para normalización en estrella y jerárquica."""
    def __init__(self, parent, headers, rows, id_col, dataset_name="Core"):
        super().__init__(parent)
        self.title(f"Asistente de Normalización DwC-A ({dataset_name})")
        self.geometry("1000x650")
        try:
            self.grab_set()
        except Exception:
            pass

        self.headers = list(headers)
        self.rows = rows
        self.id_col = id_col
        
        self.analyzer = IPTDatasetAnalyzer(headers, rows, id_col)
        self.id_idx = self.analyzer.id_idx

        self.extracted_datasets = [] 
        self.current_core_headers = [h for h in self.headers if h.lower() != self.id_col.lower()]
        self.current_ext_headers = []
        self.clean_rows = list(rows)
        self.changed = False

        self.duplicate_rows = self.analyzer.filtrar_duplicados()
        self.varying_cols = self.analyzer.detectar_columnas_variables(self.duplicate_rows)
        self.resumen_analisis = self.analyzer.generar_resumen_analisis()

        tk.Label(
            self, 
            text=f"🔍 Análisis Inteligente para: '{dataset_name}' (ID: {id_col})", 
            font=("Segoe UI", 11, "bold"), fg="#1f6fb2"
        ).pack(anchor="w", padx=15, pady=(15, 5))

        lbl_diag = tk.Label(
            self, text=self.resumen_analisis["diagnostico_texto"],
            font=("Segoe UI", 9, "italic"), fg="#d9534f" if self.resumen_analisis["sugiere_jerarquia"] else "#289530"
        )
        lbl_diag.pack(anchor="w", padx=15, pady=(0, 5))

        tk.Label(
            self, 
            text="Seleccione los campos del panel izquierdo (Core) y muévalos al panel derecho (Extensión) para segregarlos.\n"
                 "Los campos marcados como [VARIABLE] contienen múltiples valores por ID.",
            font=("Segoe UI", 9), fg="#444444"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        top_config_frame = tk.Frame(self, bg="#f8f9fa", padx=10, pady=8, relief=tk.GROOVE, bd=1)
        top_config_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(top_config_frame, text="Destino:", font=("Segoe UI", 8, "bold"), bg="#f8f9fa").pack(side="left", padx=5)
        self.dest_var = tk.StringVar(
            value="Subdivisión Jerárquica (Misma tabla - Padre/Hijo)" if self.resumen_analisis["sugiere_jerarquia"] else "Nueva Rama de Estrella (Extensión)"
        )
        ttk.Radiobutton(top_config_frame, text="Rama de Estrella", variable=self.dest_var, value="Nueva Rama de Estrella (Extensión)").pack(side="left", padx=5)
        self.dest_var.set("Nueva Rama de Estrella (Extensión)")
        tk.Label(top_config_frame, text="Jerarquías: solo visualización de relaciones existentes.",
                 bg="#f8f9fa").pack(side="left", padx=5)

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

        try:
            headers, rows, extension = split_dataset(
                self.headers, self.rows, self.id_col,
                list(self.current_ext_headers), self.combo_ext_type.get()
            )
        except ValueError as exc:
            messagebox.showwarning("Normalización no aplicada", str(exc), parent=self)
            return
        self.extracted_datasets.append(extension)
        self.headers, self.rows, self.clean_rows = headers, rows, rows
        self.changed = True
        self.current_core_headers = [h for h in headers if h != self.id_col]
        self.current_ext_headers = []
        self.analyzer = IPTDatasetAnalyzer(headers, rows, self.id_col)
        self.id_idx = self.analyzer.id_idx
        self.duplicate_rows = self.analyzer.filtrar_duplicados()
        self.varying_cols = self.analyzer.detectar_columnas_variables(self.duplicate_rows)
        self.poblar_listas_dobles()

        if not self.duplicate_rows:
            messagebox.showinfo("Normalización Completa", "¡Ya no quedan registros duplicados en esta tabla!", parent=self)
            self.destroy()
