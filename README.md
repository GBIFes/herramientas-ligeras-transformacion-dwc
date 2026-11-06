# Herramientas Ligeras
Herramientas para la preparación de archivos para el IPT GBIF.ES
pequeños programas en Python convertidos de módulos de VBA para ejecutarse sobre archivos csv que producen como resultado un archivo tambien csv con una o varias columnas con los datos convertidos, transformados, estandarizados o con el resultado de la búsqueda específica

Para obtener un ejecutable en windows ejecutar en Visual Studio Code:
	pyinstaller --onefile --windowed "C:\[path del directorio]\[nombre del programa].py


## Índice de programas:
**ScrapNombreComunes:** usa un fichero de entrada con un campo con nombres comunes separados por comas ",", puntos y comas ";" u otro separador y crea una tabla con los nombres en lineas diferentes ligados a las líneas del archivo original mediante una columa identificadora comun (Tabla de entrada.id)

**ScrapEIDOS:** Partiendo de una tabla que contenga una columna de nombres científicos o una columna con identificadores de taxones EIDOS el programa visita EIDOS y obtiene todos los datos asociados a dichos nombre o identificadores (Nombres vernáculos, Estatus legal, Información taxonómica, etc.)

**VisorDwCa:** Permite seleccionar un archivo DarwinCore y visualizar la metadata y los demás archivos de datos, salvarlos en excel o en Access de Microsoft.

**VisorDataSetsEIDOS:** Se conecta con el sitio del MITECO donde reside la data de especies silvestres en España y extrae la lista de datasets disponibles en el sevidor. al navegar por sus pestañas podemos bajar y navegar los datos de los distintos datasets y guardarlos en nuestro disco duro para su posterior uso

**DwCA_UUID:** Generador de UUID para Darwin Core Archive. Al elegir un DWC-a produce una copia en la que sustituyó los identificadores de las tablas por UUIDS agnósticos conservando las columnas de los identificadores previos para permitir su conexión con los registros originales de la base de datos.

**UUIsCSV:** Generador de UUIDs oara archivos de datos delimitados. Esta utilidad crea una copia de un archivo CSV o TSV añadiendo una nueva columna con identificadores UUID únicos. Características:
	- Detecta delimitadores: coma, punto y coma y tabulador.
	- Detecta varias codificaciones habituales automáticamente.
	- Mantiene el formato original del archivo.
	- Genera una columna UUID.
		- Si UUID ya existe, genera G_UUID.
		- Si G_UUID también existe, genera G_UUID_2, G_UUID_3, etc.
	- No modifica el archivo original.
	- Salida: archivo.csv  -> archivo_UUID.csv y  archivo.tsv  -> archivo_UUID.tsv

En desarrollo, se gradecen comentarios, correcciones y sugerencias 

