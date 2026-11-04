import { useCallback, useEffect, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { apiGet } from "../lib/api.js";

const ETIQUETAS_FASE = {
  recien_sembrada: "Recién sembrada",
  levante: "Levante",
  engorde: "Engorde",
  precosecha: "Precosecha",
  cosechando: "Cosechando",
};

// Números con formato colombiano: 13.120 y 21,8.
function numero(valor, decimales = 0) {
  return Number(valor).toLocaleString("es-CO", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
}

function Dato({ etiqueta, valor, unidad }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{etiqueta}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums">
        {valor}
        {unidad && <span className="ml-1 text-sm font-normal text-slate-500">{unidad}</span>}
      </dd>
    </div>
  );
}

function TarjetaJaula({ jaula }) {
  const { codigo, lote, alertas } = jaula;
  const conAlerta = alertas.length > 0;

  return (
    <article
      className={`rounded-xl border bg-white p-5 shadow-sm ${conAlerta ? "border-red-300 ring-1 ring-red-300" : "border-slate-200"}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold tracking-tight">{codigo}</h2>
        <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-800">
          {lote ? (ETIQUETAS_FASE[lote.fase] ?? lote.fase) : "Sin lote activo"}
        </span>
      </div>

      {alertas.map((alerta) => (
        <p
          key={alerta.tipo}
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-800"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {alerta.mensaje}
        </p>
      ))}

      {lote && (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
            <Dato etiqueta="Días de cultivo" valor={numero(lote.dias)} />
            <Dato etiqueta="Peso promedio" valor={numero(lote.peso_promedio_g)} unidad="g" />
            <Dato etiqueta="Biomasa en jaula" valor={numero(lote.biomasa_actual_kg)} unidad="kg" />
            <Dato etiqueta="Densidad" valor={numero(lote.densidad_kg_m3, 1)} unidad="kg/m³" />
          </dl>
          {/* Aclara por qué una jaula en cosecha tiene menos biomasa que la anterior. */}
          {lote.despachado_kg > 0 && (
            <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
              {numero(lote.despachado_kg)} kg ya despachados
            </p>
          )}
        </>
      )}
    </article>
  );
}

export default function Jaulas() {
  const [jaulas, setJaulas] = useState(null);
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {
    setError("");
    setJaulas(null);
    try {
      setJaulas(await apiGet("/api/jaulas"));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const totalAlertas = jaulas?.filter((j) => j.alertas.length > 0).length ?? 0;

  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">Jaulas</h1>
      <p className="mt-1 text-sm text-slate-600" aria-live="polite">
        {jaulas
          ? `${jaulas.length} jaulas en Embalse de Betania · ${
              totalAlertas === 0 ? "sin alertas" : totalAlertas === 1 ? "1 con alerta" : `${totalAlertas} con alerta`
            }`
          : "Embalse de Betania"}
      </p>

      {error && (
        <div role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p>{error}</p>
          <button type="button" onClick={cargar} className="mt-2 font-medium underline underline-offset-2">
            Reintentar
          </button>
        </div>
      )}

      {!jaulas && !error && (
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Cargando jaulas">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />
          ))}
        </div>
      )}

      {jaulas && (
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {jaulas.map((jaula) => (
            <TarjetaJaula key={jaula.codigo} jaula={jaula} />
          ))}
        </div>
      )}
    </>
  );
}
