import { cerrarSesion } from "./sesion.js";
import { supabase } from "./supabase.js";

const TIEMPO_MAXIMO_MS = 20000;

// GET a la API con el token de la sesión. Si algo falla, lanza un Error con un mensaje para el usuario.
export async function apiGet(ruta) {
  // getSession renueva el token si ya venció, así que se pide en cada llamada.
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    const mensaje = "Tu sesión expiró. Inicia sesión de nuevo.";
    await cerrarSesion(mensaje);
    throw new Error(mensaje);
  }

  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(TIEMPO_MAXIMO_MS),
    });
  } catch (error) {
    if (error.name === "TimeoutError") {
      throw new Error("El servidor tardó demasiado en responder.");
    }
    throw new Error("No se pudo conectar con el servidor.");
  }

  const cuerpo = await respuesta.json().catch(() => null);

  if (!respuesta.ok) {
    const mensaje = cuerpo?.detail ?? `El servidor respondió con error ${respuesta.status}.`;
    // Token rechazado: vuelve al login y muestra allí el motivo.
    if (respuesta.status === 401) await cerrarSesion(mensaje);
    throw new Error(mensaje);
  }
  return cuerpo;
}
