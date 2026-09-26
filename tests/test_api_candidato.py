"""Testes de GET /api/candidatos/{sq} e GET /api/fonte (banco sintético, carga v1)."""
import pytest

SQ = 190000000000
AUSENCIA = {"", "#NULO", "#NULO#", "#NE", "#NE#", "-1", "-3"}
SECOES_CAMPOS = ("identificacao", "perfil", "situacao")


def detalhe(cliente, sq):
    r = cliente.get(f"/api/candidatos/{sq}")
    assert r.status_code == 200, r.text
    return r.json()


def fonte(cliente, **params):
    r = cliente.get("/api/fonte", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_candidato_inexistente(cliente):
    assert cliente.get("/api/candidatos/1").status_code == 404
    assert cliente.get("/api/fonte", params={"tabela": "candidato", "sq": 1,
                                             "campo": "nm_urna"}).status_code == 404


def test_secoes(cliente):
    d = detalhe(cliente, SQ)
    for s in ("identificacao", "perfil", "situacao", "patrimonio", "redes", "historico",
              "fundamentos_indeferimento", "outros_registros_2026"):
        assert s in d
    assert d["geracao_tse"] == "26/09/2026 08:31:16"
    assert d["identificacao"]["nm_urna"]["valor"] == "FULANO 0"


def test_todo_campo_tem_fonte(cliente):
    d = detalhe(cliente, SQ)
    for secao in SECOES_CAMPOS:
        for nome, bloco in d[secao].items():
            assert bloco["natureza"] in ("DADO", "CALCULO"), nome
            assert bloco["fonte"]["arquivo"].endswith("_BRASIL.csv"), nome
            assert bloco["fonte"]["linha"] is not None, nome
            assert bloco["geracao_tse"], nome


@pytest.mark.parametrize("sq", [SQ, SQ + 5, SQ + 8, SQ + 9, SQ + 13])
def test_nenhum_nulo_vira_zero_ou_texto_inventado(cliente, sq):
    """Critério de aceite da T3: compara cada campo com o texto original do CSV do TSE."""
    d = detalhe(cliente, sq)
    for secao in SECOES_CAMPOS:
        for nome, bloco in d[secao].items():
            f = fonte(cliente, tabela="candidato", sq=sq, campo=nome)
            originais = [v for r in f["registros"] for v in r["valores_originais"].values()]
            if not originais:      # campo calculado sem campo único de origem
                continue
            todos_ausentes = all((v or "").strip() in AUSENCIA for v in originais)
            if todos_ausentes:
                assert bloco["valor"] is None, (nome, originais, bloco["valor"])
            if bloco["valor"] is None:
                assert bloco["disponivel"] is False
                assert bloco["mensagem"] == "Não disponível no dataset utilizado."
                assert todos_ausentes or nome == "limite_gastos", (nome, originais)


def test_situacao_de_quem_saiu_da_urna(cliente):
    s = detalhe(cliente, SQ + 8)["situacao"]
    assert s["situacao_candidatura"]["valor"] == "RENÚNCIA"
    assert s["situacao_campo_origem"]["valor"] == "DS_SITUACAO_JULGAMENTO"
    assert s["na_urna"]["valor"] is False
    f = fonte(cliente, tabela="candidato", sq=SQ + 8, campo="situacao_candidatura")
    assert f["registros"][0]["valores_originais"] == {
        "DS_SITUACAO_CANDIDATO_TOT": "#NULO", "DS_SITUACAO_JULGAMENTO": "RENÚNCIA"}


def test_booleano_ausente(cliente):
    q = detalhe(cliente, SQ + 13)["perfil"]["quilombola"]
    assert q["valor"] is None and q["disponivel"] is False


# ---------------------------------------------------------------- patrimônio
def test_patrimonio(cliente):
    p = detalhe(cliente, SQ)["patrimonio"]
    assert p["qt_bens"]["valor"] == 2
    assert p["total_bens"]["valor"] == 351200.5
    assert p["total_bens"]["natureza"] == "CALCULO"
    assert p["mensagem"] is None
    assert p["por_tipo"]["itens"] == [{"tipo": "Apartamento", "qt": 2, "total": 351200.5}]
    assert [b["valor"] for b in p["maiores_bens"]["itens"]] == [350000.5, 1200.0]
    bem = p["bens"]["itens"][0]
    assert bem["descricao"] == 'APTO; "centro"' and bem["valor_original"] == "350000,50"
    assert bem["fonte"] == {"arquivo": "bem_candidato_2026_BRASIL.csv", "linha": 2}
    assert p["bens"]["campos"]["descricao"]["natureza"] == "DECLARACAO_CANDIDATO"


def test_sem_bens_nao_e_zero(cliente):
    p = detalhe(cliente, SQ + 9)["patrimonio"]
    assert p["declarou_bens"]["valor"] == "N"
    assert p["qt_bens"]["valor"] is None and p["total_bens"]["valor"] is None
    assert p["total_bens"]["mensagem"] == "Não disponível no dataset utilizado."
    assert "não é zero" in p["mensagem"]
    assert p["bens"]["itens"] == [] and p["por_tipo"]["itens"] == []


def test_bem_com_valor_zero_aparece(cliente):
    bens = detalhe(cliente, SQ + 11)["patrimonio"]["bens"]["itens"]
    assert [(b["valor"], b["valor_original"]) for b in bens] == [(350000.5, "350000,50"),
                                                                  (0.0, "0,00")]


# ---------------------------------------------------------------- redes, histórico, fundamentos
def test_redes(cliente):
    r = detalhe(cliente, SQ)["redes"]["itens"]
    assert r == [{"nr_ordem": 1, "url": "https://www.instagram.com/fulano0",
                  "plataforma": "Instagram",
                  "fonte": {"arquivo": "rede_social_candidato_2026_BRASIL.csv", "linha": 2}}]


def test_historico(cliente):
    h = detalhe(cliente, SQ)["historico"]
    assert h["disponivel"]["valor"] is True and h["mensagem"] is None
    assert h["qt_candidaturas_anteriores"]["valor"] == 2
    assert h["qt_vezes_eleito"]["valor"] == 1
    itens = h["linha_do_tempo"]["itens"]
    assert [i["ano_eleicao"] for i in itens] == [2026, 2022, 2018]
    assert [i["eleicao_atual"] for i in itens] == [True, False, False]
    assert [i["eleito"] for i in itens] == [False, True, False]


def test_historico_indisponivel(cliente):
    h = detalhe(cliente, SQ + 7)["historico"]
    assert h["disponivel"]["valor"] is False
    assert "não significa que a pessoa nunca tenha concorrido" in h["mensagem"]
    assert h["qt_candidaturas_anteriores"]["valor"] is None
    assert h["qt_candidaturas_anteriores"]["mensagem"] == "Não disponível no dataset utilizado."
    assert h["linha_do_tempo"]["itens"] == []


def test_historico_sem_candidatura_anterior(cliente):
    h = detalhe(cliente, SQ + 10)["historico"]
    assert h["disponivel"]["valor"] is True
    assert h["qt_candidaturas_anteriores"]["valor"] == 0
    assert h["ultimo_cargo_eleito"]["valor"] is None


def test_fundamentos_indeferimento(cliente):
    f = detalhe(cliente, SQ + 5)["fundamentos_indeferimento"]
    assert "não cassações" in f["descricao"]
    assert f["itens"][0]["motivo"] == "Ausência de quitação eleitoral (Lei 9.504/97)"
    vazio = detalhe(cliente, SQ)["fundamentos_indeferimento"]
    assert vazio["itens"] == [] and vazio["mensagem"]


def test_outros_registros_sem_pessoa_id(cliente):
    r = cliente.get(f"/api/candidatos/{SQ + 1}")
    assert "pessoa_id" not in r.text
    outros = r.json()["outros_registros_2026"]["itens"]
    assert [o["sq_candidato"] for o in outros] == [SQ, SQ + 2]
    assert detalhe(cliente, SQ + 3)["outros_registros_2026"]["itens"] == []


# ---------------------------------------------------------------- /api/fonte
def test_fonte_campo_simples(cliente):
    f = fonte(cliente, tabela="candidato", sq=SQ, campo="nm_urna")
    assert f["natureza"] == "DADO" and f["campo_tse"] == "NM_URNA_CANDIDATO"
    assert f["registros"] == [{"arquivo": "consulta_cand_2026_BRASIL.csv", "linha": 2,
                               "valores_originais": {"NM_URNA_CANDIDATO": "FULANO 0"}}]
    assert f["geracao_tse"] == "26/09/2026 08:31:16"


def test_fonte_calculo_lista_linhas_usadas(cliente):
    f = fonte(cliente, tabela="candidato", sq=SQ, campo="total_bens")
    assert f["natureza"] == "CALCULO"
    assert [r["valores_originais"]["VR_BEM_CANDIDATO"] for r in f["registros"]] == [
        "350000,50", "1200.00"]


def test_fonte_item_de_lista(cliente):
    f = fonte(cliente, tabela="bem", sq=SQ, campo="valor", nr_ordem=2)
    assert f["registros"] == [{"arquivo": "bem_candidato_2026_BRASIL.csv", "linha": 3,
                               "valores_originais": {"VR_BEM_CANDIDATO": "1200.00"}}]
    h = fonte(cliente, tabela="historico", sq=SQ, campo="resultado")
    assert len(h["registros"]) == 3


def test_fonte_sem_registro(cliente):
    f = fonte(cliente, tabela="bem", sq=SQ + 9, campo="valor")
    assert f["registros"] == [] and f["mensagem"] == "Não disponível no dataset utilizado."


def test_fonte_parametros_invalidos(cliente):
    base = {"sq": SQ}
    assert cliente.get("/api/fonte", params={**base, "tabela": "carga",
                                             "campo": "x"}).status_code == 422
    assert cliente.get("/api/fonte", params={**base, "tabela": "candidato",
                                             "campo": "pessoa_id"}).status_code == 422
    assert cliente.get("/api/fonte", params={**base, "tabela": "bem",
                                             "campo": '"; DROP TABLE bem; --'}).status_code == 422
