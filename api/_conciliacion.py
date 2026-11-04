# Conciliación: cruza lo cobrado en Factus Pay con lo facturado en Factus.
from sqlmodel import Session, select

from api._despachos import estado_visible
from api._modelos import Cobro, Despacho, Factura, Jaula, Lote


def _alerta(despacho: Despacho, cobro: Cobro | None, factura: Factura | None) -> str | None:
    cobrado = cobro is not None and cobro.status == "paid"
    facturado = factura is not None and bool(factura.number)
    if cobrado and cobro.paid_amount != despacho.total:
        return "Monto pagado distinto al total"
    if cobrado and not facturado:
        return "Pagado sin factura"
    if facturado and not cobrado:
        return "Facturado sin pago"
    return None


def consultar(sesion: Session) -> dict:
    filas = sesion.exec(
        select(Despacho, Jaula.codigo, Cobro, Factura)
        .join(Lote, Despacho.lote_id == Lote.id)
        .join(Jaula, Lote.jaula_id == Jaula.id)
        .join(Cobro, Cobro.reference_code == Despacho.reference_code, isouter=True)
        .join(Factura, Factura.reference_code == Despacho.reference_code, isouter=True)
        .order_by(Despacho.fecha.desc())
    ).all()

    registros = []
    recaudado = facturado = historico = 0
    for despacho, jaula, cobro, factura in filas:
        tiene_factura = factura is not None and bool(factura.number)

        # Los históricos no pasaron por Factus: no tienen cobro ni factura que conciliar,
        # así que van aparte y no alteran la diferencia.
        if despacho.is_demo:
            historico += despacho.total
        else:
            if cobro is not None and cobro.status == "paid":
                recaudado += cobro.paid_amount or 0
            # Una factura anulada con nota crédito deja de contar como facturado.
            if tiene_factura and despacho.estado != "anulado":
                facturado += despacho.total

        registros.append({
            "reference_code": despacho.reference_code,
            "jaula": jaula,
            "kilos": despacho.kilos,
            "total": despacho.total,
            "estado": estado_visible(despacho, cobro),
            "is_demo": despacho.is_demo,
            "estado_cobro": cobro.status if cobro else None,
            "fecha_pago": cobro.collected_at if cobro else None,
            "numero_factura": factura.number if factura else None,
            "cufe": factura.cufe if factura else None,
            "enlace_factura": factura.public_url if factura else None,
            "alerta": None if despacho.is_demo else _alerta(despacho, cobro, factura),
        })

    return {
        "totales": {
            "recaudado": recaudado,
            "facturado": facturado,
            "diferencia": recaudado - facturado,
            "historico_demo": historico,
        },
        "registros": registros,
    }
