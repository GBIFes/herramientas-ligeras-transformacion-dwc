from pathlib import Path
import requests

# Taxon conocido
TAXONID = 11276

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
        "User-Agent":
        "Mozilla/5.0"
    },
    timeout=60
)

print(
    "HTTP:",
    r.status_code
)

salida = Path("ficha_11276.html")

salida.write_text(
    r.text,
    encoding="utf-8"
)

print(
    f"Guardado: {salida}"
)