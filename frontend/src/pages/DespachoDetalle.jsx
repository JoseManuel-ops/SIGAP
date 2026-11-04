import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { CuentaRegresiva, EstadoBadge, ImagenQR, LlaveBreB } from "../components/Pago.jsx";
import { apiGet, apiPost } from "../lib/api.js";
import { fechaHora, kilos, pesos } from "../lib/formato.js";
import { descargarPdfFactura } from "../lib/pdf.js";

const INTERVALO_MS = 5000;
// La DIAN puede demorar: más que el límite del backend (60 s).
const TIEMPO_FACTURA_MS = 65000;
const PASOS = ["pendiente", "pagado", "facturado"];

function Dato({ etiqueta, children }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{etiqueta}</dt>
      <dd className="mt-0.5 font-medium">{children}</dd>
    </div>
  );
}

// Avance pendiente → pagado → facturado.
function Pasos({ estado }) {
  const actual = PASOS.indexOf(estado);
  if (actual === -1) return null;
  return (
    <ol className="mt-4 flex items-center gap-2 text-xs sm:text-sm" aria-label="Avance del despacho">
      {PASOS.map((paso, i) => (
        <li key={paso} className="flex items-center gap-2" aria-current={i === actual ? "step" : undefined}>
          {i > 0 && <span className={`h-px w-4 sm:w-8 ${i <= actual ? "bg-teal-700" : "bg-slate-300"}`} aria-hidden="true" />}
          <span className={`rounded-full px-2.5 py-1 font-medium capitalize ${i <= actual ? "bg-teal-800 text-white" : "bg-slate-100 text-slate-500"}`}>
            {paso}
          </span>
        </li>
      ))}
    </ol>
  );
}

export default function DespachoDetalle({ rol }) {
  const { ref } = useParams();
  const { state } = useLocation();
  const [despacho, setDespacho] = useState(null);
  const [error, setError] = useState(state?.errorCobro ?? "");
  const [aviso, setAviso] = useState("");
  const [accion, setAccion] = useState("");
  const [anulando, setAnulando] = useState(false);
  const [motivo, setMotivo] = useState("");
  // Evita repetir la facturación automática de esta referencia si falla o se vuelve a renderizar.
  const autoFacturada = useRef(null);

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

  const ejecutar = useCallback(async (nombre, ruta, tiempoMs) => {
    setAccion(nombre);
    setError("");
    setAviso("");
    try {
      const actualizado = await apiPost(ruta, undefined, tiempoMs);
      setDespacho(actualizado);
      setAviso(actualizado.aviso ?? "");
    } catch (e) {
      setError(e.message);
    } finally {
      setAccion("");
    }
  }, []);

  const facturar = useCallback(
    () => ejecutar("facturar", `/api/despachos/${ref}/facturar`, TIEMPO_FACTURA_MS),
    [ejecutar, ref]
  );

  // Cuando el despacho pasa a pagado se factura solo, una vez. Si falla queda el botón de respaldo.
  const estado = despacho?.estado;
  useEffect(() => {
    if (estado === "pagado" && autoFacturada.current !== ref) {
      autoFacturada.current = ref;
      facturar();
    }
  }, [estado, ref, facturar]);

  async function anular(evento) {
    evento.preventDefault();
    setAccion("anular");
    setError("");
    try {
      setDespacho(await apiPost(`/api/despachos/${ref}/anular`, { motivo }, TIEMPO_FACTURA_MS));
      setAnulando(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setAccion("");
    }
  }

  async function descargarPdf() {
    setAccion("pdf");
    setError("");
    try {
      await descargarPdfFactura(ref);
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

  const { cobro, factura } = despacho;
  const enlacePago = `${window.location.origin}/pagar/${despacho.reference_code}`;
  const estiloSecundario =
    "rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium transition-colors hover:bg-slate-50 disabled:opacity-60";
  const estiloPrincipal =
    "rounded-lg bg-teal-800 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-teal-900 disabled:opacity-60";

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
      <Pasos estado={despacho.estado} />

      {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      {aviso && <p role="status" className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{aviso}</p>}
      {cobro?.monto_no_coincide && despacho.estado !== "pagado" && despacho.estado !== "facturado" && (
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

        <div className="space-y-4">
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

          {(factura || despacho.estado === "pagado") && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="font-semibold">Factura electrónica</h2>
              {!factura && (
                <>
                  <p className="mt-3 text-sm text-slate-600">
                    {accion === "facturar" ? "Emitiendo la factura ante la DIAN..." : "Este despacho está pagado y aún no tiene factura."}
                  </p>
                  <button type="button" disabled={Boolean(accion)} onClick={facturar} className={`mt-4 ${estiloPrincipal}`}>
                    {accion === "facturar" ? "Facturando..." : "Facturar"}
                  </button>
                </>
              )}
              {factura && (
                <>
                  <dl className="mt-3 space-y-3 text-sm">
                    <Dato etiqueta="Número">{factura.number}</Dato>
                    <Dato etiqueta="Validada">{fechaHora(factura.validated_at)}</Dato>
                    <Dato etiqueta="CUFE"><span className="break-all font-mono text-xs font-normal">{factura.cufe}</span></Dato>
                  </dl>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" disabled={Boolean(accion)} onClick={descargarPdf} className={estiloPrincipal}>
                      {accion === "pdf" ? "Descargando..." : "Descargar PDF"}
                    </button>
                    {factura.public_url && (
                      <a href={factura.public_url} target="_blank" rel="noreferrer" className={estiloSecundario}>Ver factura</a>
                    )}
                    {factura.qr_url && (
                      <a href={factura.qr_url} target="_blank" rel="noreferrer" className={estiloSecundario}>Consultar en la DIAN</a>
                    )}
                  </div>

                  {factura.nota_credito_number && (
                    <div className="mt-4 rounded-lg bg-slate-100 p-3 text-sm">
                      <p className="font-medium">Factura anulada con la nota crédito {factura.nota_credito_number}</p>
                      <p className="mt-0.5 text-slate-600">{fechaHora(factura.anulada_at)}</p>
                      {factura.nota_credito_public_url && (
                        <a href={factura.nota_credito_public_url} target="_blank" rel="noreferrer" className="mt-1 inline-block font-medium text-teal-800 underline underline-offset-2">
                          Ver nota crédito
                        </a>
                      )}
                    </div>
                  )}

                  {/* Solo oculta el botón: quien valida el rol es el backend. */}
                  {rol === "admin" && despacho.estado === "facturado" && !anulando && (
                    <button type="button" disabled={Boolean(accion)} onClick={() => setAnulando(true)} className="mt-4 text-sm font-medium text-red-800 underline underline-offset-2">
                      Anular con nota crédito
                    </button>
                  )}
                  {anulando && (
                    <form onSubmit={anular} className="mt-4 space-y-3 rounded-lg border border-red-200 p-3">
                      <p className="text-sm font-medium text-red-800">
                        Se enviará a la DIAN una nota crédito por {pesos(despacho.total)}. Esta acción no se puede deshacer y no devuelve el dinero al comprador.
                      </p>
                      <div>
                        <label htmlFor="motivo" className="text-sm font-medium text-slate-700">Motivo</label>
                        <input
                          id="motivo"
                          required
                          minLength={3}
                          maxLength={300}
                          value={motivo}
                          onChange={(e) => setMotivo(e.target.value)}
                          className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20"
                        />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button type="submit" disabled={Boolean(accion)} className="rounded-lg bg-red-800 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-red-900 disabled:opacity-60">
                          {accion === "anular" ? "Anulando..." : "Confirmar anulación"}
                        </button>
                        <button type="button" disabled={Boolean(accion)} onClick={() => setAnulando(false)} className={estiloSecundario}>Cancelar</button>
                      </div>
                    </form>
                  )}
                </>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
