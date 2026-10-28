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
    root.geometry("700x850")
    root.minsize(650, 700)

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
            combo_columna['values'] = columnas
            for col in columnas:
                if "taxon" in col.lower() or "eidos" in col.lower() or "id" in col.lower():
                    combo_columna.set(col)
            if not combo_columna.get() and columnas:
                combo_columna.set(columnas[0])
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
        
        col_sel = combo_columna.get()
        tipo_b = modo_busqueda.get()
        if not col_sel:
            messagebox.showerror("Error", "Debes seleccionar una columna para la búsqueda.")
            return

        # Leer también las modificaciones escritas a mano en el campo.
        dir_destino_final = salida_entry.get().strip()
        if not dir_destino_final:
            messagebox.showerror("Error", "Selecciona un directorio de salida.")
            return
        dir_salida["path"] = dir_destino_final
        dir_entrada_original = os.path.dirname(ruta_csv["path"])
        if os.path.abspath(dir_destino_final) == os.path.abspath(dir_entrada_original):
            dir_destino_final = os.path.join(dir_entrada_original, "EIDOS")

        global btn_run
        btn_run.config(state=tk.DISABLED)
        ejecutar_scraping(
            ruta_csv["path"], dir_destino_final, col_sel, tipo_b, 
            root, progress_bar, lbl_progreso, btn_run, abrir_visor_access
        )

    # --- Contenido de la Interfaz ---
    
    frame_desc = tk.Frame(scrollable_frame, bg="#F5F5F5", padx=15, pady=15, relief=tk.RIDGE, bd=1)
    frame_desc.pack(fill="x", padx=20, pady=15)

    lbl_info_texto = (
        "Extracción Completa de EIDOS (IEPNB - MITECO)\n\n"
        "ℹ️ INFORMACIÓN DE SALIDA:\n"
        "• El panel de entrada izquierdo se muestra de forma limpia y compacta sin recuadros.\n"
        "• El panel derecho incluye Coordenadas y Estado cartografía, con un botón Ver mapa.\n"
        "• Las coordenadas y los polígonos se guardan automáticamente al finalizar la descarga.\n"
        "• La exportación final incluye las coordenadas en CSV, Excel y SQLite.\n"
        "• Los puntos representan centros de cuadrículas, no observaciones exactas."
    )

    lbl_desc = tk.Label(frame_desc, text=lbl_info_texto, font=("Segoe UI", 9), bg="#F5F5F5", fg="#333333", justify="left", wraplength=600)
    lbl_desc.pack(anchor="w")

    # Selección de Archivo Entrada
    frame_archivo = tk.LabelFrame(scrollable_frame, text=" Archivo de Entrada ", font=("Segoe UI", 10, "bold"), padx=15, pady=10)
    frame_archivo.pack(fill="x", padx=20, pady=10)

    btn_sel_csv = tk.Button(frame_archivo, text="📁 Seleccionar archivo CSV / TXT", command=seleccionar_csv, bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=4)
    btn_sel_csv.pack(anchor="w", pady=5)

    label_csv = tk.Label(frame_archivo, text="(ningún archivo seleccionado)", font=("Segoe UI", 9, "italic"), fg="#666666", wraplength=600, justify="left")
    label_csv.pack(anchor="w", pady=2)

    # Criterio de Búsqueda
    frame_modo = tk.LabelFrame(scrollable_frame, text=" Criterio de Búsqueda ", font=("Segoe UI", 10, "bold"), padx=15, pady=10)
    frame_modo.pack(fill="x", padx=20, pady=10)

    modo_busqueda = tk.StringVar(value="id")
    tk.Radiobutton(frame_modo, text="Buscar por Identificador (EIDOS_ID / taxonID)", variable=modo_busqueda, value="id", font=("Segoe UI", 9)).pack(anchor="w", pady=3)
    tk.Radiobutton(frame_modo, text="Buscar por Nombre Científico (vía search_api_fulltext)", variable=modo_busqueda, value="name", font=("Segoe UI", 9)).pack(anchor="w", pady=3)

    # Selección de Columna
    frame_cols = tk.LabelFrame(scrollable_frame, text=" Columna a utilizar ", font=("Segoe UI", 10, "bold"), padx=15, pady=10)
    frame_cols.pack(fill="x", padx=20, pady=10)

    tk.Label(frame_cols, text="Selecciona la columna que contiene los criterios de búsqueda:", font=("Segoe UI", 9)).pack(anchor="w", pady=2)
    combo_columna = ttk.Combobox(frame_cols, state="readonly", width=50, font=("Segoe UI", 9))
    combo_columna.pack(anchor="w", pady=5)

    # Directoria de Salida
    frame_salida = tk.LabelFrame(scrollable_frame, text=" Directoria de Salida ", font=("Segoe UI", 10, "bold"), padx=15, pady=10)
    frame_salida.pack(fill="x", padx=20, pady=10)

    salida_entry = tk.Entry(frame_salida, width=55, font=("Segoe UI", 9))
    salida_entry.pack(side="left", padx=(0, 10), pady=5, fill="x", expand=True)

    btn_sel_dir = tk.Button(frame_salida, text="Buscar...", command=seleccionar_directorio, font=("Segoe UI", 9))
    btn_sel_dir.pack(side="right", pady=5)

    # Estado y Barra de Progreso
    frame_progreso = tk.LabelFrame(scrollable_frame, text=" Progreso de la Extracción ", font=("Segoe UI", 10, "bold"), padx=15, pady=10)
    frame_progreso.pack(fill="x", padx=20, pady=10)

    lbl_progreso = tk.Label(frame_progreso, text="Esperando inicio...", font=("Segoe UI", 9))
    lbl_progreso.pack(anchor="w", pady=4)

    progress_bar = ttk.Progressbar(frame_progreso, orient="horizontal", mode="determinate")
    progress_bar.pack(fill="x", pady=5)

    # Botón Principal
    global btn_run
    btn_run = tk.Button(scrollable_frame, text="🚀 Iniciar Scraping", command=ejecutar, bg="#4CAF50", fg="white", font=("Segoe UI", 11, "bold"), height=2, width=25)
    btn_run.pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    main()
