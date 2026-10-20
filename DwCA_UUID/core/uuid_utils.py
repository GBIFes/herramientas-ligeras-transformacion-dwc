"""
uuid_utils.py

Utilidades para trabajar con UUID.

Funciones:

- UUID aleatorios (UUID4)
- UUID deterministas (UUID5)
- Validación de UUID
- Obtención de nombres seguros para columnas UUID
- Obtención de nombres seguros para columnas *_Old
- Normalización de identificadores
- Construcción de mapas ID -> UUID
"""

import uuid


# --------------------------------------------------
# UUID GENERATION
# --------------------------------------------------

def generate_random_uuid():
    """
    Genera un UUID aleatorio (UUID4).

    Returns
    -------
    str
    """

    return str(
        uuid.uuid4()
    )


def generate_deterministic_uuid(
    value
):
    """
    Genera un UUID determinista.

    Siempre devuelve el mismo UUID
    para el mismo identificador.

    Parameters
    ----------
    value : any

    Returns
    -------
    str
    """

    value = normalize_identifier(
        value
    )

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_DNS,
            value
        )
    )


def build_uuid(
    value=None,
    deterministic=False
):
    """
    Genera UUID según el modo solicitado.

    Parameters
    ----------
    value : any

    deterministic : bool

    Returns
    -------
    str
    """

    if deterministic:

        return generate_deterministic_uuid(
            value
        )

    return generate_random_uuid()


# --------------------------------------------------
# VALIDATION
# --------------------------------------------------

def is_valid_uuid(
    value
):
    """
    Comprueba si una cadena
    contiene un UUID válido.

    Parameters
    ----------
    value : any

    Returns
    -------
    bool
    """

    if value is None:
        return False

    try:

        uuid.UUID(
            str(value)
        )

        return True

    except Exception:

        return False


# --------------------------------------------------
# NORMALIZATION
# --------------------------------------------------

def normalize_identifier(
    value
):
    """
    Normaliza identificadores.

    None -> ""

    trim espacios.

    Returns
    -------
    str
    """

    if value is None:
        return ""

    return str(
        value
    ).strip()


# --------------------------------------------------
# FIELD NAMES
# --------------------------------------------------

def is_uuid_column(
    field_name
):
    """
    Determina si una columna
    corresponde a UUID.

    Returns
    -------
    bool
    """

    if not field_name:
        return False

    name = str(
        field_name
    ).strip().upper()

    return (
        name == "UUID"
        or
        name.startswith(
            "G_UUID"
        )
    )


def find_available_uuid_column(
    fields
):
    """
    Obtiene:

    UUID

    o

    G_UUID

    o

    G_UUID_2

    etc.

    Parameters
    ----------
    fields : iterable

    Returns
    -------
    str
    """

    existing = {

        str(field)
        .strip()
        .upper()

        for field in fields

    }

    if "UUID" not in existing:
        return "UUID"

    if "G_UUID" not in existing:
        return "G_UUID"

    counter = 2

    while True:

        candidate = (
            f"G_UUID_{counter}"
        )

        if (
            candidate.upper()
            not in existing
        ):
            return candidate

        counter += 1


def safe_old_field_name(
    field_name,
    existing_fields
):
    """
    Obtiene un nombre seguro
    para *_Old.

    Ejemplos:

    occurrenceID
        ->
    occurrenceID_Old

    occurrenceID_Old ya existe
        ->
    occurrenceID_Old2

    occurrenceID_Old2 ya existe
        ->
    occurrenceID_Old3
    """

    field_name = str(
        field_name
    ).strip()

    existing = {

        str(value)
        .strip()
        .upper()

        for value
        in existing_fields

    }

    candidate = (
        f"{field_name}_Old"
    )

    if (
        candidate.upper()
        not in existing
    ):

        return candidate

    counter = 2

    while True:

        candidate = (
            f"{field_name}_Old"
            f"{counter}"
        )

        if (
            candidate.upper()
            not in existing
        ):

            return candidate

        counter += 1


# --------------------------------------------------
# UUID MAP
# --------------------------------------------------

def build_uuid_map(
    identifiers,
    deterministic=False
):
    """
    Construye un diccionario:

    ID original -> UUID

    Parameters
    ----------
    identifiers : iterable

    deterministic : bool

    Returns
    -------
    dict
    """

    result = {}

    for identifier in identifiers:

        key = normalize_identifier(
            identifier
        )

        if key in result:
            continue

        result[key] = build_uuid(
            value=key,
            deterministic=
            deterministic
        )

    return result


def get_uuid_from_map(
    uuid_map,
    identifier
):
    """
    Recupera UUID asociado.

    Parameters
    ----------
    uuid_map : dict

    identifier : any

    Returns
    -------
    str
    """

    key = normalize_identifier(
        identifier
    )

    return uuid_map.get(
        key,
        ""
    )