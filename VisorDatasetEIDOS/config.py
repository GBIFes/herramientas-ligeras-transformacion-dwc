# config.py

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://pro.iepnb.gob.es/api/especie"

REQUEST_TIMEOUT = 60

CATEGORY_ENDPOINTS = {
    "CR": "",
    "EN": "",
    "VU": "",
    "LESRPE_CEEA": "",
    "CEEEI": ""
}


def create_session():

    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504
        ],
        allowed_methods=[
            "GET"
        ]
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=20
    )

    session = Session()

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        "User-Agent": "EIDOS Biodiversity Matrix/1.0"
    })

    return session
