"""
taxa_parser.py
==============
Módulo de parseo taxonómico (Botánica, Zoología, Híbridos y Cultivares)
Adaptado directamente de la lógica optimizada en VBA.
"""

import re
import datetime

PART_BOTANICAS = "|subsp.|var.|subvar.|f.|subf.|form.|subform.|"
PARTICULAS_AUTOR = "|de|del|von|van|in|ex|y|et|"
CATS_INFRA = "|subsp.|ssp.|var.|subvar.|f.|fo.|form.|subf.|subfo.|subform.|"

_go_cache = {}

_regex_espacios = re.compile(r"\s+", re.UNICODE)
_regex_epiteto_autor = re.compile(r"([a-z])([A-Z])")
_regex_iniciales_anio = re.compile(
    r"([A-Za-z]\.?[A-Za-z]\.?[A-Za-z]?\.?),([1-2][0-9]{3})"
)
_regex_anio = re.compile(r"([1-2][0-9]{3})")


def limpiar_cache():
    _go_cache.clear()


def get_safe(lista, idx, default=""):
    return lista[idx] if 0 <= idx < len(lista) else default


def limpiar_texto(texto):

    if texto is None:
        return ""

    cad = str(texto)

    espacios_raros = [
        chr(160),
        chr(8194),
        chr(8195),
        chr(8201),
        chr(8202),
        chr(8239),
        chr(12288),
    ]

    for e in espacios_raros:
        cad = cad.replace(e, " ")

    cad = cad.replace(chr(8203), "")
    cad = cad.replace(chr(65279), "")

    cad = _regex_espacios.sub(" ", cad)

    return cad.strip()


def normalizar_nombre(nombre):

    cad = str(nombre).strip()

    cad = cad.replace("(", " (")
    cad = cad.replace(")", ") ")
    cad = cad.replace(",", ", ")

    cats = [
        "subsp.",
        "ssp.",
        "var.",
        "subvar.",
        "f.",
        "fo.",
        "form.",
        "subf.",
        "subfo.",
        "subform."
    ]

    for c in cats:
        cad = cad.replace(c, c + " ")

    cad = _regex_epiteto_autor.sub(r"\1 \2", cad)
    cad = _regex_iniciales_anio.sub(r"\1, \2", cad)

    while "  " in cad:
        cad = cad.replace("  ", " ")

    return cad.strip()


def es_anio(texto):

    if not texto:
        return False

    match = _regex_anio.search(texto)

    if not match:
        return False

    try:
        y = int(match.group(1))
        current_year = datetime.datetime.now().year
        return 1600 <= y <= current_year

    except ValueError:
        return False


def es_zoologico(partes):

    for p in partes:
        if es_anio(p):
            return True

    return False


def obtener_pos_especie(partes):

    if len(partes) < 2:
        return 0

    if partes[1].startswith("(") and partes[1].endswith(")"):
        return 2

    return 1


def es_epiteto(texto):

    if not texto:
        return False

    return "a" <= texto[0] <= "z"


def es_mayuscula(texto):

    if not texto:
        return False

    return "A" <= texto[0] <= "Z"


def es_particula_autor(texto):

    if not texto:
        return False

    return f"|{texto.lower()}|" in PARTICULAS_AUTOR


def es_epiteto_real(texto):

    return es_epiteto(texto) and not es_particula_autor(texto)


def pos_tras_autor_especie(partes, pos, es_zoo):

    i = pos + 1

    while i < len(partes):

        es_part = es_particula_autor(partes[i])

        if es_epiteto(partes[i]) and not es_part:
            break

        if f"|{partes[i].lower()}|" in CATS_INFRA.lower():
            break

        if es_part and i < len(partes) - 1:
            i += 1

        if i >= len(partes):
            break

        if es_zoo and es_anio(partes[i]):
            i += 1
            break

        i += 1

    return i


def obtener_componentes(nombre):

    if nombre is None:
        return "", [], 0, False

    clave = str(nombre)

    if clave in _go_cache:
        return _go_cache[clave]

    cad = normalizar_nombre(limpiar_texto(nombre))

    if not cad:
        resultado = ("", [], 0, False)
        _go_cache[clave] = resultado
        return resultado

    partes = [p for p in cad.split(" ") if p]

    pos = obtener_pos_especie(partes)
    es_zoo = es_zoologico(partes)

    resultado = (cad, partes, pos, es_zoo)

    _go_cache[clave] = resultado

    return resultado


def n_gen(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    return partes[0] if partes else ""


def n_sub_gen(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if len(partes) >= 2:

        if partes[1].startswith("(") and partes[1].endswith(")"):

            subg = partes[1][1:-1]

            if es_mayuscula(subg):
                return subg

    return ""


def n_sp(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    for p in partes[1:]:

        if es_epiteto(p):
            return p

    return ""
def n_cat_infra(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if es_zoo:
        return ""

    if pos + 1 >= len(partes):
        return ""

    siguiente = partes[pos + 1]

    if f"|{siguiente.lower()}|" in PART_BOTANICAS.lower():
        return siguiente

    if es_epiteto_real(siguiente):
        return "subsp."

    return ""


def n_infra(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if not partes:
        return ""

    if es_zoo:

        pos_infra = pos + 1

        if (
            pos + 1 < len(partes)
            and f"|{partes[pos + 1].lower()}|" in CATS_INFRA.lower()
        ):
            pos_infra = pos + 2

        if pos_infra < len(partes) and es_epiteto(partes[pos_infra]):
            return partes[pos_infra]

        return ""

    pos_autor = pos_tras_autor_especie(partes, pos, es_zoo)

    if pos_autor >= len(partes):
        return ""

    siguiente = partes[pos_autor]

    if f"|{siguiente.lower()}|" in CATS_INFRA.lower():

        epi = get_safe(partes, pos_autor + 1)

        if epi and not es_particula_autor(epi):
            return epi

        return ""

    if es_epiteto_real(siguiente):
        return siguiente

    return ""


def n_autor(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    res = []

    i = pos + 1

    while i < len(partes):

        es_part = es_particula_autor(partes[i])

        if es_epiteto(partes[i]) and not es_part:
            break

        if f"|{partes[i].lower()}|" in PART_BOTANICAS.lower():
            break

        res.append(partes[i])

        if es_part and i < len(partes) - 1:
            i += 1
            res.append(partes[i])

        if es_zoo and es_anio(partes[i]):
            break

        i += 1

    return " ".join(res)


def n_autinfra(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if not partes:
        return ""

    if es_zoo:

        if pos + 1 >= len(partes):
            return ""

        infra = partes[pos + 1]

        if not es_epiteto(infra):
            return ""

        res = []
        i = pos + 2

        while i < len(partes):

            res.append(partes[i])

            if partes[i].lower() == "in" and i < len(partes) - 1:
                i += 1
                res.append(partes[i])

            if es_anio(partes[i]):
                break

            i += 1

        return " ".join(res)

    pos_autor = pos_tras_autor_especie(partes, pos, es_zoo)

    pos_infra = -1

    if pos_autor < len(partes):

        if f"|{partes[pos_autor].lower()}|" in CATS_INFRA.lower():

            if pos_autor + 1 < len(partes):
                pos_infra = pos_autor + 1

        elif es_epiteto_real(partes[pos_autor]):
            pos_infra = pos_autor

    if pos_infra == -1:
        return ""

    res = []
    i = pos_infra + 1

    while i < len(partes):

        res.append(partes[i])

        if es_particula_autor(partes[i]) and i < len(partes) - 1:
            i += 1
            res.append(partes[i])

        if es_anio(partes[i]):
            break

        i += 1

    return " ".join(res)


def recortar_nombre_zoologico(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if not partes:
        return ""

    res = [partes[0]]

    if pos < len(partes) and es_epiteto_real(partes[pos]):
        res.append(partes[pos])
    else:
        return " ".join(res)

    if pos + 1 < len(partes) and es_epiteto_real(partes[pos + 1]):
        res.append(partes[pos + 1])

    return " ".join(res)


def rango_taxonomico_simple(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if not cad:
        return ""

    c = cad.lower()

    if "subvar." in c:
        return "subvarietas"

    if "var." in c:
        return "varietas"

    if "subsp." in c:
        return "subspecies"

    pz = recortar_nombre_zoologico(cad).split()

    if len(pz) == 3:
        return "subspecies"

    if len(pz) == 2:
        return "species"

    return ""


def codigo_nombre_cientifico(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if not partes:
        return "Indeterminado"

    if es_zoo:
        return "ICZN"

    if len(partes) >= 3:
        return "ICN"

    return "Indeterminado"


def es_hibrido_generico(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if not cad:
        return False

    if cad.startswith("×"):
        return True

    return (
        len(partes) >= 3
        and partes[1] == "×"
        and es_mayuscula(partes[0])
        and es_mayuscula(partes[2])
    )


def es_hibrido_especifico(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    return (
        len(partes) >= 2
        and (partes[1] == "×" or partes[1].startswith("×"))
    )


def n_hibrido_generico(nombre):

    if not es_hibrido_generico(nombre):
        return ""

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if cad.startswith("×"):
        return cad[1:]

    if len(partes) >= 3 and partes[1] == "×":
        return f"{partes[0]} × {partes[2]}"

    return ""


def n_hibrido_especifico(nombre):

    if not es_hibrido_especifico(nombre):
        return ""

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    if len(partes) >= 3 and partes[1] == "×":
        return partes[2]

    if len(partes) >= 2 and partes[1].startswith("×"):
        return partes[1][1:]

    return ""


def es_cultivar(nombre):

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    return bool(cad and "'" in cad)


def n_cultivar(nombre):

    if not es_cultivar(nombre):
        return ""

    cad, partes, pos, es_zoo = obtener_componentes(nombre)

    ini = cad.find("'")
    fin = cad.rfind("'")

    if ini != -1 and fin > ini:
        return cad[ini + 1:fin]

    return ""