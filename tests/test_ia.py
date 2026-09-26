"""Testes da camada de IA (T10) com um modelo simulado — nunca chamam serviço externo."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ia import ferramentas
from app.ia.cliente import ClienteOpenAICompativel
from app.ia.neutralidade import pedido_recusado, termos_avaliativos
from app.main import criar_app

SQ = 190000000000


class ModeloRoteirizado:
    """Devolve as mensagens do roteiro em ordem e guarda o que recebeu."""
    modelo = "modelo-de-teste"

    def __init__(self, roteiro):
        self.roteiro, self.recebido = list(roteiro), []

    def completar(self, mensagens, ferramentas_):
        self.recebido.append({"mensagens": json.loads(json.dumps(mensagens, default=str)),
                              "ferramentas": ferramentas_})
        return self.roteiro.pop(0)


def chamada(nome, **args):
    return {"content": None, "tool_calls": [{"id": f"c_{nome}", "type": "function",
                                             "function": {"name": nome, "arguments": json.dumps(args)}}]}


def final(resposta, criterio="critério", calculo=""):
    return {"content": json.dumps({"criterio": criterio, "resposta": resposta, "calculo": calculo},
                                  ensure_ascii=False)}


@pytest.fixture
def ia(banco_v1, tmp_path, monkeypatch):
    monkeypatch.setenv("IA_LOG", str(tmp_path / "ia.jsonl"))

    def fazer(roteiro):
        modelo = ModeloRoteirizado(roteiro)
        cliente = TestClient(criar_app(banco_v1, ia_cliente=modelo))
        return cliente, modelo, tmp_path / "ia.jsonl"
    return fazer


def perguntar(cliente, texto):
    r = cliente.post("/api/perguntar", json={"pergunta": texto})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- fluxo com ferramentas
def test_resposta_com_ferramentas(ia):
    cliente, modelo, log = ia([
        chamada("search_candidates", q="conceicao araujo"),
        chamada("get_candidate_assets", sq=SQ + 12),
        final("CONCEIÇÃO ARAÚJO declarou 2 bens, somando R$ 351.200,50 (geração TSE 26/09/2026 08:31:16).",
              criterio="Busca pelo nome e bens declarados."),
    ])
    r = perguntar(cliente, "Quais bens a Conceição Araújo declarou?")
    assert r["recusada"] is False and r["natureza"] == "ANALISE"
    assert r["resposta"].startswith("CONCEIÇÃO ARAÚJO declarou 2 bens")
    assert r["criterio"] == "Busca pelo nome e bens declarados."
    assert r["geracao_tse"] == "26/09/2026 08:31:16"
    usados = [d["ferramenta"] for d in r["dados_usados"]]
    assert usados == ["search_candidates", "get_candidate_assets"]
    busca = r["dados_usados"][0]["resultado"]
    assert busca["itens"][0]["sq_candidato"] == SQ + 12
    assert r["dados_usados"][1]["resultado"]["total_bens"] == 351200.5
    # o modelo recebeu o resultado da ferramenta como mensagem 'tool'
    ultima = modelo.recebido[-1]["mensagens"]
    assert any(m["role"] == "tool" and "351200" in m["content"] for m in ultima)
    assert "pessoa_id" not in json.dumps(r)
    registro = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert registro["pergunta"] == "Quais bens a Conceição Araújo declarou?"
    assert [f["nome"] for f in registro["ferramentas"]] == usados


def test_prompt_de_sistema_tem_as_regras(ia):
    cliente, modelo, _ = ia([final("ok")])
    perguntar(cliente, "Quantas candidaturas há no RJ?")
    sistema = modelo.recebido[0]["mensagens"][0]["content"]
    for trecho in ("SOMENTE informações devolvidas pelas ferramentas", "não disponível no dataset utilizado",
                   "não recomende voto", "universo e o n", "NÃO significa que a pessoa nunca concorreu"):
        assert trecho in sistema
    nomes = {f["function"]["name"] for f in modelo.recebido[0]["ferramentas"]}
    assert {"search_candidates", "get_candidate", "compare_candidates", "get_candidate_assets",
            "get_candidate_history", "get_party_statistics", "get_state_statistics",
            "calculate_statistics", "get_source"} <= nomes


def test_erro_de_ferramenta_volta_para_o_modelo(ia):
    cliente, modelo, _ = ia([chamada("get_candidate", sq=1), final("Não encontrei o registro 1.")])
    r = perguntar(cliente, "Dados do candidato 1")
    assert "não encontrado" in r["dados_usados"][0]["resultado"]["erro"]
    assert r["resposta"] == "Não encontrei o registro 1."


def test_limite_de_rodadas(ia):
    cliente, _, _ = ia([chamada("search_candidates", q="fulano")] * 6)
    r = perguntar(cliente, "Liste os fulanos")
    assert "limite de consultas" in r["resposta"] and len(r["dados_usados"]) == 6


def test_resposta_sem_json_e_aceita_como_texto(ia):
    cliente, _, _ = ia([{"content": "Há 40 candidaturas no universo consultado."}])
    assert perguntar(cliente, "Quantas candidaturas?")["resposta"] == "Há 40 candidaturas no universo consultado."


# ---------------------------------------------------------------- neutralidade
@pytest.mark.parametrize("texto", [
    "Em quem devo votar para deputado?",
    "Qual o melhor candidato do RJ?",
    "Quem é o candidato mais preparado?",
    "Faça um ranking dos partidos",
    "Esse candidato é honesto?",
    "Qual a religião do candidato 10005?",
])
def test_recusa_sem_chamar_o_modelo(ia, texto):
    cliente, modelo, log = ia([])
    r = perguntar(cliente, texto)
    assert r["recusada"] is True and r["resposta"] is None
    assert r["recusa"]["explicacao"] and r["recusa"]["alternativa"]
    assert modelo.recebido == []
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["recusa"]


@pytest.mark.parametrize("texto", [
    "Quais os 10 maiores patrimônios declarados no RJ?",
    "Quantos votos o candidato teve em 2022?",
    "Qual a mediana de idade dos candidatos a governador?",
    "Quantas candidaturas foram indeferidas?",
])
def test_perguntas_factuais_nao_sao_recusadas(texto):
    assert pedido_recusado(texto) is None


def test_termo_avaliativo_leva_a_reescrita(ia):
    cliente, modelo, log = ia([
        chamada("get_candidate", sq=SQ),
        final("FULANO 0 é um político experiente, com 2 candidaturas anteriores."),
        final("FULANO 0 possui 2 candidaturas anteriores identificadas."),
    ])
    r = perguntar(cliente, "Fale sobre o FULANO 0")
    assert r["resposta"] == "FULANO 0 possui 2 candidaturas anteriores identificadas."
    assert "experiente" in modelo.recebido[-1]["mensagens"][-1]["content"]
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["reescrita"]["termos"] == ["experiente"]


def test_termo_avaliativo_persistente_e_retido(ia):
    cliente, _, _ = ia([final("É o candidato mais preparado."), final("Continua sendo o melhor.")])
    r = perguntar(cliente, "Fale sobre o FULANO 0")
    assert "retida pelo filtro de neutralidade" in r["resposta"]


def test_dado_da_base_nao_dispara_filtro():
    base = {"SUPERIOR COMPLETO"}
    assert termos_avaliativos("Grau de instrução: SUPERIOR COMPLETO.", base) == []
    assert termos_avaliativos("Tem ensino superior.", set()) == ["superior"]


# ---------------------------------------------------------------- ferramentas e configuração
@pytest.mark.parametrize("nome,args", [
    ("search_candidates", {"q": "fulano", "uf": "RJ", "limite": 5}),
    ("get_candidate", {"sq": SQ + 5}),
    ("get_candidate_assets", {"sq": SQ + 9}),
    ("get_candidate_history", {"sq": SQ + 15}),
    ("compare_candidates", {"sqs": [SQ, SQ + 7]}),
    ("get_candidate_position", {"sq": SQ, "metrica": "idade_na_posse"}),
    ("get_party_statistics", {"sg_partido": "PT", "metrica": "total_bens"}),
    ("get_state_statistics", {"uf": "RJ", "cd_cargo": 7}),
    ("calculate_statistics", {"metrica": "qt_candidaturas_anteriores", "cruzamento": ["genero", "faixa_etaria"]}),
    ("get_source", {"tabela": "candidato", "sq": SQ + 8, "campo": "situacao_candidatura"}),
])
def test_todas_as_ferramentas_executam(con_v1, nome, args):
    r = ferramentas.executar(nome, args, con_v1.cursor())
    assert "erro" not in r, r
    texto = ferramentas.para_json(r)
    assert "pessoa_id" not in texto and len(texto) < 60_000


def test_ferramenta_ausencias(con_v1):
    bens = ferramentas.executar("get_candidate_assets", {"sq": SQ + 9}, con_v1.cursor())
    assert bens["total_bens"] is None and "não é zero" in bens["mensagem"]
    hist = ferramentas.executar("get_candidate_history", {"sq": SQ + 7}, con_v1.cursor())
    assert hist["disponivel"] is False and "não significa" in hist["mensagem"]
    assert ferramentas.executar("inexistente", {}, con_v1.cursor())["erro"]


def test_sem_chave_responde_503(banco_v1, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("IA_API_KEY", raising=False)
    c = TestClient(criar_app(banco_v1))
    assert c.get("/api/perguntar/status").json() == {"configurada": False, "modelo": None}
    r = c.post("/api/perguntar", json={"pergunta": "Quantas candidaturas há?"})
    assert r.status_code == 503 and "NVIDIA_API_KEY" in r.text
    # recusa funciona mesmo sem chave (não precisa do modelo)
    assert c.post("/api/perguntar", json={"pergunta": "Em quem devo votar?"}).json()["recusada"] is True


def test_cliente_http_formato_openai(monkeypatch):
    capturado = {}

    def falso_post(url, headers, json, timeout):
        capturado.update(url=url, headers=headers, corpo=json)
        return httpx.Response(200, json={"choices": [{"message": {"content": "oi", "tool_calls": None}}]})

    monkeypatch.setattr(httpx, "post", falso_post)
    c = ClienteOpenAICompativel("chave-x", "https://integrate.api.nvidia.com/v1/", "meta/llama-3.3-70b-instruct")
    msg = c.completar([{"role": "user", "content": "oi"}], ferramentas.DEFINICOES)
    assert msg["content"] == "oi"
    assert capturado["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert capturado["headers"]["Authorization"] == "Bearer chave-x"
    assert capturado["corpo"]["model"] == "meta/llama-3.3-70b-instruct"
    assert capturado["corpo"]["tools"][0]["type"] == "function"
