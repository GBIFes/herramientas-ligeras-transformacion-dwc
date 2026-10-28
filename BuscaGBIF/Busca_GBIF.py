import csv
import os
import requests
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# DETECCIÓN DE CODIFICACIÓN
# ============================================================

def detectar_codificacion(ruta):
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(ruta, "r", encoding=enc) as f:
                f.read(2048)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def leer_csv_codificado(ruta):
    encoding = detectar_codificacion(ruta)

    with open(ruta, "r", encoding=encoding, errors="replace") as f:
        sample = f.read(2048)
        f.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        delimiter = dialect.delimiter

        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        raise Exception("El CSV está vacío.")

    return rows, len(rows[0])


def escribir_csv_salida(ruta_salida, filas):
    with open(ruta_salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(
            f,
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\n"
        )
        for fila in filas:
            writer.writerow(fila)


# ============================================================
# CONSULTA GBIF
# ============================================================

GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_SPECIES_URL = "https://api.gbif.org/v1/species/{}"

session = requests.Session()
session.headers.update({"User-Agent": "Javier-GBIF-Tool"})


def buscar_en_gbif(nombre):
    try:
        r = session.get(GBIF_MATCH_URL, params={"name": nombre}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"status": "ERROR", "error": f"match: {type(e).__name__}: {e}"}

    usageKey = data.get("usageKey")
    if not usageKey:
        return {"status": "NO_MATCH"}

    try:
        r2 = session.get(GBIF_SPECIES_URL.format(usageKey), timeout=10)
        r2.raise_for_status()
        sp = r2.json()
    except Exception as e:
        return {"status": "ERROR", "error": f"species: {type(e).__name__}: {e}"}

    return {
        "status": "OK",
        "match": data,
        "species": sp
    }


# ============================================================
# JSON → FILA TABULAR
# ============================================================

def json_a_fila(taxonID, nombre_original, resultado):
    fila = {
        "taxonID": taxonID,
        "scientificName_original": nombre_original,
    }

    if resultado["status"] == "NO_MATCH":
        fila["comparacion"] = "NO_ENCONTRADO"
        return fila

    if resultado["status"] == "ERROR":
        fila["comparacion"] = "ERROR"
        fila["error"] = resultado["error"]
        return fila

    match_json = resultado["match"]
    species_json = resultado["species"]

    # Nombre aceptado en GBIF
    nombre_gbif = species_json.get("scientificName", "")
    fila["scientificName_GBIF"] = nombre_gbif

    # Comparación
    if nombre_original.lower() == nombre_gbif.lower():
        fila["comparacion"] = "IGUAL"
    else:
        fila["comparacion"] = "DIFERENTE"

    # Añadir todas las claves de match_*
    for k, v in match_json.items():
        fila[f"match_{k}"] = v

    # Añadir todas las claves de species_*
    for k, v in species_json.items():
        fila[f"species_{k}"] = v

    return fila


# ============================================================
# PROCESAR CSV EN HILO SEPARADO
# ============================================================

def procesar_csv_async(ruta_csv, col_id_pos, col_name_pos, ruta_salida,
                       progreso_var, progreso_label, log_text, root):

    def tarea():
        try:
            rows, num_cols = leer_csv_codificado(ruta_csv)

            idx_id = col_id_pos - 1
            idx_name = col_name_pos - 1

            salida_filas = []
            columnas_set = set()

            executor = ThreadPoolExecutor(max_workers=5)

            tareas = []
            for row in rows[1:]:
                if len(row) < num_cols:
                    continue
                taxon_id = row[idx_id].strip()
                nombre = row[idx_name].strip()
                tareas.append((taxon_id, nombre, executor.submit(buscar_en_gbif, nombre)))

            total = len(tareas)
            progreso_var.set(0)
            completados = 0

            for taxon_id, nombre, future in tareas:
                resultado = future.result()
                fila = json_a_fila(taxon_id, nombre, resultado)
                salida_filas.append(fila)
                columnas_set.update(fila.keys())

                # Log
                if resultado["status"] == "OK":
                    texto = f"{taxon_id}: {nombre} → {fila.get('scientificName_GBIF','')} ({fila.get('species_key','')}) [{fila['comparacion']}]\n"
                elif resultado["status"] == "NO_MATCH":
                    texto = f"{taxon_id}: {nombre} → NO ENCONTRADO\n"
                else:
                    texto = f"{taxon_id}: {nombre} → ERROR ({resultado['error']})\n"

                root.after(0, lambda t=texto: log_text.insert(tk.END, t))

                completados += 1
                progreso = int((completados / total) * 100)
                root.after(0, lambda p=progreso: progreso_var.set(p))
                root.after(0, lambda p=progreso: progreso_label.config(text=f"Progreso: {p}%"))

            # Orden de columnas: primero entrada + comparación, luego todo lo demás
            columnas_extra = sorted(
                c for c in columnas_set
                if c not in ("taxonID", "scientificName_original", "comparacion")
            )
            columnas = ["taxonID", "scientificName_original", "comparacion"] + columnas_extra

            filas_finales = [columnas]
            for fila in salida_filas:
                filas_finales.append([fila.get(c, "") for c in columnas])

            escribir_csv_salida(ruta_salida, filas_finales)

            root.after(0, lambda: messagebox.showinfo("Éxito", f"Archivo generado:\n{ruta_salida}"))

        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

    threading.Thread(target=tarea).start()


# ============================================================
# GUI TKINTER
# ============================================================

def main():
    root = tk.Tk()
    root.title("GBIF masivo (taxonID + scientificName + comparación + JSON)")
    root.geometry("900x650")

    ruta_csv = {"path": None}
    ruta_salida = {"path": None}

    col_id = tk.StringVar()
    col_name = tk.StringVar()

    progreso_var = tk.IntVar()

    tk.Label(root, text="Selecciona archivo CSV/TSV de entrada:", font=("Arial", 11)).pack(pady=5)
    tk.Button(root, text="Seleccionar archivo", command=lambda: seleccionar_csv()).pack()

    label_csv = tk.Label(root, text="(ningún archivo seleccionado)", font=("Arial", 9))
    label_csv.pack(pady=5)

    frame_cols = tk.Frame(root)
    frame_cols.pack(pady=10)

    tk.Label(frame_cols, text="Columna taxonID:", font=("Arial", 10)).grid(row=0, column=0, sticky="e")
    tk.Entry(frame_cols, textvariable=col_id, width=10).grid(row=0, column=1)

    tk.Label(frame_cols, text="Columna scientificName:", font=("Arial", 10)).grid(row=1, column=0, sticky="e")
    tk.Entry(frame_cols, textvariable=col_name, width=10).grid(row=1, column=1)

    tk.Label(root, text="Archivo de salida (UTF-8, TAB):", font=("Arial", 11)).pack(pady=5)
    tk.Button(root, text="Seleccionar archivo de salida", command=lambda: seleccionar_salida()).pack()

    label_salida = tk.Label(root, text="(archivo de salida sugerido)", font=("Arial", 9))
    label_salida.pack(pady=5)

    progreso_label = tk.Label(root, text="Progreso: 0%", font=("Arial", 10))
    progreso_label.pack(pady=10)

    tk.Label(root, text="Log de búsqueda:", font=("Arial", 11)).pack()
    log_text = tk.Text(root, height=20, width=110)
    log_text.pack(pady=10)

    def seleccionar_csv():
        f = filedialog.askopenfilename(
            title="Selecciona CSV de entrada",
            filetypes=[("CSV files", "*.csv"), ("TSV files", "*.tsv"), ("Todos", "*.*")]
        )
        if not f:
            return
        ruta_csv["path"] = f
        label_csv.config(text=f)

        base = os.path.splitext(os.path.basename(f))[0]
        sugerido = os.path.join(os.path.dirname(f), base + "_GBIF_FULL.tsv")
        ruta_salida["path"] = sugerido
        label_salida.config(text=sugerido)

    def seleccionar_salida():
        if not ruta_csv["path"]:
            messagebox.showerror("Error", "Primero selecciona el CSV de entrada.")
            return

        base = os.path.splitext(os.path.basename(ruta_csv["path"]))[0]

        f = filedialog.asksaveasfilename(
            title="Selecciona archivo de salida",
            defaultextension=".tsv",
            initialdir=os.path.dirname(ruta_csv["path"]),
            initialfile=base + "_GBIF_FULL.tsv",
            filetypes=[("TSV files", "*.tsv"), ("CSV files", "*.csv"), ("Todos", "*.*")]
        )
        if not f:
            return

        ruta_salida["path"] = f
        label_salida.config(text=f)

    def ejecutar():
        try:
            if not ruta_csv["path"]:
                messagebox.showerror("Error", "No se ha seleccionado CSV de entrada.")
                return
            if not ruta_salida["path"]:
                messagebox.showerror("Error", "No se ha definido archivo de salida.")
                return

            colid = int(col_id.get().strip())
            colname = int(col_name.get().strip())

            progreso_var.set(0)
            progreso_label.config(text="Progreso: 0%")
            log_text.delete("1.0", tk.END)

            procesar_csv_async(
                ruta_csv["path"],
                colid,
                colname,
                ruta_salida["path"],
                progreso_var,
                progreso_label,
                log_text,
                root
            )

        except ValueError:
            messagebox.showerror("Error", "Las columnas deben ser números enteros (1,2,3...).")
        except Exception as e:
            messagebox.showerror("Error en ejecución", str(e))

    tk.Button(root, text="Ejecutar búsqueda en GBIF", command=ejecutar, font=("Arial", 12)).pack(pady=15)

    root.mainloop()


if __name__ == "__main__":
    main()
