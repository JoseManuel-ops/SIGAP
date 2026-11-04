// Marcador para las secciones del menú que se construyen en fases posteriores.
export default function Proximamente({ titulo }) {
  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">{titulo}</h1>
      <p className="mt-2 text-slate-600">Esta sección estará disponible próximamente.</p>
    </>
  );
}
