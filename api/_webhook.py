# Webhook de Factus Pay. Solo valida, registra y responde: sin llamadas externas ni tareas
# en segundo plano. La factura se emite después, en un endpoint aparte.
import hmac
import logging
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlmodel import Session

from api._db import ConfiguracionError, variable
from api._despachos import registrar_pago
from api._factus_pay import parsear_fecha

logger = logging.getLogger("sigap")

MONTO_MAXIMO_REPORTADO = 1_000_000_000


def validar_llave(llave: str | None) -> None:
    esperada = variable("FACTUS_WEBHOOK_KEY")
    if not esperada:
        raise ConfiguracionError("Falta la variable de entorno FACTUS_WEBHOOK_KEY")
    # Comparación de tiempo constante: el tiempo de respuesta no revela cuánto acertó.
    if not hmac.compare_digest((llave or "").encode(), esperada.encode()):
        raise HTTPException(status_code=401, detail="Llave inválida")


# Siempre responde 200 si la llave es válida: Factus reintenta ante otro código, y reintentar
# no arregla una referencia desconocida o un monto distinto. Esos casos quedan en el log.
def procesar(sesion: Session, cuerpo: dict) -> dict:
    datos = cuerpo.get("data") if isinstance(cuerpo, dict) else None
    if not isinstance(datos, dict):
        logger.warning("Webhook sin campo data")
        return {"resultado": "ignorado"}

    reference_code = datos.get("reference_code")
    if datos.get("status") != "paid" or not isinstance(reference_code, str):
        return {"resultado": "ignorado"}

    try:
        monto = Decimal(str(datos.get("amount")))
        # Fuera de este rango no es un monto real (y no cabría en la base de datos).
        if not monto.is_finite() or not 0 <= monto <= MONTO_MAXIMO_REPORTADO:
            raise InvalidOperation
    except InvalidOperation:
        logger.warning("Webhook con monto inválido para %s", reference_code)
        return {"resultado": "ignorado"}

    payer = datos.get("payer") if isinstance(datos.get("payer"), dict) else None
    aceptado = registrar_pago(sesion, reference_code, monto, parsear_fecha(datos.get("collected_at")), payer)
    sesion.commit()

    if not aceptado:
        logger.warning("Webhook no aplicado a %s: referencia desconocida o monto distinto", reference_code)
        return {"resultado": "no_aplicado"}
    return {"resultado": "ok"}
