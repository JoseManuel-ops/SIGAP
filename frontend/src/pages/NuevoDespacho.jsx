import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { apiGet, apiPost } from "../lib/api.js";
import { kilos as formatoKilos, pesos } from "../lib/formato.js";

const PRECIO_KG = 10000;

export default function NuevoDespacho() {
  const navegar = useNavigate();
  const [jaulas, setJaulas] = useState([]);
  const [compradores, setCompradores] = useState([]);
  const [jaula, setJaula] = useState("");
  const [compradorId, setCompradorId] = useState("");
  const [kilos, setKilos] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let vigente = true;
    Promise.all([apiGet("/api/jaulas"), apiGet("/api/compradores")])
      .then(([listaJaulas, listaCompradores]) => {
        if (!vigente) return;
        const conBiomasa = listaJaulas.filter((j) => j.lote && j.lote.biomasa_actual_kg > 0);
        setJaulas(conBiomasa);
        setCompradores(listaCompradores);
        if (conBiomasa[0]) setJaula(conBiomasa[0].codigo);
        if (listaCompradores[0]) setCompradorId(String(listaCompradores[0].id));
      })
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
    };
  }, []);

  const total = Math.round(Number(kilos || 0) * PRECIO_KG);
  const biomasa = jaulas.find((j) => j.codigo === jaula)?.lote.biomasa_actual_kg;

  async function crear(evento) {
    evento.preventDefault();
    setError("");
    setEnviando(true);
    try {
      const despacho = await apiPost("/api/despachos", {
        jaula,
        comprador_id: Number(compradorId),
        kilos,
      });
      // Si el cobro falló, el despacho sí quedó creado: el detalle muestra el motivo y permite reintentar.
      navegar(`/despachos/${despacho.reference_code}`, { state: { errorCobro: despacho.error_cobro } });
    } catch (e) {
      setError(e.message);
      setEnviando(false);
    }
  }

  const estiloCampo =
    "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20";

  return (
    <div className="mx-auto max-w-lg">
      <Link to="/despachos" className="text-sm font-medium text-teal-800 underline underline-offset-2">
        Volver a despachos
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Nuevo despacho</h1>

      <form onSubmit={crear} className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <label htmlFor="jaula" className="text-sm font-medium text-slate-700">Jaula</label>
          <select id="jaula" required value={jaula} onChange={(e) => setJaula(e.target.value)} className={estiloCampo}>
            {jaulas.map((j) => (
              <option key={j.codigo} value={j.codigo}>
                {j.codigo} · {formatoKilos(j.lote.biomasa_actual_kg)} en jaula
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="comprador" className="text-sm font-medium text-slate-700">Comprador</label>
          <select id="comprador" required value={compradorId} onChange={(e) => setCompradorId(e.target.value)} className={estiloCampo}>
            {compradores.map((c) => (
              <option key={c.id} value={c.id}>{c.names} · {c.municipio}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="kilos" className="text-sm font-medium text-slate-700">Kilos</label>
          <input
            id="kilos"
            type="number"
            inputMode="decimal"
            min="1"
            max="1200"
            step="0.01"
            required
            value={kilos}
            onChange={(e) => setKilos(e.target.value)}
            className={estiloCampo}
          />
          <p className="mt-1 text-xs text-slate-500">
            Entre 1 y 1.200 kg por despacho{biomasa !== undefined && `. En jaula: ${formatoKilos(biomasa)}`}.
          </p>
        </div>

        <div className="flex items-baseline justify-between border-t border-slate-100 pt-4">
          <div>
            <p className="text-sm font-medium text-slate-700">Total</p>
            <p className="text-xs text-slate-500">{pesos(PRECIO_KG)} por kg</p>
          </div>
          <p className="text-2xl font-bold tabular-nums">{pesos(total)}</p>
        </div>

        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

        <button
          type="submit"
          disabled={enviando || !jaula || !compradorId}
          className="w-full rounded-lg bg-teal-800 px-4 py-2.5 font-medium text-white transition-colors hover:bg-teal-900 disabled:opacity-60"
        >
          {enviando ? "Creando cobro..." : "Crear despacho y cobro"}
        </button>
      </form>
    </div>
  );
}
