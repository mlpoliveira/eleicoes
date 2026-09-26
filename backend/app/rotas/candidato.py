"""
Página do candidato (GET /api/candidatos/{sq}) e "Ver fonte" (GET /api/fonte).

Regras aplicadas aqui (ver CLAUDE.md):
  - cada campo sai com natureza e fonte (arquivo, linha, campo do TSE, geração);
  - campo ausente sai como valor nulo + "Não disponível no dataset utilizado." — nunca 0 ou texto
    inventado; histórico indisponível é dito explicitamente;
  - fundamentos de indeferimento são mostrados como o TSE os registra, sem linguagem acusatória;
  - outros registros da mesma pessoa aparecem pelo sq_candidato; pessoa_id nunca sai da API.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import carga_atual, consultar
from ..dependencias import cursor
from ..metadados import (BEM, CAMPOS, DATASET, HIST, NAO_DISPONIVEL, RAW, TABELAS_MULTIPLAS,
                         bloco_campos, campo_com_fonte, linha_de)

router = APIRouter(prefix="/api", tags=["candidato"])

ANO_ATUAL = 2026

SECOES = {
    "identificacao": ["sq_candidato", "nr_candidato", "nm_candidato", "nm_urna", "nm_social",
                      "ds_eleicao", "dt_eleicao", "sg_uf", "nm_ue", "cd_cargo", "ds_cargo",
                      "nr_partido", "sg_partido", "nm_partido", "tp_agremiacao", "nm_federacao",
                      "composicao_federacao", "sq_coligacao", "nm_coligacao",
                      "composicao_coligacao"],
    "perfil": ["dt_nascimento", "idade_na_posse", "uf_nascimento", "municipio_nascimento",
               "nacionalidade", "genero", "cor_raca", "grau_instrucao", "estado_civil",
               "ocupacao", "quilombola", "etnia_indigena"],
    "situacao": ["situacao_candidatura", "situacao_campo_origem", "situacao_julgamento",
                 "na_urna", "destinacao_votos", "substituido", "sq_substituido", "nr_processo",
                 "limite_gastos", "resultado"],
}

TEXTO_HISTORICO_INDISPONIVEL = (
    "Histórico não disponível no dataset utilizado: este registro não aparece no arquivo "
    "historico_candidatura do TSE. Isso não significa que a pessoa nunca tenha concorrido.")
TEXTO_TURNOS = (
    "O arquivo de histórico do TSE tem uma linha por turno: candidaturas com 2º turno aparecem "
    "duas vezes na linha do tempo. As contagens consideram uma candidatura por ano, cargo e local.")
TEXTO_FUNDAMENTOS = (
    "Fundamentos legais registrados pelo TSE no julgamento do pedido de registro de candidatura "
    "(arquivo motivo_cassacao — apesar do nome, o conteúdo são fundamentos de indeferimento, não "
    "cassações). A situação atual da candidatura está na seção 'situacao'.")


def _itens(cur, tabela: str, where: str, params: list, ordem: str) -> list[dict]:
    """Registros de uma tabela com vários itens por candidato, cada um com arquivo e linha."""
    _, campos = TABELAS_MULTIPLAS[tabela]
    linhas = consultar(cur, f"""
        SELECT {', '.join(campos)}, fonte_arquivo, fonte_linha FROM {tabela}
        WHERE {where} ORDER BY {ordem}""", params)
    for l in linhas:
        l["fonte"] = {"arquivo": l.pop("fonte_arquivo"), "linha": l.pop("fonte_linha")}
    return linhas


def _campos_de(tabela: str, geracao) -> dict:
    arquivo, campos = TABELAS_MULTIPLAS[tabela]
    return bloco_campos(list(campos), geracao, campos=campos, arquivo=arquivo)


@router.get("/candidatos/{sq}")
def detalhe_candidato(sq: int, cur=Depends(cursor)):
    regs = consultar(cur, "SELECT * EXCLUDE (pessoa_id) FROM v_candidato WHERE sq_candidato = ?",
                     [sq])
    if not regs:
        raise HTTPException(404, f"Candidato {sq} não encontrado na carga atual.")
    c = regs[0]
    carga = carga_atual(cur)
    g = carga["geracao_tse"]

    resposta = {"sq_candidato": sq, "geracao_tse": g, "carga_id": carga["carga_id"],
                "dataset": DATASET}
    for secao, nomes in SECOES.items():
        resposta[secao] = {n: campo_com_fonte(n, c, g) for n in nomes}

    # ---- patrimônio
    bens = _itens(cur, "bem", "sq_candidato = ?", [sq], "nr_ordem")
    por_categoria = consultar(cur, """
        SELECT categoria, count(*) AS qt, sum(valor) AS total FROM bem WHERE sq_candidato = ?
        GROUP BY categoria ORDER BY categoria NULLS LAST""", [sq])
    por_tipo = consultar(cur, """
        SELECT tipo, count(*) AS qt, sum(valor) AS total FROM bem WHERE sq_candidato = ?
        GROUP BY tipo ORDER BY tipo""", [sq])
    maiores = sorted((b for b in bens if b["valor"] is not None),
                     key=lambda b: b["valor"], reverse=True)[:5]
    resposta["patrimonio"] = {
        "declarou_bens": campo_com_fonte("declarou_bens", c, g),
        "qt_bens": campo_com_fonte("qt_bens", c, g),
        "total_bens": campo_com_fonte("total_bens", c, g),
        "mensagem": None if bens else
            "Nenhum bem deste candidato no arquivo bem_candidato do TSE (total não disponível, "
            "não é zero).",
        "por_categoria": {"natureza": "CALCULO",
                          "descricao": "Quantidade e soma dos valores declarados por categoria. "
                                       "Categorias vêm do mapa tipo de bem -> categoria "
                                       "(ingestao/categorias_bens.csv); categoria nula = tipo "
                                       "fora do mapa.",
                          "mapa": "/api/categorias-bens",
                          "itens": por_categoria},
        "por_tipo": {"natureza": "CALCULO",
                     "descricao": "Quantidade e soma dos valores declarados por tipo de bem, "
                                  "em ordem alfabética de tipo.",
                     "fonte": {"dataset": DATASET, "arquivo": BEM,
                               "campo": "DS_TIPO_BEM_CANDIDATO | VR_BEM_CANDIDATO"},
                     "itens": por_tipo},
        "maiores_bens": {"natureza": "CALCULO",
                         "descricao": "Até 5 bens, ordenados pelo valor declarado (maior "
                                      "primeiro). Bens com valor ilegível ficam de fora.",
                         "itens": maiores},
        "bens": {"campos": _campos_de("bem", g), "itens": bens},
    }

    # ---- redes sociais
    resposta["redes"] = {"campos": _campos_de("rede_social", g),
                         "itens": _itens(cur, "rede_social", "sq_candidato = ?", [sq], "nr_ordem")}

    # ---- histórico
    disponivel = bool(c["historico_disponivel"])
    linha_tempo = _itens(cur, "historico", "sq_candidato_atual = ?", [sq],
                         "ano_eleicao DESC, turno, cd_cargo") if disponivel else []
    for h in linha_tempo:
        h["eleicao_atual"] = h["ano_eleicao"] == ANO_ATUAL
    resposta["historico"] = {
        "disponivel": campo_com_fonte("historico_disponivel", c, g),
        "mensagem": None if disponivel else TEXTO_HISTORICO_INDISPONIVEL,
        "observacao": TEXTO_TURNOS,
        "qt_candidaturas_anteriores": campo_com_fonte("qt_candidaturas_anteriores", c, g),
        "qt_vezes_eleito": campo_com_fonte("qt_vezes_eleito", c, g),
        "ultimo_cargo_eleito": campo_com_fonte("ultimo_cargo_eleito", c, g),
        "linha_do_tempo": {"campos": _campos_de("historico", g), "itens": linha_tempo},
    }

    # ---- fundamentos de indeferimento
    fundamentos = _itens(cur, "fundamento_indeferimento", "sq_candidato = ?", [sq], "fonte_linha")
    resposta["fundamentos_indeferimento"] = {
        "descricao": TEXTO_FUNDAMENTOS,
        "mensagem": None if fundamentos else
            "Nenhum fundamento de indeferimento registrado para este candidato no arquivo do TSE.",
        "campos": _campos_de("fundamento_indeferimento", g),
        "itens": fundamentos,
    }

    # ---- outros registros da mesma pessoa em 2026 (só sq e dados do registro)
    outros = consultar(cur, """
        SELECT o.sq_candidato, o.nm_urna, o.cd_cargo, o.ds_cargo, o.sg_uf,
               o.situacao_candidatura
        FROM candidato c JOIN candidato o
          ON o.pessoa_id = c.pessoa_id AND o.sq_candidato <> c.sq_candidato
        WHERE c.sq_candidato = ? ORDER BY o.sq_candidato""", [sq])
    resposta["outros_registros_2026"] = {
        "natureza": "CALCULO",
        "observacao": CAMPOS["outros_registros_2026"][3] + " "
                      + CAMPOS["qt_outros_registros_2026"][3],
        "itens": outros,
    }
    return resposta


# ---------------------------------------------------------------- Ver fonte
TABELAS_FONTE = ("candidato", "bem", "rede_social", "historico", "fundamento_indeferimento")
COLUNA_SQ = {"historico": "sq_candidato_atual"}


def _valores_originais(cur, arquivo: str, campo_tse: str | None, linhas: list[int],
                       carga_id: int) -> dict:
    """Texto exatamente como veio no CSV do TSE (tabela raw_*), por linha."""
    if not campo_tse or not linhas:
        return {}
    cols = [c.strip() for c in campo_tse.split("|")]
    existentes = {r["column_name"] for r in consultar(
        cur, "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
        [RAW[arquivo]])}
    cols = [c for c in cols if c in existentes]
    if not cols:
        return {}
    sel = ", ".join(f'"{c}"' for c in cols)
    regs = consultar(cur, f"""
        SELECT _linha, {sel} FROM {RAW[arquivo]}
        WHERE _carga_id = ? AND _linha IN ({', '.join('?' * len(linhas))})""",
                     [carga_id, *linhas])
    return {r.pop("_linha"): r for r in regs}


@router.get("/fonte")
def ver_fonte(
    tabela: Literal[TABELAS_FONTE],
    sq: int,
    campo: str = Query(..., max_length=64),
    nr_ordem: int | None = Query(None, description="bem ou rede_social: número de ordem"),
    linha: int | None = Query(None, description="historico ou fundamento: linha no arquivo"),
    cur=Depends(cursor),
):
    """Origem de um campo: dataset, arquivo, linha, campo do TSE, geração e o valor original."""
    carga = carga_atual(cur)
    cand = consultar(cur, "SELECT * EXCLUDE (pessoa_id) FROM v_candidato WHERE sq_candidato = ?",
                     [sq])
    if not cand:
        raise HTTPException(404, f"Candidato {sq} não encontrado na carga atual.")

    if tabela == "candidato":
        if campo not in CAMPOS:
            raise HTTPException(422, f"Campo desconhecido para candidato: {campo}")
        natureza, arquivo, campo_tse, obs = CAMPOS[campo]
        if arquivo in (BEM, HIST):   # cálculo a partir de outra tabela: lista as linhas usadas
            origem = "bem" if arquivo == BEM else "historico"
            col_sq = COLUNA_SQ.get(origem, "sq_candidato")
            linhas = [r["fonte_linha"] for r in consultar(
                cur, f"SELECT fonte_linha FROM {origem} WHERE {col_sq} = ? ORDER BY fonte_linha",
                [sq])]
        else:
            ln = linha_de(arquivo, cand[0])
            linhas = [ln] if ln is not None else []
    else:
        arquivo, campos = TABELAS_MULTIPLAS[tabela]
        if campo not in campos:
            raise HTTPException(422, f"Campo desconhecido para {tabela}: {campo}")
        natureza, campo_tse, obs = campos[campo]
        where, params = [f"{COLUNA_SQ.get(tabela, 'sq_candidato')} = ?"], [sq]
        if nr_ordem is not None and tabela in ("bem", "rede_social"):
            where.append("nr_ordem = ?"); params.append(nr_ordem)
        if linha is not None:
            where.append("fonte_linha = ?"); params.append(linha)
        linhas = [r["fonte_linha"] for r in consultar(
            cur, f"SELECT fonte_linha FROM {tabela} WHERE {' AND '.join(where)} "
                 "ORDER BY fonte_linha", params)]

    originais = _valores_originais(cur, arquivo, campo_tse, linhas, carga["carga_id"])
    return {
        "tabela": tabela, "sq_candidato": sq, "campo": campo,
        "natureza": natureza, "observacao": obs,
        "dataset": DATASET, "arquivo": arquivo, "campo_tse": campo_tse,
        "geracao_tse": carga["geracao_tse"], "carga_id": carga["carga_id"],
        "registros": [{"arquivo": arquivo, "linha": ln, "valores_originais": originais.get(ln, {})}
                      for ln in linhas],
        "mensagem": None if linhas else NAO_DISPONIVEL,
    }
