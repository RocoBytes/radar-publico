// Página placeholder del Sprint 0
// Se reemplaza con el dashboard real en Sprint 1

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-bold text-primary">Radar Público</h1>
      <p className="text-muted-foreground">
        Sprint 0 — entorno funcionando ✓
      </p>
      <a
        href="http://localhost:8000/docs"
        className="text-sm underline text-primary hover:opacity-80"
        target="_blank"
        rel="noopener noreferrer"
      >
        Ver API docs →
      </a>
    </main>
  );
}
