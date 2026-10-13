import tkinter as tk
from tkinter import filedialog
import zipfile
import os

from dwca_access import export_zip_to_access
from dwca_excel import export_zip_to_excel


class WelcomeFrame(tk.Frame):
    def __init__(self, root, viewer):
        super().__init__(root)
        self.root = root
        self.viewer = viewer
        self.eml_viewer_class = None

        tk.Label(
            self,
            text="Visor DwC-A GBIF.ES",
            font=("Segoe UI", 22, "bold"),
            fg="#289530"
        ).pack(pady=20)

        tk.Button(
            self,
            text="Abrir DwC-A (ZIP)",
            font=("Segoe UI", 14),
            bg="#289530",
            fg="white",
            command=self.open_zip
        ).pack(pady=10)

        tk.Button(
            self,
            text="Exportar DwC-A a Access (.accdb)",
            font=("Segoe UI", 14),
            bg="#1f6fb2",
            fg="white",
            command=lambda: export_zip_to_access(self.root)
        ).pack(pady=10)

        tk.Button(
            self,
            text="Exportar DwC-A a Excel (.xlsx)",
            font=("Segoe UI", 14),
            bg="#217346",
            fg="white",
            command=lambda: export_zip_to_excel(self.root)
        ).pack(pady=10)

    def set_eml_viewer_class(self, cls):
        """Recibe la clase EMLViewer para abrir metadata en ventana independiente."""
        self.eml_viewer_class = cls

    def open_zip(self):
        """Selecciona ZIP, lo extrae y abre meta.xml + eml.xml."""
        path = filedialog.askopenfilename(
            title="Seleccionar DwC-A (ZIP)",
            filetypes=[("DwC-A ZIP", "*.zip")]
        )
        if not path:
            return

        # Carpeta temporal donde se extrae el ZIP
        temp = os.path.join(os.path.dirname(path), "_dwca_temp")
        if not os.path.exists(temp):
            os.makedirs(temp)

        # Extraer ZIP
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(temp)

        # Detectar meta.xml y eml.xml
        meta = os.path.join(temp, "meta.xml")
        eml = os.path.join(temp, "eml.xml")

        # Abrir visor principal DwC-A
        self.pack_forget()
        self.viewer.load(meta)
        self.viewer.pack(fill="both", expand=True)

        # Abrir visor EML en ventana independiente
        if self.eml_viewer_class and os.path.exists(eml):
            self.eml_viewer_class(self.root, eml)
