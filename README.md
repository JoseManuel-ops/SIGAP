# SIGAP

Sistema Integral de Gestión y Analítica Piscícola. Proyecto para la Hackatón Reto Factus (Opción A).

Gestiona 6 jaulas de tilapia roja de "Piscícola Huila" (datos de demostración) en el Embalse de Betania y conecta la venta de la cosecha con Factus: cada despacho se cobra con QR Bre-B, se factura ante la DIAN y se concilia.

## Integrantes

- Jose Manuel <!-- Completar: nombre completo y demás integrantes del equipo -->

## Arquitectura

Un solo proyecto en Vercel:

```
Navegador (React)
   │  Supabase Auth: inicia sesión y obtiene un token firmado
   │  /api/* con el token (Bearer)
   ▼
FastAPI (función serverless, api/index.py)
   ├── Supabase Postgres, por el pooler (puerto 6543)
   ├── Factus Pay: cobros QR
   └── Factus Facturación: facturas y notas crédito
```

- `frontend/`: React, Vite, Tailwind y Recharts.
- `api/`: FastAPI, httpx y SQLModel. Los módulos llevan el prefijo `_` para que Vercel no los publique como funciones aparte.
- `db/`: esquema (`esquema.sql`) y roles (`roles.sql`).
- `scripts/cargar_demo.py`: datos de demostración.

Decisiones principales:

- **Serverless:** nada queda en memoria entre peticiones. El token OAuth de Factus se guarda en la base de datos.
- **Seguridad:** RLS activo y sin políticas en todas las tablas; solo el backend accede a los datos. El token de Supabase se verifica con su clave pública y el rol sale de `app_metadata`, que el usuario no puede editar.
- **Roles:** `admin` y `operario`. Conciliación y nota crédito son solo para `admin`, validado también en el backend. El comprador no inicia sesión.

## Flujo de las dos APIs

La misma `reference_code` del despacho une el cobro y la factura.

```
1. Despacho       POST /api/despachos
                  └─ Factus Pay: POST /v1/collections → QR y llave Bre-B
2. Pago           El comprador abre /pagar/{ref} y paga
3. Confirmación   Factus Pay → POST /api/webhooks/factus-pay?key=LLAVE → estado "pagado"
                  (respaldo: botón "Verificar pago" → GET /v1/collections/{ref})
4. Factura        POST /api/despachos/{ref}/facturar
                  └─ Factus: POST /v2/bills/validate → número, CUFE y enlaces
5. Conciliación   GET /api/conciliacion: recaudado, facturado y diferencia
6. Anulación      POST /api/despachos/{ref}/anular (opcional, admin)
                  └─ Factus: POST /v2/credit-notes/validate → estado "anulado"
```

Estados del despacho: `pendiente → pagado → facturado`. También `expirado`, `fallido` y `anulado`.

Comportamientos del sandbox que el código tiene en cuenta:

- El monto mínimo de Factus Pay es $10.000.
- Factus Pay sigue reportando `ready` cuando un QR vence, así que el vencimiento se calcula en SIGAP.
- Repetir el cobro con la misma referencia devuelve el mismo QR; solo se renueva si ya venció.

Códigos usados en la factura:

| Dato | Código | Origen |
|---|---|---|
| Rango de factura de venta | Consultado en cada emisión (`GET /v2/numbering-ranges`) | API |
| Rango de nota crédito | Prefijo `NC`, consultado igual | API |
| Medio de pago: transferencia | `47` | Tabla de referencia |
| Forma de pago: contado | `1` | Tabla de referencia |
| Unidad: kilogramo | `KGM` | Tabla de referencia |
| Municipio: Neiva | `41001` | Tabla de referencia |
| Cédula / persona natural | `13` / `2` | Tabla de referencia |
| IVA 0 % | Tributo `01`, tarifa `0.00` | Tabla de referencia |

## Ejecutar en local

Requisitos: Node.js 20 o superior y Python 3 (probado con 3.12 y 3.14; Vercel usa 3.12, fijado en `.python-version`).

Copiar `.env.example` a `.env` y poner los valores reales. Luego, en dos terminales desde la raíz (comandos para PowerShell):

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

Iniciar sesión con un usuario de Supabase Auth (`admin@sigap.demo` u `operario@sigap.demo`).

## Base de datos

Aplicar `db/esquema.sql` en Supabase, crear los usuarios en Supabase Auth, aplicar `db/roles.sql` y cargar los datos de demostración:

```powershell
python -m scripts.cargar_demo
```

Si los datos ya existen, el script no hace nada. Los 14 despachos históricos de J-01 están marcados con `is_demo`: no pasaron por Factus, así que no tienen cobro, CUFE ni número de factura, y quedan fuera de los totales de conciliación.

## Desplegar

Importar el repositorio en Vercel con la raíz del proyecto como directorio raíz. La configuración de build está en `vercel.json`.

Variables de entorno en el panel de Vercel (ver `.env.example`). Las `VITE_*` se leen al compilar, así que deben estar antes del build.

En el panel de Factus Pay, configurar el webhook:

```
https://TU-DOMINIO/api/webhooks/factus-pay?key=VALOR_DE_FACTUS_WEBHOOK_KEY
```
