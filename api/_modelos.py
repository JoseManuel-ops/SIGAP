# Modelos SQLModel. Reflejan las tablas de db/esquema.sql, que es quien crea el esquema.
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Piscicola(SQLModel, table=True):
    __tablename__ = "piscicola"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    embalse: str
    departamento: str


class Jaula(SQLModel, table=True):
    __tablename__ = "jaula"

    id: Optional[int] = Field(default=None, primary_key=True)
    piscicola_id: int = Field(foreign_key="piscicola.id")
    codigo: str
    material: str
    volumen_m3: Decimal


class Lote(SQLModel, table=True):
    __tablename__ = "lote"

    id: Optional[int] = Field(default=None, primary_key=True)
    jaula_id: int = Field(foreign_key="jaula.id")
    codigo: str
    fecha_siembra: date
    animales_sembrados: int
    peso_siembra_g: Decimal
    meta_kg: Decimal
    fase: str


class Muestreo(SQLModel, table=True):
    __tablename__ = "muestreo"

    id: Optional[int] = Field(default=None, primary_key=True)
    lote_id: int = Field(foreign_key="lote.id")
    fecha: date
    peso_promedio_g: Decimal


class Alimentacion(SQLModel, table=True):
    __tablename__ = "alimentacion"

    id: Optional[int] = Field(default=None, primary_key=True)
    lote_id: int = Field(foreign_key="lote.id")
    fecha: date
    kg: Decimal
    precio_kg: int


class Mortalidad(SQLModel, table=True):
    __tablename__ = "mortalidad"

    id: Optional[int] = Field(default=None, primary_key=True)
    lote_id: int = Field(foreign_key="lote.id")
    fecha: date
    cantidad: int


class CalidadAgua(SQLModel, table=True):
    __tablename__ = "calidad_agua"

    id: Optional[int] = Field(default=None, primary_key=True)
    jaula_id: int = Field(foreign_key="jaula.id")
    fecha: date
    oxigeno_mg_l: Decimal
    temperatura_c: Decimal
    ph: Decimal


class Comprador(SQLModel, table=True):
    __tablename__ = "comprador"

    id: Optional[int] = Field(default=None, primary_key=True)
    names: str
    identification: str
    identification_document_code: str = "13"
    legal_organization_code: str = "2"
    email: str
    phone: str
    address: str
    municipio: str
    municipio_codigo_factus: Optional[str] = None


class Despacho(SQLModel, table=True):
    __tablename__ = "despacho"

    id: Optional[int] = Field(default=None, primary_key=True)
    reference_code: str
    lote_id: int = Field(foreign_key="lote.id")
    comprador_id: int = Field(foreign_key="comprador.id")
    fecha: datetime = Field(sa_type=DateTime(timezone=True))
    kilos: Decimal
    precio_kg: int
    total: int
    estado: str = "pendiente"
    is_demo: bool = False


class Cobro(SQLModel, table=True):
    __tablename__ = "cobro"

    id: Optional[int] = Field(default=None, primary_key=True)
    reference_code: str = Field(foreign_key="despacho.reference_code")
    amount: int
    status: str
    breb_key: Optional[str] = None
    qr: Optional[str] = None
    expires_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    paid_amount: Optional[int] = None
    paid_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    payer: Optional[dict] = Field(default=None, sa_type=JSONB)
    created_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))


class Factura(SQLModel, table=True):
    __tablename__ = "factura"

    id: Optional[int] = Field(default=None, primary_key=True)
    reference_code: str = Field(foreign_key="despacho.reference_code")
    number: Optional[str] = None
    cufe: Optional[str] = None
    public_url: Optional[str] = None
    qr_url: Optional[str] = None
    validated_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
