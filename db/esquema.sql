-- Esquema de SIGAP. Copia de la migración aplicada en Supabase.
-- RLS activo y sin políticas: solo el backend accede, con DATABASE_URL.
-- Montos en pesos colombianos (COP) enteros; pesos corporales en gramos; cosecha y alimento en kg.

-- ---------- Producción ----------

create table piscicola (
  id bigint generated always as identity primary key,
  nombre text not null unique,
  embalse text not null,
  departamento text not null
);

create table jaula (
  id bigint generated always as identity primary key,
  piscicola_id bigint not null references piscicola (id),
  codigo text not null unique,
  material text not null,
  volumen_m3 numeric(8, 2) not null check (volumen_m3 > 0)
);
create index jaula_piscicola_idx on jaula (piscicola_id);

-- Un lote es un ciclo de cultivo. Una jaula puede tener lotes cerrados, pero solo uno activo.
create table lote (
  id bigint generated always as identity primary key,
  jaula_id bigint not null references jaula (id),
  codigo text not null unique,
  fecha_siembra date not null,
  animales_sembrados integer not null check (animales_sembrados > 0),
  peso_siembra_g numeric(7, 1) not null check (peso_siembra_g > 0),
  meta_kg numeric(10, 2) not null check (meta_kg > 0),
  fase text not null check (fase in ('recien_sembrada', 'levante', 'engorde', 'precosecha', 'cosechando', 'cerrado'))
);
create index lote_jaula_idx on lote (jaula_id);
create unique index lote_activo_por_jaula on lote (jaula_id) where fase <> 'cerrado';

create table muestreo (
  id bigint generated always as identity primary key,
  lote_id bigint not null references lote (id),
  fecha date not null,
  peso_promedio_g numeric(7, 1) not null check (peso_promedio_g > 0),
  unique (lote_id, fecha)
);

create table alimentacion (
  id bigint generated always as identity primary key,
  lote_id bigint not null references lote (id),
  fecha date not null,
  kg numeric(10, 2) not null check (kg > 0),
  precio_kg integer not null check (precio_kg > 0),
  unique (lote_id, fecha)
);

create table mortalidad (
  id bigint generated always as identity primary key,
  lote_id bigint not null references lote (id),
  fecha date not null,
  cantidad integer not null check (cantidad >= 0),
  unique (lote_id, fecha)
);

-- El agua se mide en la jaula, no en el lote.
create table calidad_agua (
  id bigint generated always as identity primary key,
  jaula_id bigint not null references jaula (id),
  fecha date not null,
  oxigeno_mg_l numeric(4, 1) not null,
  temperatura_c numeric(4, 1) not null,
  ph numeric(4, 1) not null,
  unique (jaula_id, fecha)
);

-- ---------- Venta ----------

-- Persona natural. El código de municipio de Factus queda vacío hasta confirmarlo en sus tablas.
create table comprador (
  id bigint generated always as identity primary key,
  names text not null,
  identification text not null unique,
  identification_document_code text not null default '13',
  legal_organization_code text not null default '2',
  email text not null,
  phone text not null,
  address text not null,
  municipio text not null,
  municipio_codigo_factus text
);

-- is_demo marca los despachos históricos: no pasaron por Factus y no tienen cobro ni factura.
create table despacho (
  id bigint generated always as identity primary key,
  reference_code text not null unique,
  lote_id bigint not null references lote (id),
  comprador_id bigint not null references comprador (id),
  fecha timestamptz not null default now(),
  kilos numeric(8, 2) not null check (kilos > 0 and kilos <= 1200),
  precio_kg integer not null check (precio_kg > 0),
  total integer not null check (total between 1000 and 12100000),
  estado text not null default 'pendiente'
    check (estado in ('pendiente', 'pagado', 'facturado', 'fallido', 'expirado', 'anulado')),
  is_demo boolean not null default false
);
create index despacho_lote_idx on despacho (lote_id);
create index despacho_comprador_idx on despacho (comprador_id);

-- status copia lo que informa Factus Pay, por eso no se restringe con un check.
-- paid_amount es lo que reporta el webhook; se compara con el total del despacho.
create table cobro (
  id bigint generated always as identity primary key,
  reference_code text not null unique references despacho (reference_code),
  amount integer not null,
  status text not null,
  breb_key text,
  qr text,
  expires_at timestamptz,
  paid_amount integer,
  paid_at timestamptz,
  payer jsonb,
  created_at timestamptz not null default now()
);

-- number y cufe los asigna Factus; quedan vacíos hasta que la factura sea validada.
create table factura (
  id bigint generated always as identity primary key,
  reference_code text not null unique references despacho (reference_code),
  number text unique,
  cufe text unique,
  public_url text,
  qr_url text,
  validated_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------- Seguridad ----------

alter table piscicola enable row level security;
alter table jaula enable row level security;
alter table lote enable row level security;
alter table muestreo enable row level security;
alter table alimentacion enable row level security;
alter table mortalidad enable row level security;
alter table calidad_agua enable row level security;
alter table comprador enable row level security;
alter table despacho enable row level security;
alter table cobro enable row level security;
alter table factura enable row level security;
