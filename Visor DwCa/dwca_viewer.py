import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from dwca_loader import DwcaLoader
from dwca_model import DwcaModel

def is_url(text):
    return isinstance(text, str) and (text.startswith("http://") or text.startswith("https://"))

class ViewerFrame(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root

        self.model = None
        self.core_fields = []
        self.core_rows = []
        self.extensions = []
        self.ext_data = {}
        self.filtered_indices = None
        self.active_index = 0
        self.welcome_frame = None
        self.core_path = ""

        # -------------------------------
        # BARRA SUPERIOR
        # -------------------------------
        self.top_bar = tk.Frame(self, bg="#e0e0e0")
        self.top_bar.pack(fill="x")

        self.lbl_path = tk.Label(
            self.top_bar,
            text="Archivo cargado: (ninguno)",
            font=("Segoe UI", 10, "bold"),
            bg="#e0e0e0",
            anchor="w"
        )
        self.lbl_path.pack(side="left", fill="x", padx=10, pady=5)

        self.btn_close = tk.Button(
            self.top_bar,
            text="Cerrar visor",
            font=("Segoe UI", 10, "bold"),
            bg="#d9534f",
            fg="white",
            relief="flat",
            command=self.close_viewer
        )
        self.btn_close.pack(side="right", padx=10, pady=5)

        # -------------------------------
        # PANEL PRINCIPAL
        # -------------------------------
        main = tk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        # -------------------------------
        # PANEL IZQUIERDO (CORE)
        # -------------------------------
        self.left = tk.Frame(main)
        main.add(self.left)

        self.left_canvas = tk.Canvas(self.left)
        self.left_canvas.pack(side="left", fill="both", expand=True)

        self.left_scroll = tk.Scrollbar(self.left, orient="vertical", command=self.left_canvas.yview)
        self.left_scroll.pack(side="right", fill="y")

        self.left_canvas.configure(yscrollcommand=self.left_scroll.set)

        self.left_record_frame = tk.Frame(self.left_canvas)
        self.left_canvas.create_window((0, 0), window=self.left_record_frame, anchor="nw")

        self.left_record_frame.bind(
            "<Configure>",
            lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        )

        # -------------------------------
        # PANEL DERECHO (EXTENSIONES)
        # -------------------------------
        self.right = tk.Frame(main)
        main.add(self.right)

        self.tabs = ttk.Notebook(self.right)
        self.tabs.pack(fill="both", expand=True)

        # -------------------------------
        # NAVEGACIÓN
        # -------------------------------
        nav = tk.Frame(self.right)
        nav.pack(fill="x", pady=5)

        tk.Button(nav, text="⏮", width=3, command=self.go_first).pack(side="left")
        tk.Button(nav, text="◀", width=3, command=self.go_prev).pack(side="left")
        tk.Button(nav, text="▶", width=3, command=self.go_next).pack(side="left")
        tk.Button(nav, text="⏭", width=3, command=self.go_last).pack(side="left")

        tk.Label(nav, text="Ir a:").pack(side="left", padx=5)
        self.goto_var = tk.StringVar()
        self.goto_entry = tk.Entry(nav, textvariable=self.goto_var, width=6)
        self.goto_entry.pack(side="left")
        tk.Button(nav, text="Ir", command=self.goto_record).pack(side="left", padx=5)

        self.nav_label = tk.Label(nav, text="0 / 0")
        self.nav_label.pack(side="left", padx=10)

        # -------------------------------
        # FILTRADO
        # -------------------------------
        filter_frame = tk.Frame(self.right)
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="Campo:").pack(side="left")
        self.filter_field_var = tk.StringVar()
        self.filter_field_cb = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_field_var,
            values=self.core_fields,
            state="readonly",
            width=20
        )
        self.filter_field_cb.pack(side="left", padx=5)

        tk.Label(filter_frame, text="Valor:").pack(side="left")
        self.filter_value_entry = tk.Entry(filter_frame, width=20)
        self.filter_value_entry.pack(side="left", padx=5)

        tk.Button(filter_frame, text="Filtrar", command=self.apply_filter_inline).pack(side="left", padx=5)
        tk.Button(filter_frame, text="Mostrar todos", command=self.clear_filter).pack(side="left", padx=5)

    # ---------------------------------------------------------
    # VINCULAR WELCOME
    # ---------------------------------------------------------
    def set_welcome(self, welcome_frame):
        self.welcome_frame = welcome_frame

    def close_viewer(self):
        if self.welcome_frame is not None:
            self.pack_forget()
            self.welcome_frame.pack(fill="both", expand=True)

    # ---------------------------------------------------------
    # CARGA DE DATOS
    # ---------------------------------------------------------
    def load(self, meta_path):
        self.core_path = meta_path
        self.lbl_path.config(text=f"Archivo cargado: {meta_path}")

        loader = DwcaLoader(meta_path)
        core_fields, core_rows, extensions, ext_data = loader.load()

        self.model = DwcaModel(core_fields, core_rows, extensions, ext_data)
        self.core_fields = core_fields
        self.core_rows = core_rows
        self.extensions = extensions
        self.ext_data = ext_data
        self.filtered_indices = None
        self.active_index = 0

        self.filter_field_cb["values"] = self.core_fields

        self.load_record()
        self.load_ext_tabs()
        self.update_right_window()

    # ---------------------------------------------------------
    # PANEL IZQUIERDO (CORE)
    # ---------------------------------------------------------
    def load_record(self):
        for w in self.left_record_frame.winfo_children():
            w.destroy()

        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        if not indices:
            self.nav_label.config(text="0 / 0")
            return

        idx = indices[self.active_index]
        row = self.core_rows[idx]

        for i, field in enumerate(self.core_fields):
            val = row[i] if i < len(row) else ""

            lbl_field = tk.Label(
                self.left_record_frame,
                text=field + ":",
                font=("Segoe UI", 9, "bold"),
                anchor="nw",
                wraplength=350
            )
            lbl_field.grid(row=i, column=0, sticky="nw", padx=4, pady=0)

            if is_url(val):
                btn = tk.Button(
                    self.left_record_frame,
                    text=val,
                    fg="blue",
                    cursor="hand2",
                    relief="flat",
                    font=("Segoe UI", 9),
                    wraplength=350,
                    justify="left",
                    command=lambda v=val: webbrowser.open(v)
                )
                btn.grid(row=i, column=1, sticky="nw", padx=4, pady=0)
            else:
                lbl_val = tk.Label(
                    self.left_record_frame,
                    text=val,
                    font=("Segoe UI", 9),
                    anchor="nw",
                    wraplength=350,
                    justify="left"
                )
                lbl_val.grid(row=i, column=1, sticky="nw", padx=4, pady=0)

        self.left_record_frame.update_idletasks()
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        self.update_nav_label()

    # ---------------------------------------------------------
    # PANEL DERECHO (EXTENSIONES)
    # ---------------------------------------------------------
    def load_ext_tabs(self):
        for t in self.tabs.tabs():
            self.tabs.forget(t)

        for name, fields in self.extensions:
            frame = tk.Frame(self.tabs)
            self.tabs.add(frame, text=name)

            canvas = tk.Canvas(frame)
            canvas.pack(side="left", fill="both", expand=True)

            scroll = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scroll.pack(side="right", fill="y")

            canvas.configure(yscrollcommand=scroll.set)

            ext_frame = tk.Frame(canvas)
            canvas.create_window((0, 0), window=ext_frame, anchor="nw")

            ext_frame.bind(
                "<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
            )

            frame.ext_frame = ext_frame

    def update_right_window(self, event=None):
        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        if not indices:
            return

        idx = indices[self.active_index]
        row = self.core_rows[idx]

        if "id" in self.core_fields:
            cid = row[self.core_fields.index("id")]
        else:
            cid = row[0]

        for i, (name, fields) in enumerate(self.extensions):
            frame = self.tabs.nametowidget(self.tabs.tabs()[i])
            ext_frame = frame.ext_frame

            for w in ext_frame.winfo_children():
                w.destroy()

            rows = self.ext_data.get(name, {}).get(cid, [])

            r_index = 0
            for r in rows:
                for j, field in enumerate(fields):
                    val = r[j] if j < len(r) else ""

                    lbl_field = tk.Label(
                        ext_frame,
                        text=field + ":",
                        font=("Segoe UI", 9, "bold"),
                        anchor="nw",
                        wraplength=350
                    )
                    lbl_field.grid(row=r_index, column=0, sticky="nw", padx=4, pady=0)

                    lbl_val = tk.Label(
                        ext_frame,
                        text=str(val),
                        font=("Segoe UI", 9),
                        anchor="nw",
                        wraplength=350,
                        justify="left"
                    )
                    lbl_val.grid(row=r_index, column=1, sticky="nw", padx=4, pady=0)

                    r_index += 1

    # ---------------------------------------------------------
    # NAVEGACIÓN
    # ---------------------------------------------------------
    def update_nav_label(self):
        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        if not indices:
            self.nav_label.config(text="0 / 0")
            return
        pos = self.active_index + 1
        total = len(indices)
        self.nav_label.config(text=f"{pos} / {total}")

    def go_first(self):
        self.active_index = 0
        self.load_record()
        self.update_right_window()

    def go_last(self):
        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        self.active_index = len(indices) - 1
        self.load_record()
        self.update_right_window()

    def go_prev(self):
        if self.active_index > 0:
            self.active_index -= 1
            self.load_record()
            self.update_right_window()

    def go_next(self):
        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        if self.active_index < len(indices) - 1:
            self.active_index += 1
            self.load_record()
            self.update_right_window()

    def goto_record(self):
        try:
            num = int(self.goto_var.get())
        except:
            messagebox.showerror("Error", "Debe ser un número entero.")
            return

        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices

        if num < 1 or num > len(indices):
            messagebox.showerror("Error", "Número fuera de rango.")
            return

        self.active_index = num - 1
        self.load_record()
        self.update_right_window()

    # ---------------------------------------------------------
    # FILTRADO
    # ---------------------------------------------------------
    def apply_filter_inline(self):
        field = self.filter_field_var.get()
        value = self.filter_value_entry.get()

        if not field:
            return

        if value.strip() == "":
            self.clear_filter()
            return

        try:
            idx = self.core_fields.index(field)
        except ValueError:
            return

        self.filtered_indices = [
            i for i, row in enumerate(self.core_rows)
            if idx < len(row) and value.lower() in str(row[idx]).lower()
        ]

        if not self.filtered_indices:
            messagebox.showinfo("Filtro", "Ningún registro coincide con el filtro.")
            self.filtered_indices = None

        self.active_index = 0
        self.load_record()
        self.update_right_window()

    def clear_filter(self):
        self.filtered_indices = None
        self.active_index = 0
        self.load_record()
        self.update_right_window()
