# Punto de entrada de la API de SIGAP (función serverless de Python en Vercel).
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from api import _conciliacion, _despachos, _facturas, _webhook
from api._auth import solo_admin, usuario_actual
from api._db import ConfiguracionError, obtener_engine
from api._factus_pay import ErrorFactus
from api._jaulas import consultar_detalle, consultar_resumenes
from api._modelos import Comprador

app = FastAPI(title="SIGAP API")
logger = logging.getLogger("sigap")

# Toda ruta de este router exige un token válido. Las públicas se declaran aparte, en app.
protegido = APIRouter(prefix="/api", dependencies=[Depends(usuario_actual)])


# Errores de base de datos: el detalle va al log para no exponer datos de conexión.
@app.exception_handler(SQLAlchemyError)
def error_base_de_datos(_: Request, error: SQLAlchemyError):
    logger.error("Error de base de datos: %s", error)
    return JSONResponse(
        status_code=503,
        content={"detail": "No se pudo consultar la base de datos. Intenta de nuevo."},
    )


@app.exception_handler(ConfiguracionError)
def error_configuracion(_: Request, error: ConfiguracionError):
    logger.error("Error de configuración: %s", error)
    return JSONResponse(
        status_code=500,
        content={"detail": "El servidor no está configurado correctamente."},
    )


@app.exception_handler(ErrorFactus)
def error_factus(_: Request, error: ErrorFactus):
    logger.warning("Error de Factus (%s): %s", error.status_code, error.detail)
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


# Mensaje en español y como texto, que es lo que muestra el frontend.
@app.exception_handler(RequestValidationError)
def error_validacion(_: Request, error: RequestValidationError):
    campos = ", ".join(str(e["loc"][-1]) for e in error.errors())
    return JSONResponse(status_code=422, content={"detail": f"Datos inválidos en: {campos}"})


# Pública: permite comprobar que la API está en línea.
@app.get("/api/health")
def health():
    return {"status": "ok"}


# Pública: la abre quien paga, sin iniciar sesión. Solo expone datos del cobro.
@app.get("/api/pago/{reference_code}")
def ver_pago(reference_code: str):
    with Session(obtener_engine()) as sesion:
        return _despachos.obtener_publico(sesion, reference_code)


# Pública, protegida con la llave de la URL. Factus reintenta si no recibe 200 en 10 s.
@app.post("/api/webhooks/factus-pay")
async def webhook_factus_pay(request: Request, key: str | None = None):
    # La llave se valida antes de leer el cuerpo o tocar la base de datos.
    _webhook.validar_llave(key)
    try:
        cuerpo = await request.json()
    except ValueError:
        return {"resultado": "ignorado"}
    with Session(obtener_engine()) as sesion:
        return _webhook.procesar(sesion, cuerpo)


# Resumen de todas las jaulas: biomasa, densidad, peso, días y alertas.
@protegido.get("/jaulas")
def listar_jaulas():
    with Session(obtener_engine()) as sesion:
        return consultar_resumenes(sesion)


# Detalle de una jaula por su código (por ejemplo, J-04).
@protegido.get("/jaulas/{codigo}")
def ver_jaula(codigo: str):
    with Session(obtener_engine()) as sesion:
        detalle = consultar_detalle(sesion, codigo.upper())
    if detalle is None:
        raise HTTPException(status_code=404, detail=f"No existe la jaula {codigo}")
    return detalle


# Compradores para el formulario de despacho.
@protegido.get("/compradores")
def listar_compradores():
    with Session(obtener_engine()) as sesion:
        compradores = sesion.exec(select(Comprador).order_by(Comprador.names)).all()
        return [{"id": c.id, "names": c.names, "municipio": c.municipio} for c in compradores]


class NuevoDespacho(BaseModel):
    jaula: str
    comprador_id: int
    kilos: Decimal


@protegido.post("/despachos", status_code=201)
def crear_despacho(datos: NuevoDespacho):
    with Session(obtener_engine()) as sesion:
        return _despachos.crear(sesion, datos.jaula, datos.comprador_id, datos.kilos)


@protegido.get("/despachos")
def listar_despachos():
    with Session(obtener_engine()) as sesion:
        return _despachos.listar(sesion)


@protegido.get("/despachos/{reference_code}")
def ver_despacho(reference_code: str):
    with Session(obtener_engine()) as sesion:
        return _despachos.obtener(sesion, reference_code)


@protegido.post("/despachos/{reference_code}/verificar")
def verificar_despacho(reference_code: str):
    with Session(obtener_engine()) as sesion:
        return _despachos.verificar(sesion, reference_code)


@protegido.post("/despachos/{reference_code}/regenerar-qr")
def regenerar_qr(reference_code: str):
    with Session(obtener_engine()) as sesion:
        return _despachos.regenerar_qr(sesion, reference_code)


# Emite la factura de un despacho pagado. Es idempotente.
@protegido.post("/despachos/{reference_code}/facturar")
def facturar_despacho(reference_code: str):
    with Session(obtener_engine()) as sesion:
        return _facturas.facturar(sesion, reference_code)


@protegido.get("/despachos/{reference_code}/factura/pdf")
def descargar_factura(reference_code: str):
    with Session(obtener_engine()) as sesion:
        return _facturas.descargar_pdf(sesion, reference_code)


@protegido.get("/conciliacion", dependencies=[Depends(solo_admin)])
def ver_conciliacion():
    with Session(obtener_engine()) as sesion:
        return _conciliacion.consultar(sesion)


app.include_router(protegido)
