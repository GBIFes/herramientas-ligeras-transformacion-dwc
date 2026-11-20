"""
VisorDatasetEIDOS.py
====================
Punto de entrada principal para el Multivisor EIDOS y Exportador Darwin Core (DwCa).
Inicializa la aplicación gráfica (Tkinter) y gestiona el bucle de eventos.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# Asegurar que el directorio actual está en el path de sys para importaciones relativas
current_dir = Path(__file__).parent.resolve()
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from gui import EidosGUI


def main():
    """Función principal de arranque de la interfaz gráfica."""
    try:
        root = tk.Tk()
        
        # Opcional: configurar estilos o icono si estuviera disponible
        try:
            root.iconbitmap(default="")
        except Exception:
            pass

        app = EidosGUI(root)
        
        # Manejador seguro de cierre de ventana
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        
        # Bucle principal de eventos de Tkinter (mantiene la ventana abierta)
        root.mainloop()
        
    except Exception as ex:
        print(f"Error crítico al iniciar la aplicación: {ex}")
        try:
            messagebox.showerror("Error Crítico", f"No se pudo iniciar la aplicación:\n\n{ex}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()