// Formatação pt-BR. Moeda só é formatada aqui (regra do projeto: nunca na API).

export const NAO_DISPONIVEL = "Não disponível no dataset utilizado";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export function moeda(v: number | null | undefined): string {
  return v === null || v === undefined ? NAO_DISPONIVEL : brl.format(v);
}
export function moedaCompacta(v: number): string {
  return `R$ ${compacto.format(v)}`;
}
export function numero(v: number | null | undefined, casas = 0): string {
  if (v === null || v === undefined) return NAO_DISPONIVEL;
  return (casas ? decimal : inteiro).format(v);
}
export function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? NAO_DISPONIVEL : `${decimal.format(v)}%`;
}
export function simNao(v: boolean | null | undefined): string {
  if (v === null || v === undefined) return NAO_DISPONIVEL;
  return v ? "Sim" : "Não";
}
/** "2026-03-15" -> "15/03/2026" (datas vêm em ISO da API). */
export function data(v: string | null | undefined): string {
  if (!v) return NAO_DISPONIVEL;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : v;
}
/** Título "DEPUTADO FEDERAL" -> "Deputado Federal" (só para rótulos de cargo). */
export function titulo(v: string | null | undefined): string {
  if (!v) return NAO_DISPONIVEL;
  return v.toLowerCase().replace(/(^|\s)(\p{L})/gu, (_, a, b) => a + b.toUpperCase());
}

/** Formata um valor conforme o nome do campo (usado nas páginas de candidato e comparação). */
export function formatarCampo(campo: string, v: unknown): string {
  if (v === null || v === undefined) return NAO_DISPONIVEL;
  if (typeof v === "boolean") return simNao(v);
  // códigos e sequenciais do TSE: identificadores, nunca com separador de milhar
  if (/^(sq_|nr_|cd_)/.test(campo)) return String(v);
  // S/N do TSE: legível, mantendo o valor original
  if (campo === "declarou_bens" && (v === "S" || v === "N")) return v === "S" ? "Sim (S)" : "Não (N)";
  if (["total_bens", "limite_gastos", "valor"].includes(campo) && typeof v === "number") return moeda(v);
  if (campo.startsWith("dt_") && typeof v === "string") return data(v);
  if (campo === "idade_na_posse" && typeof v === "number") return `${v} anos`;
  if (typeof v === "number") return numero(v);
  return String(v);
}
