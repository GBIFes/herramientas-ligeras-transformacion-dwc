import pyodbc
import requests
from bs4 import BeautifulSoup
import csv
import re
import time

# ============================================================
# CONFIGURACIÓN
# ============================================================

DATABASE = r"C:\Users\Javier Estrada\Documents\Database2.accdb"
TABLE = "LESRP"
CAMPO_NOMBRE = "NombreActualizado"
CSV_SALIDA = r"C:\Users\Javier Estrada\Documents\LESRP\ipni_datos.csv"

HEADERS = {"User-Agent": "Mozilla/5.0"}
PAUSA = 0.5

# ============================================================
# NORMALIZACIÓN DEL NOMBRE
# ============================================================

def normalizar_nombre(nombre):
    nombre = nombre.strip()
    nombre = re.sub(r"\([^)]*\)", "", nombre)  # quitar autores
    nombre = nombre.replace("subsp.", "").replace("var.", "").replace("f.", "")
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre.strip()

# ============================================================
# BÚSQUEDA INTELIGENTE EN IPNI
# ============================================================

def buscar_ipni(nombre):
    """Busca un nombre científico en IPNI con varios métodos."""

    def consulta(q):
        url = f"https://www.ipni.org/api/1/search?q={q}"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        res = data.get("results", [])
        return res[0]["id"] if res else None

    n1 = normalizar_nombre(nombre)
    id1 = consulta(n1)
    if id1:
        return id1

    partes = n1.split()
    if len(partes) >= 2:
        id2 = consulta(" ".join(partes[:2]))
        if id2:
            return id2

    if len(partes) >= 2:
        id3 = consulta(partes[1])
        if id3:
            return id3

    id4 = consulta(partes[0])
    if id4:
        return id4

    return None

# ============================================================
# EXTRAER FICHA HTML DE IPNI
# ============================================================

def limpiar(e):
    return " ".join(e.get_text(strip=True).split()) if e else ""

def extraer_ipni_html(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    h2 = soup.find("h2")
    nombre_completo = limpiar(h2)

    pub = soup.find("a", class_="publication-link")
    publicacion = limpiar(pub)

    def campo(label):
        dt = soup.find("dt", string=lambda x: x and label in x)
        if dt:
            dd = dt.find_next("dd")
            return limpiar(dd)
        return ""

    lsid = campo("LSID")
    species_name = campo("Species Name")
    collation = campo("Collation")
    family = campo("Family")
    basionym = campo("Basionym")
    same_citation = campo("Same citation")

    wfo = ""
    powo = ""

    for a in soup.find_all("a", class_="external-link"):
        href = a.get("href", "")
        if "worldfloraonline" in href:
            wfo = href
        if "powo.science.kew" in href:
            powo = href

    return {
        "url": url,
        "nombre_completo": nombre_completo,
        "publicacion": publicacion,
        "lsid": lsid,
        "species_name": species_name,
        "collation": collation,
        "family": family,
        "basionym": basionym,
        "same_citation": same_citation,
        "wfo": wfo,
        "powo": powo
    }

# ============================================================
# CONEXIÓN A ACCESS
# ============================================================

conn = pyodbc.connect(
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    rf"DBQ={DATABASE};"
)
cursor = conn.cursor()

cursor.execute(f"SELECT [{CAMPO_NOMBRE}] FROM [{TABLE}]")
registros = cursor.fetchall()

# ============================================================
# CREAR CSV
# ============================================================

with open(CSV_SALIDA, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")

    writer.writerow([
        "Nombre buscado",
        "URL",
        "Nombre completo",
        "Publicación",
        "LSID",
        "Species Name",
        "Collation",
        "Family",
        "Basionym",
        "Same citation as",
        "WFO link",
        "POWO link"
    ])

    for (nombre,) in registros:

        if not nombre:
            continue

        nombre = str(nombre).strip()
        print("Buscando en IPNI:", nombre)

        try:
            id_ipni = buscar_ipni(nombre)

            if not id_ipni:
                print("   No encontrado en IPNI")
                writer.writerow([nombre, "", "", "", "", "", "", "", "", "", "", ""])
                continue

            url_ficha = f"https://www.ipni.org/n/{id_ipni}"
            print("   Ficha:", url_ficha)

            datos = extraer_ipni_html(url_ficha)

            writer.writerow([
                nombre,
                datos["url"],
                datos["nombre_completo"],
                datos["publicacion"],
                datos["lsid"],
                datos["species_name"],
                datos["collation"],
                datos["family"],
                datos["basionym"],
                datos["same_citation"],
                datos["wfo"],
                datos["powo"]
            ])

        except Exception as e:
            print("   ERROR:", e)

        time.sleep(PAUSA)

print("\nProceso terminado.")
print("CSV generado:", CSV_SALIDA)
