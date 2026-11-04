import { supabase } from "./supabase.js";

// Motivo que se muestra si la sesión se cierra sin que el usuario lo pida
// (por ejemplo, si Supabase no pudo renovar el token).
const MOTIVO_POR_DEFECTO = "Tu sesión se cerró. Inicia sesión de nuevo.";

let motivo = MOTIVO_POR_DEFECTO;

// Sin motivo es un cierre pedido por el usuario y no se muestra ningún aviso.
export async function cerrarSesion(motivoDeCierre = "") {
  motivo = motivoDeCierre;
  const { error } = await supabase.auth.signOut({ scope: "local" });
  // Si no se pudo cerrar, la sesión sigue abierta y el motivo ya no aplica.
  if (error) motivo = MOTIVO_POR_DEFECTO;
}

// App lo llama al detectar el cierre: al cambiar de pantalla se perdería el error,
// así que el motivo se guarda aquí para mostrarlo en el login.
export function tomarMotivoDeCierre() {
  const actual = motivo;
  motivo = MOTIVO_POR_DEFECTO;
  return actual;
}
