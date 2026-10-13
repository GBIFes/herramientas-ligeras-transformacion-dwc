"""
dwca_access_forms.py
Genera en un .accdb ya creado los formularios de visualización equivalentes
a los del visor Tkinter:

    frm_core        -> campos del core (izquierda) + pestañas con las
                       extensiones y el EML (derecha), igual que el visor
    sub_<extensión> -> subformulario (formulario continuo) por extensión,
                       enlazado por id con el core
    frm_eml         -> metadatos EML (hoja de datos)

Se hace por automatización COM de Access (pywin32), sin inyectar código VBA.
Requiere Microsoft Access completo instalado (no basta el motor ACE).
La navegación (primero / anterior / siguiente / último / ir a registro) y el
filtrado (Filtro por formulario, clic derecho en un campo) son nativos de Access.
"""

import win32com.client

# Constantes de Access
AC_FORM = 2
AC_TEXTBOX = 109
AC_SUBFORM = 112
AC_TABCTL = 123
AC_PAGE = 124
AC_SAVE_YES = 1
AC_QUIT_SAVE_NONE = 2

VIEW_SINGLE = 0
VIEW_CONTINUOUS = 1
VIEW_DATASHEET = 2

# Medidas en twips (1 cm ≈ 567 twips)
MARGIN = 100
LABEL_W = 3000
TEXT_W = 6200
ROW_H = 330
MEMO_H = 1100
GAP = 60

TAB_W = 9600
TAB_H = 9000

READ_ONLY = True          # los formularios son solo de visualización


def _create_fields_form(acc, schema, view, as_sub):
    """
    Crea un formulario con un cuadro de texto (y su etiqueta) por columna.
    Devuelve (frm, nombre_temporal, borde_derecho). El formulario queda
    abierto en vista Diseño para poder seguir añadiendo controles.
    """
    frm = acc.CreateForm()
    tmp = frm.Name
    frm.RecordSource = schema["table"]
    frm.DefaultView = view
    try:
        frm.ScrollBars = 3
    except Exception:  # noqa: BLE001
        pass

    if READ_ONLY:
        for prop in ("AllowEdits", "AllowAdditions", "AllowDeletions"):
            try:
                setattr(frm, prop, False)
            except Exception:  # noqa: BLE001
                pass
    if as_sub:
        for prop in ("NavigationButtons", "RecordSelectors"):
            try:
                setattr(frm, prop, False)
            except Exception:  # noqa: BLE001
                pass

    text_left = MARGIN + LABEL_W + 100
    top = MARGIN
    for col, caption, typ in zip(schema["cols"], schema["captions"], schema["types"]):
        memo = typ == "LONGTEXT"
        h = MEMO_H if memo else ROW_H
        ctl = acc.CreateControl(tmp, AC_TEXTBOX, 0, "", col, text_left, top, TEXT_W, h)
        ctl.Name = f"txt_{col}"
        if memo:
            try:
                ctl.ScrollBars = 2
            except Exception:  # noqa: BLE001
                pass
        # Etiqueta asociada (se crea sola junto al cuadro de texto)
        try:
            lbl = ctl.Controls.Item(0)
            lbl.Caption = caption if view == VIEW_DATASHEET else f"{caption}:"
            lbl.Left = MARGIN
            lbl.Top = top
            lbl.Width = LABEL_W
            lbl.Height = ROW_H
        except Exception:  # noqa: BLE001
            pass
        top += h + GAP

    try:
        frm.Section(0).Height = top + MARGIN
    except Exception:  # noqa: BLE001
        pass
    try:
        frm.Width = text_left + TEXT_W + MARGIN
    except Exception:  # noqa: BLE001
        pass

    return frm, tmp, text_left + TEXT_W + 300


def _save_form(acc, tmp_name, final_name):
    acc.DoCmd.Close(AC_FORM, tmp_name, AC_SAVE_YES)
    acc.DoCmd.Rename(final_name, AC_FORM, tmp_name)


def _add_tabs(acc, tmp, left, pages):
    """
    Añade al formulario abierto 'tmp' un control de pestañas.
    pages = [(titulo, nombre_subformulario, enlazar_por_id), ...]
    """
    tab = acc.CreateControl(tmp, AC_TABCTL, 0, "", "", left, MARGIN, TAB_W, TAB_H)
    tab.Name = "tab_ext"

    # Un control de pestañas nuevo trae 2 páginas: ajustar al nº necesario
    while tab.Pages.Count < len(pages):
        acc.CreateControl(tmp, AC_PAGE, 0, tab.Name)
    while tab.Pages.Count > len(pages):
        acc.DeleteControl(tmp, tab.Pages.Item(tab.Pages.Count - 1).Name)

    for i, (title, sub_name, linked) in enumerate(pages):
        page = tab.Pages.Item(i)
        page.Caption = title[:40]
        sub = acc.CreateControl(tmp, AC_SUBFORM, 0, page.Name, "",
                                MARGIN, 450, TAB_W - 2 * MARGIN, TAB_H - 700)
        sub.Name = f"ctl_{sub_name}"
        sub.SourceObject = f"Form.{sub_name}"
        if linked:
            sub.LinkMasterFields = "id"
            sub.LinkChildFields = "id"


def create_forms(accdb_path, schema, eml_schema=None):
    """
    schema      : lista de dicts (el primero es el core, el resto extensiones)
                  con claves table, cols, captions, types, label.
    eml_schema  : dict equivalente para eml_metadata, o None.
    """
    acc = win32com.client.Dispatch("Access.Application")
    try:
        acc.Visible = False
        acc.OpenCurrentDatabase(accdb_path)
        try:
            acc.DoCmd.SetWarnings(False)
        except Exception:  # noqa: BLE001
            pass

        pages = []

        # --- Subformularios de extensiones -------------------
        for ext in schema[1:]:
            sub_name = f"sub_{ext['table']}"
            _frm, tmp, _right = _create_fields_form(acc, ext, VIEW_CONTINUOUS, as_sub=True)
            _save_form(acc, tmp, sub_name)
            linked = "id" in ext["cols"] and "id" in schema[0]["cols"]
            pages.append((ext["label"], sub_name, linked))

        # --- Formulario EML ----------------------------------
        if eml_schema is not None:
            _frm, tmp, _right = _create_fields_form(acc, eml_schema, VIEW_DATASHEET, as_sub=True)
            _save_form(acc, tmp, "frm_eml")
            pages.append((eml_schema["label"], "frm_eml", False))

        # --- Formulario principal (core) ---------------------
        core = schema[0]
        _frm, tmp, right = _create_fields_form(acc, core, VIEW_SINGLE, as_sub=False)
        if pages:
            _add_tabs(acc, tmp, right, pages)
            try:
                _frm.Width = right + TAB_W + MARGIN
            except Exception:  # noqa: BLE001
                pass
        _save_form(acc, tmp, "frm_core")

        # --- Abrir frm_core al arrancar la base de datos -----
        try:
            db = acc.CurrentDb()
            try:
                db.Properties.Item("StartupForm").Value = "frm_core"
            except Exception:  # noqa: BLE001
                prop = db.CreateProperty("StartupForm", 10, "frm_core")  # dbText = 10
                db.Properties.Append(prop)
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            acc.CloseCurrentDatabase()
        except Exception:  # noqa: BLE001
            pass
        try:
            acc.Quit(AC_QUIT_SAVE_NONE)
        except Exception:  # noqa: BLE001
            pass
