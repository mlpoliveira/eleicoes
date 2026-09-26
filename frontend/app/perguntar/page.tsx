"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Cartao, Erro } from "@/components/Estado";
import { SeloNatureza } from "@/components/SeloNatureza";

interface Resposta {
  pergunta: string;
  geracao_tse: string;
  natureza: "ANALISE" | "CONTEXTO";
  aviso: string;
  recusada: boolean;
  recusa: { motivo: string; explicacao: string; alternativa: string } | null;
  criterio: string | null;
  resposta: string | null;
  calculo: string | null;
  dados_usados: { ferramenta: string; argumentos: Record<string, unknown>; resultado: Record<string, unknown> }[];
  links?: { rotulo: string; href: string }[];
}

const FERRAMENTAS: Record<string, string> = {
  search_candidates: "Busca de candidaturas", get_candidate: "Dados da candidatura",
  get_candidate_assets: "Bens declarados", get_candidate_history: "Histórico de candidaturas",
  compare_candidates: "Comparação", get_candidate_position: "Posição no universo",
  get_party_statistics: "Estatísticas do partido", get_state_statistics: "Estatísticas da UF",
  calculate_statistics: "Estatísticas", get_source: "Fonte",
};

const EXEMPLOS = [
  "Quantas candidaturas a governador existem em SP e qual a mediana do patrimônio declarado?",
  "Qual a distribuição por gênero das candidaturas a deputado federal no RJ?",
  "Quantas candidaturas anteriores tem o candidato número 1234 em MG?",
  "Compare o patrimônio declarado dos candidatos a senador no DF.",
];

export default function PaginaPerguntar() {
  const [status, setStatus] = useState<{ configurada: boolean; modelo: string | null } | null>(null);
  const [texto, setTexto] = useState("");
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aguardando, setAguardando] = useState(false);

  useEffect(() => {
    api<{ configurada: boolean; modelo: string | null }>("/perguntar/status").then(setStatus).catch(() => setStatus(null));
  }, []);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (texto.trim().length < 3) return;
    setAguardando(true); setErro(null); setR(null);
    try {
      const resp = await fetch("/api/perguntar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pergunta: texto.trim() }),
      });
      const j = await resp.json();
      if (!resp.ok) throw new Error(typeof j.detail === "string" ? j.detail : `Erro ${resp.status}`);
      setR(j);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setAguardando(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Pergunte aos dados</h1>
        <p className="mt-1 text-sm text-texto-2">
          Faça uma pergunta sobre as candidaturas de 2026. A IA consulta só as funções deste laboratório (busca,
          candidato, comparação, estatísticas, fonte) e explica o que elas retornaram. Ela não recomenda voto, não
          classifica candidatos e não faz inferências pessoais.
        </p>
        {status && !status.configurada && (
          <p className="mt-2 rounded border border-aviso-borda bg-aviso-fundo p-2 text-sm text-aviso-texto">
            A IA não está configurada no servidor (variável NVIDIA_API_KEY). Perguntas que pedem recomendação ou
            ranking continuam sendo respondidas com a explicação da recusa.
          </p>
        )}
      </header>

      <form onSubmit={enviar} className="space-y-2 rounded-lg border border-borda bg-superficie p-3">
        <label htmlFor="pergunta" className="sr-only">Pergunta</label>
        <textarea id="pergunta" value={texto} onChange={(e) => setTexto(e.target.value)} rows={3} maxLength={500}
          placeholder="Ex.: Qual a mediana do patrimônio declarado dos candidatos a deputado estadual no RJ?"
          className="w-full rounded border border-borda bg-superficie px-3 py-2 text-sm" />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1">
            {EXEMPLOS.map((ex) => (
              <button key={ex} type="button" onClick={() => setTexto(ex)}
                className="rounded border border-borda px-2 py-0.5 text-left text-xs text-texto-2 hover:bg-superficie-2">{ex}</button>
            ))}
          </div>
          <button disabled={aguardando || texto.trim().length < 3} className="rounded bg-serie px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50">
            {aguardando ? "Consultando…" : "Perguntar"}
          </button>
        </div>
        {status?.modelo && <p className="text-[11px] text-texto-3">Modelo: {status.modelo}</p>}
      </form>

      {aguardando && <p className="text-sm text-texto-2">Consultando os dados — pode levar alguns segundos.</p>}
      {erro && <Erro mensagem={erro} />}

      {r?.recusada && r.recusa && (
        <Cartao titulo="Pergunta não respondida">
          <p className="text-sm">{r.recusa.explicacao}</p>
          <p className="mt-2 text-sm text-texto-2"><b>O que é possível:</b> {r.recusa.alternativa}</p>
        </Cartao>
      )}

      {r && !r.recusada && (
        <div className="space-y-3">
          <Cartao>
            <div className="mb-2 flex items-center gap-2">
              <h2 className="text-base font-semibold">Resposta</h2><SeloNatureza natureza="ANALISE" />
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{r.resposta}</p>
            {r.links && r.links.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {r.links.map((l) => (
                  <Link key={l.href} href={l.href}
                    className="rounded border border-borda bg-superficie-2 px-3 py-1 text-sm text-destaque hover:underline">
                    {l.rotulo} →
                  </Link>
                ))}
              </div>
            )}
            <p className="mt-3 text-xs text-texto-3">{r.aviso} Base: geração TSE {r.geracao_tse}.</p>
          </Cartao>
          {r.criterio && (
            <Cartao titulo="Como a pergunta foi interpretada"><p className="text-sm text-texto-2">{r.criterio}</p></Cartao>
          )}
          {r.calculo && (
            <Cartao titulo="Cálculo"><p className="text-sm text-texto-2">{r.calculo}</p></Cartao>
          )}
          <Cartao titulo={`Dados usados (${r.dados_usados.length})`}>
            {r.dados_usados.length === 0 ? <p className="text-sm text-texto-2">Nenhuma consulta foi feita.</p> : (
              <ul className="space-y-2">
                {r.dados_usados.map((d, i) => (
                  <li key={i}>
                    <details className="rounded border border-borda">
                      <summary className="cursor-pointer px-3 py-1.5 text-sm">
                        {FERRAMENTAS[d.ferramenta] ?? d.ferramenta}{" "}
                        <span className="font-mono text-xs text-texto-3">{JSON.stringify(d.argumentos)}</span>
                        {"erro" in d.resultado && <span className="ml-2 text-xs text-aviso-texto">(erro)</span>}
                      </summary>
                      <pre className="max-h-80 overflow-auto border-t border-borda bg-superficie-2 p-3 text-[11px] leading-snug">
                        {JSON.stringify(d.resultado, null, 2)}
                      </pre>
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </Cartao>
        </div>
      )}
    </div>
  );
}
