"""
Script para verificar la correspondencia entre el nombre científico almacenado en la
tabla LESRP (campo NombreActualizado) y el nombre científico publicado en cada ficha
EIDOS (campo taxonID con URL).

FUNCIONAMIENTO:
1. Conecta a la base de datos Access (.accdb) mediante pyodbc.
2. Lee cada registro de la tabla LESRP obteniendo:
      - ID (clave primaria)
      - taxonID (URL de la ficha EIDOS)
      - NombreActualizado (nombre científico local)
3. Para cada URL:
      - Descarga la página HTML con requests.
      - Extrae el nombre científico buscando encabezados <h1>/<h2> o líneas de texto
        que cumplan el patrón típico de un nombre científico (dos palabras, sin
        etiquetas HTML ni caracteres de control).
4. Compara el nombre extraído con NombreActualizado (comparación case‑insensitive).
5. Si coinciden, asigna 1; si no coinciden o no se pudo extraer, asigna 0.
6. Actualiza el campo NombreCorresponde en la tabla LESRP para cada registro.
7. Cierra la conexión y muestra un mensaje de finalización.

Este script permite validar automáticamente la coherencia taxonómica entre la base
local y las fichas EIDOS sin intervención manual.
"""

import pyodbc
import requests
from bs4 import BeautifulSoup

DB_PATH = r"C:\Users\Javier Estrada\Documents\Database2.accdb"

def obtener_nombre_eidos(url: str) -> str:
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return ""

        soup = BeautifulSoup(r.text, "html.parser")

        # Buscar encabezados que contienen el nombre científico
        for tag in soup.find_all(["h1", "h2"]):
            texto = tag.get_text(strip=True)
            if " " in texto and ":" not in texto and len(texto) > 4:
                return texto

        # Buscar líneas de texto que parezcan nombre científico
        for line in r.text.split("\n"):
            line = line.strip()
            if " " in line and "<" not in line and ":" not in line and len(line) > 4:
                return line

        return ""
    except Exception:
        return ""

def main():
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        rf"DBQ={DB_PATH};"
    )
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()

    cur.execute("SELECT ID, taxonID, NombreActualizado FROM LESRP")
    rows = cur.fetchall()

    for pk, taxonID, nombre_actualizado in rows:
        if not taxonID:
            continue

        url = str(taxonID).strip()
        nombre_tabla = (str(nombre_actualizado) if nombre_actualizado else "").strip()

        nombre_eidos = obtener_nombre_eidos(url)

        corresponde = 1 if nombre_eidos.lower() == nombre_tabla.lower() and nombre_eidos != "" else 0

        cur.execute(
            "UPDATE LESRP SET NombreCorresponde = ? WHERE ID = ?",
            corresponde,
            pk
        )

    conn.commit()
    conn.close()
    print("Actualización completada.")

if __name__ == "__main__":
    main()
