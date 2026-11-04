import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import Layout from "./components/Layout.jsx";
import { cerrarSesion, tomarMotivoDeCierre } from "./lib/sesion.js";
import { supabase } from "./lib/supabase.js";
import DespachoDetalle from "./pages/DespachoDetalle.jsx";
import Despachos from "./pages/Despachos.jsx";
import Jaulas from "./pages/Jaulas.jsx";
import Conciliacion from "./pages/Conciliacion.jsx";
import Login from "./pages/Login.jsx";
import NuevoDespacho from "./pages/NuevoDespacho.jsx";
import PagoPublico from "./pages/PagoPublico.jsx";

const ROLES_VALIDOS = ["admin", "operario"];

function PantallaCentrada({ children }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 p-4 text-center text-slate-600">
      {children}
    </main>
  );
}

// Todo lo que exige iniciar sesión.
function AreaPrivada() {
  // undefined: todavía no se sabe si hay sesión. null: no hay sesión.
  const [sesion, setSesion] = useState(undefined);
  const [avisoLogin, setAvisoLogin] = useState("");

  // Lee la sesión guardada y escucha los cambios (inicio, cierre y renovación del token).
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSesion(data.session));
    const { data } = supabase.auth.onAuthStateChange((evento, nuevaSesion) => {
      if (evento === "SIGNED_OUT") setAvisoLogin(tomarMotivoDeCierre());
      if (evento === "SIGNED_IN") setAvisoLogin("");
      setSesion(nuevaSesion);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  if (!supabase) {
    return <PantallaCentrada>Falta configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY.</PantallaCentrada>;
  }
  if (sesion === undefined) {
    return <PantallaCentrada>Cargando...</PantallaCentrada>;
  }
  if (sesion === null) {
    return <Login aviso={avisoLogin} />;
  }

  // El rol solo decide qué se muestra en pantalla. Quien protege los datos es el backend.
  const rol = sesion.user.app_metadata?.role;

  if (!ROLES_VALIDOS.includes(rol)) {
    return (
      <PantallaCentrada>
        <p role="alert" className="max-w-sm rounded-lg bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
          {sesion.user.email} no tiene un rol asignado en SIGAP. Pide a un administrador que te lo asigne.
        </p>
        <button
          type="button"
          onClick={() => cerrarSesion()}
          className="rounded-lg bg-teal-800 px-4 py-2.5 font-medium text-white transition-colors hover:bg-teal-900"
        >
          Cerrar sesión
        </button>
      </PantallaCentrada>
    );
  }

  return (
    <Routes>
      <Route element={<Layout usuario={sesion.user} rol={rol} />}>
        <Route path="/jaulas" element={<Jaulas />} />
        <Route path="/despachos" element={<Despachos />} />
        <Route path="/despachos/nuevo" element={<NuevoDespacho />} />
        <Route path="/despachos/:ref" element={<DespachoDetalle />} />
        <Route
          path="/conciliacion"
          element={rol === "admin" ? <Conciliacion /> : <Navigate to="/jaulas" replace />}
        />
        <Route path="*" element={<Navigate to="/jaulas" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Pública: el comprador paga sin iniciar sesión. */}
        <Route path="/pagar/:ref" element={<PagoPublico />} />
        <Route path="*" element={<AreaPrivada />} />
      </Routes>
    </BrowserRouter>
  );
}
