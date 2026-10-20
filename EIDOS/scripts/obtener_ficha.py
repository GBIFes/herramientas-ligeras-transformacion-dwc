import requests
from bs4 import BeautifulSoup


def obtener_soup(taxonid):

    url = (
        "https://iepnb.gob.es/"
        "areas-tematicas/"
        "especies-silvestres/"
        f"eidos/{int(float(taxonid))}"
    )

    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=60
    )

    r.raise_for_status()

    return BeautifulSoup(
        r.text,
        "html.parser"
    )