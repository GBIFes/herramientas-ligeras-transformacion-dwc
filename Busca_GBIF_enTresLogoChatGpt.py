import csv
import io
import os
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox, ttk

import requests
from PIL import Image, ImageTk
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Intenta importar cairosvg de forma segura (evita cierres si faltan binarios Cairo)
try:
    import cairosvg
    CAIROSVG_DISPONIBLE = True
except Exception:
    CAIROSVG_DISPONIBLE = False

# Intenta importar el logo externo; si no existe, usa un SVG genérico por defecto
try:
    from logo_svg import LOGO_SVG
except ImportError:
    LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="260" height="100" viewBox="0 0 260 100">
        <rect width="260" height="100" fill="#289530" rx="10"/>
        <text x="130" y="58" font-family="Arial" font-size="28" font-weight="bold" fill="#FFFFFF" text-anchor="middle">GBIF.ES</text>
    </svg>"""


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

COLOR_VERDE = "#289530"
COLOR_GRIS_OSCURO = "#333333"
COLOR_GRIS_CLARO = "#EEEEEE"
COLOR_BOTON = "#289530"
COLOR_BOTON_TEXTO = "#FFFFFF"

GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_SPECIES_URL = "https://api.gbif.org/v1/species/{}"

MAX_WORKERS = 5
REQUEST_TIMEOUT = (5, 30)

ENCODINGS_ENTRADA = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
ENCODINGS_SALIDA = ("utf-8", "utf-8-sig", "cp1252", "latin-1", "utf-7")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def crear_session():
    """Crea una Session con reintentos para errores HTTP/transitorios."""
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=MAX_WORKERS,
        pool_maxsize=MAX_WORKERS,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "GBIF-ES-Tool/2.0",
        "Accept": "application/json",
    })
    return session


_thread_local = threading.local()


def obtener_session():
    """Una Session por hilo: evita compartir una Session entre hilos."""
    if not hasattr(_thread_local, "session"):
        _thread_local.session = crear_session()
    return _thread_local.session


# ---------------------------------------------------------------------------
# CSV / TSV
# ---------------------------------------------------------------------------

def detectar_codificacion(ruta):
    """Detecta una codificación razonable sin cargar el archivo completo."""
    for enc in ENCODINGS_ENTRADA:
        try:
            with open(ruta, "r", encoding=enc, errors="strict") as f:
                f.read(8192)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def detectar_delimitador(sample):
    """Detecta delimitador; prioriza CSV/TSV habituales si Sniffer falla."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        candidatos = {
            "\t": sample.count("\t"),
            ",": sample.count(","),
            ";": sample.count(";"),
            "|": sample.count("|"),
        }
        return max(candidatos, key=candidatos.get)


def leer_csv_codificado(ruta):
    """Lee el archivo de entrada y devuelve (filas, número de columnas)."""
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No existe el archivo: {ruta}")

    encoding = detectar_codificacion(ruta)

    with open(ruta, "r", encoding=encoding, errors="replace", newline="") as f:
        sample = f.read(8192)
        if not sample.strip():
            raise ValueError("El archivo de entrada está vacío.")
        f.seek(0)

        delimiter = detectar_delimitador(sample)
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        raise ValueError("El archivo de entrada está vacío.")

    num_cols = len(rows[0])
    if num_cols == 0:
        raise ValueError("No se encontraron columnas en el archivo.")

    return rows, num_cols


def escribir_tsv(ruta, filas, encoding_salida):
    """Escribe un TSV compatible y consistente."""
    with open(
        ruta,
        "w",
        newline="",
        encoding=encoding_salida,
        errors="replace",
    ) as f:
        writer = csv.writer(
            f,
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        writer.writerows(filas)


def nombres_columnas_unicas(columnas):
    """Normaliza nombres de columnas repetidos sin perder información."""
    resultado = []
    usados = {}

    for columna in columnas:
        nombre = str(columna).strip() or "columna"
        if nombre not in usados:
            usados[nombre] = 1
            resultado.append(nombre)
        else:
            usados[nombre] += 1
            resultado.append(f"{nombre}_{usados[nombre]}")

    return resultado


# ---------------------------------------------------------------------------
# GBIF
# ---------------------------------------------------------------------------

def buscar_en_gbif(nombre):
    """
    Busca un nombre en GBIF.
    Devuelve siempre un diccionario con status: OK, NO_MATCH o ERROR.
    """
    nombre = (nombre or "").strip()

    if not nombre:
        return {
            "status": "NO_MATCH",
            "match": {},
            "error": "",
        }

    session = obtener_session()

    try:
        response = session.get(
            GBIF_MATCH_URL,
            params={"name": nombre},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        match_json = response.json()
    except requests.RequestException as exc:
        return {
            "status": "ERROR",
            "error": f"match: {exc}",
            "match": {},
        }
    except ValueError as exc:
        return {
            "status": "ERROR",
            "error": f"match: respuesta JSON no válida ({exc})",
            "match": {},
        }

    usage_key = match_json.get("usageKey")

    if not usage_key:
        return {
            "status": "NO_MATCH",
            "match": match_json,
            "error": "",
        }

    try:
        response = session.get(
            GBIF_SPECIES_URL.format(usage_key),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        species_json = response.json()
    except requests.RequestException as exc:
        return {
            "status": "ERROR",
            "error": f"species: {exc}",
            "match": match_json,
        }
    except ValueError as exc:
        return {
            "status": "ERROR",
            "error": f"species: respuesta JSON no válida ({exc})",
            "match": match_json,
        }

    return {
        "status": "OK",
        "match": match_json,
        "species": species_json,
        "error": "",
    }


def limpiar_prefijo_clave(clave, prefijo):
    """Mantiene compatibilidad con posibles claves prefijadas."""
    texto = str(clave)
    if texto.startswith(prefijo):
        return texto[len(prefijo):]
    return texto


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------

def preparar_columnas(posicion, num_cols, nombre):
    try:
        posicion = int(posicion)
    except (TypeError, ValueError):
        raise ValueError(f"La columna {nombre} debe ser un número entero.")

    if posicion < 1 or posicion > num_cols:
        raise ValueError(
            f"La columna {nombre} debe estar entre 1 y {num_cols}."
        )

    return posicion - 1


def procesar_csv(
    ruta_csv,
    col_id_pos,
    col_name_pos,
    carpeta_salida,
    modo_salida,
    encoding_salida,
    progreso_callback,
    estado_callback,
    cancel_event,
):
    rows, num_cols = leer_csv_codificado(ruta_csv)

    idx_id = preparar_columnas(col_id_pos, num_cols, "taxonID")
    idx_name = preparar_columnas(col_name_pos, num_cols, "scientificName")

    registros = []
    nombres_unicos = {}
    filas_invalidas = 0

    for row_number, row in enumerate(rows[1:], start=2):
        if cancel_event.is_set():
            return None

        if len(row) < num_cols:
            filas_invalidas += 1
            continue

        taxon_id = row[idx_id].strip()
        nombre = row[idx_name].strip()

        registro = {
            "taxonID": taxon_id,
            "scientificName_original": nombre,
            "_row_number": row_number,
        }
        registros.append(registro)

        clave = nombre.casefold()
        if clave and clave not in nombres_unicos:
            nombres_unicos[clave] = nombre

    total_nombres = len(nombres_unicos)
    resultados_por_nombre = {}

    if total_nombres:
        estado_callback(
            f"Consultando {total_nombres} nombres únicos en GBIF..."
        )

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="gbif",
        ) as executor:
            futuros = {
                executor.submit(buscar_en_gbif, nombre): clave
                for clave, nombre in nombres_unicos.items()
            }

            completados = 0

            for future in as_completed(futuros):
                if cancel_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    return None

                clave = futuros[future]

                try:
                    resultado = future.result()
                except Exception as exc:
                    resultado = {
                        "status": "ERROR",
                        "error": f"worker: {exc}",
                        "match": {},
                    }

                resultados_por_nombre[clave] = resultado
                completados += 1

                progreso = int(completados * 100 / total_nombres)
                progreso_callback(progreso)
                estado_callback(
                    f"Consultas GBIF: {completados}/{total_nombres}"
                )

    columnas_busqueda = [
        "taxonID",
        "scientificName_original",
        "comparacion",
        "error",
    ]
    columnas_match = [
        "taxonID",
        "scientificName_original",
    ]
    columnas_species = [
        "taxonID",
        "scientificName_original",
    ]

    tabla_busqueda = []
    tabla_match = []
    tabla_species = []

    match_por_id = {}
    species_por_id = {}

    for registro in registros:
        taxon_id = registro["taxonID"]
        nombre = registro["scientificName_original"]
        resultado = resultados_por_nombre.get(
            nombre.casefold(),
            {
                "status": "NO_MATCH",
                "match": {},
                "error": "",
            },
        )

        fila_busqueda = {
            "taxonID": taxon_id,
            "scientificName_original": nombre,
            "comparacion": "",
            "error": "",
        }

        status = resultado.get("status")

        if status == "NO_MATCH":
            fila_busqueda["comparacion"] = "NO_ENCONTRADO"

        elif status == "ERROR":
            fila_busqueda["comparacion"] = "ERROR"
            fila_busqueda["error"] = resultado.get("error", "")

        else:
            match_json = resultado.get("match") or {}
            species_json = resultado.get("species") or {}

            nombre_gbif = species_json.get("scientificName", "")
            fila_busqueda["comparacion"] = (
                "IGUAL"
                if nombre.casefold() == str(nombre_gbif).casefold()
                else "DIFERENTE"
            )

            fila_match = {
                "taxonID": taxon_id,
                "scientificName_original": nombre,
            }
            for key, value in match_json.items():
                columna = limpiar_prefijo_clave(key, "match_")
                if columna not in columnas_match:
                    columnas_match.append(columna)
                fila_match[columna] = value

            fila_species = {
                "taxonID": taxon_id,
                "scientificName_original": nombre,
            }
            for key, value in species_json.items():
                columna = limpiar_prefijo_clave(key, "species_")
                if columna not in columnas_species:
                    columnas_species.append(columna)
                fila_species[columna] = value

            tabla_match.append(fila_match)
            tabla_species.append(fila_species)

            match_por_id[taxon_id] = fila_match
            species_por_id[taxon_id] = fila_species

        tabla_busqueda.append(fila_busqueda)

    base = os.path.splitext(os.path.basename(ruta_csv))[0]
    encoding_seguro = encoding_salida.replace("/", "_").replace("\\", "_")

    if modo_salida == "Una tabla":
        columnas = []
        vistos = set()

        for grupo in (columnas_busqueda, columnas_match, columnas_species):
            for columna in grupo:
                if columna not in vistos:
                    vistos.add(columna)
                    columnas.append(columna)

        filas = [columnas]

        for fila_busqueda in tabla_busqueda:
            taxon_id = fila_busqueda["taxonID"]
            fila_completa = dict(fila_busqueda)

            if taxon_id in match_por_id:
                fila_completa.update(match_por_id[taxon_id])
            if taxon_id in species_por_id:
                fila_completa.update(species_por_id[taxon_id])

            filas.append([fila_completa.get(c, "") for c in columnas])

        ruta_salida = os.path.join(
            carpeta_salida,
            f"{base}_{encoding_seguro}.tsv",
        )
        escribir_tsv(ruta_salida, filas, encoding_salida)
        rutas = [ruta_salida]

    else:
        ruta_busqueda = os.path.join(
            carpeta_salida,
            f"{base}_{encoding_seguro}_Busqueda.tsv",
        )
        ruta_match = os.path.join(
            carpeta_salida,
            f"{base}_{encoding_seguro}_Encontrado.tsv",
        )
        ruta_species = os.path.join(
            carpeta_salida,
            f"{base}_{encoding_seguro}_Taxon.tsv",
        )

        escribir_tsv(
            ruta_busqueda,
            [columnas_busqueda]
            + [[fila.get(c, "") for c in columnas_busqueda]
               for fila in tabla_busqueda],
            encoding_salida,
        )

        escribir_tsv(
            ruta_match,
            [columnas_match]
            + [[fila.get(c, "") for c in columnas_match]
               for fila in tabla_match],
            encoding_salida,
        )

        escribir_tsv(
            ruta_species,
            [columnas_species]
            + [[fila.get(c, "") for c in columnas_species]
               for fila in tabla_species],
            encoding_salida,
        )

        rutas = [ruta_busqueda, ruta_match, ruta_species]

    if filas_invalidas:
        estado_callback(
            f"Proceso terminado. Filas omitidas por tener menos columnas: "
            f"{filas_invalidas}."
        )
    else:
        estado_callback("Proceso terminado correctamente.")

    progreso_callback(100)
    return rutas


# ---------------------------------------------------------------------------
# Interfaz gráfica
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("GBIF.ES — Búsqueda taxonómica")
        self.geometry("800x540")
        self.minsize(700, 480)
        self.configure(bg=COLOR_GRIS_CLARO)

        self.ruta_csv = None
        self.carpeta_salida = None
        self.frame_actual = None
        self.logo_img = None

        self.procesando = False
        self.cancel_event = threading.Event()
        self.worker_thread = None

        self.col_id = tk.StringVar()
        self.col_name = tk.StringVar()
        self.encoding_var = tk.StringVar(value="utf-8")
        self.modo_var = tk.StringVar(value="Tres tablas")
        self.progreso_var = tk.IntVar(value=0)
        self.estado_var = tk.StringVar(value="Listo.")

        self._cargar_logo_svg()
        self._crear_pantalla_presentacion()

        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _cargar_logo_svg(self):
        if not CAIROSVG_DISPONIBLE:
            self.logo_img = None
            return

        try:
            png_bytes = cairosvg.svg2png(bytestring=LOGO_SVG.encode("utf-8"))
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            img.thumbnail((260, 100), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
        except Exception as exc:
            print(f"Aviso al cargar SVG: {exc}")
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
            tk.Label(
                f,
                text="GBIF.ES",
                bg=COLOR_VERDE,
                fg="white",
                font=("Arial", 28, "bold"),
            ).pack(pady=40)

        tk.Label(
            f,
            text="Herramienta de búsqueda taxonómica\n"
                 "basada en la API de GBIF",
            bg=COLOR_VERDE,
            fg="white",
            font=("Arial", 14),
        ).pack(pady=10)

        tk.Button(
            f,
            text="Entrar",
            command=self._crear_pantalla_ejecucion,
            bg=COLOR_BOTON,
            fg=COLOR_BOTON_TEXTO,
            font=("Arial", 14, "bold"),
            padx=20,
            pady=10,
        ).pack(pady=30)

        tk.Button(
            f,
            text="Ayuda",
            command=self._crear_pantalla_ayuda,
            bg="#FFFFFF",
            fg=COLOR_VERDE,
            font=("Arial", 11),
            padx=10,
            pady=5,
        ).pack(pady=5)

    def _crear_pantalla_ejecucion(self):
        self._limpiar_frame()

        f = tk.Frame(self, bg=COLOR_GRIS_CLARO)
        f.pack(fill="both", expand=True)
        self.frame_actual = f

        tk.Label(
            f,
            text="Búsqueda taxonómica en GBIF",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 16, "bold"),
        ).pack(pady=10)

        frame_file = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_file.pack(pady=5)

        tk.Label(
            frame_file,
            text="Archivo CSV/TSV de entrada:",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 11),
        ).grid(row=0, column=0, sticky="w")

        tk.Button(
            frame_file,
            text="Seleccionar archivo",
            command=self._seleccionar_csv,
        ).grid(row=0, column=1, padx=10)

        self.label_csv = tk.Label(
            frame_file,
            text="(ningún archivo seleccionado)",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 9),
        )
        self.label_csv.grid(row=1, column=0, columnspan=2, sticky="w", pady=3)

        frame_cols = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_cols.pack(pady=10)

        tk.Label(
            frame_cols,
            text="Columna taxonID:",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
        ).grid(row=0, column=0, sticky="e")

        self.entry_col_id = tk.Entry(frame_cols, textvariable=self.col_id, width=8)
        self.entry_col_id.grid(row=0, column=1, padx=5)

        tk.Label(
            frame_cols,
            text="Columna scientificName:",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
        ).grid(row=1, column=0, sticky="e")

        self.entry_col_name = tk.Entry(frame_cols, textvariable=self.col_name, width=8)
        self.entry_col_name.grid(row=1, column=1, padx=5)

        frame_opts = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_opts.pack(pady=10)

        tk.Label(
            frame_opts,
            text="Codificación salida:",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
        ).grid(row=0, column=0, sticky="e")

        self.combo_encoding = ttk.Combobox(
            frame_opts,
            textvariable=self.encoding_var,
            values=list(ENCODINGS_SALIDA),
            width=12,
            state="readonly",
        )
        self.combo_encoding.grid(row=0, column=1, padx=5)

        tk.Label(
            frame_opts,
            text="Modo salida:",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
        ).grid(row=1, column=0, sticky="e")

        self.combo_modo = ttk.Combobox(
            frame_opts,
            textvariable=self.modo_var,
            values=["Una tabla", "Tres tablas"],
            width=12,
            state="readonly",
        )
        self.combo_modo.grid(row=1, column=1, padx=5)

        frame_out = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_out.pack(pady=10)

        tk.Label(
            frame_out,
            text="Carpeta de salida:",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 11),
        ).grid(row=0, column=0, sticky="w")

        tk.Button(
            frame_out,
            text="Seleccionar carpeta",
            command=self._seleccionar_carpeta,
        ).grid(row=0, column=1, padx=10)

        self.label_salida = tk.Label(
            frame_out,
            text="(ninguna carpeta seleccionada)",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 9),
        )
        self.label_salida.grid(row=1, column=0, columnspan=2, sticky="w", pady=3)

        self.progreso_label = tk.Label(
            f,
            text="Progreso: 0%",
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 11),
        )
        self.progreso_label.pack(pady=(8, 2))

        self.barra_progreso = ttk.Progressbar(
            f,
            variable=self.progreso_var,
            maximum=100,
            length=420,
            mode="determinate",
        )
        self.barra_progreso.pack(pady=2)

        self.estado_label = tk.Label(
            f,
            textvariable=self.estado_var,
            bg=COLOR_GRIS_CLARO,
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 9),
        )
        self.estado_label.pack(pady=5)

        frame_btn = tk.Frame(f, bg=COLOR_GRIS_CLARO)
        frame_btn.pack(pady=15)

        self.btn_ejecutar = tk.Button(
            frame_btn,
            text="Ejecutar búsqueda en GBIF",
            command=self._ejecutar,
            bg=COLOR_BOTON,
            fg=COLOR_BOTON_TEXTO,
            font=("Arial", 13, "bold"),
            padx=20,
            pady=8,
        )
        self.btn_ejecutar.grid(row=0, column=0, padx=10)

        self.btn_cancelar = tk.Button(
            frame_btn,
            text="Cancelar",
            command=self._cancelar,
            state="disabled",
            padx=10,
            pady=5,
        )
        self.btn_cancelar.grid(row=0, column=1, padx=10)

        self.btn_ayuda = tk.Button(
            frame_btn,
            text="Ayuda",
            command=self._crear_pantalla_ayuda,
            bg="#FFFFFF",
            fg=COLOR_VERDE,
            font=("Arial", 10),
            padx=10,
            pady=5,
        )
        self.btn_ayuda.grid(row=0, column=2, padx=10)

        self.btn_inicio = tk.Button(
            frame_btn,
            text="Inicio",
            command=self._crear_pantalla_presentacion,
            bg="#FFFFFF",
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
            padx=10,
            pady=5,
        )
        self.btn_inicio.grid(row=0, column=3, padx=10)

    def _crear_pantalla_ayuda(self):
        self._limpiar_frame()

        f = tk.Frame(self, bg="#FFFFFF")
        f.pack(fill="both", expand=True)
        self.frame_actual = f

        tk.Label(
            f,
            text="Ayuda — GBIF.ES Búsqueda taxonómica",
            bg="#FFFFFF",
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 16, "bold"),
        ).pack(pady=10)

        texto = (
            "Esta herramienta realiza búsquedas taxonómicas en la API de GBIF.\n\n"
            "1. Selecciona un archivo CSV/TSV de entrada.\n"
            "2. Indica el número de columna donde está taxonID.\n"
            "3. Indica el número de columna donde está scientificName.\n"
            "4. Elige la codificación de salida y el modo "
            "(una tabla o tres tablas).\n"
            "5. Selecciona la carpeta de salida.\n"
            "6. Pulsa 'Ejecutar búsqueda en GBIF' y espera a que termine.\n\n"
            "La herramienta detecta automáticamente el delimitador y la "
            "codificación de entrada.\n"
            "Los nombres científicos repetidos se consultan una sola vez.\n"
            "Los resultados se guardan en ficheros TSV."
        )

        tk.Label(
            f,
            text=texto,
            bg="#FFFFFF",
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 11),
            justify="left",
        ).pack(padx=20, pady=10, anchor="w")

        tk.Button(
            f,
            text="Volver al inicio",
            command=self._crear_pantalla_presentacion,
            bg="#FFFFFF",
            fg=COLOR_GRIS_OSCURO,
            font=("Arial", 10),
            padx=10,
            pady=5,
        ).pack(pady=10)

    def _seleccionar_csv(self):
        if self.procesando:
            return

        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo CSV/TSV",
            filetypes=[
                ("CSV/TSV", "*.csv *.tsv *.txt"),
                ("Todos", "*.*"),
            ],
        )

        if ruta:
            self.ruta_csv = ruta
            self.label_csv.config(text=ruta)

            try:
                _, num_cols = leer_csv_codificado(ruta)
                if not self.col_id.get():
                    self.col_id.set("1")
                if not self.col_name.get():
                    self.col_name.set("2")
                self.estado_var.set(
                    f"Archivo cargado: {num_cols} columnas detectadas."
                )
            except Exception as exc:
                messagebox.showwarning(
                    "Archivo",
                    f"No se pudo analizar el archivo:\n{exc}",
                )

    def _seleccionar_carpeta(self):
        if self.procesando:
            return

        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta de salida"
        )

        if carpeta:
            self.carpeta_salida = carpeta
            self.label_salida.config(text=carpeta)

    def _actualizar_progreso(self, progreso):
        self.progreso_var.set(progreso)
        self.progreso_label.config(text=f"Progreso: {progreso}%")

    def _actualizar_estado(self, texto):
        self.estado_var.set(texto)

    def _ejecutar(self):
        if self.procesando:
            return

        if not self.ruta_csv:
            messagebox.showwarning(
                "Falta archivo",
                "Selecciona un archivo de entrada.",
            )
            return

        if not self.carpeta_salida:
            self.carpeta_salida = os.path.dirname(self.ruta_csv)
            self.label_salida.config(text=self.carpeta_salida)

        try:
            col_id_pos = int(self.col_id.get())
            col_name_pos = int(self.col_name.get())
            if col_id_pos < 1 or col_name_pos < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Error",
                "Las columnas deben ser números enteros positivos.",
            )
            return

        encoding_salida = self.encoding_var.get()
        if encoding_salida not in ENCODINGS_SALIDA:
            messagebox.showerror(
                "Error",
                "La codificación de salida no es válida.",
            )
            return

        if self.modo_var.get() not in ("Una tabla", "Tres tablas"):
            messagebox.showerror(
                "Error",
                "Selecciona un modo de salida válido.",
            )
            return

        try:
            os.makedirs(self.carpeta_salida, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                "Error",
                f"No se puede utilizar la carpeta de salida:\n{exc}",
            )
            return

        self.procesando = True
        self.cancel_event.clear()
        self._actualizar_progreso(0)
        self._actualizar_estado("Preparando archivo...")
        self._cambiar_estado_controles(True)

        args = (
            self.ruta_csv,
            col_id_pos,
            col_name_pos,
            self.carpeta_salida,
            self.modo_var.get(),
            encoding_salida,
        )

        self.worker_thread = threading.Thread(
            target=self._worker,
            args=args,
            daemon=True,
            name="procesamiento-gbif",
        )
        self.worker_thread.start()

    def _worker(
        self,
        ruta_csv,
        col_id_pos,
        col_name_pos,
        carpeta_salida,
        modo_salida,
        encoding_salida,
    ):
        try:
            rutas = procesar_csv(
                ruta_csv,
                col_id_pos,
                col_name_pos,
                carpeta_salida,
                modo_salida,
                encoding_salida,
                progreso_callback=lambda p: self.after(
                    0, self._actualizar_progreso, p
                ),
                estado_callback=lambda t: self.after(
                    0, self._actualizar_estado, t
                ),
                cancel_event=self.cancel_event,
            )

            if rutas is None:
                self.after(0, self._finalizar_cancelado)
                return

            self.after(0, self._finalizar_exito, rutas)

        except Exception as exc:
            self.after(0, self._finalizar_error, str(exc))

    def _cancelar(self):
        if not self.procesando:
            return

        self.cancel_event.set()
        self._actualizar_estado(
            "Cancelando... las consultas activas finalizarán de forma segura."
        )
        self.btn_cancelar.config(state="disabled")

    def _cambiar_estado_controles(self, ocupado):
        estado = "disabled" if ocupado else "normal"

        self.btn_ejecutar.config(state=estado)
        self.btn_ayuda.config(state=estado)
        self.btn_inicio.config(state=estado)

        self.btn_cancelar.config(
            state="normal" if ocupado else "disabled"
        )

        self.entry_col_id.config(state=estado)
        self.entry_col_name.config(state=estado)
        self.combo_encoding.config(state="disabled" if ocupado else "readonly")
        self.combo_modo.config(state="disabled" if ocupado else "readonly")

    def _finalizar_exito(self, rutas):
        self.procesando = False
        self.worker_thread = None
        self._cambiar_estado_controles(False)
        self._actualizar_progreso(100)
        self._actualizar_estado("Proceso terminado correctamente.")

        messagebox.showinfo(
            "Éxito",
            "Ficheros generados:\n\n" + "\n".join(rutas),
        )

    def _finalizar_cancelado(self):
        self.procesando = False
        self.worker_thread = None
        self._cambiar_estado_controles(False)
        self._actualizar_estado("Proceso cancelado.")
        self._actualizar_progreso(0)

    def _finalizar_error(self, error):
        self.procesando = False
        self.worker_thread = None
        self._cambiar_estado_controles(False)
        self._actualizar_estado("Se produjo un error.")
        messagebox.showerror("Error", error)

    def _cerrar(self):
        if self.procesando:
            respuesta = messagebox.askyesno(
                "Salir",
                "Hay un proceso en curso. ¿Quieres cancelarlo y salir?",
            )
            if not respuesta:
                return

            self.cancel_event.set()

        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()