import { useEffect, useState } from "react";
import { CircleCheck } from "lucide-react";
import { useParams } from "react-router";
import { CuentaRegresiva, ImagenQR, LlaveBreB } from "../components/Pago.jsx";
import { apiPublicoGet } from "../lib/api.js";
import { pesos } from "../lib/formato.js";

const INTERVALO_MS = 5000;

// Página pública para quien paga. No requiere sesión y solo recibe los datos del cobro.
export default function PagoPublico() {
  const { ref } = useParams();
  const [pago, setPago] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    const refrescar = () =>
      apiPublicoGet(`/api/pago/${ref}`)
        .then((datos) => {
          if (!vigente) return;
          setPago(datos);
          setError("");
        })
        .catch((e) => vigente && setError(e.message));
    refrescar();
    const temporizador = setInterval(refrescar, INTERVALO_MS);
    return () => {
      vigente = false;
      clearInterval(temporizador);
    };
  }, [ref]);

  const pagado = pago && ["pagado", "facturado"].includes(pago.estado);

  return (
    <main className="flex min-h-screen items-center justify-center bg-teal-950 p-4 text-slate-900">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
        <p className="text-lg font-bold tracking-tight">SIGAP</p>
        <p className="text-sm text-slate-600">Pago a Piscícola Huila</p>

        {!pago && !error && <p className="mt-6 text-sm text-slate-600">Cargando cobro...</p>}
        {error && <p role="alert" className="mt-6 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

        {pago && (
          <>
            <p className="mt-6 text-sm text-slate-600">Valor a pagar</p>
            <p className="text-3xl font-bold tabular-nums">{pesos(pago.monto)}</p>

            {pagado && (
              <p role="status" className="mt-5 flex items-center gap-2 rounded-lg bg-teal-50 px-3 py-3 font-medium text-teal-900">
                <CircleCheck className="size-5 shrink-0" aria-hidden="true" />
                Pago recibido. ¡Gracias!
              </p>
            )}

            {pago.estado === "pendiente" && (
              <div className="mt-5 space-y-3">
                <ImagenQR src={pago.qr} />
                <div className="text-center"><CuentaRegresiva hasta={pago.expires_at} /></div>
                <LlaveBreB llave={pago.breb_key} />
                <p className="text-center text-xs text-slate-500">
                  Escanea el QR o usa la llave en la app de tu banco. Esta página se actualiza sola.
                </p>
              </div>
            )}

            {pago.estado === "expirado" && (
              <p role="alert" className="mt-5 rounded-lg bg-amber-50 px-3 py-3 text-sm text-amber-900">
                Este QR venció. Pide a Piscícola Huila que genere uno nuevo.
              </p>
            )}
            {pago.estado === "fallido" && (
              <p role="alert" className="mt-5 rounded-lg bg-red-50 px-3 py-3 text-sm text-red-800">
                El pago no se pudo completar. Pide a Piscícola Huila que genere un nuevo cobro.
              </p>
            )}
            {pago.estado === "anulado" && (
              <p role="alert" className="mt-5 rounded-lg bg-slate-100 px-3 py-3 text-sm text-slate-700">
                Este cobro fue anulado.
              </p>
            )}
          </>
        )}
      </div>
    </main>
  );
}
