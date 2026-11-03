"""Valida o importa un diccionario local; no anuncia sincronización con TDWG."""

import argparse
import json
from pathlib import Path
import shutil

from dwc_manager import get_dictionary_path, save_dictionary, validate_dictionary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="JSON con las categorías Cores y Extensions")
    parser.add_argument("--install", action="store_true", help="Instalar guardando copia del actual")
    args = parser.parse_args()
    with open(args.file, encoding="utf-8-sig") as handle:
        data = validate_dictionary(json.load(handle))
    if args.install:
        target = Path(get_dictionary_path())
        if target.exists():
            # Copia única, sin machacar copias de seguridad anteriores.
            import tempfile
            with tempfile.NamedTemporaryFile(
                prefix="dwc_dictionary_", suffix=".bak.json", dir=target.parent, delete=False
            ) as backup:
                backup_path = backup.name
            shutil.copy2(target, backup_path)
            print(f"Copia de seguridad: {backup_path}")
        save_dictionary(data)
        print(f"Diccionario instalado: {target}")
    else:
        print("Diccionario válido. No se ha modificado ningún archivo.")


if __name__ == "__main__":
    main()
