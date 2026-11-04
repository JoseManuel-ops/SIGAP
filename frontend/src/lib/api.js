import { cerrarSesion } from "./sesion.js";
import { supabase } from "./supabase.js";

const TIEMPO_MAXIMO_MS = 20000;

// Hace la petición y convierte cualquier fallo en un Error con un mensaje para el usuario.
async function pedir(ruta, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, { ...opciones, signal: AbortSignal.timeout(TIEMPO_MAXIMO_MS) });
  } catch (error) {
    if (error.name === "TimeoutError") {
      throw new Error("El servidor tardó demasiado en responder.");
    }
    throw new Error("No se pudo conectar con el servidor.");
  }
  const cuerpo = await respuesta.json().catch(() => null);
  return { respuesta, cuerpo };
}

function mensajeDeError(respuesta, cuerpo) {
  return cuerpo?.detail ?? `El servidor respondió con error ${respuesta.status}.`;
}

// Petición con el token de la sesión. Lanza un Error si algo falla.
async function pedirConSesion(ruta, opciones = {}) {
  // getSession renueva el token si ya venció, así que se pide en cada llamada.
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    const mensaje = "Tu sesión expiró. Inicia sesión de nuevo.";
    await cerrarSesion(mensaje);
    throw new Error(mensaje);
  }

  const { respuesta, cuerpo } = await pedir(ruta, {
    ...opciones,
    headers: { ...opciones.headers, Authorization: `Bearer ${token}` },
  });

  if (!respuesta.ok) {
    const mensaje = mensajeDeError(respuesta, cuerpo);
    // Token rechazado: vuelve al login y muestra allí el motivo.
    if (respuesta.status === 401) await cerrarSesion(mensaje);
    throw new Error(mensaje);
  }
  return cuerpo;
}

export function apiGet(ruta) {
  return pedirConSesion(ruta);
}

export function apiPost(ruta, datos) {
  return pedirConSesion(ruta, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: datos === undefined ? undefined : JSON.stringify(datos),
  });
}

// Para la página pública de pago: no usa sesión.
export async function apiPublicoGet(ruta) {
  const { respuesta, cuerpo } = await pedir(ruta);
  if (!respuesta.ok) throw new Error(mensajeDeError(respuesta, cuerpo));
  return cuerpo;
}
