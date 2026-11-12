"""
exporter.py
===========

Exportaciones para EIDOS Legal Explorer

Formatos:

    - Excel
    - CSV
    - SQLite
    - Parquet

Además:

    - apertura automática de Excel
"""

from __future__ import annotations

import csv
import os
import sqlite3

from pathlib import Path

import pandas as pd


class Exporter:

    def __init__(
        self,
        output_directory
    ):

        self.output_directory = Path(
            output_directory
        )

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

    # --------------------------------------------------
    # PATH
    # --------------------------------------------------

    def build_path(
        self,
        filename,
        extension
    ):

        if not extension.startswith("."):

            extension = "." + extension

        return (
            self.output_directory
            / f"{filename}{extension}"
        )

    # --------------------------------------------------
    # CSV
    # --------------------------------------------------

    def export_csv(
        self,
        df,
        filename
    ):

        path = self.build_path(
            filename,
            ".csv"
        )

        df.to_csv(
            path,
            index=False,
            encoding="utf-8",
            sep="\t",
            quoting=csv.QUOTE_ALL
        )

        return path

    # --------------------------------------------------
    # EXCEL
    # --------------------------------------------------

    def export_excel(
        self,
        df,
        filename,
        sheet_name="Datos"
    ):

        path = self.build_path(
            filename,
            ".xlsx"
        )

        with pd.ExcelWriter(
            path,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                index=False,
                sheet_name=sheet_name
            )

        return path

    # --------------------------------------------------
    # EXCEL MULTIHOJA
    # --------------------------------------------------

    def export_excel_sheets(
        self,
        filename,
        sheets
    ):

        path = self.build_path(
            filename,
            ".xlsx"
        )

        with pd.ExcelWriter(
            path,
            engine="openpyxl"
        ) as writer:

            for name, df in sheets.items():

                df.to_excel(
                    writer,
                    index=False,
                    sheet_name=name[:31]
                )

        return path

    # --------------------------------------------------
    # SQLITE
    # --------------------------------------------------

    def export_sqlite(
        self,
        df,
        filename,
        table_name="estadolegal"
    ):

        path = self.build_path(
            filename,
            ".db"
        )

        if path.exists():

            path.unlink()

        conn = sqlite3.connect(
            path
        )

        try:

            df.to_sql(
                table_name,
                conn,
                if_exists="replace",
                index=False
            )

        finally:

            conn.close()

        return path

    # --------------------------------------------------
    # PARQUET
    # --------------------------------------------------

    def export_parquet(
        self,
        df,
        filename
    ):

        path = self.build_path(
            filename,
            ".parquet"
        )

        df.to_parquet(
            path,
            index=False
        )

        return path

    # --------------------------------------------------
    # DICCIONARIO
    # --------------------------------------------------

    def export_dictionary(
        self,
        dictionary_df,
        filename
    ):

        return self.export_excel(
            dictionary_df,
            filename,
            "Diccionario"
        )

    # --------------------------------------------------
    # TODO
    # --------------------------------------------------

    def export_all(
        self,
        df,
        basename="eidos"
    ):

        result = {}

        result["xlsx"] = (
            self.export_excel(
                df,
                basename
            )
        )

        result["csv"] = (
            self.export_csv(
                df,
                basename
            )
        )

        result["sqlite"] = (
            self.export_sqlite(
                df,
                basename
            )
        )

        try:

            result["parquet"] = (
                self.export_parquet(
                    df,
                    basename
                )
            )

        except Exception:

            result["parquet"] = None

        return result

    # --------------------------------------------------
    # ABRIR EXCEL
    # --------------------------------------------------

    def open_excel(
        self,
        excel_file
    ):

        try:

            import platform
            import subprocess

            system = platform.system()

            if system == "Windows":
                os.startfile(str(excel_file))
            elif system == "Darwin":
                subprocess.call(["open", str(excel_file)])
            else:
                subprocess.call(["xdg-open", str(excel_file)])

            return True

        except Exception:

            return False

    # --------------------------------------------------
    # EXPORTAR Y ABRIR
    # --------------------------------------------------

    def export_all_and_open(
        self,
        df,
        basename="eidos"
    ):

        files = self.export_all(
            df,
            basename
        )

        excel_file = files.get(
            "xlsx"
        )

        if excel_file:

            self.open_excel(
                excel_file
            )

        return files


if __name__ == "__main__":

    df = pd.DataFrame(
        {
            "idtaxon": [1, 2, 3],
            "nombre": [
                "A",
                "B",
                "C"
            ]
        }
    )

    exporter = Exporter(
        "export"
    )

    files = (
        exporter.export_all_and_open(
            df,
            "prueba"
        )
    )

    print(files)