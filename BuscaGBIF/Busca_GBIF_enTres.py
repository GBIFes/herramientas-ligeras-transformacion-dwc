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


def escribir_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
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
        match_json = r.json()
    except Exception as e:
        return {"status": "ERROR", "error": f"match: {e}"}

    usageKey = match_json.get("usageKey")
    if not usageKey:
        return {"status": "NO_MATCH", "match": match_json}

    try:
        r2 = session.get(GBIF_SPECIES_URL.format(usageKey), timeout=10)
        r2.raise_for_status()
        species_json = r2.json()
    except Exception as e:
        return {"status": "ERROR", "error": f"species: {e}", "match": match_json}

    return {
        "status": "OK",
        "match": match_json,
        "species": species_json
    }


# ============================================================
# PROCESAR CSV Y DIVIDIR EN 3 TABLAS
# ============================================================

def procesar_csv_async(ruta_csv, col_id_pos, col_name_pos, carpeta_salida,
                       progreso_var, progreso_label, log_text, root):

    def tarea():
        try:
            rows, num_cols = leer_csv_codificado(ruta_csv)

            idx_id = col_id_pos - 1
            idx_name = col_name_pos - 1

            tabla_busqueda = []
            tabla_match = []
            tabla_species = []

            columnas_busqueda = set(["taxonID", "scientificName_original", "comparacion", "error"])
            columnas_match = set(["taxonID", "scientificName_original"])
            columnas_species = set(["taxonID", "scientificName_original"])

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

                fila_busqueda = {
                    "taxonID": taxon_id,
                    "scientificName_original": nombre,
                    "comparacion": "",
                    "error": ""
                }

                if resultado["status"] == "NO_MATCH":
                    fila_busqueda["comparacion"] = "NO_ENCONTRADO"
                    tabla_busqueda.append(fila_busqueda)
                    texto = f"{taxon_id}: {nombre} → NO ENCONTRADO\n"

                elif resultado["status"] == "ERROR":
                    fila_busqueda["comparacion"] = "ERROR"
                    fila_busqueda["error"] = resultado["error"]
                    tabla_busqueda.append(fila_busqueda)
                    texto = f"{taxon_id}: {nombre} → ERROR ({resultado['error']})\n"

                else:
                    match_json = resultado["match"]
                    species_json = resultado["species"]

                    nombre_gbif = species_json.get("scientificName", "")
                    fila_busqueda["comparacion"] = (
                        "IGUAL" if nombre.lower() == nombre_gbif.lower() else "DIFERENTE"
                    )
                    tabla_busqueda.append(fila_busqueda)

                    texto = f"{taxon_id}: {nombre} → {nombre_gbif}\n"

                    fila_match = {"taxonID": taxon_id, "scientificName_original": nombre}
                    fila_species = {"taxonID": taxon_id, "scientificName_original": nombre}

                    for k, v in match_json.items():
                        columnas_match.add(k.replace("match_", ""))
                        fila_match[k.replace("match_", "")] = v

                    for k, v in species_json.items():
                        columnas_species.add(k.replace("species_", ""))
                        fila_species[k.replace("species_", "")] = v

                    tabla_match.append(fila_match)
                    tabla_species.append(fila_species)

                root.after(0, lambda t=texto: log_text.insert(tk.END, t))

                completados += 1
                progreso = int((completados / total) * 100)
                root.after(0, lambda p=progreso: progreso_var.set(p))
                root.after(0, lambda p=progreso: progreso_label.config(text=f"Progreso: {p}%"))

            # Crear carpetas y archivos
            base = os.path.splitext(os.path.basename(ruta_csv))[0]

            ruta_busqueda = os.path.join(carpeta_salida, base + "_Busqueda.tsv")
            ruta_match = os.path.join(carpeta_salida, base + "_Encontrado.tsv")
            ruta_species = os.path.join(carpeta_salida, base + "_Taxon.tsv")

            # Escribir tablas
            escribir_csv(ruta_busqueda, [list(columnas_busqueda)] +
                         [[fila.get(c, "") for c in columnas_busqueda] for fila in tabla_busqueda])

            escribir_csv(ruta_match, [list(columnas_match)] +
                         [[fila.get(c, "") for c in columnas_match] for fila in tabla_match])

            escribir_csv(ruta_species, [list(columnas_species)] +
                         [[fila.get(c, "") for c in columnas_species] for fila in tabla_species])

            root.after(0, lambda: messagebox.showinfo(
                "Éxito",
                f"Generados:\n{ruta_busqueda}\n{ruta_match}\n{ruta_species}"
            ))

        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

    threading.Thread(target=tarea).start()


# ============================================================
# GUI TKINTER
# ============================================================

def main():
    root = tk.Tk()
    root.title("GBIF → 3 tablas (Búsqueda, Encontrado, Taxon)")
    root.geometry("900x650")

    ruta_csv = {"path": None}
    carpeta_salida = {"path": None}

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

    tk.Label(root, text="Carpeta de salida:", font=("Arial", 11)).pack(pady=5)
    tk.Button(root, text="Seleccionar carpeta", command=lambda: seleccionar_carpeta()).pack()

    label_salida = tk.Label(root, text="(ninguna carpeta seleccionada)", font=("Arial", 9))
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

    def seleccionar_carpeta():
        f = filedialog.askdirectory(title="Selecciona carpeta de salida")
        if not f:
            return
        carpeta_salida["path"] = f
        label_salida.config(text=f)

    def ejecutar():
        try:
            if not ruta_csv["path"]:
                messagebox.showerror("Error", "No se ha seleccionado CSV de entrada.")
                return
            if not carpeta_salida["path"]:
                messagebox.showerror("Error", "No se ha seleccionado carpeta de salida.")
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
                carpeta_salida["path"],
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
