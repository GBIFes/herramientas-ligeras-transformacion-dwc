"""
encoding_utils.py

Detección de:

- Codificación
- Delimitador
- Apertura segura de archivos delimitados

Compatible con:

- UTF-8
- UTF-8 BOM
- Windows-1252
- ISO-8859-1
- Latin1

Delimitadores:

- TAB
- ;
- ,
"""

from pathlib import Path
import csv


SUPPORTED_ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin1",
    "iso-8859-1"
]

SUPPORTED_DELIMITERS = [
    "\t",
    ";",
    ","
]


def detect_encoding(filepath):
    """
    Detecta codificación.
    """

    filepath = Path(filepath)

    for encoding in SUPPORTED_ENCODINGS:

        try:

            with open(
                filepath,
                "r",
                encoding=encoding
            ) as f:

                f.read(8192)

            return encoding

        except UnicodeDecodeError:

            pass

    return "latin1"


def read_sample(
    filepath,
    size=8192
):
    """
    Lee una muestra inicial del fichero.
    """

    encoding = detect_encoding(
        filepath
    )

    with open(
        filepath,
        "r",
        encoding=encoding,
        errors="ignore"
    ) as f:

        return f.read(size)


def detect_delimiter(
    filepath
):
    """
    Detecta TAB, ; o ,
    """

    sample = read_sample(
        filepath
    )

    try:

        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=
            SUPPORTED_DELIMITERS
        )

        return dialect.delimiter

    except Exception:

        separators = {

            "\t":
            sample.count("\t"),

            ";":
            sample.count(";"),

            ",":
            sample.count(",")

        }

        return max(
            separators,
            key=separators.get
        )


def detect_file_format(
    filepath
):
    """
    Devuelve:

    (
        encoding,
        delimiter
    )
    """

    encoding = detect_encoding(
        filepath
    )

    delimiter = detect_delimiter(
        filepath
    )

    return (
        encoding,
        delimiter
    )


def delimiter_name(
    delimiter
):

    if delimiter == "\t":
        return "TAB"

    if delimiter == ";":
        return "Punto y coma"

    if delimiter == ",":
        return "Coma"

    return "Desconocido"


def create_reader(
    file_object,
    delimiter
):

    return csv.reader(
        file_object,
        delimiter=delimiter
    )


def create_writer(
    file_object,
    delimiter
):

    return csv.writer(
        file_object,
        delimiter=delimiter,
        lineterminator="\n"
    )


def open_input_file(
    filepath
):
    """
    Apertura segura de lectura.
    """

    encoding = detect_encoding(
        filepath
    )

    return open(
        filepath,
        "r",
        encoding=encoding,
        errors="ignore",
        newline=""
    )


def open_output_file(
    filepath,
    encoding
):
    """
    Apertura segura de escritura.
    """

    return open(
        filepath,
        "w",
        encoding=encoding,
        newline=""
    )


def get_header(
    filepath
):
    """
    Devuelve cabecera.
    """

    (
        encoding,
        delimiter
    ) = detect_file_format(
        filepath
    )

    with open(
        filepath,
        "r",
        encoding=encoding,
        errors="ignore",
        newline=""
    ) as f:

        reader = create_reader(
            f,
            delimiter
        )

        try:

            return next(
                reader
            )

        except StopIteration:

            return []


def describe_file(
    filepath
):
    """
    Devuelve información descriptiva.
    """

    (
        encoding,
        delimiter
    ) = detect_file_format(
        filepath
    )

    return {

        "file":
        str(filepath),

        "encoding":
        encoding,

        "delimiter":
        delimiter,

        "delimiter_name":
        delimiter_name(
            delimiter
        )

    }


def is_tab_delimited(
    filepath
):

    return (
        detect_delimiter(
            filepath
        )
        == "\t"
    )


def is_comma_delimited(
    filepath
):

    return (
        detect_delimiter(
            filepath
        )
        == ","
    )


def is_semicolon_delimited(
    filepath
):

    return (
        detect_delimiter(
            filepath
        )
        == ";"
    )