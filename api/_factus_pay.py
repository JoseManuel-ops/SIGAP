# Cliente de Factus Pay (cobros QR). El token se lee de FACTUS_PAY_TOKEN.
# Nunca se llama a /auth desde aquí: cada /auth anula el token anterior.
import os
from datetime import datetime, timedelta, timezone

import httpx

from api._db import ConfiguracionError

ZONA_COLOMBIA = timezone(timedelta(hours=-5))

# Menor que el límite de la función serverless, para poder responder con un error claro.
TIEMPO_MAXIMO_S = 8


class ErrorFactus(Exception):
    """Falla de una API de Factus, con el código y el mensaje que verá el usuario.

    Nunca se usa 401 hacia el frontend: allí significa que la sesión de SIGAP venció.
    """

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# Convierte "04-11-2026 01:37:19 PM" (hora Colombia) en una fecha con zona horaria.
def parsear_fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%d-%m-%Y %I:%M:%S %p").replace(tzinfo=ZONA_COLOMBIA)
    except ValueError:
        return None


def _configuracion() -> tuple[str, str]:
    url, token = os.getenv("FACTUS_PAY_URL"), os.getenv("FACTUS_PAY_TOKEN")
    if not url or not token:
        raise ConfiguracionError("Faltan FACTUS_PAY_URL o FACTUS_PAY_TOKEN")
    return url.rstrip("/"), token


def _pedir(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    url, token = _configuracion()
    try:
        respuesta = httpx.request(
            metodo,
            f"{url}{ruta}",
            json=cuerpo,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=TIEMPO_MAXIMO_S,
        )
    except httpx.TimeoutException:
        raise ErrorFactus(504, "Factus Pay tardó demasiado en responder. Intenta de nuevo.")
    except httpx.HTTPError:
        raise ErrorFactus(502, "No se pudo conectar con Factus Pay. Intenta de nuevo.")

    try:
        datos = respuesta.json()
    except ValueError:
        datos = {}

    if respuesta.status_code in (401, 403):
        raise ErrorFactus(502, "Factus Pay rechazó el token configurado (FACTUS_PAY_TOKEN).")
    if respuesta.status_code == 404:
        raise ErrorFactus(404, "Factus Pay no tiene un cobro con esa referencia.")
    if respuesta.status_code == 422:
        raise ErrorFactus(422, f"Factus Pay rechazó el cobro: {datos.get('message', 'datos inválidos')}")
    if not respuesta.is_success or not isinstance(datos.get("data"), dict):
        raise ErrorFactus(502, f"Factus Pay respondió con un error ({respuesta.status_code}).")
    return datos["data"]


# Crea el cobro. Con la misma referencia devuelve el existente; si su QR ya venció, lo renueva.
def crear_cobro(reference_code: str, monto: int, expiracion_s: int) -> dict:
    return _pedir(
        "POST",
        "/v1/collections",
        {"reference_code": reference_code, "amount": monto, "expiration": expiracion_s},
    )


def consultar_cobro(reference_code: str) -> dict:
    return _pedir("GET", f"/v1/collections/{reference_code}")
