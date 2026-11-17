# Herramientas Ligeras
Herramientas para la visualización, modificación y preparación de archivos para su publicación en el IPT GBIF.ES
Programas desarrollados en Python o módulos escritos en VBA y convertidos a Python para ejecutarse sobre archivos .csv que producen como resultado archivos .csv con una o varias columnas con los datos convertidos, transformados, estandarizados o con el resultado de la búsqueda específica.

Para obtener un ejecutable en windows ejecutar en Visual Studio Code:

	pyinstaller --onefile --windowed "C:\[path del directorio]\[nombre del programa].py

El resultado es un archivo ejecutable (.exe) que contiene el código precompilado, las bibliotecas y el motor Python y un intefaz Tkinter que permite navegar en los directorios del sistema para escoger los archivos, definir parámetros y opciones, visualizar los datos en ventanas estándares de Windows. De esta manera el usuario no necesita tener instalado python en su maquina ni conocer el lenguaje de programación.

## Índice de programas:
**ScrapNombreComunes:** usa un fichero de entrada con un campo con nombres comunes separados por comas ",", puntos y comas ";" o tabulador y crea una tabla con los nombres en lineas diferentes ligados a las líneas del archivo original mediante una columa identificadora comun (Tabla de entrada.id).

**ScrapEIDOS:** Partiendo de una tabla que contenga una columna de nombres científicos o una columna con identificadores de taxones EIDOS el programa visita EIDOS y obtiene todos los datos asociados a dichos nombre o identificadores (Nombres vernáculos, Estatus legal, Información taxonómica, etc.).

**VisorDwCa:** Permite seleccionar un archivo DarwinCore y visualizar la metadata y los demás archivos de datos, salvarlos en Excel o en Access de Microsoft.

**VisorDataSetsEIDOS:** Se conecta con el sitio del MITECO donde reside la data de especies silvestres, exóticas e invasoras en España y extrae la lista de datasets disponibles en el servidor. Al navegar por sus pestañas podemos ver y guardar localmente los datos de los distintos datasets seleccionados para su posterior uso.

**DwCA_UUID:** Generador de UUIDs para Darwin Core Archive. Al elegir un DwC-a produce una copia en la que sustituye los identificadores de las tablas por UUIDs agnósticos conservando las columnas de los identificadores previos para permitir su conexión con los registros originales de la base de datos.

**UUIsCSV:** Generador de UUIDs oara archivos de datos delimitados. Esta utilidad crea una copia de un archivo CSV o TSV añadiendo una nueva columna con identificadores UUID únicos. Características:
	- Detecta delimitadores: coma, punto y coma y tabulador.
	- Detecta varias codificaciones habituales automáticamente.
	- Mantiene el formato original del archivo.
	- Genera una columna UUID.
		- Si UUID ya existe, genera G_UUID.
		- Si G_UUID también existe, genera G_UUID_2, G_UUID_3, etc.
	- No modifica el archivo original.
	- Salida: archivo.csv  -> archivo_UUID.csv y  archivo.tsv  -> archivo_UUID.tsv.

¡¡En continuo desarrollo!!, se gradecen comentarios, correcciones y sugerencias de nuevas funcionalidades.

