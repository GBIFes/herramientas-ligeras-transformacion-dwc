"""
star_schema_explorer.py
=======================
Gestor y parser para el esquema en estrella Darwin Core (Taxon, Measurements, Vernacular).
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path

class StarSchemaExplorer:
    def __init__(self, taxon_file: str | Path, measurements_file: str | Path, vernacular_file: str | Path):
        self.taxon_path = Path(taxon_file)
        self.measurements_path = Path(measurements_file)
        self.vernacular_path = Path(vernacular_file)

        self.taxon_df = pd.DataFrame()
        self.measurements_df = pd.DataFrame()
        self.vernacular_df = pd.DataFrame()
        self.consolidated_df = pd.DataFrame()

    def load_schema(self):
        """Carga los tres archivos del esquema en estrella."""
        try:
            if self.taxon_path.exists():
                self.taxon_df = pd.read_csv(self.taxon_path, sep="\t")
            if self.measurements_path.exists():
                self.measurements_df = pd.read_csv(self.measurements_path, sep="\t")
            if self.vernacular_path.exists():
                self.vernacular_df = pd.read_csv(self.vernacular_path, sep="\t")

            # Normalizar la clave relacional (tolera taxonId / taxon_id)
            for df_attr in ("taxon_df", "measurements_df", "vernacular_df"):
                df = getattr(self, df_attr)
                if not df.empty and "taxonID" not in df.columns:
                    key_col = next((c for c in df.columns if c.lower() == "taxonid"), None)
                    if key_col:
                        df = df.rename(columns={key_col: "taxonID"})
                        setattr(self, df_attr, df)
        except Exception as ex:
            print(f"Error cargando el esquema en estrella: {ex}")

    def build_unified_view(self) -> pd.DataFrame:
        """
        Realiza un 'join' relacional utilizando taxonID como clave central
        para unificar Taxonomía, Mediciones/Atributos y Nombres Vernáculos.
        """
        if self.taxon_df.empty:
            self.load_schema()

        if self.taxon_df.empty:
            return pd.DataFrame()

        # Partimos de la tabla central Taxon
        base = self.taxon_df.copy()

        # Unir VernacularName (si existe)
        if not self.vernacular_df.empty:
            base = base.merge(
                self.vernacular_df,
                on="taxonID",
                how="left",
                suffixes=("", "_vernacular")
            )

        # Unir MeasurementsOfFacts (si existe)
        if not self.measurements_df.empty:
            base = base.merge(
                self.measurements_df,
                on="taxonID",
                how="left",
                suffixes=("", "_measurement")
            )

        self.consolidated_df = base
        return self.consolidated_df

    def get_taxon_details(self, taxon_id: str | int) -> dict:
        """Extrae el perfil completo de un taxón específico cruzando las tablas."""
        if self.consolidated_df.empty:
            self.build_unified_view()

        filtered = self.consolidated_df[self.consolidated_df["taxonID"] == taxon_id]
        if filtered.empty:
            return {}

        return filtered.to_dict(orient="records")