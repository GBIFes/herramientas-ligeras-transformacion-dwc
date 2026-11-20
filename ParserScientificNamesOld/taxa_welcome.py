"""
taxa_welcome.py
==============
Ventana de bienvenida y configuración con la estructura visual y robusta
de ScrapEIDOS (scroll global, canvas, selectores de archivo, columnas y progreso).
"""

import sys
import os
import threading

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from taxa_loader import inspect_file_headers, process_taxa_file

class TaxaWelcomeFrame(tk.Frame):
    def __init__(self, root, viewer):
        super().__init__(root)
        self.root = root
        self.viewer = viewer

        # --- Variables de estado ---
        self.ruta_csv = {"path": None}
        self.dir_salida = {"path": None}

        # --- Estructura con Barra de Desplazamiento (Scrollbar) Global ---
        main_canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            main_canvas.itemconfig(canvas_window, width=event.width)

        main_canvas.bind("<Configure>", _on_canvas_configure)
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            try:
                main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def actualizar_estado_boton():
            col_target = combo_columna.get().strip()
            if self.ruta_csv["path"] and col_target and col_target != "(Ninguna)":
                btn_run.config(state=tk.NORMAL, bg="#289530")
            else:
                btn_run.config(state=tk.DISABLED, bg="#CCCCCC")

        # --- Funciones de Interfaz ---
        def seleccionar_csv():
            f = filedialog.askopenfilename(
                title="Selecciona un archivo de entrada",
                filetypes=[("Archivos de texto y CSV", "*.csv *.tsv *.txt"), ("Todos", "*.*")]
            )
            if not f:
                return
            self.ruta_csv["path"] = f
            label_csv.config(text=f, fg="#000000")
            
            dir_por_defecto = os.path.dirname(f)
            self.dir_salida["path"] = dir_por_defecto
            salida_entry.delete(0, tk.END)
            salida_entry.insert(0, dir_por_defecto)

            try:
                headers, _, _ = inspect_file_headers(f)
                combo_columna['values'] = ["(Ninguna)"] + headers
                combo_columna.set("(Ninguna)")

                # Detección automática inteligente de columna de nombres científicos
                for col in headers:
                    lcol = col.lower()
                    if any(k in lcol for k in ["scientific", "cientific", "nombre", "taxon", "species", "especie"]):
                        combo_columna.set(col)
                        break

                if combo_columna.get() == "(Ninguna)" and headers:
                    combo_columna.set(headers[0])

                actualizar_estado_boton()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudieron leer las cabeceras:\n{e}", parent=self.root)

        def seleccionar_directorio():
            d = filedialog.askdirectory(title="Selecciona el directorio de salida")
            if d:
                self.dir_salida["path"] = d
                salida_entry.delete(0, tk.END)
                salida_entry.insert(0, d)

        def ejecutar():
            if not self.ruta_csv["path"]:
                messagebox.showerror("Error", "Selecciona primero un archivo de entrada.", parent=self.root)
                return
            
            col_target = combo_columna.get().strip()
            if not col_target or col_target == "(Ninguna)":
                messagebox.showerror("Error", "Debes seleccionar la columna que contiene los nombres científicos.", parent=self.root)
                return

            dir_destino_final = salida_entry.get().strip()
            if not dir_destino_final:
                messagebox.showerror("Error", "Selecciona un directorio de salida.", parent=self.root)
                return
            
            self.dir_salida["path"] = dir_destino_final
            base_name, ext = os.path.splitext(os.path.basename(self.ruta_csv["path"]))
            output_filepath = os.path.join(dir_destino_final, f"{base_name}_ParserAutores{ext}")

            btn_run.config(state=tk.DISABLED)

            # Barra de progreso y estado
            lbl_progreso.config(text="Iniciando procesamiento y contraste con GBIF...")
            progress_bar["value"] = 0

            def run_processing():
                try:
                    fields, rows = process_taxa_file(
                        self.ruta_csv["path"], 
                        col_target, 
                        output_filepath=output_filepath, 
                        progress_callback=lambda cur, tot: self.root.after(0, lambda: update_prog_gui(cur, tot))
                    )
                    
                    def on_success():
                        progress_bar["value"] = 100
                        lbl_progreso.config(text="¡Procesamiento completado con éxito!")
                        btn_run.config(state=tk.NORMAL, bg="#289530")
                        self.pack_forget()
                        self.viewer.load_data(fields, rows, output_filepath=output_filepath)
                        self.viewer.pack(fill="both", expand=True)
                    
                    self.root.after(0, on_success)
                    
                except Exception as e:
                    err_msg = str(e)
                    def on_error():
                        progress_bar["value"] = 0
                        lbl_progreso.config(text="Error en el procesamiento.")
                        btn_run.config(state=tk.NORMAL, bg="#289530")
                        messagebox.showerror("Error de Procesamiento", f"Ocurrió un error al procesar:\n{err_msg}", parent=self.root)
                    self.root.after(0, on_error)

            def update_prog_gui(cur, tot):
                val = int((cur / tot) * 100) if tot > 0 else 0
                progress_bar["value"] = val
                lbl_progreso.config(text=f"Procesando registro {cur} de {tot} ({val}%) - Contrastando con GBIF...")

            threading.Thread(target=run_processing, daemon=True).start()

        # --- Contenido de la Interfaz (Estructura ScrapEIDOS) ---
        
        # Título Superior
        lbl_title = tk.Label(
            scrollable_frame,
            text="ParseScientificNames - Suite de Parseo Taxonómico",
            font=("Segoe UI", 16, "bold"),
            fg="#289530"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(15, 5))

        # Panel Descripción
        frame_desc = tk.Frame(scrollable_frame, bg="#F5F5F5", padx=10, pady=8, relief=tk.RIDGE, bd=1)
        frame_desc.pack(fill="x", padx=15, pady=8)

        lbl_info_texto = (
            "🎯 PROPÓSITO: Analizar, desglosar y estandarizar nombres científicos en sus partes constitutivas\n"
            "  (género, subgénero, epíteto específico, autores, rango taxonómico, híbridos y cultivares)\n"
            "  siguiendo las normativas ICN/ICZN y contrastándolos automáticamente con la API de GBIF.\n"
            "📂 ENTRADA: Archivos de texto plano (.txt) o separados por comas/delimitadores (.csv).\n"
            "📦 SALIDA: Copia enriquecida con sufijo '_ParserAutores', columnas Darwin Core, reporte de discrepancias\n"
            "  y opción de exportación adicional a Excel (.xlsx) y Access (.accdb)."
        )

        lbl_desc = tk.Label(frame_desc, text=lbl_info_texto, font=("Segoe UI", 9), bg="#F5F5F5", fg="#333333", justify="left", wraplength=700)
        lbl_desc.pack(anchor="w")

        # 1. Archivo de Entrada
        frame_archivo = tk.Frame(scrollable_frame, padx=10, pady=5)
        frame_archivo.pack(fill="x", padx=15, pady=2)

        btn_sel_csv = tk.Button(frame_archivo, text="📁 Archivo Entrada", command=seleccionar_csv, bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold"), padx=6, pady=2)
        btn_sel_csv.pack(side="left", padx=(0, 10))

        label_csv = tk.Label(frame_archivo, text="(ningún archivo seleccionado)", font=("Segoe UI", 9, "italic"), fg="#666666")
        label_csv.pack(side="left", anchor="w")

        # 2. Criterio de Búsqueda (Columna de Nombres Científicos)
        frame_criterio = tk.LabelFrame(scrollable_frame, text=" 2. Columna de Nombres Científicos ", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        frame_criterio.pack(fill="x", padx=15, pady=5)

        f_sel1 = tk.Frame(frame_criterio)
        f_sel1.pack(fill="x", pady=2)
        tk.Label(f_sel1, text="Columna Objetivo:", font=("Segoe UI", 9, "bold"), width=16, anchor="w").pack(side="left")
        
        combo_columna = ttk.Combobox(f_sel1, state="readonly", width=40, font=("Segoe UI", 9))
        combo_columna.pack(side="left", padx=5)
        combo_columna.bind("<<ComboboxSelected>>", lambda e: actualizar_estado_boton())

        tk.Label(frame_criterio, text="💡 Nota: Seleccione la columna del archivo que contiene los nombres científicos a parsear y contrastar.", font=("Segoe UI", 8, "italic"), fg="#555555").pack(anchor="w", pady=(4, 2))

        # 3. Directorio de Salida
        frame_salida = tk.LabelFrame(scrollable_frame, text=" 3. Directorio de Salida ", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        frame_salida.pack(fill="x", padx=15, pady=5)

        f_sal = tk.Frame(frame_salida)
        f_sal.pack(fill="x", pady=2)
        tk.Label(f_sal, text="Carpeta Destino:", font=("Segoe UI", 9, "bold"), width=15, anchor="w").pack(side="left")
        
        salida_entry = tk.Entry(f_sal, width=42, font=("Segoe UI", 9))
        salida_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)

        btn_sel_dir = tk.Button(f_sal, text="Explorar...", command=seleccionar_directorio, font=("Segoe UI", 9))
        btn_sel_dir.pack(side="left")

        # 4. Estado y Barra de Progreso
        frame_progreso = tk.LabelFrame(scrollable_frame, text=" 4. Progreso del Procesamiento ", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        frame_progreso.pack(fill="x", padx=15, pady=5)

        lbl_progreso = tk.Label(frame_progreso, text="Esperando inicio...", font=("Segoe UI", 9))
        lbl_progreso.pack(anchor="w", pady=1)

        progress_bar = ttk.Progressbar(frame_progreso, orient="horizontal", mode="determinate")
        progress_bar.pack(fill="x", pady=4)

        # Botón Principal (Inicia deshabilitado)
        global btn_run
        btn_run = tk.Button(
            scrollable_frame, 
            text="🚀 Iniciar Parseo y Contraste GBIF", 
            command=ejecutar, 
            bg="#CCCCCC", 
            fg="white", 
            font=("Segoe UI", 10, "bold"), 
            height=1, 
            width=32, 
            state=tk.DISABLED
        )
        btn_run.pack(pady=15)