"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type RespostaFiltros } from "@/lib/api";
import { SeletorCarga, useCargas, type InfoCarga } from "@/lib/cargas";
import { moeda, numero, titulo } from "@/lib/formato";
import { Carregando, Erro } from "@/components/Estado";
import { SelectFiltro } from "@/components/Filtro";
import { SeloNatureza } from "@/components/SeloNatureza";

interface Item {
  sq_candidato: number;
  campo: string;
  antes: string | null;
  depois: string | null;
  nm_urna: string | null;
  ds_cargo: string | null;
  sg_uf: string | null;
  sg_partido: string | null;
  na_carga_atual: boolean;
}
interface Resposta {
  descricao: string;
  carga: InfoCarga;
  carga_anterior: InfoCarga | null;
  campos: Record<string, string>;
  total: number;
  resumo: { campo: string; rotulo: string; n: number }[];
  transicoes: { campo: string; antes: string | null; depois: string | null; n: number }[];
  itens: Item[];
  mensagem: string | null;
}

const POR_PAGINA = 100;

/** Valor antes/depois como o TSE registrou; vazio aparece por extenso. */
function Valor({ campo, v }: { campo: string; v: string | null }) {
  if (v === null) return campo === "candidato" ? <span className="text-texto-3">—</span> : <span className="ausente">sem valor</span>;
  if (campo === "total_bens") return <>{moeda(Number(v))}</>;
  if (campo === "na_urna") return <>{v === "true" ? "Sim" : v === "false" ? "Não" : v}</>;
  if (campo === "candidato") return <>{v === "novo" ? "registro novo" : v === "removido" ? "registro removido" : v}</>;
  return <>{v}</>;
}

export default function PaginaAlteracoes() {
  const cargas = useCargas();
  const [carga, setCarga] = useState("");
  const [campo, setCampo] = useState("");
  const [uf, setUf] = useState("");
  const [cargo, setCargo] = useState("");
  const [pagina, setPagina] = useState(1);
  const [filtros, setFiltros] = useState<RespostaFiltros | null>(null);
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<RespostaFiltros>("/filtros").then(setFiltros).catch(() => undefined);
  }, []);
  useEffect(() => {
    setR(null);
    api<Resposta>("/alteracoes", { carga_id: carga, campo, uf, cd_cargo: cargo, pagina, por_pagina: POR_PAGINA })
      .then(setR).catch((e: Error) => setErro(e.message));
  }, [carga, campo, uf, cargo, pagina]);

  const mudar = (f: (v: string) => void) => (v: string) => { f(v); setPagina(1); };
  const paginas = r ? Math.max(1, Math.ceil(r.total / POR_PAGINA)) : 1;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Alterações desde a última atualização</h1>
        <p className="mt-1 max-w-3xl text-sm text-texto-2">
          O TSE regera os arquivos várias vezes ao dia até a eleição. Esta tela compara a carga escolhida com a
          anterior, campo a campo, e mostra os valores exatamente como o TSE os registrou em cada geração.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-borda bg-superficie p-3">
        <SeletorCarga cargas={cargas} valor={carga} onChange={mudar(setCarga)} />
        <label className="flex flex-col text-xs text-texto-2">
          Campo
          <select value={campo} onChange={(e) => mudar(setCampo)(e.target.value)}
            className="mt-0.5 rounded border border-borda bg-superficie px-2 py-1 text-sm text-texto">
            <option value="">Todos</option>
            {r && Object.entries(r.campos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <SelectFiltro id="alt-uf" rotulo="UF" valores={filtros?.filtros.uf?.valores} valor={uf} onChange={mudar(setUf)} />
        <SelectFiltro id="alt-cargo" rotulo="Cargo" valores={filtros?.filtros.cd_cargo?.valores} valor={cargo} onChange={mudar(setCargo)} cargo />
      </div>

      {erro && <Erro mensagem={erro} />}
      {!r && !erro && <Carregando />}
      {r && (
        <>
          <p className="text-sm text-texto-2">
            Carga nº {r.carga.carga_id} (geração TSE <b className="text-texto">{r.carga.geracao_tse}</b>)
            {r.carga_anterior && <> comparada com a carga nº {r.carga_anterior.carga_id} (geração {r.carga_anterior.geracao_tse})</>}
            <span className="ml-2"><SeloNatureza natureza="CALCULO" /></span>
          </p>
          {r.mensagem ? (
            <p className="rounded border border-borda bg-superficie p-3 text-sm">{r.mensagem}</p>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <section className="rounded-lg border border-borda bg-superficie p-4">
                  <h2 className="mb-2 text-base font-semibold">Alterações por campo</h2>
                  {r.resumo.length === 0 ? <p className="text-sm text-texto-2">Nenhuma alteração com os filtros escolhidos.</p> : (
                    <table className="w-full text-sm">
                      <tbody>
                        {r.resumo.map((x) => (
                          <tr key={x.campo} className="border-t border-borda first:border-0">
                            <td className="py-1">{x.rotulo}</td>
                            <td className="py-1 text-right tabular-nums">{numero(x.n)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </section>
                <section className="rounded-lg border border-borda bg-superficie p-4">
                  <h2 className="mb-2 text-base font-semibold">Mudanças de situação e registros</h2>
                  {r.transicoes.length === 0 ? <p className="text-sm text-texto-2">Nenhuma.</p> : (
                    <table className="w-full text-sm">
                      <thead className="text-left text-xs text-texto-2">
                        <tr><th className="py-1 font-medium">Campo</th><th className="py-1 font-medium">Antes → depois</th><th className="py-1 text-right font-medium">Registros</th></tr>
                      </thead>
                      <tbody>
                        {r.transicoes.map((t, i) => (
                          <tr key={i} className="border-t border-borda">
                            <td className="py-1 text-texto-2">{r.campos[t.campo] ?? t.campo}</td>
                            <td className="py-1"><Valor campo={t.campo} v={t.antes} /> → <Valor campo={t.campo} v={t.depois} /></td>
                            <td className="py-1 text-right tabular-nums">{numero(t.n)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </section>
              </div>

              <section className="rounded-lg border border-borda bg-superficie">
                <div className="border-b border-borda px-3 py-2 text-sm"><b>{numero(r.total)}</b> {r.total === 1 ? "alteração" : "alterações"}</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-superficie-2 text-left text-xs text-texto-2">
                      <tr>
                        <th scope="col" className="px-3 py-2 font-medium">Candidatura</th>
                        <th scope="col" className="px-3 py-2 font-medium">Campo</th>
                        <th scope="col" className="px-3 py-2 font-medium">Antes</th>
                        <th scope="col" className="px-3 py-2 font-medium">Depois</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.itens.map((i) => (
                        <tr key={`${i.sq_candidato}-${i.campo}`} className="border-t border-borda align-top">
                          <td className="px-3 py-2">
                            {i.na_carga_atual ? (
                              <Link href={`/candidatos/${i.sq_candidato}`} className="font-medium text-destaque hover:underline">{i.nm_urna ?? i.sq_candidato}</Link>
                            ) : <span className="font-medium">{i.nm_urna ?? i.sq_candidato}</span>}
                            <div className="text-xs text-texto-3">
                              {i.ds_cargo ? titulo(i.ds_cargo) : ""} · {i.sg_uf} · {i.sg_partido} · sq {i.sq_candidato}
                              {!i.na_carga_atual && " · não está na carga atual"}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-texto-2">{r.campos[i.campo] ?? i.campo}</td>
                          <td className="px-3 py-2"><Valor campo={i.campo} v={i.antes} /></td>
                          <td className="px-3 py-2"><Valor campo={i.campo} v={i.depois} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {r.total > POR_PAGINA && (
                  <nav aria-label="Paginação" className="flex items-center justify-between border-t border-borda px-3 py-2 text-sm">
                    <button type="button" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)} className="rounded border border-borda px-2 py-1 disabled:opacity-40">Anterior</button>
                    <span className="text-texto-2">Página {pagina} de {numero(paginas)}</span>
                    <button type="button" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)} className="rounded border border-borda px-2 py-1 disabled:opacity-40">Próxima</button>
                  </nav>
                )}
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
