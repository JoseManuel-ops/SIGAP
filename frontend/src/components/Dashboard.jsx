import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet } from "../lib/api.js";
import { pesos } from "../lib/formato.js";

// Colores en orden fijo, validados para daltonismo sobre fondo blanco.
const COLORES_JAULAS = {
  "J-01": "#2a78d6",
  "J-02": "#eb6834",
  "J-03": "#1baf7a",
  "J-04": "#eda100",
  "J-05": "#e87ba4",
  "J-06": "#008300",
};
const COLOR_INGRESOS = "#2a78d6";
const COLOR_COSTO = "#eb6834";
const COLOR_REJILLA = "#e2e8f0";
const COLOR_EJE = "#64748b";
const COLOR_CRITICO = "#b91c1c";

const EJE = { fontSize: 12, fill: COLOR_EJE };

// Las fechas llegan como AAAA-MM-DD. Se usa mediodía para que ninguna zona horaria cambie el día.
function marcaDeTiempo(fecha) {
  return new Date(`${fecha}T12:00:00`).getTime();
}

function fechaCorta(valor) {
  return new Date(valor).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function millones(valor) {
  return `$${(valor / 1000000).toLocaleString("es-CO", { maximumFractionDigits: 0 })} M`;
}

// El texto de la leyenda va en tinta normal; la línea de al lado marca la serie.
function textoLeyenda(nombre) {
  return <span className="text-slate-600">{nombre}</span>;
}

// Detalle al pasar el cursor. Los textos usan tinta normal; el color solo marca la serie.
function Detalle({ active, payload, label, formato }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-slate-900">{fechaCorta(label)}</p>
      <ul className="mt-1 space-y-0.5">
        {payload.map((item) => (
          <li key={item.dataKey} className="flex items-center gap-2 text-slate-600">
            <span className="size-2 rounded-full" style={{ backgroundColor: item.color }} aria-hidden="true" />
            {item.name}: <span className="font-semibold tabular-nums text-slate-900">{formato(item.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Tarjeta({ titulo, descripcion, children, datos }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-semibold">{titulo}</h3>
      <p className="mt-0.5 text-xs text-slate-500">{descripcion}</p>
      <div className="mt-4">{children}</div>
      {datos}
    </section>
  );
}

// Los mismos datos en texto, para quien no puede leer la gráfica.
function TablaDatos({ columnas, filas }) {
  return (
    <details className="mt-3 text-xs text-slate-600">
      <summary className="cursor-pointer font-medium">Ver datos en tabla</summary>
      <div className="mt-2 max-h-56 overflow-auto">
        <table className="min-w-full text-left">
          <thead>
            <tr>{columnas.map((c) => <th key={c} scope="col" className="whitespace-nowrap py-1 pr-3 font-medium">{c}</th>)}</tr>
          </thead>
          <tbody className="tabular-nums">
            {filas.map((fila) => (
              <tr key={fila[0]} className="border-t border-slate-100">
                {fila.map((valor, i) => <td key={i} className="whitespace-nowrap py-1 pr-3">{valor}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Crecimiento({ datos }) {
  const jaulas = Object.keys(COLORES_JAULAS);
  const serie = datos.map((d) => ({ ...d, tiempo: marcaDeTiempo(d.fecha) }));
  return (
    <Tarjeta
      titulo="Crecimiento por lote"
      descripcion="Peso promedio en cada muestreo, en gramos"
      datos={
        <TablaDatos
          columnas={["Fecha", ...jaulas]}
          filas={datos.map((d) => [d.fecha, ...jaulas.map((j) => d[j] ?? "—")])}
        />
      }
    >
      <div className="h-72" role="img" aria-label="Curvas de peso de los lotes de las jaulas J-01 a J-06 desde su siembra">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={serie} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={COLOR_REJILLA} vertical={false} />
            <XAxis dataKey="tiempo" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fechaCorta} tick={EJE} tickLine={false} axisLine={{ stroke: COLOR_REJILLA }} minTickGap={32} />
            <YAxis tick={EJE} tickLine={false} axisLine={false} width={40} unit=" g" />
            <Tooltip content={<Detalle formato={(v) => `${Number(v).toLocaleString("es-CO")} g`} />} />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} formatter={textoLeyenda} />
            {jaulas.map((j) => (
              <Line key={j} dataKey={j} name={j} stroke={COLORES_JAULAS[j]} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Tarjeta>
  );
}

function Oxigeno({ datos }) {
  const { jaula, minimo, serie } = datos;
  const puntos = serie.map((d) => ({ ...d, tiempo: marcaDeTiempo(d.fecha) }));
  const formato = (v) => `${Number(v).toLocaleString("es-CO", { minimumFractionDigits: 1 })} mg/L`;
  const ultimo = serie[serie.length - 1];
  return (
    <Tarjeta
      titulo={`Oxígeno disuelto de ${jaula}`}
      descripcion="Últimos 7 días, en mg/L"
      datos={<TablaDatos columnas={["Fecha", "Oxígeno (mg/L)"]} filas={serie.map((d) => [d.fecha, d.oxigeno_mg_l])} />}
    >
      <div className="h-72" role="img" aria-label={`Oxígeno de ${jaula}: último valor ${ultimo ? formato(ultimo.oxigeno_mg_l) : "sin datos"}, mínimo recomendado ${formato(minimo)}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={puntos} margin={{ top: 20, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={COLOR_REJILLA} vertical={false} />
            <XAxis dataKey="tiempo" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fechaCorta} tick={EJE} tickLine={false} axisLine={{ stroke: COLOR_REJILLA }} minTickGap={24} />
            <YAxis domain={[0, 8]} tick={EJE} tickLine={false} axisLine={false} width={32} />
            <Tooltip content={<Detalle formato={formato} />} />
            <ReferenceLine y={Number(minimo)} stroke={COLOR_CRITICO} strokeDasharray="4 4" label={{ value: `Mínimo ${Number(minimo).toLocaleString("es-CO", { minimumFractionDigits: 1 })}`, position: "insideBottomLeft", fontSize: 12, fill: COLOR_CRITICO }} />
            <Line dataKey="oxigeno_mg_l" name="Oxígeno" stroke={COLORES_JAULAS["J-01"]} strokeWidth={2} dot={{ r: 4, strokeWidth: 2, stroke: "#ffffff", fill: COLORES_JAULAS["J-01"] }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Tarjeta>
  );
}

function Cifra({ etiqueta, valor }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{etiqueta}</p>
      <p className="mt-0.5 text-lg font-bold tabular-nums sm:text-xl">{valor}</p>
    </div>
  );
}

function Finanzas({ datos }) {
  const { jaula, ingresos, ingresos_demo: ingresosDemo, costo_alimento: costo, margen, serie } = datos;
  const puntos = serie.map((d) => ({ ...d, tiempo: marcaDeTiempo(d.fecha) }));
  return (
    <Tarjeta
      titulo={`Ingresos y margen de ${jaula}`}
      descripcion={`Margen sobre alimento: no incluye otros costos del cultivo. Los ingresos incluyen ${pesos(ingresosDemo)} de despachos históricos de demostración.`}
      datos={
        <TablaDatos
          columnas={["Fecha", "Ingresos acumulados", "Costo de alimento acumulado"]}
          filas={serie.map((d) => [d.fecha, pesos(d.ingresos), pesos(d.costo_alimento)])}
        />
      }
    >
      <div className="grid grid-cols-3 gap-3">
        <Cifra etiqueta="Ingresos" valor={millones(ingresos)} />
        <Cifra etiqueta="Alimento" valor={millones(costo)} />
        <Cifra etiqueta="Margen" valor={millones(margen)} />
      </div>
      <div className="mt-4 h-64" role="img" aria-label={`${jaula}: ingresos acumulados de ${pesos(ingresos)} frente a un costo de alimento de ${pesos(costo)}, margen de ${pesos(margen)}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={puntos} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={COLOR_REJILLA} vertical={false} />
            <XAxis dataKey="tiempo" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fechaCorta} tick={EJE} tickLine={false} axisLine={{ stroke: COLOR_REJILLA }} minTickGap={32} />
            <YAxis tickFormatter={millones} tick={EJE} tickLine={false} axisLine={false} width={56} />
            <Tooltip content={<Detalle formato={pesos} />} />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} formatter={textoLeyenda} />
            <Line dataKey="ingresos" name="Ingresos acumulados" stroke={COLOR_INGRESOS} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="costo_alimento" name="Alimento acumulado" stroke={COLOR_COSTO} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Tarjeta>
  );
}

export default function Dashboard() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    apiGet("/api/dashboard")
      .then((d) => vigente && setDatos(d))
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
    };
  }, []);

  return (
    <section className="mt-10" aria-label="Indicadores">
      <h2 className="text-xl font-bold tracking-tight">Indicadores</h2>
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      {!datos && !error && <p className="mt-4 text-sm text-slate-600">Cargando gráficas...</p>}
      {datos && (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div className="xl:col-span-2"><Crecimiento datos={datos.crecimiento} /></div>
          <Oxigeno datos={datos.oxigeno} />
          <Finanzas datos={datos.finanzas} />
        </div>
      )}
    </section>
  );
}
