// Formatos colombianos para mostrar valores en pantalla.
export function pesos(valor) {
  return `$${Number(valor).toLocaleString("es-CO", { maximumFractionDigits: 0 })}`;
}

export function kilos(valor) {
  return `${Number(valor).toLocaleString("es-CO", { maximumFractionDigits: 2 })} kg`;
}

export function fechaHora(valor) {
  if (!valor) return "—";
  return new Date(valor).toLocaleString("es-CO", {
    timeZone: "America/Bogota",
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// Segundos como 29:05.
export function reloj(segundos) {
  const minutos = Math.floor(segundos / 60);
  return `${minutos}:${String(segundos % 60).padStart(2, "0")}`;
}
