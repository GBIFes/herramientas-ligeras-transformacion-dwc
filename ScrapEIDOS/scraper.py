"""
===============================================================================
scraper.py - Extracción Optimizada y Resiliente de EIDOS (IEPNB)
===============================================================================
"""

import re
import requests
from bs4 import BeautifulSoup
from config import BASE_URL, IDIOMA_PAIS, SEPARADOR_NOMBRES_REGEX, obtener_url_y_id_por_busqueda_texto, crear_sesion_robusta

def extraer_tabla_por_seccion_o_id(soup, posibles_ids, cabeceras_por_defecto):
    """
    Busca una tabla estrictamente dentro de los identificadores o clases permitidas 
    para esa sección específica, evitando mezclar tablas de otras pestañas (como Atributos de la Especie).
    """
    tab = None
    # Buscar estrictamente por ID o clase específica de la pestaña
    for pid in posibles_ids:
        tab = soup.find("div", id=pid) or soup.find("div", class_=pid) or soup.find("section", id=pid) or soup.find("section", class_=pid)
        if tab:
            break

    # Si no se encuentra el contenedor específico de la pestaña, retornamos vacío para no mezclar otras tablas
    if not tab:
        return cabeceras_por_defecto, []

    tabla = tab.find("table") if tab and tab.name != "table" else tab
    if not tabla:
        return cabeceras_por_defecto, []

    cabeceras = []
    filas_datos = []

    th_elems = tabla.find_all("th")
    if th_elems:
        cabeceras = [c.get_text(" ", strip=True) for c in th_elems]

    for fila in tabla.find_all("tr"):
        celdas = fila.find_all(["th", "td"])
        if not celdas:
            continue
        
        textos = []
        for c in celdas:
            for br in c.find_all(["br", "p"]):
                br.replace_with(" ")
            textos.append(c.get_text(" ", strip=True))

        if not cabeceras and any(any(def_col.lower() in t.lower() for def_col in cabeceras_por_defecto) for t in textos):
            cabeceras = textos
            continue

        if cabeceras and [t.lower() for t in textos] == [t.lower() for t in cabeceras]:
            continue

        if any(t for t in textos):
            filas_datos.append(textos)

    if not cabeceras or len(cabeceras) != (len(filas_datos[0]) if filas_datos else len(cabeceras)):
        cabeceras = cabeceras_por_defecto

    return cabeceras, filas_datos

def extraer_ficha_completa(session, url, eidos_id):
    try:
        resp = session.get(url, timeout=25)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    info_dict = {
        "EIDOS_ID": eidos_id,
        "Ambito": "", "Origen": "", "Identificador": "", "Grupo_Taxonomico": "",
        "Reino": "", "Division_o_Filo": "", "Clase": "",
        "Orden": "", "Familia": "", "Genero": "", "Especie": "", "Autor": ""
    }

    texto_total_pagina = soup.get_text(" ", strip=True)

    for elem in soup.find_all(["p", "div", "li", "span", "strong", "td", "b"]):
        texto = elem.get_text(" ", strip=True)
        if ":" in texto:
            partes = texto.split(":", 1)
            k_raw = partes[0].strip().lower()
            v_val = partes[1].strip()

            if not v_val or len(v_val) > 200:
                continue

            if ("ambito" in k_raw or "ámbito" in k_raw) and not info_dict["Ambito"]:
                info_dict["Ambito"] = v_val
            elif "origen" in k_raw and not info_dict["Origen"]:
                info_dict["Origen"] = v_val
            elif "identificador" in k_raw and not info_dict["Identificador"]:
                info_dict["Identificador"] = v_val
            elif "grupo" in k_raw and "taxon" in k_raw and not info_dict["Grupo_Taxonomico"]:
                if len(v_val.split()) <= 4:
                    info_dict["Grupo_Taxonomico"] = v_val
            elif "reino" in k_raw and not info_dict["Reino"]:
                info_dict["Reino"] = v_val
            elif ("division" in k_raw or "filo" in k_raw or "división" in k_raw) and not info_dict["Division_o_Filo"]:
                info_dict["Division_o_Filo"] = v_val
            elif "clase" in k_raw and not info_dict["Clase"]:
                info_dict["Clase"] = v_val
            elif "orden" in k_raw and not info_dict["Orden"]:
                info_dict["Orden"] = v_val
            elif "familia" in k_raw and not info_dict["Familia"]:
                info_dict["Familia"] = v_val
            elif ("genero" in k_raw or "género" in k_raw) and not info_dict["Genero"]:
                info_dict["Genero"] = v_val
            elif "especie" in k_raw and not info_dict["Especie"]:
                tokens = v_val.split()
                if len(tokens) > 3:
                    especie_limpia = " ".join(tokens[3:])
                else:
                    especie_limpia = v_val
                info_dict["Especie"] = especie_limpia
            elif "autor" in k_raw and not info_dict["Autor"]:
                info_dict["Autor"] = v_val

    if info_dict["Especie"] and info_dict["Autor"]:
        if info_dict["Especie"].endswith(info_dict["Autor"]):
            info_dict["Especie"] = info_dict["Especie"][:-len(info_dict["Autor"])].strip()

    if not info_dict["Ambito"]:
        m = re.search(r'(?:Ámbito|Ambito)\s*[:]\s*([^\|\n\r]+)', texto_total_pagina, re.IGNORECASE)
        if m: info_dict["Ambito"] = m.group(1).strip().split()[0] if " " in m.group(1) else m.group(1).strip()

    if not info_dict["Origen"]:
        m = re.search(r'Origen\s*[:]\s*([^\|\n\r]+)', texto_total_pagina, re.IGNORECASE)
        if m: info_dict["Origen"] = m.group(1).strip().split()[0]

    if not info_dict["Identificador"]:
        m = re.search(r'Identificador\s*[:]\s*([^\|\n\r]+)', texto_total_pagina, re.IGNORECASE)
        if m: info_dict["Identificador"] = m.group(1).strip().split()[0]

    if not info_dict["Grupo_Taxonomico"]:
        for grupo_comun in ["Invertebrados", "Vertebrados", "Plantas", "Hongos", "Aves", "Mamíferos", "Reptiles", "Anfibios", "Peces"]:
            if grupo_comun.lower() in texto_total_pagina.lower():
                info_dict["Grupo_Taxonomico"] = grupo_comun
                break

    # 1. Nombres Comunes
    _, nom_brutos = extraer_tabla_por_seccion_o_id(soup, ["nomcomunes", "nombres", "comunes"], ["Idioma", "Nombre"])
    nombres_comunes = []
    for fila in nom_brutos:
        if len(fila) >= 2:
            idioma, nombre = fila[0], fila[1]
            for n_ind in SEPARADOR_NOMBRES_REGEX.split(nombre):
                n_ind_clean = n_ind.strip(" ,;")
                if n_ind_clean:
                    pais = IDIOMA_PAIS.get(idioma, "")
                    nombres_comunes.append([eidos_id, idioma, pais, n_ind_clean])

    # 2. Estado de Conservación
    h_cons, cons_bruto = extraer_tabla_por_seccion_o_id(soup, ["estado-conservacion", "conservacion", "conservation"], ["Autoridad", "Aplicación", "Conservación", "Año", "Criterios"])
    conservacion_filas = [[eidos_id] + fila for fila in cons_bruto]
    headers_cons_full = ["EIDOS_ID"] + h_cons

    # 3. Colecciones / Catálogos
    h_col, col_bruto = extraer_tabla_por_seccion_o_id(soup, ["taxonomia", "colecciones", "coleccion", "catalogos", "catálogos"], ["Colección", "Nombre"])
    colecciones_filas = [[eidos_id] + fila for fila in col_bruto]
    headers_col_full = ["EIDOS_ID"] + h_col

    # 4. Estado Legal
    h_legal, legal_bruto = extraer_tabla_por_seccion_o_id(soup, ["norma", "legal", "estado-legal", "normativa"], ["Estado", "Colecciones", "Norma", "Ámbito"])
    estado_legal_filas = [[eidos_id] + fila for fila in legal_bruto]
    headers_legal_full = ["EIDOS_ID"] + h_legal

    # 5. Bibliografía
    h_bib, bib_bruto = extraer_tabla_por_seccion_o_id(soup, ["biblio", "bibliografia", "referencias"], ["id", "Referencia", "Direcciones"])
    bibliografia_filas = [[eidos_id] + fila for fila in bib_bruto]
    headers_bib_full = ["EIDOS_ID"] + h_bib

    # 6. Sinonimia
    sinonimia = []
    div_sinonimos = soup.find("div", id="sinonimos") or soup.find("div", id="sinonimia") or soup.find("div", class_="wrapper-sinonimo")
    if not div_sinonimos:
        for d in soup.find_all(["div", "section"]):
            if d.find(["h2", "h3", "h4"]) and "sinonim" in d.find(["h2", "h3", "h4"]).get_text(strip=True).lower():
                div_sinonimos = d
                break

    if div_sinonimos:
        elementos_sin = div_sinonimos.find_all("li") or div_sinonimos.find_all("a")
        for el in elementos_sin:
            a_tag = el if el.name == "a" else el.find("a", href=True)
            if a_tag:
                href = a_tag['href']
                nombre_sin = a_tag.get_text(" ", strip=True)
                sin_id = re.search(r'/eidos/(\d+)', href).group(1) if "/eidos/" in href else obtener_url_y_id_por_busqueda_texto(session, nombre_sin)[1]
            else:
                nombre_sin = el.get_text(" ", strip=True)
                sin_id = ""
                if nombre_sin and not nombre_sin.lower().startswith("sinonim"):
                    sin_id = obtener_url_y_id_por_busqueda_texto(session, nombre_sin)[1]

            if nombre_sin and not nombre_sin.lower().startswith("sinonim"):
                registro_sin = [eidos_id, sin_id, nombre_sin]
                if registro_sin not in sinonimia:
                    sinonimia.append(registro_sin)

    return {
        "info": info_dict,
        "nombres": nombres_comunes,
        "conservacion": conservacion_filas,
        "headers_cons": headers_cons_full,
        "colecciones": colecciones_filas,
        "headers_col": headers_col_full,
        "legal": estado_legal_filas,
        "headers_legal": headers_legal_full,
        "bibliografia": bibliografia_filas,
        "headers_bib": headers_bib_full,
        "sinonimia": sinonimia
    }

def procesar_fila(row, col_busqueda, tipo_busqueda):
    session = crear_sesion_robusta()
    
    val_columna = str(row.get(col_busqueda, "")).strip()
    if not val_columna:
        return None, ""

    ficha_url = None
    eidos_id_reg = ""
    scientific_name_reg = str(row.get("scientificName", "")) if "scientificName" in row else ""

    if tipo_busqueda == "id":
        eidos_id_reg = val_columna
        ficha_url = f"{BASE_URL}/{eidos_id_reg}"
    else:
        scientific_name_reg = val_columna
        ficha_url, eidos_id_reg = obtener_url_y_id_por_busqueda_texto(session, val_columna)

    if not eidos_id_reg and ficha_url:
        match = re.search(r'/eidos/(\d+)', ficha_url)
        if match:
            eidos_id_reg = match.group(1)

    if not ficha_url:
        return None, eidos_id_reg

    datos_ficha = extraer_ficha_completa(session, ficha_url, eidos_id_reg)
    if not datos_ficha:
        return None, eidos_id_reg

    resultados_nombres = [[item[0], scientific_name_reg, item[1], item[2], item[3]] for item in datos_ficha["nombres"]]
    datos_ficha["nombres"] = resultados_nombres
    return datos_ficha, eidos_id_reg