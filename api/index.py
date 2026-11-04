# Punto de entrada de la API de SIGAP (función serverless de Python en Vercel).
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from api._db import ConfiguracionError, obtener_engine
from api._jaulas import consultar_detalle, consultar_resumenes

app = FastAPI(title="SIGAP API")
logger = logging.getLogger("sigap")


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


# Permite comprobar que la API está en línea.
@app.get("/api/health")
def health():
    return {"status": "ok"}


# Resumen de todas las jaulas: biomasa, densidad, peso, días y alertas.
@app.get("/api/jaulas")
def listar_jaulas():
    with Session(obtener_engine()) as sesion:
        return consultar_resumenes(sesion)


# Detalle de una jaula por su código (por ejemplo, J-04).
@app.get("/api/jaulas/{codigo}")
def ver_jaula(codigo: str):
    with Session(obtener_engine()) as sesion:
        detalle = consultar_detalle(sesion, codigo.upper())
    if detalle is None:
        raise HTTPException(status_code=404, detail=f"No existe la jaula {codigo}")
    return detalle
