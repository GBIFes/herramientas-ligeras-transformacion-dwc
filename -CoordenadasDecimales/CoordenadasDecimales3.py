import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import csv
import re
from PIL import Image, ImageTk
import os

# ============================================================
# 1. CONVERSIÓN DE COORDENADAS (PORTADO PARCIAL DEL VBA)
# ============================================================

def coord_type(c):
    if c is None or c.strip() == "":
        return 0
    c = c.strip()

    # Geo_DMS
    if re.search(r"[0-9].*[NS]\s+[0-9].*[EW]", c):
        return 1
    # Geo_LL
    if re.search(r"lat:\s*[-0-9.]+\s+long:\s*[-0-9.]+", c.lower()):
        return 5
    # Geo_Xerox / decimales
    if re.search(r".*[0-9]+\.[0-9]+.*\s+.*[0-9]+\.[0-9]+.*", c):
        return 2
    # Decimales con coma
    if re.search(r".*[0-9]+,[0-9]+.*\s+.*[0-9]+,[0-9]+.*", c):
        return 7
    # UTM/MGRS (muy simplificado)
    if re.search(r"[0-9]{2}[A-Z]\s+[0-9]+\s+[0-9]+", c) or re.search(r"[0-9]+[A-Z]{3}[0-9]+", c):
        return 3

    return 6


def dms_to_decimal(dms, is_lat=True):
    dms = dms.strip()

    hemi = re.search(r"[NS]" if is_lat else r"[EW]", dms)
    if not hemi:
        return None

    sign = 1 if hemi.group() in ["N", "E"] else -1

    g = re.search(r"(\d+)º", dms) or re.search(r"(\d+)°", dms)
    if not g:
        return None
    grads = float(g.group(1))

    m = re.search(r"(\d+)'", dms)
    mins = float(m.group(1)) if m else 0

    s = re.search(r"(\d+)\"|(\d+)''", dms)
    secs = float(s.group(1)) if s else 0

    dec = grads + mins/60 + secs/3600
    return sign * dec


# ============================================================
# 2. STUBS PARA UTM/MGRS (A RELLENAR CON TU LÓGICA)
# ============================================================

def UTM2latlong(zona, y, x, switch4):
    """
    TODO: aquí va la lógica de UTM2latlong del VBA.
    switch4 = 1 para latitud, 0 para longitud.
    Devuelve un float (lat o lon).
    """
    # Pon aquí tu implementación real.
    return None


def mgrtgp2(utm1000_str, which):
    """
    TODO: aquí va la lógica de mgrtgp2 del VBA.
    utm1000_str: cadena UTM transformada a 1000m.
    which: 1 = lat, 2 = lon.
    Devuelve un float (lat o lon).
    """
    # Pon aquí tu implementación real.
    return None


# ============================================================
# 3. CONVERSIÓN GENERAL
# ============================================================

def convert_coordinate(c):
    tipo = coord_type(c)

    if tipo == 1:  # DMS
        parts = c.split()
        if len(parts) < 2:
            return None, None
        lat = dms_to_decimal(parts[0], True)
        lon = dms_to_decimal(parts[1], False)
        return lat, lon

    if tipo in [2, 7]:  # decimales
        parts = c.replace(",", ".").split()
        if len(parts) < 2:
            return None, None
        return float(parts[0]), float(parts[1])

    if tipo == 5:  # lat:## long:##
        c2 = c.lower().replace("lat:", "").replace("long:", "")
        parts = c2.split()
        if len(parts) < 2:
            return None, None
        return float(parts[0]), float(parts[1])

    if tipo == 3:
        # Aquí podrías parsear UTM/MGRS y llamar a UTM2latlong / mgrtgp2
        # Ejemplo muy esquemático:
        # zona, x, y = ...
        # lat = UTM2latlong(zona, y, x, 1)
        # lon = UTM2latlong(zona, y, x, 0)
        return None, None

    return None, None


# ============================================================
# 4. GUI PRINCIPAL
# ============================================================

GBIF_GREEN = "#289530"
GBIF_GRAY = "#333333"
GBIF_FONT = ("Segoe UI", 10)

class App:
    def __init__(self, root):
        self.root = root
        root.title("Conversor de Coordenadas GBIF.ES")
        root.geometry("1000x700")
        root.configure(bg="white")

        # Icono de aplicación (si tienes un .ico)
        try:
            root.iconbitmap("gbifes.ico")
        except Exception:
            pass

        self.logo_img = None
        self.load_logo("gbifes_logo.png")

        self.filepath = tk.StringVar()
        self.output_path = tk.StringVar()
        self.encoding = tk.StringVar(value="utf-8")

        self.col_id = tk.StringVar()
        self.col_x = tk.StringVar()
        self.col_y = tk.StringVar()

        self.preview_data = []

        self.build_menu()
        self.build_welcome()

    def load_logo(self, path):
        try:
            img = Image.open(path)
            img = img.resize((160, 160), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
        except Exception:
            self.logo_img = None

    # --------------------------------------------------------
    # MENÚ SUPERIOR
    # --------------------------------------------------------
    def build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Abrir CSV...", command=self.select_file)
        file_menu.add_command(label="Seleccionar salida...", command=self.select_output_file)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.quit)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Ayuda", command=self.build_help)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        self.root.config(menu=menubar)

    # --------------------------------------------------------
    # PANTALLA DE BIENVENIDA
    # --------------------------------------------------------
    def build_welcome(self):
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()

        frame = tk.Frame(self.root, bg="white")
        frame.pack(expand=True)

        if self.logo_img:
            tk.Label(frame, image=self.logo_img, bg="white").pack(pady=20)

        tk.Label(frame, text="GBIF.ES",
                 fg=GBIF_GREEN, bg="white",
                 font=("Segoe UI", 30, "bold")).pack(pady=10)

        tk.Label(frame, text="Conversor de Coordenadas",
                 fg=GBIF_GRAY, bg="white",
                 font=("Segoe UI", 18)).pack(pady=5)

        tk.Button(frame, text="Entrar",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.build_main).pack(pady=30)

    # --------------------------------------------------------
    # PANTALLA PRINCIPAL
    # --------------------------------------------------------
    def build_main(self):
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()

        frame = tk.Frame(self.root, bg="white")
        frame.pack(expand=True, fill="both", padx=10, pady=10)

        top = tk.Frame(frame, bg="white")
        top.pack(fill="x")

        if self.logo_img:
            tk.Label(top, image=self.logo_img, bg="white").pack(side="left", padx=10)

        tk.Label(top, text="Conversor de Coordenadas GBIF.ES",
                 fg=GBIF_GRAY, bg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=10)

        body = tk.Frame(frame, bg="white")
        body.pack(fill="both", expand=True, pady=10)

        # Archivo entrada
        tk.Label(body, text="Archivo CSV de entrada:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=0, column=0, sticky="w")
        tk.Entry(body, textvariable=self.filepath, width=50).grid(row=0, column=1, sticky="w")
        tk.Button(body, text="Seleccionar...",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.select_file).grid(row=0, column=2, padx=5)

        # Archivo salida (directorio + nombre en un solo diálogo)
        tk.Label(body, text="Archivo de salida (TSV):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.output_path, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(body, text="Seleccionar...",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.select_output_file).grid(row=1, column=2, padx=5)

        # Codificación
        tk.Label(body, text="Codificación CSV:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=2, column=0, sticky="w", pady=5)
        enc_combo = ttk.Combobox(body, textvariable=self.encoding,
                                 values=["utf-8", "latin-1", "cp1252"], width=10)
        enc_combo.grid(row=2, column=1, sticky="w")

        # Columnas
        tk.Label(body, text="Columna ID:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=3, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.col_id, width=10).grid(row=3, column=1, sticky="w")

        tk.Label(body, text="Columna coordenada X (o única):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=4, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.col_x, width=10).grid(row=4, column=1, sticky="w")

        tk.Label(body, text="Columna coordenada Y (opcional):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=5, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.col_y, width=10).grid(row=5, column=1, sticky="w")

        tk.Button(body, text="Validar columnas y vista previa",
                  bg=GBIF_GRAY, fg="white",
                  font=GBIF_FONT, command=self.validate_and_preview).grid(row=6, column=0, columnspan=3, pady=10)

        tk.Button(body, text="Procesar",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.process).grid(row=7, column=0, columnspan=3, pady=10)

        # Vista previa
        preview_frame = tk.Frame(frame, bg="white")
        preview_frame.pack(fill="both", expand=True)

        tk.Label(preview_frame, text="Vista previa CSV:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack(anchor="w")

        self.tree = ttk.Treeview(preview_frame, columns=("c1", "c2", "c3"), show="headings")
        self.tree.pack(fill="both", expand=True)

    # --------------------------------------------------------
    # PANTALLA DE AYUDA
    # --------------------------------------------------------
    def build_help(self):
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()

        frame = tk.Frame(self.root, bg="white")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        if self.logo_img:
            tk.Label(frame, image=self.logo_img, bg="white").pack(pady=10)

        tk.Label(frame, text="Ayuda - GBIF.ES",
                 fg=GBIF_GREEN, bg="white",
                 font=("Segoe UI", 22, "bold")).pack(pady=10)

        texto = (
            "Este conversor:\n\n"
            "• Lee un archivo CSV de entrada con la codificación seleccionada.\n"
            "• Permite elegir archivo de salida (directorio + nombre) en un solo cuadro.\n"
            "• Usa la columna ID y una o dos columnas de coordenadas.\n"
            "• Detecta formatos DMS, decimales y lat/long.\n"
            "• Está preparado para integrar UTM/MGRS (UTM2latlong, mgrtgp2).\n"
            "• Genera un TSV separado por tabulaciones con ID, original, lat, lon.\n"
        )

        tk.Label(frame, text=texto,
                 bg="white", fg=GBIF_GRAY,
                 font=GBIF_FONT, justify="left").pack(pady=10)

        tk.Button(frame, text="Volver",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.build_main).pack(pady=20)

    # --------------------------------------------------------
    # SELECCIÓN DE ARCHIVOS
    # --------------------------------------------------------
    def select_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if f:
            self.filepath.set(f)
            base = os.path.basename(f).replace(".csv", "_DecimalCoord.tsv")
            self.output_path.set(os.path.join(os.path.dirname(f), base))

    def select_output_file(self):
        f = filedialog.asksaveasfilename(defaultextension=".tsv",
                                         filetypes=[("TSV files", "*.tsv")])
        if f:
            self.output_path.set(f)

    # --------------------------------------------------------
    # VALIDACIÓN Y VISTA PREVIA
    # --------------------------------------------------------
    def validate_and_preview(self):
        archivo = self.filepath.get()
        if not archivo:
            messagebox.showerror("Error", "Selecciona un archivo de entrada.")
            return

        try:
            col_id = int(self.col_id.get())
            col_x = int(self.col_x.get())
            col_y_raw = self.col_y.get().strip()
            col_y = int(col_y_raw) if col_y_raw != "" else None
        except ValueError:
            messagebox.showerror("Error", "Columnas inválidas (usa índices numéricos).")
            return

        enc = self.encoding.get()
        self.preview_data = []

        try:
            with open(archivo, encoding=enc) as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i >= 20:
                        break
                    self.preview_data.append(row)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el CSV:\n{e}")
            return

        # Configurar Treeview según número de columnas
        if not self.preview_data:
            return

        ncols = len(self.preview_data[0])
        self.tree["columns"] = [f"c{i}" for i in range(ncols)]
        for i in range(ncols):
            self.tree.heading(f"c{i}", text=f"Col {i}")
            self.tree.column(f"c{i}", width=80)

        for row in self.tree.get_children():
            self.tree.delete(row)

        for row in self.preview_data:
            self.tree.insert("", "end", values=row)

        # Validación visual simple: marcar columnas elegidas
        msg = f"Columnas seleccionadas:\nID = {col_id}\nX = {col_x}\nY = {col_y if col_y is not None else '(no usada)'}"
        messagebox.showinfo("Columnas", msg)

    # --------------------------------------------------------
    # PROCESAMIENTO
    # --------------------------------------------------------
    def process(self):
        archivo = self.filepath.get()
        salida = self.output_path.get()
        if not archivo or not salida:
            messagebox.showerror("Error", "Selecciona archivo de entrada y salida.")
            return

        try:
            col_id = int(self.col_id.get())
            col_x = int(self.col_x.get())
            col_y_raw = self.col_y.get().strip()
            col_y = int(col_y_raw) if col_y_raw != "" else None
        except ValueError:
            messagebox.showerror("Error", "Columnas inválidas (usa índices numéricos).")
            return

        enc = self.encoding.get()
        out_rows = []

        try:
            with open(archivo, encoding=enc) as f:
                reader = csv.reader(f)
                for row in reader:
                    try:
                        id_val = row[col_id]
                        if col_y is None:
                            coord_val = row[col_x]
                        else:
                            coord_val = f"{row[col_x]} {row[col_y]}"

                        lat, lon = convert_coordinate(coord_val)
                        out_rows.append([id_val, coord_val, lat, lon])
                    except Exception:
                        out_rows.append([row[col_id] if len(row) > col_id else "",
                                         coord_val if 'coord_val' in locals() else "",
                                         None, None])

            with open(salida, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter="\t")
                writer.writerow(["ID", "Original", "Lat", "Lon"])
                writer.writerows(out_rows)

            messagebox.showinfo("OK", f"Archivo generado:\n{salida}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo procesar el archivo:\n{e}")


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
