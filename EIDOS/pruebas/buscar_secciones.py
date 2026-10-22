from pathlib import Path

html = Path(
    "ficha_11276.html"
).read_text(
    encoding="utf-8"
)

busquedas = [

    "Estado legal",
    "Estado de conservación",
    "Colecciones/Catálogos",
    "Colecciones",
    "Nombres comunes",
    "UICN",
    "Norma",
    "Ámbito de aplicación",
    "Aplicación",
    "Conservación",
    "Autoridad"
]

for texto in busquedas:

    print("-" * 60)

    print(texto)

    print(
        texto in html
    )