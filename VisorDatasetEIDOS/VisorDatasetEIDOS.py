"""
VisorDatasetEIDOS.py
====================
Punto de entrada principal para la aplicación EIDOS Multivisor.
Inicializa la interfaz gráfica con soporte para manejo limpio de interrupciones.
"""

from __future__ import annotations
import sys
import tkinter as tk
from pathlib import Path

# Asegurar que el directorio de trabajo actual permite importar los módulos locales
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from gui import EidosGUI


def main():
    """Inicializa la raíz de Tkinter y lanza la aplicación EIDOS Multivisor."""
    root = tk.Tk()
    
    # Configurar protocolo de cierre para una salida limpia
    app = EidosGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        # Cierre controlado si se interrumpe desde la consola (Ctrl+C)
        print("\nAplicación interrumpida por el usuario desde la consola. Cerrando...")
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()