"""
data_explorer.py
================

Capa de exploración de datos independiente para el Multivisor EIDOS,
con soporte de vistas dinámicas, manejo de vistas sin datasets y descargas multihilo.

Correcciones:
- load_catalog() usa ahora get_datasets_distinct() (lista ligera de PostgREST)
  y solo recurre a la descarga completa como fallback.
- load_datasets(): reintentos persistentes con backoff exponencial por dataset.
  Un fallo transitorio ya no descarta el dataset silenciosamente: se reintenta
  hasta MAX_DATASET_ATTEMPTS y los fracasos definitivos se registran en
  self.last_failed_datasets para que la GUI pueda avisar al usuario.
"""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path

import pandas as pd

from eidos_api import EidosAPI


MAX_DATASET_ATTEMPTS = 6


class DataExplorer:

    def __init__(self, view_name="v_estadolegal"):
        self.api = EidosAPI()
        self.current_view = view_name
        self.api.set_view(view_name)
        self.df = pd.DataFrame()
        self.catalog_df = pd.DataFrame()
        self.loaded_datasets = set()

    def set_view(self, view_name: str):
        """Cambia la vista activa del explorador y de la API."""
        self.current_view = view_name
        self.api.set_view(view_name)

    def load_catalog(self):
        """
        Carga la lista de datasets de la vista actual.
        Primero intenta la consulta ligera (select + distinct); si la vista no
        soporta alguna columna o falla, hace fallback a la descarga completa.
        """
        if not self.catalog_df.empty:
            return self.catalog_df
        try:
            self.catalog_df = self.api.get_datasets_distinct(
                view_name=self.current_view
            )
        except Exception:
            try:
                self.catalog_df = self.api.get_completo(view_name=self.current_view)
            except Exception:
                self.catalog_df = pd.DataFrame()
        return self.catalog_df

    def load_datasets(self, dataset_ids):
        """Carga y concatena los datasets seleccionados en paralelo usando multihilos.
           Si el dataset es sintético (ID 1 en vistas sin iddataset), descarga la vista completa.

           CORREGIDO: cada dataset se reintenta hasta MAX_DATASET_ATTEMPTS con backoff
           exponencial. Los fallos definitivos se registran en self.last_failed_datasets
           en lugar de descartarse silenciosamente."""
        frames = []
        self.last_failed_datasets = []

        def fetch_single(ds_id):
            last_exc = None
            id_col_name = "iddataset"
            has_id_col = any(
                c in self.catalog_df.columns
                for c in ["iddataset", "dataset_id", "id_dataset"]
            )
            if has_id_col:
                id_col_name = next(
                    (c for c in ["iddataset", "dataset_id", "id_dataset"] if c in self.catalog_df.columns),
                    "iddataset"
                )

            for attempt in range(1, MAX_DATASET_ATTEMPTS + 1):
                try:
                    if ds_id == 1 and not has_id_col:
                        df = self.api.get_completo(view_name=self.current_view)
                    else:
                        df = self.api.fetch_all(
                            filters={id_col_name: ds_id},
                            view_name=self.current_view
                        )
                    # Resultado válido (aunque esté vacío): no se reintenta
                    return df
                except Exception as ex:
                    last_exc = ex
                    wait = min(30, 2 ** attempt)
                    print(
                        f"Dataset {ds_id}: intento {attempt}/{MAX_DATASET_ATTEMPTS} "
                        f"fallido ({ex}). Reintentando en {wait}s..."
                    )
                    time.sleep(wait)

            # Agotados los reintentos: registrar el fallo, no descartar en silencio
            self.last_failed_datasets.append((ds_id, str(last_exc)))
            print(f"Dataset {ds_id}: FALLO DEFINITIVO tras {MAX_DATASET_ATTEMPTS} intentos: {last_exc}")
            return None

        max_workers = min(10, len(dataset_ids)) if dataset_ids else 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(fetch_single, dataset_ids)

            for df in results:
                if df is not None and not df.empty:
                    frames.append(df)

        if frames:
            self.df = pd.concat(
                frames,
                ignore_index=True
            )
        else:
            self.df = pd.DataFrame()

        if self.last_failed_datasets:
            print(
                f"Advertencia: {len(self.last_failed_datasets)} dataset(s) no pudieron "
                f"cargarse tras {MAX_DATASET_ATTEMPTS} reintentos: "
                f"{[ds for ds, _ in self.last_failed_datasets]}"
            )

        return self.df

    def datasets(self):
        """Extrae la lista de datasets disponibles adaptándose al esquema de la vista."""
        if self.catalog_df.empty:
            self.load_catalog()
            if self.catalog_df.empty:
                return pd.DataFrame()

        ds_id_col = next((c for c in ["iddataset", "dataset_id", "id_dataset"] if c in self.catalog_df.columns), None)
        ds_name_col = next((c for c in ["dataset", "nombre_dataset", "titulo"] if c in self.catalog_df.columns), None)

        if not ds_id_col:
            return pd.DataFrame([{
                "iddataset": 1,
                "dataset": f"Todos los registros de {self.current_view}",
                "ambito": "General"
            }])

        cols = [ds_id_col, ds_name_col] if ds_name_col else [ds_id_col]
        ambito_col = next((c for c in ["ambito", "idambito"] if c in self.catalog_df.columns), None)
        if ambito_col:
            cols.append(ambito_col)

        sub_df = self.catalog_df[cols].drop_duplicates().sort_values(ds_id_col).reset_index(drop=True)

        rename_map = {ds_id_col: "iddataset"}
        if ds_name_col:
            rename_map[ds_name_col] = "dataset"
        if ambito_col:
            rename_map[ambito_col] = "ambito"
        sub_df = sub_df.rename(columns=rename_map)

        if "ambito" not in sub_df.columns:
            sub_df["ambito"] = "General"

        return sub_df

    def datasets_tree(self):
        """Organiza los datasets de esta vista por ámbito para el árbol de la interfaz."""
        result = {"Nacional": [], "Internacional": [], "Autonómico": [], "General": [], "Otros": []}
        datasets = self.datasets()
        if datasets.empty:
            return result

        for _, row in datasets.iterrows():
            ambito = str(row.get("ambito", "General")).strip()
            item = {"iddataset": row["iddataset"], "dataset": row.get("dataset", "Dataset")}

            if "Nacional" in ambito:
                result["Nacional"].append(item)
            elif any(x in ambito for x in ["Internacional", "Europeo", "Comunitario"]):
                result["Internacional"].append(item)
            elif any(x in ambito for x in ["Autonómico", "Regional", "Comunidad"]):
                result["Autonómico"].append(item)
            elif any(x in ambito for x in ["General", "nan", "None"]):
                result["General"].append(item)
            else:
                result["Otros"].append(item)
        return result

    def national_matrix(self):
        """Genera la matriz nacional LESRPE / CEEA (Dataset 12)."""
        return self.api.build_national_matrix()