import csv
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

# =========================================================
# DETECTOR DE CODIFICACIÓN (sin dependencias)
# =========================================================

def detectar_codificacion(ruta):
    """
    Detecta automáticamente UTF-8, UTF-8 BOM, ISO-8859-1, Windows-1252.
    """
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            with open(ruta, "r", encoding=enc) as f:
                f.read()
            return enc
        except:
            pass
    return "latin-1"


# =========================================================
# DETECTOR DE SEPARADOR
# =========================================================

def detectar_dialect(ruta):
    """
    Detecta automáticamente separador: , ; tab | 
    Detecta comillas si existen.
    """
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


# =========================================================
# NORMALIZADOR DE DECIMALES
# =========================================================

def normalizar_decimales(texto):
    if not texto:
        return texto
    return re.sub(r"(\d+),(\d+)", r"\1.\2", texto)


# =========================================================
# PARSER TAXONÓMICO
# =========================================================

CACHE = {}

RANK_MAP = {
    "subsp.": "subspecies",
    "ssp.": "subspecies",
    "var.": "variety",
    "subvar.": "subvariety",
    "f.": "form",
    "fo.": "form",
    "form.": "form",
    "subf.": "subform",
    "subfo.": "subform",
    "subform.": "subform",
}
RANK_LITERALS = set(RANK_MAP.keys())

AUTHOR_PARTICLES = {"de", "del", "von", "van", "in", "ex", "y", "et"}

NBSP = ["\u00A0", "\u2002", "\u2003", "\u2009", "\u200A", "\u202F", "\u3000"]
ZERO_WIDTH = ["\u200B", "\uFEFF"]


def normalize_text(s):
    if not s:
        return ""

    for e in NBSP:
        s = s.replace(e, " ")

    for z in ZERO_WIDTH:
        s = s.replace(z, "")

    s = s.replace("(", " (").replace(")", ") ")
    s = s.replace(",", ", ")

    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Za-z]\.?[A-Za-z]\.?[A-Za-z]?\.?),([1-2][0-9]{3})", r"\1, \2", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def is_year(t):
    return bool(re.fullmatch(r"[1-2][0-9]{3}", t))


def detect_code(tokens):
    for t in tokens:
        if is_year(t):
            return "ICZN"
    if len(tokens) >= 3:
        return "ICN"
    return "Indeterminado"


def is_author_particle(t):
    return t.lower() in AUTHOR_PARTICLES


def get_specific_position(tokens):
    """
    Zoología: Genus (Subgenus) species
    Botánica: Genus species
    """
    if len(tokens) > 1 and tokens[1].startswith("(") and tokens[1].endswith(")"):
        start = 2
    else:
        start = 1

    for i in range(start, len(tokens)):
        t = tokens[i]
        if t and t[0].islower() and not is_author_particle(t):
            return i
    return None


def detect_hybrid(tokens):
    if not tokens:
        return None
    if tokens[0].startswith("×"):
        return "generic"
    if len(tokens) > 2 and tokens[1] == "×":
        return "generic"
    if len(tokens) > 1 and tokens[1].startswith("×"):
        return "specific"
    return None


def detect_cultivar(tokens):
    for t in tokens:
        if t.startswith("'") and t.endswith("'"):
            return t.strip("'")
    return ""


def extract_authorship(tokens, last_epithet_idx, code):
    if last_epithet_idx is None:
        return ""

    res = []
    i = last_epithet_idx + 1

    while i < len(tokens):
        t = tokens[i]
        res.append(t)

        if is_author_particle(t) and i + 1 < len(tokens):
            i += 1
            res.append(tokens[i])

        if code == "ICZN" and is_year(t):
            break

        i += 1

    return " ".join(res).strip()


def parse_scientific_name(verbatim):
    if verbatim in CACHE:
        return CACHE[verbatim]

    if not verbatim:
        return {
            "scientificName": "",
            "taxonRank": "",
            "verbatimTaxonRank": "",
            "scientificNameAuthorship": "",
            "specificEpithet": "",
            "infraspecificEpithet": "",
            "subgenus": "",
            "hybridType": "",
            "cultivar": "",
            "code": "",
            "genus": "",
        }

    name = normalize_text(str(verbatim))
    tokens = name.split()

    if not tokens:
        return {
            "scientificName": "",
            "taxonRank": "",
            "verbatimTaxonRank": "",
            "scientificNameAuthorship": "",
            "specificEpithet": "",
            "infraspecificEpithet": "",
            "subgenus": "",
            "hybridType": "",
            "cultivar": "",
            "code": "",
            "genus": "",
        }

    genus = tokens[0]

    subgenus = ""
    if len(tokens) > 1 and tokens[1].startswith("(") and tokens[1].endswith(")"):
        subgenus = tokens[1][1:-1]

    specific_idx = get_specific_position(tokens)
    specific = tokens[specific_idx] if specific_idx is not None else ""

    infra_rank_literal = ""
    infra_rank = ""
    rank_idx = None

    if specific_idx is not None:
        for i in range(specific_idx + 1, len(tokens)):
            if tokens[i] in RANK_LITERALS:
                infra_rank_literal = tokens[i]
                infra_rank = RANK_MAP[tokens[i]]
                rank_idx = i
                break

    infra_epithet = ""

    if rank_idx is not None and rank_idx + 1 < len(tokens):
        infra_epithet = tokens[rank_idx + 1]
    else:
        if specific_idx is not None:
            for i in range(specific_idx + 1, len(tokens)):
                t = tokens[i]
                if t and t[0].islower() and not is_author_particle(t):
                    infra_epithet = t
                    break

    code = detect_code(tokens)

    last_epithet_idx = None
    if infra_epithet:
        last_epithet_idx = tokens.index(infra_epithet)
    elif specific_idx is not None:
        last_epithet_idx = specific_idx

    authorship = extract_authorship(tokens, last_epithet_idx, code)

    hybrid_type = detect_hybrid(tokens)
    cultivar = detect_cultivar(tokens)

    parts = [genus]
    if subgenus:
        parts.append(f"({subgenus})")
    if specific:
        parts.append(specific)
    if infra_rank_literal:
        parts.append(infra_rank_literal)
    if infra_epithet:
        parts.append(infra_epithet)
    if authorship:
        parts.append(authorship)

    scientific_name = " ".join(parts)

    res = {
        "scientificName": scientific_name,
        "taxonRank": infra_rank,
        "verbatimTaxonRank": infra_rank_literal,
        "scientificNameAuthorship": authorship,
        "specificEpithet": specific,
        "infraspecificEpithet": infra_epithet,
        "subgenus": subgenus,
        "hybridType": hybrid_type,
        "cultivar": cultivar,
        "code": code,
        "genus": genus,
    }

    CACHE[verbatim] = res
    return res


# =========================================================
# CSV
# =========================================================

def procesar_csv(ruta_csv, ruta_salida, col_id, col_name):

    encoding = detectar_codificacion(ruta_csv)
    dialect = detectar_dialect(ruta_csv)

    with open(ruta_csv, newline="", encoding=encoding, errors="ignore") as infile, \
         open(ruta_salida, "w", newline="", encoding="utf-8") as outfile:

        lector = csv.reader(infile, dialect)

        header = next(lector)

        col_id = int(col_id) - 1
        col_name = int(col_name) - 1

        escritor = csv.writer(
            outfile,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\n"
        )

        escritor.writerow([
            "taxonID",
            "verbatimScientificName",
            "scientificName",
            "genus",
            "subgenus",
            "specificEpithet",
            "infraspecificEpithet",
            "taxonRank",
            "verbatimTaxonRank",
            "scientificNameAuthorship",
            "hybridType",
            "cultivar",
            "code",
        ])

        for row in lector:
            if len(row) == 0:
                continue

            taxon_id = normalizar_decimales(row[col_id]) if col_id < len(row) else ""
            verbatim = row[col_name] if col_name < len(row) else ""

            parsed = parse_scientific_name(verbatim)

            escritor.writerow([
                taxon_id,
                verbatim,
                parsed["scientificName"],
                parsed["genus"],
                parsed["subgenus"],
                parsed["specificEpithet"],
                parsed["infraspecificEpithet"],
                parsed["taxonRank"],
                parsed["verbatimTaxonRank"],
                parsed["scientificNameAuthorship"],
                parsed["hybridType"],
                parsed["cultivar"],
                parsed["code"],
            ])

    messagebox.showinfo("Éxito", f"Archivo generado:\n{ruta_salida}")


# =========================================================
# INTERFAZ GRÁFICA
# =========================================================

def main():
    root = tk.Tk()
    root.title("Atomización de nombres científicos")
    root.geometry("600x520")

    ruta_csv = {"path": None}
    ruta_salida = {"path": None}

    def seleccionar_csv():
        f = filedialog.askopenfilename(
            title="Selecciona un archivo CSV",
            filetypes=[("CSV/TSV", "*.csv *.tsv *.txt"), ("Todos", "*.*")]
        )
        if not f:
            return

        ruta_csv["path"] = f
        label_csv.config(text=f)

        base = os.path.splitext(f)[0]
        propuesta = base + "_ScientificNames.csv"
        salida_entry.delete(0, tk.END)
        salida_entry.insert(0, propuesta)
        ruta_salida["path"] = propuesta

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
            messagebox.showerror("Error", "No se ha seleccionado archivo de entrada.")
            return
        if not ruta_salida["path"]:
            messagebox.showerror("Error", "No se ha seleccionado archivo de salida.")
            return
        if not col_id_entry.get().isdigit():
            messagebox.showerror("Error", "Columna ID debe ser un número.")
            return
        if not col_name_entry.get().isdigit():
            messagebox.showerror("Error", "Columna nombre científico debe ser un número.")
            return

        procesar_csv(
            ruta_csv["path"],
            ruta_salida["path"],
            col_id_entry.get(),
            col_name_entry.get()
        )

    label_intro = tk.Label(
        root,
        text=(
            "Requisitos del CSV:\n"
            "- Funciona con , ; tabuladores y |\n"
            "- Funciona con comillas o sin ellas\n"
            "- Funciona con decimales con . o ,\n"
            "- Detecta UTF‑8, ISO, Windows‑1252\n"
            "- Indica el número de columna (1,2,3...)."
        ),
        justify="left",
        font=("Arial", 10),
    )
    label_intro.pack(pady=10)

    btn_csv = tk.Button(root, text="Seleccionar CSV de entrada", command=seleccionar_csv)
    btn_csv.pack(pady=5)

    label_csv = tk.Label(root, text="(ningún archivo seleccionado)", font=("Arial", 9))
    label_csv.pack(pady=5)

    frame_cols = tk.Frame(root)
    frame_cols.pack(pady=10)

    tk.Label(frame_cols, text="Columna ID (número):", font=("Arial", 10)).pack()
    col_id_entry = tk.Entry(frame_cols, width=10)
    col_id_entry.pack(pady=5)

    tk.Label(frame_cols, text="Columna nombre científico (número):", font=("Arial", 10)).pack()
    col_name_entry = tk.Entry(frame_cols, width=10)
    col_name_entry.pack(pady=5)

    frame_salida = tk.Frame(root)
    frame_salida.pack(pady=10)

    tk.Label(frame_salida, text="Archivo de salida:", font=("Arial", 10)).pack()
    salida_entry = tk.Entry(frame_salida, width=40)
    salida_entry.pack(pady=5)

    btn_salida = tk.Button(frame_salida, text="Seleccionar archivo de salida", command=seleccionar_salida)
    btn_salida.pack()

    btn_run = tk.Button(root, text="Ejecutar extracción", command=ejecutar)
    btn_run.pack(pady=15)

    root.mainloop()


if __name__ == "__main__":
    main()
