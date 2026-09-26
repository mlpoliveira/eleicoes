"use client";

import { useEffect, useState } from "react";
import { api, type RespostaEstatisticas, type RespostaFiltros } from "@/lib/api";
import { moedaCompacta, numero, pct, titulo } from "@/lib/formato";
import { Alertas, Carregando, Erro } from "@/components/Estado";
import { SelectFiltro, SelectSimNao } from "@/components/Filtro";
import { FiguraGrafico } from "@/components/FiguraGrafico";
import { BarrasHorizontais, Histograma } from "@/components/Barras";
import { Exportar } from "@/components/Exportar";

const FONTE = "TSE — Dados Abertos, candidatos 2026";

function Cartao({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe: string }) {
  return (
    <div className="rounded-lg border border-borda bg-superficie p-4">
      <p className="text-xs text-texto-2">{rotulo}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{valor}</p>
      <p className="mt-1 text-[11px] text-texto-3">{detalhe}</p>
    </div>
  );
}

export default function Inicio() {
  const [filtros, setFiltros] = useState<RespostaFiltros | null>(null);
  const [uf, setUf] = useState("");
  const [cargo, setCargo] = useState("");
  const [naUrna, setNaUrna] = useState("");
  const [est, setEst] = useState<RespostaEstatisticas | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<RespostaFiltros>("/filtros").then(setFiltros).catch((e: Error) => setErro(e.message));
  }, []);

  useEffect(() => {
    setEst(null);
    api<RespostaEstatisticas>("/estatisticas", {
      uf, cd_cargo: cargo, na_urna: naUrna, metrica: "total_bens", bins: 16,
      categoricas: ["cd_cargo", "na_urna", "historico_disponivel", "declarou_bens"],
    }).then(setEst).catch((e: Error) => setErro(e.message));
  }, [uf, cargo, naUrna]);

  const cat = (d: string) => est?.categoricas.find((c) => c.dimensao === d)?.itens ?? [];
  const contar = (d: string, v: unknown) => cat(d).find((i) => i.valor === v);
  const n = est?.universo.n ?? 0;
  const naUrnaSim = contar("na_urna", true);
  const histSim = contar("historico_disponivel", true);
  const cargos = cat("cd_cargo");
  const num = est?.numerica;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">Candidaturas registradas — Eleições 2026</h1>
        <p className="mt-1 max-w-3xl text-sm text-texto-2">
          Dados oficiais do TSE, com a natureza e a fonte de cada informação. O laboratório mostra o que
          os dados registram e o que se calcula a partir deles; as conclusões são de quem consulta.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-borda bg-superficie p-3">
        <SelectFiltro id="f-uf" rotulo="UF" valores={filtros?.filtros.uf?.valores} valor={uf} onChange={setUf} />
        <SelectFiltro id="f-cargo" rotulo="Cargo" valores={filtros?.filtros.cd_cargo?.valores} valor={cargo} onChange={setCargo} cargo />
        <SelectSimNao id="f-urna" rotulo="Na urna" valor={naUrna} onChange={setNaUrna} />
      </div>

      {erro && <Erro mensagem={erro} />}
      {!est && !erro && <Carregando />}
      {est && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-texto-2">
              Universo: <b className="text-texto">{est.universo.descricao}</b> · n = {numero(n)}
            </p>
            <Exportar caminho="estatisticas" params={{ uf, cd_cargo: cargo, na_urna: naUrna, metrica: "total_bens",
              categoricas: ["cd_cargo", "na_urna", "historico_disponivel", "genero", "cor_raca", "grau_instrucao", "faixa_etaria"] }} />
          </div>
          <Alertas itens={est.universo.alertas} />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Cartao rotulo="Candidaturas no universo" valor={numero(n)} detalhe="DADO · registros de candidatura" />
            <Cartao rotulo="Na urna" valor={numero(naUrnaSim?.n ?? 0)}
              detalhe={`CÁLCULO · ${pct(naUrnaSim?.pct)} do universo (campo ST_CANDIDATO_INSERIDO_URNA)`} />
            <Cartao rotulo="Com histórico no arquivo do TSE" valor={numero(histSim?.n ?? 0)}
              detalhe={`CÁLCULO · ${pct(histSim?.pct)}; os demais têm histórico não disponível (não significa estreia)`} />
            <Cartao rotulo="Com bens no arquivo do TSE" valor={numero(num?.n_com_dado ?? 0)}
              detalhe={`CÁLCULO · ${numero(num?.n_sem_dado ?? 0)} sem bens no arquivo (patrimônio não disponível, não zero)`} />
          </div>

          <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-2">
            <FiguraGrafico
              titulo="Candidaturas por cargo"
              unidade="número de candidaturas"
              universo={`${est.universo.descricao} (n = ${numero(n)})`}
              periodo={`geração TSE ${est.geracao_tse}`}
              fonte={`${FONTE}, arquivo consulta_cand (CD_CARGO)`}
              observacao="Ordem pelo código do cargo no TSE."
              tabela={{ colunas: ["Cargo", "Candidaturas", "% do universo"],
                linhas: cargos.map((c) => [titulo(String(c.valor).replace(/^\d+ - /, "")), numero(c.n), pct(c.pct)]) }}
            >
              {cargos.length ? (
                <BarrasHorizontais
                  rotulo="Barras: candidaturas por cargo"
                  categorias={cargos.map((c) => titulo(String(c.valor).replace(/^\d+ - /, "")))}
                  valores={cargos.map((c) => c.n)}
                  formatar={(v) => numero(v)}
                />
              ) : <p className="text-sm text-texto-2">Nenhuma candidatura no universo.</p>}
            </FiguraGrafico>

            {num?.histograma && (
              <FiguraGrafico
                titulo="Distribuição do patrimônio declarado (soma dos bens)"
                unidade="número de candidaturas por faixa de valor (R$, escala logarítmica)"
                universo={`${est.universo.descricao}, com bens no arquivo (n = ${numero(num.n_com_dado)})`}
                periodo={`geração TSE ${est.geracao_tse}`}
                fonte={`${FONTE}, arquivo bem_candidato (VR_BEM_CANDIDATO)`}
                observacao={`${num.exclusao} Mediana: ${moedaCompacta(num.mediana ?? 0)}.${num.histograma.n_fora_da_escala ? ` ${numero(num.histograma.n_fora_da_escala)} com soma igual a zero, fora da escala logarítmica.` : ""}`}
                tabela={{ colunas: ["Faixa (R$)", "Candidaturas"],
                  linhas: num.histograma.faixas.map((f) => [`${moedaCompacta(f.inicio)} a ${moedaCompacta(f.fim)}`, numero(f.n)]) }}
              >
                <Histograma rotulo="Histograma do patrimônio declarado" faixas={num.histograma.faixas} formatarBorda={moedaCompacta} />
              </FiguraGrafico>
            )}
          </div>
        </>
      )}
    </div>
  );
}
