import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET
import csv
import os
import json
import webbrowser

# ---------------------------
# Utilidades generales
# ---------------------------

def short(term):
    return term.rsplit("/", 1)[-1] if term else ""

def is_url(text):
    return isinstance(text, str) and (text.startswith("http://") or text.startswith("https://"))

# ---------------------------
# Pantalla de bienvenida con logo vectorial GBIF.ES (con letra)
# ---------------------------

class WelcomeWindow:
    def __init__(self, root, on_meta_selected):
        self.root = root
        self.on_meta_selected = on_meta_selected

        self.win = tk.Toplevel(root)
        self.win.title("GBIF.ES - Visor DwC-A")
        self.win.geometry("600x400")
        self.win.resizable(False, False)
        self.win.configure(bg="#ffffff")

        # Marco principal
        frame = tk.Frame(self.win, bg="#ffffff")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Canvas para logo vectorial
        self.canvas = tk.Canvas(frame, width=260, height=160, bg="#ffffff", highlightthickness=0)
        self.canvas.pack(pady=10)

        self.draw_gbif_logo_with_text()

        # Título
        title = tk.Label(
            frame,
            text="Visor DwC-A GBIF.ES",
            font=("Segoe UI", 16, "bold"),
            bg="#ffffff",
            fg="#289530"
        )
        title.pack(pady=(10, 5))

        # Descripción
        desc = tk.Label(
            frame,
            text=(
                "Visualiza y edita archivos Darwin Core Archive (DwC-A)\n"
                "a partir de un meta.xml del IPT."
            ),
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#333333",
            justify="center"
        )
        desc.pack(pady=(0, 15))

        # Botón para seleccionar meta.xml
        btn_meta = tk.Button(
            frame,
            text="Seleccionar meta.xml...",
            font=("Segoe UI", 10, "bold"),
            bg="#289530",
            fg="#ffffff",
            activebackground="#1f7a28",
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=5,
            command=self.select_meta
        )
        btn_meta.pack(pady=(0, 10))

        # Botón salir
        btn_exit = tk.Button(
            frame,
            text="Salir",
            font=("Segoe UI", 9),
            bg="#dddddd",
            fg="#333333",
            relief="flat",
            command=self.win.destroy
        )
        btn_exit.pack(pady=(5, 0))

        # Centrar sobre la pantalla
        self.center_window(self.win)

        # Bloquear hasta que se cierre
        self.win.transient(root)
        self.win.grab_set()

    def center_window(self, win):
        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def draw_gbif_logo_with_text(self):
        """
        Logo vectorial simplificado GBIF.ES con letra:
        - Fondo blanco
        - Símbolo verde (hoja/círculo)
        - Texto 'GBIF.ES' en gris oscuro
        """
        c = self.canvas
        c.delete("all")

        # Fondo
        c.create_rectangle(0, 0, 260, 160, fill="#ffffff", outline="")

        # Círculo verde (símbolo)
        c.create_oval(40, 30, 120, 110, fill="#289530", outline="#289530")

        # Hoja blanca estilizada dentro del círculo
        c.create_polygon(
            80, 40,
            95, 60,
            90, 80,
            70, 95,
            60, 80,
            65, 60,
            smooth=True,
            fill="#ffffff",
            outline="#ffffff"
        )

        # Nervio de la hoja
        c.create_line(80, 45, 75, 90, fill="#ffffff", width=2)

        # Texto GBIF.ES
        c.create_text(
            160, 70,
            text="GBIF.ES",
            font=("Segoe UI", 20, "bold"),
            fill="#333333",
            anchor="w"
        )

    def select_meta(self):
        path = filedialog.askopenfilename(
            parent=self.win,
            title="Seleccionar meta.xml",
            filetypes=[("meta.xml", "meta.xml"), ("XML", "*.xml"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        self.win.destroy()
        self.on_meta_selected(path)

# ---------------------------
# Visor DwC-A (corregido)
# ---------------------------

class Viewer:
    def __init__(self, root, meta_path=None):
        self.root = root
        self.root.title("Visor DWC Estrella - GBIF.ES")

        self.meta = None
        self.core_file = ""
        self.core_fields = []
        self.core_rows = []
        self.extensions = []
        self.ext_data = {}
        self.core_record_line_map = []
        self.filtered_indices = None

        top = tk.Frame(root)
        top.pack(fill="x")

        tk.Button(top, text="Abrir meta.xml", command=self.open_meta).pack(side="left", padx=5)
        tk.Button(top, text="Buscar", command=self.search_dialog).pack(side="left", padx=5)
        tk.Button(top, text="Filtrar", command=self.filter_dialog).pack(side="left", padx=5)
        tk.Button(top, text="Quitar filtro", command=self.clear_filter).pack(side="left", padx=5)
        tk.Button(top, text="Exportar registro", command=self.export_active_record).pack(side="left", padx=5)

        main = tk.PanedWindow(root, orient="horizontal")
        main.pack(fill="both", expand=True)

        left = tk.Frame(main)
        right = tk.Frame(main)
        main.add(left)
        main.add(right)

        self.core_text = tk.Text(left, wrap="word")
        self.core_text.pack(fill="both", expand=True)

        core_y = tk.Scrollbar(left, orient="vertical", command=self.core_text.yview)
        core_y.pack(side="right", fill="y")
        core_x = tk.Scrollbar(left, orient="horizontal", command=self.core_text.xview)
        core_x.pack(side="bottom", fill="x")
        self.core_text.configure(yscrollcommand=core_y.set, xscrollcommand=core_x.set)

        self.core_text.tag_config("field", foreground="#004080", font=("Segoe UI", 10, "bold"))
        self.core_text.tag_config("value", foreground="#000000", font=("Segoe UI", 10))
        self.core_text.tag_config("sep", background="#b0b0b0", font=("Segoe UI", 1))

        self.core_text.bind("<ButtonRelease-1>", self.update_right_window)
        self.core_text.bind("<KeyRelease>", self.update_right_window)
        self.core_text.bind("<MouseWheel>", self.update_right_window)

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)

        edit_frame = tk.Frame(right)
        edit_frame.pack(fill="x")
        tk.Label(edit_frame, text="Campo:").pack(side="left")
        self.edit_field_var = tk.StringVar()
        self.edit_field_entry = ttk.Combobox(edit_frame, textvariable=self.edit_field_var, state="readonly")
        self.edit_field_entry.pack(side="left", padx=5)
        tk.Label(edit_frame, text="Valor:").pack(side="left")
        self.edit_value_entry = tk.Entry(edit_frame, width=40)
        self.edit_value_entry.pack(side="left", padx=5)
        tk.Button(edit_frame, text="Guardar en core", command=self.save_edit_core).pack(side="left", padx=5)
        tk.Button(edit_frame, text="Guardar en extensión", command=self.save_edit_extension).pack(side="left", padx=5)

        if meta_path:
            self.load_meta(meta_path)

    # ---------------------------
    # Carga de meta.xml y DwC-A
    # ---------------------------

    def open_meta(self):
        path = filedialog.askopenfilename(
            title="Seleccionar meta.xml",
            filetypes=[("meta.xml", "meta.xml"), ("XML", "*.xml"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        self.load_meta(path)

    def load_meta(self, path):
        try:
            self.meta = ET.parse(path).getroot()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer meta.xml:\n{e}")
            return

        base = os.path.dirname(path)

        # CORE sin namespace
        core = self.meta.find("core")
        if core is None:
            messagebox.showerror("Error", "No se encontró elemento <core> en meta.xml.")
            return

        loc_nodes = core.findall(".//location")
        if not loc_nodes:
            messagebox.showerror("Error", "No se encontró <location> para el core en meta.xml.")
            return
        self.core_file = os.path.join(base, loc_nodes[-1].text.strip())

        # Índice de ID y campos
        id_elem = core.find("id")
        if id_elem is None or id_elem.get("index") is None:
            messagebox.showerror("Error", "No se encontró <id index=\"...\"> en el core.")
            return
        core_id_index = int(id_elem.get("index"))

        fields_raw = core.findall("field")
        # Ordenar por índice
        fields_raw_sorted = sorted(fields_raw, key=lambda f: int(f.get("index")))
        max_index = max([core_id_index] + [int(f.get("index")) for f in fields_raw_sorted])

        # Construir lista de campos según índice
        index_to_term = {}
        index_to_term[core_id_index] = "id"
        for f in fields_raw_sorted:
            idx = int(f.get("index"))
            index_to_term[idx] = short(f.get("term"))

        self.core_fields = [index_to_term.get(i, f"col_{i}") for i in range(max_index + 1)]

        # Leer core TSV
        self.core_rows = []
        try:
            with open(self.core_file, encoding="utf-8") as f:
                r = csv.reader(f, delimiter="\t")
                header = next(r, None)  # ignoramos cabecera si existe
                for row in r:
                    # Asegurar longitud
                    if len(row) < len(self.core_fields):
                        row = row + [""] * (len(self.core_fields) - len(row))
                    self.core_rows.append(row)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el archivo core:\n{e}")
            return

        # Extensiones
        self.extensions = []
        self.ext_data = {}

        for ext in self.meta.findall("extension"):
            loc_nodes = ext.findall(".//location")
            if not loc_nodes:
                continue
            fname = os.path.join(base, loc_nodes[-1].text.strip())

            fields_raw_ext = ext.findall("field")
            fields_raw_ext_sorted = sorted(fields_raw_ext, key=lambda f: int(f.get("index")))
            max_idx_ext = max(int(f.get("index")) for f in fields_raw_ext_sorted)

            # coreid
            coreid_elem = ext.find("coreid")
            if coreid_elem is None or coreid_elem.get("index") is None:
                continue
            cid_index = int(coreid_elem.get("index"))

            # Construir lista de campos de extensión
            index_to_term_ext = {}
            index_to_term_ext[cid_index] = "id"
            for f in fields_raw_ext_sorted:
                idx = int(f.get("index"))
                index_to_term_ext[idx] = short(f.get("term"))

            fields = [index_to_term_ext.get(i, f"col_{i}") for i in range(max_idx_ext + 1)]

            rows = {}
            try:
                with open(fname, encoding="utf-8") as f:
                    r = csv.reader(f, delimiter="\t")
                    header = next(r, None)
                    for row in r:
                        if len(row) < len(fields):
                            row = row + [""] * (len(fields) - len(row))
                        cid = row[cid_index]
                        rows.setdefault(cid, []).append(row)
            except Exception:
                continue

            tab_name = os.path.basename(fname)
            self.extensions.append((tab_name, fields))
            self.ext_data[tab_name] = rows

        self.filtered_indices = None
        self.edit_field_entry["values"] = self.core_fields
        self.load_core()
        self.load_ext_tabs()
        self.update_right_window()

    # ---------------------------
    # Renderizado core + extensiones
    # ---------------------------

    def insert_field(self, widget, field, value):
        widget.insert("end", field + ": ", "field")
        if is_url(value):
            btn = tk.Button(widget, text=value, fg="blue", cursor="hand2",
                            relief="flat", command=lambda v=value: webbrowser.open(v))
            widget.window_create("end", window=btn)
            widget.insert("end", "\n")
        else:
            widget.insert("end", value + "\n", "value")

    def load_core(self):
        self.core_text.delete("1.0", "end")
        self.core_record_line_map = []
        line = 1

        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices

        for idx in indices:
            row = self.core_rows[idx]
            self.core_record_line_map.append(line)
            for i, field in enumerate(self.core_fields):
                val = row[i] if i < len(row) else ""
                self.insert_field(self.core_text, field, val)
                line += 1
            self.core_text.insert("end", "\n", "sep")
            line += 1

    def load_ext_tabs(self):
        for t in self.tabs.tabs():
            self.tabs.forget(t)

        for name, fields in self.extensions:
            frame = tk.Frame(self.tabs)
            text = tk.Text(frame, wrap="word")
            text.pack(fill="both", expand=True)

            y = tk.Scrollbar(frame, orient="vertical", command=text.yview)
            y.pack(side="right", fill="y")
            x = tk.Scrollbar(frame, orient="horizontal", command=text.xview)
            x.pack(side="bottom", fill="x")
            text.configure(yscrollcommand=y.set, xscrollcommand=x.set)

            text.tag_config("field", foreground="#004080", font=("Segoe UI", 10, "bold"))
            text.tag_config("value", foreground="#000000", font=("Segoe UI", 10))
            text.tag_config("sep", background="#b0b0b0", font=("Segoe UI", 1))

            self.tabs.add(frame, text=name)
            frame.text = text

    def get_active_core_index(self):
        if not self.core_record_line_map:
            return 0
        cursor_line = int(self.core_text.index("insert").split(".")[0])
        record_index = 0
        for i, start_line in enumerate(self.core_record_line_map):
            if cursor_line >= start_line:
                record_index = i

        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        record_index = max(0, min(record_index, len(indices) - 1))
        return indices[record_index]

    def update_right_window(self, event=None):
        if not self.core_rows or not self.extensions:
            return

        core_idx = self.get_active_core_index()
        cid = self.core_rows[core_idx][self.core_fields.index("id")] if "id" in self.core_fields else self.core_rows[core_idx][0]

        for i, (name, fields) in enumerate(self.extensions):
            frame = self.tabs.nametowidget(self.tabs.tabs()[i])
            text = frame.text
            text.delete("1.0", "end")

            rows = self.ext_data.get(name, {}).get(cid, [])
            for r in rows:
                for j, field in enumerate(fields):
                    val = r[j] if j < len(r) else ""
                    self.insert_field(text, field, val)
                text.insert("end", "\n", "sep")

    # ---------------------------
    # Búsqueda y filtros
    # ---------------------------

    def search_dialog(self):
        if not self.core_rows:
            return
        win = tk.Toplevel(self.root)
        win.title("Buscar")
        tk.Label(win, text="Texto a buscar:").pack(side="left", padx=5, pady=5)
        entry = tk.Entry(win, width=40)
        entry.pack(side="left", padx=5, pady=5)
        tk.Button(win, text="Buscar", command=lambda: self.search_text(entry.get(), win)).pack(side="left", padx=5, pady=5)

    def search_text(self, text, win):
        win.destroy()
        if not text:
            return
        self.core_text.tag_remove("search", "1.0", "end")
        self.core_text.tag_config("search", background="#ffff00")
        start = "1.0"
        while True:
            pos = self.core_text.search(text, start, stopindex="end")
            if not pos:
                break
            end = f"{pos}+{len(text)}c"
            self.core_text.tag_add("search", pos, end)
            start = end

    def filter_dialog(self):
        if not self.core_rows:
            return
        win = tk.Toplevel(self.root)
        win.title("Filtrar")
        tk.Label(win, text="Campo:").grid(row=0, column=0, padx=5, pady=5)
        field_var = tk.StringVar()
        field_cb = ttk.Combobox(win, textvariable=field_var, values=self.core_fields, state="readonly")
        field_cb.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(win, text="Contiene:").grid(row=1, column=0, padx=5, pady=5)
        value_entry = tk.Entry(win, width=30)
        value_entry.grid(row=1, column=1, padx=5, pady=5)
        tk.Button(win, text="Aplicar", command=lambda: self.apply_filter(field_var.get(), value_entry.get(), win)).grid(row=2, column=0, columnspan=2, padx=5, pady=5)

    def apply_filter(self, field, value, win):
        win.destroy()
        if not field or not value:
            return
        try:
            idx = self.core_fields.index(field)
        except ValueError:
            return
        self.filtered_indices = [i for i, row in enumerate(self.core_rows) if idx < len(row) and value in row[idx]]
        if not self.filtered_indices:
            messagebox.showinfo("Filtro", "Ningún registro coincide con el filtro.")
            self.filtered_indices = None
        self.load_core()
        self.update_right_window()

    def clear_filter(self):
        if not self.core_rows:
            return
        self.filtered_indices = None
        self.load_core()
        self.update_right_window()

    # ---------------------------
    # Exportar registro activo a JSON
    # ---------------------------

    def export_active_record(self):
        if not self.core_rows:
            return
        core_idx = self.get_active_core_index()
        cid = self.core_rows[core_idx][self.core_fields.index("id")] if "id" in self.core_fields else self.core_rows[core_idx][0]

        data = {"core": {}, "extensions": {}}
        for i, field in enumerate(self.core_fields):
            val = self.core_rows[core_idx][i] if i < len(self.core_rows[core_idx]) else ""
            data["core"][field] = val

        for name, fields in self.extensions:
            rows = self.ext_data.get(name, {}).get(cid, [])
            ext_list = []
            for r in rows:
                ext_rec = {}
                for j, field in enumerate(fields):
                    val = r[j] if j < len(r) else ""
                    ext_rec[field] = val
                ext_list.append(ext_rec)
            data["extensions"][name] = ext_list

        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Exportar", f"Registro exportado a {path}")

    # ---------------------------
    # Edición de core y extensiones
    # ---------------------------

    def save_edit_core(self):
        if not self.core_rows:
            return
        field = self.edit_field_var.get()
        value = self.edit_value_entry.get()
        if not field:
            return
        try:
            idx = self.core_fields.index(field)
        except ValueError:
            return
        core_idx = self.get_active_core_index()
        if idx >= len(self.core_rows[core_idx]):
            self.core_rows[core_idx] += [""] * (idx - len(self.core_rows[core_idx]) + 1)
        self.core_rows[core_idx][idx] = value
        self.load_core()
        self.update_right_window()

    def save_edit_extension(self):
        if not self.core_rows or not self.extensions:
            return
        field = self.edit_field_var.get()
        value = self.edit_value_entry.get()
        if not field:
            return
        core_idx = self.get_active_core_index()
        cid = self.core_rows[core_idx][self.core_fields.index("id")] if "id" in self.core_fields else self.core_rows[core_idx][0]

        for name, fields in self.extensions:
            if field not in fields:
                continue
            idx = fields.index(field)
            rows = self.ext_data.get(name, {}).get(cid, [])
            for r in rows:
                if idx >= len(r):
                    r += [""] * (idx - len(r) + 1)
                r[idx] = value

        self.update_right_window()

# ---------------------------
# Arranque
# ---------------------------

def main():
    root = tk.Tk()
    root.withdraw()  # ocultar mientras la bienvenida está activa

    def start_viewer_with_meta(meta_path):
        root.deiconify()
        Viewer(root, meta_path=meta_path)

    WelcomeWindow(root, on_meta_selected=start_viewer_with_meta)
    root.mainloop()

if __name__ == "__main__":
    main()
