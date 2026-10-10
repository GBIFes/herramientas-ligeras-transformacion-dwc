# VisorDWCEstrella
# Este módulo muestra un archivo Darwin Core Archive (DwC-A) como formulario continuo.
# La ventana izquierda presenta todos los registros del core, incluyendo la columna ID.
# La ventana derecha muestra únicamente los registros de las tablas de extensión
# vinculados al registro sobre el que está el cursor. Al desplazarse por la ventana
# izquierda, la ventana derecha se actualiza automáticamente. Se detectan múltiples
# etiquetas <location> y se usan los nombres de campos según su término corto.
# Los registros se separan con una línea gruesa gris que ocupa toda la anchura.

import tkinter as tk
from tkinter import ttk, filedialog
import xml.etree.ElementTree as ET
import csv
import os

NS = {"dwc": "http://rs.tdwg.org/dwc/text/"}

def short(term):
    return term.rsplit("/", 1)[-1]

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

        top = tk.Frame(root)
        top.pack(fill="x")

        tk.Button(top, text="Abrir meta.xml", command=self.open_meta).pack(side="left", padx=5)

        main = tk.PanedWindow(root, orient="horizontal")
        main.pack(fill="both", expand=True)

        left = tk.Frame(main)
        right = tk.Frame(main)
        main.add(left)
        main.add(right)

        self.core_text = tk.Text(left, wrap="none")
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

        self.load_core()
        self.load_ext_tabs()
        self.update_right_window()
    def load_core(self):
        self.core_text.delete("1.0", "end")
        self.core_record_line_map = []
        line = 1

        for idx, row in enumerate(self.core_rows):
            self.core_record_line_map.append(line)
            for i, field in enumerate(self.core_fields):
                self.core_text.insert("end", field + ": ", "field")
                self.core_text.insert("end", row[i] + "\n", "value")
                line += 1
            self.core_text.insert("end", "\n", "sep")
            line += 1

    def load_ext_tabs(self):
        for t in self.tabs.tabs():
            self.tabs.forget(t)

        for name, fields in self.extensions:
            frame = tk.Frame(self.tabs)
            text = tk.Text(frame, wrap="none")
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

    def update_right_window(self, event=None):
        cursor_line = int(self.core_text.index("insert").split(".")[0])
        record_index = 0

        for i, start_line in enumerate(self.core_record_line_map):
            if cursor_line >= start_line:
                record_index = i

        cid = self.core_rows[record_index][0]

        for i, (name, fields) in enumerate(self.extensions):
            frame = self.tabs.nametowidget(self.tabs.tabs()[i])
            text = frame.text
            text.delete("1.0", "end")

            rows = self.ext_data[name].get(cid, [])
            for r in rows:
                for j, field in enumerate(fields):
                    text.insert("end", field + ": ", "field")
                    text.insert("end", r[j] + "\n", "value")
                text.insert("end", "\n", "sep")

root = tk.Tk()
Viewer(root)
root.mainloop()
