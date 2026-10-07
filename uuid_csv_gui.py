import uuid
import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os

def generar_uuid():
    return str(uuid.uuid4())

def detectar_delimitador(ruta):
    with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
        primera = f.readline()
        if ";" in primera:
            return ";"
        return ","

def procesar_csv():
    ruta = filedialog.askopenfilename(
        title="Selecciona un archivo CSV",
        filetypes=[("CSV files", "*.csv")]
    )

    if not ruta:
        return

    salida = os.path.splitext(ruta)[0] + "_UUID.csv"

    try:
        delimitador = detectar_delimitador(ruta)

        with open(ruta, newline="", encoding="utf-8", errors="ignore") as infile, \
             open(salida, "w", newline="", encoding="utf-8") as outfile:

            lector = csv.reader(infile, delimiter=delimitador)
            escritor = csv.writer(outfile, delimiter=delimitador)

            try:
                encabezado = next(lector)
            except StopIteration:
                messagebox.showerror("Error", "El CSV está vacío.")
                return

            encabezado.append("UUID")
            escritor.writerow(encabezado)

            for fila in lector:
                if len(fila) == 0:
                    continue
                fila.append(generar_uuid())
                escritor.writerow(fila)

        messagebox.showinfo("Éxito", f"Archivo generado:\n{salida}")

    except Exception as e:
        messagebox.showerror("Error", str(e))

root = tk.Tk()
root.title("Generador de UUID para CSV")
root.geometry("400x200")

label = tk.Label(root, text="Generar UUIDs para un archivo CSV", font=("Arial", 14))
label.pack(pady=20)

boton = tk.Button(root, text="Seleccionar CSV", command=procesar_csv, font=("Arial", 12))
boton.pack(pady=10)

root.mainloop()