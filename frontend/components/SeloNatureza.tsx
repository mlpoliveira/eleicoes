import type { Natureza } from "@/lib/api";

// Rótulo de natureza da informação (regra 2 do CLAUDE.md).
const INFO: Record<Natureza, { rotulo: string; explicacao: string }> = {
  DADO: { rotulo: "DADO", explicacao: "Valor lido diretamente da base oficial do TSE." },
  CALCULO: { rotulo: "CÁLCULO", explicacao: "Métrica derivada dos dados do TSE; o cálculo está descrito." },
  ANALISE: { rotulo: "ANÁLISE", explicacao: "Interpretação estatística dos dados; não é fato." },
  FONTE_EXTERNA: { rotulo: "FONTE EXTERNA", explicacao: "Informação de fonte fora da base do TSE." },
  DECLARACAO_CANDIDATO: {
    rotulo: "DECLARAÇÃO",
    explicacao: "Texto declarado pelo próprio candidato à Justiça Eleitoral.",
  },
  CONTEXTO: { rotulo: "CONTEXTO", explicacao: "Informação de contexto para leitura dos dados." },
};

export function SeloNatureza({ natureza }: { natureza: Natureza }) {
  const i = INFO[natureza] ?? { rotulo: natureza, explicacao: "" };
  return (
    <span
      title={i.explicacao}
      className="inline-block rounded border border-borda bg-superficie-2 px-1.5 py-px text-[10px] font-semibold tracking-wide text-texto-2 align-middle"
    >
      {i.rotulo}
    </span>
  );
}
