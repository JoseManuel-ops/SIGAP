import { useEffect, useState } from "react";

export default function App() {
  const [resultado, setResultado] = useState("Consultando...");

  // Consulta el estado de la API al abrir la página.
  useEffect(() => {
    fetch("/api/health")
      .then(async (respuesta) => {
        if (!respuesta.ok) throw new Error(`Error ${respuesta.status}`);
        return JSON.stringify(await respuesta.json());
      })
      .then(setResultado)
      .catch((error) => setResultado(`No se pudo consultar la API: ${error.message}`));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-4 text-slate-900">
      <h1 className="text-5xl font-bold">SIGAP</h1>
      <p className="font-mono text-sm">/api/health: {resultado}</p>
    </main>
  );
}
