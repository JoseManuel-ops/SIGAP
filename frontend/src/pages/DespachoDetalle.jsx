import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { CuentaRegresiva, EstadoBadge, ImagenQR, LlaveBreB } from "../components/Pago.jsx";
import { apiGet, apiPost } from "../lib/api.js";
import { fechaHora, kilos, pesos } from "../lib/formato.js";

const INTERVALO_MS = 5000;

function Dato({ etiqueta, children }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{etiqueta}</dt>
      <dd className="mt-0.5 font-medium">{children}</dd>
    </div>
  );
}

export default function DespachoDetalle() {
  const { ref } = useParams();
  const { state } = useLocation();
  const [despacho, setDespacho] = useState(null);
  const [error, setError] = useState(state?.errorCobro ?? "");
  const [aviso, setAviso] = useState("");
  const [accion, setAccion] = useState("");

  const cargar = useCallback(() => apiGet(`/api/despachos/${ref}`).then(setDespacho), [ref]);

  // Refresca el estado cada 5 s mientras esté pendiente de pago.
  const esperandoPago = !despacho || ["pendiente", "expirado"].includes(despacho.estado);
  useEffect(() => {
    if (!esperandoPago) return;
    let vigente = true;
    const refrescar = () =>
      cargar().catch((e) => {
        if (vigente) setError(e.message);
      });
    refrescar();
    const temporizador = setInterval(refrescar, INTERVALO_MS);
    return () => {
      vigente = false;
      clearInterval(temporizador);
    };
  }, [cargar, esperandoPago]);

  async function ejecutar(nombre, ruta) {
    setAccion(nombre);
    setError("");
    setAviso("");
    try {
      const actualizado = await apiPost(ruta);
      setDespacho(actualizado);
      setAviso(actualizado.aviso ?? "");
    } catch (e) {
      setError(e.message);
    } finally {
      setAccion("");
    }
  }

  if (!despacho) {
    return error ? (
      <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>
    ) : (
      <p className="text-sm text-slate-600">Cargando despacho...</p>
    );
  }

  const { cobro } = despacho;
  const enlacePago = `${window.location.origin}/pagar/${despacho.reference_code}`;
  const estiloSecundario =
    "rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium transition-colors hover:bg-slate-50 disabled:opacity-60";

  return (
    <div className="mx-auto max-w-4xl">
      <Link to="/despachos" className="text-sm font-medium text-teal-800 underline underline-offset-2">
        Volver a despachos
      </Link>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Despacho {despacho.jaula}</h1>
        <EstadoBadge estado={despacho.estado} esDemo={despacho.is_demo} />
      </div>
      <p className="mt-1 break-all text-xs text-slate-500">{despacho.reference_code}</p>

      {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      {aviso && <p role="status" className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{aviso}</p>}
      {cobro?.monto_no_coincide && (
        <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-800">
          Factus Pay reportó un pago de {pesos(cobro.paid_amount)}, distinto al total de {pesos(despacho.total)}. El despacho no se marcó como pagado.
        </p>
      )}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">Cobro</h2>
          {!cobro && (
            <p className="mt-3 text-sm text-slate-600">Este despacho todavía no tiene QR. Usa «Regenerar QR» para crearlo.</p>
          )}
          {cobro && despacho.estado === "pendiente" && (
            <div className="mt-3 space-y-3">
              <ImagenQR src={cobro.qr} />
              <div className="text-center"><CuentaRegresiva hasta={cobro.expires_at} /></div>
              <LlaveBreB llave={cobro.breb_key} />
            </div>
          )}
          {cobro && despacho.estado === "expirado" && (
            <p className="mt-3 text-sm text-slate-600">El QR venció. Genera uno nuevo para seguir cobrando.</p>
          )}
          {cobro && despacho.estado === "fallido" && (
            <p className="mt-3 text-sm text-slate-600">Factus Pay reportó el cobro como fallido. Puedes generar un QR nuevo.</p>
          )}
          {cobro?.collected_at && !cobro.monto_no_coincide && (
            <p className="mt-3 text-sm text-slate-600">Pagado el {fechaHora(cobro.collected_at)}.</p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {["pendiente", "expirado", "fallido"].includes(despacho.estado) && (
              <>
                <button type="button" disabled={Boolean(accion)} onClick={() => ejecutar("verificar", `/api/despachos/${ref}/verificar`)} className={estiloSecundario}>
                  {accion === "verificar" ? "Verificando..." : "Verificar pago"}
                </button>
                <button type="button" disabled={Boolean(accion)} onClick={() => ejecutar("regenerar", `/api/despachos/${ref}/regenerar-qr`)} className={estiloSecundario}>
                  {accion === "regenerar" ? "Generando..." : "Regenerar QR"}
                </button>
              </>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">Datos del despacho</h2>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <Dato etiqueta="Kilos">{kilos(despacho.kilos)}</Dato>
            <Dato etiqueta="Precio por kg">{pesos(despacho.precio_kg)}</Dato>
            <Dato etiqueta="Total"><span className="text-lg font-bold tabular-nums">{pesos(despacho.total)}</span></Dato>
            <Dato etiqueta="Fecha">{fechaHora(despacho.fecha)}</Dato>
            <div className="col-span-2"><Dato etiqueta="Comprador">{despacho.comprador}</Dato></div>
          </dl>
          {cobro && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="text-xs text-slate-500">Enlace de pago para el comprador</p>
              <a href={enlacePago} target="_blank" rel="noreferrer" className="mt-1 block break-all text-sm font-medium text-teal-800 underline underline-offset-2">
                {enlacePago}
              </a>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
