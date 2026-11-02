"""
dwc_manager.py
==============
Gestor centralizado de metadatos Darwin Core, verificación del archivo JSON,
antigüedad y sincronización con el estándar oficial.
"""

import os
import json
import time
from tkinter import messagebox

DICTIONARY_FILENAME = "dwc_dictionary.json"

DEFAULT_DWC_DATABASE = {
  "Cores": {
    "Occurrence": {
      "description": "Datos de ocurrencias de especímenes, fósiles u observaciones en la naturaleza.",
      "id_column_default": "occurrenceID",
      "terms": {
        "occurrenceID": { "label": "occurrenceID", "definition": "Identificador único de la ocurrencia.", "example": "urn:catalog:MNHN:Bird:12345" },
        "basisOfRecord": { "label": "basisOfRecord", "definition": "Tipo de evidencia subyacente al registro.", "example": "HumanObservation" },
        "recordedBy": { "label": "recordedBy", "definition": "Persona(s) que colectaron u observaron el registro.", "example": "Jane Doe" },
        "individualCount": { "label": "individualCount", "definition": "Número de individuos presentes en la ocurrencia.", "example": "1" },
        "sex": { "label": "sex", "definition": "Sexo biológico del organismo registrado.", "example": "Male" },
        "lifeStage": { "label": "lifeStage", "definition": "Estadio de vida o madurez del organismo.", "example": "Adult" },
        "establishmentMeans": { "label": "establishmentMeans", "definition": "Estatus de establecimiento (native, introduced, etc.).", "example": "native" },
        "occurrenceStatus": { "label": "occurrenceStatus", "definition": "Presencia o ausencia del organismo (present, absent).", "example": "present" },
        "scientificName": { "label": "scientificName", "definition": "Nombre científico completo.", "example": "Panthera onca" },
        "decimalLatitude": { "label": "decimalLatitude", "definition": "Latitud geográfica en sistema decimal WGS84.", "example": "19.4326" },
        "decimalLongitude": { "label": "decimalLongitude", "definition": "Longitud geográfica en sistema decimal WGS84.", "example": "-99.1332" },
        "eventDate": { "label": "eventDate", "definition": "Fecha o intervalo en que ocurrió el registro.", "example": "2026-06-15" }
      }
    },
    "Taxon": {
      "description": "Listas de chequeo taxonómicas y clasificación sistemática de especies.",
      "id_column_default": "taxonID",
      "terms": {
        "taxonID": { "label": "taxonID", "definition": "Identificador único del taxón.", "example": "urn:lsid:ipni.org:names:320035-2:1" },
        "scientificName": { "label": "scientificName", "definition": "Nombre científico con autoría.", "example": "Quercus robur L." },
        "acceptedNameUsage": { "label": "acceptedNameUsage", "definition": "Nombre aceptado si este registro es sinónimo.", "example": "Quercus alba" },
        "parentNameUsage": { "label": "parentNameUsage", "definition": "Nombre del taxón superior inmediato.", "example": "Quercus" },
        "taxonomicStatus": { "label": "taxonomicStatus", "definition": "Estatus taxonómico (accepted, synonym).", "example": "accepted" },
        "taxonRank": { "label": "taxonRank", "definition": "Rango taxonómico (species, genus, family).", "example": "species" },
        "kingdom": { "label": "kingdom", "definition": "Reino taxonómico.", "example": "Plantae" },
        "phylum": { "label": "phylum", "definition": "Filo o división.", "example": "Tracheophyta" },
        "class": { "label": "class", "definition": "Clase.", "example": "Magnoliopsida" },
        "order": { "label": "order", "definition": "Orden.", "example": "Fagales" },
        "family": { "label": "family", "definition": "Familia.", "example": "Fagaceae" },
        "genus": { "label": "genus", "definition": "Género.", "example": "Quercus" },
        "scientificNameAuthorship": { "label": "scientificNameAuthorship", "definition": "Autoría del nombre científico.", "example": "L." }
      }
    },
    "Event": {
      "description": "Eventos de muestreo, expediciones ecológicas o estaciones de monitoreo.",
      "id_column_default": "eventID",
      "terms": {
        "eventID": { "label": "eventID", "definition": "Identificador único del evento de muestreo.", "example": "EV-2026-01" },
        "parentEventID": { "label": "parentEventID", "definition": "ID del evento contenedor superior en jerarquías.", "example": "EV-2026" },
        "fieldNumber": { "label": "fieldNumber", "definition": "Número de campo de la expedición.", "example": "COL-456" },
        "eventDate": { "label": "eventDate", "definition": "Fecha del evento.", "example": "2026-03-10" },
        "samplingProtocol": { "label": "samplingProtocol", "definition": "Método o protocolo de muestreo empleado.", "example": "Transecto de 100m" },
        "habitat": { "label": "habitat", "definition": "Descripción textual del hábitat.", "example": "Selva baja caducifolia" },
        "decimalLatitude": { "label": "decimalLatitude", "definition": "Latitud central del evento.", "example": "18.5" },
        "decimalLongitude": { "label": "decimalLongitude", "definition": "Longitud central del evento.", "example": "-88.3" }
      }
    },
    "MaterialSample": {
      "description": "Muestras físicas de colección (tejidos, ADN, muestras de suelo, viales).",
      "id_column_default": "materialSampleID",
      "terms": {
        "materialSampleID": { "label": "materialSampleID", "definition": "ID único de la muestra de material.", "example": "MS-DNA-001" },
        "institutionCode": { "label": "institutionCode", "definition": "Código de la institución.", "example": "IBUNAM" },
        "collectionCode": { "label": "collectionCode", "definition": "Código de la colección.", "example": "CNIN" },
        "catalogNumber": { "label": "catalogNumber", "definition": "Número de catálogo en la colección.", "example": "123456" }
      }
    }
  },
  "Extensions": {
    "EMoF": {
      "description": "MeasurementOrFact: Mediciones, rasgos fenotípicos, variables ambientales o hechos cuantitativos.",
      "fk_column_default": "coreID",
      "self_id_default": "measurementID",
      "self_parent_default": "parentMeasurementID",
      "terms": {
        "measurementID": { "label": "measurementID", "definition": "ID único de la medida.", "example": "m-01" },
        "coreID": { "label": "coreID", "definition": "Clave foránea hacia el registro Core.", "example": "occ-123" },
        "parentMeasurementID": { "label": "parentMeasurementID", "definition": "ID de la medida padre para jerarquías (subtablas).", "example": "m-00" },
        "measurementType": { "label": "measurementType", "definition": "Variable o rasgo medido.", "example": "Leaf area" },
        "measurementValue": { "label": "measurementValue", "definition": "Valor de la medición.", "example": "12.5" },
        "measurementUnit": { "label": "measurementUnit", "definition": "Unidad de medida estándar.", "example": "cm2" },
        "measurementAccuracy": { "label": "measurementAccuracy", "definition": "Precisión del instrumento de medición.", "example": "0.1" },
        "measurementDeterminedBy": { "label": "measurementDeterminedBy", "definition": "Persona u organización que midió.", "example": "Dr. Smith" },
        "measurementMethod": { "label": "measurementMethod", "definition": "Método o protocolo analítico.", "example": "Digital scanner" },
        "measurementRemarks": { "label": "measurementRemarks", "definition": "Notas o comentarios adicionales.", "example": "Hoja sana sin daños" }
      }
    },
    "Distribution": {
      "description": "Species Distribution: Estatus geográfico, amenazas, estatus de invasión y regiones.",
      "fk_column_default": "coreID",
      "self_id_default": "distributionID",
      "self_parent_default": "",
      "terms": {
        "distributionID": { "label": "distributionID", "definition": "ID único del registro de distribución.", "example": "dist-01" },
        "coreID": { "label": "coreID", "definition": "Clave foránea hacia el taxón Core.", "example": "taxon-456" },
        "locality": { "label": "locality", "definition": "Nombre de la localidad geográfica.", "example": "Sierra Madre del Sur" },
        "country": { "label": "country", "definition": "Nombre del país.", "example": "México" },
        "stateProvince": { "label": "stateProvince", "definition": "Estado, provincia o departamento.", "example": "Oaxaca" },
        "occurrenceStatus": { "label": "occurrenceStatus", "definition": "Estatus de presencia en la zona.", "example": "present" },
        "threatStatus": { "label": "threatStatus", "definition": "Categoría de amenaza según la IUCN.", "example": "Endangered" },
        "establishmentMeans": { "label": "establishmentMeans", "definition": "Medio de establecimiento (native, introduced).", "example": "native" }
      }
    },
    "VernacularName": {
      "description": "Nombres comunes o vernáculos asociados a los taxones en diferentes idiomas.",
      "fk_column_default": "coreID",
      "self_id_default": "",
      "self_parent_default": "",
      "terms": {
        "coreID": { "label": "coreID", "definition": "Clave foránea hacia el taxón Core.", "example": "taxon-456" },
        "vernacularName": { "label": "vernacularName", "definition": "Nombre común de la especie.", "example": "Roble común" },
        "language": { "label": "language", "definition": "Código de idioma (ISO 639-1).", "example": "es" },
        "isPreferredName": { "label": "isPreferredName", "definition": "Indica si es el nombre común principal.", "example": "true" },
        "sex": { "label": "sex", "definition": "Sexo al que aplica el nombre común, si aplica.", "example": "both" }
      }
    },
    "Identification": {
      "description": "Historial de determinaciones e identificaciones taxonómicas de los especímenes.",
      "fk_column_default": "coreID",
      "self_id_default": "identificationID",
      "self_parent_default": "",
      "terms": {
        "identificationID": { "label": "identificationID", "definition": "ID único de la determinación.", "example": "ident-01" },
        "coreID": { "label": "coreID", "definition": "Clave foránea hacia la ocurrencia Core.", "example": "occ-123" },
        "identifiedBy": { "label": "identifiedBy", "definition": "Persona que realizó la identificación.", "example": "Dr. Botanist" },
        "dateIdentified": { "label": "dateIdentified", "definition": "Fecha en que se realizó la identificación.", "example": "2024-11-20" },
        "identificationQualifier": { "label": "identificationQualifier", "definition": "Calificador taxonómico (ej. cf., aff.).", "example": "cf." },
        "typeStatus": { "label": "typeStatus", "definition": "Estatus de tipo nomenclatural (ej. Holotype, Paratype).", "example": "Holotype" }
      }
    },
    "Multimedia": {
      "description": "Simple Multimedia: Enlaces a recursos digitales (fotografías, audios, vídeos).",
      "fk_column_default": "coreID",
      "self_id_default": "identifier",
      "self_parent_default": "",
      "terms": {
        "identifier": { "label": "identifier", "definition": "URI o URL del archivo multimedia.", "example": "https://images.org/img1.jpg" },
        "coreID": { "label": "coreID", "definition": "Clave foránea hacia el Core.", "example": "occ-123" },
        "type": { "label": "type", "definition": "Tipo de recurso (StillImage, Sound, MovingImage).", "example": "StillImage" },
        "format": { "label": "format", "definition": "Formato MIME del archivo.", "example": "image/jpeg" },
        "title": { "label": "title", "definition": "Título o descripción corta de la obra.", "example": "Flor y hoja de roble" },
        "creator": { "label": "creator", "definition": "Autor, fotógrafo o creador del recurso.", "example": "Javier Estrada" },
        "license": { "label": "license", "definition": "Enlace a la licencia de uso.", "example": "http://creativecommons.org/licenses/by/4.0/" }
      }
    },
    "ResourceRelationship": {
      "description": "Relaciones lógicas o ecológicas entre diferentes registros o recursos del dataset.",
      "fk_column_default": "coreID",
      "self_id_default": "resourceRelationshipID",
      "self_parent_default": "",
      "terms": {
        "resourceRelationshipID": { "label": "resourceRelationshipID", "definition": "ID único de la relación.", "example": "rel-01" },
        "coreID": { "label": "coreID", "definition": "Clave foránea al registro origen.", "example": "occ-123" },
        "resourceRelationship": { "label": "resourceRelationship", "definition": "Tipo de relación (ej. parasiteOf, pollinatedBy).", "example": "parasiteOf" },
        "relatedResourceID": { "label": "relatedResourceID", "definition": "ID del recurso relacionado.", "example": "occ-999" }
      }
    }
  }
}

def get_dictionary_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, DICTIONARY_FILENAME)

def verify_and_initialize_dictionary(parent_window=None):
    path = get_dictionary_path()
    if not os.path.exists(path):
        save_dictionary(DEFAULT_DWC_DATABASE)
        return
    
    try:
        file_mtime = os.path.getmtime(path)
        age_in_days = (time.time() - file_mtime) / (60 * 60 * 24)
        if age_in_days > 30:
            if parent_window:
                res = messagebox.askyesno(
                    "Actualización de Diccionario Darwin Core",
                    f"El diccionario '{DICTIONARY_FILENAME}' tiene más de 30 días de antigüedad.\n¿Desea actualizarlo con el estándar oficial?",
                    parent=parent_window
                )
                if res:
                    update_dictionary_from_source(parent_window)
    except Exception:
        pass

def save_dictionary(data):
    path = get_dictionary_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_dictionary_from_source(parent_window=None):
    try:
        save_dictionary(DEFAULT_DWC_DATABASE)
        if parent_window:
            messagebox.showinfo("Actualización Exitosa", "El diccionario Darwin Core y de Extensiones se ha sincronizado correctamente.", parent=parent_window)
    except Exception as e:
        if parent_window:
            messagebox.showerror("Error", f"No se pudo actualizar el diccionario: {e}", parent=parent_window)

def load_dwc_database():
    path = get_dictionary_path()
    if not os.path.exists(path):
        save_dictionary(DEFAULT_DWC_DATABASE)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DWC_DATABASE

def get_core_types():
    db = load_dwc_database()
    return list(db.get("Cores", {}).keys())

def get_extension_types():
    db = load_dwc_database()
    return list(db.get("Extensions", {}).keys())

def get_terms_for_type(component_type, is_core=True):
    db = load_dwc_database()
    category = "Cores" if is_core else "Extensions"
    components = db.get(category, {})
    matched_data = {}
    for key, val in components.items():
        if key.lower() in component_type.lower() or component_type.lower() in key.lower():
            matched_data = val
            break
    if not matched_data and components:
        matched_data = list(components.values())[0]
    terms_dict = matched_data.get("terms", {})
    return list(terms_dict.keys())

def get_term_metadata(component_type, term_name, is_core=True):
    db = load_dwc_database()
    category = "Cores" if is_core else "Extensions"
    components = db.get(category, {})
    matched_data = {}
    for key, val in components.items():
        if key.lower() in component_type.lower() or component_type.lower() in key.lower():
            matched_data = val
            break
    if not matched_data and components:
        matched_data = list(components.values())[0]
    terms_dict = matched_data.get("terms", {})
    return terms_dict.get(term_name, {"label": term_name, "definition": "Término estándar Darwin Core requerido para el IPT.", "example": "N/A"})