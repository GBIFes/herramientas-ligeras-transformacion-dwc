"""
===============================================================================
gui.py - Interfaz Gráfica, Visor Estilo Access y Exportación Integrada (Excel/SQLite)
===============================================================================
"""

import os
import shutil
import threading
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from config import detectar_codificacion, detectar_dialect, BASE_URL, abrir_archivo_sistema
from scraper import procesar_fila

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

        # Copia exacta del documento original al directorio de salida
        try:
            if ruta_csv and os.path.exists(ruta_csv):
                nombre_archivo_original = os.path.basename(ruta_csv)
                ruta_copia_entrada = os.path.join(dir_salida, f"copia_{nombre_archivo_original}")
                shutil.copy2(ruta_csv, ruta_copia_entrada)
        except Exception as ex:
            print(f"Aviso al copiar el archivo original: {ex}")

        nombre_base = os.path.splitext(os.path.basename(ruta_csv))[0]
        f_taxones = os.path.join(dir_salida, f"{nombre_base}_taxonesEIDOS.csv")
        f_nombres = os.path.join(dir_salida, f"{nombre_base}_NombreComunes.csv")
        f_info = os.path.join(dir_salida, f"{nombre_base}_Informacion.csv")
        f_cons = os.path.join(dir_salida, f"{nombre_base}_EstadoConservacion.csv")
        f_col = os.path.join(dir_salida, f"{nombre_base}_ColeccionesCatalogos.csv")
        f_legal = os.path.join(dir_salida, f"{nombre_base}_EstadoLegal.csv")
        f_bib = os.path.join(dir_salida, f"{nombre_base}_Bibliografia.csv")
        f_sin = os.path.join(dir_salida, f"{nombre_base}_Sinonimia.csv")

        total_filas = len(df)
        completados = [0]
        root_window.after(0, lambda: progress_bar.config(maximum=total_filas, value=0))

        lista_nombres, lista_info, lista_cons, lista_col, lista_legal, lista_bib, lista_sin = [], [], [], [], [], [], []
        headers_cons_guardado, headers_col_guardado, headers_legal_guardado, headers_bib_guardado = [], [], [], []

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_idx = {
                executor.submit(procesar_fila, row, col_busqueda, tipo_busqueda): idx 
                for idx, row in df.iterrows()
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    res, e_id = future.result()
                    if e_id:
                        df.at[idx, "EIDOS_ID"] = e_id
                    if res:
                        if res["info"]: lista_info.append(res["info"])
                        if res["nombres"]: lista_nombres.extend(res["nombres"])
                        if res["conservacion"]: 
                            lista_cons.extend(res["conservacion"])
                            if not headers_cons_guardado and res.get("headers_cons"):
                                headers_cons_guardado = res["headers_cons"]
                        if res["colecciones"]: 
                            lista_col.extend(res["colecciones"])
                            if not headers_col_guardado and res.get("headers_col"):
                                headers_col_guardado = res["headers_col"]
                        if res["legal"]: 
                            lista_legal.extend(res["legal"])
                            if not headers_legal_guardado and res.get("headers_legal"):
                                headers_legal_guardado = res["headers_legal"]
                        if res["bibliografia"]: 
                            lista_bib.extend(res["bibliografia"])
                            if not headers_bib_guardado and res.get("headers_bib"):
                                headers_bib_guardado = res["headers_bib"]
                        if res["sinonimia"]: lista_sin.extend(res["sinonimia"])
                except Exception:
                    pass

                completados[0] += 1
                prog = completados[0]
                por = int((prog / total_filas) * 100)
                root_window.after(0, lambda p=prog, tf=total_filas, p_ct=por: [
                    progress_bar.config(value=p),
                    lbl_progreso.config(text=f"Procesando registros: {p}/{tf} ({p_ct}%)")
                ])

        def crear_df_seguro(lista_datos, cabeceras_guardadas):
            if not lista_datos:
                return pd.DataFrame(columns=cabeceras_guardadas if cabeceras_guardadas else None)
            try:
                if cabeceras_guardadas and len(cabeceras_guardadas) == len(lista_datos[0]):
                    return pd.DataFrame(lista_datos, columns=cabeceras_guardadas)
                else:
                    return pd.DataFrame(lista_datos)
            except Exception:
                return pd.DataFrame(lista_datos)

        df.to_csv(f_taxones, sep=dialect.delimiter, index=False, encoding=encoding)
        pd.DataFrame(lista_nombres, columns=["EIDOS_ID", "scientificName", "idioma", "pais", "nombre"]).to_csv(f_nombres, index=False, encoding="utf-8")
        pd.DataFrame(lista_info).to_csv(f_info, index=False, encoding="utf-8")
        
        crear_df_seguro(lista_cons, headers_cons_guardado).to_csv(f_cons, index=False, encoding="utf-8")
        crear_df_seguro(lista_col, headers_col_guardado).to_csv(f_col, index=False, encoding="utf-8")
        crear_df_seguro(lista_legal, headers_legal_guardado).to_csv(f_legal, index=False, encoding="utf-8")
        crear_df_seguro(lista_bib, headers_bib_guardado).to_csv(f_bib, index=False, encoding="utf-8")
        pd.DataFrame(lista_sin, columns=["EIDOS_ID", "Sinonimo_EIDOS_ID", "Nombre_Sinonimo"]).to_csv(f_sin, index=False, encoding="utf-8")

        root_window.after(0, lambda: [
            btn_ejecutar.config(state=tk.NORMAL),
            progress_bar.config(value=0),
            lbl_progreso.config(text="¡Proceso finalizado! Abriendo visor..."),
            callback_fin(f_taxones, f_nombres, f_info, f_cons, f_col, f_legal, f_bib, f_sin, col_busqueda, tipo_busqueda, root_window)
        ])

    threading.Thread(target=proceso, daemon=True).start()

def abrir_visor_access(f_taxones, f_nombres, f_info, f_cons, f_col, f_legal, f_bib, f_sin, col_busqueda_sel, tipo_busqueda, root_main):
    try:
        enc_in = detectar_codificacion(f_taxones)
        sep_in = detectar_dialect(f_taxones).delimiter
        df_input = pd.read_csv(f_taxones, sep=sep_in, dtype=str, encoding=enc_in, engine="python")
        df_input.fillna("", inplace=True)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo cargar el archivo para el visor:\n{e}")
        return

    def cargar_df_con_cabecera(path):
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                enc = detectar_codificacion(path)
                sep = detectar_dialect(path).delimiter
                df_c = pd.read_csv(path, sep=sep, dtype=str, encoding=enc, engine="python").fillna("")
                if not df_c.empty:
                    primera_col = df_c.columns[0]
                    df_c = df_c[df_c[primera_col].astype(str).str.strip().str.lower() != primera_col.lower()]
                return df_c
            except Exception:
                try:
                    return pd.read_csv(path, dtype=str, encoding="utf-8", engine="python").fillna("")
                except Exception:
                    return pd.DataFrame()
        return pd.DataFrame()

    df_output = cargar_df_con_cabecera(f_nombres)
    df_inf = cargar_df_con_cabecera(f_info)
    df_con = cargar_df_con_cabecera(f_cons)
    df_collec = cargar_df_con_cabecera(f_col)
    df_leg = cargar_df_con_cabecera(f_legal)
    df_bi = cargar_df_con_cabecera(f_bib)
    df_si = cargar_df_con_cabecera(f_sin)

    visor = tk.Toplevel()
    visor.title("Visor Ampliado - Estilo Formulario Access")
    visor.geometry("1200x700")

    total_registros = len(df_input)
    current_idx = {"val": 0}
    url_ficha_actual = {"link": ""}

    frame_main = tk.Frame(visor)
    frame_main.pack(fill="both", expand=True, padx=10, pady=10)

    frame_left = tk.LabelFrame(frame_main, text=" Ficha de Especie (Entrada) ", font=("Segoe UI", 10, "bold"), padx=10, pady=10, width=380)
    frame_left.pack(side="left", fill="both", expand=False, padx=5)
    frame_left.pack_propagate(False)

    canvas_left = tk.Canvas(frame_left, borderwidth=0, highlightthickness=0)
    scrollbar_left = ttk.Scrollbar(frame_left, orient="vertical", command=canvas_left.yview)
    scrollable_frame_left = tk.Frame(canvas_left)
    scrollable_frame_left.bind("<Configure>", lambda e: canvas_left.configure(scrollregion=canvas_left.bbox("all")))
    canvas_left.create_window((0, 0), window=scrollable_frame_left, anchor="nw")
    canvas_left.configure(yscrollcommand=scrollbar_left.set)

    canvas_left.pack(side="left", fill="both", expand=True)
    scrollbar_left.pack(side="right", fill="y")

    entries_left = {}
    input_columns = list(df_input.columns)
    for col in input_columns:
        f_row = tk.Frame(scrollable_frame_left)
        f_row.pack(fill="x", pady=2)
        tk.Label(f_row, text=f"{col}:", width=15, anchor="w", font=("Segoe UI", 9, "bold")).pack(side="left")
        e = tk.Entry(f_row, font=("Segoe UI", 9), width=25)
        e.pack(side="right", fill="x", expand=True)
        entries_left[col] = e

    frame_right = tk.LabelFrame(frame_main, text=" Datos Extraídos de EIDOS ", font=("Segoe UI", 10, "bold"), padx=5, pady=5)
    frame_right.pack(side="right", fill="both", expand=True, padx=5)

    lbl_enlace = tk.Label(frame_right, text="🔗 Abrir ficha en EIDOS", font=("Segoe UI", 9, "underline"), fg="blue", cursor="hand2")
    lbl_enlace.pack(anchor="w", padx=5, pady=2)

    def abrir_enlace_eidos(event=None):
        if url_ficha_actual["link"] and url_ficha_actual["link"].startswith("http"):
            webbrowser.open(url_ficha_actual["link"])
        else:
            messagebox.showwarning("Aviso", "No hay un ID válido seleccionado para abrir la ficha.")
    lbl_enlace.bind("<Button-1>", abrir_enlace_eidos)

    notebook = ttk.Notebook(frame_right)
    notebook.pack(fill="both", expand=True, padx=5, pady=5)

    def crear_pestana_tree_desde_df(nombre_tab, df_origen):
        frame = tk.Frame(notebook)
        notebook.add(frame, text=nombre_tab)
        columnas = list(df_origen.columns) if not df_origen.empty else ["EIDOS_ID", "Datos"]
        tree = ttk.Treeview(frame, columns=columnas, show="headings", height=12)
        for c in columnas:
            tree.heading(c, text=str(c).capitalize())
            tree.column(c, width=120, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree, columnas

    def crear_pestana_vertical(nombre_tab):
        frame = tk.Frame(notebook)
        notebook.add(frame, text=nombre_tab)
        columnas = ["Propiedad", "Valor"]
        tree = ttk.Treeview(frame, columns=columnas, show="headings", height=12)
        tree.heading("Propiedad", text="Propiedad")
        tree.heading("Valor", text="Valor")
        tree.column("Propiedad", width=180, anchor="w")
        tree.column("Valor", width=350, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    tree_nombres, cols_nombres = crear_pestana_tree_desde_df("Nombres Comunes", df_output)
    tree_info = crear_pestana_vertical("Información")
    tree_cons, cols_cons = crear_pestana_tree_desde_df("Conservación", df_con)
    tree_col, cols_col = crear_pestana_tree_desde_df("Colecciones", df_collec)
    tree_legal, cols_legal = crear_pestana_tree_desde_df("Estado Legal", df_leg)
    tree_bib, cols_bib = crear_pestana_tree_desde_df("Bibliografía", df_bi)
    tree_sin, cols_sin = crear_pestana_tree_desde_df("Sinonimia", df_si)

    def actualizar_vista():
        if total_registros == 0:
            return
        idx = current_idx["val"]
        row = df_input.iloc[idx]

        for col in input_columns:
            entries_left[col].delete(0, tk.END)
            entries_left[col].insert(0, str(row.get(col, "")))

        e_id = str(row.get("EIDOS_ID", "")).strip()

        for t in [tree_nombres, tree_info, tree_cons, tree_col, tree_legal, tree_bib, tree_sin]:
            for item in t.get_children():
                t.delete(item)

        def poblar_tree(df_target, tree_target, columnas_tree):
            if not df_target.empty and e_id and "EIDOS_ID" in df_target.columns:
                filtrados = df_target[df_target["EIDOS_ID"].astype(str).str.strip() == e_id]
                for _, r in filtrados.iterrows():
                    vals = [r.get(c, "") for c in columnas_tree]
                    tree_target.insert("", "end", values=vals)

        poblar_tree(df_output, tree_nombres, cols_nombres)

        if not df_inf.empty and e_id and "EIDOS_ID" in df_inf.columns:
            match_info = df_inf[df_inf["EIDOS_ID"].astype(str).str.strip() == e_id]
            if not match_info.empty:
                r_inf = match_info.iloc[0]
                for k, v in r_inf.items():
                    if k != "EIDOS_ID" and str(v).strip():
                        tree_info.insert("", "end", values=(k, v))

        poblar_tree(df_con, tree_cons, cols_cons)
        poblar_tree(df_collec, tree_col, cols_col)
        poblar_tree(df_leg, tree_legal, cols_legal)
        poblar_tree(df_bi, tree_bib, cols_bib)
        poblar_tree(df_si, tree_sin, cols_sin)

        if e_id:
            url_ficha_actual["link"] = f"{BASE_URL}/{e_id}"
            lbl_enlace.config(text=f"🔗 Abrir ficha de EIDOS (ID: {e_id})", fg="blue")
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
    lbl_estado = tk.Label(frame_nav, text="Registro 0 de 0", font=("Segoe UI", 9))
    lbl_estado.pack(side="left", padx=10)
    tk.Button(frame_nav, text=">", width=4, command=ir_siguiente).pack(side="left", padx=2)
    tk.Button(frame_nav, text=">|", width=4, command=ir_ultimo).pack(side="left", padx=2)

    tk.Label(frame_nav, text="Ir a:", font=("Segoe UI", 9)).pack(side="left", padx=10)
    entry_ir = tk.Entry(frame_nav, width=6, font=("Segoe UI", 9))
    entry_ir.pack(side="left", padx=2)
    entry_ir.bind("<Return>", ir_a_registro)

    def exportar_todo_en_directorio():
        dir_destino = os.path.dirname(f_taxones)
        nombre_base_infile = os.path.basename(f_taxones).replace("_taxonesEIDOS.csv", "")
        
        f_excel = os.path.join(dir_destino, f"{nombre_base_infile}_exportacion_Access.xlsx")
        f_db = os.path.join(dir_destino, f"{nombre_base_infile}_EIDOS.db")
        
        try:
            df_t_exp = cargar_df_con_cabecera(f_taxones)
            df_n_exp = cargar_df_con_cabecera(f_nombres)
            df_i_exp = cargar_df_con_cabecera(f_info)
            df_c_exp = cargar_df_con_cabecera(f_cons)
            df_col_exp = cargar_df_con_cabecera(f_col)
            df_l_exp = cargar_df_con_cabecera(f_legal)
            df_b_exp = cargar_df_con_cabecera(f_bib)
            df_s_exp = cargar_df_con_cabecera(f_sin)

            # 1. Generar Excel completo con OpenPyXL en el directorio de salida
            with pd.ExcelWriter(f_excel, engine="openpyxl") as writer:
                if not df_t_exp.empty: df_t_exp.to_excel(writer, sheet_name="taxones", index=False)
                if not df_n_exp.empty: df_n_exp.to_excel(writer, sheet_name="Resultados_NombresComunes", index=False)
                if not df_i_exp.empty: df_i_exp.to_excel(writer, sheet_name="Informacion", index=False)
                if not df_c_exp.empty: df_c_exp.to_excel(writer, sheet_name="EstadoConservacion", index=False)
                if not df_col_exp.empty: df_col_exp.to_excel(writer, sheet_name="ColeccionesCatalogos", index=False)
                if not df_l_exp.empty: df_l_exp.to_excel(writer, sheet_name="EstadoLegal", index=False)
                if not df_b_exp.empty: df_b_exp.to_excel(writer, sheet_name="Bibliografia", index=False)
                if not df_s_exp.empty: df_s_exp.to_excel(writer, sheet_name="Sinonimia", index=False)

            # 2. Generar Base de Datos SQLite (.db) en el mismo directorio de salida
            conn = sqlite3.connect(f_db)
            if not df_t_exp.empty: df_t_exp.to_sql("taxones", conn, if_exists="replace", index=False)
            if not df_n_exp.empty: df_n_exp.to_sql("NombresComunes", conn, if_exists="replace", index=False)
            if not df_i_exp.empty: df_i_exp.to_sql("Informacion", conn, if_exists="replace", index=False)
            if not df_c_exp.empty: df_c_exp.to_sql("EstadoConservacion", conn, if_exists="replace", index=False)
            if not df_col_exp.empty: df_col_exp.to_sql("ColeccionesCatalogos", conn, if_exists="replace", index=False)
            if not df_l_exp.empty: df_l_exp.to_sql("EstadoLegal", conn, if_exists="replace", index=False)
            if not df_b_exp.empty: df_b_exp.to_sql("Bibliografia", conn, if_exists="replace", index=False)
            if not df_s_exp.empty: df_s_exp.to_sql("Sinonimia", conn, if_exists="replace", index=False)
            conn.close()

            messagebox.showinfo(
                "Éxito", 
                f"Exportación completada correctamente en:\n{dir_destino}\n\n"
                f"• Copia del archivo original guardada\n"
                f"• Excel generado: {os.path.basename(f_excel)}\n"
                f"• SQLite DB generada: {os.path.basename(f_db)}"
            )
            abrir_archivo_sistema(dir_destino)
            visor.destroy()
            root_main.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo completar la exportación:\n{e}")

    tk.Button(frame_nav, text="Exportar (Excel + SQLite DB)", command=exportar_todo_en_directorio, bg="#217346", fg="white", font=("Segoe UI", 9, "bold")).pack(side="right", padx=5)

    actualizar_vista()