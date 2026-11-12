"""
dwca_viewer.py
==============
Módulo principal del visor de Darwin Core Archive con paneles adaptativos,
campos editables y copiables, borrado de registros con integridad referencial,
guardado del DwC-A modificado y barras de desplazamiento vertical y horizontal.
"""

import os
import csv
import xml.etree.ElementTree as ET
import shutil
import tempfile
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from dwca_loader import DwcaLoader, detect_delimiter, safe_open, strip_ns
from dwca_model import DwcaModel
from dwca_access import export_dwca_to_access
from dwca_excel import export_dwca_to_excel


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
        self.loader_base = ""
        self.core_filename = ""
        self.ext_filenames = {}

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

        self.btn_save = tk.Button(
            self.top_bar,
            text="💾 Guardar DwC-A",
            font=("Segoe UI", 10, "bold"),
            bg="#b8860b",
            fg="white",
            relief="flat",
            command=self.save_dwca,
            state="disabled"
        )
        self.btn_save.pack(side="right", padx=5, pady=5)

        self.btn_access = tk.Button(
            self.top_bar,
            text="Exportar a Access",
            font=("Segoe UI", 10, "bold"),
            bg="#1f6fb2",
            fg="white",
            relief="flat",
            command=self.export_access
        )
        self.btn_access.pack(side="right", padx=5, pady=5)

        self.btn_excel = tk.Button(
            self.top_bar,
            text="Exportar a Excel",
            font=("Segoe UI", 10, "bold"),
            bg="#217346",
            fg="white",
            relief="flat",
            command=self.export_excel
        )
        self.btn_excel.pack(side="right", padx=5, pady=5)

        # -------------------------------
        # PANEL PRINCIPAL (PanedWindow con sash ancho)
        # -------------------------------
        main = tk.PanedWindow(self, orient="horizontal", sashwidth=10, sashpad=2,
                              sashrelief="raised", bd=1)
        main.pack(fill="both", expand=True)
        self.main_paned = main

        # -------------------------------
        # PANEL IZQUIERDO (CORE) CON SCROLL DUAL
        # -------------------------------
        self.left_container = tk.Frame(main)
        main.add(self.left_container, width=600, minsize=300)

        core_actions = tk.Frame(self.left_container, bg="#f5f5f5")
        core_actions.pack(fill="x")

        self.btn_del_core = tk.Button(
            core_actions,
            text="🗑",
            font=("Segoe UI", 11),
            bg="#d9534f",
            fg="white",
            relief="flat",
            width=3,
            command=self.delete_core_record
        )
        self.btn_del_core.pack(side="left", padx=5, pady=4)

        self.left_canvas = tk.Canvas(self.left_container, highlightthickness=0)
        self.left_scroll_y = tk.Scrollbar(self.left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_scroll_x = tk.Scrollbar(self.left_container, orient="horizontal", command=self.left_canvas.xview)

        self.left_canvas.configure(
            yscrollcommand=self.left_scroll_y.set,
            xscrollcommand=self.left_scroll_x.set
        )

        self.left_scroll_y.pack(side="right", fill="y")
        self.left_scroll_x.pack(side="bottom", fill="x")
        self.left_canvas.pack(side="left", fill="both", expand=True)

        self.left_record_frame = tk.Frame(self.left_canvas)
        self.left_canvas_window = self.left_canvas.create_window((0, 0), window=self.left_record_frame, anchor="nw")

        self.left_record_frame.bind(
            "<Configure>",
            lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        )

        # -------------------------------
        # PANEL DERECHO (EXTENSIONES)
        # -------------------------------
        self.right = tk.Frame(main)
        main.add(self.right, width=600, minsize=300)

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

        # -------------------------------
        # SCROLL CON LA RUEDA DEL RATÓN
        # -------------------------------
        self.left_canvas.bind("<Enter>", lambda e: self.left_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.left_canvas.bind("<Leave>", lambda e: self.left_canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self.left_canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def set_welcome(self, welcome_frame):
        self.welcome_frame = welcome_frame

    def close_viewer(self):
        if self.welcome_frame is not None:
            self.pack_forget()
            self.welcome_frame.pack(fill="both", expand=True)

    def export_access(self):
        if self.model is None:
            messagebox.showwarning("Exportar a Access", "Primero abre un DwC-A.")
            return
        eml_path = os.path.join(self.loader_base, "eml.xml")
        export_dwca_to_access(self.root, self.core_fields, self.core_rows,
                              self.extensions, self.ext_data, eml_path)

    def export_excel(self):
        if self.model is None:
            messagebox.showwarning("Exportar a Excel", "Primero abre un DwC-A.")
            return
        eml_path = os.path.join(self.loader_base, "eml.xml")
        export_dwca_to_excel(self.root, self.core_fields, self.core_rows,
                             self.extensions, self.ext_data, eml_path)

    def load(self, meta_path):
        self.load_with_schema(meta_path, manual_schema=None)

    def load_with_schema(self, path, manual_schema=None):
        self.core_path = path
        self.lbl_path.config(text=f"Archivo cargado: {os.path.basename(path)}")

        loader = DwcaLoader(path)
        core_fields, core_rows, extensions, ext_data = loader.load(manual_schema=manual_schema)

        self.model = DwcaModel(core_fields, core_rows, extensions, ext_data)
        self.model.core_id_index = getattr(loader, 'core_id_index', 0)
        self.core_fields = core_fields
        self.core_rows = core_rows
        self.extensions = extensions
        self.ext_data = ext_data
        self.filtered_indices = None
        self.active_index = 0

        self.loader_base = loader.base or ""
        self.core_filename = ""
        self.ext_filenames = {}
        meta_path_real = os.path.join(self.loader_base, "meta.xml")
        if os.path.exists(meta_path_real):
            try:
                self._read_filenames_from_meta(meta_path_real)
            except Exception:
                self.core_filename = ""
                self.ext_filenames = {}

        self.filter_field_cb["values"] = self.core_fields
        self.btn_save.config(state="normal")

        self.load_record()
        self.load_ext_tabs()
        self.update_right_window()

    def _read_filenames_from_meta(self, meta_path):
        root = ET.parse(meta_path).getroot()
        for child in root.iter():
            if strip_ns(child.tag) == "core":
                loc = [n for n in child.iter() if strip_ns(n.tag) == "location"]
                if loc:
                    self.core_filename = os.path.basename(loc[-1].text.strip())
            elif strip_ns(child.tag) == "extension":
                loc = [n for n in child.iter() if strip_ns(n.tag) == "location"]
                if loc:
                    fname = os.path.basename(loc[-1].text.strip())
                    self.ext_filenames[fname] = fname

    # ---------------------------------------------------------------
    # GUARDAR DwC-A
    # ---------------------------------------------------------------
    def _read_original_header(self, fpath):
        if not os.path.exists(fpath):
            return None
        try:
            with safe_open(fpath) as f:
                return f.readline().rstrip("\r\n")
        except Exception:
            return None

    def _write_table(self, fpath, header_line, rows):
        delim = detect_delimiter(fpath) if os.path.exists(fpath) else "\t"
        with open(fpath, "w", encoding="utf-8", newline="") as f:
            if header_line:
                f.write(header_line + "\n")
            w = csv.writer(f, delimiter=delim, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
            w.writerows(rows)

    def save_dwca(self):
        if self.model is None:
            messagebox.showwarning("Guardar DwC-A", "Primero abre un DwC-A.")
            return
        if not self.loader_base or not os.path.isdir(self.loader_base):
            messagebox.showerror(
                "Guardar DwC-A",
                "No se ha localizado el directorio con los datos extraídos.\n"
                "Vuelve a abrir el DwC-A e inténtalo de nuevo."
            )
            return

        default_name = os.path.basename(self.core_path) if self.core_path.lower().endswith(".zip") \
            else os.path.basename(self.core_path) + ".zip"

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar DwC-A (ZIP)",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("DwC-A ZIP", "*.zip")],
            confirmoverwrite=True,
        )
        if not path:
            return

        if os.path.exists(path):
            if not messagebox.askyesno(
                "Guardar DwC-A",
                f"El archivo ya existe:\n{os.path.basename(path)}\n\n¿Sobrescribirlo?"
            ):
                return

        try:
            if self.core_filename:
                core_fpath = os.path.join(self.loader_base, self.core_filename)
                header = self._read_original_header(core_fpath)
                self._write_table(core_fpath, header, self.core_rows)

            for tab_name, _fields in self.extensions:
                fname = self.ext_filenames.get(tab_name, tab_name)
                fpath = os.path.join(self.loader_base, fname)
                if not os.path.exists(fpath):
                    continue
                header = self._read_original_header(fpath)
                rows = [r for lst in self.ext_data.get(tab_name, {}).values() for r in lst]
                self._write_table(fpath, header, rows)

            tmp_zip = tempfile.mktemp(suffix=".zip")
            with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as z:
                for root_dir, _dirs, files in os.walk(self.loader_base):
                    for fname in files:
                        full = os.path.join(root_dir, fname)
                        arcname = os.path.relpath(full, self.loader_base)
                        z.write(full, arcname)

            shutil.move(tmp_zip, path)

        except PermissionError:
            messagebox.showerror(
                "Guardar DwC-A",
                "No se pudo guardar el archivo. ¿Está abierto en otro programa? Ciérralo e inténtalo de nuevo."
            )
            return
        except Exception as e:
            messagebox.showerror("Guardar DwC-A", f"Error al guardar:\n{e}")
            return

        messagebox.showinfo("Guardar DwC-A", f"DwC-A guardado correctamente en:\n{path}")

    # ---------------------------------------------------------------
    # UTILIDADES DE ÍNDICES
    # ---------------------------------------------------------------
    def _current_indices(self):
        return list(range(len(self.core_rows))) if self.filtered_indices is None else list(self.filtered_indices)

    def _current_core_id(self):
        indices = self._current_indices()
        if not indices or self.active_index >= len(indices):
            return None
        row = self.core_rows[indices[self.active_index]]
        if hasattr(self.model, 'core_id_index') and self.model.core_id_index < len(row):
            return str(row[self.model.core_id_index]).strip()
        if "id" in self.core_fields:
            return str(row[self.core_fields.index("id")]).strip()
        return str(row[0]).strip()

    # ---------------------------------------------------------------
    # EDICIÓN INLINE
    # ---------------------------------------------------------------
    def _commit_core_edit(self, event, idx, col_index, widget):
        new_val = widget.get()
        row = self.core_rows[idx]
        if col_index >= len(row):
            row += [""] * (col_index - len(row) + 1)
        row[col_index] = new_val

    def _commit_ext_edit(self, event, ext_name, cid, row_ref, col_index, widget):
        new_val = widget.get()
        if col_index >= len(row_ref):
            row_ref += [""] * (col_index - len(row_ref) + 1)
        row_ref[col_index] = new_val
        rows = self.ext_data.get(ext_name, {}).get(cid, [])
        if row_ref not in rows:
            rows.append(row_ref)

    # ---------------------------------------------------------------
    # BORRADO CON INTEGRIDAD REFERENCIAL
    # ---------------------------------------------------------------
    def delete_core_record(self):
        """Borra el registro core activo y todas sus filas dependientes."""
        indices = self._current_indices()
        if not indices or self.active_index >= len(indices):
            return

        idx = indices[self.active_index]
        cid = self._current_core_id()

        n_dep = sum(len(self.ext_data.get(name, {}).get(cid, [])) for name, _ in self.extensions)
        msg = f"¿Eliminar el registro core nº {self.active_index + 1}?"
        if n_dep:
            msg += f"\nTambién se eliminarán {n_dep} registro(s) dependiente(s) de las extensiones."
        if not messagebox.askyesno("Eliminar registro", msg):
            return

        for name, _ in self.extensions:
            self.ext_data.get(name, {}).pop(cid, None)

        del self.core_rows[idx]

        if self.filtered_indices is not None:
            self.filtered_indices = [i for i in self.filtered_indices if i != idx]
            self.filtered_indices = [i - 1 if i > idx else i for i in self.filtered_indices]

        if self.active_index >= len(self._current_indices()):
            self.active_index = max(0, len(self._current_indices()) - 1)

        self.load_record()
        self.update_right_window()

    def delete_ext_row(self, ext_name, cid, row_ref):
        """Borra una fila concreta de una extensión para el registro core actual."""
        rows = self.ext_data.get(ext_name, {}).get(cid, [])
        if row_ref not in rows:
            return
        if not messagebox.askyesno("Eliminar registro", f"¿Eliminar esta fila de '{ext_name}'?"):
            return
        rows.remove(row_ref)
        if not rows:
            self.ext_data[ext_name].pop(cid, None)
        self.update_right_window()

    # ---------------------------------------------------------------
    # RENDERIZADO
    # ---------------------------------------------------------------
    def load_record(self):
        for w in self.left_record_frame.winfo_children():
            w.destroy()

        indices = self._current_indices()
        if not indices:
            self.nav_label.config(text="0 / 0")
            return

        if self.active_index >= len(indices):
            self.active_index = 0

        idx = indices[self.active_index]
        row = self.core_rows[idx]

        for i, field in enumerate(self.core_fields):
            val = row[i] if i < len(row) else ""

            # El título del campo es clicable si el valor es una URL
            if is_url(val):
                lbl_field = tk.Label(
                    self.left_record_frame,
                    text=field + ":",
                    font=("Segoe UI", 9, "bold", "underline"),
                    fg="blue",
                    cursor="hand2",
                    anchor="nw"
                )
                lbl_field.grid(row=i, column=0, sticky="nw", padx=6, pady=3)
                lbl_field.bind("<Button-1>", lambda e, v=val: webbrowser.open(v))
            else:
                lbl_field = tk.Label(
                    self.left_record_frame,
                    text=field + ":",
                    font=("Segoe UI", 9, "bold"),
                    anchor="nw"
                )
                lbl_field.grid(row=i, column=0, sticky="nw", padx=6, pady=3)

            entry = tk.Entry(self.left_record_frame, font=("Segoe UI", 9), width=70)
            entry.insert(0, val)
            entry.grid(row=i, column=1, sticky="nw", padx=6, pady=3)
            entry.bind("<Return>", lambda e, ix=idx, ci=i, w=entry: self._commit_core_edit(e, ix, ci, w))
            entry.bind("<FocusOut>", lambda e, ix=idx, ci=i, w=entry: self._commit_core_edit(e, ix, ci, w))

        self.left_record_frame.update_idletasks()
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        self.update_nav_label()

    def load_ext_tabs(self):
        for t in self.tabs.tabs():
            self.tabs.forget(t)

        for name, fields in self.extensions:
            frame = tk.Frame(self.tabs)
            self.tabs.add(frame, text=name)

            canvas = tk.Canvas(frame, highlightthickness=0)
            scroll_y = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)

            canvas.configure(
                yscrollcommand=scroll_y.set,
                xscrollcommand=scroll_x.set
            )

            scroll_y.pack(side="right", fill="y")
            scroll_x.pack(side="bottom", fill="x")
            canvas.pack(side="left", fill="both", expand=True)

            ext_frame = tk.Frame(canvas)
            canvas.create_window((0, 0), window=ext_frame, anchor="nw")

            ext_frame.bind(
                "<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
            )

            canvas.bind("<Enter>", lambda e, c=canvas: c.bind_all(
                "<MouseWheel>", lambda ev, cv=c: cv.yview_scroll(-1 * (ev.delta // 120), "units")))
            canvas.bind("<Leave>", lambda e, c=canvas: c.unbind_all("<MouseWheel>"))

            frame.ext_frame = ext_frame

    def update_right_window(self, event=None):
        indices = self._current_indices()
        if not indices:
            return

        if self.active_index >= len(indices):
            self.active_index = 0

        cid = self._current_core_id()
        if cid is None:
            return

        for i, (name, fields) in enumerate(self.extensions):
            if i >= len(self.tabs.tabs()):
                continue

            frame = self.tabs.nametowidget(self.tabs.tabs()[i])
            ext_frame = getattr(frame, 'ext_frame', frame)

            for w in ext_frame.winfo_children():
                w.destroy()

            rows = self.ext_data.get(name, {}).get(cid, [])

            if not rows:
                lbl_empty = tk.Label(
                    ext_frame,
                    text="(Sin registros asociados)",
                    font=("Segoe UI", 9, "italic"),
                    fg="#666666"
                )
                lbl_empty.pack(padx=10, pady=10)
                continue

            r_index = 0
            for r in rows:
                # Botón de papelera para borrar esta fila concreta
                btn_del = tk.Button(
                    ext_frame,
                    text="🗑",
                    font=("Segoe UI", 10),
                    bg="#d9534f",
                    fg="white",
                    relief="flat",
                    width=2,
                    command=lambda en=name, c=cid, rr=r: self.delete_ext_row(en, c, rr)
                )
                btn_del.grid(row=r_index, column=0, sticky="nw", padx=6, pady=(6, 2))
                r_index += 1

                for j, field in enumerate(fields):
                    val = r[j] if j < len(r) else ""

                    lbl_field = tk.Label(
                        ext_frame,
                        text=field + ":",
                        font=("Segoe UI", 9, "bold"),
                        anchor="nw"
                    )
                    lbl_field.grid(row=r_index, column=0, sticky="nw", padx=6, pady=2)

                    entry = tk.Entry(ext_frame, font=("Segoe UI", 9), width=70)
                    entry.insert(0, str(val))
                    entry.grid(row=r_index, column=1, sticky="nw", padx=6, pady=2)
                    entry.bind(
                        "<Return>",
                        lambda e, en=name, c=cid, rr=r, cj=j, w=entry: self._commit_ext_edit(e, en, c, rr, cj, w)
                    )
                    entry.bind(
                        "<FocusOut>",
                        lambda e, en=name, c=cid, rr=r, cj=j, w=entry: self._commit_ext_edit(e, en, c, rr, cj, w)
                    )

                    r_index += 1

                # Separador entre registros de la extensión
                ttk.Separator(ext_frame, orient="horizontal").grid(
                    row=r_index, column=0, columnspan=2, sticky="ew", pady=6
                )
                r_index += 1

    def update_nav_label(self):
        indices = self._current_indices()
        if not indices:
            self.nav_label.config(text="0 / 0")
            return
        pos = self.active_index + 1
        total = len(indices)
        self.nav_label.config(text=f"{pos} / {total}")

    # ---------------------------------------------------------------
    # NAVEGACIÓN
    # ---------------------------------------------------------------
    def go_first(self):
        self.active_index = 0
        self.load_record()
        self.update_right_window()

    def go_last(self):
        indices = self._current_indices()
        self.active_index = max(len(indices) - 1, 0)
        self.load_record()
        self.update_right_window()

    def go_prev(self):
        if self.active_index > 0:
            self.active_index -= 1
            self.load_record()
            self.update_right_window()

    def go_next(self):
        indices = self._current_indices()
        if self.active_index < len(indices) - 1:
            self.active_index += 1
            self.load_record()
            self.update_right_window()

    def goto_record(self):
        try:
            num = int(self.goto_var.get())
        except ValueError:
            messagebox.showerror("Error", "Debe ser un número entero.")
            return

        indices = self._current_indices()

        if num < 1 or num > len(indices):
            messagebox.showerror("Error", "Número fuera de rango.")
            return

        self.active_index = num - 1
        self.load_record()
        self.update_right_window()

    # ---------------------------------------------------------------
    # FILTRADO
    # ---------------------------------------------------------------
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