"""
===============================================================================
ParseScientificNames.py - Punto de Entrada Principal (Suite de Parseo Taxonómico)
===============================================================================
"""

import sys
import os
import tkinter as tk

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from taxa_welcome import TaxaWelcomeFrame
from taxa_viewer import TaxaViewerFrame

def main():
    root = tk.Tk()
    root.title("ParseScientificNames - Suite de Parseo Taxonómico y Contraste GBIF")
    root.geometry("850x700")  # Tamaño inicial cómodo
    root.minsize(700, 550)    # Tamaño mínimo para que no se deforme
    
    # Habilitar explícitamente el redimensionamiento dinámico (ancho y alto)
    root.resizable(True, True)

    # Inicializar marcos de la interfaz
    viewer = TaxaViewerFrame(root)
    welcome = TaxaWelcomeFrame(root, viewer)
    
    # Enlazar la navegación de vuelta
    viewer.set_welcome(welcome)
    
    # Mostrar pantalla de bienvenida inicialmente
    welcome.pack(fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()