"""
actualizar_bd.py

Actualiza la tabla especies a partir
del fichero de descarga que genera
descargar_taxones.py.

Uso:

    python actualizar_bd.py
"""

from pathlib import Path
import sqlite3

import pandas as pd

from modulos.config import (
    DATA_DIR,
    DB
)


# ==========================================================
# FICHERO
# ==========================================================

CSV = (
    DATA_DIR /
    "taxones_eidos.csv"
)


# ==========================================================
# SQLITE
# ==========================================================

def conectar():

    return sqlite3.connect(DB)


# ==========================================================
# COMPROBACIONES
# ==========================================================

def comprobar_csv():

    if not CSV.exists():

        raise FileNotFoundError(
            f"No existe:\n{CSV}"
        )


# ==========================================================
# CARGA
# ==========================================================

def cargar_csv():

    comprobar_csv()

    return pd.read_csv(
        CSV,
        encoding="utf-8"
    )


# ==========================================================
# SUSTITUCIÓN
# ==========================================================

def actualizar():

    df = cargar_csv()

    conn = conectar()

    df.to_sql(

        "especies",

        conn,

        if_exists="replace",

        index=False

    )

    conn.close()

    return len(df)


# ==========================================================
# MAIN
# ==========================================================

def main():

    total = actualizar()

    print()

    print(
        f"Registros cargados: "
        f"{total:,}"
    )

    print()


if __name__ == "__main__":

    main()