# Despachos y cobros: creación, consulta, verificación y regeneración del QR.
import secrets
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from api._factus_pay import ErrorFactus, consultar_cobro, crear_cobro, parsear_fecha
from api._jaulas import consultar_resumenes
from api._modelos import Cobro, Comprador, Despacho, Factura, Jaula, Lote

PRECIO_KG = 10_000
KILOS_MAXIMOS = Decimal(1200)
# Mínimo real del sandbox: Factus Pay rechaza montos menores a $10.000 aunque la guía diga $1.000.
TOTAL_MINIMO = 10_000
TOTAL_MAXIMO = 12_100_000
EXPIRACION_QR_S = 1800

# En estos estados ya no se puede cobrar de nuevo.
ESTADOS_COBRADOS = ("pagado", "facturado", "anulado")


def ahora() -> datetime:
    return datetime.now(timezone.utc)


# Factus sigue reportando "ready" cuando el QR vence, así que el vencimiento se calcula aquí.
def estado_visible(despacho: Despacho, cobro: Cobro | None) -> str:
    if despacho.estado == "pendiente" and cobro and cobro.expires_at and cobro.expires_at <= ahora():
        return "expirado"
    return despacho.estado


def a_dict(despacho: Despacho, codigo_jaula: str, comprador: str, cobro: Cobro | None, factura: Factura | None = None) -> dict:
    return {
        "reference_code": despacho.reference_code,
        "jaula": codigo_jaula,
        "comprador": comprador,
        "fecha": despacho.fecha,
        "kilos": despacho.kilos,
        "precio_kg": despacho.precio_kg,
        "total": despacho.total,
        "estado": estado_visible(despacho, cobro),
        "is_demo": despacho.is_demo,
        "cobro": None if cobro is None else {
            "status": cobro.status,
            "breb_key": cobro.breb_key,
            "expires_at": cobro.expires_at,
            "collected_at": cobro.collected_at,
            "paid_amount": cobro.paid_amount,
            # El pago llegó, pero no coincide con el total: el despacho no se marca pagado.
            "monto_no_coincide": cobro.paid_amount is not None and cobro.paid_amount != despacho.total,
        },
        "factura": None if factura is None or not factura.number else {
            "number": factura.number,
            "cufe": factura.cufe,
            "public_url": factura.public_url,
            "qr_url": factura.qr_url,
            "validated_at": factura.validated_at,
        },
    }


def _consulta_base():
    return (
        select(Despacho, Jaula.codigo, Comprador.names, Cobro, Factura)
        .join(Lote, Despacho.lote_id == Lote.id)
        .join(Jaula, Lote.jaula_id == Jaula.id)
        .join(Comprador, Despacho.comprador_id == Comprador.id)
        .join(Cobro, Cobro.reference_code == Despacho.reference_code, isouter=True)
        .join(Factura, Factura.reference_code == Despacho.reference_code, isouter=True)
    )


def listar(sesion: Session) -> list[dict]:
    filas = sesion.exec(_consulta_base().order_by(Despacho.fecha.desc())).all()
    return [a_dict(*fila) for fila in filas]


def obtener(sesion: Session, reference_code: str) -> dict:
    fila = sesion.exec(_consulta_base().where(Despacho.reference_code == reference_code)).first()
    if fila is None:
        raise HTTPException(status_code=404, detail="No existe ese despacho")
    detalle = a_dict(*fila)
    if fila[3] is not None:
        detalle["cobro"]["qr"] = fila[3].qr
    return detalle


# Vista pública para quien paga: solo monto, estado, QR, llave y vencimiento.
def obtener_publico(sesion: Session, reference_code: str) -> dict:
    fila = sesion.exec(
        select(Despacho, Cobro)
        .join(Cobro, Cobro.reference_code == Despacho.reference_code)
        .where(Despacho.reference_code == reference_code, Despacho.is_demo == False)  # noqa: E712
    ).first()
    if fila is None:
        raise HTTPException(status_code=404, detail="No encontramos este cobro")
    despacho, cobro = fila
    return {
        "monto": despacho.total,
        "estado": estado_visible(despacho, cobro),
        "qr": cobro.qr,
        "breb_key": cobro.breb_key,
        "expires_at": cobro.expires_at,
    }


# Kilos reservados por despachos pendientes con QR vigente. Si no se pudo crear el QR, la
# reserva dura lo mismo que duraría uno, para que un fallo de Factus no la deje para siempre.
def _kilos_reservados(sesion: Session, lote_id: int) -> Decimal:
    reservados = sesion.exec(
        select(func.coalesce(func.sum(Despacho.kilos), 0))
        .join(Cobro, Cobro.reference_code == Despacho.reference_code, isouter=True)
        .where(
            Despacho.lote_id == lote_id,
            Despacho.estado == "pendiente",
            (Cobro.expires_at > ahora())
            | ((Cobro.id == None) & (Despacho.fecha > ahora() - timedelta(seconds=EXPIRACION_QR_S))),  # noqa: E711
        )
    ).one()
    return Decimal(reservados)


def _guardar_cobro(sesion: Session, reference_code: str, monto: int, datos: dict) -> Cobro:
    cobro = sesion.exec(select(Cobro).where(Cobro.reference_code == reference_code)).first()
    if cobro is None:
        cobro = Cobro(reference_code=reference_code, amount=monto, status=datos.get("status", "ready"))
    cobro.status = datos.get("status", cobro.status)
    cobro.breb_key = datos.get("breb_key", cobro.breb_key)
    cobro.qr = datos.get("qr", cobro.qr)
    cobro.expires_at = parsear_fecha(datos.get("qr_expires_at")) or cobro.expires_at
    sesion.add(cobro)
    return cobro


# Aplica un pago reportado por Factus. Lo usan el webhook y "Verificar pago". Es idempotente.
# El llamador hace commit. Devuelve False si el monto no coincide con el total.
def registrar_pago(
    sesion: Session,
    reference_code: str,
    monto: Decimal,
    collected_at: datetime | None,
    payer: dict | None,
) -> bool:
    despacho = sesion.exec(
        select(Despacho).where(Despacho.reference_code == reference_code).with_for_update()
    ).first()
    if despacho is None:
        return False
    if despacho.estado in ESTADOS_COBRADOS:
        return True

    cobro = sesion.exec(select(Cobro).where(Cobro.reference_code == reference_code)).first()
    if cobro is None:
        cobro = Cobro(reference_code=reference_code, amount=despacho.total, status="paid")
    cobro.status = "paid"
    cobro.paid_amount = int(monto.to_integral_value(ROUND_HALF_UP))
    cobro.collected_at = collected_at or ahora()
    if payer:
        cobro.payer = payer
    sesion.add(cobro)

    # Comparación exacta, con decimales: $10.000,50 no es igual a $10.000.
    if monto != Decimal(despacho.total):
        return False
    despacho.estado = "pagado"
    sesion.add(despacho)
    return True


def crear(sesion: Session, codigo_jaula: str, comprador_id: int, kilos: Decimal) -> dict:
    if kilos != kilos.quantize(Decimal("0.01")):
        raise HTTPException(status_code=422, detail="Los kilos admiten máximo dos decimales")
    if kilos <= 0:
        raise HTTPException(status_code=422, detail="Los kilos deben ser mayores que cero")
    if kilos > KILOS_MAXIMOS:
        raise HTTPException(status_code=422, detail=f"Un despacho admite máximo {KILOS_MAXIMOS} kg")

    total = int(kilos * PRECIO_KG)
    if not TOTAL_MINIMO <= total <= TOTAL_MAXIMO:
        raise HTTPException(
            status_code=422,
            detail=f"El total debe estar entre ${TOTAL_MINIMO:,} y ${TOTAL_MAXIMO:,}".replace(",", "."),
        )

    codigo_jaula = codigo_jaula.upper()
    if sesion.get(Comprador, comprador_id) is None:
        raise HTTPException(status_code=422, detail="El comprador no existe")

    resumenes = consultar_resumenes(sesion, codigo_jaula)
    if not resumenes:
        raise HTTPException(status_code=422, detail=f"La jaula {codigo_jaula} no existe")
    if resumenes[0]["lote"] is None:
        raise HTTPException(status_code=422, detail=f"La jaula {codigo_jaula} no tiene un lote activo")

    # Bloquea el lote: dos despachos simultáneos no pueden vender la misma biomasa.
    lote = sesion.exec(
        select(Lote)
        .join(Jaula, Lote.jaula_id == Jaula.id)
        .where(Jaula.codigo == codigo_jaula, Lote.fase != "cerrado")
        .with_for_update()
    ).one()
    disponible = resumenes[0]["lote"]["biomasa_actual_kg"] - _kilos_reservados(sesion, lote.id)
    if kilos > disponible:
        raise HTTPException(
            status_code=422,
            detail=f"Solo hay {max(disponible, Decimal(0)):.1f} kg disponibles en {codigo_jaula}",
        )

    # 64 bits aleatorios: la página pública de pago no se puede adivinar.
    reference_code = f"SIGAP-{codigo_jaula.replace('-', '')}-{secrets.token_hex(8).upper()}"
    sesion.add(Despacho(
        reference_code=reference_code,
        lote_id=lote.id,
        comprador_id=comprador_id,
        fecha=ahora(),
        kilos=kilos,
        precio_kg=PRECIO_KG,
        total=total,
    ))
    # Se guarda antes de llamar a Factus: si el cobro falla, el despacho no se pierde.
    sesion.commit()

    error_cobro = None
    try:
        datos = crear_cobro(reference_code, total, EXPIRACION_QR_S)
        _guardar_cobro(sesion, reference_code, total, datos)
        sesion.commit()
    except ErrorFactus as error:
        error_cobro = error.detail

    return {**obtener(sesion, reference_code), "error_cobro": error_cobro}


def _despacho_real(sesion: Session, reference_code: str) -> Despacho:
    despacho = sesion.exec(select(Despacho).where(Despacho.reference_code == reference_code)).first()
    if despacho is None:
        raise HTTPException(status_code=404, detail="No existe ese despacho")
    if despacho.is_demo:
        raise HTTPException(status_code=409, detail="Los despachos históricos de demostración no tienen cobro")
    return despacho


# Consulta el cobro en Factus Pay y actualiza el estado del despacho.
def verificar(sesion: Session, reference_code: str) -> dict:
    despacho = _despacho_real(sesion, reference_code)
    # Termina la transacción de lectura: no se deja abierta durante la llamada a Factus.
    sesion.commit()
    datos = consultar_cobro(reference_code)

    aviso = None
    if datos.get("status") == "paid":
        monto = Decimal(str(datos.get("amount", "0")))
        if not registrar_pago(sesion, reference_code, monto, parsear_fecha(datos.get("collected_at")), datos.get("payer")):
            aviso = f"El pago reportado (${int(monto):,}) no coincide con el total del despacho.".replace(",", ".")
    else:
        despacho = sesion.exec(
            select(Despacho).where(Despacho.reference_code == reference_code).with_for_update()
        ).one()
        if despacho.estado not in ESTADOS_COBRADOS:
            cobro = _guardar_cobro(sesion, reference_code, despacho.total, datos)
            if datos.get("status") == "failed":
                despacho.estado = "fallido"
            else:
                despacho.estado = estado_visible(despacho, cobro) if despacho.estado == "pendiente" else despacho.estado
            sesion.add(despacho)
    sesion.commit()
    return {**obtener(sesion, reference_code), "aviso": aviso}


# Pide un QR nuevo con la misma referencia y monto. Factus solo lo renueva si el anterior ya venció.
def regenerar_qr(sesion: Session, reference_code: str) -> dict:
    despacho = _despacho_real(sesion, reference_code)
    if despacho.estado in ESTADOS_COBRADOS:
        raise HTTPException(status_code=409, detail=f"Este despacho ya está {despacho.estado}: no se puede regenerar el QR")
    total = despacho.total
    cobro_previo = sesion.exec(select(Cobro).where(Cobro.reference_code == reference_code)).first()
    vencimiento_previo = cobro_previo.expires_at if cobro_previo else None
    sesion.commit()

    # Antes de renovar se confirma que no lo hayan pagado mientras tanto.
    if cobro_previo is not None:
        try:
            actual = consultar_cobro(reference_code)
        except ErrorFactus as error:
            if error.status_code != 404:
                raise
        else:
            if actual.get("status") == "paid":
                return verificar(sesion, reference_code)

    datos = crear_cobro(reference_code, total, EXPIRACION_QR_S)

    despacho = sesion.exec(
        select(Despacho).where(Despacho.reference_code == reference_code).with_for_update()
    ).one()
    if despacho.estado in ESTADOS_COBRADOS:
        sesion.rollback()
        return {**obtener(sesion, reference_code), "aviso": None}
    cobro = _guardar_cobro(sesion, reference_code, total, datos)
    despacho.estado = "pendiente"
    sesion.add(despacho)
    sesion.commit()

    aviso = None
    if vencimiento_previo and cobro.expires_at and cobro.expires_at <= vencimiento_previo:
        aviso = "El QR actual sigue vigente. Factus Pay solo genera uno nuevo cuando el anterior vence."
    return {**obtener(sesion, reference_code), "aviso": aviso}
