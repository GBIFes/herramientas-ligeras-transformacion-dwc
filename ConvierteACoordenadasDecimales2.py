import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import csv
import re
from PIL import Image, ImageTk
import os

# ============================================================
# 1. CONVERSIÓN DE COORDENADAS (PORTADO DEL VBA)
# ============================================================

def coord_type(c):
    if c is None or c.strip() == "":
        return 0
    c = c.strip()

    if re.search(r"[0-9].*[NS]\s+[0-9].*[EW]", c):
        return 1
    if re.search(r"lat:\s*[-0-9.]+\s+long:\s*[-0-9.]+", c.lower()):
        return 5
    if re.search(r".*[0-9]+\.[0-9]+.*\s+.*[0-9]+\.[0-9]+.*", c):
        return 2
    if re.search(r".*[0-9]+,[0-9]+.*\s+.*[0-9]+,[0-9]+.*", c):
        return 7

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


def convert_coordinate(c):
    tipo = coord_type(c)

    if tipo == 1:
        parts = c.split()
        if len(parts) < 2:
            return None, None
        lat = dms_to_decimal(parts[0], True)
        lon = dms_to_decimal(parts[1], False)
        return lat, lon

    if tipo in [2, 7]:
        parts = c.replace(",", ".").split()
        if len(parts) < 2:
            return None, None
        return float(parts[0]), float(parts[1])

    if tipo == 5:
        c = c.lower().replace("lat:", "").replace("long:", "")
        parts = c.split()
        if len(parts) < 2:
            return None, None
        return float(parts[0]), float(parts[1])

    return None, None


# ============================================================
# 2. GUI PRINCIPAL
# ============================================================

GBIF_GREEN = "#289530"
GBIF_GRAY = "#333333"
GBIF_FONT = ("Segoe UI", 11)

class App:
    def __init__(self, root):
        self.root = root
        root.title("Conversor de Coordenadas GBIF.ES")
        root.geometry("900x650")
        root.configure(bg="white")

        self.logo_img = None
        self.load_logo("gbifes_logo.png")

        self.filepath = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.output_file = tk.StringVar()

        self.col_id = tk.StringVar()
        self.col_x = tk.StringVar()
        self.col_y = tk.StringVar()

        self.build_welcome()

    def load_logo(self, path):
        try:
            img = Image.open(path)
            img = img.resize((180, 180), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
        except Exception:
            self.logo_img = None

    # --------------------------------------------------------
    # PANTALLA DE BIENVENIDA
    # --------------------------------------------------------
    def build_welcome(self):
        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg="white")
        frame.pack(expand=True)

        if self.logo_img:
            tk.Label(frame, image=self.logo_img, bg="white").pack(pady=20)

        tk.Label(frame, text="GBIF.ES",
                 fg=GBIF_GREEN, bg="white",
                 font=("Segoe UI", 32, "bold")).pack(pady=10)

        tk.Label(frame, text="Conversor de Coordenadas",
                 fg=GBIF_GRAY, bg="white",
                 font=("Segoe UI", 20)).pack(pady=5)

        tk.Button(frame, text="Entrar",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.build_main).pack(pady=30)

        tk.Button(frame, text="Ayuda",
                  bg=GBIF_GRAY, fg="white",
                  font=GBIF_FONT, command=self.build_help).pack()

    # --------------------------------------------------------
    # PANTALLA PRINCIPAL
    # --------------------------------------------------------
    def build_main(self):
        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg="white")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        # LOGO
        if self.logo_img:
            tk.Label(frame, image=self.logo_img, bg="white").pack(pady=10)

        # ARCHIVO DE ENTRADA
        tk.Label(frame, text="Archivo CSV de entrada:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack()
        tk.Entry(frame, textvariable=self.filepath, width=60).pack()
        tk.Button(frame, text="Seleccionar archivo...",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.select_file).pack(pady=10)

        # DIRECTORIO DE SALIDA
        tk.Label(frame, text="Directorio de salida:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack()
        tk.Entry(frame, textvariable=self.output_dir, width=60).pack()
        tk.Button(frame, text="Seleccionar directorio...",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.select_output_dir).pack(pady=10)

        # ARCHIVO DE SALIDA
        tk.Label(frame, text="Archivo de salida:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack()
        tk.Entry(frame, textvariable=self.output_file, width=60).pack()
        tk.Button(frame, text="Seleccionar archivo de salida...",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.select_output_file).pack(pady=10)

        # COLUMNAS
        tk.Label(frame, text="Número de columna ID:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack()
        tk.Entry(frame, textvariable=self.col_id, width=10).pack()

        tk.Label(frame, text="Columna coordenada X (o única):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack()
        tk.Entry(frame, textvariable=self.col_x, width=10).pack()

        tk.Label(frame, text="Columna coordenada Y (opcional):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).pack()
        tk.Entry(frame, textvariable=self.col_y, width=10).pack()

        tk.Button(frame, text="Procesar",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.process).pack(pady=20)

        tk.Button(frame, text="Ayuda",
                  bg=GBIF_GRAY, fg="white",
                  font=GBIF_FONT, command=self.build_help).pack()

    # --------------------------------------------------------
    # PANTALLA DE AYUDA
    # --------------------------------------------------------
    def build_help(self):
        for w in self.root.winfo_children():
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
            "• Lee un archivo CSV de entrada.\n"
            "• Usa la columna ID seleccionada.\n"
            "• Usa la columna de coordenadas X (o única).\n"
            "• Opcionalmente, usa una columna Y si las coordenadas están separadas.\n"
            "• Detecta si las coordenadas están en formato DMS, decimales o lat/long.\n"
            "• Convierte a coordenadas decimales.\n"
            "• Permite elegir directorio y archivo de salida.\n"
            "• Genera un archivo TSV separado por tabulaciones.\n"
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
            # nombre por defecto del archivo de salida
            base = os.path.basename(f).replace(".csv", "_DecimalCoord.tsv")
            self.output_file.set(base)
            # directorio por defecto
            self.output_dir.set(os.path.dirname(f))

    def select_output_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir.set(d)

    def select_output_file(self):
        f = filedialog.asksaveasfilename(defaultextension=".tsv",
                                         filetypes=[("TSV files", "*.tsv")])
        if f:
            self.output_file.set(os.path.basename(f))
            self.output_dir.set(os.path.dirname(f))

    # --------------------------------------------------------
    # PROCESAMIENTO
    # --------------------------------------------------------
    def process(self):
        archivo = self.filepath.get()
        out_dir = self.output_dir.get()
        out_file = self.output_file.get()

        if not archivo:
            messagebox.showerror("Error", "Selecciona un archivo de entrada.")
            return

        if not out_dir or not out_file:
            messagebox.showerror("Error", "Selecciona directorio y archivo de salida.")
            return

        salida = os.path.join(out_dir, out_file)

        try:
            col_id = int(self.col_id.get())
            col_x = int(self.col_x.get())
            col_y_raw = self.col_y.get().strip()
            col_y = int(col_y_raw) if col_y_raw != "" else None
        except ValueError:
            messagebox.showerror("Error", "Columnas inválidas (usa números).")
            return

        out_rows = []

        try:
            with open(archivo, encoding="utf-8") as f:
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
