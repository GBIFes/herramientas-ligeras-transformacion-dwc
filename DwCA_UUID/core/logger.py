"""
logger.py

Registro de ejecución del proceso.

Utilizado para:

- Información general
- Advertencias
- Errores
- Estadísticas de transformación
"""

from pathlib import Path
from datetime import datetime


class ProcessLogger:

    def __init__(
        self,
        log_file
    ):

        self.log_file = Path(
            log_file
        )

        self._create_log()

    # --------------------------------------------------
    # INTERNOS
    # --------------------------------------------------

    def _timestamp(
        self
    ):

        return datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def _create_log(
        self
    ):

        with open(
            self.log_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "=" * 80
            )

            f.write("\n")

            f.write(
                "DWCA UUID TRANSFORMER LOG\n"
            )

            f.write(
                "=" * 80
            )

            f.write("\n\n")

            f.write(
                f"Inicio: "
                f"{self._timestamp()}\n\n"
            )

    def _write(
        self,
        level,
        message
    ):

        with open(
            self.log_file,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                f"[{self._timestamp()}] "
                f"{level:<7} "
                f"{message}\n"
            )

    # --------------------------------------------------
    # API PÚBLICA
    # --------------------------------------------------

    def info(
        self,
        message
    ):

        self._write(
            "INFO",
            message
        )

    def warning(
        self,
        message
    ):

        self._write(
            "WARNING",
            message
        )

    def error(
        self,
        message
    ):

        self._write(
            "ERROR",
            message
        )

    def separator(
        self
    ):

        with open(
            self.log_file,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                "-" * 80
            )

            f.write("\n")

    def write_title(
        self,
        title
    ):

        self.separator()

        self.info(
            title
        )

        self.separator()

    # --------------------------------------------------
    # RESUMEN DWCA
    # --------------------------------------------------

    def log_dwca_info(
        self,
        dwca_file,
        deterministic
    ):

        self.write_title(
            "CONFIGURACION"
        )

        self.info(
            f"Archivo origen: "
            f"{dwca_file}"
        )

        self.info(
            f"Modo UUID: "
            f"{'Determinista' if deterministic else 'Aleatorio'}"
        )

    def log_core(
        self,
        file_name,
        record_count
    ):

        self.write_title(
            "CORE"
        )

        self.info(
            f"Archivo: "
            f"{file_name}"
        )

        self.info(
            f"Registros: "
            f"{record_count:,}"
        )

    def log_extension(
        self,
        file_name,
        record_count
    ):

        self.write_title(
            "EXTENSION"
        )

        self.info(
            f"Archivo: "
            f"{file_name}"
        )

        self.info(
            f"Registros: "
            f"{record_count:,}"
        )

    def log_output(
        self,
        output_zip
    ):

        self.write_title(
            "RESULTADO"
        )

        self.info(
            f"ZIP generado: "
            f"{output_zip}"
        )

    def log_exception(
        self,
        exception
    ):

        self.write_title(
            "ERROR"
        )

        self.error(
            str(exception)
        )

    def finish(
        self
    ):

        self.separator()

        self.info(
            "FIN DEL PROCESO"
        )

        self.separator()