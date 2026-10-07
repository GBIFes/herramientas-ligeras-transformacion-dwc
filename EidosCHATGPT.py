"""
MÓDULO: Verificación automática de coherencia taxonómica entre Access y fichas EIDOS

Este script realiza una revisión sistemática de los nombres científicos almacenados en la
base de datos Access (tabla LESRP) comparándolos con los nombres publicados en las fichas
EIDOS accesibles mediante las URLs contenidas en el campo taxonID.

FUNCIONAMIENTO GENERAL:
1. Conexión a la base de datos Access (.accdb) mediante pyodbc.
2. Lectura de todos los registros de la tabla LESRP, obteniendo:
      - NombreActualizado (nombre científico local)
      - taxonID (hipervínculo o URL hacia la ficha EIDOS)
3. Normalización del campo taxonID:
      - Extracción robusta de la URL real incluso si Access la almacena como hipervínculo
        con formato “Texto#URL#”.
4. Descarga de cada página EIDOS:
      - Solicitud HTTP con User-Agent realista y timeout configurable.
      - Detección de codificación y parseo HTML con BeautifulSoup.
      - Extracción estricta del nombre científico desde el primer <h1><span> de la página.
5. Normalización de nombres:
      - Eliminación de espacios redundantes, corrección de separadores y casefold para
        comparación insensible a mayúsculas/minúsculas.
6. Comparación:
      - Si el nombre normalizado de Access coincide con el de la web → resultado = 1.
      - Si difiere → resultado = 0.
      - Si la página no puede abrirse o no contiene el <h1><span> esperado → se registra
        como ERROR pero **no** se asigna 0 (para evitar falsos negativos por fallos de red).
7. Escritura del resultado en Access:
      - Actualización del campo NombreCorresponde para cada registro.
8. Generación de un archivo de log detallado:
      - Incluye número de registro, nombre Access, nombre web, resultado, URL y observación.
9. Resumen final:
      - Totales de coincidencias, no coincidencias, errores, registros sin nombre y sin URL.

Este script permite validar de forma automatizada la coherencia taxonómica entre la base
local y las fichas EIDOS, generando además un log exhaustivo para auditoría y depuración.
"""

import pyodbc
import requests
from bs4 import BeautifulSoup
import re
import time


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Ruta de la base de datos Access
DATABASE = r"C:\Users\Javier Estrada\Documents\Database2.accdb"

# Tabla de Access
TABLE = "LESRP"

# Campos de la tabla
CAMPO_NOMBRE = "NombreActualizado"
CAMPO_TAXON = "taxonID"
CAMPO_RESULTADO = "NombreCorresponde"

# Tiempo máximo para esperar una página web
TIMEOUT = 30

# Pausa entre páginas
PAUSA = 0.5

# Identificación del navegador
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36"
)


# ============================================================
# FUNCIÓN PARA EXTRAER LA URL DE taxonID
# ============================================================

def extraer_url(valor):

    if valor is None:
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    # Access puede guardar los hipervínculos así:
    #
    # Texto#https://www.ejemplo.com/pagina#
    #
    # Buscamos la parte que empieza por http:// o https://

    partes = valor.split("#")

    for parte in partes:

        parte = parte.strip()

        if parte.startswith("https://"):
            return parte

        if parte.startswith("http://"):
            return parte

    # Por si el campo ya contiene directamente la URL

    if valor.startswith("https://"):
        return valor

    if valor.startswith("http://"):
        return valor

    return None


# ============================================================
# FUNCIÓN PARA OBTENER EL NOMBRE DEL H1
# ============================================================

def obtener_nombre_web(url):

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }

    # Abrir página
    respuesta = requests.get(
        url,
        headers=headers,
        timeout=TIMEOUT
    )

    # Comprobar que la página respondió correctamente
    respuesta.raise_for_status()

    # Detectar codificación
    if respuesta.apparent_encoding:
        respuesta.encoding = respuesta.apparent_encoding

    # Analizar HTML
    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    # --------------------------------------------------------
    # BUSCAR EL H1
    # --------------------------------------------------------

    h1 = soup.find("h1")

    if h1 is None:
        raise Exception(
            "No se encontró ningún <h1> en la página"
        )

    # --------------------------------------------------------
    # BUSCAR EL PRIMER SPAN DEL H1
    # --------------------------------------------------------

    primer_span = h1.find("span")

    if primer_span is None:
        raise Exception(
            "El <h1> no contiene ningún <span>"
        )

    # --------------------------------------------------------
    # EXTRAER EL TEXTO
    # --------------------------------------------------------

    nombre = primer_span.get_text(
        " ",
        strip=True
    )

    # Eliminar espacios repetidos
    nombre = re.sub(
        r"\s+",
        " ",
        nombre
    ).strip()

    if not nombre:
        raise Exception(
            "El primer <span> del <h1> está vacío"
        )

    return nombre


# ============================================================
# FUNCIÓN PARA NORMALIZAR LOS NOMBRES
# ============================================================

def normalizar_nombre(nombre):

    if nombre is None:
        return ""

    # Convertir a texto
    nombre = str(nombre)

    # Quitar espacios al principio y final
    nombre = nombre.strip()

    # Convertir varios espacios en uno
    nombre = re.sub(
        r"\s+",
        " ",
        nombre
    )

    # Quitar espacios antes de puntos y comas
    nombre = re.sub(
        r"\s+([.,;:)])",
        r"\1",
        nombre
    )

    # No distinguir mayúsculas/minúsculas
    nombre = nombre.casefold()

    return nombre


# ============================================================
# FUNCIÓN PARA ACTUALIZAR NombreCorresponde
# ============================================================

def actualizar_resultado(
    cursor,
    nombre,
    taxon,
    resultado
):

    sql = f"""
        UPDATE [{TABLE}]
        SET [{CAMPO_RESULTADO}] = ?
        WHERE [{CAMPO_NOMBRE}] = ?
          AND [{CAMPO_TAXON}] = ?
    """

    cursor.execute(
        sql,
        resultado,
        nombre,
        taxon
    )


# ============================================================
# INICIO
# ============================================================

print()
print("=" * 75)
print("COMPROBACIÓN DE NOMBRES CIENTÍFICOS")
print("=" * 75)
print()

print("Base de datos:")
print(DATABASE)
print()

print("Tabla:")
print(TABLE)
print()

print("Conectando con Access...")


# ============================================================
# CONEXIÓN CON ACCESS
# ============================================================

try:

    connection_string = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        rf"DBQ={DATABASE};"
    )

    conn = pyodbc.connect(
        connection_string
    )

    cursor = conn.cursor()

except Exception as e:

    print()
    print("ERROR: No se pudo conectar con Access.")
    print()
    print(e)
    print()

    print(
        "Comprueba que está instalado el controlador:"
    )

    print(
        "Microsoft Access Driver (*.mdb, *.accdb)"
    )

    input("\nPulsa ENTER para cerrar...")

    raise SystemExit


print("Conexión correcta.")
print()


# ============================================================
# COMPROBAR TABLA
# ============================================================

try:

    cursor.execute(
        f"SELECT COUNT(*) FROM [{TABLE}]"
    )

    total = cursor.fetchone()[0]

except Exception as e:

    print()
    print("ERROR al acceder a la tabla LESRP.")
    print()
    print(e)

    cursor.close()
    conn.close()

    input("\nPulsa ENTER para cerrar...")

    raise SystemExit


print(
    f"Registros encontrados: {total}"
)

print()


# ============================================================
# LEER LOS REGISTROS
# ============================================================

sql = f"""
    SELECT
        [{CAMPO_NOMBRE}],
        [{CAMPO_TAXON}]
    FROM [{TABLE}]
"""

try:

    cursor.execute(sql)

    registros = cursor.fetchall()

except Exception as e:

    print()
    print("ERROR al leer los registros.")
    print()
    print(e)

    cursor.close()
    conn.close()

    input("\nPulsa ENTER para cerrar...")

    raise SystemExit


# ============================================================
# CREAR ARCHIVO DE RESULTADOS
# ============================================================

LOG_FILE = "resultado_revision_taxonomia.txt"

log = open(
    LOG_FILE,
    "w",
    encoding="utf-8"
)

log.write(
    "REVISION DE NOMBRES CIENTIFICOS\n"
)

log.write(
    "=" * 120 + "\n"
)

log.write(
    "Nº\tNombre Access\tNombre Web\tResultado\tURL\tObservación\n"
)

log.write(
    "-" * 120 + "\n"
)


# ============================================================
# CONTADORES
# ============================================================

coinciden = 0
no_coinciden = 0
errores = 0
sin_nombre = 0
sin_url = 0


# ============================================================
# RECORRER LA TABLA
# ============================================================

for numero, registro in enumerate(
    registros,
    start=1
):

    nombre_access = registro[0]
    taxon = registro[1]

    print()
    print(
        f"[{numero}/{total}] {nombre_access}"
    )

    # --------------------------------------------------------
    # COMPROBAR QUE HAY NOMBRE
    # --------------------------------------------------------

    if (
        nombre_access is None
        or
        not str(nombre_access).strip()
    ):

        print(
            "    ERROR: NombreActualizado vacío"
        )

        sin_nombre += 1

        log.write(
            f"{numero}\t\t\t0\t\t"
            f"NombreActualizado vacío\n"
        )

        continue


    # --------------------------------------------------------
    # EXTRAER URL
    # --------------------------------------------------------

    url = extraer_url(taxon)

    if not url:

        print(
            "    ERROR: No se encontró URL en taxonID"
        )

        sin_url += 1

        # Ponemos 0 porque no existe una página
        try:

            actualizar_resultado(
                cursor,
                nombre_access,
                taxon,
                0
            )

            conn.commit()

        except Exception as e:

            print(
                "    Error actualizando Access:"
            )

            print(
                f"    {e}"
            )

        log.write(
            f"{numero}\t"
            f"{nombre_access}\t"
            f"\t"
            f"0\t"
            f"\t"
            f"No se encontró URL\n"
        )

        continue


    # --------------------------------------------------------
    # MOSTRAR URL
    # --------------------------------------------------------

    print(
        f"    URL: {url}"
    )


    # --------------------------------------------------------
    # ABRIR LA PÁGINA
    # --------------------------------------------------------

    try:

        nombre_web = obtener_nombre_web(
            url
        )

        print(
            f"    Nombre encontrado en web: "
            f"{nombre_web}"
        )

    except Exception as e:

        errores += 1

        print(
            "    ERROR al abrir/comprobar la página:"
        )

        print(
            f"    {e}"
        )

        # IMPORTANTE:
        # Si la página no se puede abrir,
        # NO escribimos 0.
        #
        # Un error de Internet no significa
        # que el nombre sea incorrecto.

        log.write(
            f"{numero}\t"
            f"{nombre_access}\t"
            f"\t"
            f"ERROR\t"
            f"{url}\t"
            f"{e}\n"
        )

        time.sleep(PAUSA)

        continue


    # --------------------------------------------------------
    # NORMALIZAR
    # --------------------------------------------------------

    nombre_access_normalizado = normalizar_nombre(
        nombre_access
    )

    nombre_web_normalizado = normalizar_nombre(
        nombre_web
    )


    # --------------------------------------------------------
    # COMPARAR
    # --------------------------------------------------------

    if (
        nombre_access_normalizado
        ==
        nombre_web_normalizado
    ):

        resultado = 1

        coinciden += 1

        observacion = "COINCIDE"

        print(
            "    >>> COINCIDE <<<"
        )

    else:

        resultado = 0

        no_coinciden += 1

        observacion = "NO COINCIDE"

        print(
            "    >>> NO COINCIDE <<<"
        )

        print(
            f"    Access : {nombre_access}"
        )

        print(
            f"    Web    : {nombre_web}"
        )


    # --------------------------------------------------------
    # ESCRIBIR RESULTADO EN ACCESS
    # --------------------------------------------------------

    try:

        actualizar_resultado(
            cursor,
            nombre_access,
            taxon,
            resultado
        )

        # Guardar inmediatamente
        conn.commit()

    except Exception as e:

        errores += 1

        print(
            "    ERROR actualizando Access:"
        )

        print(
            f"    {e}"
        )

        log.write(
            f"{numero}\t"
            f"{nombre_access}\t"
            f"{nombre_web}\t"
            f"ERROR\t"
            f"{url}\t"
            f"Error Access: {e}\n"
        )

        continue


    # --------------------------------------------------------
    # GUARDAR EN EL ARCHIVO LOG
    # --------------------------------------------------------

    log.write(
        f"{numero}\t"
        f"{nombre_access}\t"
        f"{nombre_web}\t"
        f"{resultado}\t"
        f"{url}\t"
        f"{observacion}\n"
    )


    # --------------------------------------------------------
    # PAUSA
    # --------------------------------------------------------

    time.sleep(PAUSA)


# ============================================================
# CERRAR ARCHIVO
# ============================================================

log.close()


# ============================================================
# CERRAR ACCESS
# ============================================================

cursor.close()
conn.close()


# ============================================================
# RESUMEN FINAL
# ============================================================

print()
print()
print("=" * 75)
print("PROCESO TERMINADO")
print("=" * 75)
print()

print(
    f"Total de registros:       {total}"
)

print(
    f"Coinciden (1):            {coinciden}"
)

print(
    f"No coinciden (0):         {no_coinciden}"
)

print(
    f"Sin nombre:               {sin_nombre}"
)

print(
    f"Sin URL:                  {sin_url}"
)

print(
    f"Errores:                  {errores}"
)

print()
print(
    "Archivo de resultados:"
)

print(
    LOG_FILE
)

print()
print(
    "La base de datos ha sido actualizada."
)

print()

input(
    "Pulsa ENTER para cerrar..."
)
