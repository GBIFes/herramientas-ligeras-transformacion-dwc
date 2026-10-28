"""Integración WFS, persistencia y mapas Leaflet para ScrapEIDOS."""
import json
import os
import re
import subprocess
import sys
import tempfile
import webbrowser
from html import escape
from pathlib import Path

import pandas as pd

from config import crear_sesion_robusta
from eidos_a_csv import consultar, centro_wgs84

COLUMNAS_COORD = ["taxonId", "utm", "latdecimal", "longdecimal"]
COLUMNAS_ESTADO = ["EIDOS_ID", "estado", "cuadriculas", "detalle"]


def extraer_id(valor):
    texto = str(valor).strip()
    match = re.fullmatch(r"(?:https?://[^/]+/.*/eidos/)?([0-9]+)/?", texto)
    if not match:
        raise ValueError(f"Identificador EIDOS no válido: {texto!r}")
    return str(int(match.group(1)))


def recopilar_coordenadas(identificadores, progreso=None):
    """Consulta IDs únicos; un fallo no impide guardar los demás taxones.

    Si una página o una geometría falla, no publica datos parciales del taxón.
    Los errores se diferencian expresamente de «sin distribución».
    """
    filas, features, estados = [], [], []
    ids = list(dict.fromkeys(str(i).strip() for i in identificadores if str(i).strip()))
    with crear_sesion_robusta() as session:
        for numero, valor in enumerate(ids, 1):
            try:
                e_id = extraer_id(valor)
                filas_taxon, features_taxon = [], []
                for feature in consultar(session, e_id):
                    lat, lon = centro_wgs84(feature["geometry"])
                    utm = feature["properties"]["cuadricula"]
                    filas_taxon.append([e_id, utm, round(lat, 8), round(lon, 8)])
                    features_taxon.append({
                        "type": "Feature",
                        "geometry": feature["geometry"],
                        "properties": {"taxonId": e_id, "utm": utm},
                    })
                filas.extend(filas_taxon)
                features.extend(features_taxon)
                estados.append([
                    e_id, "ok" if filas_taxon else "sin_distribucion",
                    len(filas_taxon), "",
                ])
            except Exception as exc:
                estados.append([valor, "error", 0, str(exc)])
            if progreso:
                progreso(numero, len(ids))
    return (
        pd.DataFrame(filas, columns=COLUMNAS_COORD),
        {"type": "FeatureCollection", "features": features},
        pd.DataFrame(estados, columns=COLUMNAS_ESTADO),
    )


def _reemplazar_atomico(ruta, escribir):
    ruta = Path(ruta)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as salida:
            escribir(salida)
        os.replace(tmp, ruta)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def guardar_cartografia(df_coord, geojson, df_estado, directorio, nombre_base):
    """Persiste incluso tablas vacías, con cabeceras y estado de consulta."""
    Path(directorio).mkdir(parents=True, exist_ok=True)
    rutas = {
        "csv": Path(directorio) / f"{nombre_base}_Coordenadas.csv",
        "geojson": Path(directorio) / f"{nombre_base}_Distribucion.geojson",
        "estado": Path(directorio) / f"{nombre_base}_EstadoCartografia.csv",
    }
    _reemplazar_atomico(
        rutas["csv"], lambda out: df_coord.to_csv(out, sep=";", index=False)
    )
    _reemplazar_atomico(
        rutas["estado"], lambda out: df_estado.to_csv(out, sep=";", index=False)
    )
    # GeoJSON sin BOM para máxima compatibilidad con lectores JSON.
    fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(geojson, out, ensure_ascii=False)
        os.replace(tmp, rutas["geojson"])
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return rutas


def generar_mapa(e_id, nombre, df_coord, geojson, ruta):
    """Genera HTML local con Folium/Leaflet, sin subir datos a un servidor."""
    import folium

    e_id = extraer_id(e_id)
    puntos = df_coord[df_coord["taxonId"].astype(str) == e_id]
    if puntos.empty:
        raise ValueError("Este taxón no tiene coordenadas disponibles.")
    features = [
        f for f in geojson.get("features", [])
        if str(f["properties"]["taxonId"]) == e_id
    ]
    mapa = folium.Map(
        location=[float(puntos.latdecimal.mean()), float(puntos.longdecimal.mean())],
        zoom_start=6,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Esri, HERE, Garmin, USGS, NGA, EPA, NPS",
        control_scale=True,
        prefer_canvas=True,
    )
    titulo = escape(nombre or f"Taxón {e_id}")
    mapa.get_root().header.add_child(folium.Element(
        f"<title>Distribución EIDOS: {titulo}</title>"
    ))
    mapa.get_root().html.add_child(folium.Element(
        '<aside style="position:fixed;top:12px;left:56px;right:56px;z-index:999;'
        'background:white;padding:12px 16px;border:1px solid #bbb;'
        'font:14px sans-serif;max-width:520px">'
        f"<strong>{titulo}</strong> · EIDOS {e_id}<br>"
        f"{len(puntos)} cuadrículas. Los puntos son centros, no observaciones.<br>"
        '<a href="https://iepnb.gob.es/geoserver/especies/wfs" target="_blank" '
        'rel="noopener">Distribución: IEPNB / EIDOS (WFS)</a>'
        "</aside>"
    ))
    if features:
        capa = folium.GeoJson(
            {"type": "FeatureCollection", "features": features},
            name="Cuadrículas de distribución",
            style_function=lambda _: {
                "color": "#217346", "weight": 2, "fillOpacity": 0.22,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["taxonId", "utm"], aliases=["Taxón", "Cuadrícula"],
            ),
        ).add_to(mapa)
        mapa.fit_bounds(capa.get_bounds(), padding=(40, 40))
    centros = folium.FeatureGroup(name="Centros de cuadrículas", show=False)
    for fila in puntos.itertuples(index=False):
        folium.CircleMarker(
            [float(fila.latdecimal), float(fila.longdecimal)], radius=4,
            color="#174e31", fill=True,
            tooltip=f"Cuadrícula {escape(str(fila.utm))}",
        ).add_to(centros)
    centros.add_to(mapa)
    if not features:
        mapa.fit_bounds([
            [float(puntos.latdecimal.min()), float(puntos.longdecimal.min())],
            [float(puntos.latdecimal.max()), float(puntos.longdecimal.max())],
        ], max_zoom=12)
    folium.LayerControl().add_to(mapa)
    mapa.save(str(ruta))
    return Path(ruta)


def abrir_mapa(ruta, titulo):
    """Webview nativa en otro proceso; si no está instalada, navegador."""
    import importlib.util

    ruta = Path(ruta).resolve()
    if importlib.util.find_spec("webview") is not None:
        subprocess.Popen([
            sys.executable, str(Path(__file__).resolve()),
            str(ruta), titulo,
        ])
        return "ventana"
    webbrowser.open(ruta.as_uri(), new=1)
    return "navegador"


if __name__ == "__main__":
    # pywebview necesita su propio hilo principal, separado del bucle de Tk.
    ruta = Path(sys.argv[1]).resolve()
    try:
        import webview
        webview.create_window(sys.argv[2], ruta.as_uri(), width=1100, height=760)
        webview.start()
    except Exception:
        webbrowser.open(ruta.as_uri(), new=1)
