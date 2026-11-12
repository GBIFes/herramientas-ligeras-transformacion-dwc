"""
eidos_api.py
============

Cliente de acceso a la API EIDOS con soporte de vistas dinámicas
y compatibilidad con métodos auxiliares.
"""

from __future__ import annotations

import urllib.parse

import pandas as pd
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = (
    "https://pro.iepnb.gob.es/"
    "api/especie"
)

DEFAULT_PAGE_SIZE = 10000
DEFAULT_TIMEOUT = 120


class EidosAPI:

    def __init__(self, view_name="v_estadolegal"):
        self.session = self._create_session()
        self.view_name = view_name

    def _create_session(self):
        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=20,
            pool_maxsize=20
        )
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": "EIDOS-Legal-Explorer"})
        return session

    def set_view(self, view_name: str):
        """Cambia la vista activa de la API."""
        self.view_name = view_name

    def build_url(
        self,
        filters=None,
        limit=None,
        offset=None,
        view_name=None
    ):
        v_name = view_name or self.view_name
        url = f"{BASE_URL}/{v_name}"
        params = []

        if filters:
            for key, value in filters.items():
                # Codificación segura para espacios, acentos y caracteres especiales
                params.append(f"{key}=eq.{urllib.parse.quote(str(value), safe='')}")

        if limit is not None:
            params.append(f"limit={limit}")

        if offset is not None:
            params.append(f"offset={offset}")

        if params:
            url += "?" + "&".join(params)

        return url

    def fetch(
        self,
        filters=None,
        limit=DEFAULT_PAGE_SIZE,
        offset=0,
        view_name=None
    ):
        url = self.build_url(
            filters=filters,
            limit=limit,
            offset=offset,
            view_name=view_name
        )
        response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return pd.DataFrame(response.json())

    def fetch_all(
        self,
        filters=None,
        page_size=DEFAULT_PAGE_SIZE,
        view_name=None
    ):
        dfs = []
        current_offset = 0

        while True:
            df = self.fetch(
                filters=filters,
                limit=page_size,
                offset=current_offset,
                view_name=view_name
            )
            if df.empty:
                break
            dfs.append(df)
            if len(df) < page_size:
                break
            current_offset += page_size

        if not dfs:
            return pd.DataFrame()

        return pd.concat(dfs, ignore_index=True)

    # --------------------------------------------------
    # MÉTODOS COMPATIBLES Y ESPECÍFICOS
    # --------------------------------------------------

    def get_estadolegal_completo(self):
        """Método requerido por DataExplorer para v_estadolegal."""
        return self.fetch_all(view_name="v_estadolegal")

    def get_completo(self, view_name=None):
        return self.fetch_all(view_name=view_name)

    def get_dataset(self, dataset_id, view_name=None):
        return self.fetch_all(
            filters={"iddataset": dataset_id},
            view_name=view_name
        )

    def get_dataset_12(self):
        return self.get_dataset(12, view_name="v_estadolegal")

    def get_dataset_38(self):
        return self.get_dataset(38, view_name="v_estadolegal")

    def get_vigentes(self):
        return self.fetch_all(
            filters={"idvigente": 1},
            view_name="v_estadolegal"
        )

    def datasets(self, df):
        cols = [
            "iddataset",
            "dataset",
            "idambito",
            "ambito"
        ]
        present = [
            c
            for c in cols
            if c in df.columns
        ]
        return (
            df[present]
            .drop_duplicates()
            .sort_values(
                "iddataset"
            )
            .reset_index(
                drop=True
            )
        )

    def build_national_matrix(self):
        df = self.get_dataset_12()

        if df.empty:
            return df

        if "idvigente" in df.columns:
            df = df[df["idvigente"].astype(str).isin(["1", "1.0"])]

        grouped = {}

        for _, row in df.iterrows():
            taxon = row.get("idtaxon")
            nombre = row.get("nombre_aceptado")
            estado = str(row.get("estadolegal", "")).lower()

            if taxon not in grouped:
                grouped[taxon] = {
                    "idtaxon": taxon,
                    "nombre_aceptado": nombre,
                    "LESRPE": "No",
                    "CEEA_EN": "No",
                    "CEEA_VU": "No"
                }

            if "lesrpe" in estado or "protección especial" in estado:
                grouped[taxon]["LESRPE"] = "Yes"

            if "en peligro" in estado:
                grouped[taxon]["CEEA_EN"] = "Yes"

            if "vulnerable" in estado:
                grouped[taxon]["CEEA_VU"] = "Yes"

        return pd.DataFrame(
            grouped.values()
        )