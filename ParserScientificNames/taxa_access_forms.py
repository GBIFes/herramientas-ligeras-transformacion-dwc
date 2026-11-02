"""
taxa_access_forms.py
====================
Genera de forma automatizada un formulario de visualización en el archivo .accdb
creado para los datos taxonómicos parseados.
"""

import win32com.client

# Constantes de Access
AC_FORM = 2
AC_TEXTBOX = 109
AC_SAVE_YES = 1
AC_QUIT_SAVE_NONE = 2

VIEW_SINGLE = 0

# Medidas en twips (1 cm ≈ 567 twips)
MARGIN = 100
LABEL_W = 3500
TEXT_W = 6000
ROW_H = 330
GAP = 60
READ_ONLY = True

def create_taxa_form(accdb_path, fields):
    """
    Crea un formulario principal 'frm_taxonomia' en la base de datos Access
    mostrando todos los campos del parseo en vista de registro único.
    """
    acc = win32com.client.Dispatch("Access.Application")
    try:
        try:
            acc.Visible = False
        except Exception:
            pass

        acc.OpenCurrentDatabase(accdb_path)
        
        try:
            acc.DoCmd.SetWarnings(False)
        except Exception:
            pass

        # --- Crear Formulario ---
        frm = acc.CreateForm()
        tmp_name = frm.Name
        frm.RecordSource = "taxonomia_parseada"
        frm.DefaultView = VIEW_SINGLE
        
        try:
            frm.ScrollBars = 3  # Ambas barras
        except Exception:
            pass

        if READ_ONLY:
            for prop in ("AllowEdits", "AllowAdditions", "AllowDeletions"):
                try:
                    setattr(frm, prop, False)
                except Exception:
                    pass

        # --- Añadir controles (Etiqueta y Cuadro de Texto por campo) ---
        text_left = MARGIN + LABEL_W + 100
        top = MARGIN
        
        for f in fields:
            safe_col = f.replace("-", "_").replace(" ", "_")[:64]
            ctl = acc.CreateControl(tmp_name, AC_TEXTBOX, 0, "", safe_col, text_left, top, TEXT_W, ROW_H)
            ctl.Name = f"txt_{safe_col}"
            
            try:
                lbl = ctl.Controls.Item(0)
                lbl.Caption = f"{f}:"
                lbl.Left = MARGIN
                lbl.Top = top
                lbl.Width = LABEL_W
                lbl.Height = ROW_H
            except Exception:
                pass
            
            top += ROW_H + GAP

        try:
            frm.Section(0).Height = top + MARGIN
        except Exception:
            pass
        try:
            frm.Width = text_left + TEXT_W + MARGIN
        except Exception:
            pass

        # Guardar y renombrar como frm_taxonomia
        acc.DoCmd.Close(AC_FORM, tmp_name, AC_SAVE_YES)
        acc.DoCmd.Rename("frm_taxonomia", AC_FORM, tmp_name)

        # Configurar formulario de inicio (StartupForm)
        try:
            db = acc.CurrentDb()
            try:
                db.Properties.Item("StartupForm").Value = "frm_taxonomia"
            except Exception:
                prop = db.CreateProperty("StartupForm", 10, "frm_taxonomia")  # dbText = 10
                db.Properties.Append(prop)
        except Exception:
            pass

    except Exception as e:
        print(f"Aviso al generar formularios de Access: {e}")
    finally:
        try:
            acc.CloseCurrentDatabase()
        except Exception:
            pass
        try:
            acc.Quit(AC_QUIT_SAVE_NONE)
        except Exception:
            pass