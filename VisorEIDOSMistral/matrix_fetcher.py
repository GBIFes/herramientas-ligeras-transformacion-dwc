# matrix_fetcher.py

import pandas as pd

from config import (
    BASE_URL_API,
    CATEGORY_ENDPOINTS,
    REQUEST_TIMEOUT,
    crear_sesion_robusta as create_session
)


class MatrixFetcher:

    def __init__(self):

        self.session = create_session()

    def _query_category(self, category):

        endpoint = CATEGORY_ENDPOINTS.get(category)

        if not endpoint:
            return pd.DataFrame(
                columns=[
                    "EIDOS_ID",
                    "scientificName"
                ]
            )

        url = f"{BASE_URL_API}/{endpoint}"

        r = self.session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        r.raise_for_status()

        data = r.json()

        if not data:
            return pd.DataFrame(
                columns=[
                    "EIDOS_ID",
                    "scientificName"
                ]
            )

        df = pd.DataFrame(data)

        # Adapta el nombre de columnas según la vista devuelta por la API
        id_col = next(
            (c for c in ("taxonid", "idtaxon", "taxon_id") if c in df.columns),
            None
        )
        name_col = next(
            (c for c in ("scientificname", "nombre_aceptado", "nombre_cientifico") if c in df.columns),
            None
        )

        if not id_col or not name_col:
            return pd.DataFrame(
                columns=[
                    "EIDOS_ID",
                    "scientificName"
                ]
            )

        df = df.rename(columns={id_col: "EIDOS_ID", name_col: "scientificName"})

        return df[
            [
                "EIDOS_ID",
                "scientificName"
            ]
        ].drop_duplicates()

    def build_matrix(
        self,
        categories,
        progress_callback=None
    ):

        category_data = {}

        total = len(categories)

        for i, category in enumerate(categories, start=1):

            if progress_callback:
                progress_callback(
                    f"Consultando {category}..."
                )

            category_data[category] = \
                self._query_category(category)

            if progress_callback:
                percent = int(
                    (i / total) * 100
                )

                progress_callback(
                    f"{category} completado",
                    percent
                )

        universe = []

        for df in category_data.values():

            if len(df):
                universe.append(df)

        if not universe:
            return pd.DataFrame()

        universe_df = pd.concat(
            universe,
            ignore_index=True
        )

        universe_df = (
            universe_df
            .drop_duplicates()
            .reset_index(drop=True)
        )

        matrix = universe_df.copy()

        for category in categories:

            ids = set(
                category_data[category]["EIDOS_ID"]
            )

            matrix[category] = matrix[
                "EIDOS_ID"
            ].apply(
                lambda x:
                "Yes"
                if x in ids
                else "No"
            )

        return matrix