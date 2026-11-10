"""
column_selector.py

Diálogo para configurar las columnas a concatenar, junto con prefijo manual
y semilla manual para la generación del UUID determinista.
"""

import tkinter as tk
from tkinter import messagebox


class ColumnSelectorDialog(tk.Toplevel):

    def __init__(self, parent, file_name, columns):
        super().__init__(parent)
        self.title(f"Configurar UUID Determinista - {file_name}")
        self.geometry("500x580")
        self.transient(parent)
        self.grab_set()

        self.columns = columns
        self.selected_columns = []
        self.prefix = ""
        self.seed = ""
        self.use_sequence_fallback = False
        self.cancelled = False

        self.create_widgets()

    def create_widgets(self):
        lbl = tk.Label(
            self,
            text="Configura los parámetros para la generación del UUID determinista:\nEl formato será: Prefijo-Semilla-Campo1-Campo2...",
            font=("Arial", 9, "bold"),
            justify="left"
        )
        lbl.pack(padx=15, pady=10, anchor="w")

        # Frame para Prefijo y Semilla
        frame_inputs = tk.LabelFrame(self, text=" Parámetros Manuales ", font=("Arial", 9, "bold"), padx=10, pady=5)
        frame_inputs.pack(padx=15, pady=5, fill="x")

        tk.Label(frame_inputs, text="Prefijo manual (opcional):", font=("Arial", 9)).grid(row=0, column=0, sticky="w", pady=3)
        self.entry_prefix = tk.Entry(frame_inputs, width=25)
        self.entry_prefix.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        tk.Label(frame_inputs, text="Semilla manual (opcional):", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=3)
        self.entry_seed = tk.Entry(frame_inputs, width=25)
        self.entry_seed.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        # Listado de columnas con Scroll
        lbl_cols = tk.Label(self, text="Selecciona las columnas a concatenar:", font=("Arial", 9, "bold"))
        lbl_cols.pack(padx=15, pady=(10, 2), anchor="w")

        frame_list = tk.Frame(self)
        frame_list.pack(padx=15, pady=5, fill="both", expand=True)

        canvas = tk.Canvas(frame_list, borderwidth=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame_list, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.vars = []
        for col in self.columns:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(scrollable_frame, text=col, variable=var, anchor="w")
            cb.pack(anchor="w", fill="x", pady=2)
            self.vars.append((col, var))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Opciones de secuencia fallback
        frame_options = tk.Frame(self)
        frame_options.pack(padx=15, pady=5, fill="x")

        self.fallback_var = tk.BooleanVar(value=True)
        chk_fallback = tk.Checkbutton(
            frame_options,
            text="Si no hay valores en las columnas, usar secuencia n+1",
            variable=self.fallback_var,
            font=("Arial", 8, "italic")
        )
        chk_fallback.pack(anchor="w")

        # Botones
        frame_buttons = tk.Frame(self)
        frame_buttons.pack(padx=15, pady=15, fill="x")

        btn_back = tk.Button(
            frame_buttons,
            text="Volver / Reconfigurar",
            bg="#D32F2F",
            fg="white",
            font=("Arial", 9, "bold"),
            width=18,
            command=self.on_back
        )
        btn_back.pack(side="left", padx=5)

        btn_ok = tk.Button(
            frame_buttons,
            text="Confirmar",
            bg="#2E7D32",
            fg="white",
            font=("Arial", 9, "bold"),
            width=18,
            command=self.on_confirm
        )
        btn_ok.pack(side="right", padx=5)

    def on_back(self):
        self.cancelled = True
        self.destroy()

    def on_confirm(self):
        self.selected_columns = [col for col, var in self.vars if var.get()]
        self.prefix = self.entry_prefix.get().strip()
        self.seed = self.entry_seed.get().strip()
        self.use_sequence_fallback = self.fallback_var.get()

        if not self.selected_columns and not self.prefix and not self.seed and not self.use_sequence_fallback:
            messagebox.showwarning(
                "Advertencia",
                "Debes seleccionar al menos una columna, escribir un prefijo/semilla o activar la secuencia n+1."
            )
            return

        self.cancelled = False
        self.destroy()