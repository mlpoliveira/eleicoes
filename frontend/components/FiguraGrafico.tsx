"use client";

import { useState } from "react";

interface Props {
  titulo: string;
  unidade: string;
  universo: string;
  periodo: string;
  fonte: string;
  natureza?: string;
  observacao?: string;
  /** tabela equivalente ao gráfico (acessibilidade e conferência) */
  tabela: { colunas: string[]; linhas: (string | number)[][] };
  children: React.ReactNode;
}

// Moldura obrigatória de todo gráfico: título, unidade, universo, período e fonte (T7).
export function FiguraGrafico({ titulo, unidade, universo, periodo, fonte, natureza = "CÁLCULO", observacao, tabela, children }: Props) {
  const [verTabela, setVerTabela] = useState(false);
  return (
    <figure className="rounded-lg border border-borda bg-superficie p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{titulo}</h3>
          <p className="text-xs text-texto-2">
            Unidade: {unidade} · Universo: {universo} · Período: {periodo}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setVerTabela((v) => !v)}
          className="rounded border border-borda px-2 py-0.5 text-xs text-texto-2 hover:bg-superficie-2"
          aria-pressed={verTabela}
        >
          {verTabela ? "Ver gráfico" : "Ver tabela"}
        </button>
      </div>
      <div className="mt-3">
        {verTabela ? (
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-texto-2">
                <tr>{tabela.colunas.map((c) => <th key={c} className="border-b border-borda px-2 py-1 font-medium">{c}</th>)}</tr>
              </thead>
              <tbody>
                {tabela.linhas.map((l, i) => (
                  <tr key={i} className="border-b border-borda last:border-0">
                    {l.map((v, j) => <td key={j} className={`px-2 py-1 ${j > 0 ? "text-right tabular-nums" : ""}`}>{v}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>
      <figcaption className="mt-2 text-[11px] text-texto-3">
        Natureza: {natureza}. Fonte: {fonte}.{observacao ? ` ${observacao}` : ""}
      </figcaption>
    </figure>
  );
}
