import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { reloj } from "../lib/formato.js";

const ESTADOS = {
  pendiente: { texto: "Pendiente", estilo: "bg-amber-50 text-amber-800" },
  pagado: { texto: "Pagado", estilo: "bg-teal-50 text-teal-800" },
  facturado: { texto: "Facturado", estilo: "bg-emerald-100 text-emerald-900" },
  fallido: { texto: "Fallido", estilo: "bg-red-50 text-red-800" },
  expirado: { texto: "Expirado", estilo: "bg-slate-100 text-slate-700" },
  anulado: { texto: "Anulado", estilo: "bg-slate-200 text-slate-800" },
};

export function EstadoBadge({ estado, esDemo = false }) {
  const { texto, estilo } = ESTADOS[estado] ?? { texto: estado, estilo: "bg-slate-100 text-slate-700" };
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${estilo}`}>
      {esDemo ? "Histórico demo" : texto}
    </span>
  );
}

// Tiempo restante del QR. Se calcula con el reloj del navegador y la fecha que da el servidor.
export function CuentaRegresiva({ hasta }) {
  const [ahora, setAhora] = useState(() => Date.now());

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(temporizador);
  }, []);

  const restante = Math.max(0, Math.floor((new Date(hasta).getTime() - ahora) / 1000));
  if (restante === 0) return <p className="text-sm font-medium text-red-800">El QR venció</p>;
  return (
    <p className="text-sm text-slate-600">
      Vence en <span className="font-semibold tabular-nums text-slate-900">{reloj(restante)}</span>
    </p>
  );
}

export function LlaveBreB({ llave }) {
  const [copiada, setCopiada] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(llave);
      setCopiada(true);
      setTimeout(() => setCopiada(false), 2000);
    } catch {
      // Sin permiso para el portapapeles: la llave sigue visible para copiarla a mano.
    }
  }

  return (
    <div className="flex items-center justify-between gap-2 rounded-lg bg-slate-100 px-3 py-2">
      <div className="min-w-0">
        <p className="text-xs text-slate-500">Llave Bre-B</p>
        <p className="break-all font-mono text-sm font-semibold">{llave}</p>
      </div>
      <button
        type="button"
        onClick={copiar}
        aria-label="Copiar llave Bre-B"
        className="shrink-0 rounded-lg p-2 text-slate-600 hover:bg-slate-200"
      >
        {copiada ? <Check className="size-5 text-teal-700" aria-hidden="true" /> : <Copy className="size-5" aria-hidden="true" />}
      </button>
    </div>
  );
}

export function ImagenQR({ src }) {
  return (
    <img
      src={src}
      alt="Código QR para pagar con Bre-B"
      className="mx-auto aspect-square w-full max-w-72 rounded-lg border border-slate-200 bg-white p-2"
    />
  );
}
