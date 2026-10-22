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
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=60
)

soup = BeautifulSoup(
    r.text,
    "html.parser"
)

# Buscar todos los elementos li
for li in soup.find_all("li"):

    texto = li.get_text(
        " ",
        strip=True
    )

    if (
        "Reino:" in texto
        or "Filo:" in texto
        or "División o Filo:" in texto
        or "Clase:" in texto
        or "Orden:" in texto
        or "Familia:" in texto
        or "Género:" in texto
        or "Especie:" in texto
        or "Autor:" in texto
    ):

        print(texto)