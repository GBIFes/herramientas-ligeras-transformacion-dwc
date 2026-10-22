"""
enriquecer_lote.py

Procesamiento por lotes con:

- reanudación automática
- reintentos
- registro de progreso
- barra de progreso
- estadísticas finales
"""

import sys
import time
from datetime import datetime

from modulos.config import LOG_DIR

from modulos.conexion import (
    obtener_taxones
)

from modulos.control import (
    pendientes
)

from enriquecer_taxon import (
    enriquecer_taxon
)

MAX_REINTENTOS = 3
ESPERA_REINTENTO = 5

LOG_DIR.mkdir(
    exist_ok=True
)

LOG_FILE = (
    LOG_DIR /
    f"enriquecimiento_"
    f"{datetime.now():%Y%m%d}.log"
)


def escribir_log(texto):

    marca = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    linea = (
        f"[{marca}] "
        f"{texto}\n"
    )

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(linea)

    print(texto)


def obtener_limite():

    if len(sys.argv) < 2:
        return None

    try:
        return int(sys.argv[1])

    except ValueError:
        return None


def obtener_lista_trabajo():

    lista = pendientes()

    if lista:
        return lista

    return obtener_taxones()


def barra_progreso(
    actual,
    total,
    ancho=40
):

    if total == 0:
        return ""

    porcentaje = actual / total

    completado = int(
        ancho * porcentaje
    )

    barra = (
        "█" * completado
        + "-"
        * (ancho - completado)
    )

    return (
        f"[{barra}] "
        f"{porcentaje * 100:5.1f}%"
    )


def procesar_taxon(taxonid):

    ultimo_error = None

    for intento in range(
        1,
        MAX_REINTENTOS + 1
    ):

        try:

            enriquecer_taxon(
                taxonid
            )

            return True

        except Exception as e:

            ultimo_error = e

            escribir_log(
                f"ERROR "
                f"{taxonid} "
                f"(intento {intento}) "
                f"{e}"
            )

            if intento < MAX_REINTENTOS:

                time.sleep(
                    ESPERA_REINTENTO
                )

    escribir_log(
        f"FALLO DEFINITIVO "
        f"{taxonid} "
        f"{ultimo_error}"
    )

    return False
def ejecutar():

    inicio = time.time()

    limite = obtener_limite()

    taxones = obtener_lista_trabajo()

    if limite is not None:

        taxones = taxones[:limite]

    total = len(
        taxones
    )

    correctos = 0
    errores = 0

    escribir_log(
        f"INICIO "
        f"Taxones={total}"
    )

    print()

    for posicion, taxonid in enumerate(
        taxones,
        start=1
    ):

        barra = barra_progreso(
            posicion - 1,
            total
        )

        print(
            f"\r{barra} "
            f"{posicion}/{total} "
            f"TaxonID={taxonid}",
            end="",
            flush=True
        )

        ok = procesar_taxon(
            taxonid
        )

        if ok:
            correctos += 1

        else:
            errores += 1

    print()

    barra = barra_progreso(
        total,
        total
    )

    print(barra)

    duracion = (
        time.time()
        - inicio
    )

    escribir_log("")

    escribir_log(
        "RESUMEN FINAL"
    )

    escribir_log(
        f"Total: {total}"
    )

    escribir_log(
        f"Correctos: {correctos}"
    )

    escribir_log(
        f"Errores: {errores}"
    )

    escribir_log(
        f"Duración: "
        f"{duracion:.1f} s"
    )

    escribir_log(
        f"Log: {LOG_FILE}"
    )


if __name__ == "__main__":

    ejecutar()