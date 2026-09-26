"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Campo, type Fonte, type Natureza, type Universo } from "@/lib/api";
import { formatarCampo, moeda, NAO_DISPONIVEL, numero, titulo } from "@/lib/formato";
import { useComparacao } from "@/lib/comparacao";
import { Alertas, Cartao, Carregando, Erro } from "@/components/Estado";
import { MapaCategorias } from "@/components/MapaCategorias";
import { SeloNatureza } from "@/components/SeloNatureza";
import { ValorCampo } from "@/components/ValorCampo";
import { VerFonte } from "@/components/VerFonte";

type Secao = Record<string, Campo>;
interface Lista<T> { campos?: Record<string, { natureza: Natureza; fonte: Fonte; observacao?: string }>; itens: T[] }
type ComFonte = { fonte: { arquivo: string; linha: number } };

interface Detalhe {
  sq_candidato: number;
  geracao_tse: string;
  identificacao: Secao;
  perfil: Secao;
  situacao: Secao;
  patrimonio: {
    declarou_bens: Campo; qt_bens: Campo<number>; total_bens: Campo<number>; mensagem: string | null;
    por_categoria: { descricao: string; itens: { categoria: string | null; qt: number; total: number | null }[] };
    bens: Lista<{ nr_ordem: number; tipo: string; categoria: string | null; descricao: string | null; valor: number | null; valor_original: string; dt_atualizacao: string | null } & ComFonte>;
  };
  redes: Lista<{ nr_ordem: number; url: string; plataforma: string } & ComFonte>;
  historico: {
    disponivel: Campo<boolean>; mensagem: string | null; observacao: string;
    qt_candidaturas_anteriores: Campo<number>; qt_vezes_eleito: Campo<number>; ultimo_cargo_eleito: Campo<string>;
    linha_do_tempo: Lista<{ ano_eleicao: number; turno: number; ds_cargo: string; sg_uf: string; nm_ue: string; sg_partido: string; nr_candidato: string; situacao_julgamento: string | null; resultado: string | null; eleito: boolean; eleicao_atual: boolean } & ComFonte>;
  };
  fundamentos_indeferimento: { descricao: string; mensagem: string | null; itens: ({ tipo: string; motivo: string } & ComFonte)[] };
  outros_registros_2026: { observacao: string; itens: { sq_candidato: number; nm_urna: string; ds_cargo: string; sg_uf: string; situacao_candidatura: string | null }[] };
}

interface Posicao {
  rotulo: string; valor: number | null; percentil: number | null; descricao?: string; mensagem?: string;
  universo: Universo; definicao_percentil?: string; exclusao: string; geracao_tse: string;
}

const ROTULOS: Record<string, string> = {
  sq_candidato: "Sequencial TSE (sq_candidato)", nr_candidato: "Número", nm_candidato: "Nome completo",
  nm_urna: "Nome de urna", nm_social: "Nome social", ds_eleicao: "Eleição", dt_eleicao: "Data da eleição",
  sg_uf: "UF", nm_ue: "Unidade eleitoral", cd_cargo: "Código do cargo", ds_cargo: "Cargo",
  nr_partido: "Número do partido", sg_partido: "Partido", nm_partido: "Nome do partido",
  tp_agremiacao: "Tipo de agremiação", nm_federacao: "Federação", composicao_federacao: "Composição da federação",
  sq_coligacao: "Sequencial da coligação", nm_coligacao: "Coligação", composicao_coligacao: "Composição da coligação",
  dt_nascimento: "Data de nascimento", idade_na_posse: "Idade na data da posse", uf_nascimento: "UF de nascimento",
  municipio_nascimento: "Município de nascimento", nacionalidade: "Nacionalidade", genero: "Gênero",
  cor_raca: "Cor/raça", grau_instrucao: "Grau de instrução", estado_civil: "Estado civil", ocupacao: "Ocupação declarada",
  quilombola: "Quilombola", etnia_indigena: "Etnia indígena",
  situacao_candidatura: "Situação da candidatura", situacao_campo_origem: "Campo de origem da situação",
  situacao_julgamento: "Situação do julgamento", na_urna: "Na urna", destinacao_votos: "Destinação dos votos",
  substituido: "Substituído", sq_substituido: "Sequencial do substituído", nr_processo: "Número do processo",
  limite_gastos: "Limite de gastos de campanha", resultado: "Resultado",
  declarou_bens: "Declarou bens", qt_bens: "Quantidade de bens", total_bens: "Patrimônio declarado (soma)",
  historico_disponivel: "Histórico disponível no arquivo do TSE",
  qt_candidaturas_anteriores: "Candidaturas anteriores identificadas (desde 2004)",
  qt_vezes_eleito: "Candidaturas anteriores com resultado 'Eleito'", ultimo_cargo_eleito: "Último cargo com resultado 'Eleito'",
};

function Secao({ titulo, secao, sq }: { titulo: string; secao: Secao; sq: number }) {
  return (
    <Cartao titulo={titulo}>
      <dl>
        {Object.entries(secao).map(([nome, campo]) => (
          <ValorCampo key={nome} nome={nome} rotulo={ROTULOS[nome] ?? nome} campo={campo} sq={sq} />
        ))}
      </dl>
    </Cartao>
  );
}

function PosicaoNoGrupo({ p }: { p: Posicao | null }) {
  if (!p) return null;
  return (
    <div className="rounded border border-borda p-3 text-sm">
      <div className="mb-1 flex items-center gap-2">
        <span className="font-medium">{p.rotulo}</span><SeloNatureza natureza="CALCULO" />
      </div>
      {p.percentil === null ? (
        <p className="ausente">{p.mensagem ?? NAO_DISPONIVEL}</p>
      ) : (
        <>
          <p>{p.descricao}</p>
          <p className="mt-1 text-xs text-texto-3">{p.definicao_percentil} {p.exclusao}</p>
        </>
      )}
      {p.universo.alertas.length > 0 && <div className="mt-2"><Alertas itens={p.universo.alertas} /></div>}
    </div>
  );
}

export default function PaginaCandidato() {
  const { sq: sqTexto } = useParams<{ sq: string }>();
  const sq = Number(sqTexto);
  const [d, setD] = useState<Detalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [posicoes, setPosicoes] = useState<(Posicao | null)[]>([null, null]);
  const comp = useComparacao();

  useEffect(() => {
    setD(null);
    api<Detalhe>(`/candidatos/${sq}`).then(setD).catch((e: Error) => setErro(e.message));
    Promise.all(["total_bens", "idade_na_posse"].map((m) =>
      api<Posicao>(`/candidatos/${sq}/posicao`, { metrica: m }).catch(() => null),
    )).then(setPosicoes);
  }, [sq]);

  if (erro) return <Erro mensagem={erro} />;
  if (!d) return <Carregando />;

  const id = d.identificacao;
  const nome = String(id.nm_urna.valor ?? id.nm_candidato.valor);
  const pat = d.patrimonio;
  const hist = d.historico;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm"><Link href="/candidatos" className="text-destaque hover:underline">← Candidatos</Link></p>
          <h1 className="mt-1 text-2xl font-semibold">{nome}</h1>
          <p className="text-sm text-texto-2">
            {titulo(String(id.ds_cargo.valor))} · {String(id.sg_uf.valor)} · {String(id.sg_partido.valor)} · nº {String(id.nr_candidato.valor)}
            {" · "}situação: {formatarCampo("situacao_candidatura", d.situacao.situacao_candidatura.valor)}
          </p>
        </div>
        {comp.contem(sq) ? (
          <Link href="/comparar" className="rounded border border-borda px-3 py-1.5 text-sm hover:bg-superficie-2">Na comparação — abrir</Link>
        ) : (
          <button type="button" disabled={comp.cheio}
            onClick={() => comp.adicionar({ sq, nome, cargo: titulo(String(id.ds_cargo.valor)), uf: String(id.sg_uf.valor) })}
            className="rounded bg-serie px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
            {comp.cheio ? "Comparação cheia (5)" : "Adicionar à comparação"}
          </button>
        )}
      </header>

      {d.outros_registros_2026.itens.length > 0 && (
        <div className="rounded border border-borda bg-superficie p-3 text-sm">
          <p className="mb-1 flex items-center gap-2 font-medium">Outros registros de candidatura desta pessoa em 2026 <SeloNatureza natureza="CALCULO" /></p>
          <ul className="list-inside list-disc">
            {d.outros_registros_2026.itens.map((o) => (
              <li key={o.sq_candidato}>
                <Link href={`/candidatos/${o.sq_candidato}`} className="text-destaque hover:underline">{o.nm_urna}</Link>
                {" — "}{titulo(o.ds_cargo)} · {o.sg_uf} · {o.situacao_candidatura ?? NAO_DISPONIVEL}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-texto-3">{d.outros_registros_2026.observacao}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Secao titulo="Identificação" secao={id} sq={sq} />
        <div className="space-y-4">
          <Secao titulo="Situação" secao={d.situacao} sq={sq} />
          <Secao titulo="Perfil" secao={d.perfil} sq={sq} />
        </div>
      </div>

      <Cartao titulo="Patrimônio declarado">
        <dl>
          <ValorCampo nome="declarou_bens" rotulo={ROTULOS.declarou_bens} campo={pat.declarou_bens} sq={sq} />
          <ValorCampo nome="qt_bens" rotulo={ROTULOS.qt_bens} campo={pat.qt_bens} sq={sq} />
          <ValorCampo nome="total_bens" rotulo={ROTULOS.total_bens} campo={pat.total_bens} sq={sq} />
        </dl>
        {pat.mensagem && <p className="mt-2 text-sm ausente">{pat.mensagem}</p>}
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <PosicaoNoGrupo p={posicoes[0]} />
          <PosicaoNoGrupo p={posicoes[1]} />
        </div>
        {pat.por_categoria.itens.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-1 flex flex-wrap items-center gap-2 text-sm font-medium">Por categoria <SeloNatureza natureza="CALCULO" /> <MapaCategorias /></h3>
            <table className="w-full max-w-xl text-sm">
              <tbody>
                {pat.por_categoria.itens.map((c) => (
                  <tr key={c.categoria ?? "—"} className="border-t border-borda">
                    <td className="py-1">{c.categoria ?? <span className="ausente">sem categoria no mapa</span>}</td>
                    <td className="py-1 text-right tabular-nums">{numero(c.qt)} {c.qt === 1 ? "bem" : "bens"}</td>
                    <td className="py-1 text-right tabular-nums">{moeda(c.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {pat.bens.itens.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <h3 className="mb-1 text-sm font-medium">Bens declarados ({numero(pat.bens.itens.length)})</h3>
            <table className="w-full text-sm">
              <thead className="bg-superficie-2 text-left text-xs text-texto-2">
                <tr>
                  <th className="px-2 py-1">Nº</th><th className="px-2 py-1">Tipo <SeloNatureza natureza="DADO" /></th>
                  <th className="px-2 py-1">Categoria <SeloNatureza natureza="CALCULO" /></th>
                  <th className="px-2 py-1">Descrição <SeloNatureza natureza="DECLARACAO_CANDIDATO" /></th>
                  <th className="px-2 py-1 text-right">Valor <SeloNatureza natureza="DADO" /></th><th className="px-2 py-1" />
                </tr>
              </thead>
              <tbody>
                {pat.bens.itens.map((b) => (
                  <tr key={b.nr_ordem} className="border-t border-borda align-top">
                    <td className="px-2 py-1 tabular-nums">{b.nr_ordem}</td>
                    <td className="px-2 py-1">{b.tipo}</td>
                    <td className="px-2 py-1">{b.categoria ?? <span className="ausente">sem categoria no mapa</span>}</td>
                    <td className="px-2 py-1 text-texto-2">{b.descricao ?? <span className="ausente">{NAO_DISPONIVEL}</span>}</td>
                    <td className="px-2 py-1 text-right tabular-nums" title={`Valor original no arquivo: ${b.valor_original}`}>{moeda(b.valor)}</td>
                    <td className="px-2 py-1"><VerFonte consulta={{ tabela: "bem", sq, campo: "valor", nr_ordem: b.nr_ordem }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Cartao>

      <Cartao titulo="Histórico de candidaturas (desde 2004)">
        <dl>
          <ValorCampo nome="historico_disponivel" rotulo={ROTULOS.historico_disponivel} campo={hist.disponivel} sq={sq} />
          <ValorCampo nome="qt_candidaturas_anteriores" rotulo={ROTULOS.qt_candidaturas_anteriores} campo={hist.qt_candidaturas_anteriores} sq={sq} />
          <ValorCampo nome="qt_vezes_eleito" rotulo={ROTULOS.qt_vezes_eleito} campo={hist.qt_vezes_eleito} sq={sq} />
          <ValorCampo nome="ultimo_cargo_eleito" rotulo={ROTULOS.ultimo_cargo_eleito} campo={hist.ultimo_cargo_eleito} sq={sq} />
        </dl>
        {hist.mensagem ? <p className="mt-2 text-sm ausente">{hist.mensagem}</p> : (
          <div className="mt-3 overflow-x-auto">
            <p className="mb-1 text-xs text-texto-3">{hist.observacao}</p>
            <table className="w-full text-sm">
              <thead className="bg-superficie-2 text-left text-xs text-texto-2">
                <tr><th className="px-2 py-1">Ano</th><th className="px-2 py-1">Turno</th><th className="px-2 py-1">Cargo</th><th className="px-2 py-1">Local</th>
                  <th className="px-2 py-1">Partido</th><th className="px-2 py-1">Julgamento</th><th className="px-2 py-1">Resultado</th><th className="px-2 py-1" /></tr>
              </thead>
              <tbody>
                {hist.linha_do_tempo.itens.map((h) => (
                  <tr key={`${h.fonte.linha}`} className={`border-t border-borda ${h.eleicao_atual ? "bg-superficie-2/60" : ""}`}>
                    <td className="px-2 py-1 tabular-nums">{h.ano_eleicao}{h.eleicao_atual && <span className="ml-1 text-[10px] text-texto-3">(atual)</span>}</td>
                    <td className="px-2 py-1">{h.turno}º</td>
                    <td className="px-2 py-1">{titulo(h.ds_cargo)}</td>
                    <td className="px-2 py-1">{h.nm_ue} ({h.sg_uf})</td>
                    <td className="px-2 py-1">{h.sg_partido}</td>
                    <td className="px-2 py-1">{h.situacao_julgamento ?? <span className="ausente">{NAO_DISPONIVEL}</span>}</td>
                    <td className="px-2 py-1">{h.resultado ?? <span className="ausente">{h.eleicao_atual ? "sem resultado (eleição em andamento)" : NAO_DISPONIVEL}</span>}</td>
                    <td className="px-2 py-1"><VerFonte consulta={{ tabela: "historico", sq, campo: "resultado", linha: h.fonte.linha }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Cartao>

      <Cartao titulo="Fundamentos de indeferimento registrados pelo TSE">
        <p className="text-xs text-texto-3">{d.fundamentos_indeferimento.descricao}</p>
        {d.fundamentos_indeferimento.itens.length === 0 ? (
          <p className="mt-2 text-sm text-texto-2">{d.fundamentos_indeferimento.mensagem}</p>
        ) : (
          <ul className="mt-2 space-y-2 text-sm">
            {d.fundamentos_indeferimento.itens.map((f) => (
              <li key={f.fonte.linha} className="rounded border border-borda p-2">
                <span className="text-texto-2">{f.tipo}:</span> {f.motivo} <SeloNatureza natureza="DADO" />{" "}
                <VerFonte consulta={{ tabela: "fundamento_indeferimento", sq, campo: "motivo", linha: f.fonte.linha }} />
              </li>
            ))}
          </ul>
        )}
      </Cartao>

      <Cartao titulo="Redes sociais e sites informados ao TSE">
        {d.redes.itens.length === 0 ? <p className="text-sm ausente">Nenhum endereço no arquivo de redes sociais do TSE.</p> : (
          <ul className="space-y-1 text-sm">
            {d.redes.itens.map((r) => (
              <li key={r.nr_ordem} className="flex flex-wrap items-center gap-2">
                <span className="w-24 text-texto-2">{r.plataforma}</span>
                <a href={r.url.startsWith("http") ? r.url : `https://${r.url}`} target="_blank" rel="noopener noreferrer nofollow" className="break-all text-destaque hover:underline">{r.url}</a>
                <VerFonte consulta={{ tabela: "rede_social", sq, campo: "url", nr_ordem: r.nr_ordem }} />
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-texto-3">Plataforma identificada pelo domínio do endereço (CÁLCULO). Links externos não são verificados.</p>
      </Cartao>
    </div>
  );
}
