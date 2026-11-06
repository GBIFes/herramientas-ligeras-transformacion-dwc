"""
star_schema_transformer.py
==========================
Módulo de transformación, normalización y búsqueda avanzada para el 
esquema en estrella Darwin Core (Taxon, MeasurementsOfFacts, VernacularName).
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path


class StarSchemaTransformer:

    def __init__(self, taxon_df: pd.DataFrame, measurements_df: pd.DataFrame, vernacular_df: pd.DataFrame):
        self.taxon_df = taxon_df.copy() if not taxon_df.empty else pd.DataFrame()
        self.measurements_df = measurements_df.copy() if not measurements_df.empty else pd.DataFrame()
        self.vernacular_df = vernacular_df.copy() if not vernacular_df.empty else pd.DataFrame()
        self.unified_df = pd.DataFrame()

    def transform_and_merge(self) -> pd.DataFrame:
        """
        Realiza las transformaciones, limpieza y cruces relacionales en estrella.
        """
        if self.taxon_df.empty:
            return pd.DataFrame()

        # 1. Transformación de Nombres Vernáculos (Aplanar múltiples idiomas/nombres a una lista o cadena)
        vernacular_agg = pd.DataFrame()
        if not self.vernacular_df.empty:
            # Normalizar textos
            self.vernacular_df["vernacularName"] = self.vernacular_df["vernacularName"].astype(str).str.strip()
            
            # Agrupar nombres comunes por taxonID separados por comas
            vernacular_agg = self.vernacular_df.groupby("taxonID").agg({
                "vernacularName": lambda x: ", ".join(x.unique()),
                "languaje": lambda x: ", ".join(str(v) for v in x.unique() if pd.notna(v))
            }).reset_index().rename(columns={
                "vernacularName": "nombres_comunes",
                "languaje": "idiomas_vernaculos"
            })

        # 2. Transformación de Mediciones (MeasurementsOfFacts -> Pivote a columnas o resumen)
        measurements_agg = pd.DataFrame()
        if not self.measurements_df.empty:
            # Si hay tipos de mediciones específicas, podemos pivotarlas o mantenerlas resumidas
            self.measurements_df["measurementType"] = self.measurements_df["measurementType"].astype(str).str.strip()
            self.measurements_df["measurementValue"] = self.measurements_df["measurementValue"].astype(str).str.strip()
            
            # Crear un resumen concatenado de atributos/mediciones
            self.measurements_df["medicion_detalle"] = (
                self.measurements_df["measurementType"] + ": " + self.measurements_df["measurementValue"]
            )
            measurements_agg = self.measurements_df.groupby("taxonID").agg({
                "medicion_detalle": lambda x: " | ".join(x.unique())
            }).reset_index().rename(columns={"medicion_detalle": "detalles_mediciones"})

        # 3. Cruce en Estrella (Star Join) con la tabla central Taxon
        base = self.taxon_df.copy()
        
        # Limpieza básica de la tabla central
        for col in ["scientificName", "kingdom", "family", "genus", "taxonomicStatus"]:
            if col in base.columns:
                base[col] = base[col].astype(str).str.strip()

        if not vernacular_agg.empty:
            base = base.merge(vernacular_agg, on="taxonID", how="left")
            
        if not measurements_agg.empty:
            base = base.merge(measurements_agg, on="taxonID", how="left")

        # Rellenar valores nulos resultantes del cruce
        base["nombres_comunes"] = base.get("nombres_comunes", pd.Series([None]*len(base))).fillna("")
        base["detalles_mediciones"] = base.get("detalles_mediciones", pd.Series([None]*len(base))).fillna("")

        self.unified_df = base
        return self.unified_df

    def search(self, query: str, field: str = "Todas") -> pd.DataFrame:
        """
        Realiza búsquedas avanzadas sobre el dataset unificado.
        """
        if self.unified_df.empty:
            self.transform_and_merge()

        if self.unified_df.empty or not query:
            return self.unified_df

        q = query.lower().strip()
        df = self.unified_df

        try:
            if field == "Todas" or not field:
                # Buscar de forma global en columnas clave
                mask = False
                search_cols = [c for c in ["scientificName", "nombres_comunes", "family", "genus", "detalles_mediciones", "vernacularName"] if c in df.columns]
                for col in search_cols:
                    mask = mask | df[col].astype(str).str.lower().str.contains(q, na=False)
                return df[mask].reset_index(drop=True)
            else:
                if field in df.columns:
                    mask = df[field].astype(str).str.lower().str.contains(q, na=False)
                    return df[mask].reset_index(drop=True)
        except Exception as ex:
            print(fs:=f"Error en búsqueda: {ex}")
            
        return df