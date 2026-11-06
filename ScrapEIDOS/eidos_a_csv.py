#!/usr/bin/env python3
"""Exporta cuadrículas EIDOS por taxón a CSV y, opcionalmente, GeoJSON.

Instalación: pip install requests "shapely>=2.1" pyproj
Ejemplo:
    python eidos_a_csv.py 10903 --csv eidos_10903.csv --geojson eidos_10903.geojson

También se puede importar exportar() y pasarle una lista de IDs.
El CSV contiene centros de cuadrículas, NO localizaciones de observaciones.
utm es el código del campo cuadricula, no un par de coordenadas UTM.
La geometría se solicita en WGS84. Su centroide se calcula en una proyección
local equivalente y después se transforma a latitud/longitud WGS84.

Servicio:
https://iepnb.gob.es/geoserver/especies/wfs
Documentación de consulta:
https://docs.geoserver.org/latest/en/user/services/wfs/reference.html
"""

import argparse
import csv
import json
import os
import re
import tempfile
from pathlib import Path

import requests
from pyproj import CRS, Transformer
from requests.adapters import HTTPAdapter
from shapely import transform
from shapely.geometry import shape
from urllib3.util.retry import Retry

URL = "https://iepnb.gob.es/geoserver/especies/wfs"


def normalizar_id(valor):
    """Normaliza y valida los identificadores numéricos de EIDOS."""
    valor = str(valor).strip()
    # Eliminar posibles prefijos de URL o parámetros extras si se pasan accidentalmente
    if "/eidos/" in valor:
        valor = valor.split("/eidos/")[-1].strip("/")
    match = re.search(r"(\d+)", valor)
    if not match:
        raise ValueError(f"taxonId no válido: {valor!r}; se esperan dígitos.")
    # str(int(...)) garantiza eliminar ceros a la izquierda (ej. "010903" -> "10903")
    return str(int(match.group(1)))


def filtro_taxon(taxon_id):
    """Coincidencia de elemento completo en una lista separada por comas."""
    taxon_id_norm = normalizar_id(taxon_id)
    # Probar coincidencia con o sin ceros por flexibilidad en GeoServer
    taxon_id_padded = taxon_id_norm.zfill(6)
    
    campo = "lista_idstaxon_filtro"
    filtro_norm = (
        f"({campo} = '{taxon_id_norm}' OR "
        f"{campo} LIKE '{taxon_id_norm},%' OR "
        f"{campo} LIKE '%,{taxon_id_norm},%' OR "
        f"{campo} LIKE '%,{taxon_id_norm}')"
    )
    if taxon_id_padded != taxon_id_norm:
        filtro_padded = (
            f"({campo} = '{taxon_id_padded}' OR "
            f"{campo} LIKE '{taxon_id_padded},%' OR "
            f"{campo} LIKE '%,{taxon_id_padded},%' OR "
            f"{campo} LIKE '%,{taxon_id_padded}')"
        )
        return f"({filtro_norm} OR {filtro_padded})"
    return filtro_norm


def consultar(session, taxon_id, page_size=1000):
    inicio = 0
    vistos = set()
    taxon_id_clean = normalizar_id(taxon_id)
    
    while True:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "especies:distribucion_especies",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "propertyName": "id,cuadricula,geom",
            "CQL_FILTER": filtro_taxon(taxon_id_clean),
            "sortBy": "id A",
            "count": page_size,
            "startIndex": inicio,
        }
        response = session.get(URL, params=params, timeout=(15, 120))
        response.raise_for_status()
        
        # Validar si GeoServer devolvió XML de error pese al status HTTP 200 OK
        if response.text.strip().startswith("<"):
            raise RuntimeError(
                f"WFS devolvió XML en lugar de JSON para {taxon_id_clean}: {response.text[:500]}"
            )
            
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"WFS no devolvió JSON válido para {taxon_id_clean}: {response.text[:800]}"
            ) from exc

        if data.get("type") != "FeatureCollection":
            raise RuntimeError(f"Respuesta WFS inesperada: {str(data)[:800]}")
            
        features = data.get("features", [])
        if not features:
            total = str(data.get("numberMatched", "unknown"))
            if total.isdigit() and inicio < int(total):
                raise RuntimeError("El WFS terminó antes del total anunciado.")
            break

        for feature in features:
            clave = feature["properties"]["id"]
            if clave in vistos:
                raise RuntimeError(
                    "El WFS repitió un id: comprueba paginación/estabilidad de datos."
                )
            vistos.add(clave)
            yield feature

        inicio += len(features)
        total = str(data.get("numberMatched", "unknown"))
        if total.isdigit() and inicio >= int(total):
            break


def centro_wgs84(geometry):
    geom = shape(geometry)
    if geom.is_empty or not geom.is_valid:
        raise ValueError("Geometría vacía o no válida; no se genera un centro ficticio.")
    xmin, ymin, xmax, ymax = geom.bounds
    local = CRS.from_proj4(
        f"+proj=laea +lat_0={(ymin + ymax) / 2} "
        f"+lon_0={(xmin + xmax) / 2} +datum=WGS84 +units=m +no_defs"
    )
    proyectar = Transformer.from_crs("EPSG:4326", local, always_xy=True)
    desproyectar = Transformer.from_crs(local, "EPSG:4326", always_xy=True)
    centro = transform(geom, proyectar.transform, interleaved=False).centroid
    lon, lat = desproyectar.transform(centro.x, centro.y)
    return lat, lon


def exportar(taxon_ids, csv_path="eidos.csv", geojson_path=None):
    ids = list(dict.fromkeys(normalizar_id(t) for t in taxon_ids))
    if not ids:
        raise ValueError("Proporciona al menos un taxonId.")
    csv_path = Path(csv_path)
    if geojson_path and csv_path.resolve() == Path(geojson_path).resolve():
        raise ValueError("CSV y GeoJSON deben tener rutas distintas.")
    retry = Retry(
        total=4, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"], respect_retry_after_header=True,
    )
    geometries = []
    filas = 0
    temporal = None
    try:
        with requests.Session() as session, tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="",
            dir=csv_path.parent, suffix=".csv.tmp", delete=False,
        ) as output:
            temporal = output.name
            session.mount("https://", HTTPAdapter(max_retries=retry))
            writer = csv.writer(output, delimiter=";")
            writer.writerow(["taxonId", "utm", "latdecimal", "longdecimal"])
            for taxon_id in ids:
                n = 0
                for feature in consultar(session, taxon_id):
                    lat, lon = centro_wgs84(feature["geometry"])
                    utm = feature["properties"]["cuadricula"]
                    writer.writerow([taxon_id, utm, f"{lat:.8f}", f"{lon:.8f}"])
                    if geojson_path:
                        geometries.append({
                            "type": "Feature",
                            "geometry": feature["geometry"],
                            "properties": {"taxonId": taxon_id, "utm": utm},
                        })
                    filas += 1
                    n += 1
                print(f"taxonId {taxon_id}: {n} cuadrículas")
        os.replace(temporal, csv_path)
        temporal = None
    finally:
        if temporal and os.path.exists(temporal):
            os.unlink(temporal)
    if geojson_path:
        with open(geojson_path, "w", encoding="utf-8") as output:
            json.dump(
                {"type": "FeatureCollection", "features": geometries},
                output, ensure_ascii=False,
            )
    return filas


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("taxon_ids", nargs="+", help="IDs taxonómicos EIDOS")
    parser.add_argument("--csv", default="eidos.csv", help="Ruta del CSV de salida")
    parser.add_argument("--geojson", help="Ruta opcional para conservar los polígonos")
    args = parser.parse_args()
    exportar(args.taxon_ids, args.csv, args.geojson)