"""
dwca_access.py  (v2)
Exporta un Darwin Core Archive a una base de datos Microsoft Access (.accdb):
    - tabla  core
    - una tabla por extensión
    - tabla  eml_metadata (resumen del EML, ver dwca_eml_summary.py)
    - relaciones 1:N core.id -> extensión.id
    - (opcional) formularios de visualización, ver dwca_access_forms.py

Requisitos (solo Windows):
    pip install pyodbc pywin32
    + Microsoft Access Database Engine (ACE), misma arquitectura que Python
    + Para los formularios: Microsoft Access completo instalado
"""

import os
import re
import sys
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pyodbc
    # Sin pooling, ODBC suelta el .accdb al cerrar la conexión y Access puede abrirlo después
    pyodbc.pooling = False
except ImportError:
    pyodbc = None

try:
    import win32com.client
except ImportError:
    win32com = None

from dwca_loader import DwcaLoader
from dwca_eml_summary import (
    build_summary,
    COLUMNS as EML_META_COLS,
    CAPTIONS as EML_META_CAPTIONS,
    TYPES as EML_META_TYPES,
)

ODBC_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"
ACE_PROVIDERS = ("Microsoft.ACE.OLEDB.16.0", "Microsoft.ACE.OLEDB.12.0")
BATCH_SIZE = 2000
MAX_ACCESS_FIELDS = 255


class AccessExportError(Exception):
    pass


# ---------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------
def _safe_name(raw, used, fallback):
    """Nombre válido para Access, único dentro de 'used' (sin distinguir mayúsculas)."""
    name = re.sub(r"\W", "_", str(raw or "").strip()) or fallback
    name = name[:60]
    base, k = name, 2
    while name.lower() in used:
        name = f"{base}_{k}"
        k += 1
    used.add(name.lower())
    return name


def _column_types(ncols, rows):
    """TEXT(255) si cabe, LONGTEXT (memo) si algún valor supera 255 caracteres."""
    maxlen = [0] * ncols
    for r in rows:
        for i in range(min(ncols, len(r))):
            n = len(r[i])
            if n > maxlen[i]:
                maxlen[i] = n
    return ["TEXT(255)" if m <= 255 else "LONGTEXT" for m in maxlen]


def _create_empty_accdb(path):
    last_error = None
    for provider in ACE_PROVIDERS:
        try:
            catalog = win32com.client.Dispatch("ADOX.Catalog")
            catalog.Create(f"Provider={provider};Data Source={path};")
            catalog.ActiveConnection.Close()
            catalog = None
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
    raise AccessExportError(
        "No se pudo crear el archivo .accdb. Comprueba que está instalado el "
        "Microsoft Access Database Engine (ACE) con la misma arquitectura que Python.\n"
        f"Detalle: {last_error}"
    )


def _insert_rows(conn, table, ncols, rows, tick):
    cur = conn.cursor()
    sql = f"INSERT INTO [{table}] VALUES ({','.join('?' * ncols)})"
    for k in range(0, len(rows), BATCH_SIZE):
        chunk = [
            tuple((r[i] if i < len(r) and r[i] != "" else None) for i in range(ncols))
            for r in rows[k:k + BATCH_SIZE]
        ]
        try:
            cur.executemany(sql, chunk)
        except pyodbc.Error:
            conn.rollback()
            for values in chunk:          # reintento fila a fila
                cur.execute(sql, values)
        conn.commit()
        tick(len(chunk))


# ---------------------------------------------------------------
# CONSTRUCCIÓN DE LA BASE DE DATOS
# ---------------------------------------------------------------
def build_access_db(path, core_fields, core_rows, extensions, ext_data,
                    eml=None, create_forms=True,
                    on_message=None, on_tick=None):
    """
    Crea 'path' (.accdb). 'eml' es la lista de filas de build_summary() o None.
    Devuelve una lista de advertencias.
    """
    on_message = on_message or (lambda m: None)
    on_tick = on_tick or (lambda n: None)
    warnings = []

    # ---- Preparar tablas -------------------------------------
    used_tables = set()
    raw_tables = [("core", core_fields, core_rows)]
    for name, fields in extensions:
        rows = [r for lst in ext_data.get(name, {}).values() for r in lst]
        raw_tables.append((os.path.splitext(name)[0], fields, rows))

    schema = []      # lo usa dwca_access_forms
    prepared = []
    for i, (label, fields, rows) in enumerate(raw_tables):
        tname = _safe_name(label, used_tables, "extension")
        if len(fields) > MAX_ACCESS_FIELDS:
            raise AccessExportError(
                f"La tabla '{tname}' tiene {len(fields)} campos; Access admite {MAX_ACCESS_FIELDS}."
            )
        used_cols = set()
        cols = [_safe_name(f, used_cols, f"col_{k}") for k, f in enumerate(fields)]
        types = _column_types(len(cols), rows)
        prepared.append((tname, cols, types, rows))
        schema.append({
            "kind": "core" if i == 0 else "ext",
            "label": label,
            "table": tname,
            "cols": cols,
            "captions": list(fields),
            "types": types,
        })

    eml_schema = None
    if eml is not None:
        t_meta = _safe_name("eml_metadata", used_tables, "eml_metadata")
        eml_schema = {
            "kind": "eml",
            "label": "EML (metadatos)",
            "table": t_meta,
            "cols": list(EML_META_COLS),
            "captions": list(EML_META_CAPTIONS),
            "types": list(EML_META_TYPES),
        }

    if os.path.exists(path):
        os.remove(path)

    on_message("Creando base de datos Access...")
    _create_empty_accdb(path)

    conn = pyodbc.connect(f"Driver={{{ODBC_DRIVER}}};DBQ={path};", autocommit=False)
    try:
        cur = conn.cursor()

        # ---- Tablas DwC-A ------------------------------------
        for tname, cols, types, rows in prepared:
            on_message(f"Importando tabla '{tname}' ({len(rows)} filas)...")
            ddl = ", ".join(f"[{c}] {t}" for c, t in zip(cols, types))
            cur.execute(f"CREATE TABLE [{tname}] ({ddl})")
            conn.commit()
            _insert_rows(conn, tname, len(cols), rows, on_tick)

        # ---- Tablas EML --------------------------------------
        if eml is not None:
            on_message("Importando resumen del EML...")
            ddl = ", ".join(f"[{c}] {t}" for c, t in zip(EML_META_COLS, EML_META_TYPES))
            cur.execute(f"CREATE TABLE [{eml_schema['table']}] ({ddl})")
            conn.commit()
            _insert_rows(conn, eml_schema["table"], len(EML_META_COLS), eml, on_tick)

        # ---- Clave primaria + relaciones ---------------------
        on_message("Creando relaciones...")
        core_name, core_cols = prepared[0][0], prepared[0][1]
        core_has_pk = False
        if "id" in core_cols:
            try:
                cur.execute(f"ALTER TABLE [{core_name}] ADD CONSTRAINT [pk_{core_name}] PRIMARY KEY ([id])")
                conn.commit()
                core_has_pk = True
            except pyodbc.Error as e:
                conn.rollback()
                warnings.append(f"No se pudo crear la clave primaria de '{core_name}' (¿ids duplicados o vacíos?): {e}")
        else:
            warnings.append(f"La tabla '{core_name}' no tiene columna 'id'; no se crean relaciones.")

        for tname, cols, _types, _rows in prepared[1:]:
            if "id" not in cols:
                continue
            try:
                cur.execute(f"CREATE INDEX [idx_{tname}_id] ON [{tname}] ([id])")
                conn.commit()
            except pyodbc.Error:
                conn.rollback()
            if core_has_pk:
                try:
                    cur.execute(
                        f"ALTER TABLE [{tname}] ADD CONSTRAINT [fk_{tname}_core] "
                        f"FOREIGN KEY ([id]) REFERENCES [{core_name}] ([id])"
                    )
                    conn.commit()
                except pyodbc.Error as e:
                    conn.rollback()
                    warnings.append(f"No se pudo crear la relación {core_name} → {tname} (¿registros huérfanos?): {e}")
    finally:
        conn.close()

    # ---- Formularios (requiere Access instalado) --------------
    if create_forms:
        on_message("Creando formularios de Access (puede tardar)...")
        try:
            from dwca_access_forms import create_forms as _create_forms
            warnings.extend(_create_forms(path, schema, eml_schema) or [])
        except Exception as e:  # noqa: BLE001
            log_path = os.path.splitext(path)[0] + "_error_formularios.txt"
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except OSError:
                log_path = "(no se pudo escribir el registro)"
            warnings.append(
                "La base de datos se creó, pero no se pudieron generar los formularios: "
                f"{e}\nDetalle completo en: {log_path}"
            )

    return warnings


# ---------------------------------------------------------------
# VENTANA DE PROGRESO
# ---------------------------------------------------------------
class _ProgressWindow(tk.Toplevel):
    def __init__(self, parent, total):
        super().__init__(parent)
        self.title("Exportando a Access")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.lbl = tk.Label(self, text="Preparando...", width=60, anchor="w")
        self.lbl.pack(padx=15, pady=(15, 5))
        self.bar = ttk.Progressbar(self, maximum=max(total, 1), length=420)
        self.bar.pack(padx=15, pady=(0, 15))
        self.value = 0
        self.grab_set()
        self.update()

    def message(self, text):
        self.lbl.config(text=text)
        self.update()

    def advance(self, n):
        self.value += n
        self.bar["value"] = self.value
        self.update()


# ---------------------------------------------------------------
# FUNCIONES PÚBLICAS
# ---------------------------------------------------------------
def _check_requirements():
    if sys.platform != "win32":
        return "La exportación a Access solo funciona en Windows."
    if pyodbc is None or win32com is None:
        return "Faltan dependencias. Instálalas con:\n\npip install pyodbc pywin32"
    return None


def export_dwca_to_access(parent, core_fields, core_rows, extensions, ext_data, eml_path=None):
    """Pide el destino y exporta datos ya cargados en memoria (+ EML si existe)."""
    problem = _check_requirements()
    if problem:
        messagebox.showerror("Exportar a Access", problem, parent=parent)
        return

    path = filedialog.asksaveasfilename(
        parent=parent,
        title="Guardar base de datos Access",
        defaultextension=".accdb",
        filetypes=[("Access DB", "*.accdb")],
    )
    if not path:
        return

    make_forms = messagebox.askyesno(
        "Exportar a Access",
        "¿Crear también los formularios de visualización?\n\n"
        "(Requiere tener Microsoft Access instalado. Si no, la base de datos "
        "se crea igualmente, solo con las tablas.)",
        parent=parent,
    )

    eml = None
    if eml_path and os.path.exists(eml_path):
        try:
            eml = build_summary(eml_path)
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning("EML", f"No se pudo leer eml.xml; se exporta sin metadatos.\n{e}", parent=parent)

    total = len(core_rows) + sum(
        len(lst) for name, _ in extensions for lst in ext_data.get(name, {}).values()
    )
    if eml is not None:
        total += len(eml)

    progress = _ProgressWindow(parent, total)
    try:
        warnings = build_access_db(
            path, core_fields, core_rows, extensions, ext_data,
            eml=eml, create_forms=make_forms,
            on_message=progress.message, on_tick=progress.advance,
        )
    except Exception as e:  # noqa: BLE001
        progress.destroy()
        messagebox.showerror("Exportar a Access", f"Error durante la exportación:\n{e}", parent=parent)
        return
    progress.destroy()

    msg = f"Base de datos creada correctamente:\n{path}"
    if warnings:
        msg += "\n\nAdvertencias:\n- " + "\n- ".join(warnings)
    msg += "\n\n¿Quieres abrir ahora la base de datos en Access?"
    if messagebox.askyesno("Exportar a Access", msg, parent=parent):
        try:
            os.startfile(path)   # abre el .accdb con Access (aplicación asociada)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(
                "Exportar a Access",
                f"No se pudo abrir la base de datos:\n{e}",
                parent=parent,
            )


def export_zip_to_access(parent):
    """Pide un ZIP DwC-A, lo carga y lo exporta junto con su eml.xml."""
    problem = _check_requirements()
    if problem:
        messagebox.showerror("Exportar a Access", problem, parent=parent)
        return

    zip_path = filedialog.askopenfilename(
        parent=parent,
        title="Seleccionar DwC-A (ZIP) para exportar a Access",
        filetypes=[("DwC-A ZIP", "*.zip")],
    )
    if not zip_path:
        return

    try:
        parent.config(cursor="watch")
        parent.update()
        loader = DwcaLoader(zip_path)
        core_fields, core_rows, extensions, ext_data = loader.load()
        eml_path = os.path.join(loader.base, "eml.xml")
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Exportar a Access", f"No se pudo leer el DwC-A:\n{e}", parent=parent)
        return
    finally:
        parent.config(cursor="")

    export_dwca_to_access(parent, core_fields, core_rows, extensions, ext_data, eml_path)
