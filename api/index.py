# Punto de entrada de la API de SIGAP (función serverless de Python en Vercel).
from fastapi import FastAPI

app = FastAPI(title="SIGAP API")


# Permite comprobar que la API está en línea.
@app.get("/api/health")
def health():
    return {"status": "ok"}
