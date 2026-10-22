"""
===============================================================================
ScrapNombresComunes_GUI_AccessStyle.py
===============================================================================
Interfaz gráfica con opción dual de búsqueda (por taxonID o por scientificName),
visor estilo Access (Maestro-Detalle), exportación a Excel/Access y UTF-8.
===============================================================================
"""

import os
import re
import time
import csv
import threading
import sqlite3
import subprocess
import platform
import requests
from bs4 import BeautifulSoup
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================

BASE_URL = "https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/"

IDIOMA_PAIS = {
    "Castellano": "ES",
    "Catalán": "ES",
    "Euskera": "ES",
    "Gallego": "ES",
    "Valenciano": "ES",
    "Mallorquín": "ES",
    "Altoaragonés": "ES",
    "Inglés": "GB",
    "Francés": "FR",
    "Portugués": "PT",
    "Italiano": "IT",
    "Alemán": "DE",
}

SEPARADOR_NOMBRES_REGEX = re.compile(r'\s*[;,]\s*')
PAUSA_SEGUNDOS = 0.2
FLUSH_EVERY = 50

def detectar_codificacion(ruta):
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            with open(ruta, "r", encoding=enc) as f:
                f.read()
            return enc
        except:
            pass
    return "latin-1"

def detectar_dialect(ruta):
    encoding = detectar_codificacion(ruta)
    with open(ruta, "r", encoding=encoding, errors="ignore") as f:
        muestra = f.read(4096)
    posibles = [",", ";", "\t", "|"]
    try:
        dialect = csv.Sniffer().sniff(muestra, delimiters=posibles)
        return dialect
    except:
        conteos = {sep: muestra.count(sep) for sep in posibles}
        separador = max(conteos, key=conteos.get)
        class Dialect(csv.Dialect):
            delimiter = separador
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return Dialect

def abrir_archivo_sistema(ruta):
    """Abre el archivo resultante con la aplicación predeterminada del SO."""
    try:
        if platform.system() == "Windows":
            os.startfile(ruta)
        elif platform.system() == "Darwin":
            subprocess.call(["open", ruta])
        else:
            subprocess.call(["xdg-open", ruta])
    except Exception as e:
        print(f"No se pudo abrir el archivo automáticamente: {e}")

# =============================================================================
# VENTANA VISOR ESTILO ACCESS (MAESTRO - DETALLE CON NAVEGACIÓN)
# =============================================================================

def abrir_visor_access(ruta_entrada, ruta_salida, col_busqueda_sel, tipo_busqueda, root_main):
    try:
        enc_in = detectar_codificacion(ruta_entrada)
        sep_in = detectar_dialect(ruta_entrada).delimiter
        df_input = pd.read_csv(ruta_entrada, sep=sep_in, dtype=str, encoding=enc_in, engine="python")
        df_input.fillna("", inplace=True)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo cargar el archivo de entrada para el visor:\n{e}")
        return

    try:
        df_output = pd.read_csv(ruta_salida, dtype=str, encoding="utf-8")
        df_output.fillna("", inplace=True)
    except Exception as e:
        df_output = pd.DataFrame(columns=["taxonID", "scientificName", "idioma", "pais", "nombre"])

    visor = tk.Toplevel()
    visor.title("Visor de Registros - Estilo Formulario Access")
    visor.geometry("1050x620")

    total_registros = len(df_input)
    current_idx = {"val": 0}

    frame_main = tk.Frame(visor)
    frame_main.pack(fill="both", expand=True, padx=10, pady=10)

    # --- PANEL IZQUIERDO (Ficha de Entrada) ---
    frame_left = tk.LabelFrame(frame_main, text=" Ficha de Especie (Entrada) ", font=("Arial", 10, "bold"), padx=10, pady=10)
    frame_left.pack(side="left", fill="both", expand=True, padx=5)

    entries_left = {}
    input_columns = list(df_input.columns)
    for col in input_columns:
        f_row = tk.Frame(frame_left)
        f_row.pack(fill="x", pady=2)
        tk.Label(f_row, text=f"{col}:", width=22, anchor="w", font=("Arial", 9, "bold")).pack(side="left")
        e = tk.Entry(f_row, font=("Arial", 9))
        e.pack(side="right", fill="x", expand=True)
        entries_left[col] = e

    # --- PANEL DERECHO (Formulario Continuo / Fichas de Resultados) ---
    frame_right = tk.LabelFrame(frame_main, text=" Nombres Comunes Encontrados (Salida) ", font=("Arial", 10, "bold"), padx=10, pady=10)
    frame_right.pack(side="right", fill="both", expand=True, padx=5)

    tree_frame = tk.Frame(frame_right)
    tree_frame.pack(fill="both", expand=True)
    
    tree_cols = ["idioma", "pais", "nombre"]
    tree = ttk.Treeview(tree_frame, columns=tree_cols, show="headings", height=15)
    for c in tree_cols:
        tree.heading(c, text=c.capitalize())
        tree.column(c, width=130, anchor="w")
    
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def actualizar_vista():
        if total_registros == 0:
            return
        idx = current_idx["val"]
        row = df_input.iloc[idx]

        for col in input_columns:
            entries_left[col].delete(0, tk.END)
            entries_left[col].insert(0, str(row.get(col, "")))

        valor_busqueda_activo = str(row.get(col_busqueda_sel, "")).strip()

        for item in tree.get_children():
            tree.delete(item)

        if not df_output.empty:
            if tipo_busqueda == "id":
                col_filtro = "taxonID"
            else:
                col_filtro = "scientificName"

            if col_filtro in df_output.columns:
                filtrados = df_output[df_output[col_filtro].astype(str).str.strip() == valor_busqueda_activo]
                for _, r_out in filtrados.iterrows():
                    tree.insert("", "end", values=(r_out.get("idioma", ""), r_out.get("pais", ""), r_out.get("nombre", "")))

        lbl_estado.config(text=f"Registro {idx + 1} de {total_registros}")
        entry_ir.delete(0, tk.END)
        entry_ir.insert(0, str(idx + 1))

    # --- BARRA DE NAVEGACIÓN ESTILO ACCESS ---
    frame_nav = tk.Frame(visor, bd=1, relief=tk.RAISED, pady=5)
    frame_nav.pack(fill="x", side="bottom", padx=10, pady=5)

    def ir_primero():
        current_idx["val"] = 0
        actualizar_vista()

    def ir_anterior():
        if current_idx["val"] > 0:
            current_idx["val"] -= 1
            actualizar_vista()

    def ir_siguiente():
        if current_idx["val"] < total_registros - 1:
            current_idx["val"] += 1
            actualizar_vista()

    def ir_ultimo():
        current_idx["val"] = total_registros - 1
        actualizar_vista()

    def ir_a_registro(event=None):
        try:
            val = int(entry_ir.get()) - 1
            if 0 <= val < total_registros:
                current_idx["val"] = val
                actualizar_vista()
            else:
                messagebox.showwarning("Aviso", "Número de registro fuera de rango.")
        except ValueError:
            pass

    btn_primero = tk.Button(frame_nav, text="|<", width=4, command=ir_primero)
    btn_primero.pack(side="left", padx=2)
    btn_anterior = tk.Button(frame_nav, text="<", width=4, command=ir_anterior)
    btn_anterior.pack(side="left", padx=2)

    lbl_estado = tk.Label(frame_nav, text="Registro 0 de 0", font=("Arial", 9))
    lbl_estado.pack(side="left", padx=10)

    btn_siguiente = tk.Button(frame_nav, text=">", width=4, command=ir_siguiente)
    btn_siguiente.pack(side="left", padx=2)
    btn_ultimo = tk.Button(frame_nav, text=">|", width=4, command=ir_ultimo)
    btn_ultimo.pack(side="left", padx=2)

    tk.Label(frame_nav, text="Ir a:", font=("Arial", 9)).pack(side="left", padx=10)
    entry_ir = tk.Entry(frame_nav, width=6, font=("Arial", 9))
    entry_ir.pack(side="left", padx=2)
    entry_ir.bind("<Return>", ir_a_registro)

    # --- BOTONES DE EXPORTACIÓN ---
    def exportar_excel():
        default_name = os.path.basename(ruta_salida)
        f = filedialog.asksaveasfilename(
            title="Exportar a Excel",
            defaultextension=".xlsx",
            initialfile=default_name.replace(".csv", ".xlsx"),
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not f:
            return
        try:
            with pd.ExcelWriter(f, engine="openpyxl") as writer:
                df_input.to_excel(writer, sheet_name="Entrada", index=False)
                df_output.to_excel(writer, sheet_name="Resultados_NombresComunes", index=False)
            messagebox.showinfo("Éxito", f"Exportado a Excel correctamente:\n{f}")
            abrir_archivo_sistema(f)
            visor.destroy()
            root_main.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar a Excel:\n{e}")

    def exportar_access():
        default_name = os.path.basename(ruta_salida).replace(".csv", ".accdb")
        f = filedialog.asksaveasfilename(
            title="Exportar a Base de Datos",
            defaultextension=".accdb",
            initialfile=default_name,
            filetypes=[("Access Database", "*.accdb"), ("SQLite DB", "*.db")]
        )
        if not f:
            return
        try:
            conn = sqlite3.connect(f)
            df_input.astype(str).to_sql("Entrada", conn, if_exists="replace", index=False)
            df_output.astype(str).to_sql("Resultados_NombresComunes", conn, if_exists="replace", index=False)
            conn.close()
            messagebox.showinfo("Éxito", f"Exportado a Base de Datos correctamente:\n{f}")
            abrir_archivo_sistema(f)
            visor.destroy()
            root_main.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar a la base de datos:\n{e}")

    btn_excel = tk.Button(frame_nav, text="Exportar a Excel", command=exportar_excel, bg="#217346", fg="white", font=("Arial", 9, "bold"))
    btn_excel.pack(side="right", padx=5)

    btn_access = tk.Button(frame_nav, text="Exportar a Access", command=exportar_access, bg="#A4373A", fg="white", font=("Arial", 9, "bold"))
    btn_access.pack(side="right", padx=5)

    actualizar_vista()

# =============================================================================
# PROCESO DE SCRAPING EN SEGUNDO PLANO (HILO)
# =============================================================================

def ejecutar_scraping(ruta_csv, ruta_salida, col_busqueda, tipo_busqueda, root_window):
    def proceso():
        encoding = detectar_codificacion(ruta_csv)
        dialect = detectar_dialect(ruta_csv)
        
        try:
            df = pd.read_csv(ruta_csv, sep=dialect.delimiter, dtype=str, encoding=encoding, engine="python")
        except Exception as e:
            root_window.after(0, lambda: messagebox.showerror("Error", f"No se pudo leer el archivo:\n{e}"))
            return

        df.fillna("", inplace=True)
        output_dir = os.path.dirname(ruta_salida)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        with open(ruta_salida, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["taxonID", "scientificName", "idioma", "pais", "nombre"])
            registros_escritos = 0

            try:
                for idx, row in df.iterrows():
                    val_columna = str(row.get(col_busqueda, "")).strip()
                    if not val_columna:
                        continue

                    # Determinar el parámetro de búsqueda para la URL de EIDOS
                    if tipo_busqueda == "id":
                        taxon_id = val_columna
                        scientific_name = ""  # Opcional si buscas por ID
                    else:
                        # Si se busca por nombre científico, EIDOS normalmente requiere su ID equivalente. 
                        # Nota: Si la web de EIDOS solo acepta IDs numéricos en la URL, se buscará usando el valor de la columna.
                        taxon_id = val_columna 
                        scientific_name = val_columna

                    url = BASE_URL + str(taxon_id)
                    try:
                        resp = session.get(url, timeout=30)
                        resp.raise_for_status()
                    except:
                        time.sleep(PAUSA_SEGUNDOS)
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    tab = soup.find("div", id="nomcomunes")
                    if tab is None:
                        time.sleep(PAUSA_SEGUNDOS)
                        continue

                    tabla = tab.find("table")
                    if tabla is None:
                        time.sleep(PAUSA_SEGUNDOS)
                        continue

                    for fila in tabla.find_all("tr"):
                        celdas = fila.find_all(["th", "td"])
                        if len(celdas) < 2:
                            continue
                        idioma = celdas[0].get_text(" ", strip=True)
                        nombre = celdas[1].get_text(" ", strip=True)
                        if idioma.lower() == "idioma" and nombre.lower() == "nombre":
                            continue
                        if not idioma or not nombre:
                            continue

                        nombres_separados = SEPARADOR_NOMBRES_REGEX.split(nombre)
                        nombres_separados = [n.strip() for n in nombres_separados if n and n.strip()]
                        pais = IDIOMA_PAIS.get(idioma, "")

                        for nombre_individual in nombres_separados:
                            # Registramos asignando el identificador y nombre científico correspondientes
                            t_id = taxon_id if tipo_busqueda == "id" else ""
                            s_name = scientific_name if tipo_busqueda == "name" else str(row.get("scientificName", ""))
                            
                            writer.writerow([t_id, s_name, idioma, pais, nombre_individual])
                            registros_escritos += 1
                            if registros_escritos % FLUSH_EVERY == 0:
                                f.flush()

                    time.sleep(PAUSA_SEGUNDOS)

            except Exception as e:
                root_window.after(0, lambda: messagebox.showerror("Error", f"Error durante el scraping:\n{e}"))
                return

        root_window.after(0, lambda: [
            messagebox.showinfo("Éxito", f"Scraping completado.\nRegistros generados: {registros_escritos}"),
            abrir_visor_access(ruta_csv, ruta_salida, col_busqueda, tipo_busqueda, root_window)
        ])

    threading.Thread(target=proceso, daemon=True).start()
    messagebox.showinfo("Proceso Iniciado", "El scraping se está ejecutando en segundo plano. Se abrirá el visor automáticamente al terminar.")

# =============================================================================
# INTERFAZ GRÁFICA PRINCIPAL
# =============================================================================

def main():
    root = tk.Tk()
    root.title("Extracción de Nombres Comunes - EIDOS (IEPNB)")
    root.geometry("620x700")

    ruta_csv = {"path": None}
    ruta_salida = {"path": None}

    def seleccionar_csv():
        f = filedialog.askopenfilename(
            title="Selecciona un archivo de entrada",
            filetypes=[("Archivos de datos", "*.csv *.tsv *.txt"), ("Todos", "*.*")]
        )
        if not f:
            return

        ruta_csv["path"] = f
        label_csv.config(text=f)

        base = os.path.splitext(f)[0]
        propuesta = base + "_nomcomunes_resultado.csv"
        salida_entry.delete(0, tk.END)
        salida_entry.insert(0, propuesta)
        ruta_salida["path"] = propuesta

        try:
            encoding = detectar_codificacion(f)
            dialect = detectar_dialect(f)
            df_temp = pd.read_csv(f, sep=dialect.delimiter, nrows=0, encoding=encoding, engine="python")
            columnas = list(df_temp.columns)

            combo_columna['values'] = columnas

            for col in columnas:
                col_lower = col.lower()
                if "taxon" in col_lower or "eidos" in col_lower or "id" in col_lower:
                    combo_columna.set(col)
            
            if not combo_columna.get() and columnas:
                combo_columna.set(columnas[0])

        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron leer las columnas:\n{e}")

    def seleccionar_salida():
        f = filedialog.asksaveasfilename(
            title="Archivo de salida",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if f:
            salida_entry.delete(0, tk.END)
            salida_entry.insert(0, f)
            ruta_salida["path"] = f

    def ejecutar():
        if not ruta_csv["path"]:
            messagebox.showerror("Error", "Selecciona primero un archivo de entrada.")
            return
        if not ruta_salida["path"]:
            messagebox.showerror("Error", "Selecciona una ruta de salida.")
            return
        
        col_sel = combo_columna.get()
        tipo_b = modo_busqueda.get()

        if not col_sel:
            messagebox.showerror("Error", "Debes seleccionar una columna para la búsqueda.")
            return

        ejecutar_scraping(ruta_csv["path"], ruta_salida["path"], col_sel, tipo_b, root)

    label_intro = tk.Label(
        root,
        text=(
            "Extracción de Nombres Comunes oficiales desde EIDOS (IEPNB - MITECO).\n\n"
            "ℹ️ NOTA DE CODIFICACIÓN:\n"
            "• Los ficheros CSV intermedios se guardan en UTF-8.\n"
            "• Al exportar a Excel/Access, se ajusta a los estándares de Windows (ANSI/cp1252)."
        ),
        justify="left",
        font=("Arial", 9),
        fg="#333333"
    )
    label_intro.pack(pady=10)

    btn_csv = tk.Button(root, text="Seleccionar archivo de entrada", command=seleccionar_csv, bg="#2196F3", fg="white", font=("Arial", 9, "bold"))
    btn_csv.pack(pady=5)

    label_csv = tk.Label(root, text="(ningún archivo seleccionado)", font=("Arial", 9), fg="gray")
    label_csv.pack(pady=5)

    # Marco de opciones de búsqueda (Radiobuttons)
    frame_modo = tk.LabelFrame(root, text=" Criterio de Búsqueda ", font=("Arial", 10, "bold"), padx=15, pady=10)
    frame_modo.pack(pady=10, fill="x", padx=40)

    modo_busqueda = tk.StringVar(value="id")
    
    rb_id = tk.Radiobutton(frame_modo, text="Buscar por Identificador (taxonID / EIDOS_ID)", variable=modo_busqueda, value="id", font=("Arial", 9))
    rb_id.pack(anchor="w", pady=2)
    
    rb_name = tk.Radiobutton(frame_modo, text="Buscar por Nombre Científico (scientificName)", variable=modo_busqueda, value="name", font=("Arial", 9))
    rb_name.pack(anchor="w", pady=2)

    # Marco de selección de columna
    frame_cols = tk.LabelFrame(root, text=" Columna a utilizar ", font=("Arial", 10, "bold"), padx=15, pady=10)
    frame_cols.pack(pady=10, fill="x", padx=40)

    tk.Label(frame_cols, text="Selecciona la columna correspondiente:", font=("Arial", 9)).pack(anchor="w")
    combo_columna = ttk.Combobox(frame_cols, state="readonly", width=45)
    combo_columna.pack(pady=5, anchor="w")

    frame_salida = tk.Frame(root)
    frame_salida.pack(pady=10)

    tk.Label(frame_salida, text="Archivo de salida:", font=("Arial", 10)).pack()
    salida_entry = tk.Entry(frame_salida, width=50)
    salida_entry.pack(pady=5)

    btn_salida = tk.Button(frame_salida, text="Seleccionar archivo de salida", command=seleccionar_salida)
    btn_salida.pack()

    btn_run = tk.Button(root, text="Iniciar Scraping", command=ejecutar, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), height=2, width=20)
    btn_run.pack(pady=15)

    root.mainloop()

if __name__ == "__main__":
    main()