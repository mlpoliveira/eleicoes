"use client";

import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

export interface Cores {
  serie: string;
  superficie: string;
  texto: string;
  texto2: string;
  grade: string;
  borda: string;
}

function lerCores(): Cores {
  const s = getComputedStyle(document.documentElement);
  const v = (n: string) => s.getPropertyValue(n).trim();
  return {
    serie: v("--serie-1"), superficie: v("--superficie"), texto: v("--texto"),
    texto2: v("--texto-2"), grade: v("--grade"), borda: v("--borda"),
  };
}

/** Gráfico ECharts; `opcoes` recebe as cores do tema atual (claro/escuro). */
export function Grafico({ opcoes, altura = 320, rotulo }: {
  opcoes: (c: Cores) => echarts.EChartsCoreOption;
  altura?: number;
  rotulo: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [cores, setCores] = useState<Cores | null>(null);

  useEffect(() => {
    setCores(lerCores());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const trocar = () => setCores(lerCores());
    mq.addEventListener("change", trocar);
    return () => mq.removeEventListener("change", trocar);
  }, []);

  useEffect(() => {
    if (!ref.current || !cores) return;
    const g = echarts.init(ref.current, undefined, { renderer: "canvas" });
    g.setOption(opcoes(cores));
    const ro = new ResizeObserver(() => g.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      g.dispose();
    };
  }, [cores, opcoes]);

  return <div ref={ref} role="img" aria-label={rotulo} style={{ height: altura, width: "100%" }} />;
}
