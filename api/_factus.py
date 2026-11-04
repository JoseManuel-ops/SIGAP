# Cliente de Factus Facturación. El token OAuth se guarda en la base de datos: en serverless
# no hay memoria entre peticiones.
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session

from api._db import ConfiguracionError
from api._factus_pay import ErrorFactus
from api._modelos import FactusToken

# La DIAN puede demorar. La función de Vercel tiene 30 s (ver vercel.json).
TIEMPO_MAXIMO_S = 25
# Renueva un minuto antes de vencer para que el token no expire a mitad de una petición.
MARGEN_RENOVACION = timedelta(seconds=60)


def _url() -> str:
    url = os.getenv("FACTUS_URL")
    if not url:
        raise ConfiguracionError("Falta la variable de entorno FACTUS_URL")
    return url.rstrip("/")


def _credenciales() -> dict:
    nombres = {
        "client_id": "FACTUS_CLIENT_ID",
        "client_secret": "FACTUS_CLIENT_SECRET",
        "username": "FACTUS_USERNAME",
        "password": "FACTUS_PASSWORD",
    }
    valores = {campo: os.getenv(variable) for campo, variable in nombres.items()}
    if not all(valores.values()):
        raise ConfiguracionError("Faltan credenciales de Factus (FACTUS_CLIENT_ID y demás)")
    return valores


# Devuelve la respuesta de /oauth/token, o None si Factus rechazó los datos.
def _pedir_token(datos: dict) -> dict | None:
    try:
        respuesta = httpx.post(
            f"{_url()}/oauth/token",
            data=datos,
            headers={"Accept": "application/json"},
            timeout=TIEMPO_MAXIMO_S,
        )
    except httpx.TimeoutException:
        raise ErrorFactus(504, "Factus tardó demasiado en autenticar. Intenta de nuevo.")
    except httpx.HTTPError:
        raise ErrorFactus(502, "No se pudo conectar con Factus. Intenta de nuevo.")
    return respuesta.json() if respuesta.is_success else None


def _guardar_token(sesion: Session, respuesta: dict) -> str:
    fila = sesion.get(FactusToken, 1) or FactusToken(id=1)
    fila.access_token = respuesta["access_token"]
    fila.refresh_token = respuesta.get("refresh_token")
    fila.expires_at = datetime.now(timezone.utc) + timedelta(seconds=respuesta.get("expires_in", 3600))
    fila.updated_at = datetime.now(timezone.utc)
    sesion.add(fila)
    sesion.commit()
    return fila.access_token


# Renueva con refresh_token. Si no sirve (venció o ya se usó), inicia sesión de nuevo con la clave.
def _renovar_token(sesion: Session) -> str:
    credenciales = _credenciales()
    fila = sesion.get(FactusToken, 1)
    respuesta = None
    if fila and fila.refresh_token:
        respuesta = _pedir_token({
            "grant_type": "refresh_token",
            "client_id": credenciales["client_id"],
            "client_secret": credenciales["client_secret"],
            "refresh_token": fila.refresh_token,
        })
    if respuesta is None:
        respuesta = _pedir_token({"grant_type": "password", **credenciales})
    if respuesta is None:
        raise ErrorFactus(502, "Factus rechazó las credenciales configuradas (FACTUS_USERNAME y demás).")
    return _guardar_token(sesion, respuesta)


def _token_vigente(sesion: Session) -> str:
    fila = sesion.get(FactusToken, 1)
    if fila and fila.expires_at > datetime.now(timezone.utc) + MARGEN_RENOVACION:
        return fila.access_token
    return _renovar_token(sesion)


# Convierte los errores de validación de Factus en un texto legible.
def _detalle_validacion(cuerpo: dict) -> str:
    datos = cuerpo.get("data")
    errores = (datos.get("errors") if isinstance(datos, dict) else None) or cuerpo.get("errors") or {}
    if isinstance(errores, dict) and errores:
        partes = []
        for campo, mensajes in errores.items():
            texto = "; ".join(map(str, mensajes)) if isinstance(mensajes, list) else str(mensajes)
            partes.append(f"{campo}: {texto}")
        return " | ".join(partes)
    return cuerpo.get("message") or "datos inválidos"


def _traducir_error(respuesta: httpx.Response, mensaje_409: str) -> ErrorFactus:
    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = {}
    if respuesta.status_code == 409:
        return ErrorFactus(409, mensaje_409)
    if respuesta.status_code == 404:
        return ErrorFactus(404, "Factus no encontró ese documento.")
    if respuesta.status_code in (400, 422):
        return ErrorFactus(422, f"Factus rechazó el documento: {_detalle_validacion(cuerpo)}")
    if respuesta.status_code in (401, 403):
        return ErrorFactus(502, "Factus rechazó la autenticación después de renovar el token.")
    return ErrorFactus(502, f"Factus respondió con un error ({respuesta.status_code}). {cuerpo.get('message', '')}".strip())


# Petición autenticada. Ante un 401 renueva el token y reintenta una sola vez.
def pedir(sesion: Session, metodo: str, ruta: str, mensaje_409: str = "Factus reportó un conflicto.", **opciones) -> dict:
    token = _token_vigente(sesion)
    for intento in (1, 2):
        try:
            respuesta = httpx.request(
                metodo,
                f"{_url()}{ruta}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=TIEMPO_MAXIMO_S,
                **opciones,
            )
        except httpx.TimeoutException:
            raise ErrorFactus(504, "Factus tardó demasiado en responder. Reintenta: con la misma referencia no se duplica el documento.")
        except httpx.HTTPError:
            raise ErrorFactus(502, "No se pudo conectar con Factus. Intenta de nuevo.")

        if respuesta.status_code == 401 and intento == 1:
            token = _renovar_token(sesion)
            continue
        if not respuesta.is_success:
            raise _traducir_error(respuesta, mensaje_409)
        try:
            return respuesta.json()
        except ValueError:
            raise ErrorFactus(502, "Factus devolvió una respuesta inválida.")
    raise ErrorFactus(502, "Factus rechazó la autenticación después de renovar el token.")


# Busca el rango activo y vigente de un tipo de documento, por ejemplo "Factura de Venta".
def rango_activo(sesion: Session, documento: str, prefijo: str | None = None) -> int:
    respuesta = pedir(sesion, "GET", "/v2/numbering-ranges", params={"filter[is_active]": 1})
    for rango in respuesta["data"]["data"]:
        if (
            rango["document"] == documento
            and rango["is_active"]
            and not rango["is_expired"]
            and rango["deleted_at"] is None
            and (prefijo is None or rango["prefix"] == prefijo)
        ):
            return rango["id"]
    raise ErrorFactus(502, f"Factus no tiene un rango de numeración activo para «{documento}».")
