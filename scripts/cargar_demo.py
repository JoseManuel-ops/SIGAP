# Carga los datos de demostración de Piscícola Huila. Son datos simulados.
# Uso, desde la raíz del proyecto: python -m scripts.cargar_demo
# Si los datos ya existen no hace nada, así que se puede ejecutar más de una vez.
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlmodel import Session, select

from api._db import obtener_engine
from api._modelos import (
    Alimentacion,
    CalidadAgua,
    Comprador,
    Despacho,
    Jaula,
    Lote,
    Mortalidad,
    Muestreo,
    Piscicola,
)

# Fecha de corte de los datos (miércoles). Los muestreos caen todos los miércoles.
FECHA_CORTE = date(2026, 11, 4)

ANIMALES_SEMBRADOS = 68_000
PESO_SIEMBRA_G = 25
META_KG = 30_000
PRECIO_ALIMENTO_KG = 3_000
PRECIO_VENTA_KG = 10_000
KILOS_POR_DESPACHO = 1_200

# codigo, fecha de siembra, fase, peso actual (g), supervivencia (%), alimento acumulado (kg)
JAULAS = [
    ("J-01", date(2026, 5, 8), "cosechando", 500, Decimal("88.0"), 45_700),
    ("J-02", date(2026, 5, 23), "precosecha", 446, Decimal("88.9"), 40_000),
    ("J-03", date(2026, 7, 7), "engorde", 266, Decimal("91.8"), 23_100),
    ("J-04", date(2026, 8, 11), "engorde", 149, Decimal("94.1"), 11_300),
    ("J-05", date(2026, 9, 25), "levante", 60, Decimal("97.2"), 2_900),
    ("J-06", date(2026, 10, 25), "recien_sembrada", 31, Decimal("99.3"), 400),
]

# Oxígeno de los últimos 7 días, del más antiguo al más reciente.
# J-04 cae hasta 3,6 mg/L para mostrar la alerta.
OXIGENO_MG_L = {
    "J-01": ["5.8", "5.6", "5.9", "5.7", "5.5", "5.8", "5.6"],
    "J-02": ["5.9", "6.0", "5.8", "5.7", "5.9", "5.8", "5.9"],
    "J-03": ["6.1", "6.0", "6.2", "5.9", "6.1", "6.0", "6.1"],
    "J-04": ["5.4", "5.2", "5.0", "4.7", "4.4", "4.0", "3.6"],
    "J-05": ["6.4", "6.5", "6.3", "6.4", "6.6", "6.4", "6.5"],
    "J-06": ["6.7", "6.6", "6.8", "6.7", "6.6", "6.8", "6.7"],
}
TEMPERATURA_C = ["27.2", "27.5", "27.8", "27.4", "27.1", "27.6", "27.3"]
PH = ["7.4", "7.5", "7.3", "7.4", "7.6", "7.4", "7.5"]


# Curva de crecimiento común: el peso depende de la edad del lote (días, gramos).
# Sale de los pesos actuales pedidos para cada jaula.
CURVA = [(0, PESO_SIEMBRA_G)] + sorted(
    ((FECHA_CORTE - siembra).days, peso) for _, siembra, _, peso, _, _ in JAULAS
)


# Peso a una edad dada. Interpola en escala logarítmica porque el crecimiento es exponencial.
def peso_a_la_edad(dias: int) -> Decimal:
    for (d0, p0), (d1, p1) in zip(CURVA, CURVA[1:]):
        if d0 <= dias <= d1:
            avance = (dias - d0) / (d1 - d0)
            peso = math.exp(math.log(p0) + avance * (math.log(p1) - math.log(p0)))
            return Decimal(str(round(peso, 1)))
    raise ValueError(f"Edad fuera de la curva: {dias}")


# Miércoles posteriores a la siembra, hasta la fecha de corte.
def fechas_de_muestreo(siembra: date) -> list[date]:
    fechas = []
    fecha = FECHA_CORTE
    while fecha > siembra:
        fechas.append(fecha)
        fecha -= timedelta(days=7)
    return list(reversed(fechas))


# Reparte un total entero según unos pesos y garantiza que la suma sea exacta.
def repartir(total: int, pesos: list[float]) -> list[int]:
    suma = sum(pesos)
    exactos = [total * p / suma for p in pesos]
    partes = [math.floor(x) for x in exactos]
    faltante = total - sum(partes)
    # El faltante va a las partes con mayor residuo.
    orden = sorted(range(len(pesos)), key=lambda i: exactos[i] - partes[i], reverse=True)
    for i in orden[:faltante]:
        partes[i] += 1
    return partes


def cargar_lote(sesion: Session, lote: Lote, supervivencia: Decimal, alimento_kg: int):
    siembra = lote.fecha_siembra
    fechas = fechas_de_muestreo(siembra)

    # Muestreo inicial el día de la siembra y luego uno semanal.
    sesion.add(Muestreo(lote_id=lote.id, fecha=siembra, peso_promedio_g=Decimal(PESO_SIEMBRA_G)))
    for fecha in fechas:
        sesion.add(Muestreo(lote_id=lote.id, fecha=fecha, peso_promedio_g=peso_a_la_edad((fecha - siembra).days)))

    # Cada periodo va del registro anterior al actual: (días del periodo, edad al final).
    periodos = []
    anterior = siembra
    for fecha in fechas:
        periodos.append(((fecha - anterior).days, (fecha - siembra).days))
        anterior = fecha

    # La mortalidad es mayor en las primeras semanas después de la siembra.
    muertes_totales = int(ANIMALES_SEMBRADOS * (100 - supervivencia) / 100)
    muertes = repartir(muertes_totales, [d * (1 + 3 * math.exp(-edad / 30)) for d, edad in periodos])
    for fecha, cantidad in zip(fechas, muertes):
        sesion.add(Mortalidad(lote_id=lote.id, fecha=fecha, cantidad=cantidad))

    # El consumo de alimento crece con el peso de los peces.
    consumo = repartir(alimento_kg, [d * float(peso_a_la_edad(edad)) ** 0.7 for d, edad in periodos])
    for fecha, kg in zip(fechas, consumo):
        sesion.add(Alimentacion(lote_id=lote.id, fecha=fecha, kg=Decimal(kg), precio_kg=PRECIO_ALIMENTO_KG))


# 14 despachos de J-01: de lunes a sábado, terminando el día anterior al corte.
def fechas_de_despacho() -> list[datetime]:
    colombia = timezone(timedelta(hours=-5))
    fechas = []
    dia = FECHA_CORTE - timedelta(days=1)
    while len(fechas) < 14:
        if dia.weekday() != 6:  # 6 = domingo
            fechas.append(datetime(dia.year, dia.month, dia.day, 8, 0, tzinfo=colombia))
        dia -= timedelta(days=1)
    return list(reversed(fechas))


def main():
    with Session(obtener_engine()) as sesion:
        if sesion.exec(select(Piscicola).where(Piscicola.nombre == "Piscícola Huila")).first():
            print("Los datos de demostración ya existen; no se cargó nada.")
            return

        piscicola = Piscicola(nombre="Piscícola Huila", embalse="Embalse de Betania", departamento="Huila")
        sesion.add(piscicola)
        sesion.flush()

        lote_j01 = None
        for codigo, siembra, fase, _, supervivencia, alimento_kg in JAULAS:
            jaula = Jaula(piscicola_id=piscicola.id, codigo=codigo, material="HDPE", volumen_m3=Decimal(603))
            sesion.add(jaula)
            sesion.flush()

            lote = Lote(
                jaula_id=jaula.id,
                codigo=f"L-{codigo}-{siembra.year}",
                fecha_siembra=siembra,
                animales_sembrados=ANIMALES_SEMBRADOS,
                peso_siembra_g=Decimal(PESO_SIEMBRA_G),
                meta_kg=Decimal(META_KG),
                fase=fase,
            )
            sesion.add(lote)
            sesion.flush()
            if codigo == "J-01":
                lote_j01 = lote

            cargar_lote(sesion, lote, supervivencia, alimento_kg)

            # Un registro de agua diario durante los últimos 7 días.
            for i in range(7):
                sesion.add(CalidadAgua(
                    jaula_id=jaula.id,
                    fecha=FECHA_CORTE - timedelta(days=6 - i),
                    oxigeno_mg_l=Decimal(OXIGENO_MG_L[codigo][i]),
                    temperatura_c=Decimal(TEMPERATURA_C[i]),
                    ph=Decimal(PH[i]),
                ))

        # Comprador de prueba: datos ficticios. 41001 es Neiva en las tablas de Factus.
        comprador = Comprador(
            names="Comprador de Prueba SIGAP",
            identification="123456789",
            email="comprador.prueba@example.com",
            phone="3000000000",
            address="Calle 1 # 1-01",
            municipio="Neiva",
            municipio_codigo_factus="41001",
        )
        sesion.add(comprador)
        sesion.flush()

        # Despachos históricos: is_demo=True y estado facturado, sin filas en cobro ni factura.
        # No se inventan CUFE ni números de factura; el prefijo DEMO evita confundirlos con reales.
        for n, fecha in enumerate(fechas_de_despacho(), start=1):
            sesion.add(Despacho(
                reference_code=f"DEMO-J01-{n:03d}",
                lote_id=lote_j01.id,
                comprador_id=comprador.id,
                fecha=fecha,
                kilos=Decimal(KILOS_POR_DESPACHO),
                precio_kg=PRECIO_VENTA_KG,
                total=KILOS_POR_DESPACHO * PRECIO_VENTA_KG,
                estado="facturado",
                is_demo=True,
            ))

        sesion.commit()
        print("Datos de demostración cargados.")


if __name__ == "__main__":
    main()
