"""
dwca_downloader.py
==================
Gestor de búsqueda local inteligente de ejecutables .exe o scripts .py.
"""

from __future__ import annotations
import sys
from pathlib import Path
from tkinter import messagebox, filedialog

GITHUB_RELEASES_PAGE = "https://github.com/GBIFes/herramientas-ligeras-transformacion-dwc/releases/tag/Herramientas_Ligeras"


class DwCaDownloader:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent

    def locate_or_acquire_executable(self) -> Path | None:
        target_names = ["VisorDwCa.exe", "VisorDwCa.py"]
        
        for name in target_names:
            candidates = [
                self.base_dir / name,
                self.base_dir.parent / name,
                self.base_dir / "VisorDwCa" / name,
                Path.home() / "Downloads" / name,
                Path.home() / "Downloads" / "VisorDwCa" / name
            ]
            for cand in candidates:
                if cand.exists():
                    return cand

        answer = messagebox.askyesno(
            "VisorDwCa no encontrado",
            "No se ha encontrado el programa VisorDwCa en el equipo.\n\n"
            "¿Desea abrir la página oficial de GitHub para descargarlo?"
        )

        if answer:
            import webbrowser
            try:
                webbrowser.open_new_tab(GITHUB_RELEASES_PAGE)
            except Exception:
                pass

        messagebox.showinfo(
            "Localización Manual",
            "Por favor, seleccione el archivo ejecutable o script de VisorDwCa en su equipo."
        )
        file_path = filedialog.askopenfilename(
            title="Seleccionar VisorDwCa",
            initialdir=str(self.base_dir),
            filetypes=[("Aplicaciones y Scripts", "*.exe *.py"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            return Path(file_path)

        return None