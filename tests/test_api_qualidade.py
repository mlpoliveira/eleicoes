"""Testes de /api/qualidade, /api/cargas e /api/alteracoes (T9)."""
import pytest
from fastapi.testclient import TestClient

from app.main import criar_app
from conftest import ingerir

SQ = 190000000000


@pytest.fixture(scope="module")
def cliente2(banco_v2):
    """Banco com cargas v1 (carga 1) e v2 (carga 2)."""
    with TestClient(criar_app(banco_v2)) as c:
        yield c


@pytest.fixture(scope="module")
def cliente_removido(tmp_path_factory, dados_v1, dados_v2):
    """Cargas v2 e depois v1: o candidato 40 some e o 5 volta a DEFERIDO."""
    banco = tmp_path_factory.mktemp("banco_removido") / "e.duckdb"
    ingerir(dados_v2, banco)
    ingerir(dados_v1, banco)
    with TestClient(criar_app(banco)) as c:
        yield c


def test_cargas(cliente2):
    r = cliente2.get("/api/cargas").json()
    assert [c["carga_id"] for c in r["itens"]] == [2, 1]
    assert r["itens"][0]["geracao_tse"] == "26/09/2026 09:10:00"
    assert "categorias_bens.csv" in r["itens"][0]["arquivos"]


def test_qualidade_carga_atual(cliente2):
    r = cliente2.get("/api/qualidade").json()
    assert r["natureza"] == "CALCULO"
    assert r["carga"]["carga_id"] == 2 and r["carga_anterior"]["carga_id"] == 1
    v = {x["verificacao"]: x for x in r["verificacoes"]}
    assert v["candidatos"]["quantidade"] == 41
    assert v["candidatos"]["quantidade_anterior"] == 40 and v["candidatos"]["variacao"] == 1
    # toda verificação gravada pela ingestão tem explicação em texto
    assert all(x["explicacao"] for x in r["verificacoes"]), [
        x["verificacao"] for x in r["verificacoes"] if not x["explicacao"]]
    assert "não significa que a pessoa nunca concorreu" in v[
        "candidatos ausentes do arquivo de histórico (histórico indisponível, não 'estreantes')"]["explicacao"]


def test_qualidade_primeira_carga(cliente2):
    r = cliente2.get("/api/qualidade", params={"carga_id": 1}).json()
    assert r["carga_anterior"] is None
    assert all(x["quantidade_anterior"] is None and x["variacao"] is None for x in r["verificacoes"])
    assert cliente2.get("/api/qualidade", params={"carga_id": 9}).status_code == 404


def test_alteracoes(cliente2):
    r = cliente2.get("/api/alteracoes").json()
    assert r["carga"]["carga_id"] == 2 and r["carga_anterior"]["carga_id"] == 1
    assert r["total"] == 3
    assert {x["campo"]: x["n"] for x in r["resumo"]} == {
        "candidato": 1, "situacao_candidatura": 1, "situacao_julgamento": 1}
    assert {"campo": "situacao_candidatura", "antes": "DEFERIDO", "depois": "INDEFERIDO",
            "n": 1} in r["transicoes"]
    item = next(i for i in r["itens"] if i["campo"] == "situacao_candidatura")
    assert (item["sq_candidato"], item["nm_urna"], item["sg_uf"]) == (SQ + 5, "FULANO 5", "RJ")
    novo = next(i for i in r["itens"] if i["campo"] == "candidato")
    assert (novo["sq_candidato"], novo["depois"], novo["na_carga_atual"]) == (SQ + 40, "novo", True)
    assert "pessoa_id" not in cliente2.get("/api/alteracoes").text


def test_alteracoes_filtros(cliente2):
    assert cliente2.get("/api/alteracoes", params={"campo": "candidato"}).json()["total"] == 1
    assert cliente2.get("/api/alteracoes", params={"uf": "sp"}).json()["total"] == 0
    assert cliente2.get("/api/alteracoes", params={"cd_cargo": 7}).json()["total"] == 3
    assert cliente2.get("/api/alteracoes", params={"campo": "x"}).status_code == 422
    p = cliente2.get("/api/alteracoes", params={"por_pagina": 2, "pagina": 2}).json()
    assert p["total"] == 3 and len(p["itens"]) == 1


def test_alteracoes_primeira_carga(cliente2):
    r = cliente2.get("/api/alteracoes", params={"carga_id": 1}).json()
    assert r["total"] == 0 and "primeira carga" in r["mensagem"]


def test_candidato_removido_usa_dados_da_carga_anterior(cliente_removido):
    r = cliente_removido.get("/api/alteracoes").json()
    rem = next(i for i in r["itens"] if i["campo"] == "candidato")
    assert (rem["sq_candidato"], rem["antes"], rem["depois"]) == (SQ + 40, "existia", "removido")
    assert rem["na_carga_atual"] is False
    assert (rem["nm_urna"], rem["sg_uf"], rem["cd_cargo"]) == ("FULANO 40", "RJ", 7)
    assert {"campo": "situacao_candidatura", "antes": "INDEFERIDO", "depois": "DEFERIDO",
            "n": 1} in r["transicoes"]
