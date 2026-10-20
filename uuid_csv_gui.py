# -----------------------------------------------------------------------------
# GENERADOR DE UUID PARA ARCHIVOS DELIMITADOS
# -----------------------------------------------------------------------------
# Esta utilidad crea una copia de un archivo CSV o TSV añadiendo una nueva
# columna con identificadores UUID únicos.
#
# Características:
# - Detecta delimitadores: coma, punto y coma y tabulador.
# - Detecta varias codificaciones habituales automáticamente.
# - Mantiene el formato original del archivo.
# - Genera una columna UUID.
# - Si UUID ya existe, genera G_UUID.
# - Si G_UUID también existe, genera G_UUID_2, G_UUID_3, etc.
# - No modifica el archivo original.
#
# Salida:
# archivo.csv  -> archivo_UUID.csv
# archivo.tsv  -> archivo_UUID.tsv
# -----------------------------------------------------------------------------

import tkinter as tk
from tkinter import filedialog, messagebox
import uuid
import csv
import os


def generar_uuid():
    """Genera un UUID v4."""
    return str(uuid.uuid4())


def detectar_codificacion(ruta):
    """
    Detecta la codificación probando las más habituales.
    """

    codificaciones = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin1",
        "iso-8859-1"
    ]

    for codificacion in codificaciones:
        try:
            with open(ruta, "r", encoding=codificacion) as f:
                f.read(4096)
            return codificacion
        except UnicodeDecodeError:
            continue

    return "latin1"


def detectar_formato(ruta):
    """
    Detecta delimitador y codificación.
    """

    codificacion = detectar_codificacion(ruta)

    with open(
        ruta,
        "r",
        encoding=codificacion,
        errors="ignore"
    ) as f:

        muestra = f.read(4096)

        try:
            dialecto = csv.Sniffer().sniff(
                muestra,
                delimiters=[",", ";", "\t"]
            )

            delimitador = dialecto.delimiter

        except Exception:
            delimitador = ";"

    return delimitador, codificacion


def obtener_nombre_columna(encabezado):
    """
    Devuelve UUID, G_UUID, G_UUID_2, etc.,
    evitando duplicados.
    """

    existentes = {col.strip().upper() for col in encabezado}

    if "UUID" not in existentes:
        return "UUID"

    if "G_UUID" not in existentes:
        return "G_UUID"

    contador = 2

    while True:
        candidato = f"G_UUID_{contador}"

        if candidato.upper() not in existentes:
            return candidato

        contador += 1


def procesar_archivo():

    ruta = filedialog.askopenfilename(
        title="Seleccionar archivo",
        filetypes=[
            ("Archivos delimitados", "*.csv *.txt *.tsv"),
            ("Todos los archivos", "*.*")
        ]
    )

    if not ruta:
        return

    nombre, extension = os.path.splitext(ruta)

    salida = f"{nombre}_UUID{extension}"

    try:

        delimitador, codificacion = detectar_formato(ruta)

        with open(
            ruta,
            "r",
            encoding=codificacion,
            errors="ignore",
            newline=""
        ) as infile, open(
            salida,
            "w",
            encoding=codificacion,
            newline=""
        ) as outfile:

            lector = csv.reader(infile, delimiter=delimitador)
            escritor = csv.writer(outfile, delimiter=delimitador)

            try:
                encabezado = next(lector)
            except StopIteration:
                messagebox.showerror(
                    "Error",
                    "El archivo está vacío."
                )
                return

            nueva_columna = obtener_nombre_columna(encabezado)

            encabezado.append(nueva_columna)
            escritor.writerow(encabezado)

            total = 0

            for fila in lector:

                if not fila:
                    continue

                fila.append(generar_uuid())
                escritor.writerow(fila)
                total += 1

        tipo_delimitador = {
            ",": "Coma (,)",
            ";": "Punto y coma (;)",
            "\t": "Tabulador (TSV)"
        }.get(delimitador, "Desconocido")

        messagebox.showinfo(
            "Proceso completado",
            f"Registros procesados: {total:,}\n\n"
            f"Columna añadida: {nueva_columna}\n"
            f"Codificación detectada: {codificacion}\n"
            f"Separador detectado: {tipo_delimitador}\n\n"
            f"Archivo generado:\n{salida}\n\n"
            f"El archivo original no ha sido modificado."
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            f"Se ha producido un error:\n\n{str(e)}"
        )


# -------------------------------------------------------------------------
# INTERFAZ
# -------------------------------------------------------------------------

root = tk.Tk()
root.title("Generador de UUID")
root.geometry("650x350")
root.resizable(False, False)

titulo = tk.Label(
    root,
    text="Generador de UUID para archivos delimitados",
    font=("Arial", 16, "bold")
)

titulo.pack(pady=(20, 10))

mensaje = (
    "Esta herramienta genera una copia del archivo seleccionado\n"
    "añadiendo identificadores UUID únicos para cada registro.\n\n"
    "Formatos admitidos:\n"
    "• CSV separado por comas (,)\n"
    "• CSV separado por punto y coma (;)\n"
    "• TSV separado por tabulador\n\n"
    "La codificación y el delimitador originales se conservan.\n"
    "El archivo original no se modifica."
)

texto = tk.Label(
    root,
    text=mensaje,
    justify="center",
    font=("Arial", 11)
)

texto.pack(pady=10)

boton = tk.Button(
    root,
    text="Seleccionar archivo",
    command=procesar_archivo,
    width=28,
    height=2,
    font=("Arial", 12, "bold"),
    bg="#4CAF50",
    fg="white"
)

boton.pack(pady=20)

pie = tk.Label(
    root,
    text="Compatible con CSV, TSV y TXT delimitados",
    fg="gray",
    font=("Arial", 9)
)

pie.pack(side="bottom", pady=15)

root.mainloop()