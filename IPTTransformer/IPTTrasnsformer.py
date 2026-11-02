"""
===============================================================================
IPTTransformer.py - Punto de Entrada Principal (Estructuración DwC-A / IPT)
===============================================================================
"""

import sys
import os
import tkinter as tk

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from ipt_welcome import IPTWelcomeFrame
from ipt_viewer import IPTViewerWindow

def main():
    root = tk.Tk()
    root.title("IPT-Transformer - Validador y Estructurador Darwin Core Archive")
    root.geometry("900x700")
    root.minsize(750, 600)
    root.resizable(True, True)

    viewer = IPTViewerWindow(root)
    welcome = IPTWelcomeFrame(root, viewer)
    
    viewer.set_welcome(welcome)
    welcome.pack(fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()