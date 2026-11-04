# SIGAP

Sistema Integral de Gestión y Analítica Piscícola. Proyecto para la Hackatón Reto Factus.

## Estructura

- `frontend/`: React + Vite + Tailwind
- `api/`: FastAPI (función serverless de Python en Vercel)
- `vercel.json`: envía `/api/*` a Python y el resto al frontend

## Requisitos

Node.js 20 o superior y Python 3 (probado en local con Python 3.14). En Vercel se usa Python 3.12, fijado en `.python-version`.

## Ejecutar en local

Copiar `.env.example` a `.env`. Luego, en dos terminales desde la raíz del proyecto (comandos para PowerShell):

**API** (http://127.0.0.1:8000)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn api.index:app --reload --port 8000
```

**Frontend** (http://localhost:5173)

```powershell
cd frontend
npm install
npm run dev
```

Abrir http://localhost:5173: debe mostrar `SIGAP` y `/api/health: {"status":"ok"}`.

## Base de datos

El esquema está en `db/esquema.sql` (aplicado en Supabase como migración). Para cargar los datos de demostración, con `DATABASE_URL` en el `.env`:

```powershell
python -m scripts.cargar_demo
```

Si los datos ya existen, el script no hace nada.

## Desplegar

Importar el repositorio en Vercel con la raíz del proyecto como directorio raíz. La configuración de build está en `vercel.json`. Las variables de entorno se configuran en el panel de Vercel.
