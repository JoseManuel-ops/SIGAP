import { useState } from "react";
import { supabase } from "../lib/supabase.js";

// Traduce los errores de Supabase Auth a mensajes claros.
function mensajeDeError(error) {
  if (error.code === "invalid_credentials") return "Correo o contraseña incorrectos.";
  if (error.code === "email_not_confirmed") return "Este correo todavía no está confirmado.";
  if (error.code === "user_banned") return "Este usuario está bloqueado.";
  if (error.status === 429) return "Demasiados intentos. Espera un momento e intenta de nuevo.";
  if (!error.status) return "No se pudo conectar con el servicio de autenticación.";
  return `No se pudo iniciar sesión: ${error.message}`;
}

// aviso: motivo por el que se cerró la sesión anterior, si lo hubo.
export default function Login({ aviso = "" }) {
  const [correo, setCorreo] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function iniciarSesion(evento) {
    evento.preventDefault();
    setError("");
    setEnviando(true);
    // Si todo sale bien, App detecta la sesión nueva y cambia de pantalla.
    try {
      const { error: errorAuth } = await supabase.auth.signInWithPassword({ email: correo.trim(), password: clave });
      if (errorAuth) setError(mensajeDeError(errorAuth));
    } catch (errorInesperado) {
      setError(mensajeDeError(errorInesperado));
    } finally {
      setEnviando(false);
    }
  }

  // El error del último intento reemplaza al aviso de la sesión anterior.
  const mensaje = error || aviso;

  const estiloCampo =
    "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20";

  return (
    <main className="flex min-h-screen items-center justify-center bg-teal-950 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl sm:p-8">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">SIGAP</h1>
        <p className="mt-1 text-sm text-slate-600">Sistema Integral de Gestión y Analítica Piscícola</p>

        <form onSubmit={iniciarSesion} className="mt-6 space-y-4">
          <div>
            <label htmlFor="correo" className="text-sm font-medium text-slate-700">Correo</label>
            <input
              id="correo"
              type="email"
              autoComplete="username"
              required
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              className={estiloCampo}
            />
          </div>
          <div>
            <label htmlFor="clave" className="text-sm font-medium text-slate-700">Contraseña</label>
            <input
              id="clave"
              type="password"
              autoComplete="current-password"
              required
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              className={estiloCampo}
            />
          </div>

          {mensaje && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{mensaje}</p>
          )}

          <button
            type="submit"
            disabled={enviando}
            className="w-full rounded-lg bg-teal-800 px-4 py-2.5 font-medium text-white transition-colors hover:bg-teal-900 disabled:opacity-60"
          >
            {enviando ? "Ingresando..." : "Iniciar sesión"}
          </button>
        </form>
      </div>
    </main>
  );
}
