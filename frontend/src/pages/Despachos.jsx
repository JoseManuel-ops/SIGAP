import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Link } from "react-router";
import { EstadoBadge } from "../components/Pago.jsx";
import { apiGet } from "../lib/api.js";
import { fechaHora, kilos, pesos } from "../lib/formato.js";

export default function Despachos() {
  const [despachos, setDespachos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    apiGet("/api/despachos")
      .then((datos) => vigente && setDespachos(datos))
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
    };
  }, []);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Despachos</h1>
        <Link
          to="/despachos/nuevo"
          className="inline-flex items-center gap-2 rounded-lg bg-teal-800 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-teal-900"
        >
          <Plus className="size-4" aria-hidden="true" />
          Nuevo despacho
        </Link>
      </div>

      {error && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      {!despachos && !error && <p className="mt-6 text-sm text-slate-600">Cargando despachos...</p>}
      {despachos?.length === 0 && <p className="mt-6 text-sm text-slate-600">Todavía no hay despachos.</p>}

      {despachos?.length > 0 && (
        <ul className="mt-6 divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          {despachos.map((d) => {
            const contenido = (
              <>
                <div className="min-w-0">
                  <p className="font-semibold">
                    {d.jaula} · {kilos(d.kilos)} · <span className="tabular-nums">{pesos(d.total)}</span>
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">{d.reference_code}</p>
                  <p className="text-xs text-slate-500">{fechaHora(d.fecha)} · {d.comprador}</p>
                </div>
                <EstadoBadge estado={d.estado} esDemo={d.is_demo} />
              </>
            );
            const estilo = "flex items-center justify-between gap-3 p-4";
            return (
              <li key={d.reference_code}>
                {/* Los históricos de demostración no tienen cobro: no hay detalle que abrir. */}
                {d.is_demo ? (
                  <div className={estilo}>{contenido}</div>
                ) : (
                  <Link to={`/despachos/${d.reference_code}`} className={`${estilo} transition-colors hover:bg-slate-50`}>
                    {contenido}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
