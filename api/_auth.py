# Validación del token de Supabase Auth.
# Supabase firma con una clave privada ES256; aquí se verifica con su clave pública (JWKS),
# así que el backend no guarda ningún secreto para esto.
import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api._db import url_base

ROLES_VALIDOS = ("admin", "operario")

# Tolerancia entre el reloj de este servidor y el de Supabase. Sin ella, si este reloj va
# un segundo atrasado, un token recién emitido parece del futuro ("iat") y se rechaza.
TOLERANCIA_RELOJ_S = 30

logger = logging.getLogger("sigap")

# auto_error=False: la respuesta 401 la arma usuario_actual, con mensaje en español.
esquema_bearer = HTTPBearer(auto_error=False)


def url_auth() -> str:
    return f"{url_base('SUPABASE_URL')}/auth/v1"


# El cliente guarda las claves públicas unos minutos solo para no descargarlas en cada
# petición. Es una copia prescindible: si la instancia se reinicia, las vuelve a descargar.
@lru_cache
def cliente_jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        f"{url_auth()}/.well-known/jwks.json",
        timeout=5,
        headers={"User-Agent": "sigap-api"},
    )


def no_autorizado(mensaje: str) -> HTTPException:
    return HTTPException(status_code=401, detail=mensaje, headers={"WWW-Authenticate": "Bearer"})


# Dependencia de FastAPI: devuelve el usuario del token o corta la petición con un error.
def usuario_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)) -> dict:
    if credenciales is None:
        raise no_autorizado("Debes iniciar sesión")

    token = credenciales.credentials
    try:
        # La clave se elige por el "kid" del token, pero siempre entre las de Supabase.
        clave = cliente_jwks().get_signing_key_from_jwt(token)
        datos = jwt.decode(
            token,
            clave,
            # Lista fija: se ignora el algoritmo que el token diga tener (evita "none" y HS256).
            algorithms=["ES256"],
            audience="authenticated",
            issuer=url_auth(),
            leeway=TOLERANCIA_RELOJ_S,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise no_autorizado("Tu sesión expiró. Inicia sesión de nuevo")
    except jwt.PyJWKClientConnectionError:
        # No es culpa del token: no se pudo consultar a Supabase.
        raise HTTPException(status_code=503, detail="No se pudo verificar la sesión. Intenta de nuevo")
    except jwt.PyJWTError as error:
        # El motivo exacto queda en el log, sin registrar el token.
        logger.warning("Token rechazado: %s: %s", type(error).__name__, error)
        raise no_autorizado("La sesión no es válida")

    # El rol sale de app_metadata, que el usuario no puede modificar (user_metadata sí).
    # Un token válido sin rol, por ejemplo de una cuenta creada por fuera, no da acceso.
    rol = (datos.get("app_metadata") or {}).get("role")
    if rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=403, detail="Tu usuario no tiene un rol asignado en SIGAP")

    return {"id": datos["sub"], "email": datos.get("email"), "rol": rol}


# Para rutas exclusivas de administración. Ocultar el menú no basta: esto lo valida el servidor.
def solo_admin(usuario: dict = Depends(usuario_actual)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Esta acción es solo para administradores")
    return usuario
