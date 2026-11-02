"""
===============================================================================
ScrapEIDOS.py - Punto de Entrada Principal (Aplicación ScrapEIDOS)
===============================================================================
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd

from config import detectar_codificacion, detectar_dialect
from gui import ejecutar_scraping, abrir_visor_access

def main():
    root = tk.Tk()
    root.title("Extracción Completa EIDOS - IEPNB")
    root.geometry("750x740")
    root.minsize(680, 650)

    # --- Estructura con Barra de Desplazamiento (Scrollbar) Global ---
    main_canvas = tk.Canvas(root, borderwidth=0, highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
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
        main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # --- Variables de estado ---
    ruta_csv = {"path": None}
    dir_salida = {"path": None}

    def actualizar_estado_boton():
        col_i = combo_id.get().strip()
        col_n = combo_nombre.get().strip()
        if ruta_csv["path"] and (col_i or col_n):
            btn_run.config(state=tk.NORMAL, bg="#4CAF50")
        else:
            btn_run.config(state=tk.DISABLED, bg="#CCCCCC")

    # --- Funciones de Interfaz ---
    def seleccionar_csv():
        f = filedialog.askopenfilename(
            title="Selecciona un archivo de entrada",
            filetypes=[("Archivos de datos", "*.csv *.tsv *.txt"), ("Todos", "*.*")]
        )
        if not f:
            return
        ruta_csv["path"] = f
        label_csv.config(text=f)
        
        dir_por_defecto = os.path.dirname(f)
        dir_salida["path"] = dir_por_defecto
        salida_entry.delete(0, tk.END)
        salida_entry.insert(0, dir_por_defecto)

        try:
            encoding = detectar_codificacion(f)
            dialect = detectar_dialect(f)
            df_temp = pd.read_csv(f, sep=dialect.delimiter, nrows=0, encoding=encoding, engine="python")
            columnas = list(df_temp.columns)
            
            combo_id['values'] = ["(Ninguna)"] + columnas
            combo_nombre['values'] = ["(Ninguna)"] + columnas
            
            combo_id.set("(Ninguna)")
            combo_nombre.set("(Ninguna)")

            for col in columnas:
                lcol = col.lower()
                if "eidos" in lcol or "id" in lcol:
                    combo_id.set(col)
                elif "taxon" in lcol or "scientific" in lcol or "nombre" in lcol:
                    combo_nombre.set(col)

            actualizar_estado_boton()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron leer las columnas:\n{e}")

    def seleccionar_directorio():
        d = filedialog.askdirectory(title="Selecciona el directorio de salida")
        if d:
            dir_salida["path"] = d
            salida_entry.delete(0, tk.END)
            salida_entry.insert(0, d)

    def ejecutar():
        if not ruta_csv["path"]:
            messagebox.showerror("Error", "Selecciona primero un archivo de entrada.")
            return
        if not dir_salida["path"]:
            messagebox.showerror("Error", "Selecciona un directorio de salida.")
            return
        
        col_i = combo_id.get().strip()
        col_n = combo_nombre.get().strip()
        
        if col_i == "(Ninguna)": col_i = ""
        if col_n == "(Ninguna)": col_n = ""

        if not col_i and not col_n:
            messagebox.showerror("Error", "Debes seleccionar al menos una columna (EIDOS_ID o Nombre Científico).")
            return

        dir_destino_final = salida_entry.get().strip()
        if not dir_destino_final:
            messagebox.showerror("Error", "Selecciona un directorio de salida.")
            return
        dir_salida["path"] = dir_destino_final
        dir_entrada_original = os.path.dirname(ruta_csv["path"])
        if os.path.abspath(dir_destino_final) == os.path.abspath(dir_entrada_original):
            dir_destino_final = os.path.join(dir_entrada_original, "EIDOS")

        btn_run.config(state=tk.DISABLED)
        
        incluir_cartografia = var_carto.get()
        nivel_prec = combo_precision.get()
        
        ejecutar_scraping(
            ruta_csv["path"], dir_destino_final, col_i, col_n, 
            root, progress_bar, lbl_progreso, btn_run, abrir_visor_access,
            incluir_cartografia=incluir_cartografia, nivel_precision=nivel_prec
        )

    # --- Contenido de la Pantalla de Bienvenida y Configuración (Compacta) ---
    
    frame_desc = tk.Frame(scrollable_frame, bg="#F5F5F5", padx=10, pady=8, relief=tk.RIDGE, bd=1)
    frame_desc.pack(fill="x", padx=15, pady=8)

    lbl_info_texto = (
        "🎯 PROPÓSITO: Extracción automatizada de fichas, taxonomía, conservación y mapas de EIDOS (IEPNB - MITECO).\n"
        "📂 ENTRADA: Archivo CSV/TSV/TXT con identificadores o nombres científicos.\n"
        "📦 SALIDA: CSVs categorizados, libros Excel (.xlsx), bases SQLite (.db), GeoJSON y mapas Leaflet."
    )

    lbl_desc = tk.Label(frame_desc, text=lbl_info_texto, font=("Segoe UI", 9), bg="#F5F5F5", fg="#333333", justify="left", wraplength=640)
    lbl_desc.pack(anchor="w")

    # 1. Archivo de Entrada
    frame_archivo = tk.Frame(scrollable_frame, padx=10, pady=2)
    frame_archivo.pack(fill="x", padx=15, pady=2)

    btn_sel_csv = tk.Button(frame_archivo, text="📁 Archivo Entrada", command=seleccionar_csv, bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold"), padx=6, pady=2)
    btn_sel_csv.pack(side="left", padx=(0, 10))

    label_csv = tk.Label(frame_archivo, text="(ningún archivo seleccionado)", font=("Segoe UI", 9, "italic"), fg="#666666")
    label_csv.pack(side="left", anchor="w")

    # 2. Criterio de Búsqueda (Dos selectores de columna)
    frame_criterio = tk.LabelFrame(scrollable_frame, text=" 2. Columnas de Búsqueda (EIDOS_ID y Nombre Científico) ", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
    frame_criterio.pack(fill="x", padx=15, pady=5)

    f_sel1 = tk.Frame(frame_criterio)
    f_sel1.pack(fill="x", pady=2)
    tk.Label(f_sel1, text="Columna EIDOS_ID:", font=("Segoe UI", 9, "bold"), width=18, anchor="w").pack(side="left")
    combo_id = ttk.Combobox(f_sel1, state="readonly", width=35, font=("Segoe UI", 9))
    combo_id.pack(side="left", padx=5)
    combo_id.bind("<<ComboboxSelected>>", lambda e: actualizar_estado_boton())

    f_sel2 = tk.Frame(frame_criterio)
    f_sel2.pack(fill="x", pady=2)
    tk.Label(f_sel2, text="Col. Nombre Científ.:", font=("Segoe UI", 9, "bold"), width=18, anchor="w").pack(side="left")
    combo_nombre = ttk.Combobox(f_sel2, state="readonly", width=35, font=("Segoe UI", 9))
    combo_nombre.pack(side="left", padx=5)
    combo_nombre.bind("<<ComboboxSelected>>", lambda e: actualizar_estado_boton())

    tk.Label(frame_criterio, text="💡 Nota: Si selecciona ambas, se priorizará EIDOS_ID; si está vacío, se buscará por Nombre Científico.", font=("Segoe UI", 8, "italic"), fg="#555555").pack(anchor="w", pady=(4, 2))

    # 3. Scraping de Datos Geográficos y Precisión
    frame_geo = tk.LabelFrame(scrollable_frame, text=" 3. Datos Geográficos y Mapas ", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
    frame_geo.pack(fill="x", padx=15, pady=5)

    var_carto = tk.BooleanVar(value=True)
    chk_carto = tk.Checkbutton(
        frame_geo, 
        text="Incluir mapas y descarga cartográfica WFS (⚠️ Advertencia: Aumenta el tiempo de descarga)", 
        variable=var_carto, 
        font=("Segoe UI", 9, "bold"),
        fg="#D32F2F"
    )
    chk_carto.pack(anchor="w", pady=2)

    frame_prec = tk.Frame(frame_geo)
    frame_prec.pack(fill="x", pady=(4, 2))
    tk.Label(frame_prec, text="Precisión WFS:", font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
    
    combo_precision = ttk.Combobox(frame_prec, state="readonly", width=42, font=("Segoe UI", 9))
    combo_precision['values'] = [
        "Estándar (Paginación 1000 - Recomendado)",
        "Alta densidad (Reintentos exhaustivos)",
        "Rápido (Sin reintentos)"
    ]
    combo_precision.set("Estándar (Paginación 1000 - Recomendado)")
    combo_precision.pack(side="left", padx=(0, 10))

    # 4. Directorio de Salida
    frame_salida = tk.Frame(scrollable_frame, padx=10, pady=2)
    frame_salida.pack(fill="x", padx=15, pady=5)

    tk.Label(frame_salida, text="Salida:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
    salida_entry = tk.Entry(frame_salida, width=45, font=("Segoe UI", 9))
    salida_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)

    btn_sel_dir = tk.Button(frame_salida, text="Explorar...", command=seleccionar_directorio, font=("Segoe UI", 9))
    btn_sel_dir.pack(side="left")

    # Estado y Barra de Progreso
    frame_progreso = tk.Frame(scrollable_frame, padx=10, pady=2)
    frame_progreso.pack(fill="x", padx=15, pady=2)

    lbl_progreso = tk.Label(frame_progreso, text="Esperando inicio...", font=("Segoe UI", 9))
    lbl_progreso.pack(anchor="w", pady=1)

    progress_bar = ttk.Progressbar(frame_progreso, orient="horizontal", mode="determinate")
    progress_bar.pack(fill="x", pady=2)

    # Botón Principal (Inicia deshabilitado hasta que haya archivo y al menos una columna seleccionada)
    global btn_run
    btn_run = tk.Button(scrollable_frame, text="🚀 Iniciar Scraping", command=ejecutar, bg="#CCCCCC", fg="white", font=("Segoe UI", 10, "bold"), height=1, width=22, state=tk.DISABLED)
    btn_run.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()