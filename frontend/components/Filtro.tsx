"use client";

import type { ValorFiltro } from "@/lib/api";
import { titulo } from "@/lib/formato";

// Seletor de um valor (vazio = todos). Valores em ordem alfabética, como vêm de /api/filtros.
export function SelectFiltro({ id, rotulo, valores, valor, onChange, cargo = false }: {
  id: string;
  rotulo: string;
  valores: ValorFiltro[] | undefined;
  valor: string;
  onChange: (v: string) => void;
  cargo?: boolean;
}) {
  return (
    <label htmlFor={id} className="flex flex-col text-xs text-texto-2">
      {rotulo}
      <select
        id={id}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 max-w-56 rounded border border-borda bg-superficie px-2 py-1 text-sm text-texto"
      >
        <option value="">Todos</option>
        {(valores ?? []).map((v) => (
          <option key={String(v.valor)} value={String(v.valor)}>
            {cargo ? titulo(v.rotulo ?? String(v.valor)) : v.rotulo && v.rotulo !== v.valor ? `${v.valor} — ${v.rotulo}` : String(v.valor)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SelectSimNao({ id, rotulo, valor, onChange }: {
  id: string; rotulo: string; valor: string; onChange: (v: string) => void;
}) {
  return (
    <label htmlFor={id} className="flex flex-col text-xs text-texto-2">
      {rotulo}
      <select id={id} value={valor} onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 rounded border border-borda bg-superficie px-2 py-1 text-sm text-texto">
        <option value="">Todos</option>
        <option value="true">Sim</option>
        <option value="false">Não</option>
      </select>
    </label>
  );
}
