"""Testes de GET /api/candidatos e GET /api/filtros (banco sintético, carga v1)."""
import pytest

SQ = 190000000000
SQ_ACENTO = SQ + 12  # "MARIA CONCEIÇÃO ARAÚJO" / urna "CONCEIÇÃO ARAÚJO"


def buscar(cliente, **params):
    r = cliente.get("/api/candidatos", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def sqs(resp):
    return [it["sq_candidato"] for it in resp["itens"]]


# ---------------------------------------------------------------- tolerância na busca
@pytest.mark.parametrize("q", ["conceicao", "CONCEIÇÃO", "Conceiçao", "conceição araújo",
                               "ARAUJO", "araú", "maria araujo", "  araujo  "])
def test_busca_ignora_caixa_e_acentos(cliente, q):
    r = buscar(cliente, q=q)
    assert sqs(r) == [SQ_ACENTO]
    assert r["itens"][0]["correspondencia"] == "exata"


@pytest.mark.parametrize("q", ["arauju", "concecao", "conseicao araujo"])
def test_busca_tolera_erro_de_digitacao(cliente, q):
    r = buscar(cliente, q=q)
    assert SQ_ACENTO in sqs(r)
    item = next(it for it in r["itens"] if it["sq_candidato"] == SQ_ACENTO)
    assert item["correspondencia"] == "aproximada"


def test_variantes_encontram_os_mesmos_registros(cliente):
    """Critério de aceite da T2, aplicado ao nome sintético."""
    base = set(sqs(buscar(cliente, q="araujo")))
    for q in ["ARAUJO", "arauj", "araújo"]:
        assert set(sqs(buscar(cliente, q=q))) == base


def test_exato_antes_do_aproximado(cliente):
    r = buscar(cliente, q="fulano", por_pagina=200)
    tipos = [it["correspondencia"] for it in r["itens"]]
    assert tipos == sorted(tipos, key=lambda t: t == "aproximada")
    assert r["total"] == 39  # todos menos a MARIA


def test_busca_sem_resultado(cliente):
    r = buscar(cliente, q="xyzwqk")
    assert r["total"] == 0 and r["itens"] == []


def test_palavra_curta_nao_usa_aproximacao(cliente):
    # "da" aparece em "FULANO i DA SILVA"; "do" não aparece em nenhum nome
    assert buscar(cliente, q="do")["total"] == 0


def test_termo_so_com_pontuacao(cliente):
    assert cliente.get("/api/candidatos", params={"q": "!!!"}).status_code == 422


def test_busca_por_numero(cliente):
    r = buscar(cliente, q="10005")
    assert sqs(r) == [SQ + 5]
    assert r["itens"][0]["correspondencia"] == "numero"
    assert sqs(buscar(cliente, q=str(SQ + 7))) == [SQ + 7]


def test_busca_com_aspas_e_sql(cliente):
    """Termo vai sempre como parâmetro, nunca concatenado no SQL."""
    r = buscar(cliente, q="araujo'; DROP TABLE candidato; --")
    assert r["total"] == 0
    assert buscar(cliente)["total"] == 40


# ---------------------------------------------------------------- filtros, paginação, ordem
def test_sem_termo_lista_todos(cliente):
    r = buscar(cliente)
    assert r["total"] == 40 and len(r["itens"]) == 40
    assert r["itens"][0]["correspondencia"] is None


def test_filtros(cliente):
    assert buscar(cliente, uf="rj")["total"] == 40
    assert buscar(cliente, uf="SP")["total"] == 0
    assert buscar(cliente, cd_cargo=7, sg_partido="PT")["total"] == 40
    assert buscar(cliente, cd_cargo=6)["total"] == 0
    assert sqs(buscar(cliente, na_urna="false")) == [SQ + 8]
    assert sqs(buscar(cliente, situacao="RENÚNCIA")) == [SQ + 8]
    assert buscar(cliente, idade_min=40, idade_max=49)["total"] == 10   # idade = 30 + índice
    assert buscar(cliente, idade_min=70)["total"] == 0
    assert buscar(cliente, genero="FEMININO", cor_raca="PARDA",
                  grau_instrucao="SUPERIOR COMPLETO", federacao="FE BRASIL")["total"] == 26


def test_filtro_com_varios_valores(cliente):
    r = cliente.get("/api/candidatos", params=[("situacao", "RENÚNCIA"), ("situacao", "DEFERIDO")])
    assert r.json()["total"] == 40


def test_filtro_combinado_com_busca(cliente):
    assert buscar(cliente, q="araujo", na_urna="false")["total"] == 0


def test_paginacao(cliente):
    p1 = buscar(cliente, por_pagina=15, pagina=1, ordenar_por="nr_candidato")
    p3 = buscar(cliente, por_pagina=15, pagina=3, ordenar_por="nr_candidato")
    assert len(p1["itens"]) == 15 and len(p3["itens"]) == 10
    assert p1["total"] == p3["total"] == 40
    assert not set(sqs(p1)) & set(sqs(p3))


def test_ordenacao_escolhida(cliente):
    asc = buscar(cliente, ordenar_por="nr_candidato", ordem="asc")
    desc = buscar(cliente, ordenar_por="nr_candidato", ordem="desc")
    assert sqs(asc) == list(reversed(sqs(desc)))


def test_ordenacao_nulos_por_ultimo(cliente):
    """Quem não tem bens (total nulo) fica no fim nos dois sentidos — nulo não vira zero."""
    for ordem in ("asc", "desc"):
        r = buscar(cliente, ordenar_por="total_bens", ordem=ordem)
        assert r["itens"][-1]["sq_candidato"] == SQ + 9
        assert r["itens"][-1]["total_bens"] is None


def test_ordenacao_invalida(cliente):
    assert cliente.get("/api/candidatos", params={"ordenar_por": "pessoa_id"}).status_code == 422
    assert cliente.get("/api/candidatos", params={"ordem": "x"}).status_code == 422


# ---------------------------------------------------------------- conteúdo da resposta
def test_pessoa_id_nunca_exposto(cliente):
    r = cliente.get("/api/candidatos", params={"por_pagina": 200})
    assert "pessoa_id" not in r.text


def test_outros_registros_sinalizados(cliente):
    itens = {it["sq_candidato"]: it for it in buscar(cliente)["itens"]}
    assert itens[SQ]["possui_outro_registro_2026"] is True
    assert itens[SQ]["outros_registros_2026"] == [SQ + 1, SQ + 2]
    assert itens[SQ + 3]["possui_outro_registro_2026"] is False
    assert itens[SQ + 3]["outros_registros_2026"] == []


def test_bloco_de_fonte(cliente):
    r = buscar(cliente, q="araujo")
    assert r["natureza"] == "DADO"
    assert r["geracao_tse"] == "26/09/2026 08:31:16"
    assert r["campos"]["total_bens"]["natureza"] == "CALCULO"
    assert r["campos"]["nm_urna"]["fonte"]["campo"] == "NM_URNA_CANDIDATO"
    assert r["consulta"]["criterio_busca"]
    it = r["itens"][0]
    assert it["fonte_arquivo"] == "consulta_cand_2026_BRASIL.csv" and it["fonte_linha"] == 14
    assert it["fonte_arquivo_compl"] == "consulta_cand_complementar_2026_BRASIL.csv"


def test_ausencias_continuam_nulas(cliente):
    itens = {it["sq_candidato"]: it for it in buscar(cliente)["itens"]}
    assert itens[SQ + 9]["qt_bens"] is None and itens[SQ + 9]["total_bens"] is None
    assert itens[SQ + 7]["historico_disponivel"] is False


# ---------------------------------------------------------------- /api/filtros
def test_filtros_disponiveis(cliente):
    r = cliente.get("/api/filtros").json()
    f = r["filtros"]
    assert r["universo"]["n"] == 40
    assert [v["valor"] for v in f["uf"]["valores"]] == ["RJ"]
    assert f["cd_cargo"]["valores"] == [{"valor": 7, "rotulo": "DEPUTADO ESTADUAL", "n": 40}]
    assert f["sg_partido"]["valores"][0]["rotulo"] == "PARTIDO DOS TRABALHADORES"
    assert {v["valor"]: v["n"] for v in f["situacao"]["valores"]} == {"DEFERIDO": 39, "RENÚNCIA": 1}
    assert {v["valor"]: v["n"] for v in f["na_urna"]["valores"]} == {True: 39, False: 1}
    assert f["idade"] == {"coluna": "idade_na_posse", "min": 30, "max": 69, "n_nao_disponivel": 0}


def test_banco_inexistente(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import criar_app
    with TestClient(criar_app(tmp_path / "nao_existe.duckdb")) as c:
        assert c.get("/api/candidatos").status_code == 503


def test_carga_atual(cliente):
    r = cliente.get("/api/carga").json()
    assert r["carga_id"] == 1 and r["geracao_tse"] == "26/09/2026 08:31:16"
    assert r["qt_candidaturas"] == 40 and r["qt_cargas"] == 1
