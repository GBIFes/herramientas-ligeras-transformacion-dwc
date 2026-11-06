"""
dwca_bridge.py
==============
Puente optimizado para la exportación de datos de EIDOS al estándar Darwin Core 
(Core + Extensiones + ZIP) directamente en el directorio elegido por el usuario.
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path
from dwca_transformer import DwCaTransformer


class DwCaBridge:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_dwca_package(self, df: pd.DataFrame, base_name: str = "lesrpe_dwca") -> Path:
        """
        Transforma los datos al esquema Darwin Core y genera el paquete ZIP 
        en el directorio de destino especificado.
        """
        if df is None or df.empty:
            raise ValueError("El DataFrame proporcionado está vacío.")

        transformer = DwCaTransformer(self.output_dir)
        dwca_zip_path = transformer.transform_and_export(df, base_name)
        return dwca_zip_path