# SIGAP – Hackatón Reto Factus

## Qué es
SIGAP (Sistema Integral de Gestión y Analítica Piscícola) para "Piscícola Huila" (datos de demostración):
6 jaulas flotantes de tilapia roja en el Embalse de Betania. Cada jaula tiene un lote (ciclo de cultivo).
La cosecha se vende por despachos de hasta 1.200 kg a comercializadores persona natural.

## Flujo obligatorio (Opción A del reto)
Despacho → cobro QR con Factus Pay → pago en el simulador sandbox → webhook → factura electrónica con Factus → conciliación.
Extra: nota crédito para anular una factura validada.
La misma reference_code del despacho une el cobro y la factura.

## Estados del despacho
pendiente → pagado → facturado. También: fallido, expirado, anulado (con nota crédito).

## Stack
- Monorepo desplegado en Vercel (proyecto único)
- /frontend: React + Vite + Tailwind + shadcn/ui + Recharts
- /api: FastAPI (Python serverless en Vercel), httpx, SQLModel
- Base de datos: Supabase Postgres (usar el pooler, puerto 6543)
- Login: Supabase Auth, roles admin y operario. El comprador NO inicia sesión (página pública de pago).

## Reglas
- Nunca escribir credenciales en el código. Todo sale de variables de entorno.
- .env en .gitignore. .env.example solo con valores simulados.
- Serverless: nada en memoria entre peticiones; todo en la base de datos.
- Webhook: validar la llave (comparación de tiempo constante), marcar pagado, responder 200 rápido.
  NO usar tareas en segundo plano. La factura se emite en un endpoint aparte.
- Validar que el monto pagado sea igual al total del despacho.
- Manejar y mostrar errores de las APIs (401, 409, 422, timeouts).
- Código simple y comentado en español. Trabajar una fase a la vez y no agregar funciones no pedidas.
- El código debe ser escrito desde cero en el evento.

## Factus Pay (sandbox: https://pay-api-sandbox.factus.com.co)
- POST /auth (JSON: email, password) → token que no vence. Cada /auth anula el anterior: usar el token guardado en la variable FACTUS_PAY_TOKEN.
- POST /v1/collections (reference_code, amount 1000–12100000 COP, expiration en segundos) → status ready, breb_key, qr (PNG base64).
- GET /v1/collections/{reference_code} → estado (ready, paid, failed).
- GET /v1/collections?status=&reference_code= → listado paginado (15 por página).
- Webhook: POST a nuestra URL con ?key=LLAVE; body data.reference_code, amount, status "paid", payer opcional. Hasta 6 reintentos, timeout 10 s.
- Mismo reference_code devuelve el cobro existente (idempotente).

## Factus Facturación (sandbox: https://api-sandbox.factus.com.co)
- POST /oauth/token (form: grant_type=password, client_id, client_secret, username, password) → access_token (~1 h) y refresh_token.
- Refresh: POST /oauth/token con grant_type=refresh_token.
- POST /v2/bills/validate → factura (reference_code, numbering_range_id, payment_details, customer, items). Respuesta: data.number, data.cufe, data.links.public_url, data.links.qr.
- GET /v2/bills/{number}/download-pdf → pdf_base_64_encoded.
- Persona natural: legal_organization_code "2", identification_document_code "13" (cédula), campo names.
- payment_form "1" (contado). Códigos de medio de pago, unidad kg y municipio: consultar tablas de Factus (pendiente confirmar).
- Error 409: hay una factura pendiente sin enviar a la DIAN; eliminarla antes de crear otra.

## Datos de demostración
6 jaulas HDPE de 603 m³ (J-01 a J-06), siembra de 68.000 juveniles de 25 g, meta 30 t por lote.
J-01 cosechando (14 despachos históricos pagados y facturados), J-02 precosecha, J-03 y J-04 engorde,
J-05 levante, J-06 recién sembrada. J-04 con oxígeno bajo (3,6 mg/L) para mostrar una alerta.
Precio de venta: $10.000/kg.