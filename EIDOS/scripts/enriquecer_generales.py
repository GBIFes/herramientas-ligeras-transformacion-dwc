"""
enriquecer_generales.py

Obtiene de la ficha EIDOS:

- Ámbito
- Grupo taxonómico
- Reino
- Filo
- Clase
- Orden
- Familia
- Género
- Especie
- Autor

y actualiza la tabla especies.

Autor: Javier Estrada
"""

from pathlib import Path
import sqlite3
import requests

from bs4 import BeautifulSoup


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

TAXONID = 11276

BASE_DIR = Path(
    r"C:\Users\Javier Estrada\Documents\GitHub\herramientas-ligeras-transformacion-dwc\EIDOS"
)

DB = BASE_DIR / "data" / "especies_legales.sqlite"

# ==========================================================
# DESCARGAR FICHA
# ==========================================================

url = (
    "https://iepnb.gob.es/"
    "areas-tematicas/"
    "especies-silvestres/"
    f"eidos/{TAXONID}"
)

print(url)

r = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=60
)

print(
    "HTTP:",
    r.status_code
)

soup = BeautifulSoup(
    r.text,
    "html.parser"
)

# ==========================================================
# TEXTO GENERAL
# ==========================================================

texto = soup.get_text(
    "\n",
    strip=True
)

lineas = [
    linea.strip()
    for linea in texto.splitlines()
    if linea.strip()
]

# ==========================================================
# VARIABLES
# ==========================================================

ambito = None
grupo_taxonomico = None

reino = None
filo = None
clase = None
orden = None
familia = None
genero = None
especie = None
autor = None

# ==========================================================
# ÁMBITO Y GRUPO TAXONÓMICO
# ==========================================================

for i, linea in enumerate(lineas):

    if linea == "Ámbito:":

        if i + 1 < len(lineas):
            ambito = lineas[i + 1]

    elif linea == "Grupo Taxonómico":

        if i + 1 < len(lineas):
            grupo_taxonomico = lineas[i + 1]

# ==========================================================
# TAXONOMÍA
# ==========================================================

for li in soup.find_all("li"):

    texto_li = li.get_text(
        " ",
        strip=True
    )

    if texto_li.startswith("Reino:"):

        reino = (
            texto_li
            .replace(
                "Reino:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith(
        "División o Filo:"
    ):

        filo = (
            texto_li
            .replace(
                "División o Filo:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Filo:"):

        filo = (
            texto_li
            .replace(
                "Filo:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Clase:"):

        clase = (
            texto_li
            .replace(
                "Clase:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Orden:"):

        orden = (
            texto_li
            .replace(
                "Orden:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Familia:"):

        familia = (
            texto_li
            .replace(
                "Familia:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Género:"):

        genero = (
            texto_li
            .replace(
                "Género:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Especie:"):

        especie = (
            texto_li
            .replace(
                "Especie:",
                ""
            )
            .strip()
        )

    elif texto_li.startswith("Autor:"):

        autor = (
            texto_li
            .replace(
                "Autor:",
                ""
            )
            .strip()
        )

# ==========================================================
# INFORMACIÓN EXTRAÍDA
# ==========================================================

print()
print("Ámbito:", ambito)
print("Grupo taxonómico:", grupo_taxonomico)

print()
print("Reino:", reino)
print("Filo:", filo)
print("Clase:", clase)
print("Orden:", orden)
print("Familia:", familia)
print("Género:", genero)
print("Especie:", especie)
print("Autor:", autor)

# ==========================================================
# GUARDAR EN SQLITE
# ==========================================================

conn = sqlite3.connect(DB)

cur = conn.cursor()

cur.execute(
    """
    UPDATE especies
    SET

        ambito = ?,

        grupo_taxonomico = ?,

        reino = COALESCE(?, reino),

        phylum = COALESCE(?, phylum),

        clase = COALESCE(?, clase),

        orden_taxonomico = COALESCE(
            ?,
            orden_taxonomico
        ),

        familia = COALESCE(
            ?,
            familia
        ),

        genero = COALESCE(
            ?,
            genero
        ),

        especie_epiteto = ?,

        autor_taxon = ?,

        fecha_enriquecimiento = datetime('now')

    WHERE taxonid = ?
    """,
    (
        ambito,
        grupo_taxonomico,

        reino,
        filo,
        clase,
        orden,
        familia,
        genero,

        especie,
        autor,

        TAXONID
    )
)

conn.commit()

conn.close()

print()
print(
    "Datos generales actualizados."
)
