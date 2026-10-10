# VisorDWCEstrella
# Visor de DwC-A con wrap inteligente, URLs navegables, navegación estilo Access,
# búsqueda, filtros, edición, exportación y estadísticas avanzadas.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET
import csv
import os
import json
import webbrowser

NS = {"dwc": "http://rs.tdwg.org/dwc/text/"}

def short(term):
    return term.rsplit("/", 1)[-1]

def is_url(text):
    return text.startswith("http://") or text.startswith("https://")

class Viewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Visor DWC Estrella")
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
        tk.Button(top, text="Estadísticas", command=self.show_stats).pack(side="left", padx=5)

        main = tk.PanedWindow(root, orient="horizontal")
        main.pack(fill="both", expand=True)

        # Panel izquierdo: core
        left = tk.Frame(main)
        main.add(left)

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

        # Navegación estilo Access
        nav = tk.Frame(left)
        nav.pack(fill="x")
        tk.Button(nav, text="⏮", command=self.go_first).pack(side="left")
        tk.Button(nav, text="◀", command=self.go_prev).pack(side="left")
        tk.Button(nav, text="▶", command=self.go_next).pack(side="left")
        tk.Button(nav, text="⏭", command=self.go_last).pack(side="left")
        self.nav_label = tk.Label(nav, text="0 / 0")
        self.nav_label.pack(side="left", padx=10)

        # Panel derecho: extensiones
        right = tk.Frame(main)
        main.add(right)

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)

        # Edición
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
    def open_meta(self):
        path = filedialog.askopenfilename(filetypes=[("meta.xml", "meta.xml")])
        if not path:
            return

        self.meta = ET.parse(path).getroot()
        core = self.meta.find("dwc:core", NS)
        loc = core.findall(".//dwc:location", NS)[-1]
        base = os.path.dirname(path)
        self.core_file = os.path.join(base, loc.text.strip())

        core_id_index = int(core.find("dwc:id", NS).get("index"))
        self.core_fields = ["id"] + [short(f.get("term")) for f in core.findall("dwc:field", NS)]

        self.core_rows = []
        with open(self.core_file, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            next(r)
            for row in r:
                self.core_rows.append(row)

        self.extensions = []
        self.ext_data = {}

        for ext in self.meta.findall("dwc:extension", NS):
            loc_nodes = ext.findall(".//dwc:location", NS)
            if not loc_nodes:
                continue
            fname = os.path.join(base, loc_nodes[-1].text.strip())

            fields_raw = ext.findall("dwc:field", NS)
            fields = ["id"] + [short(f.get("term")) for f in fields_raw]

            coreid_elem = ext.find("dwc:coreid", NS)
            cid_index = int(coreid_elem.get("index"))

            rows = {}
            with open(fname, encoding="utf-8") as f:
                r = csv.reader(f, delimiter="\t")
                next(r)
                for row in r:
                    cid = row[cid_index]
                    rows.setdefault(cid, []).append(row)

            tab_name = os.path.basename(fname)
            self.extensions.append((tab_name, fields))
            self.ext_data[tab_name] = rows

        self.filtered_indices = None
        self.edit_field_entry["values"] = self.core_fields
        self.load_core()
        self.load_ext_tabs()
        self.update_right_window()

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
                self.insert_field(self.core_text, field, row[i])
                line += 1
            self.core_text.insert("end", "\n", "sep")
            line += 1

        self.update_nav_label()

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
        return indices[record_index]

    def update_right_window(self, event=None):
        if not self.core_rows or not self.extensions or not self.core_record_line_map:
            return

        core_idx = self.get_active_core_index()
        cid = self.core_rows[core_idx][0]

        for i, (name, fields) in enumerate(self.extensions):
            frame = self.tabs.nametowidget(self.tabs.tabs()[i])
            text = frame.text
            text.delete("1.0", "end")

            rows = self.ext_data[name].get(cid, [])
            for r in rows:
                for j, field in enumerate(fields):
                    self.insert_field(text, field, r[j])
                text.insert("end", "\n", "sep")

        self.update_nav_label()

    # Navegación estilo Access
    def update_nav_label(self):
        if not self.core_rows:
            self.nav_label.config(text="0 / 0")
            return
        total = len(self.core_rows) if self.filtered_indices is None else len(self.filtered_indices)
        active = self.get_active_core_index() + 1
        self.nav_label.config(text=f"{active} / {total}")

    def go_first(self):
        if not self.core_record_line_map:
            return
        self.core_text.mark_set("insert", f"{self.core_record_line_map[0]}.0")
        self.core_text.see(f"{self.core_record_line_map[0]}.0")
        self.update_right_window()

    def go_last(self):
        if not self.core_record_line_map:
            return
        last = len(self.core_record_line_map) - 1
        self.core_text.mark_set("insert", f"{self.core_record_line_map[last]}.0")
        self.core_text.see(f"{self.core_record_line_map[last]}.0")
        self.update_right_window()

    def go_prev(self):
        if not self.core_record_line_map:
            return
        idx = self.get_active_core_index()
        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        pos = indices.index(idx)
        if pos > 0:
            prev_line = self.core_record_line_map[pos - 1]
            self.core_text.mark_set("insert", f"{prev_line}.0")
            self.core_text.see(f"{prev_line}.0")
            self.update_right_window()

    def go_next(self):
        if not self.core_record_line_map:
            return
        idx = self.get_active_core_index()
        indices = range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices
        pos = indices.index(idx)
        if pos < len(indices) - 1:
            next_line = self.core_record_line_map[pos + 1]
            self.core_text.mark_set("insert", f"{next_line}.0")
            self.core_text.see(f"{next_line}.0")
            self.update_right_window()
    # --- BÚSQUEDA GLOBAL ---
    def search_dialog(self):
        if not self.core_rows:
            return
        win = tk.Toplevel(self.root)
        win.title("Buscar texto")
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

    # --- FILTROS ---
    def filter_dialog(self):
        if not self.core_rows:
            return
        win = tk.Toplevel(self.root)
        win.title("Filtrar registros")

        tk.Label(win, text="Campo:").grid(row=0, column=0, padx=5, pady=5)
        field_var = tk.StringVar()
        field_cb = ttk.Combobox(win, textvariable=field_var, values=self.core_fields, state="readonly")
        field_cb.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(win, text="Contiene:").grid(row=1, column=0, padx=5, pady=5)
        value_entry = tk.Entry(win, width=30)
        value_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Button(win, text="Aplicar filtro",
                  command=lambda: self.apply_filter(field_var.get(), value_entry.get(), win)).grid(row=2, column=0, padx=5, pady=5)

        tk.Button(win, text="Quitar filtro",
                  command=lambda: (self.clear_filter(), win.destroy())).grid(row=2, column=1, padx=5, pady=5)

    def apply_filter(self, field, value, win):
        win.destroy()
        if not field or not value:
            return
        try:
            idx = self.core_fields.index(field)
        except ValueError:
            return
        self.filtered_indices = [i for i, row in enumerate(self.core_rows) if value in row[idx]]
        if not self.filtered_indices:
            messagebox.showinfo("Filtro", "Ningún registro coincide con el filtro.")
            self.filtered_indices = None
        self.load_core()
        self.update_right_window()

    def clear_filter(self):
        self.filtered_indices = None
        self.load_core()
        self.update_right_window()

    # --- EXPORTACIÓN DEL REGISTRO ACTIVO ---
    def export_active_record(self):
        if not self.core_rows:
            return
        core_idx = self.get_active_core_index()
        cid = self.core_rows[core_idx][0]

        data = {"core": {}, "extensions": {}}

        # Core
        for i, field in enumerate(self.core_fields):
            data["core"][field] = self.core_rows[core_idx][i]

        # Extensiones
        for name, fields in self.extensions:
            rows = self.ext_data[name].get(cid, [])
            ext_list = []
            for r in rows:
                ext_rec = {}
                for j, field in enumerate(fields):
                    ext_rec[field] = r[j]
                ext_list.append(ext_rec)
            data["extensions"][name] = ext_list

        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Exportar", f"Registro exportado a {path}")

    # --- EDICIÓN ---
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
        cid = self.core_rows[core_idx][0]

        for name, fields in self.extensions:
            if field not in fields:
                continue
            idx = fields.index(field)
            rows = self.ext_data[name].get(cid, [])
            for r in rows:
                r[idx] = value

        self.update_right_window()
    def show_stats(self):
        win = tk.Toplevel(self.root)
        win.title("Estadísticas de tablas")

        text = tk.Text(win, wrap="word", width=90, height=35)
        text.pack(fill="both", expand=True)

        total_core = len(self.core_rows)

        # === CORE ===
        text.insert("end", "=== CORE ===\n", "field")
        for i, field in enumerate(self.core_fields):
            values = [row[i] for row in self.core_rows if row[i].strip() != ""]
            count_nonempty = len(values)
            distinct = len(set(values))
            pct = (count_nonempty / total_core * 100) if total_core else 0
            text.insert(
                "end",
                f"{field}: {count_nonempty} con contenido ({pct:.1f}%), "
                f"{distinct} valores distintos\n"
            )

        text.insert("end", "\n")

        # === EXTENSIONES ===
        for name, fields in self.extensions:
            text.insert("end", f"=== {name} ===\n", "field")

            # Todas las filas de la extensión
            rows = []
            for cid, ext_rows in self.ext_data[name].items():
                rows.extend(ext_rows)

            # Cardinalidad respecto al core
            counts = [
                len(self.ext_data[name].get(self.core_rows[i][0], []))
                for i in range(total_core)
            ]
            max_count = max(counts) if counts else 0
            min_count = min(counts) if counts else 0

            if max_count > 1:
                cardinalidad = "1:N"
            elif max_count == 1 and min_count == 1:
                cardinalidad = "1:1"
            elif max_count == 1 and min_count == 0:
                cardinalidad = "0:N"
            else:
                cardinalidad = "N:N"

            text.insert("end", f"Cardinalidad: {cardinalidad}\n\n")

            total_ext = len(rows)

            # Estadísticas de campos
            for j, field in enumerate(fields):
                values = [r[j] for r in rows if r[j].strip() != ""]
                count_nonempty = len(values)
                distinct = len(set(values))
                pct = (count_nonempty / total_ext * 100) if total_ext else 0
                text.insert(
                    "end",
                    f"{field}: {count_nonempty} con contenido ({pct:.1f}%), "
                    f"{distinct} valores distintos\n"
                )

            text.insert("end", "\n")

        text.tag_config("field", foreground="#004080", font=("Segoe UI", 11, "bold"))
