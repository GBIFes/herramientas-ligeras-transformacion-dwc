"""
main_window.py

Interfaz gráfica principal.
"""

import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox

from core.file_processor import (
    process_single_file
)

from core.dwca_processor import (
    process_dwca
)

from core.constants import (
    APP_TITLE,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT
)


class MainWindow:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            APP_TITLE
        )

        self.root.geometry(
            f"{DEFAULT_WINDOW_WIDTH}x"
            f"{DEFAULT_WINDOW_HEIGHT}"
        )

        self.root.resizable(
            False,
            False
        )

        self.create_widgets()

    # --------------------------------------------------
    # INTERFAZ
    # --------------------------------------------------

    def create_widgets(self):

        title = tk.Label(
            self.root,
            text=APP_TITLE,
            font=("Arial", 18, "bold")
        )

        title.pack(
            pady=(20, 10)
        )

        description = """
Esta herramienta permite:

• Añadir UUID a archivos CSV, TSV y TXT delimitados.

• Transformar un Darwin Core Archive (DwC-A).

• Sustituir identificadores del Core por UUID.

• Propagar automáticamente dichos UUID
  a todas las extensiones.

• Conservar los identificadores originales
  en columnas *_Old.

• Generar automáticamente un nuevo meta.xml.

• Crear un nuevo DwC-A comprimido.

MODOS

UUID determinista:
Genera siempre el mismo UUID
para el mismo identificador.

UUID aleatorio:
Genera UUID distintos en cada ejecución.

Los archivos originales nunca se modifican.
"""

        text = tk.Label(
            self.root,
            text=description,
            justify="left",
            anchor="w",
            font=("Arial", 10)
        )

        text.pack(
            padx=20,
            pady=10,
            fill="x"
        )

        frame = tk.Frame(
            self.root
        )

        frame.pack(
            pady=20
        )

        btn_file = tk.Button(
            frame,
            text="Añadir UUID a un archivo",
            width=40,
            height=2,
            font=("Arial", 11, "bold"),
            command=self.process_file
        )

        btn_file.pack(
            pady=5
        )

        btn_dwca_det = tk.Button(
            frame,
            text="Modificar DwC-A con UUID deterministas",
            width=40,
            height=2,
            font=("Arial", 11, "bold"),
            command=self.process_dwca_deterministic
        )

        btn_dwca_det.pack(
            pady=5
        )

        btn_dwca_rand = tk.Button(
            frame,
            text="Modificar DwC-A con UUID aleatorios",
            width=40,
            height=2,
            font=("Arial", 11, "bold"),
            command=self.process_dwca_random
        )

        btn_dwca_rand.pack(
            pady=5
        )

        btn_exit = tk.Button(
            frame,
            text="Salir",
            width=40,
            command=self.root.destroy
        )

        btn_exit.pack(
            pady=(15, 0)
        )

    # --------------------------------------------------
    # ARCHIVO INDIVIDUAL
    # --------------------------------------------------

    def process_file(self):

        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[
                (
                    "Archivos delimitados",
                    "*.csv *.tsv *.txt"
                ),
                (
                    "Todos los archivos",
                    "*.*"
                )
            ]
        )

        if not file_path:
            return

        try:

            output_file = (
                process_single_file(
                    file_path
                )
            )

            messagebox.showinfo(
                "Completado",
                f"Archivo generado:\n\n{output_file}"
            )

        except Exception as ex:

            messagebox.showerror(
                "Error",
                str(ex)
            )

    # --------------------------------------------------
    # DWCA DETERMINISTA
    # --------------------------------------------------

    def process_dwca_deterministic(
        self
    ):

        self.process_dwca(
            deterministic=True
        )

    # --------------------------------------------------
    # DWCA ALEATORIO
    # --------------------------------------------------

    def process_dwca_random(
        self
    ):

        self.process_dwca(
            deterministic=False
        )

    # --------------------------------------------------
    # DWCA
    # --------------------------------------------------

    def process_dwca(
        self,
        deterministic
    ):

        dwca_file = filedialog.askopenfilename(
            title="Seleccionar DwC-A",
            filetypes=[
                (
                    "Darwin Core Archive",
                    "*.zip"
                )
            ]
        )

        if not dwca_file:
            return

        try:

            result = process_dwca(
                dwca_file,
                deterministic
            )

            mode = (
                "Determinista"
                if deterministic
                else
                "Aleatorio"
            )

            messagebox.showinfo(
                "Proceso completado",
                (
                    f"Modo: {mode}\n\n"
                    f"Registros Core: "
                    f"{result.records_core}\n\n"
                    f"Registros Extensions: "
                    f"{result.records_extensions}\n\n"
                    f"Archivo generado:\n\n"
                    f"{result.output_zip}"
                )
            )

        except Exception as ex:

            messagebox.showerror(
                "Error",
                str(ex)
            )

    # --------------------------------------------------
    # EJECUCIÓN
    # --------------------------------------------------

    def run(self):

        self.root.mainloop()