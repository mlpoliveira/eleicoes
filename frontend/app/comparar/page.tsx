"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Campo, type ItemBusca, type RespostaBusca } from "@/lib/api";
import { formatarCampo, moeda, NAO_DISPONIVEL, numero, titulo } from "@/lib/formato";
import { MAX_COMPARAR, useComparacao } from "@/lib/comparacao";
import { Alertas, Cartao, Carregando, Erro } from "@/components/Estado";
import { SeloNatureza } from "@/components/SeloNatureza";
import { VerFonte } from "@/components/VerFonte";

interface Linha {
  secao: string;
  campo: string;
  natureza: Campo["natureza"];
  iguais?: boolean;
  valores: (Campo & { valor: unknown })[];
}
interface Diferenca {
  campo: string;
  rotulo: string;
  natureza: Campo["natureza"];
  texto: string;
  valores: { sq_candidato: number; nm_urna: string; valor: number | string | null }[];
}
interface Comparacao {
  geracao_tse: string;
  candidatos: { sq_candidato: number; nm_urna: string; nr_candidato: string; ds_cargo: string; sg_uf: string; sg_partido: string }[];
  verificacoes: Record<string, boolean>;
  alertas: string[];
  tabela: Linha[];
  diferencas: { titulo: string; descricao: string; itens: Diferenca[] };
}

const SECOES: Record<string, string> = {
  eleitoral: "Eleitoral", perfil: "Perfil", patrimonio: "Patrimônio", historico: "Histórico", redes: "Redes sociais",
};
const ROTULOS: Record<string, string> = {
  nr_candidato: "Número", nm_urna: "Nome de urna", cd_cargo: "Código do cargo", ds_cargo: "Cargo", sg_uf: "UF",
  nm_ue: "Unidade eleitoral", sg_partido: "Partido", nm_federacao: "Federação", situacao_candidatura: "Situação da candidatura",
  situacao_campo_origem: "Campo de origem da situação", na_urna: "Na urna", limite_gastos: "Limite de gastos",
  idade_na_posse: "Idade na posse", genero: "Gênero", cor_raca: "Cor/raça", grau_instrucao: "Grau de instrução",
  estado_civil: "Estado civil", ocupacao: "Ocupação declarada", uf_nascimento: "UF de nascimento", nacionalidade: "Nacionalidade",
  declarou_bens: "Declarou bens", qt_bens: "Quantidade de bens", total_bens: "Patrimônio declarado (soma)",
  por_categoria: "Patrimônio por categoria", historico_disponivel: "Histórico disponível",
  qt_candidaturas_anteriores: "Candidaturas anteriores identificadas", qt_vezes_eleito: "Anteriores com resultado 'Eleito'",
  ultimo_cargo_eleito: "Último cargo com resultado 'Eleito'", redes: "Endereços informados",
};
const VERIFICACOES: Record<string, string> = {
  mesmo_cargo: "Mesmo cargo", mesma_uf: "Mesma UF", mesmo_partido: "Mesmo partido",
  historico_disponivel_para_todos: "Histórico disponível para todos", bens_disponiveis_para_todos: "Bens no arquivo para todos",
};

function ValorCelula({ linha, v, sq }: { linha: Linha; v: Linha["valores"][number]; sq: number }) {
  if (linha.campo === "por_categoria") {
    const itens = (v.valor as { categoria: string | null; qt: number; total: number | null }[]) ?? [];
    if (!itens.length) return <span className="ausente">{NAO_DISPONIVEL}</span>;
    return (
      <ul className="space-y-0.5">
        {itens.map((c) => <li key={c.categoria ?? "—"}>{c.categoria ?? "sem categoria"}: {moeda(c.total)} ({numero(c.qt)})</li>)}
      </ul>
    );
  }
  if (linha.campo === "redes") {
    const itens = (v.valor as { plataforma: string; url: string }[]) ?? [];
    if (!itens.length) return <span className="ausente">nenhum endereço no arquivo</span>;
    return <ul>{itens.map((r) => <li key={r.url}>{r.plataforma}</li>)}</ul>;
  }
  const ausente = v.valor === null || v.valor === undefined;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5">
      <span className={`[overflow-wrap:anywhere] ${ausente ? "ausente" : ""}`}>{ausente ? NAO_DISPONIVEL : formatarCampo(linha.campo, v.valor)}</span>
      <VerFonte consulta={{ tabela: "candidato", sq, campo: linha.campo }} fonte={v.fonte} geracao={v.geracao_tse} observacao={v.observacao} />
    </span>
  );
}

function Adicionar() {
  const comp = useComparacao();
  const [termo, setTermo] = useState("");
  const [res, setRes] = useState<ItemBusca[] | null>(null);
  const buscar = (e: React.FormEvent) => {
    e.preventDefault();
    if (!termo.trim()) return;
    api<RespostaBusca>("/candidatos", { q: termo.trim(), por_pagina: 8 }).then((r) => setRes(r.itens)).catch(() => setRes([]));
  };
  return (
    <div>
      <form onSubmit={buscar} className="flex gap-2">
        <label htmlFor="busca-comparar" className="sr-only">Buscar candidato para comparar</label>
        <input id="busca-comparar" value={termo} onChange={(e) => setTermo(e.target.value)} placeholder="Nome ou número"
          className="flex-1 rounded border border-borda bg-superficie px-3 py-1.5 text-sm" disabled={comp.cheio} />
        <button className="rounded border border-borda px-3 py-1.5 text-sm hover:bg-superficie-2" disabled={comp.cheio}>Buscar</button>
      </form>
      {res && (
        <ul className="mt-2 divide-y divide-borda rounded border border-borda text-sm">
          {res.length === 0 && <li className="p-2 text-texto-2">Nenhum registro encontrado.</li>}
          {res.map((it) => (
            <li key={it.sq_candidato} className="flex items-center justify-between gap-2 p-2">
              <span>
                <b>{it.nm_urna}</b> <span className="text-texto-2">— {titulo(it.ds_cargo)} · {it.sg_uf} · {it.sg_partido} · nº {it.nr_candidato}</span>
              </span>
              <button type="button" disabled={comp.contem(it.sq_candidato) || comp.cheio}
                onClick={() => comp.adicionar({ sq: it.sq_candidato, nome: it.nm_urna, cargo: titulo(it.ds_cargo), uf: it.sg_uf })}
                className="text-xs text-destaque underline disabled:text-texto-3 disabled:no-underline">
                {comp.contem(it.sq_candidato) ? "já incluído" : "Adicionar"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PaginaComparar() {
  const comp = useComparacao();
  const [dados, setDados] = useState<Comparacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const chave = comp.lista.map((s) => s.sq).join(",");

  useEffect(() => {
    setDados(null);
    setErro(null);
    if (chave.split(",").filter(Boolean).length < 2) return;
    api<Comparacao>("/comparar", { sq: chave }).then(setDados).catch((e: Error) => setErro(e.message));
  }, [chave]);

  const secoes = dados ? [...new Set(dados.tabela.map((l) => l.secao))] : [];

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Comparar candidaturas</h1>
        <p className="mt-1 text-sm text-texto-2">
          Escolha de 2 a {MAX_COMPARAR} candidatos. A seleção fica guardada só neste navegador. A comparação mostra os dados
          lado a lado e as diferenças encontradas, sem apontar qual é preferível.
        </p>
      </header>

      <Cartao titulo={`Selecionados (${comp.lista.length} de ${MAX_COMPARAR})`}>
        {comp.lista.length === 0 && <p className="mb-2 text-sm text-texto-2">Nenhum candidato selecionado. Busque abaixo ou use “Adicionar” na lista de candidatos.</p>}
        <ul className="mb-3 flex flex-wrap gap-2">
          {comp.lista.map((s) => (
            <li key={s.sq} className="flex items-center gap-2 rounded border border-borda bg-superficie-2 px-2 py-1 text-sm">
              <Link href={`/candidatos/${s.sq}`} className="hover:underline">{s.nome}</Link>
              <span className="text-xs text-texto-3">{s.cargo} · {s.uf}</span>
              <button type="button" onClick={() => comp.remover(s.sq)} aria-label={`Remover ${s.nome}`} className="text-texto-3 hover:text-texto">×</button>
            </li>
          ))}
          {comp.lista.length > 0 && (
            <li><button type="button" onClick={comp.limpar} className="px-2 py-1 text-xs text-texto-2 underline">limpar seleção</button></li>
          )}
        </ul>
        <Adicionar />
      </Cartao>

      {erro && <Erro mensagem={erro} />}
      {comp.lista.length >= 2 && !dados && !erro && <Carregando />}
      {dados && (
        <>
          <Alertas itens={dados.alertas} />
          <div className="flex flex-wrap gap-2 text-xs">
            {Object.entries(dados.verificacoes).map(([k, v]) => (
              <span key={k} className="rounded border border-borda bg-superficie px-2 py-1">
                {VERIFICACOES[k] ?? k}: <b>{v ? "sim" : "não"}</b>
              </span>
            ))}
          </div>

          <Cartao titulo={dados.diferencas.titulo}>
            <p className="mb-2 text-xs text-texto-3">{dados.diferencas.descricao}</p>
            {dados.diferencas.itens.length === 0 ? <p className="text-sm text-texto-2">Nenhuma diferença nos campos verificados.</p> : (
              <ul className="space-y-2 text-sm">
                {dados.diferencas.itens.map((d) => (
                  <li key={d.campo}>
                    <span className="mr-2 font-medium">{d.rotulo}</span><SeloNatureza natureza={d.natureza} />
                    <p className="text-texto-2">{d.texto}</p>
                    {d.campo === "total_bens" && (
                      <p className="text-texto-2">{d.valores.map((v) => `${v.nm_urna}: ${moeda(v.valor as number | null)}`).join("; ")}.</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Cartao>

          <section className="overflow-x-auto rounded-lg border border-borda bg-superficie">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-superficie-2 text-left">
                <tr>
                  <th scope="col" className="w-56 px-3 py-2 text-xs font-medium text-texto-2">Campo</th>
                  {dados.candidatos.map((c) => (
                    <th key={c.sq_candidato} scope="col" className="px-3 py-2 align-top">
                      <Link href={`/candidatos/${c.sq_candidato}`} className="text-destaque hover:underline">{c.nm_urna}</Link>
                      <div className="text-xs font-normal text-texto-2">{titulo(c.ds_cargo)} · {c.sg_uf} · {c.sg_partido}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              {secoes.map((s) => (
                <tbody key={s}>
                  <tr><th colSpan={dados.candidatos.length + 1} scope="colgroup" className="bg-superficie-2/60 px-3 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-texto-2">{SECOES[s] ?? s}</th></tr>
                  {dados.tabela.filter((l) => l.secao === s).map((l) => (
                    <tr key={l.campo} className="border-t border-borda align-top">
                      <th scope="row" className="px-3 py-2 text-left font-normal text-texto-2">
                        {ROTULOS[l.campo] ?? l.campo} <SeloNatureza natureza={l.natureza} />
                        {l.iguais && <span className="ml-1 text-[10px] text-texto-3">(igual)</span>}
                      </th>
                      {l.valores.map((v, i) => (
                        <td key={dados.candidatos[i].sq_candidato} className="px-3 py-2">
                          <ValorCelula linha={l} v={v} sq={dados.candidatos[i].sq_candidato} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </section>
          <p className="text-xs text-texto-3">Geração TSE: {dados.geracao_tse}. Cada valor tem “Ver fonte” com arquivo, linha e campo do TSE.</p>
        </>
      )}
    </div>
  );
}
