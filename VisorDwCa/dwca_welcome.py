"""
dwca_welcome.py
==============
Ventana de bienvenida y selector de esquemas en estrella.
El diálogo de selección de core, extensiones y claves foráneas se muestra
SIEMPRE; si el paquete trae meta.xml, los campos se autorrellenan con lo
que declara meta.xml y el usuario puede confirmarlos o cambiarlos.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

from dwca_loader import DwcaLoader, inspect_txt_headers
from dwca_access import export_zip_to_access
from dwca_excel import export_zip_to_excel


class StarSchemaDialog(tk.Toplevel):
    def __init__(self, parent, headers_map, prefill=None):
        super().__init__(parent)
        self.title("Configuración de Esquema en Estrella")
        self.geometry("820x580")
        self.transient(parent)
        self.grab_set()

        self.headers_map = headers_map
        self.prefill = prefill or {}
        self.result_schema = None

        self._build_ui()

    def _build_ui(self):
        lbl_info = tk.Label(
            self,
            text="Seleccione la Tabla Core (principal) y su columna ID. Para cada brazo o tabla relacionada, elija la columna que actúa como clave foránea:",
            font=("Segoe UI", 10, "bold"),
            wraplength=780,
            justify="left"
        )
        lbl_info.pack(anchor="w", padx=15, pady=10)

        # ---- SELECCIÓN DE CORE ----
        frame_core = ttk.LabelFrame(self, text=" 1. Tabla Core ")
        frame_core.pack(fill="x", padx=15, pady=5)

        tk.Label(frame_core, text="Archivo Core:").grid(row=0, column=0, padx=8, pady=8, sticky="e")
        self.combo_core = ttk.Combobox(frame_core, values=list(self.headers_map.keys()), state="readonly", width=25)
        self.combo_core.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        self.combo_core.bind("<<ComboboxSelected>>", self._on_core_changed)

        tk.Label(frame_core, text="Campo ID (Clave):").grid(row=0, column=2, padx=8, pady=8, sticky="e")
        self.combo_core_id = ttk.Combobox(frame_core, state="readonly", width=25)
        self.combo_core_id.grid(row=0, column=3, padx=8, pady=8, sticky="w")

        # ---- SELECCIÓN DE CLAVES FORÁNEAS (BRAZOS DE LA ESTRELLA) ----
        self.frame_ext = ttk.LabelFrame(self, text=" 2. Pestañas de Archivos Relacionados (Brazos y Claves Foráneas) ")
        self.frame_ext.pack(fill="both", expand=True, padx=15, pady=10)

        self.canvas_ext = tk.Canvas(self.frame_ext, highlightthickness=0)
        self.scroll_ext = ttk.Scrollbar(self.frame_ext, orient="vertical", command=self.canvas_ext.yview)
        self.container_ext = ttk.Frame(self.canvas_ext)

        self.container_ext.bind(
            "<Configure>",
            lambda e: self.canvas_ext.configure(scrollregion=self.canvas_ext.bbox("all"))
        )
        self.canvas_ext.create_window((0, 0), window=self.container_ext, anchor="nw")
        self.canvas_ext.configure(yscrollcommand=self.scroll_ext.set)

        self.canvas_ext.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.scroll_ext.pack(side="right", fill="y", pady=5)

        self.ext_widgets = {}

        files = list(self.headers_map.keys())
        if files:
            if self.prefill.get('core_file') in self.headers_map:
                self.combo_core.set(self.prefill['core_file'])
            else:
                self.combo_core.set(files[0])
            self._on_core_changed()

            # Autorrelleno de la columna ID del core
            if self.prefill.get('core_id_col') in self.headers_map.get(self.combo_core.get(), []):
                self.combo_core_id.set(self.prefill['core_id_col'])

        # Botones de acción inferior
        frame_btns = ttk.Frame(self)
        frame_btns.pack(fill="x", padx=15, pady=10)

        btn_ok = tk.Button(frame_btns, text="Cargar Pestañas", bg="#289530", fg="white",
                           font=("Segoe UI", 10, "bold"), command=self._on_accept)
        btn_ok.pack(side="right", padx=5)

        btn_cancel = tk.Button(frame_btns, text="Cancelar", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)

    def _on_core_changed(self, event=None):
        core_file = self.combo_core.get()
        cols = self.headers_map.get(core_file, [])
        self.combo_core_id["values"] = cols

        # Autorrelleno de la columna ID del core
        if self.prefill.get('core_id_col') in cols:
            self.combo_core_id.set(self.prefill['core_id_col'])
        elif "id" in cols:
            self.combo_core_id.set("id")
        elif cols:
            self.combo_core_id.set(cols[0])

        for child in self.container_ext.winfo_children():
            child.destroy()

        self.ext_widgets.clear()

        prefill_fk = {
            e['file']: e['fk_col']
            for e in self.prefill.get('extensions', [])
        }

        row = 0
        for fname, fields in self.headers_map.items():
            if fname == core_file:
                continue

            lbl_f = tk.Label(self.container_ext, text=f"• {fname}", font=("Segoe UI", 9, "bold"),
                             anchor="w", width=28)
            lbl_f.grid(row=row, column=0, padx=8, pady=6, sticky="w")

            lbl_fk = tk.Label(self.container_ext, text="Columna Clave Foránea:", anchor="e")
            lbl_fk.grid(row=row, column=1, padx=8, pady=6, sticky="e")

            combo_fk = ttk.Combobox(self.container_ext, values=fields, state="readonly", width=32)
            combo_fk.grid(row=row, column=2, padx=8, pady=6, sticky="w")

            # Autorrelleno de la clave foránea
            if fname in prefill_fk and prefill_fk[fname] in fields:
                combo_fk.set(prefill_fk[fname])
            elif "coreid" in fields:
                combo_fk.set("coreid")
            elif "id" in fields:
                combo_fk.set("id")
            elif fields:
                combo_fk.set(fields[0])

            self.ext_widgets[fname] = combo_fk
            row += 1

    def _on_accept(self):
        core_file = self.combo_core.get()
        core_id_col = self.combo_core_id.get()

        if not core_file or not core_id_col:
            messagebox.showwarning("Incompleto", "Por favor, seleccione el archivo Core y su columna ID.", parent=self)
            return

        ext_list = []
        for fname, combo_fk in self.ext_widgets.items():
            ext_list.append({
                'file': fname,
                'fk_col': combo_fk.get()
            })

        self.result_schema = {
            'core_file': core_file,
            'core_id_col': core_id_col,
            'extensions': ext_list
        }
        self.destroy()


class WelcomeFrame(tk.Frame):
    def __init__(self, root, viewer):
        super().__init__(root)
        self.root = root
        self.viewer = viewer
        self.eml_viewer_class = None

        tk.Label(
            self,
            text="Visor DwC-A GBIF.ES",
            font=("Segoe UI", 22, "bold"),
            fg="#289530"
        ).pack(pady=20)

        tk.Button(
            self,
            text="Abrir DwC-A (ZIP)",
            font=("Segoe UI", 14),
            bg="#289530",
            fg="white",
            command=self.open_zip
        ).pack(pady=10)

        tk.Button(
            self,
            text="Exportar DwC-A a Access (.accdb)",
            font=("Segoe UI", 14),
            bg="#1f6fb2",
            fg="white",
            command=lambda: export_zip_to_access(self.root)
        ).pack(pady=10)

        tk.Button(
            self,
            text="Exportar DwC-A a Excel (.xlsx)",
            font=("Segoe UI", 14),
            bg="#217346",
            fg="white",
            command=lambda: export_zip_to_excel(self.root)
        ).pack(pady=10)

    def set_eml_viewer_class(self, cls):
        self.eml_viewer_class = cls

    def open_zip(self):
        path = filedialog.askopenfilename(
            title="Seleccionar DwC-A (ZIP)",
            filetypes=[("DwC-A ZIP", "*.zip")]
        )
        if not path:
            return

        loader = DwcaLoader(path)
        try:
            loader.load()  # descomprime en un directorio temporal único y limpio
        except FileNotFoundError:
            pass  # sin meta.xml: el esquema se definirá por completo en el diálogo
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo descomprimir el archivo ZIP:\n{e}")
            return

        eml = os.path.join(loader.base, "eml.xml")

        headers_map = inspect_txt_headers(loader.base)
        if not headers_map:
            messagebox.showerror("Error", "No se encontraron archivos .txt o .csv válidos dentro del paquete ZIP.")
            return

        # El diálogo SIEMPRE se muestra. Si hay meta.xml, se autorrellena
        # con lo que declara; el usuario puede cambiar cualquier campo.
        prefill = None
        if os.path.exists(os.path.join(loader.base, "meta.xml")):
            try:
                prefill = self._schema_from_meta(loader)
            except Exception:
                prefill = None

        dialog = StarSchemaDialog(self.root, headers_map, prefill=prefill)
        self.root.wait_window(dialog)
        manual_schema = dialog.result_schema

        if not manual_schema:
            return

        try:
            self.pack_forget()
            self.viewer.load_with_schema(path, manual_schema=manual_schema)
            self.viewer.pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Error al cargar", f"Ocurrió un error al procesar las tablas:\n{e}")
            return

        if self.eml_viewer_class and os.path.exists(eml):
            self.eml_viewer_class(self.root, eml)

    def _schema_from_meta(self, loader):
        """Deduce el esquema (core, id, claves foráneas) del meta.xml del paquete."""

        def strip_ns(tag):
            return tag.split("}", 1)[1] if "}" in tag else tag

        meta = ET.parse(os.path.join(loader.base, "meta.xml")).getroot()

        core = None
        for child in meta.iter():
            if strip_ns(child.tag) == "core":
                core = child
                break
        if core is None:
            return None

        loc = [n for n in core.iter() if strip_ns(n.tag) == "location"]
        core_file = os.path.basename(loc[-1].text.strip()) if loc else None
        if not core_file:
            return None

        id_elem = next((n for n in core.iter() if strip_ns(n.tag) == "id"), None)
        id_index = int(id_elem.get("index")) if id_elem is not None and id_elem.get("index") is not None else 0

        headers_map = inspect_txt_headers(loader.base)
        headers = headers_map.get(core_file, [])
        core_id_col = headers[id_index] if id_index < len(headers) else "id"

        extensions = []
        for child in meta.iter():
            if strip_ns(child.tag) != "extension":
                continue
            loc = [n for n in child.iter() if strip_ns(n.tag) == "location"]
            if not loc:
                continue
            ext_file = os.path.basename(loc[-1].text.strip())
            coreid_elem = next((n for n in child.iter() if strip_ns(n.tag) == "coreid"), None)
            cid_index = int(coreid_elem.get("index")) if coreid_elem is not None and coreid_elem.get("index") is not None else 0
            ext_headers = headers_map.get(ext_file, [])
            fk_col = ext_headers[cid_index] if cid_index < len(ext_headers) else "id"
            extensions.append({'file': ext_file, 'fk_col': fk_col})

        return {
            'core_file': core_file,
            'core_id_col': core_id_col,
            'extensions': extensions,
        }