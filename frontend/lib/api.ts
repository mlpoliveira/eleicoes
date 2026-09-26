// Tipos e acesso à API (FastAPI em /api, repassada pelo next.config.ts).

export type Natureza =
  | "DADO" | "CALCULO" | "ANALISE" | "FONTE_EXTERNA" | "DECLARACAO_CANDIDATO" | "CONTEXTO";

export interface Fonte {
  dataset?: string;
  arquivo?: string | null;
  linha?: number | null;
  campo?: string | null;
  observacao?: string;
}

/** Um campo com valor, natureza e fonte (formato de /api/candidatos/{sq} e /api/comparar). */
export interface Campo<T = unknown> {
  valor: T | null;
  natureza: Natureza;
  fonte?: Fonte;
  geracao_tse?: string;
  observacao?: string;
  disponivel?: boolean;
  mensagem?: string;
}

export interface Universo {
  descricao: string;
  n: number;
  filtros: Record<string, unknown>;
  alertas: string[];
}

export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

type Params = Record<string, string | number | boolean | (string | number)[] | null | undefined>;

export function montarQuery(params: Params): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => qs.append(k, String(x)));
    else qs.append(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(caminho: string, params: Params = {}): Promise<T> {
  const r = await fetch(`/api${caminho}${montarQuery(params)}`);
  if (!r.ok) {
    let msg = `Erro ${r.status}`;
    try {
      const j = await r.json();
      if (typeof j.detail === "string") msg = j.detail;
    } catch {
      /* corpo não é JSON */
    }
    throw new ErroApi(r.status, msg);
  }
  return r.json() as Promise<T>;
}

// ---------------------------------------------------------------- respostas
export interface Carga {
  carga_id: number | null;
  geracao_tse: string | null;
  carregada_em?: string;
  qt_candidaturas?: number;
  dataset?: string;
}

export interface ItemBusca {
  sq_candidato: number;
  nr_candidato: string;
  nm_candidato: string;
  nm_urna: string;
  nm_social: string | null;
  sg_uf: string;
  cd_cargo: number;
  ds_cargo: string;
  sg_partido: string;
  nm_federacao: string | null;
  situacao_candidatura: string | null;
  na_urna: boolean | null;
  genero: string | null;
  idade_na_posse: number | null;
  qt_bens: number | null;
  total_bens: number | null;
  historico_disponivel: boolean;
  possui_outro_registro_2026: boolean;
  outros_registros_2026: number[];
  correspondencia: "exata" | "aproximada" | "numero" | null;
  fonte_arquivo: string;
  fonte_linha: number;
}

export interface MetaCampo {
  natureza: Natureza;
  fonte: Fonte;
  geracao_tse: string;
  observacao?: string;
}

export interface RespostaBusca {
  geracao_tse: string;
  total: number;
  pagina: number;
  por_pagina: number;
  itens: ItemBusca[];
  campos: Record<string, MetaCampo>;
  consulta: { criterio_busca: string | null };
}

export interface ValorFiltro {
  valor: string | number | boolean;
  rotulo?: string;
  n: number;
}

export interface RespostaFiltros {
  universo: { n: number };
  filtros: Record<string, { valores?: ValorFiltro[]; n_nao_disponivel: number; min?: number; max?: number }>;
}

export interface ItemCategoria {
  valor: string | number | boolean;
  n: number;
  pct: number | null;
}

export interface Numerica {
  metrica: string;
  rotulo: string;
  unidade: string;
  n_com_dado: number;
  n_sem_dado: number;
  sem_dado_por_motivo: Record<string, number>;
  exclusao: string;
  mensagem?: string;
  media?: number;
  mediana?: number;
  min?: number;
  max?: number;
  desvio_padrao?: number | null;
  percentis?: Record<string, number>;
  histograma?: {
    escala: string;
    faixas: { inicio: number; fim: number; n: number }[];
    n_fora_da_escala?: number;
    observacao: string;
  };
  fonte: Fonte;
}

export interface RespostaEstatisticas {
  geracao_tse: string;
  universo: Universo;
  numerica: Numerica | null;
  categoricas: { dimensao: string; natureza: Natureza; itens: ItemCategoria[] }[];
  fonte: Fonte;
}
