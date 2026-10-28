import csv
import os
import io
import requests
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageTk
import cairosvg

from logo_svg import LOGO_SVG


COLOR_VERDE = "#289530"
COLOR_GRIS_OSCURO = "#333333"
COLOR_GRIS_CLARO = "#EEEEEE"
COLOR_BOTON = "#289530"
COLOR_BOTON_TEXTO = "#FFFFFF"


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


def escribir_csv(ruta, filas, encoding_salida):
    with open(ruta, "w", newline="", encoding=encoding_salida) as f:
        writer = csv.writer(
            f, delimiter="\t", quotechar='"',
            quoting=csv.QUOTE_ALL, lineterminator="\n"
        )
        for fila in filas:
            writer.writerow(fila)


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

    return {"status": "OK", "match": match_json, "species": species_json}

def procesar_csv_async(ruta_csv, col_id_pos, col_name_pos,
                       carpeta_salida, modo_salida, encoding_salida,
                       progreso_var, progreso_label, root):

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

                elif resultado["status"] == "ERROR":
                    fila_busqueda["comparacion"] = "ERROR"
                    fila_busqueda["error"] = resultado["error"]
                    tabla_busqueda.append(fila_busqueda)

                else:
                    match_json = resultado["match"]
                    species_json = resultado["species"]

                    nombre_gbif = species_json.get("scientificName", "")
                    fila_busqueda["comparacion"] = (
                        "IGUAL" if nombre.lower() == nombre_gbif.lower() else "DIFERENTE"
                    )
                    tabla_busqueda.append(fila_busqueda)

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

                completados += 1
                progreso = int((completados / total) * 100)
                root.after(0, lambda p=progreso: progreso_var.set(p))
                root.after(0, lambda p=progreso: progreso_label.config(text=f"Progreso: {p}%"))

            base = os.path.splitext(os.path.basename(ruta_csv))[0]

            if modo_salida == "Una tabla":
                columnas = sorted(columnas_busqueda | columnas_match | columnas_species)
                filas = [columnas]

                for fila in tabla_busqueda:
                    fila_completa = fila.copy()

                    for fm in tabla_match:
                        if fm["taxonID"] == fila["taxonID"]:
                            fila_completa.update(fm)

                    for fs in tabla_species:
                        if fs["taxonID"] == fila["taxonID"]:
                            fila_completa.update(fs)

                    filas.append([fila_completa.get(c, "") for c in columnas])

                ruta_salida = os.path.join(carpeta_salida, f"{base}_{encoding_salida}.tsv")
                escribir_csv(ruta_salida, filas, encoding_salida)

                root.after(0, lambda: messagebox.showinfo("Éxito", f"Generado:\n{ruta_salida}"))

            else:
                ruta_busqueda = os.path.join(carpeta_salida, f"{base}_{encoding_salida}_Busqueda.tsv")
                ruta_match = os.path.join(carpeta_salida, f"{base}_{encoding_salida}_Encontrado.tsv")
                ruta_species = os.path.join(carpeta_salida, f"{base}_{encoding_salida}_Taxon.tsv")

                escribir_csv(
                    ruta_busqueda,
                    [list(columnas_busqueda)] +
                    [[fila.get(c, "") for c in columnas_busqueda] for fila in tabla_busqueda],
                    encoding_salida
                )

                escribir_csv(
                    ruta_match,
                    [list(columnas_match)] +
                    [[fila.get(c, "") for c in columnas_match] for fila in tabla_match],
                    encoding_salida
                )

                escribir_csv(
                    ruta_species,
                    [list(columnas_species)] +
                    [[fila.get(c, "") for c in columnas_species] for fila in tabla_species],
                    encoding_salida
                )

                root.after(0, lambda: messagebox.showinfo(
                    "Éxito",
                    f"Generados:\n{ruta_busqueda}\n{ruta_match}\n{ruta_species}"
                ))

        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))

    threading.Thread(target=tarea).start()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GBIF.ES — Búsqueda taxonómica")
        self.geometry("800x500")
        self.configure(bg=COLOR_GRIS_CLARO)

        self.ruta_csv = None
        self.carpeta_salida = None

        self.col_id = tk.StringVar()
        self.col_name = tk.StringVar()
        self.encoding_var = tk.StringVar(value="utf-8")
        self.modo_var = tk.StringVar(value="Tres tablas")
        self.progreso_var = tk.IntVar()

        self.logo_img = None
        self._cargar_logo_svg()

        self.frame_actual = None
        self._crear_pantalla_presentacion()

    def _cargar_logo_svg(self):
        try:
            png_bytes = cairosvg.svg2png(bytestring=LOGO_SVG.encode("utf-8"))
            img = Image.open(io.BytesIO(png_bytes))
            img = img.resize((260, 100), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
        except Exception as e:
            print("Error cargando SVG:", e)
            self.logo_img = None

    def _limpiar_frame(self):
        if self.frame_actual is not None:
            self.frame_actual.destroy()
            self.frame_actual = None

    def _crear_pantalla_presentacion(self):
        self._limpiar_frame()
        f = tk.Frame(self, bg=COLOR_VERDE)
        f.pack(fill="both", expand=True)
        self.frame_actual = f

        if self.logo_img:
            tk.Label(f, image=self.logo_img, bg=COLOR_VERDE).pack(pady=40)
        else:
            tk.Label(f, text="GBIF.ES", bg=COLOR_VERDE,
                     fg="white", font=("Arial", 28, "bold")).pack(pady=40)

        tk.Label(
            f,
            text="Herramienta de búsqueda taxonómica\nbasada en la API de GBIF",
            bg=COLOR_VERDE,
            fg="white",
            font=("Arial", 14)
        ).pack(pady=10)

        tk.Button(
            f,
            text="Entrar",
            command=self._crear_pantalla_ejecucion,
            bg=COLOR_BOTON,
            fg=COLOR_BOTON_TEXTO,
            font=("Arial", 14, "bold"),
            padx=20, pady=10
        ).pack(pady=30)

        tk.Button(
            f,
            text="Ayuda",
            command=self._crear_pantalla_ayuda,
            bg="#FFFFFF",
            fg=COLOR_VERDE,
            font=("Arial", 11),
            padx=10, pady=5
        ).pack(pady=5)

    def _crear_pantalla_ejecucion(self):
        self._limpiar_frame()
        f = tk.Frame(self, bg=COLOR_GRIS_CLARO)
        f.pack(fill="both", expand=True)
        self.frame_actual = f

        tk.Label(
            f, text="Búsqueda taxonómica en GBIF",
            bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        frame_file = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_file.pack(pady=5)
        tk.Label(frame_file, text="Archivo CSV/TSV de entrada:",
                 bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                 font=("Arial", 11)).grid(row=0, column=0, sticky="w")
        tk.Button(frame_file, text="Seleccionar archivo",
                  command=self._seleccionar_csv).grid(row=0, column=1, padx=10)
        self.label_csv = tk.Label(frame_file, text="(ningún archivo seleccionado)",
                                  bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                                  font=("Arial", 9))
        self.label_csv.grid(row=1, column=0, columnspan=2, sticky="w", pady=3)

        frame_cols = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_cols.pack(pady=10)
        tk.Label(frame_cols, text="Columna taxonID:",
                 bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                 font=("Arial", 10)).grid(row=0, column=0, sticky="e")
        tk.Entry(frame_cols, textvariable=self.col_id, width=8).grid(row=0, column=1, padx=5)

        tk.Label(frame_cols, text="Columna scientificName:",
                 bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                 font=("Arial", 10)).grid(row=1, column=0, sticky="e")
        tk.Entry(frame_cols, textvariable=self.col_name, width=8).grid(row=1, column=1, padx=5)

        frame_opts = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_opts.pack(pady=10)

        tk.Label(frame_opts, text="Codificación salida:",
                 bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                 font=("Arial", 10)).grid(row=0, column=0, sticky="e")
        ttk.Combobox(frame_opts, textvariable=self.encoding_var,
                     values=["utf-8", "utf-8-sig", "latin-1", "cp1252", "utf-7"],
                     width=12).grid(row=0, column=1, padx=5)

        tk.Label(frame_opts, text="Modo salida:",
                 bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                 font=("Arial", 10)).grid(row=1, column=0, sticky="e")
        ttk.Combobox(frame_opts, textvariable=self.modo_var,
                     values=["Una tabla", "Tres tablas"],
                     width=12).grid(row=1, column=1, padx=5)

        frame_out = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_out.pack(pady=10)
        tk.Label(frame_out, text="Carpeta de salida:",
                 bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                 font=("Arial", 11)).grid(row=0, column=0, sticky="w")
        tk.Button(frame_out, text="Seleccionar carpeta",
                  command=self._seleccionar_carpeta).grid(row=0, column=1, padx=10)
        self.label_salida = tk.Label(frame_out, text="(ninguna carpeta seleccionada)",
                                     bg=COLOR_GRIS_CLARO, fg=COLOR_GRIS_OSCURO,
                                     font=("Arial", 9))
        self.label_salida.grid(row=1, column=0, columnspan=2, sticky="w", pady=3)

        self.progreso_label = tk.Label(
            f, text="Progreso: 0%", bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO, font=("Arial", 11)
        )
        self.progreso_label.pack(pady=10)

        frame_btn = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_btn.pack(pady=15)

        tk.Button(
            frame_btn,
            text="Ejecutar búsqueda en GBIF",
            command=self._ejecutar,
            bg=COLOR_BOTON,
            fg=COLOR_BOTON_TEXTO,
            font=("Arial", 13, "bold"),
            padx=20, pady=8
        ).grid(row=0, column=0, padx=10)

        tk.Button(
            frame_btn,
            text="Ayuda",
            command=self._crear_pantalla_ayuda,
            bg="#FFFFFF",
            fg=COLOR_VERDE,
            font=("Arial", 10),
            padx=10, pady=5
        ).grid(row=0, column=1, padx=10)

        tk.Button(
            frame_btn,
            text="Inicio",
            command=self._crear_pantalla_presentacion,
            bg="#FFFFFF",
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
            padx=10, pady=5
        ).grid(row=0, column=2, padx=10)

    def _crear_pantalla_ayuda(self):
        self._limpiar_frame()
        f = tk.Frame(self, bg="#FFFFFF")
        f.pack(fill="both", expand=True)
        self.frame_actual = f

        tk.Label(
            f, text="Ayuda — GBIF.ES Búsqueda taxonómica",
            bg="#FFFFFF", fg=COLOR_GRIS_OSCURO,
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        texto = (
            "Esta herramienta realiza búsquedas taxonómicas en la API de GBIF.\n\n"
            "1. Selecciona un archivo CSV/TSV de entrada.\n"
            "2. Indica el número de columna donde está taxonID.\n"
            "3. Indica el número de columna donde está scientificName.\n"
            "4. Elige la codificación de salida y el modo (una tabla o tres tablas).\n"
            "5. Selecciona la carpeta de salida.\n"
            "6. Pulsa 'Ejecutar búsqueda en GBIF' y espera a que termine.\n\n"
            "Los resultados se guardarán en ficheros TSV en la carpeta indicada."
        )

        tk.Label(
            f, text=texto,
            bg="#FFFFFF", fg=COLOR_GRIS_OSCURO,
            font=("Arial", 11), justify="left"
        ).pack(padx=20, pady=10, anchor="w")

        tk.Button(
            f,
            text="Volver al inicio",
            command=self._crear_pantalla_presentacion,
            bg="#FFFFFF",
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
            padx=10, pady=5
        ).pack(pady=10)

    def _seleccionar_csv(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo CSV/TSV",
            filetypes=[("CSV/TSV", "*.csv *.tsv *.txt"), ("Todos", "*.*")]
        )
        if ruta:
            self.ruta_csv = ruta
            self.label_csv.config(text=ruta)

    def _seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if carpeta:
            self.carpeta_salida = carpeta
            self.label_salida.config(text=carpeta)

    def _ejecutar(self):
        if not self.ruta_csv:
            messagebox.showwarning("Falta archivo", "Selecciona un archivo de entrada.")
            return
        if not self.carpeta_salida:
            self.carpeta_salida = os.path.dirname(self.ruta_csv)
            self.label_salida.config(text=self.carpeta_salida)

        try:
            col_id_pos = int(self.col_id.get())
            col_name_pos = int(self.col_name.get())
        except ValueError:
            messagebox.showerror("Error", "Las columnas deben ser números.")
            return

        procesar_csv_async(
            self.ruta_csv,
            col_id_pos,
            col_name_pos,
            self.carpeta_salida,
            self.modo_var.get(),
            self.encoding_var.get(),
            self.progreso_var,
            self.progreso_label,
            self
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()