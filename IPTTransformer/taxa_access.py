"""
taxa_access.py
==============
Exporta los resultados parseados del módulo taxonómico a una base de datos
Microsoft Access (.accdb) e invoca la creación automática de formularios.
"""

import os
import sys
from tkinter import messagebox, filedialog
try:
    import win32com.client
except ImportError:
    win32com = None

try:
    import pyodbc
    pyodbc.pooling = False
except ImportError:
    pyodbc = None

ODBC_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"
ACE_PROVIDERS = ("Microsoft.ACE.OLEDB.16.0", "Microsoft.ACE.OLEDB.12.0")

def _create_empty_accdb(path):
    last_error = None
    for provider in ACE_PROVIDERS:
        try:
            catalog = win32com.client.Dispatch("ADOX.Catalog")
            catalog.Create(f"Provider={provider};Data Source={path};")
            catalog.ActiveConnection.Close()
            return
        except Exception as e:
            last_error = e
    raise RuntimeError(
        "No se pudo crear el archivo .accdb. Comprueba que está instalado el "
        "Microsoft Access Database Engine (ACE) con la misma arquitectura que Python.\n"
        f"Detalle: {last_error}"
    )

def export_to_access(parent, fields, rows, default_filename="taxonomia.accdb"):
    """
    Pide la ruta de destino y exporta la tabla de datos taxonómicos parseados
    a Access, generando tablas y formularios interactivos de navegación.
    """
    if sys.platform != "win32" or pyodbc is None or win32com is None:
        messagebox.showerror(
            "Exportar a Access",
            "La exportación a Access solo funciona en Windows y requiere "
            "'pyodbc', 'pywin32' y Microsoft Access Database Engine.",
            parent=parent
        )
        return

    path = filedialog.asksaveasfilename(
        parent=parent,
        title="Guardar base de datos Access",
        defaultextension=".accdb",
        initialfile=default_filename,
        filetypes=[("Access DB", "*.accdb")]
    )
    if not path:
        return

    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            messagebox.showerror(
                "Exportar a Access",
                "No se pudo sobrescribir el archivo. ¿Está abierto en Microsoft Access? Ciérralo e inténtalo de nuevo.",
                parent=parent
            )
            return

    try:
        _create_empty_accdb(path)
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)
        return

    # Normalizar nombres de columnas para que sean totalmente compatibles con Access
    safe_fields = [f.replace("-", "_").replace(" ", "_")[:64] for f in fields]

    conn = pyodbc.connect(f"Driver={{{ODBC_DRIVER}}};DBQ={path};", autocommit=False)
    try:
        cur = conn.cursor()
        ddl = ", ".join(f"[{col}] LONGTEXT" for col in safe_fields)
        cur.execute(f"CREATE TABLE [taxonomia_parseada] ({ddl})")
        conn.commit()

        sql = f"INSERT INTO [taxonomia_parseada] VALUES ({','.join(['?'] * len(safe_fields))})"
        for k in range(0, len(rows), 2000):
            chunk = [tuple(r if r != "" else None for r in row) for row in rows[k:k+2000]]
            cur.executemany(sql, chunk)
            conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error Access", f"Error al insertar registros en la base de datos:\n{e}", parent=parent)
        conn.close()
        return
    finally:
        conn.close()

    # Generar automáticamente el formulario de Access si está disponible
    try:
        from taxa_access_forms import create_taxa_form
        create_taxa_form(path, fields)
    except Exception as e:
        print(f"Aviso: La base de datos se creó pero no se pudieron generar los formularios: {e}")

    if messagebox.askyesno("Éxito", f"Base de datos Access creada correctamente:\n{path}\n\n¿Desea abrirla ahora en Access?", parent=parent):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Exportar a Access", f"No se pudo abrir la base de datos:\n{e}", parent=parent)
