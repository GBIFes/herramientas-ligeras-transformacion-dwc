"""
update_dictionary.py
================    
Script para administradores de nodos: Descarga el estándar oficial actualizado 
de términos Darwin Core directamente desde los repositorios de TDWG.
"""

import requests
import json

DWC_JSON_URL = "http://rs.tdwg.org/dwc/terms.json"

def fetch_official_dwc_terms():
    try:
        response = requests.get(DWC_JSON_URL)
        if response.status_code == 200:
            data = response.json()
            terms_database = {"Cores": {}, "Extensions": {}}
            
            # Procesar y filtrar términos vigentes (no obsoletos)
            # TDWG categoriza los términos y puedes estructurarlos automáticamente
            print("¡Datos oficiales de Darwin Core descargados con éxito!")
            return data
    except Exception as e:
        print(f"Error al conectar con TDWG: {e}")
    return None

if __name__ == "__main__":
    fetch_official_dwc_terms()