"""Exportación tabular fiel y trazable. No genera un archivo DwC-A."""

import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from ipt_model import mapped_dataset, validate_dataset


def open_directory(path):
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _safe_name(value):
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value))[:60] or "tabla"


def _excel_export(path, datasets):
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font
    workbook = Workbook(write_only=True)
    for index, cfg in enumerate(datasets):
        sheet = workbook.create_sheet(f"{index}_{_safe_name(cfg['tipo'])}"[:31])
        sheet.freeze_panes = "A2"
        for row_index, row in enumerate([cfg["fields"]] + cfg["rows"]):
            cells = []
            for value in row:
                cell = WriteOnlyCell(sheet, value="" if value is None else str(value))
                # Los textos que empiezan por '=' son datos, no fórmulas.
                cell.data_type = "s"
                if row_index == 0:
                    cell.font = Font(bold=True)
                cells.append(cell)
            sheet.append(cells)
    workbook.save(path)


def export_project(output_dir, original_path, core, extensions, excel=False):
    errors = [f"Core: {error}" for error in validate_dataset(core, is_core=True)]
    core_ids = set()
    if core.get("id_col") in core.get("fields", []):
        idx = core["fields"].index(core["id_col"])
        core_ids = {str(row[idx]) for row in core["rows"] if len(row) > idx}
    for index, ext in enumerate(extensions, 1):
        errors.extend(f"Extensión {index}: {e}" for e in validate_dataset(ext, core_ids=core_ids))
    if errors:
        raise ValueError("\n".join(errors))
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    prefix = _safe_name(Path(original_path).stem) + "_IPTTransf_"
    # Carpeta nueva por ejecución: no sobrescribe exportaciones previas.
    folder = Path(tempfile.mkdtemp(prefix=prefix, dir=destination))
    try:
        originals = folder / "Old"
        originals.mkdir()
        shutil.copy2(original_path, originals / Path(original_path).name)
        manifest = {
            "format": "IPT-Transformer tabular project", "version": 1,
            "dwca": False, "encoding": "utf-8", "delimiter": "\\t",
            "note": "Tablas preparatorias: no incluye meta.xml ni eml.xml.",
            "datasets": [],
        }
        configs = [core] + list(extensions)
        mapped = [mapped_dataset(cfg) for cfg in configs]
        for index, (source, data) in enumerate(zip(configs, mapped)):
            name = f"{'Core' if index == 0 else 'Extension'}_{index}_{_safe_name(data['tipo'])}.tsv"
            with (folder / name).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
                writer.writerow(data["fields"])
                writer.writerows(data["rows"])
            source_path = source.get("source_path")
            if index and source_path and Path(source_path).is_file():
                shutil.copy2(source_path, originals / f"{index}_{Path(source_path).name}")
            manifest["datasets"].append({
                "file": name, "type": source["tipo"], "rows": len(source["rows"]),
                "source_fields": source["fields"], "output_fields": data["fields"],
                "mapping": source.get("mapping", {}),
                "id_col": source.get("id_col"), "fk_col": source.get("fk_col"),
                "self_id_col": source.get("self_id_col"),
                "self_parent_col": source.get("self_parent_col"),
            })
        if excel:
            _excel_export(folder / "normalizado.xlsx", mapped)
        with (folder / "project.json").open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
        return folder
    except Exception:
        # El directorio pertenece únicamente a esta exportación fallida.
        shutil.rmtree(folder)
        raise
