"""Aplicación Tkinter para explorar GBIF.es con filtros completos (Geo + ejes B, C, D, E),
wrap inteligente, colores diferenciados (negro, verde oscuro, azul oscuro),
árbol sumatorio IN -> CO -> DR -> STATS y ventana secundaria interactiva de evolución
anual (publicación de datasets, descargas, registros bajados y citas científicas)
con ventana de ayuda integrada («Help»).

Usa únicamente la librería estándar de Python (`tkinter`, `urllib.request`, `json`, `threading`, `csv`).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import queue
import re
import textwrap
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_SEARCH_URL = "https://registros-ws.gbif.es/occurrences/search"
BASE_FIELDS_URL = "https://registros-ws.gbif.es/index/fields"
COLLECTORY_DR_URL = "https://colecciones.gbif.es/ws/dataResource/{uid}"
GBIF_GLOBAL_DATASET_URL = "https://api.gbif.org/v1/dataset/{uuid}"
GBIF_GLOBAL_DOWNLOAD_DATASET_URL = (
    "https://api.gbif.org/v1/occurrence/download/dataset/{uuid}"
)
GBIF_GLOBAL_DOWNLOAD_DETAIL_URL = (
    "https://api.gbif.org/v1/occurrence/download/{download_key}"
)
GBIF_GLOBAL_LITERATURE_URL = "https://api.gbif.org/v1/literature/search"

DEFAULT_USER_AGENT = "gbif-es-full-catalog-explorer/7.5"

PRESET_QUERIES: dict[str, str] = {
    "Plants (Reino Plantae)": "kingdom:Plantae",
    "Animals (Reino Animalia)": "kingdom:Animalia",
    "Fungi (Reino Fungi)": "kingdom:Fungi",
    "Bacteria (Reino Bacteria)": "kingdom:Bacteria",
    "Chromista (Reino Chromista)": "kingdom:Chromista",
    "Protozoa (Reino Protozoa)": "kingdom:Protozoa",
    "Grupo: Plants (species_group)": "species_group:Plants",
    "Grupo: Animals (species_group)": "species_group:Animals",
    "Grupo: Birds (Aves)": "species_group:Birds",
    "Grupo: Insects (Insecta)": "species_group:Insects",
    "Todos los registros (*:*)": "*:*",
}

ALL_OPTION = "(Todos)"

CHARTS_HELP_TEXT = """CARACTERÍSTICAS Y LIMITACIONES DE LAS GRÁFICAS ANUALES
========================================================

1. ÁMBITO DINÁMICO Y SINCRONIZACIÓN CON EL ÁRBOL
------------------------------------------------
- Por defecto, al abrir la ventana se muestra el ámbito «Total Global» correspondiente a todos los conjuntos de datos (DR) recuperados en la consulta actual del árbol.
- Al seleccionar o hacer clic en una fila de Institución (IN), Colección (CO) o Recurso/Dataset (DR) en la ventana principal, las 4 gráficas, la tabla numérica y la exportación CSV se actualizan automáticamente al subconjunto de DR de esa entidad.
- El botón «Volver a Total Global» restaura la vista agregada completa de la consulta activa.
- El botón «Exportar serie anual CSV» guarda la tabla anual del ámbito visualizado actualmente (separador «;», codificación UTF-8 con BOM).

2. DESCRIPCIÓN DE LAS 4 GRÁFICAS
--------------------------------
- Gráfico 1 — Datasets publicados por año:
  * Barras verdes: número de datasets (DR) cuyo año de publicación/alta se ha detectado en ese año.
  * Línea negra con marcadores: acumulado progresivo de datasets publicados a lo largo de la serie.
- Gráfico 2 — Consultas / descargas realizadas por año:
  * Barras azul oscuro: número de eventos de descarga de GBIF.org asociados a los DR del ámbito cuyo año de creación se ha resuelto en ese año.
- Gráfico 3 — Registros bajados en descargas por año:
  * Barras azul medio: suma de registros descargados (numberRecords / totalRecords) en las descargas asignadas a cada año.
- Gráfico 4 — Citas científicas publicadas por año:
  * Barras moradas: número de publicaciones científicas indexadas en GBIF Literature vinculadas al gbifDatasetKey del DR, agrupadas por año de publicación.

3. TABLA INFERIOR DE DETALLE Y FILA TOTAL
-----------------------------------------
- Muestra los años en orden descendente (más reciente arriba) dentro del rango continuo entre el primer año y el último año con datos en cualquiera de las series.
- La última fila («TOTAL») muestra la sumatoria de «Datasets publicados», «Descargas (consultas)», «Registros bajados» y «Citas científicas», junto con el acumulado final de datasets.

4. LIMITACIONES IMPORTANTES Y POSIBLES DISCREPANCIAS
----------------------------------------------------
- Origen cruzado de datos: El árbol de registros proviene de GBIF.es (registros-ws.gbif.es / colecciones.gbif.es), mientras que descargas y citas provienen de la API global de GBIF.org. Si un DR no tiene «gbifRegistryKey» o no está indexado en GBIF.org, sus métricas de descarga y citas aparecerán en 0.
- Filtros del árbol vs. métricas históricas de GBIF.org: Los totales de descargas y citas de un DR en GBIF.org corresponden al conjunto de datos en GBIF.org y no se filtran individualmente por los filtros Solr (continente, año, incertidumbre, etc.) aplicados en la consulta de ocurrencias de GBIF.es.
- Doble cómputo entre entidades y entre datasets:
  * Si una misma descarga incluye varios datasets (DR) del mismo ámbito, cada DR contabiliza su participación/registros según devuelve el endpoint de descarga por dataset, por lo que sumar varios DR o varias instituciones no equivale a descargas únicas globales sin deduplicar.
  * Un mismo artículo científico puede citar más de un dataset; al sumar citas entre distintos DR o IN puede existir solapamiento entre entidades.
- Fechas de descarga y años sin asignar:
  * La resolución del año de descarga depende de los campos de fecha devueltos por GBIF.org o del detalle de la descarga (/v1/occurrence/download/{key}). Si una descarga carece de fecha válida o no puede resolverse, no se le asigna año artificial y puede no figurar en el desglose anual aunque sume en el total histórico.
  * Solo se consideran años en el rango 1990–2026 para descartar fechas erróneas o valores atípicos.
- Dibujo nativo en tk.Canvas y legibilidad:
  * Las gráficas se dibujan directamente sobre un lienzo tk.Canvas sin Matplotlib. Al haber muchos años o valores muy dispares (por ejemplo, un año con millones de registros frente a años con pocos), las barras pequeñas pueden verse bajas y algunas etiquetas numéricas superiores se omiten automáticamente para evitar solapamientos.
  * Si se redimensiona la ventana o se cambia de ámbito mientras la consulta principal sigue descargando datos, los valores se recalculan al completarse el lote.
"""


@dataclass
class InstitutionRow:
  uid: str
  label: str
  records: int


@dataclass
class CollectionRow:
  uid: str
  institution_uid: str
  label: str
  records: int


@dataclass
class DatasetRow:
  uid: str
  institution_uid: str
  collection_uid: str | None
  label: str
  records: int


@dataclass
class DatasetStatsRow:
  dataset_uid: str
  gbif_uuid: str
  pub_year: int | None
  downloads: int
  downloaded_records: int
  citations: int
  status: str
  downloads_by_year: dict[int, int] = field(default_factory=dict)
  downloaded_records_by_year: dict[int, int] = field(default_factory=dict)
  citations_by_year: dict[int, int] = field(default_factory=dict)


@dataclass
class FacetChoice:
  display: str
  raw_value: str
  fq: str
  count: int


def _extract_year(value: Any) -> int | None:
  """Extrae un año válido (1990..2026) desde fecha ISO, texto o timestamp epoch."""
  if value is None:
    return None

  if isinstance(value, (int, float)):
    if value > 1e11:
      yr = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).year
      return yr if 1990 <= yr <= 2026 else None
    if value > 1e8:
      yr = datetime.fromtimestamp(value, tz=timezone.utc).year
      return yr if 1990 <= yr <= 2026 else None
    yr_int = int(value)
    return yr_int if 1990 <= yr_int <= 2026 else None

  text = str(value).strip()
  if not text:
    return None

  if text.isdigit():
    num = int(text)
    if num > 1e11:
      yr = datetime.fromtimestamp(num / 1000.0, tz=timezone.utc).year
      return yr if 1990 <= yr <= 2026 else None
    if num > 1e8:
      yr = datetime.fromtimestamp(num, tz=timezone.utc).year
      return yr if 1990 <= yr <= 2026 else None
    return num if 1990 <= num <= 2026 else None

  match = re.search(r"\b(199\d|20[0-2]\d)\b", text)
  if match:
    yr = int(match.group(1))
    return yr if yr <= 2026 else None
  return None


def fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: float = 25.0,
) -> tuple[Any, str]:
  """Realiza una petición HTTP GET y devuelve (datos_json, estado)."""
  target_url = f"{url}?{urlencode(params, doseq=True)}" if params else url
  req = Request(
      target_url,
      headers={
          "Accept": "application/json",
          "User-Agent": DEFAULT_USER_AGENT,
      },
  )
  try:
    with urlopen(req, timeout=timeout) as response:
      raw = response.read().decode("utf-8", errors="replace")
      parsed = json.loads(raw) if raw else {}
      return parsed, f"HTTP {response.status}"
  except HTTPError as exc:
    return None, f"HTTP {exc.code}"
  except URLError as exc:
    return None, f"URL_ERROR: {exc.reason}"
  except TimeoutError:
    return None, "TIMEOUT"
  except json.JSONDecodeError as exc:
    return None, f"JSON_ERROR: {exc.msg}"


def _resolve_download_year(
    entry: dict[str, Any],
    dl_year_cache: dict[str, int | None],
    resolve_remote_detail: bool = True,
) -> int | None:
  """Obtiene el año real de creación de la descarga usando caché por downloadKey."""
  dl_obj = (
      entry.get("download")
      if isinstance(entry.get("download"), dict)
      else {}
  )

  for candidate in (
      entry.get("created"),
      dl_obj.get("created"),
  ):
    yr = _extract_year(candidate)
    if yr is not None:
      return yr

  dl_key = str(
      entry.get("downloadKey") or dl_obj.get("key") or entry.get("key") or ""
  ).strip()
  if not dl_key:
    return None

  if dl_key in dl_year_cache:
    return dl_year_cache[dl_key]

  if not resolve_remote_detail:
    return None

  detail, status = fetch_json(
      GBIF_GLOBAL_DOWNLOAD_DETAIL_URL.format(download_key=dl_key),
      timeout=12.0,
  )
  resolved_year: int | None = None
  if status == "HTTP 200" and isinstance(detail, dict):
    resolved_year = _extract_year(detail.get("created"))

  dl_year_cache[dl_key] = resolved_year
  return resolved_year


def fetch_dataset_download_and_citation_stats(
    uid: str,
    dl_year_cache: dict[str, int | None],
    resolve_download_years: bool = True,
) -> DatasetStatsRow:
  """Cruza el dr... de colecciones.gbif.es con api.gbif.org y extrae totales y series por año."""
  dr_meta, meta_status = fetch_json(
      COLLECTORY_DR_URL.format(uid=uid), timeout=15.0
  )
  if not isinstance(dr_meta, dict):
    return DatasetStatsRow(
        dataset_uid=uid,
        gbif_uuid="",
        pub_year=None,
        downloads=0,
        downloaded_records=0,
        citations=0,
        status=f"Collectory {meta_status}",
    )

  pub_year = (
      _extract_year(dr_meta.get("pubDate"))
      or _extract_year(dr_meta.get("dateCreated"))
      or _extract_year(dr_meta.get("created"))
  )

  gbif_uuid = str(dr_meta.get("gbifRegistryKey") or "").strip()
  if not gbif_uuid:
    return DatasetStatsRow(
        dataset_uid=uid,
        gbif_uuid="",
        pub_year=pub_year,
        downloads=0,
        downloaded_records=0,
        citations=0,
        status="Sin gbifRegistryKey",
    )

  if pub_year is None:
    ds_global, _ = fetch_json(
        GBIF_GLOBAL_DATASET_URL.format(uuid=gbif_uuid), timeout=12.0
    )
    if isinstance(ds_global, dict):
      pub_year = _extract_year(ds_global.get("pubDate")) or _extract_year(
          ds_global.get("created")
      )

  total_downloads = 0
  total_downloaded_records = 0
  downloads_by_year: dict[int, int] = {}
  downloaded_records_by_year: dict[int, int] = {}
  offset = 0
  limit = 300

  while True:
    dl_payload, dl_status = fetch_json(
        GBIF_GLOBAL_DOWNLOAD_DATASET_URL.format(uuid=gbif_uuid),
        params={"limit": limit, "offset": offset},
        timeout=20.0,
    )
    if not isinstance(dl_payload, dict):
      if offset == 0:
        return DatasetStatsRow(
            dataset_uid=uid,
            gbif_uuid=gbif_uuid,
            pub_year=pub_year,
            downloads=0,
            downloaded_records=0,
            citations=0,
            status=f"GBIF.org {dl_status}",
        )
      break

    if offset == 0:
      total_downloads = int(dl_payload.get("count", 0) or 0)

    results = dl_payload.get("results", [])
    if not isinstance(results, list) or not results:
      break

    for entry in results:
      if not isinstance(entry, dict):
        continue
      dl_obj = (
          entry.get("download")
          if isinstance(entry.get("download"), dict)
          else {}
      )
      rec_in_dl = entry.get("numberRecords")
      if rec_in_dl is None:
        rec_in_dl = dl_obj.get("totalRecords", 0)
      rec_count = int(rec_in_dl or 0)
      total_downloaded_records += rec_count

      ev_year = _resolve_download_year(
          entry=entry,
          dl_year_cache=dl_year_cache,
          resolve_remote_detail=resolve_download_years,
      )
      if ev_year is not None:
        downloads_by_year[ev_year] = downloads_by_year.get(ev_year, 0) + 1
        downloaded_records_by_year[ev_year] = (
            downloaded_records_by_year.get(ev_year, 0) + rec_count
        )

    if dl_payload.get("endOfRecords", True) or len(results) < limit:
      break
    offset += limit

  total_citations = 0
  citations_by_year: dict[int, int] = {}
  lit_payload, _ = fetch_json(
      GBIF_GLOBAL_LITERATURE_URL,
      params={
          "gbifDatasetKey": gbif_uuid,
          "facet": "year",
          "facetLimit": 200,
          "limit": 0,
      },
      timeout=15.0,
  )
  if isinstance(lit_payload, dict):
    total_citations = int(lit_payload.get("count", 0) or 0)
    for facet_block in lit_payload.get("facets", []):
      if isinstance(facet_block, dict) and str(
          facet_block.get("field", "")
      ).upper() == "YEAR":
        for count_item in facet_block.get("counts", []):
          if isinstance(count_item, dict):
            yr = _extract_year(count_item.get("name"))
            cnt = int(count_item.get("count", 0) or 0)
            if yr is not None and cnt > 0:
              citations_by_year[yr] = citations_by_year.get(yr, 0) + cnt

  return DatasetStatsRow(
      dataset_uid=uid,
      gbif_uuid=gbif_uuid,
      pub_year=pub_year,
      downloads=total_downloads,
      downloaded_records=total_downloaded_records,
      citations=total_citations,
      status="OK (GBIF.org)",
      downloads_by_year=downloads_by_year,
      downloaded_records_by_year=downloaded_records_by_year,
      citations_by_year=citations_by_year,
  )


def extract_uid(facet_item: dict[str, Any]) -> str:
  """Extrae el identificador limpio (in..., co..., dr...) de un elemento de faceta."""
  fq = str(facet_item.get("fq", ""))
  if ":" in fq:
    return fq.split(":", 1)[1].strip().strip('"').strip("'")
  return str(facet_item.get("label", "")).strip()


def get_facet_items(payload: Any, field_name: str) -> list[dict[str, Any]]:
  """Recupera la lista fieldResult para una faceta concreta."""
  if not isinstance(payload, dict):
    return []
  for facet in payload.get("facetResults", []):
    if facet.get("fieldName") == field_name:
      items = facet.get("fieldResult", [])
      if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
  return []


def parse_facet_choices(
    payload: Any, field_name: str
) -> dict[str, FacetChoice]:
  """Convierte los items de una faceta en un diccionario {texto_mostrado: FacetChoice}."""
  choices: dict[str, FacetChoice] = {}
  for item in get_facet_items(payload, field_name):
    label = str(item.get("label") or "").strip()
    fq = str(item.get("fq") or "").strip()
    count = int(item.get("count", 0) or 0)
    if not label and not fq:
      continue
    raw_val = fq.split(":", 1)[1].strip().strip('"') if ":" in fq else label
    if not fq and raw_val:
      fq = f'{field_name}:"{raw_val}"'
    display = f"{label or raw_val} ({count:,})"
    choices[display] = FacetChoice(
        display=display,
        raw_value=raw_val,
        fq=fq,
        count=count,
    )
  return choices


def build_solr_range_fq(
    field_name: str,
    lower_raw: str,
    upper_raw: str,
    label_es: str,
    is_int: bool = True,
) -> str | None:
  """Construye un filtro de rango Solr `campo:[inf TO sup]` validando los límites."""
  low = lower_raw.strip()
  high = upper_raw.strip()
  if not low and not high:
    return None

  parser = int if is_int else float
  low_val: int | float | None = None
  high_val: int | float | None = None

  if low:
    try:
      low_val = parser(low)
    except ValueError as exc:
      raise ValueError(
          f"El valor inferior de «{label_es}» debe ser numérico ({low!r})."
      ) from exc

  if high:
    try:
      high_val = parser(high)
    except ValueError as exc:
      raise ValueError(
          f"El valor superior de «{label_es}» debe ser numérico ({high!r})."
      ) from exc

  if low_val is not None and high_val is not None and low_val > high_val:
    raise ValueError(
        f"En «{label_es}», el límite inferior ({low_val}) no puede ser mayor que el superior ({high_val})."
    )

  low_token = str(low_val) if low_val is not None else "*"
  high_token = str(high_val) if high_val is not None else "*"
  return f"{field_name}:[{low_token} TO {high_token}]"


class ChartsHelpWindow(tk.Toplevel):
  """Ventana de ayuda con características y limitaciones de las gráficas anuales."""

  def __init__(self, master: tk.Misc) -> None:
    super().__init__(master)
    self.title("Ayuda — Características y limitaciones de las gráficas")
    self.geometry("760x580")
    self.minsize(560, 380)

    container = ttk.Frame(self, padding=12)
    container.pack(fill=tk.BOTH, expand=True)

    header = ttk.Label(
        container,
        text="Guía de interpretación y limitaciones de las gráficas anuales",
        font=("Segoe UI", 11, "bold"),
        foreground="#1B4F72",
    )
    header.pack(anchor=tk.W, pady=(0, 8))

    text_frame = ttk.Frame(container)
    text_frame.pack(fill=tk.BOTH, expand=True)

    txt = tk.Text(
        text_frame,
        wrap=tk.WORD,
        font=("Segoe UI", 9),
        bg="#FFFFFF",
        fg="#222222",
        padx=10,
        pady=8,
        relief=tk.SOLID,
        borderwidth=1,
    )
    txt.insert(tk.END, CHARTS_HELP_TEXT.strip())
    txt.configure(state=tk.DISABLED)

    sb = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)

    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    btn_bar = ttk.Frame(container)
    btn_bar.pack(fill=tk.X, pady=(10, 0))
    ttk.Button(btn_bar, text="Cerrar", command=self.destroy).pack(side=tk.RIGHT)


class TemporalChartsWindow(tk.Toplevel):
  """Ventana independiente de gráficas anuales (Total global o entidad IN / CO / DR seleccionada)."""

  def __init__(self, master: GbifEsFullCatalogExplorerApp) -> None:
    super().__init__(master)
    self.app = master
    self.title("Evolución Anual — Publicación de Datasets y Consultas/Descargas")
    self.geometry("1240x820")
    self.minsize(980, 660)

    self._current_scope_label = "Total Global (todas las instituciones)"
    self._current_dr_uids: set[str] = set()
    self._yearly_rows: list[dict[str, int]] = []
    self._help_window: ChartsHelpWindow | None = None

    self._build_ui()
    self.show_total_global()

  def _build_ui(self) -> None:
    top_bar = ttk.Frame(self, padding=(10, 8, 10, 4))
    top_bar.pack(fill=tk.X)

    self.scope_var = tk.StringVar(
        value="Ámbito visualizado: Total Global (todas las instituciones)"
    )
    ttk.Label(
        top_bar,
        textvariable=self.scope_var,
        font=("Segoe UI", 10, "bold"),
        foreground="#1B4F72",
    ).pack(side=tk.LEFT)

    ttk.Button(
        top_bar,
        text="Help",
        command=self._open_help_window,
    ).pack(side=tk.RIGHT, padx=(6, 0))

    ttk.Button(
        top_bar,
        text="Exportar serie anual CSV",
        command=self._export_yearly_csv,
    ).pack(side=tk.RIGHT, padx=(6, 0))

    ttk.Button(
        top_bar,
        text="Volver a Total Global",
        command=self.show_total_global,
    ).pack(side=tk.RIGHT)

    hint_lbl = ttk.Label(
        self,
        text=(
            "Haz clic en cualquier fila (IN, CO o DR) de la ventana principal para ver su evolución anual. "
            "La tabla inferior muestra cada año y la fila TOTAL al final con la sumatoria."
        ),
        foreground="#444444",
        padding=(10, 0, 10, 4),
    )
    hint_lbl.pack(anchor=tk.W)

    charts_grid = ttk.Frame(self, padding=(10, 2, 10, 4))
    charts_grid.pack(fill=tk.BOTH, expand=True)
    charts_grid.rowconfigure(0, weight=1)
    charts_grid.rowconfigure(1, weight=1)
    charts_grid.columnconfigure(0, weight=1)
    charts_grid.columnconfigure(1, weight=1)

    self.canvas_pub = self._create_chart_card(
        charts_grid,
        row=0,
        col=0,
        title="1. Datasets publicados por año (fecha de alta/publicación)",
    )
    self.canvas_dl = self._create_chart_card(
        charts_grid,
        row=0,
        col=1,
        title="2. Consultas / descargas realizadas por año",
    )
    self.canvas_rec = self._create_chart_card(
        charts_grid,
        row=1,
        col=0,
        title="3. Registros bajados en descargas por año",
    )
    self.canvas_cit = self._create_chart_card(
        charts_grid,
        row=1,
        col=1,
        title="4. Citas científicas publicadas por año",
    )

    table_frame = ttk.LabelFrame(
        self, text="Detalle numérico por año y sumatoria total", padding=(8, 4)
    )
    table_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

    cols = ("year", "pub_ds", "cum_ds", "downloads", "dl_records", "citations")
    self.year_tree = ttk.Treeview(
        table_frame, columns=cols, show="headings", height=7
    )
    self.year_tree.heading("year", text="Año", anchor=tk.CENTER)
    self.year_tree.heading("pub_ds", text="Datasets publicados", anchor=tk.E)
    self.year_tree.heading("cum_ds", text="Datasets acumulados", anchor=tk.E)
    self.year_tree.heading("downloads", text="Descargas (consultas)", anchor=tk.E)
    self.year_tree.heading("dl_records", text="Registros bajados", anchor=tk.E)
    self.year_tree.heading("citations", text="Citas científicas", anchor=tk.E)

    self.year_tree.tag_configure(
        "total_row", font=("Segoe UI", 9, "bold"), background="#EEF2F5"
    )

    for col_name, width in (
        ("year", 95),
        ("pub_ds", 150),
        ("cum_ds", 160),
        ("downloads", 170),
        ("dl_records", 180),
        ("citations", 150),
    ):
      self.year_tree.column(
          col_name,
          width=width,
          anchor=tk.CENTER if col_name == "year" else tk.E,
      )

    ysb = ttk.Scrollbar(
        table_frame, orient=tk.VERTICAL, command=self.year_tree.yview
    )
    self.year_tree.configure(yscrollcommand=ysb.set)
    self.year_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
    ysb.pack(side=tk.RIGHT, fill=tk.Y)

    self.bind("<Configure>", lambda _: self._redraw_all_charts())

  def _open_help_window(self) -> None:
    if self._help_window is not None and self._help_window.winfo_exists():
      self._help_window.lift()
      self._help_window.focus_force()
    else:
      self._help_window = ChartsHelpWindow(self)

  def _create_chart_card(
      self, parent: ttk.Frame, row: int, col: int, title: str
  ) -> tk.Canvas:
    card = ttk.LabelFrame(parent, text=title, padding=(6, 4))
    card.grid(row=row, column=col, sticky="nsew", padx=5, pady=4)
    canvas = tk.Canvas(card, bg="#FFFFFF", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    return canvas

  def show_total_global(self) -> None:
    data = self.app._current_data
    if not data:
      return
    all_uids = {ds.uid for ds in data["datasets"]}
    self.update_scope(
        scope_label=(
            f"Total Global — {len(data['institutions'])} IN / "
            f"{len(data['collections'])} CO / {len(all_uids)} DR"
        ),
        dr_uids=all_uids,
    )

  def update_scope(self, scope_label: str, dr_uids: set[str]) -> None:
    self._current_scope_label = scope_label
    self._current_dr_uids = set(dr_uids)
    self.scope_var.set(f"Ámbito visualizado: {scope_label}")
    self._recompute_series()
    self._redraw_all_charts()

  def _recompute_series(self) -> None:
    data = self.app._current_data
    if not data:
      self._yearly_rows = []
      return

    stats_by_uid: dict[str, DatasetStatsRow] = data["stats_by_uid"]
    pub_by_year: dict[int, int] = {}
    dl_by_year: dict[int, int] = {}
    rec_by_year: dict[int, int] = {}
    cit_by_year: dict[int, int] = {}

    for uid in self._current_dr_uids:
      st = stats_by_uid.get(uid)
      if not st:
        continue
      if st.pub_year is not None:
        pub_by_year[st.pub_year] = pub_by_year.get(st.pub_year, 0) + 1
      for yr, cnt in st.downloads_by_year.items():
        dl_by_year[yr] = dl_by_year.get(yr, 0) + cnt
      for yr, cnt in st.downloaded_records_by_year.items():
        rec_by_year[yr] = rec_by_year.get(yr, 0) + cnt
      for yr, cnt in st.citations_by_year.items():
        cit_by_year[yr] = cit_by_year.get(yr, 0) + cnt

    all_years = sorted(
        set(pub_by_year) | set(dl_by_year) | set(rec_by_year) | set(cit_by_year)
    )
    year_span = (
        list(range(min(all_years), max(all_years) + 1)) if all_years else []
    )

    rows: list[dict[str, int]] = []
    cum_ds = 0
    sum_pub = 0
    sum_dl = 0
    sum_rec = 0
    sum_cit = 0

    for yr in year_span:
      p_cnt = pub_by_year.get(yr, 0)
      d_cnt = dl_by_year.get(yr, 0)
      r_cnt = rec_by_year.get(yr, 0)
      c_cnt = cit_by_year.get(yr, 0)

      cum_ds += p_cnt
      sum_pub += p_cnt
      sum_dl += d_cnt
      sum_rec += r_cnt
      sum_cit += c_cnt

      rows.append(
          {
              "year": yr,
              "pub_ds": p_cnt,
              "cum_ds": cum_ds,
              "downloads": d_cnt,
              "dl_records": r_cnt,
              "citations": c_cnt,
          }
      )

    self._yearly_rows = rows
    self.year_tree.delete(*self.year_tree.get_children())

    for r in reversed(rows):
      self.year_tree.insert(
          "",
          tk.END,
          values=(
              r["year"],
              f"{r['pub_ds']:,}",
              f"{r['cum_ds']:,}",
              f"{r['downloads']:,}",
              f"{r['dl_records']:,}",
              f"{r['citations']:,}",
          ),
      )

    if rows:
      self.year_tree.insert(
          "",
          tk.END,
          values=(
              "TOTAL",
              f"{sum_pub:,}",
              f"{cum_ds:,}",
              f"{sum_dl:,}",
              f"{sum_rec:,}",
              f"{sum_cit:,}",
          ),
          tags=("total_row",),
      )

  def _redraw_all_charts(self) -> None:
    self._draw_bar_chart(
        self.canvas_pub,
        key="pub_ds",
        line_key="cum_ds",
        bar_color="#145A32",
        line_color="#111111",
        legend_text="Barras: Nuevos/año | Línea: Acumulado",
    )
    self._draw_bar_chart(
        self.canvas_dl,
        key="downloads",
        line_key=None,
        bar_color="#1B4F72",
        line_color=None,
        legend_text="Eventos de descarga / año",
    )
    self._draw_bar_chart(
        self.canvas_rec,
        key="dl_records",
        line_key=None,
        bar_color="#2874A6",
        line_color=None,
        legend_text="Registros descargados / año",
    )
    self._draw_bar_chart(
        self.canvas_cit,
        key="citations",
        line_key=None,
        bar_color="#7D3C98",
        line_color=None,
        legend_text="Artículos científicos / año",
    )

  def _draw_bar_chart(
      self,
      canvas: tk.Canvas,
      key: str,
      line_key: str | None,
      bar_color: str,
      line_color: str | None,
      legend_text: str,
  ) -> None:
    canvas.delete("all")
    w = max(canvas.winfo_width(), 320)
    h = max(canvas.winfo_height(), 180)

    if not self._yearly_rows:
      canvas.create_text(
          w // 2,
          h // 2,
          text="Sin datos temporales para esta selección",
          fill="#666666",
          font=("Segoe UI", 9, "italic"),
      )
      return

    pad_left = 72
    pad_right = 20
    pad_top = 34
    pad_bottom = 32
    plot_w = max(w - pad_left - pad_right, 80)
    plot_h = max(h - pad_top - pad_bottom, 60)

    values = [r[key] for r in self._yearly_rows]
    line_values = [r[line_key] for r in self._yearly_rows] if line_key else []
    max_val = max([*values, *line_values, 1])

    canvas.create_text(
        w - pad_right,
        10,
        text=legend_text,
        anchor=tk.E,
        fill="#444444",
        font=("Segoe UI", 8),
    )

    for step in range(5):
      frac = step / 4.0
      y = pad_top + plot_h - frac * plot_h
      val_tick = int(round(max_val * frac))
      canvas.create_line(pad_left, y, w - pad_right, y, fill="#ECEFF1")
      canvas.create_text(
          pad_left - 6,
          y,
          text=f"{val_tick:,}",
          anchor=tk.E,
          fill="#555555",
          font=("Segoe UI", 8),
      )

    canvas.create_line(
        pad_left, pad_top, pad_left, pad_top + plot_h, fill="#90A4AE"
    )
    canvas.create_line(
        pad_left,
        pad_top + plot_h,
        w - pad_right,
        pad_top + plot_h,
        fill="#90A4AE",
    )

    n = len(self._yearly_rows)
    slot_w = plot_w / max(n, 1)
    bar_w = max(min(slot_w * 0.65, 28), 3)
    label_every = max(1, n // 10)
    val_label_every = max(1, (n + 9) // 10)

    line_points: list[tuple[float, float]] = []

    for idx, row in enumerate(self._yearly_rows):
      cx = pad_left + (idx + 0.5) * slot_w
      val = row[key]
      bar_h = (val / max_val) * plot_h
      y0 = pad_top + plot_h - bar_h
      y1 = pad_top + plot_h

      if val > 0:
        canvas.create_rectangle(
            cx - bar_w / 2,
            y0,
            cx + bar_w / 2,
            y1,
            fill=bar_color,
            outline="",
        )
        if slot_w >= 26 and (idx % val_label_every == 0 or idx == n - 1):
          canvas.create_text(
              cx,
              max(y0 - 7, pad_top - 8),
              text=f"{val:,}",
              fill="#222222",
              font=("Segoe UI", 7),
          )

      if line_key is not None:
        l_val = row[line_key]
        ly = pad_top + plot_h - (l_val / max_val) * plot_h
        line_points.append((cx, ly))

      if idx % label_every == 0 or idx == n - 1:
        canvas.create_text(
            cx,
            pad_top + plot_h + 13,
            text=str(row["year"]),
            fill="#333333",
            font=("Segoe UI", 8),
        )

    if len(line_points) >= 2 and line_color:
      flat_coords = [coord for pt in line_points for coord in pt]
      canvas.create_line(*flat_coords, fill=line_color, width=2)
      for cx, ly in line_points:
        canvas.create_oval(
            cx - 2.5, ly - 2.5, cx + 2.5, ly + 2.5, fill=line_color, outline=""
        )

  def _export_yearly_csv(self) -> None:
    if not self._yearly_rows:
      return
    filepath = filedialog.asksaveasfilename(
        parent=self,
        title="Guardar evolución anual en CSV",
        defaultextension=".csv",
        filetypes=[("Archivo CSV", "*.csv")],
        initialfile="gbif_es_evolucion_anual.csv",
    )
    if not filepath:
      return

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
      writer = csv.writer(f, delimiter=";")
      writer.writerow(
          [
              "ambito",
              "year",
              "datasets_publicados",
              "datasets_acumulados",
              "descargas_realizadas",
              "registros_bajados",
              "citas_cientificas",
          ]
      )
      for r in self._yearly_rows:
        writer.writerow(
            [
                self._current_scope_label,
                r["year"],
                r["pub_ds"],
                r["cum_ds"],
                r["downloads"],
                r["dl_records"],
                r["citations"],
            ]
        )
    messagebox.showinfo(
        "Exportación completada",
        f"Serie anual guardada en:\n{filepath}",
        parent=self,
    )


class GbifEsFullCatalogExplorerApp(tk.Tk):
  """Interfaz Tkinter principal con árbol IN/CO/DR y enlace a la ventana de gráficas anuales."""

  def __init__(self) -> None:
    super().__init__()
    self.title(
        "Explorador GBIF.es — Catálogo Completo (Geo + B, C, D, E + Años) y Árbol IN → CO → DR"
    )
    self.geometry("1440x860")
    self.minsize(1160, 660)

    self._worker_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
    self._cancel_event = threading.Event()
    self._is_running = False
    self._worker_thread: threading.Thread | None = None
    self._current_data: dict[str, Any] | None = None
    self._last_col0_width: int = 410
    self._rewrap_after_id: str | None = None
    self._charts_window: TemporalChartsWindow | None = None
    self._node_scope_map: dict[str, tuple[str, set[str]]] = {}

    self._facet_choices: dict[str, dict[str, FacetChoice]] = {
        "continent": {},
        "country": {},
        "stateProvince": {},
        "county": {},
        "municipality": {},
        "basisOfRecord": {},
        "typeStatus": {},
        "establishmentMeans": {},
        "decade": {},
        "month": {},
        "multimedia": {},
        "license": {},
        "geospatialIssues": {},
        "data_provider_uid": {},
        "institutionCode": {},
        "collectionCode": {},
    }
    self._extra_geo_choices: dict[str, FacetChoice] = {}
    self._extra_geo_fields: dict[str, str] = {}

    self._build_ui()
    self.after(80, self._poll_queue)
    self.after(200, self._load_all_facets_async)

  def _build_ui(self) -> None:
    self.style = ttk.Style(self)
    self._tree_font = tkfont.Font(family="Segoe UI", size=9)
    self.style.configure("Treeview", font=self._tree_font, rowheight=24)

    query_frame = ttk.LabelFrame(
        self, text="1. Grupo taxonómico / Consulta Solr", padding=(10, 5)
    )
    query_frame.pack(fill=tk.X, padx=10, pady=(6, 4))

    ttk.Label(query_frame, text="Grupo:").grid(
        row=0, column=0, sticky=tk.W, padx=(0, 4)
    )
    self.preset_var = tk.StringVar(value="Plants (Reino Plantae)")
    self.preset_combo = ttk.Combobox(
        query_frame,
        textvariable=self.preset_var,
        values=list(PRESET_QUERIES.keys()),
        state="readonly",
        width=26,
    )
    self.preset_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
    self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

    ttk.Label(query_frame, text="Consulta (q=):").grid(
        row=0, column=2, sticky=tk.W, padx=(0, 4)
    )
    self.query_var = tk.StringVar(value=PRESET_QUERIES["Plants (Reino Plantae)"])
    self.query_entry = ttk.Entry(query_frame, textvariable=self.query_var, width=28)
    self.query_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))
    self.query_entry.bind("<Return>", lambda _: self._start_search())

    ttk.Button(
        query_frame,
        text="Actualizar todos los filtros",
        command=self._load_all_facets_async,
    ).grid(row=0, column=4, padx=(0, 10))

    self.fetch_stats_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        query_frame,
        text="Consultar descargas, citas y series anuales (GBIF.org)",
        variable=self.fetch_stats_var,
    ).grid(row=0, column=5, sticky=tk.W, padx=(0, 10))

    self.search_btn = ttk.Button(
        query_frame, text="Consultar árbol", command=self._start_search
    )
    self.search_btn.grid(row=0, column=6, padx=(0, 6))

    self.cancel_btn = ttk.Button(
        query_frame, text="Detener", command=self._cancel_search, state=tk.DISABLED
    )
    self.cancel_btn.grid(row=0, column=7)

    geo_frame = ttk.LabelFrame(
        self,
        text="2. Filtros geográficos (mandatorios AND, dinámicos y en cascada)",
        padding=(10, 5),
    )
    geo_frame.pack(fill=tk.X, padx=10, pady=(0, 4))

    ttk.Label(geo_frame, text="Continente:").grid(
        row=0, column=0, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.continent_var = tk.StringVar(value=ALL_OPTION)
    self.continent_combo = ttk.Combobox(
        geo_frame, textvariable=self.continent_var, state="readonly", width=23
    )
    self.continent_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 10), pady=2)
    self.continent_combo.bind(
        "<<ComboboxSelected>>",
        lambda _: self._load_all_facets_async(cascade_level="continent"),
    )

    ttk.Label(geo_frame, text="País (country):").grid(
        row=0, column=2, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.country_var = tk.StringVar(value=ALL_OPTION)
    self.country_combo = ttk.Combobox(
        geo_frame, textvariable=self.country_var, state="readonly", width=26
    )
    self.country_combo.grid(row=0, column=3, sticky=tk.W, padx=(0, 10), pady=2)
    self.country_combo.bind(
        "<<ComboboxSelected>>",
        lambda _: self._load_all_facets_async(cascade_level="country"),
    )

    ttk.Label(geo_frame, text="Región / Prov. (stateProvince):").grid(
        row=0, column=4, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.state_var = tk.StringVar(value=ALL_OPTION)
    self.state_combo = ttk.Combobox(
        geo_frame, textvariable=self.state_var, state="readonly", width=28
    )
    self.state_combo.grid(row=0, column=5, sticky=tk.W, pady=2)
    self.state_combo.bind(
        "<<ComboboxSelected>>",
        lambda _: self._load_all_facets_async(cascade_level="state"),
    )

    ttk.Label(geo_frame, text="Subregión (county):").grid(
        row=1, column=0, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.county_var = tk.StringVar(value=ALL_OPTION)
    self.county_combo = ttk.Combobox(
        geo_frame, textvariable=self.county_var, state="readonly", width=23
    )
    self.county_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(geo_frame, text="Municipio (municipality):").grid(
        row=1, column=2, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.municipality_var = tk.StringVar(value=ALL_OPTION)
    self.municipality_combo = ttk.Combobox(
        geo_frame, textvariable=self.municipality_var, state="readonly", width=26
    )
    self.municipality_combo.grid(row=1, column=3, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(geo_frame, text="Capa espacial extra:").grid(
        row=1, column=4, sticky=tk.W, padx=(0, 4), pady=2
    )
    extra_box = ttk.Frame(geo_frame)
    extra_box.grid(row=1, column=5, sticky=tk.W, pady=2)

    self.extra_field_var = tk.StringVar(value="(Ninguno)")
    self.extra_field_combo = ttk.Combobox(
        extra_box, textvariable=self.extra_field_var, state="readonly", width=16
    )
    self.extra_field_combo.pack(side=tk.LEFT, padx=(0, 4))
    self.extra_field_combo.bind(
        "<<ComboboxSelected>>", lambda _: self._load_extra_field_values_async()
    )

    self.extra_value_var = tk.StringVar(value=ALL_OPTION)
    self.extra_value_combo = ttk.Combobox(
        extra_box, textvariable=self.extra_value_var, state="readonly", width=16
    )
    self.extra_value_combo.pack(side=tk.LEFT)

    catalog_frame = ttk.LabelFrame(
        self,
        text="3. Catálogo Darwin Core y Calidad (B: Naturaleza, C: Tiempo/Años, D: Calidad/Multimedia, E: Procedencia)",
        padding=(10, 5),
    )
    catalog_frame.pack(fill=tk.X, padx=10, pady=(0, 4))

    ttk.Label(catalog_frame, text="[B] Base registro (basisOfRecord):").grid(
        row=0, column=0, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.basis_var = tk.StringVar(value=ALL_OPTION)
    self.basis_combo = ttk.Combobox(
        catalog_frame, textvariable=self.basis_var, state="readonly", width=24
    )
    self.basis_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(catalog_frame, text="[B] Material tipo (typeStatus):").grid(
        row=0, column=2, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.type_status_var = tk.StringVar(value=ALL_OPTION)
    self.type_status_combo = ttk.Combobox(
        catalog_frame, textvariable=self.type_status_var, state="readonly", width=22
    )
    self.type_status_combo.grid(row=0, column=3, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(catalog_frame, text="[B] Origen (establishmentMeans):").grid(
        row=0, column=4, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.establishment_var = tk.StringVar(value=ALL_OPTION)
    self.establishment_combo = ttk.Combobox(
        catalog_frame,
        textvariable=self.establishment_var,
        state="readonly",
        width=24,
    )
    self.establishment_combo.grid(row=0, column=5, sticky=tk.W, pady=2)

    ttk.Label(catalog_frame, text="[C] Rango de años (year):").grid(
        row=1, column=0, sticky=tk.W, padx=(0, 4), pady=2
    )
    year_range_box = ttk.Frame(catalog_frame)
    year_range_box.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(year_range_box, text="Inf:").pack(side=tk.LEFT, padx=(0, 2))
    self.year_min_var = tk.StringVar()
    ttk.Entry(year_range_box, textvariable=self.year_min_var, width=7).pack(
        side=tk.LEFT, padx=(0, 6)
    )
    ttk.Label(year_range_box, text="Sup:").pack(side=tk.LEFT, padx=(0, 2))
    self.year_max_var = tk.StringVar()
    ttk.Entry(year_range_box, textvariable=self.year_max_var, width=7).pack(
        side=tk.LEFT
    )

    ttk.Label(catalog_frame, text="[C] Década / Mes:").grid(
        row=1, column=2, sticky=tk.W, padx=(0, 4), pady=2
    )
    dec_month_box = ttk.Frame(catalog_frame)
    dec_month_box.grid(row=1, column=3, sticky=tk.W, padx=(0, 10), pady=2)

    self.decade_var = tk.StringVar(value=ALL_OPTION)
    self.decade_combo = ttk.Combobox(
        dec_month_box, textvariable=self.decade_var, state="readonly", width=11
    )
    self.decade_combo.pack(side=tk.LEFT, padx=(0, 4))

    self.month_var = tk.StringVar(value=ALL_OPTION)
    self.month_combo = ttk.Combobox(
        dec_month_box, textvariable=self.month_var, state="readonly", width=10
    )
    self.month_combo.pack(side=tk.LEFT)

    ttk.Label(catalog_frame, text="[C] Colector (recordedBy):").grid(
        row=1, column=4, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.collector_var = tk.StringVar()
    ttk.Entry(catalog_frame, textvariable=self.collector_var, width=26).grid(
        row=1, column=5, sticky=tk.W, pady=2
    )

    ttk.Label(catalog_frame, text="[D] Multimedia / Licencia:").grid(
        row=2, column=0, sticky=tk.W, padx=(0, 4), pady=2
    )
    media_lic_box = ttk.Frame(catalog_frame)
    media_lic_box.grid(row=2, column=1, sticky=tk.W, padx=(0, 10), pady=2)

    self.multimedia_var = tk.StringVar(value=ALL_OPTION)
    self.multimedia_combo = ttk.Combobox(
        media_lic_box, textvariable=self.multimedia_var, state="readonly", width=11
    )
    self.multimedia_combo.pack(side=tk.LEFT, padx=(0, 4))

    self.license_var = tk.StringVar(value=ALL_OPTION)
    self.license_combo = ttk.Combobox(
        media_lic_box, textvariable=self.license_var, state="readonly", width=11
    )
    self.license_combo.pack(side=tk.LEFT)

    ttk.Label(catalog_frame, text="[D] Alertas esp. (geospatialIssues):").grid(
        row=2, column=2, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.issues_var = tk.StringVar(value=ALL_OPTION)
    self.issues_combo = ttk.Combobox(
        catalog_frame, textvariable=self.issues_var, state="readonly", width=22
    )
    self.issues_combo.grid(row=2, column=3, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(catalog_frame, text="[D] Incertidumbre m (Inf / Sup):").grid(
        row=2, column=4, sticky=tk.W, padx=(0, 4), pady=2
    )
    unc_box = ttk.Frame(catalog_frame)
    unc_box.grid(row=2, column=5, sticky=tk.W, pady=2)

    ttk.Label(unc_box, text="Inf:").pack(side=tk.LEFT, padx=(0, 2))
    self.unc_min_var = tk.StringVar()
    ttk.Entry(unc_box, textvariable=self.unc_min_var, width=8).pack(
        side=tk.LEFT, padx=(0, 6)
    )
    ttk.Label(unc_box, text="Sup:").pack(side=tk.LEFT, padx=(0, 2))
    self.unc_max_var = tk.StringVar()
    ttk.Entry(unc_box, textvariable=self.unc_max_var, width=8).pack(side=tk.LEFT)

    ttk.Label(catalog_frame, text="[E] Proveedor (data_provider_uid):").grid(
        row=3, column=0, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.provider_var = tk.StringVar(value=ALL_OPTION)
    self.provider_combo = ttk.Combobox(
        catalog_frame, textvariable=self.provider_var, state="readonly", width=24
    )
    self.provider_combo.grid(row=3, column=1, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(catalog_frame, text="[E] Cód. Institución (institutionCode):").grid(
        row=3, column=2, sticky=tk.W, padx=(0, 4), pady=2
    )
    self.inst_code_var = tk.StringVar(value=ALL_OPTION)
    self.inst_code_combo = ttk.Combobox(
        catalog_frame, textvariable=self.inst_code_var, state="readonly", width=22
    )
    self.inst_code_combo.grid(row=3, column=3, sticky=tk.W, padx=(0, 10), pady=2)

    ttk.Label(catalog_frame, text="[E] Cód. Colección (collectionCode):").grid(
        row=3, column=4, sticky=tk.W, padx=(0, 4), pady=2
    )
    col_reset_box = ttk.Frame(catalog_frame)
    col_reset_box.grid(row=3, column=5, sticky=tk.W, pady=2)

    self.col_code_var = tk.StringVar(value=ALL_OPTION)
    self.col_code_combo = ttk.Combobox(
        col_reset_box, textvariable=self.col_code_var, state="readonly", width=14
    )
    self.col_code_combo.pack(side=tk.LEFT, padx=(0, 6))

    ttk.Button(
        col_reset_box,
        text="Limpiar filtros",
        command=self._reset_all_filters,
    ).pack(side=tk.LEFT)

    toolbar = ttk.Frame(self, padding=(10, 2, 10, 4))
    toolbar.pack(fill=tk.X)

    ttk.Button(
        toolbar, text="Expandir todo", command=lambda: self._toggle_all(True)
    ).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(
        toolbar, text="Contraer todo", command=lambda: self._toggle_all(False)
    ).pack(side=tk.LEFT, padx=(0, 14))

    ttk.Label(toolbar, text="Filtrar texto en árbol:").pack(side=tk.LEFT, padx=(0, 6))
    self.filter_var = tk.StringVar()
    self.filter_var.trace_add("write", lambda *_: self._apply_tree_filter())
    ttk.Entry(toolbar, textvariable=self.filter_var, width=22).pack(
        side=tk.LEFT, padx=(0, 12)
    )

    legend_frame = ttk.Frame(toolbar)
    legend_frame.pack(side=tk.LEFT, padx=(4, 10))
    tk.Label(
        legend_frame,
        text="■ IN (Negro negrita)",
        fg="#111111",
        font=("Segoe UI", 9, "bold"),
    ).pack(side=tk.LEFT, padx=(0, 8))
    tk.Label(
        legend_frame,
        text="■ CO (Verde oscuro cursiva)",
        fg="#145A32",
        font=("Segoe UI", 9, "italic"),
    ).pack(side=tk.LEFT, padx=(0, 8))
    tk.Label(
        legend_frame,
        text="■ DR (Azul oscuro)",
        fg="#1B4F72",
        font=("Segoe UI", 9, "normal"),
    ).pack(side=tk.LEFT)

    self.export_btn = ttk.Button(
        toolbar,
        text="Exportar CSV",
        command=self._export_csv,
        state=tk.DISABLED,
    )
    self.export_btn.pack(side=tk.RIGHT, padx=(6, 0))

    self.charts_btn = ttk.Button(
        toolbar,
        text="Ver gráficas por año",
        command=self._open_charts_window,
        state=tk.DISABLED,
    )
    self.charts_btn.pack(side=tk.RIGHT)

    summary_frame = ttk.LabelFrame(self, text="Resumen global", padding=(10, 4))
    summary_frame.pack(fill=tk.X, padx=10, pady=(0, 4))

    self.summary_var = tk.StringVar(
        value="Cargando valores de facetas (Geografía + B, C, D, E) desde GBIF.es..."
    )
    ttk.Label(summary_frame, textvariable=self.summary_var).pack(anchor=tk.W)

    tree_frame = ttk.Frame(self, padding=(10, 0, 10, 4))
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (
        "nivel",
        "uid",
        "hijos",
        "registros",
        "descargas",
        "bajados",
        "citas",
        "estado",
    )
    self.tree = ttk.Treeview(
        tree_frame, columns=columns, show="tree headings", selectmode="browse"
    )

    self.tree.heading("#0", text="Entidad (IN → CO → DR)", anchor=tk.W)
    self.tree.heading("nivel", text="Nivel", anchor=tk.CENTER)
    self.tree.heading("uid", text="UID", anchor=tk.W)
    self.tree.heading("hijos", text="Sub-elementos", anchor=tk.CENTER)
    self.tree.heading("registros", text="Σ Registros", anchor=tk.E)
    self.tree.heading("descargas", text="Σ Descargas", anchor=tk.E)
    self.tree.heading("bajados", text="Σ Reg. bajados", anchor=tk.E)
    self.tree.heading("citas", text="Σ Citas cient.", anchor=tk.E)
    self.tree.heading("estado", text="Origen métricas", anchor=tk.W)

    self.tree.column("#0", width=410, minwidth=230, stretch=True)
    self.tree.column("nivel", width=52, minwidth=48, anchor=tk.CENTER, stretch=False)
    self.tree.column("uid", width=82, minwidth=72, anchor=tk.W, stretch=False)
    self.tree.column("hijos", width=105, minwidth=90, anchor=tk.CENTER, stretch=False)
    self.tree.column("registros", width=110, minwidth=85, anchor=tk.E, stretch=False)
    self.tree.column("descargas", width=98, minwidth=80, anchor=tk.E, stretch=False)
    self.tree.column("bajados", width=115, minwidth=90, anchor=tk.E, stretch=False)
    self.tree.column("citas", width=95, minwidth=80, anchor=tk.E, stretch=False)
    self.tree.column("estado", width=165, minwidth=120, anchor=tk.W, stretch=False)

    self.tree.tag_configure(
        "in_row",
        foreground="#111111",
        background="#F7F8FA",
        font=("Segoe UI", 9, "bold"),
    )
    self.tree.tag_configure(
        "co_row",
        foreground="#145A32",
        background="#F4FAF6",
        font=("Segoe UI", 9, "italic"),
    )
    self.tree.tag_configure(
        "dr_row",
        foreground="#1B4F72",
        background="#FFFFFF",
        font=("Segoe UI", 9, "normal"),
    )

    self.tree.bind("<Configure>", self._on_tree_configure)
    self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
    self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    self.tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    tree_frame.rowconfigure(0, weight=1)
    tree_frame.columnconfigure(0, weight=1)

    status_frame = ttk.Frame(self, padding=(10, 2, 10, 6))
    status_frame.pack(fill=tk.X)

    self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=200)
    self.progress.pack(side=tk.RIGHT)

    self.status_var = tk.StringVar(value="Listo.")
    ttk.Label(status_frame, textvariable=self.status_var).pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )

  def _open_charts_window(self) -> None:
    if self._current_data is None:
      return
    if self._charts_window is not None and self._charts_window.winfo_exists():
      self._charts_window.lift()
      self._charts_window.focus_force()
    else:
      self._charts_window = TemporalChartsWindow(self)
    self._sync_selection_to_charts()

  def _on_tree_select(self, _: Any) -> None:
    if self._charts_window is not None and self._charts_window.winfo_exists():
      self._sync_selection_to_charts()

  def _sync_selection_to_charts(self) -> None:
    if self._charts_window is None or not self._charts_window.winfo_exists():
      return
    selection = self.tree.selection()
    if not selection:
      self._charts_window.show_total_global()
      return
    node_id = selection[0]
    if node_id in self._node_scope_map:
      scope_label, dr_uids = self._node_scope_map[node_id]
      self._charts_window.update_scope(scope_label, dr_uids)
    else:
      self._charts_window.show_total_global()

  def _smart_wrap_label(self, text: str, level_depth: int = 0) -> tuple[str, int]:
    """Envuelve por palabras según el ancho real en píxeles de la columna #0."""
    clean = " ".join(text.split())
    if not clean:
      return "", 1

    col_width = max(int(self.tree.column("#0", "width")), 220)
    usable_px = max(col_width - (46 + level_depth * 22), 140)
    avg_char_px = max(self._tree_font.measure("n"), 6)
    max_chars = max(int(usable_px / avg_char_px), 22)

    wrapped_lines = textwrap.wrap(
        clean,
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=True,
    )
    if not wrapped_lines:
      return clean, 1
    if len(wrapped_lines) > 3:
      wrapped_lines = [*wrapped_lines[:2], f"{wrapped_lines[2]}…"]
    return "\n".join(wrapped_lines), len(wrapped_lines)

  def _on_tree_configure(self, _: Any) -> None:
    if self._current_data is None:
      return
    current_w = int(self.tree.column("#0", "width"))
    if abs(current_w - self._last_col0_width) >= 24:
      self._last_col0_width = current_w
      if self._rewrap_after_id is not None:
        self.after_cancel(self._rewrap_after_id)
      self._rewrap_after_id = self.after(180, self._apply_tree_filter)

  def _on_preset_selected(self, _: Any) -> None:
    selected_label = self.preset_var.get()
    if selected_label in PRESET_QUERIES:
      self.query_var.set(PRESET_QUERIES[selected_label])
      self._load_all_facets_async()

  def _reset_all_filters(self) -> None:
    for var in (
        self.continent_var,
        self.country_var,
        self.state_var,
        self.county_var,
        self.municipality_var,
        self.extra_value_var,
        self.basis_var,
        self.type_status_var,
        self.establishment_var,
        self.decade_var,
        self.month_var,
        self.multimedia_var,
        self.license_var,
        self.issues_var,
        self.provider_var,
        self.inst_code_var,
        self.col_code_var,
    ):
      var.set(ALL_OPTION)

    self.extra_field_var.set("(Ninguno)")
    self.year_min_var.set("")
    self.year_max_var.set("")
    self.collector_var.set("")
    self.unc_min_var.set("")
    self.unc_max_var.set("")
    self._load_all_facets_async()

  def _collect_active_fqs(
      self,
      stop_at_geo: str | None = None,
      strict_ranges: bool = True,
  ) -> list[str]:
    fqs: list[str] = []

    geo_sequence = [
        ("continent", self.continent_var.get()),
        ("country", self.country_var.get()),
        ("stateProvince", self.state_var.get()),
        ("county", self.county_var.get()),
        ("municipality", self.municipality_var.get()),
    ]
    for field_name, selected_val in geo_sequence:
      choices = self._facet_choices.get(field_name, {})
      if selected_val in choices:
        fqs.append(choices[selected_val].fq)
      if stop_at_geo == field_name:
        return fqs

    extra_val_sel = self.extra_value_var.get()
    if extra_val_sel in self._extra_geo_choices:
      fqs.append(self._extra_geo_choices[extra_val_sel].fq)

    catalog_combos = [
        ("basisOfRecord", self.basis_var.get()),
        ("typeStatus", self.type_status_var.get()),
        ("establishmentMeans", self.establishment_var.get()),
        ("decade", self.decade_var.get()),
        ("month", self.month_var.get()),
        ("multimedia", self.multimedia_var.get()),
        ("license", self.license_var.get()),
        ("geospatialIssues", self.issues_var.get()),
        ("data_provider_uid", self.provider_var.get()),
        ("institutionCode", self.inst_code_var.get()),
        ("collectionCode", self.col_code_var.get()),
    ]
    for field_name, selected_val in catalog_combos:
      choices = self._facet_choices.get(field_name, {})
      if selected_val in choices:
        fqs.append(choices[selected_val].fq)

    collector_txt = self.collector_var.get().strip()
    if collector_txt:
      safe_col = collector_txt.replace('"', '\\"')
      fqs.append(f"recordedBy:*{safe_col}*")

    try:
      year_fq = build_solr_range_fq(
          "year",
          self.year_min_var.get(),
          self.year_max_var.get(),
          "Rango de años",
          is_int=True,
      )
      if year_fq:
        fqs.append(year_fq)

      unc_fq = build_solr_range_fq(
          "coordinateUncertaintyInMeters",
          self.unc_min_var.get(),
          self.unc_max_var.get(),
          "Incertidumbre espacial (m)",
          is_int=False,
      )
      if unc_fq:
        fqs.append(unc_fq)
    except ValueError:
      if strict_ranges:
        raise

    return fqs

  def _load_all_facets_async(self, cascade_level: str | None = None) -> None:
    if cascade_level == "continent":
      self.country_var.set(ALL_OPTION)
      self.state_var.set(ALL_OPTION)
      self.county_var.set(ALL_OPTION)
      self.municipality_var.set(ALL_OPTION)
    elif cascade_level == "country":
      self.state_var.set(ALL_OPTION)
      self.county_var.set(ALL_OPTION)
      self.municipality_var.set(ALL_OPTION)
    elif cascade_level == "state":
      self.county_var.set(ALL_OPTION)
      self.municipality_var.set(ALL_OPTION)

    query = self.query_var.get().strip() or "*:*"
    fqs = self._collect_active_fqs(
        stop_at_geo=cascade_level, strict_ranges=False
    )

    if not self._is_running:
      self.status_var.set(
          "Actualizando filtros disponibles (Geo + B, C, D, E)..."
      )
    facet_list = ",".join(self._facet_choices.keys())

    def _worker() -> None:
      params: dict[str, Any] = {
          "q": query,
          "pageSize": 0,
          "facets": facet_list,
          "flimit": 3000,
      }
      if fqs:
        params["fq"] = fqs

      payload, status = fetch_json(BASE_SEARCH_URL, params=params)

      extra_fields: dict[str, str] = {}
      if not self._extra_geo_fields:
        fields_payload, _ = fetch_json(BASE_FIELDS_URL)
        if isinstance(fields_payload, list):
          for f in fields_payload:
            if not isinstance(f, dict):
              continue
            name = str(f.get("name") or "")
            desc = str(f.get("description") or f.get("info") or name)
            indexed = bool(f.get("indexed", True))
            if indexed and (
                name.startswith("cl")
                or name
                in {
                    "island",
                    "islandGroup",
                    "waterBody",
                    "higherGeography",
                    "locality",
                    "biogeographicRegion",
                }
            ):
              label = f"{desc} [{name}]" if desc and desc != name else name
              extra_fields[label] = name

      self._worker_queue.put(
          (
              "all_facets_loaded",
              {
                  "payload": payload,
                  "status": status,
                  "cascade_level": cascade_level,
                  "extra_fields": extra_fields,
              },
          )
      )

    threading.Thread(target=_worker, daemon=True).start()

  def _load_extra_field_values_async(self) -> None:
    selected_label = self.extra_field_var.get()
    self.extra_value_var.set(ALL_OPTION)
    self._extra_geo_choices = {}
    self.extra_value_combo["values"] = [ALL_OPTION]

    if selected_label not in self._extra_geo_fields:
      return

    field_name = self._extra_geo_fields[selected_label]
    query = self.query_var.get().strip() or "*:*"
    base_fqs = [
        fq
        for fq in self._collect_active_fqs(strict_ranges=False)
        if not fq.startswith(f"{field_name}:")
    ]
    if not self._is_running:
      self.status_var.set(f"Cargando valores para {field_name}...")

    def _worker() -> None:
      params: dict[str, Any] = {
          "q": query,
          "pageSize": 0,
          "facets": field_name,
          "flimit": 5000,
      }
      if base_fqs:
        params["fq"] = base_fqs
      payload, _ = fetch_json(BASE_SEARCH_URL, params=params)
      choices = parse_facet_choices(payload, field_name)
      self._worker_queue.put(("extra_values_loaded", choices))

    threading.Thread(target=_worker, daemon=True).start()

  def _start_search(self) -> None:
    if self._is_running:
      if self._worker_thread is None or not self._worker_thread.is_alive():
        self._is_running = False
      else:
        self.status_var.set(
            "Ya hay una consulta en curso. Pulsa «Detener» si deseas cancelarla."
        )
        self.update_idletasks()
        return

    query = self.query_var.get().strip()
    if not query:
      messagebox.showwarning(
          "Consulta vacía", "Introduce una palabra clave o consulta Solr."
      )
      return

    try:
      active_fqs = self._collect_active_fqs(strict_ranges=True)
    except ValueError as exc:
      messagebox.showwarning("Rango numérico inválido", str(exc))
      return

    while not self._worker_queue.empty():
      try:
        self._worker_queue.get_nowait()
      except queue.Empty:
        break

    self._is_running = True
    self._cancel_event.clear()
    self.search_btn.configure(state=tk.DISABLED)
    self.cancel_btn.configure(state=tk.NORMAL)
    self.export_btn.configure(state=tk.DISABLED)
    self.charts_btn.configure(state=tk.DISABLED)
    self.tree.delete(*self.tree.get_children())
    self._node_scope_map.clear()
    self.status_var.set(f"Paso 1/3 — Consultando instituciones para {query}...")
    self.progress.stop()
    self.progress.start(12)
    self.update_idletasks()

    fetch_stats = self.fetch_stats_var.get()
    self._worker_thread = threading.Thread(
        target=self._run_pipeline,
        args=(query, active_fqs, fetch_stats),
        daemon=True,
    )
    self._worker_thread.start()

  def _run_pipeline(
      self, query: str, base_fqs: list[str], fetch_stats: bool
  ) -> None:
    finished_event: tuple[str, Any] = (
        "error",
        "La consulta finalizó sin devolver resultados.",
    )
    try:
      root_params: dict[str, Any] = {
          "q": query,
          "pageSize": 0,
          "facets": "institution_uid",
          "flimit": 2000,
      }
      if base_fqs:
        root_params["fq"] = base_fqs

      payload, status = fetch_json(BASE_SEARCH_URL, params=root_params)
      if payload is None:
        finished_event = (
            "error",
            f"No se pudo conectar con GBIF.es ({status}).",
        )
        return

      total_records = int(payload.get("totalRecords", 0) or 0)
      institutions: list[InstitutionRow] = []
      for item in get_facet_items(payload, "institution_uid"):
        uid = extract_uid(item)
        if uid:
          institutions.append(
              InstitutionRow(
                  uid=uid,
                  label=str(item.get("label") or uid),
                  records=int(item.get("count", 0) or 0),
              )
          )
      institutions.sort(key=lambda r: r.records, reverse=True)

      collections: list[CollectionRow] = []
      datasets: list[DatasetRow] = []

      for idx, inst in enumerate(institutions, start=1):
        if self._cancel_event.is_set():
          finished_event = ("cancelled", None)
          return

        self._worker_queue.put(
            (
                "progress",
                f"Paso 2/3 — Instituciones ({idx}/{len(institutions)}): {inst.label}",
            )
        )

        inst_fqs = [*base_fqs, f'institution_uid:"{inst.uid}"']
        inst_payload, _ = fetch_json(
            BASE_SEARCH_URL,
            params={
                "q": query,
                "fq": inst_fqs,
                "pageSize": 0,
                "facets": "collection_uid,data_resource_uid",
                "flimit": 2000,
            },
        )

        inst_cos: list[CollectionRow] = []
        for item in get_facet_items(inst_payload, "collection_uid"):
          co_uid = extract_uid(item)
          if co_uid:
            row = CollectionRow(
                uid=co_uid,
                institution_uid=inst.uid,
                label=str(item.get("label") or co_uid),
                records=int(item.get("count", 0) or 0),
            )
            collections.append(row)
            inst_cos.append(row)

        assigned_dr: set[str] = set()
        for co in inst_cos:
          if self._cancel_event.is_set():
            finished_event = ("cancelled", None)
            return

          co_fqs = [
              *base_fqs,
              f'institution_uid:"{inst.uid}"',
              f'collection_uid:"{co.uid}"',
          ]
          co_payload, _ = fetch_json(
              BASE_SEARCH_URL,
              params={
                  "q": query,
                  "fq": co_fqs,
                  "pageSize": 0,
                  "facets": "data_resource_uid",
                  "flimit": 2000,
              },
          )
          for item in get_facet_items(co_payload, "data_resource_uid"):
            dr_uid = extract_uid(item)
            if dr_uid:
              assigned_dr.add(dr_uid)
              datasets.append(
                  DatasetRow(
                      uid=dr_uid,
                      institution_uid=inst.uid,
                      collection_uid=co.uid,
                      label=str(item.get("label") or dr_uid),
                      records=int(item.get("count", 0) or 0),
                  )
              )

        for item in get_facet_items(inst_payload, "data_resource_uid"):
          dr_uid = extract_uid(item)
          if dr_uid and dr_uid not in assigned_dr:
            datasets.append(
                DatasetRow(
                    uid=dr_uid,
                    institution_uid=inst.uid,
                    collection_uid=None,
                    label=str(item.get("label") or dr_uid),
                    records=int(item.get("count", 0) or 0),
                )
            )

      stats_by_uid: dict[str, DatasetStatsRow] = {}
      unique_dr_uids = list(dict.fromkeys(ds.uid for ds in datasets))
      dl_year_cache: dict[str, int | None] = {}

      if fetch_stats:
        for idx, dr_uid in enumerate(unique_dr_uids, start=1):
          if self._cancel_event.is_set():
            finished_event = ("cancelled", None)
            return

          self._worker_queue.put(
              (
                  "progress",
                  f"Paso 3/3 — Descargas, citas y años ({idx}/{len(unique_dr_uids)}): {dr_uid}",
              )
          )
          stats_by_uid[dr_uid] = fetch_dataset_download_and_citation_stats(
              uid=dr_uid,
              dl_year_cache=dl_year_cache,
              resolve_download_years=True,
          )
      else:
        for dr_uid in unique_dr_uids:
          stats_by_uid[dr_uid] = DatasetStatsRow(
              dr_uid, "", None, 0, 0, 0, "OMITIDO"
          )

      finished_event = (
          "done",
          {
              "query": query,
              "active_fqs": base_fqs,
              "total_records": total_records,
              "institutions": institutions,
              "collections": collections,
              "datasets": datasets,
              "stats_by_uid": stats_by_uid,
          },
      )
    except Exception as exc:  # noqa: BLE001
      finished_event = ("error", str(exc))
    finally:
      self._worker_queue.put(finished_event)

  def _cancel_search(self) -> None:
    if self._is_running:
      self._cancel_event.set()
      self.status_var.set("Cancelando operación...")
      self.update_idletasks()

  def _poll_queue(self) -> None:
    try:
      while True:
        msg_type, payload = self._worker_queue.get_nowait()
        if msg_type == "all_facets_loaded":
          self._apply_loaded_facets(payload)
        elif msg_type == "extra_values_loaded":
          self._extra_geo_choices = payload
          self.extra_value_combo["values"] = [ALL_OPTION, *payload.keys()]
          if not self._is_running:
            self.status_var.set(f"Cargados {len(payload)} valores espaciales.")
        elif msg_type == "progress":
          if self._is_running:
            self.status_var.set(str(payload))
            self.update_idletasks()
        elif msg_type == "cancelled":
          self._finish_worker("Consulta cancelada por el usuario.")
        elif msg_type == "error":
          self._finish_worker("Error en la consulta.")
          messagebox.showerror("Error", str(payload))
        elif msg_type == "done":
          self._current_data = payload
          self._populate_tree(payload)
          self._finish_worker("Consulta completada.")
          if (
              self._charts_window is not None
              and self._charts_window.winfo_exists()
          ):
            self._charts_window.show_total_global()
    except queue.Empty:
      pass
    finally:
      self.after(80, self._poll_queue)

  def _apply_loaded_facets(self, info: dict[str, Any]) -> None:
    payload = info.get("payload")
    cascade_level = info.get("cascade_level")
    extra_fields = info.get("extra_fields") or {}

    if extra_fields and not self._extra_geo_fields:
      self._extra_geo_fields = dict(sorted(extra_fields.items()))
      self.extra_field_combo["values"] = [
          "(Ninguno)",
          *self._extra_geo_fields.keys(),
      ]

    if payload is None:
      if not self._is_running:
        self.status_var.set(
            f"No se pudieron cargar facetas ({info.get('status')})."
        )
      return

    combo_map: dict[str, ttk.Combobox] = {
        "continent": self.continent_combo,
        "country": self.country_combo,
        "stateProvince": self.state_combo,
        "county": self.county_combo,
        "municipality": self.municipality_combo,
        "basisOfRecord": self.basis_combo,
        "typeStatus": self.type_status_combo,
        "establishmentMeans": self.establishment_combo,
        "decade": self.decade_combo,
        "month": self.month_combo,
        "multimedia": self.multimedia_combo,
        "license": self.license_combo,
        "geospatialIssues": self.issues_combo,
        "data_provider_uid": self.provider_combo,
        "institutionCode": self.inst_code_combo,
        "collectionCode": self.col_code_combo,
    }

    skip_fields: set[str] = set()
    if cascade_level == "continent":
      skip_fields.add("continent")
    elif cascade_level == "country":
      skip_fields.update({"continent", "country"})
    elif cascade_level == "state":
      skip_fields.update({"continent", "country", "stateProvince"})

    for field_name, combo in combo_map.items():
      if field_name in skip_fields:
        continue
      choices = parse_facet_choices(payload, field_name)
      self._facet_choices[field_name] = choices
      combo["values"] = [ALL_OPTION, *choices.keys()]

    if not self._is_running:
      self.status_var.set(
          f"Filtros actualizados: {len(self._facet_choices['country'])} países, "
          f"{len(self._facet_choices['stateProvince'])} regiones/prov., "
          f"{len(self._facet_choices['basisOfRecord'])} bases reg., "
          f"{len(self._facet_choices['institutionCode'])} cód. institución."
      )
    if self._current_data is None:
      self.summary_var.set(
          "Filtros cargados. Combina país/región, rango de años o ejes B–E y pulsa «Consultar árbol»."
      )

  def _finish_worker(self, status_text: str) -> None:
    self._is_running = False
    self._worker_thread = None
    self.progress.stop()
    self.search_btn.configure(state=tk.NORMAL)
    self.cancel_btn.configure(state=tk.DISABLED)
    self.status_var.set(status_text)
    if self._current_data is not None:
      self.export_btn.configure(state=tk.NORMAL)
      self.charts_btn.configure(state=tk.NORMAL)
    self.update_idletasks()

  @staticmethod
  def _summarize_statuses(
      dr_uids: set[str], stats_by_uid: dict[str, DatasetStatsRow]
  ) -> str:
    if not dr_uids:
      return "Sin DR"
    statuses = {
        stats_by_uid[uid].status for uid in dr_uids if uid in stats_by_uid
    }
    if not statuses:
      return "SIN_DATO"
    if len(statuses) == 1:
      return next(iter(statuses))
    ok_count = sum(
        1
        for uid in dr_uids
        if uid in stats_by_uid and stats_by_uid[uid].status.startswith("OK")
    )
    return f"Mixto ({ok_count}/{len(dr_uids)} OK)"

  def _populate_tree(self, data: dict[str, Any], text_filter: str = "") -> None:
    self.tree.delete(*self.tree.get_children())
    self._node_scope_map.clear()

    institutions: list[InstitutionRow] = data["institutions"]
    collections: list[CollectionRow] = data["collections"]
    datasets: list[DatasetRow] = data["datasets"]
    stats_by_uid: dict[str, DatasetStatsRow] = data["stats_by_uid"]

    needle = text_filter.strip().lower()
    max_lines_seen = 1

    co_by_inst: dict[str, list[CollectionRow]] = {}
    for co in collections:
      co_by_inst.setdefault(co.institution_uid, []).append(co)

    dr_by_inst_co: dict[tuple[str, str | None], list[DatasetRow]] = {}
    for ds in datasets:
      dr_by_inst_co.setdefault((ds.institution_uid, ds.collection_uid), []).append(
          ds
      )

    total_downloads = sum(s.downloads for s in stats_by_uid.values())
    total_bajados = sum(s.downloaded_records for s in stats_by_uid.values())
    total_citas = sum(s.citations for s in stats_by_uid.values())
    unique_drs = len({ds.uid for ds in datasets})
    fq_summary = ", ".join(data.get("active_fqs") or []) or "Sin filtros fq"

    self.summary_var.set(
        f"q={data['query']} | fq=[{fq_summary}]   ||   "
        f"IN: {len(institutions):,} | CO: {len(collections):,} | DR: {unique_drs:,} | "
        f"Σ Registros: {data['total_records']:,} | "
        f"Σ Descargas: {total_downloads:,} | "
        f"Σ Reg. bajados: {total_bajados:,} | "
        f"Σ Citas cient.: {total_citas:,}"
    )

    for inst in institutions:
      inst_cos = co_by_inst.get(inst.uid, [])
      direct_drs = dr_by_inst_co.get((inst.uid, None), [])

      inst_matches = (
          not needle
          or needle in inst.label.lower()
          or needle in inst.uid.lower()
      )

      visible_cos: list[tuple[CollectionRow, list[DatasetRow]]] = []
      for co in inst_cos:
        co_drs = dr_by_inst_co.get((inst.uid, co.uid), [])
        co_matches = (
            inst_matches
            or needle in co.label.lower()
            or needle in co.uid.lower()
        )
        matching_drs = [
            ds
            for ds in co_drs
            if co_matches
            or needle in ds.label.lower()
            or needle in ds.uid.lower()
        ]
        if co_matches or matching_drs:
          visible_cos.append((co, matching_drs if not co_matches else co_drs))

      visible_direct_drs = [
          ds
          for ds in direct_drs
          if inst_matches
          or needle in ds.label.lower()
          or needle in ds.uid.lower()
      ]

      if not inst_matches and not visible_cos and not visible_direct_drs:
        continue

      inst_unique_dr_uids: set[str] = set()
      for _, co_drs in visible_cos:
        for ds in co_drs:
          inst_unique_dr_uids.add(ds.uid)
      for ds in visible_direct_drs:
        inst_unique_dr_uids.add(ds.uid)

      inst_sum_downloads = sum(
          stats_by_uid[uid].downloads
          for uid in inst_unique_dr_uids
          if uid in stats_by_uid
      )
      inst_sum_bajados = sum(
          stats_by_uid[uid].downloaded_records
          for uid in inst_unique_dr_uids
          if uid in stats_by_uid
      )
      inst_sum_citas = sum(
          stats_by_uid[uid].citations
          for uid in inst_unique_dr_uids
          if uid in stats_by_uid
      )
      inst_status = self._summarize_statuses(inst_unique_dr_uids, stats_by_uid)
      inst_children_label = (
          f"{len(visible_cos)} CO / {len(inst_unique_dr_uids)} DR"
      )

      inst_wrapped, n_lines = self._smart_wrap_label(inst.label, level_depth=0)
      max_lines_seen = max(max_lines_seen, n_lines)

      inst_node = self.tree.insert(
          "",
          tk.END,
          text=inst_wrapped,
          values=(
              "IN",
              inst.uid,
              inst_children_label,
              f"{inst.records:,}",
              f"{inst_sum_downloads:,}",
              f"{inst_sum_bajados:,}",
              f"{inst_sum_citas:,}",
              inst_status,
          ),
          open=bool(needle),
          tags=("in_row",),
      )
      self._node_scope_map[inst_node] = (
          f"[IN {inst.uid}] {inst.label} ({len(inst_unique_dr_uids)} DR)",
          inst_unique_dr_uids,
      )

      for co, co_drs in visible_cos:
        co_unique_dr_uids = {ds.uid for ds in co_drs}
        co_sum_downloads = sum(
            stats_by_uid[uid].downloads
            for uid in co_unique_dr_uids
            if uid in stats_by_uid
        )
        co_sum_bajados = sum(
            stats_by_uid[uid].downloaded_records
            for uid in co_unique_dr_uids
            if uid in stats_by_uid
        )
        co_sum_citas = sum(
            stats_by_uid[uid].citations
            for uid in co_unique_dr_uids
            if uid in stats_by_uid
        )
        co_status = self._summarize_statuses(co_unique_dr_uids, stats_by_uid)

        co_wrapped, n_lines = self._smart_wrap_label(co.label, level_depth=1)
        max_lines_seen = max(max_lines_seen, n_lines)

        co_node = self.tree.insert(
            inst_node,
            tk.END,
            text=co_wrapped,
            values=(
                "CO",
                co.uid,
                f"{len(co_drs)} DR",
                f"{co.records:,}",
                f"{co_sum_downloads:,}",
                f"{co_sum_bajados:,}",
                f"{co_sum_citas:,}",
                co_status,
            ),
            open=bool(needle),
            tags=("co_row",),
        )
        self._node_scope_map[co_node] = (
            f"[CO {co.uid}] {co.label} ({len(co_unique_dr_uids)} DR)",
            co_unique_dr_uids,
        )

        for ds in co_drs:
          st = stats_by_uid.get(
              ds.uid,
              DatasetStatsRow(ds.uid, "", None, 0, 0, 0, "SIN_DATO"),
          )
          ds_wrapped, n_lines = self._smart_wrap_label(ds.label, level_depth=2)
          max_lines_seen = max(max_lines_seen, n_lines)

          dr_node = self.tree.insert(
              co_node,
              tk.END,
              text=ds_wrapped,
              values=(
                  "DR",
                  ds.uid,
                  "—",
                  f"{ds.records:,}",
                  f"{st.downloads:,}",
                  f"{st.downloaded_records:,}",
                  f"{st.citations:,}",
                  st.status,
              ),
              tags=("dr_row",),
          )
          pub_txt = f" — publicado en {st.pub_year}" if st.pub_year else ""
          self._node_scope_map[dr_node] = (
              f"[DR {ds.uid}] {ds.label}{pub_txt}",
              {ds.uid},
          )

      for ds in visible_direct_drs:
        st = stats_by_uid.get(
            ds.uid,
            DatasetStatsRow(ds.uid, "", None, 0, 0, 0, "SIN_DATO"),
        )
        ds_wrapped, n_lines = self._smart_wrap_label(ds.label, level_depth=1)
        max_lines_seen = max(max_lines_seen, n_lines)

        dr_node = self.tree.insert(
            inst_node,
            tk.END,
            text=ds_wrapped,
            values=(
                "DR",
                ds.uid,
                "—",
                f"{ds.records:,}",
                f"{st.downloads:,}",
                f"{st.downloaded_records:,}",
                f"{st.citations:,}",
                st.status,
            ),
            tags=("dr_row",),
        )
        pub_txt = f" — publicado en {st.pub_year}" if st.pub_year else ""
        self._node_scope_map[dr_node] = (
            f"[DR {ds.uid}] {ds.label}{pub_txt}",
            {ds.uid},
        )

    line_height = self._tree_font.metrics("linespace") + 4
    computed_rowheight = max(24, min(max_lines_seen * line_height + 6, 68))
    self.style.configure("Treeview", rowheight=computed_rowheight)

  def _apply_tree_filter(self) -> None:
    if self._current_data is not None:
      self._populate_tree(self._current_data, text_filter=self.filter_var.get())

  def _toggle_all(self, open_state: bool) -> None:
    def _walk(item_id: str) -> None:
      self.tree.item(item_id, open=open_state)
      for child in self.tree.get_children(item_id):
        _walk(child)

    for root_id in self.tree.get_children():
      _walk(root_id)

  def _export_csv(self) -> None:
    if self._current_data is None:
      return

    filepath = filedialog.asksaveasfilename(
        title="Guardar desagregación IN → CO → DR con descargas, citas y año de publicación",
        defaultextension=".csv",
        filetypes=[("Archivo CSV", "*.csv")],
        initialfile="gbif_es_catalogo_in_co_dr_citas.csv",
    )
    if not filepath:
      return

    inst_map = {i.uid: i for i in self._current_data["institutions"]}
    co_map = {c.uid: c for c in self._current_data["collections"]}
    stats_map: dict[str, DatasetStatsRow] = self._current_data["stats_by_uid"]
    fq_text = " AND ".join(self._current_data.get("active_fqs") or [])

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
      writer = csv.writer(f, delimiter=";")
      writer.writerow(
          [
              "query",
              "active_filters_fq",
              "institution_uid",
              "institution_label",
              "institution_records",
              "collection_uid",
              "collection_label",
              "collection_records",
              "dataset_uid",
              "dataset_label",
              "dataset_records",
              "dataset_publication_year",
              "gbif_registry_uuid",
              "downloads",
              "downloaded_records",
              "scientific_citations",
              "stats_status",
          ]
      )
      for ds in self._current_data["datasets"]:
        inst = inst_map.get(ds.institution_uid)
        co = co_map.get(ds.collection_uid) if ds.collection_uid else None
        st = stats_map.get(
            ds.uid,
            DatasetStatsRow(ds.uid, "", None, 0, 0, 0, "SIN_DATO"),
        )
        writer.writerow(
            [
                self._current_data["query"],
                fq_text,
                ds.institution_uid,
                inst.label if inst else "",
                inst.records if inst else 0,
                ds.collection_uid or "",
                co.label if co else "",
                co.records if co else 0,
                ds.uid,
                ds.label,
                ds.records,
                st.pub_year or "",
                st.gbif_uuid,
                st.downloads,
                st.downloaded_records,
                st.citations,
                st.status,
            ]
        )

    messagebox.showinfo(
        "Exportación completada", f"Datos guardados en:\n{filepath}"
    )


def main() -> None:
  app = GbifEsFullCatalogExplorerApp()
  app.mainloop()


if __name__ == "__main__":
  main()