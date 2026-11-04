import { useEffect, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { EstadoBadge } from "../components/Pago.jsx";
import { apiGet } from "../lib/api.js";
import { fechaHora, kilos, pesos } from "../lib/formato.js";
import { descargarPdfFactura } from "../lib/pdf.js";

const ETIQUETAS_COBRO = { ready: "Listo para pagar", paid: "Pagado", failed: "Fallido" };

function Total({ etiqueta, valor, resaltado = false }) {
  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm ${resaltado ? "border-red-300 ring-1 ring-red-300" : "border-slate-200"}`}>
      <p className="text-xs text-slate-500">{etiqueta}</p>
      <p className="mt-1 text-xl font-bold tabular-nums sm:text-2xl">{pesos(valor)}</p>
    </div>
  );
}

function BotonPdf({ referencia, alError }) {
  const [descargando, setDescargando] = useState(false);

  async function descargar() {
    setDescargando(true);
    alError("");
    try {
      await descargarPdfFactura(referencia);
    } catch (e) {
      alError(e.message);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <button type="button" onClick={descargar} disabled={descargando} className="font-medium text-teal-800 underline underline-offset-2 disabled:opacity-60">
      {descargando ? "..." : "PDF"}
    </button>
  );
}

function Fila({ registro: r, alError }) {
  const celda = "whitespace-nowrap px-3 py-3 align-top";
  return (
    <tr className={r.alerta ? "bg-red-50" : ""}>
      <td className={celda}>
        <p className="max-w-52 truncate text-xs font-medium" title={r.reference_code}>{r.reference_code}</p>
        <div className="mt-1"><EstadoBadge estado={r.estado} esDemo={r.is_demo} /></div>
        {r.alerta && (
          <p className="mt-1 flex items-center gap-1 text-xs font-semibold text-red-800">
            <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
            {r.alerta}
          </p>
        )}
      </td>
      <td className={celda}>{r.jaula}</td>
      <td className={`${celda} text-right tabular-nums`}>{kilos(r.kilos)}</td>
      <td className={`${celda} text-right tabular-nums`}>{pesos(r.total)}</td>
      {r.is_demo ? (
        <td className={`${celda} text-slate-500`} colSpan={6}>Histórico demo: no pasó por Factus, sin cobro, CUFE ni factura.</td>
      ) : (
        <>
          <td className={celda}>{ETIQUETAS_COBRO[r.estado_cobro] ?? r.estado_cobro ?? "Sin cobro"}</td>
          <td className={celda}>{fechaHora(r.fecha_pago)}</td>
          <td className={celda}>
            {r.numero_factura ?? "—"}
            {r.nota_credito && <p className="text-xs text-slate-500">Anulada con {r.nota_credito}</p>}
          </td>
          <td className={celda}>
            {r.cufe ? <span className="block max-w-32 truncate font-mono text-xs" title={r.cufe}>{r.cufe}</span> : "—"}
          </td>
          <td className={celda}>
            {r.enlace_factura ? (
              <a href={r.enlace_factura} target="_blank" rel="noreferrer" className="font-medium text-teal-800 underline underline-offset-2">Ver</a>
            ) : "—"}
          </td>
          <td className={celda}>{r.numero_factura ? <BotonPdf referencia={r.reference_code} alError={alError} /> : "—"}</td>
        </>
      )}
    </tr>
  );
}

export default function Conciliacion() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    apiGet("/api/conciliacion")
      .then((d) => vigente && setDatos(d))
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
    };
  }, []);

  const columnas = ["Despacho", "Jaula", "Kg", "Total", "Cobro", "Fecha de pago", "Factura", "CUFE", "Enlace", "PDF"];
  const conAlerta = datos?.registros.filter((r) => r.alerta).length ?? 0;

  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">Conciliación</h1>
      <p className="mt-1 text-sm text-slate-600">Cobros de Factus Pay frente a facturas de Factus</p>

      {error && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      {!datos && !error && <p className="mt-6 text-sm text-slate-600">Cargando conciliación...</p>}

      {datos && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Total etiqueta="Recaudado" valor={datos.totales.recaudado} />
            <Total etiqueta="Facturado" valor={datos.totales.facturado} />
            <div className="col-span-2 lg:col-span-1">
              <Total etiqueta="Diferencia" valor={datos.totales.diferencia} resaltado={datos.totales.diferencia !== 0} />
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Los totales no incluyen los despachos históricos de demostración ({pesos(datos.totales.historico_demo)}).
          </p>

          {conAlerta > 0 && (
            <p role="alert" className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-800">
              <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
              {conAlerta === 1 ? "1 despacho requiere revisión" : `${conAlerta} despachos requieren revisión`}
            </p>
          )}

          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium text-slate-600">
                <tr>
                  {columnas.map((c) => (
                    <th key={c} scope="col" className={`whitespace-nowrap px-3 py-2.5 ${c === "Kg" || c === "Total" ? "text-right" : ""}`}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {datos.registros.map((r) => (
                  <Fila key={r.reference_code} registro={r} alError={setError} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
