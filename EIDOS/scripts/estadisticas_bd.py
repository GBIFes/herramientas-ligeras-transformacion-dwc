"""
estadisticas_bd.py

Muestra estadísticas de la base de datos
especies_legales.sqlite

Autor: Javier Estrada
"""

from pathlib import Path
import sqlite3


# ==========================================================
# Rutas
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DB = BASE_DIR / "data" / "especies_legales.sqlite"

print("\nBase de datos:")
print(DB)

if not DB.exists():
    print("\nERROR: La base de datos no existe.")
    exit()


# ==========================================================
# Conexión
# ==========================================================

conn = sqlite3.connect(DB)
cur = conn.cursor()


# ==========================================================
# Comprobar tabla
# ==========================================================

cur.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
  AND name='especies'
""")

if cur.fetchone() is None:
    print("\nERROR: La tabla 'especies' no existe.")
    conn.close()
    exit()


# ==========================================================
# Estadísticas generales
# ==========================================================

cur.execute("""
SELECT COUNT(*)
FROM especies
""")

total = cur.fetchone()[0]


cur.execute("""
SELECT COUNT(*)
FROM especies
WHERE es_no_nativa = 1
""")

no_nativas = cur.fetchone()[0]


cur.execute("""
SELECT COUNT(*)
FROM especies
WHERE es_cites = 1
""")

cites = cur.fetchone()[0]


cur.execute("""
SELECT COUNT(*)
FROM especies
WHERE es_euring = 1
""")

euring = cur.fetchone()[0]


cur.execute("""
SELECT COUNT(*)
FROM especies
WHERE es_red_natura = 1
""")

red_natura = cur.fetchone()[0]


# ==========================================================
# Mostrar resultados
# ==========================================================

print("\n" + "=" * 50)
print("ESTADÍSTICAS DE LA BASE DE DATOS")
print("=" * 50)

print(f"\nTotal especies     : {total:,}")
print(f"No nativas         : {no_nativas:,}")
print(f"CITES              : {cites:,}")
print(f"EURING             : {euring:,}")
print(f"Red Natura 2000    : {red_natura:,}")

print("\nPorcentaje sobre el total:")

print(f"No nativas         : {(no_nativas/total)*100:.2f}%")
print(f"CITES              : {(cites/total)*100:.2f}%")
print(f"EURING             : {(euring/total)*100:.2f}%")
print(f"Red Natura 2000    : {(red_natura/total)*100:.2f}%")

conn.close()

print("\nProceso finalizado.")