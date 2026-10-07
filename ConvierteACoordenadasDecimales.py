import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import csv
import re
from PIL import Image, ImageTk  # necesitas instalar pillow: pip install pillow

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
GBIF_FONT = ("Segoe UI", 11)  # Open Sans no siempre está instalada

class App:
    def __init__(self, root):
        self.root = root
        root.title("Conversor de Coordenadas GBIF.ES")
        root.geometry("800x600")
        root.configure(bg="white")

        self.logo_img = None
        self.load_logo("gbifes_logo.png")  # pon aquí el nombre de tu PNG

        self.filepath = tk.StringVar()
        self.col_id = tk.StringVar()
        self.col_x = tk.StringVar()
        self.col_y = tk.StringVar()

        self.build_welcome()

    def load_logo(self, path):
        try:
            img = Image.open(path)
            img = img.resize((200, 200), Image.LANCZOS)
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
        frame.pack(expand=True, fill="both")

        if self.logo_img:
            tk.Label(frame, image=self.logo_img, bg="white").pack(pady=20)

        tk.Label(frame, text="GBIF.ES",
                 fg=GBIF_GREEN, bg="white",
                 font=("Segoe UI", 28, "bold")).pack(pady=10)

        tk.Label(frame, text="Conversor de Coordenadas",
                 fg=GBIF_GRAY, bg="white",
                 font=("Segoe UI", 18)).pack(pady=5)

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

        top = tk.Frame(frame, bg="white")
        top.pack(fill="x")

        if self.logo_img:
            tk.Label(top, image=self.logo_img, bg="white").pack(side="left", padx=10)

        tk.Label(top, text="Conversor de Coordenadas GBIF.ES",
                 fg=GBIF_GRAY, bg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=10)

        body = tk.Frame(frame, bg="white")
        body.pack(expand=True, fill="both", pady=20)

        tk.Label(body, text="Archivo CSV de entrada:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=0, column=0, sticky="w")
        tk.Entry(body, textvariable=self.filepath, width=50).grid(row=0, column=1, padx=5)
        tk.Button(body, text="Seleccionar...",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.select_file).grid(row=0, column=2, padx=5)

        tk.Label(body, text="Número de columna ID:",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.col_id, width=10).grid(row=1, column=1, sticky="w")

        tk.Label(body, text="Columna coordenada X (o única):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=2, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.col_x, width=10).grid(row=2, column=1, sticky="w")

        tk.Label(body, text="Columna coordenada Y (opcional):",
                 bg="white", fg=GBIF_GRAY, font=GBIF_FONT).grid(row=3, column=0, sticky="w", pady=5)
        tk.Entry(body, textvariable=self.col_y, width=10).grid(row=3, column=1, sticky="w")

        tk.Button(body, text="Procesar",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.process).grid(row=4, column=0, columnspan=3, pady=20)

        tk.Button(body, text="Ayuda",
                  bg=GBIF_GRAY, fg="white",
                  font=GBIF_FONT, command=self.build_help).grid(row=5, column=0, columnspan=3)

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
                 font=("Segoe UI", 20, "bold")).pack(pady=10)

        texto = (
            "Este conversor:\n\n"
            "• Lee un archivo CSV de entrada.\n"
            "• Usa la columna ID seleccionada.\n"
            "• Usa la columna de coordenadas X (o única).\n"
            "• Opcionalmente, usa una columna Y si las coordenadas están separadas.\n"
            "• Detecta si las coordenadas están en formato DMS, decimales o lat/long.\n"
            "• Convierte a coordenadas decimales.\n"
            "• Genera un archivo de salida TSV (separado por tabulaciones).\n\n"
            "Logo y estilo basados en la identidad gráfica de GBIF.ES."
        )

        tk.Label(frame, text=texto,
                 bg="white", fg=GBIF_GRAY,
                 font=GBIF_FONT, justify="left").pack(pady=10)

        tk.Button(frame, text="Volver",
                  bg=GBIF_GREEN, fg="white",
                  font=GBIF_FONT, command=self.build_main).pack(pady=20)

    # --------------------------------------------------------
    # SELECCIÓN DE ARCHIVO
    # --------------------------------------------------------
    def select_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if f:
            self.filepath.set(f)

    # --------------------------------------------------------
    # PROCESAMIENTO
    # --------------------------------------------------------
    def process(self):
        try:
            col_id = int(self.col_id.get())
            col_x = int(self.col_x.get())
            col_y_raw = self.col_y.get().strip()
            col_y = int(col_y_raw) if col_y_raw != "" else None
        except ValueError:
            messagebox.showerror("Error", "Columnas inválidas (usa números de índice).")
            return

        archivo = self.filepath.get()
        if not archivo:
            messagebox.showerror("Error", "Selecciona un archivo CSV.")
            return

        salida = archivo.replace(".csv", "_converted.tsv")
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
