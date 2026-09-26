export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return <p className="py-8 text-center text-sm text-texto-2">{texto}</p>;
}

export function Erro({ mensagem }: { mensagem: string }) {
  return (
    <div role="alert" className="rounded border border-aviso-borda bg-aviso-fundo p-3 text-sm text-aviso-texto">
      {mensagem.includes("Failed to fetch") || mensagem.includes("Erro 50")
        ? "Não foi possível falar com a API. Verifique se o backend está rodando (uvicorn) e se o banco existe."
        : mensagem}
    </div>
  );
}

export function Alertas({ itens }: { itens: string[] }) {
  if (!itens.length) return null;
  return (
    <ul role="note" className="space-y-1 rounded border border-aviso-borda bg-aviso-fundo p-3 text-sm text-aviso-texto">
      {itens.map((a) => (
        <li key={a}>⚠ {a}</li>
      ))}
    </ul>
  );
}

export function Cartao({ titulo, children, className = "" }: { titulo?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-borda bg-superficie p-4 ${className}`}>
      {titulo && <h2 className="mb-3 text-base font-semibold">{titulo}</h2>}
      {children}
    </section>
  );
}
