"""
main.py
=======

Punto de entrada de EIDOS Multivisor con diagnóstico de errores.
"""

import sys
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

from gui import EidosGUI


def configure_style():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "Treeview",
        rowheight=24
    )

    style.configure(
        "Treeview.Heading",
        font=(
            "Segoe UI",
            9,
            "bold"
        )
    )


def center_window(
    root,
    width=1400,
    height=850
):
    # Ajustado ligeramente por seguridad a 1400x850 para evitar problemas en pantallas pequeñas
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Si la pantalla es más pequeña que el tamaño por defecto, ajustamos
    if width > screen_width:
        width = screen_width - 100
    if height > screen_height:
        height = screen_height - 100

    x = int((screen_width - width) / 2)
    y = int((screen_height - height) / 2)

    root.geometry(f"{width}x{height}+{x}+{y}")


def main():
    try:
        root = tk.Tk()
        root.title("EIDOS Multivisor Avanzado")

        center_window(root)
        configure_style()

        app = EidosGUI(root)

        root.protocol(
            "WM_DELETE_WINDOW",
            app.on_close
        )

        root.mainloop()

    except Exception as ex:
        # Si ocurre cualquier error crítico al arrancar, se muestra en un cuadro de diálogo
        root_err = tk.Tk()
        root_err.withdraw()
        error_detalle = traceback.format_exc()
        messagebox.showerror(
            "Error Crítico al Iniciar",
            f"Se ha producido un error:\n\n{ex}\n\nDetalles:\n{error_detalle}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()