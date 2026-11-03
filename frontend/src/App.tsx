import React from "react";

export function App(): React.JSX.Element {
  return (
    <main className="min-h-screen p-8 flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold tracking-tight mb-2">
        Pampero Claims Assistant
      </h1>
      <p className="text-muted-foreground text-sm">
        Asistente RAG multi-tenant para reclamaciones de seguros de vehículos.
      </p>
    </main>
  );
}

export default App;
