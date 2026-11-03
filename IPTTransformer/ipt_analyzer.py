"""
ipt_analyzer.py
===============
Motor de análisis inteligente para detección de duplicados, columnas con
variabilidad interna y generación de diagnósticos relacionales para Cores DwC.
"""

from collections import Counter

class IPTDatasetAnalyzer:
    """Analiza la estructura de un dataset tabular para identificar IDs duplicados,
    columnas con múltiples valores y sugerir normalización en estrella o jerárquica."""
    
    def __init__(self, headers, rows, id_col):
        self.headers = list(headers)
        self.rows = [list(r) for r in rows]
        self.id_col = str(id_col).strip()
        if not self.headers:
            raise ValueError("La tabla no tiene cabeceras.")
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Todas las filas deben tener tantas celdas como cabeceras.")
        
        # Encontrar el índice de la columna ID principal
        self.id_idx = self._encontrar_indice_id()

    def _encontrar_indice_id(self):
        for i, h in enumerate(self.headers):
            if h.strip().casefold() == self.id_col.casefold():
                return i
        raise ValueError(f"No existe la columna de identificación '{self.id_col}'.")

    def filtrar_duplicados(self):
        """Devuelve todas las filas que comparten un ID duplicado en el dataset."""
        if not self.rows or self.id_idx >= len(self.rows[0]):
            return []
        
        id_counts = Counter(str(r[self.id_idx]) for r in self.rows if len(r) > self.id_idx)
        ids_duplicados = {cid for cid, count in id_counts.items() if count > 1}
        
        return [r for r in self.rows if len(r) > self.id_idx and str(r[self.id_idx]) in ids_duplicados]

    def detectar_columnas_variables(self, duplicate_rows):
        """Identifica qué columnas varían en valor para un mismo ID duplicado."""
        if not duplicate_rows:
            return []

        # Mapear ID -> {col_idx: set(valores)}
        mapa_valores = {}
        for r in duplicate_rows:
            if len(r) <= self.id_idx:
                continue
            cid = str(r[self.id_idx])
            if cid not in mapa_valores:
                mapa_valores[cid] = {i: set() for i in range(len(self.headers))}
            
            for i, val in enumerate(r):
                if i < len(self.headers):
                    mapa_valores[cid][i].add(str(val).strip())

        columnas_variables = []
        for i, h in enumerate(self.headers):
            if i == self.id_idx:
                continue
            # Comprobar si al menos un ID tiene múltiples valores distintos para esta columna
            varia = False
            for cid, col_dict in mapa_valores.items():
                if len(col_dict.get(i, set())) > 1:
                    varia = True
                    break
            if varia:
                columnas_variables.append(h)

        return columnas_variables

    def generar_resumen_analisis(self):
        """Genera un diccionario con el diagnóstico y sugerencia estructural."""
        dups = self.filtrar_duplicados()
        total_dups = len(dups)
        vars_cols = self.detectar_columnas_variables(dups)

        sugiere_jerarquia = len(vars_cols) > 2 or any("parent" in c.lower() or "child" in c.lower() for c in self.headers)

        if total_dups == 0:
            diagnostico = "Dataset limpio: No se detectan registros duplicados en la clave principal."
        else:
            diagnostico = f"Se detectaron {total_dups} registros con IDs duplicados. Se recomienda segregar columnas variables."

        return {
            "total_duplicados": total_dups,
            "ids_duplicados": len({str(r[self.id_idx]) for r in dups}),
            "ids_vacios": sum(not str(r[self.id_idx]).strip() for r in self.rows),
            "columnas_variables": vars_cols,
            "sugiere_jerarquia": sugiere_jerarquia,
            "diagnostico_texto": diagnostico
        }
