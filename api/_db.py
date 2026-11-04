# Conexión a Supabase Postgres por el pooler (puerto 6543, modo transacción).
# El prefijo "_" evita que Vercel publique este archivo como otra función serverless.
import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlmodel import create_engine

# En local lee el .env; en Vercel no hay archivo y se usan las variables del panel.
load_dotenv()


class ConfiguracionError(RuntimeError):
    """Falta una variable de entorno necesaria o su valor no sirve."""


# Lee una variable sin espacios ni saltos de línea, que se cuelan al pegarla en un panel.
def variable(nombre: str) -> str | None:
    valor = (os.getenv(nombre) or "").strip()
    return valor or None


# Lee una URL base, sin "/" final. Unas comillas o la falta de https:// se reportan aquí,
# con el nombre de la variable, en vez de aparecer luego como un error de conexión.
def url_base(nombre: str) -> str:
    url = variable(nombre)
    if not url:
        raise ConfiguracionError(f"Falta la variable de entorno {nombre}")
    if not url.startswith(("https://", "http://")):
        raise ConfiguracionError(f"{nombre} debe empezar por https:// (revisa comillas o espacios)")
    return url.rstrip("/")


# El engine no guarda conexiones abiertas (NullPool); solo la configuración para abrirlas.
@lru_cache
def obtener_engine() -> Engine:
    url = variable("DATABASE_URL")
    if not url:
        raise ConfiguracionError("Falta la variable de entorno DATABASE_URL")

    # SQLAlchemy necesita que la URL indique el driver psycopg (versión 3).
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return create_engine(
        url,
        # Serverless: cada petición abre y cierra su conexión; el pooler las reutiliza.
        poolclass=NullPool,
        connect_args={
            "sslmode": "require",
            "connect_timeout": 10,
            # El pooler en modo transacción no admite sentencias preparadas.
            "prepare_threshold": None,
        },
    )
