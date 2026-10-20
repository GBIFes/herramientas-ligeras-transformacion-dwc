from pathlib import Path
from bs4 import BeautifulSoup

html = Path(
    "ficha_11276.html"
).read_text(
    encoding="utf-8"
)

soup = BeautifulSoup(
    html,
    "html.parser"
)

tablas = soup.find_all("table")

print(
    f"Tablas: {len(tablas)}"
)

# =====================================================
# TABLA 1
# NOMBRES COMUNES
# =====================================================

tabla = tablas[0]

print("\n")
print("=" * 80)
print("NOMBRES COMUNES")
print("=" * 80)

filas = tabla.find_all("tr")

for fila in filas:

    columnas = [
        td.get_text(
            strip=True
        )
        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    print(columnas)

# =====================================================
# TABLA 3
# ESTADO CONSERVACION
# =====================================================

tabla = tablas[2]

print("\n")
print("=" * 80)
print("ESTADO CONSERVACION")
print("=" * 80)

filas = tabla.find_all("tr")

for fila in filas:

    columnas = [
        td.get_text(
            strip=True
        )
        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    print(columnas)

# =====================================================
# TABLA 4
# COLECCIONES
# =====================================================

tabla = tablas[3]

print("\n")
print("=" * 80)
print("COLECCIONES")
print("=" * 80)

filas = tabla.find_all("tr")

for fila in filas:

    columnas = [
        td.get_text(
            strip=True
        )
        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    print(columnas)

# =====================================================
# TABLA 5
# ESTADO LEGAL
# =====================================================

tabla = tablas[4]

print("\n")
print("=" * 80)
print("ESTADO LEGAL")
print("=" * 80)

filas = tabla.find_all("tr")

for fila in filas:

    columnas = [
        td.get_text(
            strip=True
        )
        for td in fila.find_all(
            ["td", "th"]
        )
    ]

    print(columnas)