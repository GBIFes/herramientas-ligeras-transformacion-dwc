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
    f"Tablas encontradas: {len(tablas)}"
)

for i, tabla in enumerate(tablas):

    print("\n")
    print("=" * 80)
    print(f"TABLA {i+1}")
    print("=" * 80)

    texto = tabla.get_text(
        separator=" | ",
        strip=True
    )

    print(
        texto[:2000]
    )