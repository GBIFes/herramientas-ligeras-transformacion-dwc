import requests
from bs4 import BeautifulSoup

TAXONID = 11276

url = (
    "https://iepnb.gob.es/"
    "areas-tematicas/"
    "especies-silvestres/"
    f"eidos/{TAXONID}"
)

r = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=60
)

soup = BeautifulSoup(
    r.text,
    "html.parser"
)

tabla = soup.find_all("table")[5]

for fila in tabla.find_all("tr"):

    celdas = fila.find_all(
        ["td", "th"]
    )

    print("--------------------------------")

    for celda in celdas:

        print(
            celda.get_text(
                " ",
                strip=True
            )
        )

        enlace = celda.find("a")

        if enlace:

            print(
                "URL:",
                enlace.get("href")
            )