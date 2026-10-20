import requests
import pandas as pd

url = (
    "https://iepnb.gob.es/api/especie/v_taxonomia"
    "?select=name,taxonid,citescode,euniscode,euringcode,rednaturacode"
)

datos = requests.get(
    url,
    headers={"Accept": "application/json"},
    timeout=120
).json()

df = pd.DataFrame(datos)

print("Total registros:", len(df))

for campo in [
    "citescode",
    "euniscode",
    "euringcode",
    "rednaturacode"
]:

    n = df[campo].notna().sum()

    print(f"\n{campo}: {n}")