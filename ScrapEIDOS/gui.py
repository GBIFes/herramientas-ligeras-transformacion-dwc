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
from cartografia import (
    COLUMNAS_COORD, COLUMNAS_ESTADO, recopilar_coordenadas,
    guardar_cartografia, generar_mapa, abrir_mapa,
)


class VentanaProgresoModal:
    """Ventana emergente modal con barra de progreso reutilizable."""
    def __init__(self, parent, titulo="Cargando datos...", mensaje="Procesando registros, por favor espera..."):
        self.top = tk.Toplevel(parent)
        self.top.title(titulo)
        self.top.geometry("450x150")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        # Centrar la ventana respecto al padre
        self.top.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 225
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 75
        self.top.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.lbl_mensaje = tk.Label(self.top, text=mensaje, font=("Segoe UI", 9, "bold"), fg="#333333", wraplength=420, justify="left")
        self.lbl_mensaje.pack(pady=(15, 5), padx=20, anchor="w")

        self.lbl_detalle = tk.Label(self.top, text="Iniciando...", font=("Segoe UI", 8), fg="#666666", anchor="w")
        self.lbl_detalle.pack(pady=(0, 5), padx=20, fill="x")

        self.progress = ttk.Progressbar(self.top, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=(5, 15), padx=20)

    def actualizar(self, valor, maximo, detalle=""):
        if maximo > 0:
            self.progress.config(maximum=maximo, value=valor)
        if detalle:
            self.lbl_detalle.config(text=detalle)
        self.top.update_idletasks()

    def set_indeterminado(self, activo=True):
        if activo:
            self.progress.config(mode="indeterminate")
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.config(mode="determinate")

    def cerrar(self):
        try:
            self.progress.stop()
            self.top.grab_release()
            self.top.destroy()
        except Exception:
            pass


def ejecutar_scraping(ruta_csv, dir_salida, col_busqueda, tipo_busqueda, root_window, progress_bar, lbl_progreso, btn_ejecutar, callback_fin, incluir_cartografia=True, nivel_precision="Estándar (Paginación normal - Recomendado)"):
    # Crear ventana emergente de progreso
    modal = VentanaProgresoModal(root_window, titulo="Ejecutando Extracción EIDOS", mensaje="Extrayendo datos de EIDOS...")

    def proceso():
        encoding = detectar_codificacion(ruta_csv)
        dialect = detectar_dialect(ruta_csv)
        
        try:
            df = pd.read_csv(ruta_csv, sep=dialect.delimiter, dtype=str, encoding=encoding, engine="python")
        except Exception as e:
            root_window.after(0, lambda: modal.cerrar())
            root_window.after(0, lambda error=str(e): messagebox.showerror("Error", f"No se pudo leer el archivo:\n{error}"))
            root_window.after(0, lambda: btn_ejecutar.config(state=tk.NORMAL))
            return

        df.fillna("", inplace=True)
        if "EIDOS_ID" not in df.columns:
            df["EIDOS_ID"] = ""
        if "taxonId" not in df.columns:
            df["taxonId"] = ""

        if col_busqueda not in df.columns and tipo_busqueda not in df.columns:
            root_window.after(0, lambda: modal.cerrar())
            root_window.after(0, lambda: messagebox.showerror("Error", "Las columnas seleccionadas no existen en el archivo."))
            root_window.after(0, lambda: btn_ejecutar.config(state=tk.NORMAL))
            return

        total_filas = len(df)
        completados = [0]
        
        root_window.after(0, lambda: [
            progress_bar.config(maximum=total_filas, value=0),
            modal.actualizar(0, total_filas, f"0 de {total_filas} registros procesados")
        ])

        lista_nombres, lista_info, lista_cons, lista_col, lista_legal, lista_bib, lista_sin = [], [], [], [], [], [], []
        headers_cons_guardado, headers_col_guardado, headers_legal_guardado, headers_bib_guardado = [], [], [], []

        filas_pendientes = list(df.iterrows())

        for intento in range(2):
            if not filas_pendientes:
                break
            if intento > 0:
                root_window.after(0, lambda: [
                    lbl_progreso.config(text=f"Reintentando {len(filas_pendientes)} registros pendientes..."),
                    modal.actualizar(completados[0], total_filas, f"Reintentando {len(filas_pendientes)} registros pendientes...")
                ])

            futures_map = {}
            max_w = 8 if intento == 0 else 1
            with ThreadPoolExecutor(max_workers=max_w) as executor:
                for idx, row in filas_pendientes:
                    futures_map[executor.submit(procesar_fila, row, col_busqueda, tipo_busqueda)] = (idx, row)

                filas_pendientes = []
                for future in as_completed(futures_map):
                    idx, row = futures_map[future]
                    try:
                        res, e_id = future.result()
                        if res or e_id:
                            if e_id:
                                df.at[idx, "EIDOS_ID"] = e_id
                                df.at[idx, "taxonId"] = f"{BASE_URL}/{e_id}"
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
                        else:
                            filas_pendientes.append((idx, row))
                    except Exception as exc:
                        print(f"Error en fila {idx} (intento {intento+1}): {exc}")
                        filas_pendientes.append((idx, row))

                    completados[0] += 1
                    prog = min(completados[0], total_filas)
                    por = int((prog / total_filas) * 100) if total_filas > 0 else 100
                    txt_estado = f"Procesando registros: {prog}/{total_filas} ({por}%)"
                    
                    root_window.after(0, lambda p=prog, tf=total_filas, msg=txt_estado: [
                        progress_bar.config(value=p),
                        lbl_progreso.config(text=msg),
                        modal.actualizar(p, tf, msg)
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

        df_coord_mem = pd.DataFrame(columns=COLUMNAS_COORD)
        geojson_mem = {"type": "FeatureCollection", "features": []}
        df_estado_mem = pd.DataFrame(columns=COLUMNAS_ESTADO)

        if incluir_cartografia:
            root_window.after(0, lambda: [
                lbl_progreso.config(text="Descargando cartografía WFS..."),
                modal.actualizar(0, len(df["EIDOS_ID"].tolist()), "Descargando cartografía WFS...")
            ])
            def progreso_carto(n, total):
                txt_c = f"Cartografía: {n}/{total} taxones descargados"
                root_window.after(0, lambda n=n, total=total, t=txt_c: [
                    progress_bar.config(maximum=max(total, 1), value=n),
                    lbl_progreso.config(text=t),
                    modal.actualizar(n, total, t)
                ])
            
            df_coord_mem, geojson_mem, df_estado_mem = recopilar_coordenadas(
                df["EIDOS_ID"].tolist(), progreso_carto
            )
            nombre_base = os.path.splitext(os.path.basename(ruta_csv))[0]
            try:
                guardar_cartografia(
                    df_coord_mem, geojson_mem, df_estado_mem, dir_salida, nombre_base
                )
            except Exception as exc:
                root_window.after(0, lambda error=str(exc): messagebox.showwarning(
                    "Cartografía sin guardar",
                    f"Los datos siguen en memoria. Intenta exportarlos desde el visor.\n{error}",
                ))

        df_taxones_mem = df
        df_nombres_mem = pd.DataFrame(lista_nombres, columns=["EIDOS_ID", "taxonId", "scientificName", "idioma", "pais", "nombre"])
        df_info_mem = pd.DataFrame(lista_info)
        df_cons_mem = crear_df_seguro(lista_cons, headers_cons_guardado)
        df_col_mem = crear_df_seguro(lista_col, headers_col_guardado)
        df_legal_mem = crear_df_seguro(lista_legal, headers_legal_guardado)
        df_bib_mem = crear_df_seguro(lista_bib, headers_bib_guardado)
        df_sin_mem = pd.DataFrame(lista_sin, columns=["EIDOS_ID", "taxonId", "Sinonimo_EIDOS_ID", "Sinonimo_taxonId", "Nombre_Sinonimo"])

        root_window.after(0, lambda: [
            modal.cerrar(),
            btn_ejecutar.config(state=tk.NORMAL),
            progress_bar.config(value=0),
            lbl_progreso.config(text="¡Proceso finalizado! Abriendo visor..."),
            callback_fin(
                df_taxones_mem, df_nombres_mem, df_info_mem, df_cons_mem,
                df_col_mem, df_legal_mem, df_bib_mem, df_sin_mem,
                dir_salida, ruta_csv, root_window,
                df_coord=df_coord_mem, geojson=geojson_mem, df_estado=df_estado_mem,
            )
        ])

    threading.Thread(target=proceso, daemon=True).start()


def abrir_visor_access(df_input, df_output, df_inf, df_con, df_collec, df_leg, df_bi, df_si, dir_salida, ruta_csv, root_main, df_coord=None, geojson=None, df_estado=None):
    df_coord = df_coord if df_coord is not None else pd.DataFrame(columns=COLUMNAS_COORD)
    df_estado = df_estado if df_estado is not None else pd.DataFrame(columns=COLUMNAS_ESTADO)
    geojson = geojson if geojson is not None else {"type": "FeatureCollection", "features": []}
    
    hay_cartografia = not df_coord.empty or not df_estado.empty

    visor = tk.Toplevel(root_main)
    visor.title("Visor Ampliado - Estilo Formulario Access")
    ancho = min(1400, max(1000, visor.winfo_screenwidth() - 60))
    alto = min(780, max(650, visor.winfo_screenheight() - 80))
    visor.geometry(f"{ancho}x{alto}")
    visor.minsize(1000, 650)

    total_registros = len(df_input)
    current_idx = {"val": 0}
    url_ficha_actual = {"link": ""}

    frame_main = tk.Frame(visor)
    frame_main.pack(fill="both", expand=True, padx=10, pady=10)

    frame_left = tk.LabelFrame(frame_main, text=" Ficha de Especie (Entrada) ", font=("Segoe UI", 10, "bold"), padx=10, pady=10, width=350, bg="white")
    frame_left.pack(side="left", fill="both", expand=False, padx=5)
    frame_left.pack_propagate(False)

    canvas_left = tk.Canvas(frame_left, borderwidth=0, highlightthickness=0, bg="white")
    scrollbar_left = ttk.Scrollbar(frame_left, orient="vertical", command=canvas_left.yview)
    scrollable_frame_left = tk.Frame(canvas_left, bg="white")
    scrollable_frame_left.bind("<Configure>", lambda e: canvas_left.configure(scrollregion=canvas_left.bbox("all")))
    canvas_left.create_window((0, 0), window=scrollable_frame_left, anchor="nw")
    canvas_left.configure(yscrollcommand=scrollbar_left.set)

    canvas_left.pack(side="left", fill="both", expand=True)
    scrollbar_left.pack(side="right", fill="y")

    labels_left_values = {}
    input_columns = list(df_input.columns)
    for col in input_columns:
        f_row = tk.Frame(scrollable_frame_left, bg="white")
        f_row.pack(fill="x", pady=2)
        
        lbl_k = tk.Label(f_row, text=f"{col}:", font=("Segoe UI", 9, "bold"), bg="white", fg="#444444", anchor="w", width=16)
        lbl_k.pack(side="top", anchor="w")
        
        lbl_v = tk.Label(f_row, text="", font=("Segoe UI", 9), bg="white", fg="#111111", anchor="w", justify="left", wraplength=310)
        lbl_v.pack(side="top", fill="x", expand=True, anchor="w", pady=(0, 4))
        labels_left_values[col] = lbl_v

    frame_right = tk.LabelFrame(frame_main, text=" Datos Extraídos de EIDOS ", font=("Segoe UI", 10, "bold"), padx=5, pady=5)
    frame_right.pack(side="right", fill="both", expand=True, padx=5)

    barra_carto = ttk.Frame(frame_right)
    barra_carto.pack(fill="x", padx=5, pady=2)
    lbl_enlace = tk.Label(barra_carto, text="Abrir ficha en EIDOS", font=("Segoe UI", 9, "underline"), fg="blue", cursor="hand2")
    lbl_enlace.pack(side="left", padx=5, pady=2)
    lbl_carto = ttk.Label(frame_right, text="")
    lbl_carto.pack(fill="x", padx=10, pady=2)

    def ver_mapa():
        if not total_registros:
            return
        fila = df_input.iloc[current_idx["val"]]
        e_id = str(fila.get("EIDOS_ID", "")).strip()
        nombre = str(fila.get("verbatimScientificName", "")).strip()
        if not df_inf.empty and "EIDOS_ID" in df_inf.columns:
            info = df_inf[df_inf["EIDOS_ID"].astype(str) == e_id]
            if not info.empty:
                nombre = str(info.iloc[0].get("scientificName", "")) or nombre
        try:
            mapas_dir = os.path.join(dir_salida, "mapas")
            os.makedirs(mapas_dir, exist_ok=True)
            ruta = generar_mapa(
                e_id, nombre, df_coord, geojson,
                os.path.join(mapas_dir, f"EIDOS_{e_id}.html"),
            )
            modo = abrir_mapa(ruta, f"Distribución EIDOS: {nombre or e_id}")
            if modo == "navegador":
                lbl_carto.config(text="Mapa abierto en el navegador.")
        except Exception as exc:
            messagebox.showerror("Mapa no disponible", str(exc), parent=visor)

    btn_mapa = ttk.Button(barra_carto, text="🌐 Ver mapa", command=ver_mapa, state="disabled")
    btn_mapa.pack(side="right", padx=5)

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
        columnas = list(df_origen.columns) if len(df_origen.columns) else ["EIDOS_ID", "taxonId", "Datos"]
        tree = ttk.Treeview(frame, columns=columnas, show="headings", height=12)
        for c in columnas:
            tree.heading(c, text=str(c))
            tree.column(c, width=130, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree, columnas

    def crear_pestana_vertical_wrap(nombre_tab):
        frame = tk.Frame(notebook, bg="white")
        notebook.add(frame, text=nombre_tab)
        canvas = tk.Canvas(frame, borderwidth=0, highlightthickness=0, background="white")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_f = tk.Frame(canvas, background="white")
        
        scrollable_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window_right = canvas.create_window((0, 0), window=scrollable_f, anchor="nw")
        
        def _on_canvas_configure_right(event):
            canvas.itemconfig(canvas_window_right, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure_right)
        
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scroll.pack(side="right", fill="y")
        return scrollable_f, canvas

    scrollable_frame_info, canvas_info = crear_pestana_vertical_wrap("🔵 Información")
    tree_sin, cols_sin = crear_pestana_tree_desde_df("🟣 Sinonimia", df_si)
    tree_cons, cols_cons = crear_pestana_tree_desde_df("🟢 Conservación", df_con)
    tree_legal, cols_legal = crear_pestana_tree_desde_df("⚖️ Estado Legal", df_leg)
    tree_col, cols_col = crear_pestana_tree_desde_df("📚 Colecciones", df_collec)
    tree_bib, cols_bib = crear_pestana_tree_desde_df("📖 Bibliografía", df_bi)
    tree_nombres, cols_nombres = crear_pestana_tree_desde_df("🏷️ Nombres Comunes", df_output)

    tree_estado, cols_estado = None, []
    tree_coord, cols_coord = None, []
    if hay_cartografia:
        tree_estado, cols_estado = crear_pestana_tree_desde_df("🗺️ Estado cartografía", df_estado)
        tree_coord, cols_coord = crear_pestana_tree_desde_df("📍 Coordenadas", df_coord)

    def ejecutar_refresco_panel():
        """Refresca el panel de datos mostrando una ventana emergente de progreso."""
        if total_registros == 0:
            return

        modal_refresco = VentanaProgresoModal(visor, titulo="Actualizando Vista", mensaje="Cargando los datos del registro...")
        modal_refresco.set_indeterminado(True)

        def actualizar_logica():
            idx = current_idx["val"]
            row = df_input.iloc[idx]

            for col in input_columns:
                val_text = str(row.get(col, ""))
                labels_left_values[col].config(text=val_text if val_text else "-")

            e_id = str(row.get("EIDOS_ID", "")).strip()

            lista_trees = [tree_nombres, tree_cons, tree_col, tree_legal, tree_bib, tree_sin]
            if hay_cartografia:
                lista_trees.extend([tree_estado, tree_coord])

            for t in lista_trees:
                if t:
                    for item in t.get_children():
                        t.delete(item)

            for widget in scrollable_frame_info.winfo_children():
                widget.destroy()

            def poblar_tree(df_target, tree_target, columnas_tree):
                if tree_target and not df_target.empty and e_id and "EIDOS_ID" in df_target.columns:
                    filtrados = df_target[df_target["EIDOS_ID"].astype(str).str.strip() == e_id]
                    for _, r in filtrados.iterrows():
                        vals = [r.get(c, "") for c in columnas_tree]
                        tree_target.insert("", "end", values=vals)

            poblar_tree(df_output, tree_nombres, cols_nombres)
            
            puntos = df_coord[df_coord["taxonId"].astype(str) == e_id] if not df_coord.empty else pd.DataFrame()
            if hay_cartografia:
                poblar_tree(df_estado, tree_estado, cols_estado)
                for _, punto in puntos.iterrows():
                    tree_coord.insert("", "end", values=[
                        f"{punto[c]:.8f}" if c in ("latdecimal", "longdecimal") else punto[c]
                        for c in cols_coord
                    ])
            
            if not puntos.empty:
                btn_mapa.config(state="normal")
                lbl_carto.config(text=f"🌐 {len(puntos)} cuadrículas encontradas. Coordenadas WGS84 de sus centros.")
            else:
                btn_mapa.config(state="disabled")
                estado = df_estado[df_estado["EIDOS_ID"].astype(str) == e_id] if not df_estado.empty else pd.DataFrame()
                if not estado.empty and estado.iloc[0]["estado"] == "error":
                    lbl_carto.config(text="⚠️ Error de consulta WFS. Consulta la pestaña 'Estado cartografía'.")
                elif not estado.empty:
                    lbl_carto.config(text="Sin cuadrículas de distribución registradas para este taxón.")
                else:
                    lbl_carto.config(text="Cartografía no descargada o sin datos.")

            if not df_inf.empty and e_id and "EIDOS_ID" in df_inf.columns:
                match_info = df_inf[df_inf["EIDOS_ID"].astype(str).str.strip() == e_id]
                if not match_info.empty:
                    r_inf = match_info.iloc[0]
                    anchura_canvas = canvas_info.winfo_width()
                    wrap_val = max(anchura_canvas - 180, 300)

                    for k, v in r_inf.items():
                        if k != "EIDOS_ID" and str(v).strip():
                            f_item = tk.Frame(scrollable_frame_info, bg="white")
                            f_item.pack(fill="x", pady=3, padx=2)
                            
                            lbl_k = tk.Label(f_item, text=f"{k}:", font=("Segoe UI", 9, "bold"), bg="white", fg="#333333", anchor="w", width=18)
                            lbl_k.pack(side="left", anchor="n")
                            
                            lbl_v = tk.Label(f_item, text=str(v), font=("Segoe UI", 9), bg="white", fg="#111111", anchor="w", justify="left", wraplength=wrap_val)
                            lbl_v.pack(side="left", fill="x", expand=True, anchor="w")

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
                lbl_enlace.config(text="🔗 Ficha de EIDOS no disponible", fg="gray")

            lbl_estado.config(text=f"Registro {idx + 1} de {total_registros}")
            entry_ir.delete(0, tk.END)
            entry_ir.insert(0, str(idx + 1))

            modal_refresco.cerrar()

        visor.after(50, actualizar_logica)

    actualizar_vista = ejecutar_refresco_panel

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

    exportado_realizado = {"val": False}

    def exportar_todo_en_directorio():
        if not os.path.exists(dir_salida):
            os.makedirs(dir_salida, exist_ok=True)

        try:
            if ruta_csv and os.path.exists(ruta_csv):
                nombre_archivo_original = os.path.basename(ruta_csv)
                ruta_copia_entrada = os.path.join(dir_salida, f"copia_{nombre_archivo_original}")
                shutil.copy2(ruta_csv, ruta_copia_entrada)
        except Exception as ex:
            print(f"Aviso al copiar el archivo original: {ex}")

        nombre_base = os.path.splitext(os.path.basename(ruta_csv))[0] if ruta_csv else "resultado"
        f_taxones = os.path.join(dir_salida, f"{nombre_base}_taxonesEIDOS.csv")
        f_nombres = os.path.join(dir_salida, f"{nombre_base}_NombreComunes.csv")
        f_info = os.path.join(dir_salida, f"{nombre_base}_Informacion.csv")
        f_cons = os.path.join(dir_salida, f"{nombre_base}_EstadoConservacion.csv")
        f_col = os.path.join(dir_salida, f"{nombre_base}_ColeccionesCatalogos.csv")
        f_legal = os.path.join(dir_salida, f"{nombre_base}_EstadoLegal.csv")
        f_bib = os.path.join(dir_salida, f"{nombre_base}_Bibliografia.csv")
        f_sin = os.path.join(dir_salida, f"{nombre_base}_Sinonimia.csv")

        f_excel = os.path.join(dir_salida, f"{nombre_base}_exportacion_Access.xlsx")
        f_db = os.path.join(dir_salida, f"{nombre_base}_EIDOS.db")
        
        try:
            enc_csv = detectar_codificacion(ruta_csv) if ruta_csv else "utf-8"
            sep_csv = detectar_dialect(ruta_csv).delimiter if ruta_csv else ","

            df_input.to_csv(f_taxones, sep=sep_csv, index=False, encoding=enc_csv)
            df_output.to_csv(f_nombres, index=False, encoding="utf-8")
            df_inf.to_csv(f_info, index=False, encoding="utf-8")
            df_con.to_csv(f_cons, index=False, encoding="utf-8")
            df_collec.to_csv(f_col, index=False, encoding="utf-8")
            df_leg.to_csv(f_legal, index=False, encoding="utf-8")
            df_bi.to_csv(f_bib, index=False, encoding="utf-8")
            df_sin.to_csv(f_sin, index=False, encoding="utf-8")
            
            if hay_cartografia:
                guardar_cartografia(
                    df_coord, geojson, df_estado, dir_salida, nombre_base
                )

            with pd.ExcelWriter(f_excel, engine="openpyxl") as writer:
                if not df_input.empty: df_input.to_excel(writer, sheet_name="taxones", index=False)
                if not df_output.empty: df_output.to_excel(writer, sheet_name="Resultados_NombresComunes", index=False)
                if not df_inf.empty: df_inf.to_excel(writer, sheet_name="Informacion", index=False)
                if not df_con.empty: df_con.to_excel(writer, sheet_name="EstadoConservacion", index=False)
                if not df_collec.empty: df_collec.to_excel(writer, sheet_name="ColeccionesCatalogos", index=False)
                if not df_leg.empty: df_leg.to_excel(writer, sheet_name="EstadoLegal", index=False)
                if not df_bi.empty: df_bi.to_excel(writer, sheet_name="Bibliografia", index=False)
                if not df_sin.empty: df_sin.to_excel(writer, sheet_name="Sinonimia", index=False)
                if hay_cartografia:
                    df_coord.to_excel(writer, sheet_name="Coordenadas", index=False)
                    df_estado.to_excel(writer, sheet_name="EstadoCartografia", index=False)

            conn = sqlite3.connect(f_db)
            if not df_input.empty: df_input.to_sql("taxones", conn, if_exists="replace", index=False)
            if not df_output.empty: df_output.to_sql("NombresComunes", conn, if_exists="replace", index=False)
            if not df_inf.empty: df_inf.to_sql("Informacion", conn, if_exists="replace", index=False)
            if not df_con.empty: df_con.to_sql("EstadoConservacion", conn, if_exists="replace", index=False)
            if not df_collec.empty: df_collec.to_sql("ColeccionesCatalogos", conn, if_exists="replace", index=False)
            if not df_leg.empty: df_leg.to_sql("EstadoLegal", conn, if_exists="replace", index=False)
            if not df_bi.empty: df_bi.to_sql("Bibliografia", conn, if_exists="replace", index=False)
            if not df_si.empty: df_si.to_sql("Sinonimia", conn, if_exists="replace", index=False)
            if hay_cartografia:
                df_coord.to_sql("Coordenadas", conn, if_exists="replace", index=False)
                df_estado.to_sql("EstadoCartografia", conn, if_exists="replace", index=False)
            conn.close()

            exportado_realizado["val"] = True

            messagebox.showinfo(
                "Éxito", 
                f"Exportación completada correctamente en:\n{dir_salida}\n\n"
                f"• Archivos CSV generados\n"
                f"• Excel y SQLite generados con éxito."
            )
            abrir_archivo_sistema(dir_salida)
            visor.destroy()
            root_main.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo completar la exportación:\n{e}")

    tk.Button(frame_nav, text="Exportar (Excel + SQLite DB)", command=exportar_todo_en_directorio, bg="#217346", fg="white", font=("Segoe UI", 9, "bold")).pack(side="right", padx=5)

    def al_cerrar_visor():
        if not exportado_realizado["val"]:
            respuesta = messagebox.askyesnocancel(
                "Cerrar visor",
                "¿Quieres exportar todos los resultados antes de cerrar?\n\n"
                "Las coordenadas y el GeoJSON se guardan automáticamente al terminar.",
                parent=visor,
            )
            if respuesta is None:
                return
            if respuesta:
                exportar_todo_en_directorio()
                return
        visor.destroy()
        root_main.destroy()

    visor.protocol("WM_DELETE_WINDOW", al_cerrar_visor)
    actualizar_vista()