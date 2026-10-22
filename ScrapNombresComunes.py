"""
===============================================================================
ScrapNombresComunes.py - Aplicación con Directorio de Salida, Nombres Personalizados
y Hoja de Excel llamada 'taxones'
===============================================================================
"""

import os
import re
import time
import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import platform
import webbrowser
import requests
from bs4 import BeautifulSoup
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BASE_URL = "https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos"

IDIOMA_PAIS = {
    "Castellano": "ES", "Catalán": "ES", "Euskera": "ES", "Gallego": "ES",
    "Valenciano": "ES", "Mallorquín": "ES", "Altoaragonés": "ES", "Inglés": "GB",
    "Francés": "FR", "Portugués": "PT", "Italiano": "IT", "Alemán": "DE",
}

SEPARADOR_NOMBRES_REGEX = re.compile(r'\s*[;,]\s*')

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
    try:
        if platform.system() == "Windows":
            os.startfile(ruta)
        elif platform.system() == "Darwin":
            subprocess.call(["open", ruta])
        else:
            subprocess.call(["xdg-open", ruta])
    except Exception as e:
        print(f"No se pudo abrir el archivo automáticamente: {e}")

def extraer_desde_url_ficha(session, url):
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    tab = soup.find("div", id="nomcomunes")
    if tab is None:
        return []

    tabla = tab.find("table")
    if tabla is None:
        return []

    datos = []
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
        datos.append((idioma, nombre))
    return datos

def obtener_url_y_id_por_busqueda_texto(session, texto_busqueda):
    search_url = f"{BASE_URL}?search_api_fulltext={requests.utils.quote(texto_busqueda)}"
    try:
        resp = session.get(search_url, timeout=20)
        resp.raise_for_status()
    except:
        return None, ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a['href']
        if "/eidos/" in href:
            full_url = href if href.startswith("http") else "https://iepnb.gob.es" + href
            match = re.search(r'/eidos/(\d+)', full_url)
            eidos_id = match.group(1) if match else ""
            return full_url, eidos_id
    return None, ""

def procesar_fila(row, col_busqueda, tipo_busqueda):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    val_columna = str(row.get(col_busqueda, "")).strip()
    if not val_columna:
        return [], ""

    ficha_url = None
    eidos_id_reg = ""
    scientific_name_reg = str(row.get("scientificName", "")) if "scientificName" in row else ""

    if tipo_busqueda == "id":
        eidos_id_reg = val_columna
        ficha_url = f"{BASE_URL}/{eidos_id_reg}"
    else:
        scientific_name_reg = val_columna
        ficha_url, eidos_id_reg = obtener_url_y_id_por_busqueda_texto(session, val_columna)

    if not eidos_id_reg and ficha_url:
        match = re.search(r'/eidos/(\d+)', ficha_url)
        if match:
            eidos_id_reg = match.group(1)

    if not ficha_url:
        return [], eidos_id_reg

    nomcomunes = extraer_desde_url_ficha(session, ficha_url)
    resultados_fila = []

    for idioma, nombre in nomcomunes:
        nombres_separados = SEPARADOR_NOMBRES_REGEX.split(nombre)
        nombres_separados = [n.strip() for n in nombres_separados if n and n.strip()]
        pais = IDIOMA_PAIS.get(idioma, "")

        for nombre_individual in nombres_separados:
            resultados_fila.append([eidos_id_reg, scientific_name_reg, idioma, pais, nombre_individual])

    return resultados_fila, eidos_id_reg

def ejecutar_scraping(ruta_csv, dir_salida, col_busqueda, tipo_busqueda, root_window, progress_bar, lbl_progreso, btn_ejecutar, callback_fin):
    def proceso():
        encoding = detectar_codificacion(ruta_csv)
        dialect = detectar_dialect(ruta_csv)
        
        try:
            df = pd.read_csv(ruta_csv, sep=dialect.delimiter, dtype=str, encoding=encoding, engine="python")
        except Exception as e:
            root_window.after(0, lambda: messagebox.showerror("Error", f"No se pudo leer el archivo:\n{e}"))
            root_window.after(0, lambda: btn_ejecutar.config(state=tk.NORMAL))
            return

        df.fillna("", inplace=True)
        if "EIDOS_ID" not in df.columns:
            df["EIDOS_ID"] = ""

        if not os.path.exists(dir_salida):
            os.makedirs(dir_salida, exist_ok=True)

        nombre_base_infile = os.path.splitext(os.path.basename(ruta_csv))[0]
        ruta_salida_taxones = os.path.join(dir_salida, f"{nombre_base_infile}_taxonesEIDOS.csv")
        ruta_salida_nombres = os.path.join(dir_salida, f"{nombre_base_infile}_NombreComunes.csv")

        total_filas = len(df)
        completados = [0]
        root_window.after(0, lambda: progress_bar.config(maximum=total_filas, value=0))

        resultados_totales = []

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_idx = {
                executor.submit(procesar_fila, row, col_busqueda, tipo_busqueda): idx 
                for idx, row in df.iterrows()
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    res_filas, e_id = future.result()
                    if e_id:
                        df.at[idx, "EIDOS_ID"] = e_id
                    if res_filas:
                        resultados_totales.extend(res_filas)
                except Exception:
                    pass

                completados[0] += 1
                prog = completados[0]
                porcentaje = int((prog / total_filas) * 100)
                
                root_window.after(0, lambda p=prog, tf=total_filas, por=porcentaje: [
                    progress_bar.config(value=p),
                    lbl_progreso.config(text=f"Procesando registros: {p}/{tf} ({por}%)")
                ])

        with open(ruta_salida_nombres, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["EIDOS_ID", "scientificName", "idioma", "pais", "nombre"])
            writer.writerows(resultados_totales)

        df.to_csv(ruta_salida_taxones, sep=dialect.delimiter, index=False, encoding=encoding)

        root_window.after(0, lambda: [
            btn_ejecutar.config(state=tk.NORMAL),
            progress_bar.config(value=0),
            lbl_progreso.config(text="¡Proceso finalizado! Abriendo visor..."),
            callback_fin(ruta_salida_taxones, ruta_salida_nombres, col_busqueda, tipo_busqueda, root_window)
        ])

    threading.Thread(target=proceso, daemon=True).start()

def abrir_visor_access(ruta_taxones, ruta_nombres, col_busqueda_sel, tipo_busqueda, root_main):
    try:
        enc_in = detectar_codificacion(ruta_taxones)
        sep_in = detectar_dialect(ruta_taxones).delimiter
        df_input = pd.read_csv(ruta_taxones, sep=sep_in, dtype=str, encoding=enc_in, engine="python")
        df_input.fillna("", inplace=True)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo cargar el archivo de taxones para el visor:\n{e}")
        return

    try:
        df_output = pd.read_csv(ruta_nombres, dtype=str, encoding="utf-8")
        df_output.fillna("", inplace=True)
    except Exception as e:
        df_output = pd.DataFrame(columns=["EIDOS_ID", "scientificName", "idioma", "pais", "nombre"])

    visor = tk.Toplevel()
    visor.title("Visor de Registros - Estilo Formulario Access")
    visor.geometry("1100x620")

    total_registros = len(df_input)
    current_idx = {"val": 0}
    url_ficha_actual = {"link": ""}

    frame_main = tk.Frame(visor)
    frame_main.pack(fill="both", expand=True, padx=10, pady=10)

    frame_left = tk.LabelFrame(frame_main, text=" Ficha de Especie (Entrada) ", font=("Arial", 10, "bold"), padx=10, pady=10)
    frame_left.pack(side="left", fill="both", expand=True, padx=5)

    entries_left = {}
    input_columns = list(df_input.columns)
    for col in input_columns:
        f_row = tk.Frame(frame_left)
        f_row.pack(fill="x", pady=2)
        tk.Label(f_row, text=f"{col}:", width=20, anchor="w", font=("Arial", 9, "bold")).pack(side="left")
        e = tk.Entry(f_row, font=("Arial", 9))
        e.pack(side="right", fill="x", expand=True)
        entries_left[col] = e

    frame_right = tk.LabelFrame(frame_main, text=" Nombres Comunes Encontrados (Salida) ", font=("Arial", 10, "bold"), padx=10, pady=10)
    frame_right.pack(side="right", fill="both", expand=True, padx=5)

    lbl_enlace = tk.Label(frame_right, text="🔗 Abrir ficha en EIDOS (Seleccione un registro)", font=("Arial", 9, "underline"), fg="blue", cursor="hand2")
    lbl_enlace.pack(anchor="w", pady=5)

    def abrir_enlace_eidos(event=None):
        if url_ficha_actual["link"] and url_ficha_actual["link"].startswith("http"):
            webbrowser.open(url_ficha_actual["link"])
        else:
            messagebox.showwarning("Aviso", "No hay un ID válido seleccionado para abrir la ficha.")

    lbl_enlace.bind("<Button-1>", abrir_enlace_eidos)

    tree_frame = tk.Frame(frame_right)
    tree_frame.pack(fill="both", expand=True)
    
    tree_cols = ["EIDOS_ID", "idioma", "pais", "nombre"]
    tree = ttk.Treeview(tree_frame, columns=tree_cols, show="headings", height=13)
    for c in tree_cols:
        tree.heading(c, text=c.capitalize())
        tree.column(c, width=110, anchor="w")
    
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

        eidos_id_encontrado = ""
        if not df_output.empty:
            if tipo_busqueda == "id":
                filtrados = df_output[df_output["EIDOS_ID"].astype(str).str.strip() == valor_busqueda_activo]
            else:
                filtrados = df_output[df_output["scientificName"].astype(str).str.strip().str.lower() == valor_busqueda_activo.lower()]

            for _, r_out in filtrados.iterrows():
                e_id = r_out.get("EIDOS_ID", "")
                if not eidos_id_encontrado and e_id:
                    eidos_id_encontrado = e_id
                tree.insert("", "end", values=(e_id, r_out.get("idioma", ""), r_out.get("pais", ""), r_out.get("nombre", "")))

        if not eidos_id_encontrado and "EIDOS_ID" in row:
            eidos_id_encontrado = str(row.get("EIDOS_ID", "")).strip()

        if eidos_id_encontrado:
            url_ficha = f"https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/{eidos_id_encontrado}"
            url_ficha_actual["link"] = url_ficha
            lbl_enlace.config(text=f"🔗 Abrir ficha de EIDOS (ID: {eidos_id_encontrado})", fg="blue")
        else:
            url_ficha_actual["link"] = ""
            lbl_enlace.config(text="🔗 Ficha de EIDOS no disponible para este registro", fg="gray")

        lbl_estado.config(text=f"Registro {idx + 1} de {total_registros}")
        entry_ir.delete(0, tk.END)
        entry_ir.insert(0, str(idx + 1))

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

    tk.Button(frame_nav, text="|<", width=4, command=ir_primero).pack(side="left", padx=2)
    tk.Button(frame_nav, text="<", width=4, command=ir_anterior).pack(side="left", padx=2)
    lbl_estado = tk.Label(frame_nav, text="Registro 0 de 0", font=("Arial", 9))
    lbl_estado.pack(side="left", padx=10)
    tk.Button(frame_nav, text=">", width=4, command=ir_siguiente).pack(side="left", padx=2)
    tk.Button(frame_nav, text=">|", width=4, command=ir_ultimo).pack(side="left", padx=2)

    tk.Label(frame_nav, text="Ir a:", font=("Arial", 9)).pack(side="left", padx=10)
    entry_ir = tk.Entry(frame_nav, width=6, font=("Arial", 9))
    entry_ir.pack(side="left", padx=2)
    entry_ir.bind("<Return>", ir_a_registro)

    def exportar_excel_en_directorio():
        dir_destino = os.path.dirname(ruta_taxones)
        nombre_base_infile = os.path.basename(ruta_taxones).replace("_taxonesEIDOS.csv", "")
        f_excel = os.path.join(dir_destino, f"{nombre_base_infile}_exportacion_Access.xlsx")
        
        try:
            with pd.ExcelWriter(f_excel, engine="openpyxl") as writer:
                # Se nombra la hoja de entrada como 'taxones' y la de salida como 'Resultados_NombresComunes'
                df_input.to_excel(writer, sheet_name="taxones", index=False)
                df_output.to_excel(writer, sheet_name="Resultados_NombresComunes", index=False)
            messagebox.showinfo(
                "Éxito", 
                f"Excel generado correctamente en el directorio:\n{f_excel}\n\n"
                "Para llevarlo a Access: Abre Access > Datos externos > Nuevo origen de datos > Desde un archivo > Excel."
            )
            abrir_archivo_sistema(f_excel)
            visor.destroy()
            root_main.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar a Excel:\n{e}")

    tk.Button(frame_nav, text="Exportar a Excel (Acceso Directo Access)", command=exportar_excel_en_directorio, bg="#217346", fg="white", font=("Arial", 9, "bold")).pack(side="right", padx=5)

    actualizar_vista()

def main():
    root = tk.Tk()
    root.title("Extracción de Nombres Comunes - EIDOS (IEPNB)")
    root.geometry("620x780")

    ruta_csv = {"path": None}
    dir_salida = {"path": None}

    def seleccionar_csv():
        f = filedialog.askopenfilename(title="Selecciona un archivo de entrada", filetypes=[("Archivos de datos", "*.csv *.tsv *.txt"), ("Todos", "*.*")])
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

        dir_destino_final = dir_salida["path"]
        dir_entrada_original = os.path.dirname(ruta_csv["path"])
        if os.path.abspath(dir_destino_final) == os.path.abspath(dir_entrada_original):
            dir_destino_final = os.path.join(dir_entrada_original, "EIDOS")

        btn_run.config(state=tk.DISABLED)
        ejecutar_scraping(
            ruta_csv["path"], dir_destino_final, col_sel, tipo_b, 
            root, progress_bar, lbl_progreso, btn_run, abrir_visor_access
        )

    tk.Label(
        root, 
        text=(
            "Extracción de Nombres Comunes oficiales desde EIDOS (IEPNB - MITECO).\n\n"
            "ℹ️ INFORMACIÓN DE SALIDA:\n"
            "• Se crearán los ficheros '[Entrada]_taxonesEIDOS.csv' y '[Entrada]_NombreComunes.csv'.\n"
            "• Al exportar a Excel, la hoja de entrada se llamará 'taxones' (ideal para Access).\n"
            "• Si eliges el mismo directorio que el fichero de entrada, se creará automáticamente\n"
            "  una carpeta llamada 'EIDOS' para almacenar todos los resultados."
        ), 
        justify="left", font=("Arial", 9), fg="#333333"
    ).pack(pady=10)

    tk.Button(root, text="Seleccionar archivo de entrada", command=seleccionar_csv, bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(pady=5)
    label_csv = tk.Label(root, text="(ningún archivo seleccionado)", font=("Arial", 9), fg="gray")
    label_csv.pack(pady=5)

    frame_modo = tk.LabelFrame(root, text=" Criterio de Búsqueda ", font=("Arial", 10, "bold"), padx=15, pady=10)
    frame_modo.pack(pady=10, fill="x", padx=40)
    modo_busqueda = tk.StringVar(value="id")
    tk.Radiobutton(frame_modo, text="Buscar por Identificador (EIDOS_ID / taxonID)", variable=modo_busqueda, value="id", font=("Arial", 9)).pack(anchor="w", pady=2)
    tk.Radiobutton(frame_modo, text="Buscar por Nombre Científico (vía search_api_fulltext)", variable=modo_busqueda, value="name", font=("Arial", 9)).pack(anchor="w", pady=2)

    frame_cols = tk.LabelFrame(root, text=" Columna a utilizar ", font=("Arial", 10, "bold"), padx=15, pady=10)
    frame_cols.pack(pady=10, fill="x", padx=40)
    tk.Label(frame_cols, text="Selecciona la columna correspondiente:", font=("Arial", 9)).pack(anchor="w")
    combo_columna = ttk.Combobox(frame_cols, state="readonly", width=45)
    combo_columna.pack(pady=5, anchor="w")

    frame_salida = tk.Frame(root)
    frame_salida.pack(pady=10)
    tk.Label(frame_salida, text="Directorio de salida:", font=("Arial", 10)).pack()
    salida_entry = tk.Entry(frame_salida, width=50)
    salida_entry.pack(pady=5)
    tk.Button(frame_salida, text="Seleccionar directorio de salida", command=seleccionar_directorio).pack()

    frame_progreso = tk.Frame(root)
    frame_progreso.pack(pady=10, fill="x", padx=40)

    lbl_progreso = tk.Label(frame_progreso, text="Esperando inicio...", font=("Arial", 9))
    lbl_progreso.pack(anchor="w", pady=2)

    progress_bar = ttk.Progressbar(frame_progreso, orient="horizontal", length=520, mode="determinate")
    progress_bar.pack(pady=2)

    btn_run = tk.Button(root, text="Iniciar Scraping", command=ejecutar, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), height=2, width=20)
    btn_run.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()