"""
dwca_bridge.py
==============
Puente gestor para la exportación a Darwin Core Archive (DwCa),
integrando parámetros personalizados de tipo de medición y acrónimo.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from dwca_transformer import DwCaTransformer


class DwCaBridge:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def export_dwca_package(self, df: pd.DataFrame, base_name: str = "lesrpe_dwca", measurement_type: str = None, dataset_acronym: str = None) -> Path:
        transformer = DwCaTransformer(self.output_dir)
        return transformer.transform_and_export(df, base_name, measurement_type=measurement_type, dataset_acronym=dataset_acronym)