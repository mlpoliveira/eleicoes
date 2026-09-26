"""Testes de GET /api/estatisticas e GET /api/candidatos/{sq}/posicao (banco sintético v1).

As estatísticas são conferidas contra um recálculo independente (numpy) sobre os valores
lidos diretamente do banco.
"""
import numpy as np
import pytest

SQ = 190000000000
BASE = {"cd_cargo": 7, "uf": "RJ"}


def est(cliente, **params):
    r = cliente.get("/api/estatisticas", params={**BASE, **params})
    assert r.status_code == 200, r.text
    return r.json()


def valores(con, expr, cond="TRUE"):
    return np.array([r[0] for r in con.execute(
        f"SELECT {expr}::DOUBLE FROM v_candidato WHERE {expr} IS NOT NULL AND {cond}").fetchall()])


# ---------------------------------------------------------------- universo
def test_universo_explicito(cliente):
    r = est(cliente)
    assert r["natureza"] == "CALCULO" and r["geracao_tse"]
    u = r["universo"]
    assert u["n"] == 40
    assert u["descricao"] == "Candidaturas a Deputado Estadual em RJ — Eleições 2026"
    assert u["filtros"] == {"uf": ["RJ"], "cd_cargo": [7]}
    assert u["alertas"] == []


def test_universo_com_filtros_e_pequeno(cliente):
    u = est(cliente, genero="MASCULINO", idade_min=30)["universo"]
    assert u["n"] == 14
    assert "gênero = MASCULINO" in u["descricao"] and "idade na posse entre 30 e —" in u["descricao"]
    assert any("Universo pequeno (n = 14)" in a for a in u["alertas"])


def test_universo_vazio(cliente):
    r = est(cliente, uf="SP", metrica="total_bens")
    assert r["universo"]["n"] == 0
    assert "Nenhuma candidatura" in r["universo"]["alertas"][0]
    assert r["numerica"]["n_com_dado"] == 0 and r["numerica"]["mensagem"]


def test_ano_indisponivel(cliente):
    r = cliente.get("/api/estatisticas", params={"ano": 2022})
    assert r.status_code == 422 and "não disponível" in r.text


def test_parametros_invalidos(cliente):
    for params in ({"metrica": "score"}, {"categoricas": "pessoa_id"},
                   {"cruzamentos": "genero"}, {"cruzamentos": "genero,xyz"},
                   {"escala": "quadratica"}):
        assert cliente.get("/api/estatisticas", params=params).status_code == 422, params


# ---------------------------------------------------------------- métrica numérica
def test_idade_confere_com_recalculo(cliente, con_v1):
    v = valores(con_v1, "idade_na_posse")
    n = est(cliente, metrica="idade_na_posse", bins=4)["numerica"]
    assert n["n_com_dado"] == len(v) == 40 and n["n_sem_dado"] == 0
    assert n["media"] == pytest.approx(v.mean())
    assert n["mediana"] == pytest.approx(np.median(v))
    assert (n["min"], n["max"]) == (v.min(), v.max()) == (30, 69)
    assert n["desvio_padrao"] == pytest.approx(v.std(ddof=1))
    for p in (10, 25, 50, 75, 90):
        assert n["percentis"][f"p{p}"] == pytest.approx(np.percentile(v, p))
    h = n["histograma"]
    assert h["escala"] == "linear"
    assert [f["n"] for f in h["faixas"]] == [10, 10, 10, 10]
    assert h["faixas"][0]["inicio"] == 30 and h["faixas"][-1]["fim"] == 69


def test_total_bens_sem_bens_fica_de_fora(cliente, con_v1):
    v = valores(con_v1, "total_bens")
    n = est(cliente, metrica="total_bens")["numerica"]
    assert n["n_com_dado"] == len(v) == 39
    assert n["n_sem_dado"] == 1
    assert n["sem_dado_por_motivo"] == {"declarou_bens_n": 1,
                                        "declarou_bens_s_sem_bens_no_arquivo": 0,
                                        "declarou_bens_nao_informado": 0}
    assert "não é tratado como zero" in n["exclusao"]
    assert n["media"] == pytest.approx(v.mean())
    assert n["min"] == pytest.approx(v.min())
    h = n["histograma"]
    assert h["escala"] == "log10"
    assert sum(f["n"] for f in h["faixas"]) + h["n_fora_da_escala"] == 39


def test_histograma_linear_soma_n(cliente):
    n = est(cliente, metrica="total_bens", escala="linear", bins=7)["numerica"]
    assert len(n["histograma"]["faixas"]) == 7
    assert sum(f["n"] for f in n["histograma"]["faixas"]) == n["n_com_dado"]


def test_historico_indisponivel_fica_de_fora(cliente, con_v1):
    v = valores(con_v1, "qt_candidaturas_anteriores", "historico_disponivel")
    n = est(cliente, metrica="qt_candidaturas_anteriores")["numerica"]
    assert n["n_com_dado"] == len(v) == 39
    assert n["sem_dado_por_motivo"] == {"historico_indisponivel": 1}
    assert "não significa que nunca concorreram" in n["exclusao"]
    assert n["media"] == pytest.approx(v.mean())


def test_um_unico_valor(cliente):
    n = est(cliente, metrica="idade_na_posse", idade_min=45, idade_max=45)["numerica"]
    assert n["n_com_dado"] == 1 and n["desvio_padrao"] is None
    assert n["histograma"]["faixas"] == [{"inicio": 45, "fim": 46, "n": 1}]


# ---------------------------------------------------------------- categóricas e cruzamentos
def test_categoricas(cliente):
    r = est(cliente, categoricas=["genero", "faixa_etaria", "historico_disponivel"])
    g, f, h = r["categoricas"]
    assert g["natureza"] == "DADO"
    assert g["itens"] == [{"valor": "FEMININO", "n": 26, "pct": 65.0},
                          {"valor": "MASCULINO", "n": 14, "pct": 35.0}]
    assert f["natureza"] == "CALCULO"
    assert {i["valor"]: i["n"] for i in f["itens"]} == {
        "30 a 39": 10, "40 a 49": 10, "50 a 59": 10, "60 a 69": 10}
    assert {i["valor"]: i["n"] for i in h["itens"]} == {False: 1, True: 39}


def test_categorica_com_ausencia(cliente):
    r = est(cliente, categoricas=["eleito_anteriormente"])
    itens = {i["valor"]: i["n"] for i in r["categoricas"][0]["itens"]}
    # SQ+7 sem histórico → não disponível (não é "não eleito"); SQ+10 só tem 2026 → False
    assert itens == {False: 1, True: 38, "não disponível no dataset utilizado": 1}


def test_cargo_com_rotulo(cliente):
    itens = est(cliente, categoricas=["cd_cargo"])["categoricas"][0]["itens"]
    assert itens == [{"valor": "7 - Deputado Estadual", "n": 40, "pct": 100.0}]


def test_cruzamento(cliente):
    c = est(cliente, categoricas=[], cruzamentos=["genero,faixa_etaria"])["cruzamentos"][0]
    assert (c["linhas"], c["colunas"]) == ("genero", "faixa_etaria")
    assert sum(x["n"] for x in c["celulas"]) == 40
    for g in ("FEMININO", "MASCULINO"):
        assert sum(x["pct_linha"] for x in c["celulas"] if x["genero"] == g) == pytest.approx(100)
    masc_30 = next(x for x in c["celulas"]
                   if x["genero"] == "MASCULINO" and x["faixa_etaria"] == "30 a 39")
    assert masc_30["n"] == 4  # índices 0, 3, 6, 9


def test_metricas_disponiveis(cliente):
    r = cliente.get("/api/estatisticas/metricas").json()
    assert "total_bens" in r["metricas"] and "faixa_etaria" in r["categoricas"]


# ---------------------------------------------------------------- posição do candidato
def test_posicao(cliente):
    r = cliente.get(f"/api/candidatos/{SQ}/posicao", params={"metrica": "idade_na_posse"}).json()
    assert r["natureza"] == "CALCULO"
    assert r["universo"]["n"] == 40 and r["universo"]["filtros"] == {"uf": ["RJ"], "cd_cargo": [7]}
    assert r["valor"] == 30 and r["percentil"] == 1   # (0 menores + 0,5 × 1 igual) / 40
    assert r["relacao_mediana"] == "abaixo da mediana"
    assert r["descricao"] == ("Idade na data da posse abaixo da mediana do universo: percentil 1 "
                              "entre candidaturas a Deputado Estadual em RJ — Eleições 2026 com "
                              "o dado disponível, n = 40.")
    topo = cliente.get(f"/api/candidatos/{SQ + 39}/posicao",
                       params={"metrica": "idade_na_posse"}).json()
    assert topo["percentil"] == 99 and topo["relacao_mediana"] == "acima da mediana"


def test_posicao_sem_dado(cliente):
    r = cliente.get(f"/api/candidatos/{SQ + 9}/posicao", params={"metrica": "total_bens"}).json()
    assert r["valor"] is None and r["percentil"] is None and "não disponível" in r["mensagem"]
    r = cliente.get(f"/api/candidatos/{SQ + 7}/posicao",
                    params={"metrica": "qt_candidaturas_anteriores"}).json()
    assert r["percentil"] is None


def test_posicao_invalida(cliente):
    assert cliente.get(f"/api/candidatos/{SQ}/posicao",
                       params={"metrica": "score"}).status_code == 422
    assert cliente.get("/api/candidatos/1/posicao",
                       params={"metrica": "total_bens"}).status_code == 404
