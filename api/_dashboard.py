# Datos de las gráficas de la pantalla Jaulas.
from decimal import Decimal

from sqlmodel import Session, select

from api._jaulas import OXIGENO_MIN_MG_L, ZONA_COLOMBIA
from api._modelos import Alimentacion, CalidadAgua, Despacho, Jaula, Lote, Muestreo

JAULA_FINANZAS = "J-01"
JAULA_OXIGENO = "J-04"
# Solo lo cobrado cuenta como ingreso. Lo anulado o pendiente no.
ESTADOS_CON_INGRESO = ("pagado", "facturado")


def _crecimiento(sesion: Session) -> list[dict]:
    filas = sesion.exec(
        select(Muestreo.fecha, Muestreo.peso_promedio_g, Jaula.codigo)
        .join(Lote, Muestreo.lote_id == Lote.id)
        .join(Jaula, Lote.jaula_id == Jaula.id)
        .where(Lote.fase != "cerrado")
        .order_by(Muestreo.fecha)
    ).all()
    # Una fila por fecha, con el peso de cada jaula medida ese día.
    por_fecha: dict = {}
    for fecha, peso, codigo in filas:
        por_fecha.setdefault(fecha, {"fecha": fecha})[codigo] = peso
    return list(por_fecha.values())


def _oxigeno(sesion: Session) -> list[dict]:
    filas = sesion.exec(
        select(CalidadAgua.fecha, CalidadAgua.oxigeno_mg_l)
        .join(Jaula, CalidadAgua.jaula_id == Jaula.id)
        .where(Jaula.codigo == JAULA_OXIGENO)
        .order_by(CalidadAgua.fecha.desc())
        .limit(7)
    ).all()
    return [{"fecha": fecha, "oxigeno_mg_l": valor} for fecha, valor in reversed(filas)]


# Ingresos y costo de alimento acumulados de la jaula, por fecha.
def _finanzas(sesion: Session) -> dict:
    lote_id = sesion.exec(
        select(Lote.id)
        .join(Jaula, Lote.jaula_id == Jaula.id)
        .where(Jaula.codigo == JAULA_FINANZAS, Lote.fase != "cerrado")
    ).first()
    if lote_id is None:
        return {"ingresos": 0, "ingresos_demo": 0, "costo_alimento": 0, "margen": 0, "serie": []}

    alimentos = sesion.exec(select(Alimentacion).where(Alimentacion.lote_id == lote_id)).all()
    despachos = sesion.exec(
        select(Despacho).where(Despacho.lote_id == lote_id, Despacho.estado.in_(ESTADOS_CON_INGRESO))
    ).all()

    # Movimientos por día: (fecha, costo de alimento, ingreso).
    movimientos: dict = {}
    for a in alimentos:
        dia = movimientos.setdefault(a.fecha, [Decimal(0), 0])
        dia[0] += a.kg * a.precio_kg
    for d in despachos:
        # Fecha en hora Colombia: las 8:00 p. m. de un día no deben caer en el siguiente (UTC).
        dia = movimientos.setdefault(d.fecha.astimezone(ZONA_COLOMBIA).date(), [Decimal(0), 0])
        dia[1] += d.total

    serie = []
    costo = Decimal(0)
    ingresos = 0
    for fecha in sorted(movimientos):
        costo += movimientos[fecha][0]
        ingresos += movimientos[fecha][1]
        serie.append({"fecha": fecha, "ingresos": ingresos, "costo_alimento": int(costo)})

    return {
        "ingresos": ingresos,
        "ingresos_demo": sum(d.total for d in despachos if d.is_demo),
        "costo_alimento": int(costo),
        "margen": ingresos - int(costo),
        "serie": serie,
    }


def consultar(sesion: Session) -> dict:
    return {
        "crecimiento": _crecimiento(sesion),
        "oxigeno": {"jaula": JAULA_OXIGENO, "minimo": OXIGENO_MIN_MG_L, "serie": _oxigeno(sesion)},
        "finanzas": {"jaula": JAULA_FINANZAS, **_finanzas(sesion)},
    }
