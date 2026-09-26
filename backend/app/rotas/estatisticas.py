"""
Estatísticas de grupo (GET /api/estatisticas) e posição do candidato no seu universo
(GET /api/candidatos/{sq}/posicao).

Tudo aqui é CÁLCULO sobre dados do TSE e sempre informa o universo (descrição + n). Registros
sem o dado (ex.: candidato sem bens no arquivo, histórico indisponível) NÃO entram nos cálculos:
são contados à parte em n_sem_dado, com o motivo. Nenhum valor ausente vira zero.
Não existe aqui ordenação de candidatos nem "ranking": a posição de um candidato é dada só como
percentil e em relação à mediana do universo.
"""
import math

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import carga_atual, consultar
from ..dependencias import cursor
from ..metadados import BEM, CAND, COMPL, DATASET, HIST
from ..universo import Universo, fmt_n, universo_dos_parametros

router = APIRouter(prefix="/api", tags=["estatisticas"])

PERCENTIS = [10, 25, 50, 75, 90]

# métrica -> definição. `expr` é SQL sobre v_candidato; `exige` restringe quem tem o dado.
METRICAS = {
    "total_bens": {
        "rotulo": "Patrimônio declarado (soma dos bens)", "unidade": "BRL",
        "expr": "total_bens::DOUBLE", "escala": "log10",
        "fonte": {"arquivo": BEM, "campo": "VR_BEM_CANDIDATO"},
        "exclusao": "Candidaturas sem nenhum bem no arquivo bem_candidato do TSE não entram no "
                    "cálculo (total não disponível — não é tratado como zero); são contadas em "
                    "n_sem_dado. Bens declarados com valor zero entram normalmente."},
    "qt_bens": {
        "rotulo": "Quantidade de bens declarados", "unidade": "bens",
        "expr": "qt_bens::DOUBLE", "escala": "linear",
        "fonte": {"arquivo": BEM, "campo": "NR_ORDEM_BEM_CANDIDATO"},
        "exclusao": "Candidaturas sem nenhum bem no arquivo bem_candidato do TSE não entram no "
                    "cálculo; são contadas em n_sem_dado."},
    "idade_na_posse": {
        "rotulo": "Idade na data da posse", "unidade": "anos",
        "expr": "idade_na_posse::DOUBLE", "escala": "linear",
        "fonte": {"arquivo": COMPL, "campo": "NR_IDADE_DATA_POSSE"},
        "exclusao": "Candidaturas sem idade informada não entram no cálculo."},
    "limite_gastos": {
        "rotulo": "Limite de gastos de campanha", "unidade": "BRL",
        "expr": "limite_gastos::DOUBLE", "escala": "log10",
        "fonte": {"arquivo": COMPL, "campo": "VR_DESPESA_MAX_CAMPANHA"},
        "exclusao": "Candidaturas sem limite informado (ou com valor <= 0 no arquivo) não entram "
                    "no cálculo."},
    "qt_candidaturas_anteriores": {
        "rotulo": "Candidaturas anteriores identificadas (desde 2004)", "unidade": "candidaturas",
        "expr": "qt_candidaturas_anteriores::DOUBLE", "escala": "linear",
        "exige": "historico_disponivel",
        "fonte": {"arquivo": HIST, "campo": "ANO_ELEICAO"},
        "exclusao": "Candidaturas ausentes do arquivo de histórico do TSE (histórico não "
                    "disponível — não significa que nunca concorreram) não entram no cálculo."},
    "qt_vezes_eleito": {
        "rotulo": "Vezes eleito(a) em candidaturas anteriores (desde 2004)", "unidade": "vezes",
        "expr": "qt_vezes_eleito::DOUBLE", "escala": "linear",
        "exige": "historico_disponivel",
        "fonte": {"arquivo": HIST, "campo": "DS_SIT_TOT_TURNO"},
        "exclusao": "Candidaturas ausentes do arquivo de histórico do TSE (histórico não "
                    "disponível) não entram no cálculo."},
}

# dimensão categórica -> expressão SQL sobre v_candidato (NULL = não disponível)
CATEGORICAS = {
    "genero": "genero", "cor_raca": "cor_raca", "grau_instrucao": "grau_instrucao",
    "estado_civil": "estado_civil", "ocupacao": "ocupacao", "sg_partido": "sg_partido",
    "federacao": "nm_federacao", "sg_uf": "sg_uf", "cd_cargo": "cd_cargo",
    "situacao": "situacao_candidatura", "na_urna": "na_urna", "declarou_bens": "declarou_bens",
    "historico_disponivel": "historico_disponivel",
    "eleito_anteriormente": "CASE WHEN historico_disponivel THEN qt_vezes_eleito > 0 END",
    "faixa_etaria": """CASE WHEN idade_na_posse IS NULL THEN NULL
                            WHEN idade_na_posse < 30 THEN 'até 29'
                            WHEN idade_na_posse < 40 THEN '30 a 39'
                            WHEN idade_na_posse < 50 THEN '40 a 49'
                            WHEN idade_na_posse < 60 THEN '50 a 59'
                            WHEN idade_na_posse < 70 THEN '60 a 69'
                            ELSE '70 ou mais' END""",
}
CATEGORICAS_CALCULADAS = {"eleito_anteriormente", "faixa_etaria", "historico_disponivel"}
NAO_DISPONIVEL = "não disponível no dataset utilizado"


def _motivos_sem_dado(cur, metrica: str, fonte: str) -> dict:
    """Por que parte do universo ficou fora do cálculo (contagens por motivo)."""
    m = METRICAS[metrica]
    if metrica in ("total_bens", "qt_bens"):
        sql = f"""SELECT count(*) FILTER (WHERE declarou_bens = 'N') AS declarou_bens_n,
                         count(*) FILTER (WHERE declarou_bens = 'S') AS declarou_bens_s_sem_bens_no_arquivo,
                         count(*) FILTER (WHERE declarou_bens IS NULL) AS declarou_bens_nao_informado
                  FROM {fonte} WHERE qt_bens IS NULL"""
    elif m.get("exige") == "historico_disponivel":
        sql = f"""SELECT count(*) FILTER (WHERE NOT historico_disponivel) AS historico_indisponivel
                  FROM {fonte}"""
    else:
        return {}
    return consultar(cur, sql)[0]


def _histograma(cur, fonte, expr, cond, escala, bins, vmin, vmax) -> dict:
    """Contagens por faixa. Em log10, valores <= 0 ficam numa contagem à parte."""
    fora = 0
    if escala == "log10":
        fora = consultar(cur, f"SELECT count(*) AS n FROM {fonte} {cond} AND {expr} <= 0")[0]["n"]
        pos = consultar(cur, f"SELECT min({expr}) AS mn FROM {fonte} {cond} AND {expr} > 0")[0]["mn"]
        if pos is None:
            return {"escala": escala, "faixas": [], "n_fora_da_escala": fora,
                    "observacao": "Nenhum valor positivo para a escala logarítmica."}
        lo, hi, val = math.log10(pos), math.log10(vmax), f"log10({expr})"
        cond = f"{cond} AND {expr} > 0"
    else:
        lo, hi, val = vmin, vmax, expr
    largura = (hi - lo) / bins if hi > lo else 1.0
    n_bins = bins if hi > lo else 1
    linhas = consultar(cur, f"""
        SELECT greatest(least(floor(({val} - ?) / ?)::INT, ?), 0) AS i, count(*) AS n
        FROM {fonte} {cond} GROUP BY 1 ORDER BY 1""", [lo, largura, n_bins - 1])
    contagem = {l["i"]: l["n"] for l in linhas}
    borda = (lambda x: 10 ** x) if escala == "log10" else (lambda x: x)
    faixas = [{"inicio": round(borda(lo + i * largura), 2),
               "fim": round(borda(lo + (i + 1) * largura), 2),
               "n": contagem.get(i, 0)} for i in range(n_bins)]
    saida = {"escala": escala, "faixas": faixas,
             "observacao": "Faixas fechadas à esquerda; a última inclui o máximo. "
                           "Bordas arredondadas em 2 casas decimais."}
    if escala == "log10":
        saida["n_fora_da_escala"] = fora
        saida["observacao"] += (" Escala logarítmica (base 10): cada faixa cobre a mesma razão "
                                "entre início e fim. Valores iguais a zero são contados em "
                                "n_fora_da_escala.")
    return saida


def _numerica(cur, fonte: str, metrica: str, bins: int, escala: str | None, n: int):
    m = METRICAS[metrica]
    expr = m["expr"]
    cond = f"WHERE {expr} IS NOT NULL"
    if m.get("exige"):
        cond += f" AND {m['exige']}"
    qs = ", ".join(f"quantile_cont({expr}, {p / 100})" for p in PERCENTIS)
    r = consultar(cur, f"""
        SELECT count({expr}) AS n_com_dado, avg({expr}) AS media, median({expr}) AS mediana,
               min({expr}) AS min, max({expr}) AS max, stddev_samp({expr}) AS desvio_padrao,
               [{qs}] AS percentis
        FROM {fonte} {cond}""")[0]
    n_com = r["n_com_dado"]
    saida = {
        "metrica": metrica, "rotulo": m["rotulo"], "unidade": m["unidade"],
        "natureza": "CALCULO",
        "fonte": {"dataset": DATASET, **m["fonte"]},
        "n_com_dado": n_com, "n_sem_dado": n - n_com,
        "sem_dado_por_motivo": _motivos_sem_dado(cur, metrica, fonte),
        "entram_no_calculo": "Somente as candidaturas com o dado (n_com_dado).",
        "exclusao": m["exclusao"],
    }
    if n_com == 0:
        saida["mensagem"] = "Nenhuma candidatura do universo tem este dado."
        return saida
    saida.update({
        "media": r["media"], "mediana": r["mediana"], "min": r["min"], "max": r["max"],
        "desvio_padrao": r["desvio_padrao"],
        "percentis": {f"p{p}": v for p, v in zip(PERCENTIS, r["percentis"])},
        "observacao_calculo": "Desvio padrão amostral; percentis por interpolação linear "
                              "(quantile_cont). Desvio padrão nulo quando n_com_dado = 1.",
        "histograma": _histograma(cur, fonte, expr, cond, escala or m["escala"], bins,
                                  r["min"], r["max"]),
    })
    return saida


COLUNAS_UNIVERSO = ["cd_cargo", "sg_uf", "genero", "cor_raca", "grau_instrucao", "estado_civil",
                    "ocupacao", "sg_partido", "nm_federacao", "situacao_candidatura", "na_urna",
                    "declarou_bens", "idade_na_posse", "total_bens", "qt_bens", "limite_gastos",
                    "historico_disponivel", "qt_candidaturas_anteriores", "qt_vezes_eleito"]


def _materializar(cur, universo: Universo) -> str:
    """Lê o universo de v_candidato UMA vez e o registra no cursor desta requisição (a conexão
    continua somente leitura; o registro some quando o cursor é fechado)."""
    clausula, params = universo.sql()
    df = cur.execute(f"SELECT {', '.join(COLUNAS_UNIVERSO)} FROM v_candidato {clausula}",
                     params).df()
    cur.register("universo_consulta", df)
    return "universo_consulta"


def _rotulos_cargo(cur) -> dict:
    return {r["cd_cargo"]: r["ds"].title() for r in consultar(
        cur, "SELECT cd_cargo, min(ds_cargo) AS ds FROM candidato GROUP BY 1")}


def _valor_categoria(dim, v, cargos):
    if v is None:
        return NAO_DISPONIVEL
    if dim == "cd_cargo":
        return f"{v} - {cargos.get(v, '')}".strip(" -")
    return v


def _categorica(cur, fonte: str, dim: str, n: int, cargos: dict) -> dict:
    linhas = consultar(cur, f"""
        SELECT {CATEGORICAS[dim]} AS valor, count(*) AS n FROM {fonte}
        GROUP BY 1 ORDER BY valor NULLS LAST""")
    return {
        "dimensao": dim,
        "natureza": "CALCULO" if dim in CATEGORICAS_CALCULADAS else "DADO",
        "ordem": "alfabética do valor; 'não disponível' por último",
        "itens": [{"valor": _valor_categoria(dim, l["valor"], cargos), "n": l["n"],
                   "pct": round(100 * l["n"] / n, 2) if n else None} for l in linhas],
    }


def _cruzamento(cur, fonte: str, a: str, b: str, n: int, cargos: dict) -> dict:
    linhas = consultar(cur, f"""
        SELECT {CATEGORICAS[a]} AS a, {CATEGORICAS[b]} AS b, count(*) AS n
        FROM {fonte} GROUP BY 1, 2 ORDER BY a NULLS LAST, b NULLS LAST""")
    total_linha = {}
    for l in linhas:
        total_linha[l["a"]] = total_linha.get(l["a"], 0) + l["n"]
    return {
        "linhas": a, "colunas": b, "natureza": "CALCULO",
        "descricao": "Contagem de candidaturas por combinação de valores; pct_universo sobre o "
                     "universo inteiro, pct_linha sobre o total do valor da linha.",
        "celulas": [{a: _valor_categoria(a, l["a"], cargos), b: _valor_categoria(b, l["b"], cargos),
                     "n": l["n"], "pct_universo": round(100 * l["n"] / n, 2) if n else None,
                     "pct_linha": round(100 * l["n"] / total_linha[l["a"]], 2)}
                    for l in linhas],
    }


@router.get("/estatisticas")
def estatisticas(
    universo: Universo = Depends(universo_dos_parametros),
    metrica: str | None = Query(None, description=f"Uma de: {', '.join(METRICAS)}"),
    categoricas: list[str] = Query(["genero", "cor_raca", "grau_instrucao"],
                                   description=f"Dimensões: {', '.join(CATEGORICAS)}"),
    cruzamentos: list[str] = Query([], description="Pares 'dimensao_a,dimensao_b'"),
    bins: int = Query(20, ge=1, le=100),
    escala: str | None = Query(None, pattern="^(linear|log10)$",
                               description="Escala do histograma (padrão depende da métrica)"),
    cur=Depends(cursor),
):
    if metrica is not None and metrica not in METRICAS:
        raise HTTPException(422, f"Métrica desconhecida: {metrica}. Use: {', '.join(METRICAS)}")
    desconhecidas = [c for c in categoricas if c not in CATEGORICAS]
    pares = [tuple(p.split(",")) for p in cruzamentos]
    desconhecidas += [d for par in pares for d in par if d not in CATEGORICAS]
    if desconhecidas or any(len(p) != 2 for p in pares):
        raise HTTPException(422, f"Dimensão inválida: {desconhecidas or cruzamentos}. "
                                 f"Use: {', '.join(CATEGORICAS)}")

    fonte = _materializar(cur, universo)
    n = consultar(cur, f"SELECT count(*) AS n FROM {fonte}")[0]["n"]
    cargos = _rotulos_cargo(cur)
    return {
        "natureza": "CALCULO",
        "geracao_tse": carga_atual(cur)["geracao_tse"],
        "fonte": {"dataset": DATASET, "arquivo": f"{CAND} | {COMPL} | {BEM} | {HIST}",
                  "linha": None, "campo": None},
        "universo": universo.bloco(cur, n),
        "numerica": _numerica(cur, fonte, metrica, bins, escala, n) if metrica else None,
        "categoricas": [_categorica(cur, fonte, c, n, cargos) for c in categoricas],
        "cruzamentos": [_cruzamento(cur, fonte, a, b, n, cargos) for a, b in pares],
    }


@router.get("/estatisticas/metricas")
def metricas_disponiveis():
    """Métricas numéricas e dimensões categóricas aceitas por /api/estatisticas."""
    return {"metricas": {k: {c: v[c] for c in ("rotulo", "unidade", "exclusao")}
                         for k, v in METRICAS.items()},
            "categoricas": list(CATEGORICAS)}


@router.get("/candidatos/{sq}/posicao")
def posicao(
    sq: int,
    metrica: str = Query(..., description=f"Uma de: {', '.join(METRICAS)}"),
    cur=Depends(cursor),
):
    """Percentil do candidato entre as candidaturas do mesmo cargo e UF (universo padrão)."""
    if metrica not in METRICAS:
        raise HTTPException(422, f"Métrica desconhecida: {metrica}. Use: {', '.join(METRICAS)}")
    m = METRICAS[metrica]
    c = consultar(cur, f"""SELECT cd_cargo, sg_uf, historico_disponivel, {m['expr']} AS valor
                           FROM v_candidato WHERE sq_candidato = ?""", [sq])
    if not c:
        raise HTTPException(404, f"Candidato {sq} não encontrado na carga atual.")
    c = c[0]
    universo = Universo(cd_cargo=[c["cd_cargo"]], uf=[c["sg_uf"]])
    clausula, params = universo.sql()
    n = consultar(cur, f"SELECT count(*) AS n FROM v_candidato {clausula}", params)[0]["n"]
    base = {
        "sq_candidato": sq, "metrica": metrica, "rotulo": m["rotulo"], "unidade": m["unidade"],
        "natureza": "CALCULO",
        "geracao_tse": carga_atual(cur)["geracao_tse"],
        "fonte": {"dataset": DATASET, **m["fonte"]},
        "universo": universo.bloco(cur, n),
        "exclusao": m["exclusao"],
    }
    sem_dado = c["valor"] is None or (m.get("exige") == "historico_disponivel"
                                      and not c["historico_disponivel"])
    if sem_dado:
        return {**base, "valor": None, "percentil": None,
                "mensagem": "Dado não disponível no dataset utilizado para esta candidatura; "
                            "não é possível calcular a posição."}

    cond = f"{clausula} AND {m['expr']} IS NOT NULL" + (
        f" AND {m['exige']}" if m.get("exige") else "")
    r = consultar(cur, f"""
        SELECT count(*) AS n_com_dado,
               count(*) FILTER (WHERE {m['expr']} < ?) AS menores,
               count(*) FILTER (WHERE {m['expr']} = ?) AS iguais,
               median({m['expr']}) AS mediana
        FROM v_candidato {cond}""", [c["valor"], c["valor"], *params])[0]
    percentil = round(100 * (r["menores"] + 0.5 * r["iguais"]) / r["n_com_dado"])
    if c["valor"] > r["mediana"]:
        relacao = "acima da mediana"
    elif c["valor"] < r["mediana"]:
        relacao = "abaixo da mediana"
    else:
        relacao = "igual à mediana"
    desc_universo = base["universo"]["descricao"]
    return {
        **base,
        "valor": c["valor"], "mediana_universo": r["mediana"], "n_com_dado": r["n_com_dado"],
        "percentil": percentil,
        "relacao_mediana": relacao,
        "definicao_percentil": "Percentual das candidaturas do universo com valor menor que o "
                               "do candidato, mais metade das com valor igual (posição média).",
        "descricao": f"{m['rotulo']} {relacao} do universo: percentil {percentil} entre "
                     f"{desc_universo[0].lower() + desc_universo[1:]} "
                     f"com o dado disponível, n = {fmt_n(r['n_com_dado'])}.",
    }
