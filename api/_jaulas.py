# Cálculo del resumen de cada jaula (biomasa, densidad, peso, días y alertas).
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, and_, select

from api._modelos import Alimentacion, CalidadAgua, Despacho, Jaula, Lote, Mortalidad, Muestreo

# Colombia no cambia de horario: UTC-5 todo el año (Vercel corre en UTC).
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

# Solo lo pagado o facturado ya salió de la jaula.
ESTADOS_DESPACHADOS = ("pagado", "facturado")

# Rangos de referencia para tilapia roja en jaula.
OXIGENO_MIN_MG_L = Decimal("4.0")
TEMPERATURA_MIN_C, TEMPERATURA_MAX_C = Decimal("24.0"), Decimal("32.0")
PH_MIN, PH_MAX = Decimal("6.5"), Decimal("9.0")


def hoy_colombia() -> date:
    return datetime.now(ZONA_COLOMBIA).date()


# Compara el último registro de agua con los rangos de referencia.
def calcular_alertas(agua: CalidadAgua | None) -> list[dict]:
    if agua is None:
        return []

    alertas = []
    if agua.oxigeno_mg_l < OXIGENO_MIN_MG_L:
        alertas.append({
            "tipo": "oxigeno_bajo",
            "mensaje": f"Oxígeno en {agua.oxigeno_mg_l} mg/L (mínimo {OXIGENO_MIN_MG_L})",
            "fecha": agua.fecha,
        })
    if not TEMPERATURA_MIN_C <= agua.temperatura_c <= TEMPERATURA_MAX_C:
        alertas.append({
            "tipo": "temperatura_fuera_de_rango",
            "mensaje": f"Temperatura en {agua.temperatura_c} °C (rango {TEMPERATURA_MIN_C}–{TEMPERATURA_MAX_C})",
            "fecha": agua.fecha,
        })
    if not PH_MIN <= agua.ph <= PH_MAX:
        alertas.append({
            "tipo": "ph_fuera_de_rango",
            "mensaje": f"pH en {agua.ph} (rango {PH_MIN}–{PH_MAX})",
            "fecha": agua.fecha,
        })
    return alertas


# Arma el resumen de una jaula a partir de los datos ya consultados.
def armar_resumen(
    jaula: Jaula,
    lote: Lote | None,
    peso_g: Decimal | None,
    muertes: int,
    alimento_kg: Decimal,
    costo_alimento: Decimal,
    despachado_kg: Decimal,
    agua: CalidadAgua | None,
) -> dict:
    resumen = {
        "codigo": jaula.codigo,
        "material": jaula.material,
        "volumen_m3": jaula.volumen_m3,
        "lote": None,
        "ultima_calidad_agua": None,
        "alertas": calcular_alertas(agua),
    }
    if agua is not None:
        resumen["ultima_calidad_agua"] = {
            "fecha": agua.fecha,
            "oxigeno_mg_l": agua.oxigeno_mg_l,
            "temperatura_c": agua.temperatura_c,
            "ph": agua.ph,
        }
    if lote is None:
        return resumen

    peso = peso_g if peso_g is not None else lote.peso_siembra_g
    sobrevivientes = lote.animales_sembrados - muertes
    # Biomasa producida: todo lo que ha crecido en el ciclo, incluida la parte ya vendida.
    biomasa_producida = sobrevivientes * peso / 1000
    # Biomasa actual: lo que sigue en el agua. De aquí sale la densidad.
    biomasa_actual = max(biomasa_producida - despachado_kg, Decimal(0))

    resumen["lote"] = {
        "codigo": lote.codigo,
        "fase": lote.fase,
        "fecha_siembra": lote.fecha_siembra,
        "dias": (hoy_colombia() - lote.fecha_siembra).days,
        "animales_sembrados": lote.animales_sembrados,
        "mortalidad_acumulada": muertes,
        "supervivencia_pct": round(Decimal(sobrevivientes) * 100 / lote.animales_sembrados, 1),
        "peso_promedio_g": peso,
        "meta_kg": lote.meta_kg,
        "biomasa_producida_kg": round(biomasa_producida, 1),
        "despachado_kg": despachado_kg,
        "biomasa_actual_kg": round(biomasa_actual, 1),
        "densidad_kg_m3": round(biomasa_actual / jaula.volumen_m3, 1),
        "alimento_kg": alimento_kg,
        "costo_alimento_cop": int(costo_alimento),
    }
    return resumen


# Consulta todas las jaulas (o solo una si se indica el código).
# Usa consultas agrupadas para no hacer una consulta por jaula en cada petición.
def consultar_resumenes(sesion: Session, codigo: str | None = None) -> list[dict]:
    consulta = (
        select(Jaula, Lote)
        .join(Lote, and_(Lote.jaula_id == Jaula.id, Lote.fase != "cerrado"), isouter=True)
        .order_by(Jaula.codigo)
    )
    if codigo is not None:
        consulta = consulta.where(Jaula.codigo == codigo)
    filas = sesion.exec(consulta).all()
    if not filas:
        return []

    ids_jaulas = [jaula.id for jaula, _ in filas]
    ids_lotes = [lote.id for _, lote in filas if lote is not None]

    # DISTINCT ON se queda con la fila más reciente de cada lote o jaula.
    ultimos_pesos = sesion.exec(
        select(Muestreo)
        .where(Muestreo.lote_id.in_(ids_lotes))
        .distinct(Muestreo.lote_id)
        .order_by(Muestreo.lote_id, Muestreo.fecha.desc())
    ).all()
    pesos = {m.lote_id: m.peso_promedio_g for m in ultimos_pesos}

    ultimas_aguas = sesion.exec(
        select(CalidadAgua)
        .where(CalidadAgua.jaula_id.in_(ids_jaulas))
        .distinct(CalidadAgua.jaula_id)
        .order_by(CalidadAgua.jaula_id, CalidadAgua.fecha.desc())
    ).all()
    aguas = {a.jaula_id: a for a in ultimas_aguas}

    muertes = dict(sesion.exec(
        select(Mortalidad.lote_id, func.sum(Mortalidad.cantidad))
        .where(Mortalidad.lote_id.in_(ids_lotes))
        .group_by(Mortalidad.lote_id)
    ).all())

    alimento = {
        lote_id: (kg, costo)
        for lote_id, kg, costo in sesion.exec(
            select(
                Alimentacion.lote_id,
                func.sum(Alimentacion.kg),
                func.sum(Alimentacion.kg * Alimentacion.precio_kg),
            )
            .where(Alimentacion.lote_id.in_(ids_lotes))
            .group_by(Alimentacion.lote_id)
        ).all()
    }

    despachado = dict(sesion.exec(
        select(Despacho.lote_id, func.sum(Despacho.kilos))
        .where(Despacho.lote_id.in_(ids_lotes), Despacho.estado.in_(ESTADOS_DESPACHADOS))
        .group_by(Despacho.lote_id)
    ).all())

    resumenes = []
    for jaula, lote in filas:
        lote_id = lote.id if lote is not None else None
        alimento_kg, costo = alimento.get(lote_id, (Decimal(0), Decimal(0)))
        resumenes.append(armar_resumen(
            jaula=jaula,
            lote=lote,
            peso_g=pesos.get(lote_id),
            muertes=int(muertes.get(lote_id, 0)),
            alimento_kg=alimento_kg,
            costo_alimento=costo,
            despachado_kg=despachado.get(lote_id, Decimal(0)),
            agua=aguas.get(jaula.id),
        ))
    return resumenes


# Detalle de una jaula: su resumen más las series para gráficas y los despachos del lote.
def consultar_detalle(sesion: Session, codigo: str) -> dict | None:
    resumenes = consultar_resumenes(sesion, codigo)
    if not resumenes:
        return None
    detalle = resumenes[0]

    jaula_id = sesion.exec(select(Jaula.id).where(Jaula.codigo == codigo)).one()
    aguas = sesion.exec(
        select(CalidadAgua)
        .where(CalidadAgua.jaula_id == jaula_id)
        .order_by(CalidadAgua.fecha.desc())
        .limit(7)
    ).all()
    detalle["calidad_agua"] = [
        {
            "fecha": a.fecha,
            "oxigeno_mg_l": a.oxigeno_mg_l,
            "temperatura_c": a.temperatura_c,
            "ph": a.ph,
        }
        for a in reversed(aguas)
    ]

    detalle["muestreos"] = []
    detalle["despachos"] = []
    if detalle["lote"] is None:
        return detalle

    lote_id = sesion.exec(select(Lote.id).where(Lote.codigo == detalle["lote"]["codigo"])).one()
    muestreos = sesion.exec(
        select(Muestreo).where(Muestreo.lote_id == lote_id).order_by(Muestreo.fecha)
    ).all()
    detalle["muestreos"] = [
        {"fecha": m.fecha, "peso_promedio_g": m.peso_promedio_g} for m in muestreos
    ]

    despachos = sesion.exec(
        select(Despacho).where(Despacho.lote_id == lote_id).order_by(Despacho.fecha.desc())
    ).all()
    detalle["despachos"] = [
        {
            "reference_code": d.reference_code,
            "fecha": d.fecha,
            "kilos": d.kilos,
            "precio_kg": d.precio_kg,
            "total": d.total,
            "estado": d.estado,
            "is_demo": d.is_demo,
        }
        for d in despachos
    ]
    return detalle
