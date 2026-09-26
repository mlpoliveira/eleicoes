"""
Exportação CSV/Excel (T8): busca, comparação e estatísticas.

Cada rota chama a MESMA função da rota de consulta correspondente (mesmos filtros, mesmos cálculos)
e só converte o resultado em tabelas + metadados. Assim a exportação nunca diverge da tela.
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..db import carga_atual
from ..dependencias import cursor
from ..exportar import (NAO_DISPONIVEL, Exportacao, Tabela, metadados_base, montar_tabela,
                        para_csv, para_xlsx)
from ..metadados import DATASET
from ..universo import Universo, universo_dos_parametros
from .candidatos import ORDENAVEIS, buscar_candidatos
from .comparar import comparar
from .estatisticas import CATEGORICAS, METRICAS, estatisticas

router = APIRouter(prefix="/api/exportar", tags=["exportar"])

Formato = Literal["csv", "xlsx"]
TIPOS = {"csv": "text/csv; charset=utf-8",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

COLUNAS_BUSCA = [
    "sq_candidato", "nr_candidato", "nm_candidato", "nm_urna", "nm_social", "sg_uf", "cd_cargo",
    "ds_cargo", "sg_partido", "nm_partido", "nm_federacao", "situacao_candidatura",
    "situacao_campo_origem", "na_urna", "genero", "cor_raca", "grau_instrucao", "idade_na_posse",
    "qt_bens", "total_bens", "historico_disponivel", "qt_outros_registros_2026",
    "outros_registros_2026", "correspondencia", "fonte_arquivo", "fonte_linha",
    "fonte_arquivo_compl", "fonte_linha_compl",
]


def _resposta(exp: Exportacao, formato: str, nome: str, campos=None) -> Response:
    corpo = para_csv(exp) if formato == "csv" else para_xlsx(exp, campos)
    arquivo = f"eleicoes2026_{nome}_{datetime.now():%Y%m%d-%H%M}.{formato}"
    return Response(corpo, media_type=TIPOS[formato],
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


def _campos_da_busca(campos: dict) -> list[dict]:
    return [{"coluna": k, "natureza": v["natureza"], "arquivo": v["fonte"].get("arquivo"),
             "campo_tse": v["fonte"].get("campo"), "observacao": v.get("observacao")}
            for k, v in campos.items()]


@router.get("/candidatos")
def exportar_candidatos(
    formato: Formato = "xlsx",
    q: str | None = Query(None, max_length=120),
    universo: Universo = Depends(universo_dos_parametros),
    ordenar_por: Literal[tuple(ORDENAVEIS)] = "nm_urna",
    ordem: Literal["asc", "desc"] = "asc",
    cur=Depends(cursor),
):
    """Todos os resultados da busca (sem paginação), com as mesmas colunas e critério da tela."""
    r = buscar_candidatos(q=q, universo=universo, pagina=1, por_pagina=1_000_000,
                          ordenar_por=ordenar_por, ordem=ordem, cur=cur)
    filtros = {**universo.filtros(), **({"q": q} if q else {}),
               "ordenacao": f"{ordenar_por} {ordem}"}
    exp = Exportacao(
        titulo="Busca de candidaturas",
        metadados=metadados_base(
            "Busca de candidaturas — Eleições 2026", r["geracao_tse"],
            f"{DATASET}; arquivo e linha de cada registro nas colunas fonte_*", universo.descricao(cur),
            filtros, "DADO (colunas qt_bens, total_bens, historico_disponivel e "
                     "qt_outros_registros_2026: CALCULO — ver aba/seção 'campos')",
            [("total_de_registros", str(r["total"])),
             ("criterio_busca", r["consulta"]["criterio_busca"] or "—")]),
        tabelas=[montar_tabela("candidatos", r["itens"], COLUNAS_BUSCA, moeda={"total_bens"})],
    )
    campos = _campos_da_busca(r["campos"])
    if formato == "csv":
        exp.tabelas.append(Tabela("campos", ["coluna", "natureza", "arquivo", "campo_tse", "observacao"],
                                  [[c["coluna"], c["natureza"], c["arquivo"], c["campo_tse"],
                                    c["observacao"] or ""] for c in campos]))
    return _resposta(exp, formato, "candidatos", campos)


def _texto_valor(campo: str, v):
    """Valor de célula da comparação (listas viram texto; ausência por extenso)."""
    if v is None:
        return None
    if campo == "por_categoria":
        return "; ".join(f"{c['categoria'] or 'sem categoria'}: {c['total']} ({c['qt']})" for c in v) \
            or NAO_DISPONIVEL
    if campo == "redes":
        return "; ".join(f"{r['plataforma']}: {r['url']}" for r in v) or NAO_DISPONIVEL
    return v


@router.get("/comparar")
def exportar_comparacao(
    formato: Formato = "xlsx",
    sq: list[str] = Query(..., description="2 a 5 sq_candidato"),
    cur=Depends(cursor),
):
    r = comparar(sq=sq, cur=cur)
    nomes = [f"{c['nm_urna']} ({c['sq_candidato']})" for c in r["candidatos"]]
    linhas = [[l["secao"], l["campo"], l["natureza"],
               *[_texto_valor(l["campo"], v["valor"]) for v in l["valores"]]] for l in r["tabela"]]
    exp = Exportacao(
        titulo="Comparação de candidaturas",
        metadados=metadados_base(
            "Comparação de candidaturas — Eleições 2026", r["geracao_tse"], DATASET,
            "Candidaturas selecionadas: " + "; ".join(nomes), {"sq": [c["sq_candidato"] for c in r["candidatos"]]},
            "DADO e CALCULO (natureza por linha na coluna 'natureza')",
            [("alertas", " | ".join(r["alertas"]) or "nenhum")]),
        tabelas=[
            Tabela("comparacao", ["secao", "campo", "natureza", *nomes], linhas,
                   nota="Valores em R$ (sem formatação) nas linhas total_bens, limite_gastos e "
                        "por_categoria."),
            Tabela("diferencas", ["campo", "rotulo", "natureza", "texto"],
                   [[d["campo"], d["rotulo"], d["natureza"], d["texto"]] for d in r["diferencas"]["itens"]],
                   nota=r["diferencas"]["descricao"]),
            Tabela("verificacoes", ["verificacao", "resultado"],
                   [[k, v] for k, v in r["verificacoes"].items()]),
        ],
    )
    return _resposta(exp, formato, "comparacao")


@router.get("/estatisticas")
def exportar_estatisticas(
    formato: Formato = "xlsx",
    universo: Universo = Depends(universo_dos_parametros),
    metrica: str | None = Query(None),
    categoricas: list[str] = Query(["genero", "cor_raca", "grau_instrucao"]),
    cruzamentos: list[str] = Query([]),
    bins: int = Query(20, ge=1, le=100),
    escala: str | None = Query(None, pattern="^(linear|log10)$"),
    cur=Depends(cursor),
):
    r = estatisticas(universo=universo, metrica=metrica, categoricas=categoricas,
                     cruzamentos=cruzamentos, bins=bins, escala=escala, cur=cur)
    u = r["universo"]
    tabelas = []
    num = r["numerica"]
    if num:
        moeda = num["unidade"] == "BRL"
        resumo = [["n_universo", u["n"], "candidaturas"],
                  ["n_com_dado", num["n_com_dado"], "candidaturas (entram no cálculo)"],
                  ["n_sem_dado", num["n_sem_dado"], "candidaturas (fora do cálculo)"]]
        resumo += [[f"sem_dado: {k}", v, "candidaturas"] for k, v in num["sem_dado_por_motivo"].items()]
        for k in ("media", "mediana", "min", "max", "desvio_padrao"):
            resumo.append([k, num.get(k), num["unidade"]])
        resumo += [[k, v, num["unidade"]] for k, v in (num.get("percentis") or {}).items()]
        tabelas.append(Tabela(f"resumo {num['metrica']}", ["medida", "valor", "unidade"], resumo,
                              nota=f"{num['rotulo']}. {num['exclusao']}"))
        if num.get("histograma"):
            h = num["histograma"]
            tabelas.append(Tabela("histograma", ["inicio", "fim", "candidaturas"],
                                  [[f["inicio"], f["fim"], f["n"]] for f in h["faixas"]],
                                  moeda={"inicio", "fim"} if moeda else set(),
                                  nota=f"Escala {h['escala']}. {h['observacao']}"
                                       + (f" Fora da escala: {h['n_fora_da_escala']}."
                                          if h.get("n_fora_da_escala") else "")))
    for c in r["categoricas"]:
        tabelas.append(Tabela(c["dimensao"], ["valor", "candidaturas", "pct_do_universo"],
                              [[i["valor"], i["n"], i["pct"]] for i in c["itens"]],
                              nota=f"Natureza: {c['natureza']}. Ordem alfabética do valor."))
    for x in r["cruzamentos"]:
        a, b = x["linhas"], x["colunas"]
        tabelas.append(Tabela(f"{a} x {b}", [a, b, "candidaturas", "pct_universo", "pct_linha"],
                              [[c[a], c[b], c["n"], c["pct_universo"], c["pct_linha"]] for c in x["celulas"]],
                              nota=x["descricao"]))
    exp = Exportacao(
        titulo="Estatísticas de grupo",
        metadados=metadados_base(
            "Estatísticas de grupo — Eleições 2026", r["geracao_tse"],
            f"{DATASET}; {r['fonte']['arquivo']}", f"{u['descricao']} (n = {u['n']})",
            {**u["filtros"], **({"metrica": metrica} if metrica else {})}, "CALCULO",
            [("alertas", " | ".join(u["alertas"]) or "nenhum")]),
        tabelas=tabelas,
    )
    return _resposta(exp, formato, "estatisticas")
