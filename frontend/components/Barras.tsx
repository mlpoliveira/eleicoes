"use client";

import { useCallback } from "react";
import { Grafico, type Cores } from "./Grafico";

const eixo = (c: Cores) => ({
  axisLine: { lineStyle: { color: c.borda } },
  axisTick: { show: false },
  axisLabel: { color: c.texto2, fontSize: 11 },
  splitLine: { lineStyle: { color: c.grade } },
});

const dica = (c: Cores) => ({
  backgroundColor: c.superficie, borderColor: c.borda, textStyle: { color: c.texto, fontSize: 12 },
});

/** Barras horizontais de uma série (ex.: candidaturas por cargo). Ordem = a recebida. */
export function BarrasHorizontais({ categorias, valores, formatar, rotulo }: {
  categorias: string[];
  valores: number[];
  formatar: (v: number) => string;
  rotulo: string;
}) {
  const opcoes = useCallback((c: Cores) => ({
    animation: false,
    grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "item", ...dica(c),
      formatter: (p: { name: string; value: number }) => `${p.name}<br/><b>${formatar(p.value)}</b>`,
    },
    xAxis: { type: "value", ...eixo(c), axisLabel: { ...eixo(c).axisLabel, formatter: formatar } },
    yAxis: { type: "category", inverse: true, data: categorias, ...eixo(c), splitLine: { show: false } },
    series: [{
      type: "bar", data: valores, barMaxWidth: 24,
      itemStyle: { color: c.serie, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: "right", color: c.texto2, fontSize: 11, formatter: (p: { value: number }) => formatar(p.value) },
    }],
  }), [categorias, valores, formatar]);
  return <Grafico opcoes={opcoes} altura={Math.max(120, categorias.length * 30 + 16)} rotulo={rotulo} />;
}

/** Histograma: colunas encostadas separadas por 2px de superfície. */
export function Histograma({ faixas, formatarBorda, rotulo }: {
  faixas: { inicio: number; fim: number; n: number }[];
  formatarBorda: (v: number) => string;
  rotulo: string;
}) {
  const opcoes = useCallback((c: Cores) => {
    // eixo: só o início da faixa (rótulos curtos); tooltip e tabela mostram a faixa completa
    const nomes = faixas.map((f) => formatarBorda(f.inicio));
    const faixa = (i: number) => `${formatarBorda(faixas[i].inicio)} a ${formatarBorda(faixas[i].fim)}`;
    return {
      animation: false,
      grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "item", ...dica(c),
        formatter: (p: { dataIndex: number; value: number }) =>
          `${faixa(p.dataIndex)}<br/><b>${p.value.toLocaleString("pt-BR")} ${p.value === 1 ? "candidatura" : "candidaturas"}</b>`,
      },
      xAxis: { type: "category", data: nomes, ...eixo(c), axisLabel: { ...eixo(c).axisLabel, hideOverlap: true } },
      yAxis: { type: "value", minInterval: 1, ...eixo(c) },
      series: [{
        type: "bar", data: faixas.map((f) => f.n), barCategoryGap: 2,
        itemStyle: { color: c.serie, borderRadius: [4, 4, 0, 0] },
      }],
    };
  }, [faixas, formatarBorda]);
  return <Grafico opcoes={opcoes} altura={280} rotulo={rotulo} />;
}
