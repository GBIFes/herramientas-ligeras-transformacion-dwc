"""
actualizar_bd.py

Actualiza la base de datos local ejecutando
descargar_taxones.py.

Autor: Javier Estrada
"""

from pathlib import Path
import subprocess
import sys

# ==========================================================
# Rutas
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

SCRIPT_DESCARGA = BASE_DIR / "descargar_taxones.py"

print("\nActualizando base de datos...\n")

print("Script:")
print(SCRIPT_DESCARGA)
print()

try:

    resultado = subprocess.run(
        [sys.executable, str(SCRIPT_DESCARGA)],
        check=True
    )

    print("\n===================================")
    print("Actualización completada")
    print("===================================\n")

except subprocess.CalledProcessError as e:

    print("\nERROR durante la actualización")
    print(e)