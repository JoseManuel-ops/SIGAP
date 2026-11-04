# Emisión de la factura electrónica de un despacho pagado.
from fastapi import HTTPException
from sqlmodel import Session, select

from api._despachos import obtener
from api._factus import pedir, rango_activo
from api._factus_pay import ErrorFactus, parsear_fecha
from api._modelos import Cobro, Comprador, Despacho, Factura, Jaula, Lote

# Códigos de las tablas de referencia de Factus (son catálogos fijos, sin endpoint en la v2).
DOCUMENTO_FACTURA_VENTA = "01"
OPERACION_ESTANDAR = "10"
PAGO_DE_CONTADO = "1"
MEDIO_TRANSFERENCIA = "47"
UNIDAD_KILOGRAMO = "KGM"
ESTANDAR_DEL_CONTRIBUYENTE = "999"
TRIBUTO_IVA = "01"
CEDULA = "13"
PERSONA_NATURAL = "2"
TRIBUTO_NO_APLICA = "ZZ"

MENSAJE_409 = (
    "Factus tiene una factura pendiente de enviar a la DIAN y no deja crear otra hasta resolverla. "
    "Elimínala desde el panel de Factus (o revísala allí) y vuelve a pulsar «Facturar»."
)


def armar_factura(despacho: Despacho, comprador: Comprador, jaula: str, lote: str, breb_key: str | None, rango_id: int) -> dict:
    return {
        "reference_code": despacho.reference_code,
        "document": DOCUMENTO_FACTURA_VENTA,
        "numbering_range_id": rango_id,
        "operation_type": OPERACION_ESTANDAR,
        "send_email": False,
        "observation": f"Jaula {jaula}, lote {lote}, referencia Bre-B {breb_key or 'no disponible'}",
        "payment_details": [{
            "payment_form": PAGO_DE_CONTADO,
            "payment_method_code": MEDIO_TRANSFERENCIA,
            "amount": f"{despacho.total}.00",
        }],
        "customer": {
            "identification_document_code": comprador.identification_document_code or CEDULA,
            "identification": comprador.identification,
            "legal_organization_code": comprador.legal_organization_code or PERSONA_NATURAL,
            "tribute_code": TRIBUTO_NO_APLICA,
            "names": comprador.names,
            "address": comprador.address,
            "email": comprador.email,
            "phone": comprador.phone,
            "country_code": "CO",
            "municipality_code": comprador.municipio_codigo_factus,
        },
        "items": [{
            "code_reference": "TILAPIA-ROJA-FRESCA",
            "name": f"Tilapia roja entera fresca - Jaula {jaula}",
            "quantity": f"{despacho.kilos:.2f}",
            "price": f"{despacho.precio_kg}.00",
            "unit_measure_code": UNIDAD_KILOGRAMO,
            "standard_code": ESTANDAR_DEL_CONTRIBUYENTE,
            # IVA 0 %: tilapia fresca.
            "taxes": [{"code": TRIBUTO_IVA, "rate": "0.00", "is_excluded": False}],
        }],
    }


def _datos_de_factura(sesion: Session, reference_code: str) -> tuple:
    fila = sesion.exec(
        select(Despacho, Comprador, Jaula.codigo, Lote.codigo)
        .join(Comprador, Despacho.comprador_id == Comprador.id)
        .join(Lote, Despacho.lote_id == Lote.id)
        .join(Jaula, Lote.jaula_id == Jaula.id)
        .where(Despacho.reference_code == reference_code)
    ).first()
    if fila is None:
        raise HTTPException(status_code=404, detail="No existe ese despacho")
    return fila


# Solo si está pagado y sin factura. Repetir la llamada devuelve lo mismo, sin emitir de nuevo.
def facturar(sesion: Session, reference_code: str) -> dict:
    despacho, comprador, jaula, lote = _datos_de_factura(sesion, reference_code)
    if despacho.is_demo:
        raise HTTPException(status_code=409, detail="Los despachos históricos de demostración no se facturan")

    existente = sesion.exec(select(Factura).where(Factura.reference_code == reference_code)).first()
    if existente and existente.number:
        return obtener(sesion, reference_code)
    if despacho.estado != "pagado":
        raise HTTPException(status_code=409, detail=f"Solo se factura un despacho pagado (estado actual: {despacho.estado})")

    cobro = sesion.exec(select(Cobro).where(Cobro.reference_code == reference_code)).first()
    if not comprador.municipio_codigo_factus:
        raise HTTPException(status_code=422, detail="El comprador no tiene código de municipio de Factus")

    cuerpo = armar_factura(despacho, comprador, jaula, lote, cobro.breb_key if cobro else None, rango_activo(sesion, "Factura de Venta"))
    # Si Factus ya procesó esta referencia, devuelve la factura existente en vez de duplicarla.
    respuesta = pedir(sesion, "POST", "/v2/bills/validate", mensaje_409=MENSAJE_409, json=cuerpo)
    datos = respuesta.get("data") or {}

    if not datos.get("number") or not datos.get("is_validated"):
        raise ErrorFactus(409, MENSAJE_409)

    # Bloquea el despacho: una petición simultánea no puede guardar la factura dos veces.
    despacho = sesion.exec(
        select(Despacho).where(Despacho.reference_code == reference_code).with_for_update()
    ).one()
    factura = sesion.exec(select(Factura).where(Factura.reference_code == reference_code)).first()
    if factura is None or not factura.number:
        factura = factura or Factura(reference_code=reference_code)
        enlaces = datos.get("links") or {}
        factura.number = datos["number"]
        factura.cufe = datos.get("cufe")
        factura.public_url = enlaces.get("public_url")
        factura.qr_url = enlaces.get("qr")
        factura.validated_at = parsear_fecha(datos.get("validated_at"))
        sesion.add(factura)
        despacho.estado = "facturado"
        sesion.add(despacho)
    sesion.commit()
    return obtener(sesion, reference_code)


# El PDF sale de Factus en base64 y lo descarga el navegador.
def descargar_pdf(sesion: Session, reference_code: str) -> dict:
    factura = sesion.exec(select(Factura).where(Factura.reference_code == reference_code)).first()
    if factura is None or not factura.number:
        raise HTTPException(status_code=404, detail="Este despacho no tiene factura")
    respuesta = pedir(sesion, "GET", f"/v2/bills/{factura.number}/download-pdf")
    datos = respuesta.get("data") or {}
    if not datos.get("pdf_base_64_encoded"):
        raise ErrorFactus(502, "Factus no devolvió el PDF de la factura.")
    return {
        "nombre": datos.get("file_name") or f"factura-{factura.number}",
        "pdf_base64": datos["pdf_base_64_encoded"],
    }
