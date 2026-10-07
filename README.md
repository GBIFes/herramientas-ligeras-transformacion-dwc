# Herramientas Ligeras
Herramientas para la preparación de archivos para el IPT GBIF.ES
pequeños programas en Python convertidos de módulos de VBA para ejecutarse sobre archivos csv que producen como resultado un archivo tambien csv con una o varias columnas con los datos convertidos, transformados, estandarizados o con el resultado de la búsqueda específica

Para obtener un ejecutable en windows ejecutar en Visua Studio Code:
	pyinstaller --onefile --windowed "C:\[path del directorio]\[nombre del programa].py


Índice de programas:
ScrapNombreComunes: usa un dichero de entrada con un campo con nombres comunes separados por comas ",", puntos ty comas ";" u otro separador y crea una tabla con los nombres en lineas diferentes ligados a las líneas del archivo original mediante una columa identificadora comun (Tabla de entrada.id)

En desarrollo
