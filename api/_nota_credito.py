# Anulación de una factura validada con nota crédito.
from fastapi import HTTPException
from sqlmodel import Session, select

from api._despachos import obtener
from api._facturas import _datos_de_factura, armar_factura
from api._factus import pedir, rango_activo
from api._factus_pay import ErrorFactus, parsear_fecha
from api._modelos import Despacho, Factura

CONCEPTO_ANULACION = "2"
NOTA_CON_REFERENCIA_A_FACTURA = "20"
# Factus tiene dos rangos activos de nota crédito y exige indicar uno. "NC" es el estándar.
PREFIJO_RANGO = "NC"

MENSAJE_409 = (
    "Factus tiene una nota crédito pendiente de enviar a la DIAN y no deja crear otra hasta resolverla. "
    "Revísala en el panel de Factus y vuelve a intentar."
)


def anular(sesion: Session, reference_code: str, motivo: str) -> dict:
    despacho, comprador, jaula, lote = _datos_de_factura(sesion, reference_code)
    if despacho.is_demo:
        raise HTTPException(status_code=409, detail="Los despachos históricos de demostración no tienen factura que anular")
    if despacho.estado == "anulado":
        return obtener(sesion, reference_code)
    factura = sesion.exec(select(Factura).where(Factura.reference_code == reference_code)).first()
    if despacho.estado != "facturado" or factura is None or not factura.number:
        raise HTTPException(status_code=409, detail="Solo se anula un despacho facturado")

    # Repite ítems y cliente de la factura original: la nota la anula por el valor total.
    original = armar_factura(despacho, comprador, jaula, lote, None, 0)
    cuerpo = {
        # Referencia fija: repetir la anulación devuelve la misma nota, no crea otra.
        "reference_code": f"NC-{reference_code}",
        "correction_concept_code": CONCEPTO_ANULACION,
        "customization_id": NOTA_CON_REFERENCIA_A_FACTURA,
        "bill_number": factura.number,
        "numbering_range_id": rango_activo(sesion, "Nota Crédito", PREFIJO_RANGO),
        "observation": f"Anula la factura {factura.number}. Motivo: {motivo}"[:500],
        "payment_details": original["payment_details"],
        "customer": original["customer"],
        "items": original["items"],
    }
    respuesta = pedir(sesion, "POST", "/v2/credit-notes/validate", mensaje_409=MENSAJE_409, json=cuerpo)
    datos = respuesta.get("data") or {}
    if not datos.get("number") or not datos.get("is_validated", True):
        raise ErrorFactus(409, MENSAJE_409)

    despacho = sesion.exec(
        select(Despacho).where(Despacho.reference_code == reference_code).with_for_update()
    ).one()
    factura = sesion.exec(select(Factura).where(Factura.reference_code == reference_code)).one()
    factura.nota_credito_number = datos["number"]
    factura.nota_credito_cufe = datos.get("cude") or datos.get("cufe")
    factura.nota_credito_public_url = (datos.get("links") or {}).get("public_url")
    factura.anulada_at = parsear_fecha(datos.get("validated_at"))
    sesion.add(factura)
    despacho.estado = "anulado"
    sesion.add(despacho)
    sesion.commit()
    return obtener(sesion, reference_code)
