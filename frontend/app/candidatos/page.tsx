"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, type ItemBusca, type RespostaBusca, type RespostaFiltros } from "@/lib/api";
import { moeda, NAO_DISPONIVEL, numero, titulo } from "@/lib/formato";
import { useComparacao } from "@/lib/comparacao";
import { Carregando, Erro } from "@/components/Estado";
import { SelectFiltro, SelectSimNao } from "@/components/Filtro";
import { SeloNatureza } from "@/components/SeloNatureza";

const POR_PAGINA = 50;
const FILTROS = ["uf", "cd_cargo", "sg_partido", "federacao", "situacao", "genero", "cor_raca", "grau_instrucao"] as const;

// Colunas ordenáveis (a ordenação é sempre escolhida por quem consulta).
const COLUNAS: { chave: string; rotulo: string; ordenavel?: string; direita?: boolean }[] = [
  { chave: "nm_urna", rotulo: "Nome de urna", ordenavel: "nm_urna" },
  { chave: "nr_candidato", rotulo: "Número", ordenavel: "nr_candidato" },
  { chave: "ds_cargo", rotulo: "Cargo", ordenavel: "cd_cargo" },
  { chave: "sg_uf", rotulo: "UF", ordenavel: "sg_uf" },
  { chave: "sg_partido", rotulo: "Partido", ordenavel: "sg_partido" },
  { chave: "situacao_candidatura", rotulo: "Situação", ordenavel: "situacao_candidatura" },
  { chave: "idade_na_posse", rotulo: "Idade na posse", ordenavel: "idade_na_posse", direita: true },
  { chave: "total_bens", rotulo: "Bens declarados (R$)", ordenavel: "total_bens", direita: true },
];

function Celula({ item, chave }: { item: ItemBusca; chave: string }) {
  const v = item[chave as keyof ItemBusca];
  if (chave === "nm_urna")
    return (
      <div>
        <Link href={`/candidatos/${item.sq_candidato}`} className="font-medium text-destaque hover:underline">
          {item.nm_urna}
        </Link>
        <div className="text-xs text-texto-3">{item.nm_candidato}</div>
        <div className="mt-0.5 flex flex-wrap gap-1">
          {item.correspondencia === "aproximada" && (
            <span className="rounded bg-superficie-2 px-1 text-[10px] text-texto-2" title="Nome parecido com o termo buscado (tolerância a erro de digitação)">
              correspondência aproximada
            </span>
          )}
          {item.possui_outro_registro_2026 && (
            <span className="rounded bg-superficie-2 px-1 text-[10px] text-texto-2"
              title={`A mesma pessoa tem outro registro de candidatura em 2026: ${item.outros_registros_2026.join(", ")}`}>
              outro registro em 2026
            </span>
          )}
        </div>
      </div>
    );
  if (chave === "ds_cargo") return <>{titulo(item.ds_cargo)}</>;
  if (chave === "total_bens")
    return item.total_bens === null ? <span className="ausente text-xs">{NAO_DISPONIVEL}</span> : <>{moeda(item.total_bens)}</>;
  if (chave === "idade_na_posse")
    return item.idade_na_posse === null ? <span className="ausente text-xs">{NAO_DISPONIVEL}</span> : <>{item.idade_na_posse}</>;
  if (v === null || v === undefined) return <span className="ausente text-xs">{NAO_DISPONIVEL}</span>;
  return <>{String(v)}</>;
}

function Busca() {
  const params = useSearchParams();
  const router = useRouter();
  const caminho = usePathname();
  const [filtros, setFiltros] = useState<RespostaFiltros | null>(null);
  const [res, setRes] = useState<RespostaBusca | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [termo, setTermo] = useState(params.get("q") ?? "");
  const comp = useComparacao();

  const p = (k: string) => params.get(k) ?? "";
  const pagina = Number(p("pagina") || 1);
  const ordenarPor = p("ordenar_por") || "nm_urna";
  const ordem = p("ordem") || "asc";

  const mudar = (novos: Record<string, string>, voltarPagina1 = true) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(novos)) (v ? q.set(k, v) : q.delete(k));
    if (voltarPagina1 && !("pagina" in novos)) q.delete("pagina");
    router.replace(`${caminho}?${q.toString()}`, { scroll: false });
  };

  useEffect(() => {
    api<RespostaFiltros>("/filtros").then(setFiltros).catch((e: Error) => setErro(e.message));
  }, []);

  const chave = params.toString();
  useEffect(() => {
    setRes(null);
    setErro(null);
    const q = new URLSearchParams(chave);
    const consulta: Record<string, string | number> = { por_pagina: POR_PAGINA };
    q.forEach((v, k) => (consulta[k] = v));
    api<RespostaBusca>("/candidatos", consulta).then(setRes).catch((e: Error) => setErro(e.message));
  }, [chave]);

  const ordenar = (col: string) =>
    mudar({ ordenar_por: col, ordem: ordenarPor === col && ordem === "asc" ? "desc" : "asc" });
  const totalPaginas = res ? Math.max(1, Math.ceil(res.total / POR_PAGINA)) : 1;
  const f = filtros?.filtros;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Candidatos</h1>
        <p className="mt-1 text-sm text-texto-2">
          Busque por nome completo, nome de urna ou número. A busca ignora acentos e maiúsculas e tolera erros de
          digitação. Clique no título de uma coluna para ordenar por ela.
        </p>
      </header>

      <form
        onSubmit={(e) => { e.preventDefault(); mudar({ q: termo.trim() }); }}
        className="space-y-3 rounded-lg border border-borda bg-superficie p-3"
      >
        <div className="flex gap-2">
          <label htmlFor="q" className="sr-only">Nome ou número</label>
          <input id="q" value={termo} onChange={(e) => setTermo(e.target.value)} placeholder="Nome ou número do candidato"
            className="flex-1 rounded border border-borda bg-superficie px-3 py-1.5 text-sm" />
          <button className="rounded bg-serie px-4 py-1.5 text-sm font-medium text-white">Buscar</button>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <SelectFiltro id="uf" rotulo="UF" valores={f?.uf?.valores} valor={p("uf")} onChange={(v) => mudar({ uf: v })} />
          <SelectFiltro id="cargo" rotulo="Cargo" valores={f?.cd_cargo?.valores} valor={p("cd_cargo")} onChange={(v) => mudar({ cd_cargo: v })} cargo />
          <SelectFiltro id="partido" rotulo="Partido" valores={f?.sg_partido?.valores} valor={p("sg_partido")} onChange={(v) => mudar({ sg_partido: v })} />
          <SelectFiltro id="federacao" rotulo="Federação" valores={f?.federacao?.valores} valor={p("federacao")} onChange={(v) => mudar({ federacao: v })} />
          <SelectFiltro id="situacao" rotulo="Situação" valores={f?.situacao?.valores} valor={p("situacao")} onChange={(v) => mudar({ situacao: v })} />
          <SelectFiltro id="genero" rotulo="Gênero" valores={f?.genero?.valores} valor={p("genero")} onChange={(v) => mudar({ genero: v })} />
          <SelectFiltro id="cor" rotulo="Cor/raça" valores={f?.cor_raca?.valores} valor={p("cor_raca")} onChange={(v) => mudar({ cor_raca: v })} />
          <SelectFiltro id="instrucao" rotulo="Grau de instrução" valores={f?.grau_instrucao?.valores} valor={p("grau_instrucao")} onChange={(v) => mudar({ grau_instrucao: v })} />
          <label className="flex flex-col text-xs text-texto-2">
            Idade na posse
            <span className="mt-0.5 flex items-center gap-1">
              <input aria-label="Idade mínima" type="number" min={0} max={130} defaultValue={p("idade_min")}
                onBlur={(e) => mudar({ idade_min: e.target.value })} className="w-16 rounded border border-borda bg-superficie px-2 py-1 text-sm" />
              a
              <input aria-label="Idade máxima" type="number" min={0} max={130} defaultValue={p("idade_max")}
                onBlur={(e) => mudar({ idade_max: e.target.value })} className="w-16 rounded border border-borda bg-superficie px-2 py-1 text-sm" />
            </span>
          </label>
          <SelectSimNao id="urna" rotulo="Na urna" valor={p("na_urna")} onChange={(v) => mudar({ na_urna: v })} />
          {(FILTROS.some((k) => p(k)) || p("q") || p("na_urna") || p("idade_min") || p("idade_max")) && (
            <button type="button" onClick={() => { setTermo(""); router.replace(caminho); }}
              className="rounded border border-borda px-2 py-1 text-xs text-texto-2 hover:bg-superficie-2">
              Limpar filtros
            </button>
          )}
        </div>
      </form>

      {erro && <Erro mensagem={erro} />}
      {!res && !erro && <Carregando />}
      {res && (
        <section className="rounded-lg border border-borda bg-superficie">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-borda px-3 py-2 text-sm">
            <span>
              <b>{numero(res.total)}</b> {res.total === 1 ? "registro encontrado" : "registros encontrados"}
              <span className="ml-2"><SeloNatureza natureza="DADO" /></span>
              <span className="ml-1 text-xs text-texto-3">geração TSE {res.geracao_tse}</span>
            </span>
            {res.consulta.criterio_busca && <span className="max-w-3xl text-xs text-texto-3">Critério: {res.consulta.criterio_busca}</span>}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-superficie-2 text-left text-xs text-texto-2">
                <tr>
                  {COLUNAS.map((c) => (
                    <th key={c.chave} scope="col" className={`px-3 py-2 font-medium ${c.direita ? "text-right" : ""}`}
                      aria-sort={ordenarPor === c.ordenavel ? (ordem === "asc" ? "ascending" : "descending") : undefined}>
                      {c.ordenavel ? (
                        <button type="button" onClick={() => ordenar(c.ordenavel!)} className="hover:text-texto">
                          {c.rotulo} {ordenarPor === c.ordenavel ? (ordem === "asc" ? "▲" : "▼") : ""}
                        </button>
                      ) : c.rotulo}
                    </th>
                  ))}
                  <th scope="col" className="px-3 py-2 font-medium">Comparar</th>
                </tr>
              </thead>
              <tbody>
                {res.itens.map((it) => (
                  <tr key={it.sq_candidato} className="border-t border-borda align-top hover:bg-superficie-2/50">
                    {COLUNAS.map((c) => (
                      <td key={c.chave} className={`px-3 py-2 ${c.direita ? "text-right tabular-nums" : ""}`}>
                        <Celula item={it} chave={c.chave} />
                      </td>
                    ))}
                    <td className="px-3 py-2">
                      {comp.contem(it.sq_candidato) ? (
                        <button type="button" onClick={() => comp.remover(it.sq_candidato)} className="text-xs text-texto-2 underline">Remover</button>
                      ) : (
                        <button type="button" disabled={comp.cheio}
                          onClick={() => comp.adicionar({ sq: it.sq_candidato, nome: it.nm_urna, cargo: titulo(it.ds_cargo), uf: it.sg_uf })}
                          className="text-xs text-destaque underline disabled:text-texto-3 disabled:no-underline"
                          title={comp.cheio ? "Limite de 5 candidatos na comparação" : undefined}>
                          Adicionar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {res.total > POR_PAGINA && (
            <nav aria-label="Paginação" className="flex items-center justify-between border-t border-borda px-3 py-2 text-sm">
              <button type="button" disabled={pagina <= 1} onClick={() => mudar({ pagina: String(pagina - 1) }, false)}
                className="rounded border border-borda px-2 py-1 disabled:opacity-40">Anterior</button>
              <span className="text-texto-2">Página {pagina} de {numero(totalPaginas)}</span>
              <button type="button" disabled={pagina >= totalPaginas} onClick={() => mudar({ pagina: String(pagina + 1) }, false)}
                className="rounded border border-borda px-2 py-1 disabled:opacity-40">Próxima</button>
            </nav>
          )}
        </section>
      )}
    </div>
  );
}

export default function PaginaCandidatos() {
  return (
    <Suspense fallback={<Carregando />}>
      <Busca />
    </Suspense>
  );
}
