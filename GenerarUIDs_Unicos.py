"""
Script: añadir UUID v4 a un CSV existente

Qué hace:
Este script toma un archivo CSV situado en el mismo directorio que el propio
script y genera un nuevo archivo con una columna adicional llamada 'UUID'. Para
cada fila de datos del CSV original, el script crea un identificador UUID v4
distinto y lo añade al final de la fila. El proceso no modifica el archivo
original, sino que genera un segundo archivo con los UUID incorporados, listo
para ser importado en Access, GBIF, IPT o cualquier flujo que requiera
identificadores globalmente únicos.

Dónde busca los UUID:
Los UUID no se buscan en ningún sitio externo; se generan directamente en el
script mediante la función uuid.uuid4() de la biblioteca estándar de Python.
Cada llamada produce un identificador aleatorio conforme a la especificación
RFC 4122. El script no consulta bases de datos, servicios web ni archivos
previos: todos los UUID se crean en tiempo de ejecución y se insertan en el
CSV de salida.

Características de los UUID generados:
Los UUID v4 producidos por uuid.uuid4() son identificadores aleatorios de 128
bits, representados como cadenas en formato estándar 8-4-4-4-12. No dependen de
la máquina, del usuario ni del contenido del CSV, y no se repiten salvo por
probabilidad astronómicamente baja. Son adecuados para identificar registros en
sistemas distribuidos, para trazabilidad en flujos Darwin Core y para evitar
colisiones en procesos de integración de datos.

Cómo se emplea:
1. Coloca este script (.py) en la misma carpeta que tu archivo CSV de entrada.
2. Cambia el nombre del archivo de entrada en la constante INPUT_CSV si es
   necesario.
3. Ejecuta el script con:
       python añadir_uuid_csv.py
4. Se generará un archivo nuevo (OUTPUT_CSV) en la misma carpeta, con la columna
   'UUID' añadida. Ese archivo es el que luego puedes importar en Access o donde
   sea necesario.
"""


import uuid
import csv
import os

# ⚙️ CONFIGURACIÓN
INPUT_CSV = "SinUUIDs.csv"   # nombre del CSV de entrada (en el mismo directorio)
OUTPUT_CSV = "ConUUIDs.csv"  # nombre del CSV de salida


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_CSV)
    output_path = os.path.join(script_dir, OUTPUT_CSV)

    if not os.path.exists(input_path):
        print(f"ERROR: No se encontró el archivo '{INPUT_CSV}' en {script_dir}")
        return

    with open(input_path, "r", newline="", encoding="utf-8") as fin:
        reader = csv.reader(fin)
        rows = list(reader)

    if not rows:
        print("El archivo CSV está vacío.")
        return

    header = rows[0]
    data_rows = rows[1:]

    # Añadimos la nueva columna 'UUID' al encabezado
    header.append("UUID")

    # Generamos un UUID v4 por cada fila de datos
    new_rows = [header]
    for row in data_rows:
        row_with_uuid = row + [str(uuid.uuid4())]
        new_rows.append(row_with_uuid)

    # Escribimos el nuevo CSV
    with open(output_path, "w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerows(new_rows)

    print(f"Archivo de entrada: {input_path}")
    print(f"Filas de datos (sin cabecera): {len(data_rows)}")
    print(f"Archivo generado con UUID: {output_path}")


if __name__ == "__main__":
    main()
