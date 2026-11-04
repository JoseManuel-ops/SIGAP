import { useState } from "react";
import { Fish, LogOut, Menu, Scale, Truck, X } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { cerrarSesion } from "../lib/sesion.js";

const ETIQUETAS_ROL = { admin: "Administrador", operario: "Operario" };

function Marca() {
  return (
    <div>
      <p className="text-lg font-bold tracking-tight text-white">SIGAP</p>
      <p className="text-xs text-teal-200">Piscícola Huila</p>
    </div>
  );
}

// Contenido del menú. Es el mismo en el celular (panel desplegable) y en el escritorio (columna fija).
function Navegacion({ usuario, rol, alNavegar }) {
  const enlaces = [
    { ruta: "/jaulas", texto: "Jaulas", Icono: Fish },
    { ruta: "/despachos", texto: "Despachos", Icono: Truck },
    ...(rol === "admin" ? [{ ruta: "/conciliacion", texto: "Conciliación", Icono: Scale }] : []),
  ];

  return (
    <>
      <nav className="flex-1 space-y-1 p-3" aria-label="Menú principal">
        {enlaces.map(({ ruta, texto, Icono }) => (
          <NavLink
            key={ruta}
            to={ruta}
            onClick={alNavegar}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive ? "bg-teal-700 text-white" : "text-teal-100 hover:bg-teal-900"
              }`
            }
          >
            <Icono className="size-5" aria-hidden="true" />
            {texto}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-teal-900 p-3">
        <p className="truncate px-3 text-sm text-white">{usuario.email}</p>
        <p className="px-3 pb-2 text-xs text-teal-200">{ETIQUETAS_ROL[rol] ?? "Sin rol asignado"}</p>
        <button
          type="button"
          onClick={() => cerrarSesion()}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-teal-100 transition-colors hover:bg-teal-900"
        >
          <LogOut className="size-5" aria-hidden="true" />
          Cerrar sesión
        </button>
      </div>
    </>
  );
}

export default function Layout({ usuario, rol }) {
  const [menuAbierto, setMenuAbierto] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Escritorio: columna fija */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col bg-teal-950 lg:flex">
        <div className="flex h-16 items-center px-6">
          <Marca />
        </div>
        <Navegacion usuario={usuario} rol={rol} />
      </aside>

      {/* Celular: barra superior y panel desplegable */}
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between bg-teal-950 px-4 lg:hidden">
        <Marca />
        <button
          type="button"
          onClick={() => setMenuAbierto(true)}
          aria-label="Abrir menú"
          className="rounded-lg p-2 text-white hover:bg-teal-900"
        >
          <Menu className="size-6" aria-hidden="true" />
        </button>
      </header>

      {menuAbierto && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-slate-950/50" onClick={() => setMenuAbierto(false)} />
          <aside className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col bg-teal-950">
            <div className="flex h-14 items-center justify-between px-4">
              <Marca />
              <button
                type="button"
                onClick={() => setMenuAbierto(false)}
                aria-label="Cerrar menú"
                className="rounded-lg p-2 text-white hover:bg-teal-900"
              >
                <X className="size-6" aria-hidden="true" />
              </button>
            </div>
            <Navegacion usuario={usuario} rol={rol} alNavegar={() => setMenuAbierto(false)} />
          </aside>
        </div>
      )}

      <main className="px-4 py-6 sm:px-6 lg:ml-60 lg:px-8 lg:py-8">
        <Outlet />
      </main>
    </div>
  );
}
