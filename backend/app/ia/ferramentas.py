"""
Ferramentas da IA (T10) = funções do backend. Sem acesso direto ao banco (regra 8).

Cada ferramenta chama a MESMA função da rota correspondente e devolve ao modelo uma versão
enxuta (sem metadados repetidos), mantendo o que a resposta precisa citar: valores, natureza,
universo, geração TSE e arquivo/linha de origem.
"""
import json
from decimal import Decimal
from datetime import date, datetime

from fastapi import HTTPException

from ..rotas.candidato import detalhe_candidato, ver_fonte
from ..rotas.candidatos import ORDENAVEIS, buscar_candidatos
from ..rotas.comparar import comparar
from ..rotas.estatisticas import CATEGORICAS, METRICAS, estatisticas, posicao
from ..universo import Universo

MAX_ITENS = 20

_FILTROS = {
    "uf": {"type": "string", "description": "Sigla da UF (ex.: RJ) ou BR para presidente"},
    "cd_cargo": {"type": "integer", "description": "Código do cargo no TSE: 1 Presidente, 3 Governador, "
                 "5 Senador, 6 Deputado Federal, 7 Deputado Estadual, 8 Deputado Distrital"},
    "sg_partido": {"type": "string", "description": "Sigla do partido (ex.: PT, PL, PSD)"},
    "situacao": {"type": "string", "description": "Situação da candidatura (ex.: DEFERIDO, INDEFERIDO)"},
    "genero": {"type": "string", "description": "FEMININO ou MASCULINO"},
}
_METRICA = {"type": "string", "enum": list(METRICAS), "description": "Métrica numérica"}


def _f(nome, descricao, props, obrig=()):
    return {"type": "function", "function": {
        "name": nome, "description": descricao,
        "parameters": {"type": "object", "properties": props, "required": list(obrig)}}}


DEFINICOES = [
    _f("search_candidates", "Busca candidaturas 2026 por nome/número e filtros. Devolve até "
       f"{MAX_ITENS} itens e o total. Use para achar o sq_candidato de alguém.",
       {"q": {"type": "string", "description": "Nome ou número"}, **_FILTROS,
        "ordenar_por": {"type": "string", "enum": ORDENAVEIS},
        "ordem": {"type": "string", "enum": ["asc", "desc"]},
        "limite": {"type": "integer", "description": f"Máximo {MAX_ITENS}"}}),
    _f("get_candidate", "Dados de uma candidatura: identificação, perfil, situação, resumo de "
       "patrimônio e de histórico, fundamentos de indeferimento, outros registros 2026.",
       {"sq": {"type": "integer"}}, ["sq"]),
    _f("get_candidate_assets", "Bens declarados de uma candidatura (lista, por categoria, total).",
       {"sq": {"type": "integer"}}, ["sq"]),
    _f("get_candidate_history", "Histórico de candidaturas desde 2004 (uma linha por turno).",
       {"sq": {"type": "integer"}}, ["sq"]),
    _f("compare_candidates", "Compara 2 a 5 candidaturas: verificações, alertas, diferenças factuais.",
       {"sqs": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 5}}, ["sqs"]),
    _f("get_candidate_position", "Percentil de uma candidatura em uma métrica, no universo "
       "mesmo cargo + UF.", {"sq": {"type": "integer"}, "metrica": _METRICA}, ["sq", "metrica"]),
    _f("get_party_statistics", "Estatísticas das candidaturas de um partido (opcionalmente por UF/cargo).",
       {"sg_partido": _FILTROS["sg_partido"], "uf": _FILTROS["uf"], "cd_cargo": _FILTROS["cd_cargo"],
        "metrica": _METRICA}, ["sg_partido"]),
    _f("get_state_statistics", "Estatísticas das candidaturas de uma UF (opcionalmente por cargo).",
       {"uf": _FILTROS["uf"], "cd_cargo": _FILTROS["cd_cargo"], "metrica": _METRICA}, ["uf"]),
    _f("calculate_statistics", "Estatísticas de um universo qualquer: n, média, mediana, percentis "
       "de uma métrica; distribuições e cruzamentos categóricos.",
       {**_FILTROS, "metrica": _METRICA,
        "categoricas": {"type": "array", "items": {"type": "string", "enum": list(CATEGORICAS)}},
        "cruzamento": {"type": "array", "items": {"type": "string", "enum": list(CATEGORICAS)},
                       "minItems": 2, "maxItems": 2}}),
    _f("get_source", "Origem de um campo: arquivo, linha, campo do TSE e texto original do CSV.",
       {"tabela": {"type": "string", "enum": ["candidato", "bem", "rede_social", "historico",
                                               "fundamento_indeferimento"]},
        "sq": {"type": "integer"}, "campo": {"type": "string"},
        "nr_ordem": {"type": "integer"}, "linha": {"type": "integer"}}, ["tabela", "sq", "campo"]),
]
NOMES = {d["function"]["name"] for d in DEFINICOES}


# ---------------------------------------------------------------- execução
def _universo(a: dict) -> Universo:
    lista = lambda k: [a[k]] if a.get(k) not in (None, "") else []  # noqa: E731
    return Universo(uf=lista("uf"), cd_cargo=lista("cd_cargo"), sg_partido=lista("sg_partido"),
                    situacao=lista("situacao"), genero=lista("genero"))


def _valores(secao: dict) -> dict:
    return {k: v["valor"] for k, v in secao.items()}


def _estat(cur, a: dict) -> dict:
    cruz = a.get("cruzamento") or []
    r = estatisticas(universo=_universo(a), metrica=a.get("metrica"),
                     categoricas=a.get("categoricas") or ["genero", "grau_instrucao", "faixa_etaria"],
                     cruzamentos=[",".join(cruz)] if len(cruz) == 2 else [], bins=10, escala=None,
                     cur=cur)
    num = r["numerica"]
    if num:
        num = {k: v for k, v in num.items() if k not in ("histograma", "fonte", "observacao_calculo")}
    return {"natureza": "CALCULO", "geracao_tse": r["geracao_tse"], "universo": r["universo"],
            "numerica": num,
            "categoricas": [{"dimensao": c["dimensao"], "itens": c["itens"][:30]} for c in r["categoricas"]],
            "cruzamentos": [{"linhas": x["linhas"], "colunas": x["colunas"], "celulas": x["celulas"][:60]}
                            for x in r["cruzamentos"]]}


def _executar(nome: str, a: dict, cur) -> dict:
    if nome == "search_candidates":
        r = buscar_candidatos(q=a.get("q"), universo=_universo(a), pagina=1,
                              por_pagina=max(1, min(int(a.get("limite") or 10), MAX_ITENS)),
                              ordenar_por=a.get("ordenar_por") if a.get("ordenar_por") in ORDENAVEIS else "nm_urna",
                              ordem=a.get("ordem") if a.get("ordem") in ("asc", "desc") else "asc", cur=cur)
        campos = ["sq_candidato", "nm_urna", "nm_candidato", "nr_candidato", "ds_cargo", "sg_uf",
                  "sg_partido", "situacao_candidatura", "idade_na_posse", "total_bens", "qt_bens",
                  "historico_disponivel", "outros_registros_2026", "correspondencia", "fonte_linha"]
        return {"natureza": "DADO", "geracao_tse": r["geracao_tse"], "total": r["total"],
                "criterio_busca": r["consulta"]["criterio_busca"],
                "ordenacao": f"{r['consulta']['ordenar_por']} {r['consulta']['ordem']}",
                "itens": [{c: it.get(c) for c in campos} for it in r["itens"]]}
    if nome == "get_candidate":
        d = detalhe_candidato(sq=int(a["sq"]), cur=cur)
        h, p = d["historico"], d["patrimonio"]
        return {"geracao_tse": d["geracao_tse"], "fonte_arquivo": "consulta_cand_2026_BRASIL.csv",
                "fonte_linha": d["identificacao"]["sq_candidato"]["fonte"]["linha"],
                "identificacao": _valores(d["identificacao"]), "perfil": _valores(d["perfil"]),
                "situacao": _valores(d["situacao"]),
                "patrimonio": {"declarou_bens": p["declarou_bens"]["valor"], "qt_bens": p["qt_bens"]["valor"],
                               "total_bens": p["total_bens"]["valor"], "mensagem": p["mensagem"]},
                "historico": {"disponivel": h["disponivel"]["valor"], "mensagem": h["mensagem"],
                              "qt_candidaturas_anteriores": h["qt_candidaturas_anteriores"]["valor"],
                              "qt_vezes_eleito": h["qt_vezes_eleito"]["valor"],
                              "ultimo_cargo_eleito": h["ultimo_cargo_eleito"]["valor"]},
                "fundamentos_indeferimento": {"descricao": d["fundamentos_indeferimento"]["descricao"],
                                              "itens": [{"tipo": f["tipo"], "motivo": f["motivo"]}
                                                        for f in d["fundamentos_indeferimento"]["itens"]]},
                "outros_registros_2026": d["outros_registros_2026"]["itens"]}
    if nome == "get_candidate_assets":
        p = detalhe_candidato(sq=int(a["sq"]), cur=cur)["patrimonio"]
        bens = p["bens"]["itens"]
        return {"natureza": "DADO (valores) / CALCULO (total, categorias)",
                "total_bens": p["total_bens"]["valor"], "qt_bens": p["qt_bens"]["valor"],
                "mensagem": p["mensagem"], "por_categoria": p["por_categoria"]["itens"],
                "bens": [{k: b[k] for k in ("nr_ordem", "tipo", "categoria", "descricao", "valor")}
                         | {"fonte_linha": b["fonte"]["linha"]} for b in bens[:50]],
                "bens_omitidos": max(0, len(bens) - 50)}
    if nome == "get_candidate_history":
        h = detalhe_candidato(sq=int(a["sq"]), cur=cur)["historico"]
        return {"disponivel": h["disponivel"]["valor"], "mensagem": h["mensagem"],
                "observacao": h["observacao"],
                "linha_do_tempo": [{k: i[k] for k in ("ano_eleicao", "turno", "ds_cargo", "sg_uf", "nm_ue",
                                                      "sg_partido", "situacao_julgamento", "resultado", "eleito")}
                                   for i in h["linha_do_tempo"]["itens"]]}
    if nome == "compare_candidates":
        r = comparar(sq=[",".join(str(int(s)) for s in a["sqs"])], cur=cur)
        return {"geracao_tse": r["geracao_tse"], "candidatos": r["candidatos"],
                "verificacoes": r["verificacoes"], "alertas": r["alertas"],
                "diferencas": [d["texto"] for d in r["diferencas"]["itens"]],
                "tabela": {l["campo"]: [v["valor"] for v in l["valores"]] for l in r["tabela"]}}
    if nome == "get_candidate_position":
        r = posicao(sq=int(a["sq"]), metrica=a["metrica"], cur=cur)
        return {k: r.get(k) for k in ("natureza", "rotulo", "valor", "percentil", "relacao_mediana",
                                      "mediana_universo", "n_com_dado", "descricao", "mensagem",
                                      "exclusao", "universo", "geracao_tse")}
    if nome == "get_party_statistics":
        return _estat(cur, a)
    if nome == "get_state_statistics":
        return _estat(cur, a)
    if nome == "calculate_statistics":
        return _estat(cur, a)
    if nome == "get_source":
        return ver_fonte(tabela=a["tabela"], sq=int(a["sq"]), campo=a["campo"],
                         nr_ordem=a.get("nr_ordem"), linha=a.get("linha"), cur=cur)
    raise ValueError(f"Ferramenta desconhecida: {nome}")


def executar(nome: str, argumentos: dict, cur) -> dict:
    """Executa uma ferramenta; erro vira resultado (o modelo precisa saber o que falhou)."""
    if nome not in NOMES:
        return {"erro": f"Ferramenta desconhecida: {nome}"}
    try:
        return _executar(nome, argumentos, cur)
    except HTTPException as e:
        return {"erro": e.detail}
    except (KeyError, ValueError, TypeError) as e:
        return {"erro": f"Argumentos inválidos para {nome}: {e}"}


def _json_padrao(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def para_json(resultado: dict) -> str:
    return json.dumps(resultado, ensure_ascii=False, default=_json_padrao)


def strings_da_base(resultado) -> set[str]:
    """Todas as strings vindas da base (para a checagem de neutralidade não confundi-las com
    texto gerado — ex.: grau de instrução 'SUPERIOR COMPLETO')."""
    saida = set()
    if isinstance(resultado, str):
        saida.add(resultado)
    elif isinstance(resultado, dict):
        for v in resultado.values():
            saida |= strings_da_base(v)
    elif isinstance(resultado, list):
        for v in resultado:
            saida |= strings_da_base(v)
    return saida
