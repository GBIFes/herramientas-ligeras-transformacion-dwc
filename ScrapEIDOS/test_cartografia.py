"""Pruebas locales: python -m unittest -v test_cartografia.py.

Pruebas Tk opcionales:
RUN_GUI_TESTS=1 xvfb-run -a python -m unittest -v test_cartografia.py
"""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from cartografia import (
    COLUMNAS_COORD, extraer_id, recopilar_coordenadas,
    guardar_cartografia, generar_mapa,
)
from eidos_a_csv import consultar, filtro_taxon


FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[-5.4, 36.8], [-5.3, 36.8], [-5.3, 36.9],
                           [-5.4, 36.9], [-5.4, 36.8]]]],
    },
    "properties": {"id": 1, "cuadricula": "CUADRICULA_PRUEBA"},
}


class CartografiaTests(unittest.TestCase):
    def test_ids_y_filtro(self):
        self.assertEqual(extraer_id("0010903"), "10903")
        self.assertEqual(extraer_id(
            "https://iepnb.gob.es/areas-tematicas/especies-silvestres/eidos/10903"
        ), "10903")
        with self.assertRaises(ValueError):
            extraer_id("10903 OR 1=1")
        self.assertIn("lista_idstaxon_filtro = '10903'", filtro_taxon("10903"))
        self.assertIn("LIKE '%,10903,%'", filtro_taxon("10903"))

    def test_exito_sin_datos_error_y_descartar_parciales(self):
        def simular(session, e_id):
            if e_id == "1":
                yield FEATURE
            elif e_id == "3":
                yield FEATURE
                raise RuntimeError("Fallo de la segunda página")
        with patch("cartografia.consultar", side_effect=simular) as consulta:
            df, geo, estado = recopilar_coordenadas(["1", "1", "2", "3"])
        self.assertEqual(consulta.call_count, 3)
        self.assertEqual(list(df.columns), COLUMNAS_COORD)
        self.assertEqual(len(df), 1)
        self.assertEqual(len(geo["features"]), 1)
        self.assertEqual(estado.estado.tolist(), ["ok", "sin_distribucion", "error"])
        self.assertTrue(36.8 < df.iloc[0].latdecimal < 36.9)
        self.assertTrue(-5.4 < df.iloc[0].longdecimal < -5.3)
        with tempfile.TemporaryDirectory() as tmp:
            rutas = guardar_cartografia(df, geo, estado, tmp, "prueba")
            self.assertTrue(rutas["csv"].read_text(encoding="utf-8-sig").startswith(
                "taxonId;utm;latdecimal;longdecimal"
            ))
            self.assertEqual(len(json.loads(rutas["geojson"].read_text())["features"]), 1)
            mapa = generar_mapa("1", "Taxón de prueba", df, geo, Path(tmp) / "mapa.html")
            self.assertIn("L.geoJson", mapa.read_text())
            self.assertIn("Centros de cuadr", mapa.read_text())

    def test_paginacion_total_desconocido_y_limite_servidor(self):
        from unittest.mock import Mock
        session = Mock()
        segundo = dict(FEATURE, properties={"id": 2, "cuadricula": "PRUEBA2"})
        def respuesta(features):
            response = Mock()
            response.json.return_value = {
                "type": "FeatureCollection", "features": features,
                "numberMatched": "unknown",
            }
            return response
        session.get.side_effect = [
            respuesta([FEATURE]), respuesta([segundo]), respuesta([]),
        ]
        self.assertEqual(len(list(consultar(session, "1", page_size=1000))), 2)
        self.assertEqual(
            [call.kwargs["params"]["startIndex"] for call in session.get.call_args_list],
            [0, 1, 2],
        )

    def test_respuesta_xml_y_pagina_repetida(self):
        from unittest.mock import Mock
        session = Mock()
        session.get.return_value.json.side_effect = ValueError("XML")
        session.get.return_value.text = "<ExceptionReport>Error</ExceptionReport>"
        with self.assertRaises(RuntimeError):
            list(consultar(session, "1"))
        session = Mock()
        session.get.return_value.json.return_value = {
            "type": "FeatureCollection", "features": [FEATURE], "numberMatched": 2,
        }
        with self.assertRaisesRegex(RuntimeError, "repitió"):
            list(consultar(session, "1", page_size=1))


@unittest.skipUnless(os.getenv("RUN_GUI_TESTS") == "1", "Requiere pantalla o Xvfb")
class InterfazTests(unittest.TestCase):
    def test_descarga_guarda_sin_abrir_pestana(self):
        import tkinter as tk
        from tkinter import ttk
        import gui

        with tempfile.TemporaryDirectory() as tmp:
            entrada = Path(tmp) / "entrada.csv"
            pd.DataFrame({"ID": ["10903"]}).to_csv(entrada, index=False)
            salida = Path(tmp) / "salida"
            root = tk.Tk()
            root.withdraw()
            progress = ttk.Progressbar(root)
            label = ttk.Label(root)
            boton = ttk.Button(root)
            recibido = []
            errores_tk = []
            root.report_callback_exception = lambda *args: errores_tk.append(args)
            def fin(*args, **kwargs):
                recibido.append((args, kwargs))
                root.quit()
            with patch.object(gui, "procesar_fila", return_value=(None, "10903")), patch(
                "cartografia.consultar", return_value=iter([FEATURE])
            ):
                root.after(0, lambda: gui.ejecutar_scraping(
                    str(entrada), str(salida), "ID", "id", root, progress,
                    label, boton, fin,
                ))
                limite = root.after(15000, root.quit)
                root.mainloop()
                root.after_cancel(limite)
            self.assertFalse(errores_tk, errores_tk)
            self.assertEqual(len(recibido), 1)
            self.assertEqual(len(recibido[0][1]["df_coord"]), 1)
            self.assertTrue((salida / "entrada_Coordenadas.csv").exists())
            self.assertTrue((salida / "entrada_Distribucion.geojson").exists())
            root.destroy()

    def test_navegacion_mapa_exportacion_y_cierre_no_destructivo(self):
        import tkinter as tk
        from tkinter import ttk
        import gui

        def descendientes(widget):
            for hijo in widget.winfo_children():
                yield hijo
                yield from descendientes(hijo)

        with tempfile.TemporaryDirectory() as tmp:
            with patch("cartografia.consultar", return_value=iter([FEATURE])):
                df, geo, estado = recopilar_coordenadas(["1"])
            entrada = pd.DataFrame([
                {"EIDOS_ID": "1", "verbatimScientificName": "Especie de prueba"},
                {"EIDOS_ID": "2", "verbatimScientificName": "Sin distribución"},
            ])
            estado.loc[len(estado)] = ["2", "sin_distribucion", 0, ""]
            vacio = pd.DataFrame()
            root = tk.Tk()
            root.withdraw()
            with patch.object(gui, "abrir_mapa", return_value="ventana") as abrir:
                gui.abrir_visor_access(
                    entrada, vacio, vacio, vacio, vacio, vacio, vacio,
                    vacio, tmp, "", root, df, geo, estado,
                )
                root.update()
                visor = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                widgets = list(descendientes(visor))
                mapa = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget("text") == "Ver mapa")
                mapa.invoke()
                self.assertEqual(abrir.call_count, 1)
                self.assertTrue((Path(tmp) / "mapas" / "EIDOS_1.html").exists())
                trees = [w for w in widgets if isinstance(w, ttk.Treeview)]
                self.assertEqual(len(trees[0].get_children()), 1)
                siguiente = next(w for w in widgets if isinstance(w, tk.Button) and w.cget("text") == ">")
                anterior = next(w for w in widgets if isinstance(w, tk.Button) and w.cget("text") == "<")
                siguiente.invoke()
                root.update()
                self.assertTrue(mapa.instate(["disabled"]))
                self.assertEqual(len(trees[0].get_children()), 0)
                anterior.invoke()
                root.update()
                self.assertFalse(mapa.instate(["disabled"]))
                exportar = next(w for w in widgets if isinstance(w, tk.Button) and "Exportar" in w.cget("text"))
                with patch.object(gui.messagebox, "showinfo"), patch.object(
                    gui.messagebox, "showerror"
                ) as error, patch.object(gui, "abrir_archivo_sistema"):
                    exportar.invoke()
                error.assert_not_called()
            excel = pd.read_excel(Path(tmp) / "resultado_exportacion_Access.xlsx", sheet_name="Coordenadas")
            self.assertEqual(len(excel), 1)
            with sqlite3.connect(Path(tmp) / "resultado_EIDOS.db") as conn:
                tablas = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                self.assertIn(("Coordenadas",), tablas)
                schema = conn.execute("PRAGMA table_info(Coordenadas)").fetchall()
                self.assertEqual([c[1] for c in schema], COLUMNAS_COORD)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM Coordenadas").fetchone()[0], 1)
            self.assertTrue((Path(tmp) / "resultado_Coordenadas.csv").exists())

            # Sin exportar: cerrar no elimina ficheros preexistentes.
            protegido = Path(tmp) / "no_borrar.txt"
            protegido.write_text("conservar", encoding="utf-8")
            root = tk.Tk()
            root.withdraw()
            gui.abrir_visor_access(
                entrada, vacio, vacio, vacio, vacio, vacio, vacio, vacio,
                tmp, "", root, df, geo, estado,
            )
            visor = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            with patch.object(gui.messagebox, "askyesnocancel", return_value=False):
                visor.tk.call(visor.protocol("WM_DELETE_WINDOW"))
            self.assertEqual(protegido.read_text(), "conservar")


if __name__ == "__main__":
    unittest.main()
