"""
diagnostico_access.py
Comprueba paso a paso si Python puede crear formularios y módulos en Access.

Uso (en la terminal de VS Code, en la carpeta del visor):
    python diagnostico_access.py
    python diagnostico_access.py "C:\\ruta\\mi_base.accdb"     (además lista los formularios y módulos de esa base)
"""

import os
import struct
import sys
import tempfile

print(f"Python de {struct.calcsize('P') * 8} bits")


def paso(nombre, fn):
    try:
        r = fn()
        print(f"[OK]    {nombre}" + (f"  ->  {r}" if r not in (None, "") else ""))
        return True, r
    except Exception as e:  # noqa: BLE001
        print(f"[FALLO] {nombre}: {e}")
        return False, None


ok, _ = paso("Importar pywin32", lambda: __import__("win32com.client"))
if not ok:
    print("\nInstala pywin32:  python -m pip install pywin32")
    sys.exit(1)
import win32com.client  # noqa: E402

# --- 1. Crear una base de datos temporal --------------------------------
tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "diagnostico.accdb")


def crear_db():
    ultimo = None
    for prov in ("Microsoft.ACE.OLEDB.16.0", "Microsoft.ACE.OLEDB.12.0"):
        try:
            cat = win32com.client.Dispatch("ADOX.Catalog")
            cat.Create(f"Provider={prov};Data Source={db_path};")
            cat.ActiveConnection.Close()
            return prov
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise RuntimeError(ultimo)


ok, _ = paso("Crear .accdb temporal (ADOX)", crear_db)
if not ok:
    sys.exit(1)

# --- 2. Arrancar Access por COM -----------------------------------------
ok, acc = paso("Iniciar Access.Application", lambda: win32com.client.Dispatch("Access.Application"))
if not ok:
    print("\nAccess completo no está instalado o no está registrado para COM.")
    sys.exit(1)

try:
    paso("Versión de Access", lambda: acc.Version)
    paso("Abrir la base de datos", lambda: acc.OpenCurrentDatabase(db_path))

    # --- 3. Formularios --------------------------------------------------
    def crear_form():
        frm = acc.CreateForm()
        tmp = frm.Name
        ctl = acc.CreateControl(tmp, 109, 0, "", "", 1000, 100, 3000, 300)
        ctl.Name = "txt_prueba"
        acc.DoCmd.Close(2, tmp, 1)
        acc.DoCmd.Rename("diag_form", 2, tmp)
        return "formulario guardado como diag_form"

    paso("Crear, guardar y renombrar un formulario", crear_form)

    # --- 4. Módulo VBA: vía LoadFromText --------------------------------
    def cargar_modulo():
        ruta = os.path.join(tmpdir, "modDiag.bas")
        with open(ruta, "w", encoding="cp1252", newline="") as f:
            f.write('Attribute VB_Name = "modDiag"\r\nOption Compare Database\r\nOption Explicit\r\n\r\n'
                    'Public Function Hola() As Boolean\r\n    Hola = True\r\nEnd Function\r\n')
        acc.LoadFromText(5, "modDiag", ruta)
        nombres = [acc.CurrentProject.AllModules.Item(i).Name
                   for i in range(acc.CurrentProject.AllModules.Count)]
        return f"módulos en la base: {nombres}"

    ok_lt, _ = paso("Instalar módulo VBA con LoadFromText", cargar_modulo)

    # --- 5. Módulo VBA: vía VBE (necesita confiar en el modelo de objetos de VBA)
    ok_vbe, _ = paso("Acceder al proyecto VBA (VBE)", lambda: acc.VBE.ActiveVBProject.Name)

    print()
    if ok_lt or ok_vbe:
        print("Conclusión: Access puede crear formularios y módulos desde Python.")
    else:
        print("Conclusión: no se puede instalar ningún módulo VBA. Activa en Access:")
        print("  Archivo > Opciones > Centro de confianza > Configuración del Centro de confianza")
        print("  > Configuración de macros > 'Confiar en el acceso al modelo de objetos de proyectos de VBA'")
        print("  (cierra Access del todo y vuelve a ejecutar este diagnóstico)")

    # --- 6. Listar objetos de la base real (opcional) --------------------
    if len(sys.argv) > 1:
        real = sys.argv[1]
        print(f"\nContenido de {real}:")
        try:
            acc.CloseCurrentDatabase()
            acc.OpenCurrentDatabase(real)
            for etiqueta, col in (("Formularios", acc.CurrentProject.AllForms),
                                  ("Módulos", acc.CurrentProject.AllModules)):
                nombres = [col.Item(i).Name for i in range(col.Count)]
                print(f"  {etiqueta}: {nombres if nombres else '(ninguno)'}")
        except Exception as e:  # noqa: BLE001
            print(f"  [FALLO] no se pudo abrir esa base: {e}")
finally:
    try:
        acc.CloseCurrentDatabase()
    except Exception:  # noqa: BLE001
        pass
    try:
        acc.Quit(2)
    except Exception:  # noqa: BLE001
        pass
