"""Entrada principal: python ipt_transformer.py."""

import logging
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk


def main():
    log_dir = Path.home() / ".ipt_transformer"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "application.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8"
    )
    root = None
    try:
        from ipt_welcome import IPTWelcomeWindow
        root = tk.Tk()
        root.title("IPT-Transformer | Normalización y mapeo")
        root.geometry("1200x760")
        root.minsize(1000, 640)
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        def report_error(exc_type, exc, tb):
            logging.error("Error de interfaz", exc_info=(exc_type, exc, tb))
            messagebox.showerror(
                "Error de aplicación",
                f"{exc}\n\nEl diagnóstico se ha guardado en {log_dir / 'application.log'}.",
                parent=root
            )
        root.report_callback_exception = report_error
        IPTWelcomeWindow(root).pack(fill="both", expand=True)
        root.mainloop()
        return 0
    except Exception:
        logging.exception("Error al iniciar")
        print(f"No se pudo iniciar IPT-Transformer. Consulte {log_dir / 'application.log'}.",
              file=sys.stderr)
        if root is not None:
            root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
