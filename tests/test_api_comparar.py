"""Testes de GET /api/comparar (bancos sintéticos v1 e v3)."""
import re

SQ = 190000000000

# critério de aceite da T6: nenhuma frase conclusiva ou avaliativa
TERMOS_PROIBIDOS = re.compile(
    r"\b(melhor|pior|ideal|preparad|experiente|inexperiente|qualificad|competente|honest|"
    r"confi[aá]vel|ric[oa]s?|pobre|forte|fraco|vantagem|desvantagem|recomend|vot[ea] em|"
    r"supera|superior|inferior|ranking|score|nota|destaca|lidera)\w*", re.IGNORECASE)


def comparar(cliente, *sqs):
    r = cliente.get("/api/comparar", params=[("sq", str(s)) for s in sqs])
    assert r.status_code == 200, r.text
    return r.json()


def textos(obj):
    """Todas as strings de uma resposta (para o teste de neutralidade)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from textos(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from textos(v)


# ---------------------------------------------------------------- validação
def test_quantidade_de_candidatos(cliente):
    assert cliente.get("/api/comparar", params={"sq": str(SQ)}).status_code == 422
    seis = ",".join(str(SQ + i) for i in range(6))
    assert cliente.get("/api/comparar", params={"sq": seis}).status_code == 422
    assert cliente.get("/api/comparar", params={"sq": f"{SQ},{SQ}"}).status_code == 422
    assert cliente.get("/api/comparar", params={"sq": "abc,1"}).status_code == 422


def test_candidato_inexistente(cliente):
    r = cliente.get("/api/comparar", params={"sq": f"{SQ},1"})
    assert r.status_code == 404 and "[1]" in r.text


def test_formatos_de_parametro(cliente):
    a = cliente.get("/api/comparar", params={"sq": f"{SQ},{SQ + 3}"}).json()
    b = comparar(cliente, SQ, SQ + 3)
    assert a["candidatos"] == b["candidatos"]


# ---------------------------------------------------------------- tabela lado a lado
def test_ordem_e_tabela(cliente):
    r = comparar(cliente, SQ + 4, SQ + 3)
    assert [c["sq_candidato"] for c in r["candidatos"]] == [SQ + 4, SQ + 3]   # ordem pedida
    secoes = {l["secao"] for l in r["tabela"]}
    assert secoes == {"eleitoral", "perfil", "patrimonio", "historico", "redes"}
    idade = next(l for l in r["tabela"] if l["campo"] == "idade_na_posse")
    assert [v["valor"] for v in idade["valores"]] == [34, 33] and idade["iguais"] is False
    assert idade["valores"][0]["fonte"]["arquivo"] == "consulta_cand_complementar_2026_BRASIL.csv"
    partido = next(l for l in r["tabela"] if l["campo"] == "sg_partido")
    assert partido["iguais"] is True
    redes = next(l for l in r["tabela"] if l["campo"] == "redes")
    assert redes["valores"][0]["valor"] == [{"plataforma": "Instagram",
                                             "url": "https://www.instagram.com/fulano4"}]


def test_ausencias_na_tabela(cliente):
    r = comparar(cliente, SQ, SQ + 9)
    total = next(l for l in r["tabela"] if l["campo"] == "total_bens")
    assert total["valores"][1]["valor"] is None
    assert total["valores"][1]["mensagem"] == "Não disponível no dataset utilizado."


def test_pessoa_id_nunca_exposto(cliente):
    r = cliente.get("/api/comparar", params={"sq": f"{SQ},{SQ + 1}"})
    assert "pessoa_id" not in r.text


# ---------------------------------------------------------------- verificações e alertas
def test_mesmo_universo(cliente):
    r = comparar(cliente, SQ + 3, SQ + 4)
    assert r["verificacoes"] == {"mesmo_cargo": True, "mesma_uf": True, "mesmo_partido": True,
                                 "historico_disponivel_para_todos": True,
                                 "bens_disponiveis_para_todos": True}
    assert r["alertas"] == []


def test_universos_diferentes(cliente_v3):
    r = comparar(cliente_v3, SQ, SQ + 40, SQ + 41)
    v = r["verificacoes"]
    assert v["mesmo_cargo"] is False and v["mesma_uf"] is False
    assert ("Os candidatos pertencem a cargos/UFs diferentes. Algumas comparações estatísticas "
            "não são diretamente equivalentes.") in r["alertas"]
    so_cargo = comparar(cliente_v3, SQ, SQ + 40)
    assert so_cargo["verificacoes"]["mesma_uf"] is True
    assert any("cargos/UFs diferentes" in a for a in so_cargo["alertas"])


def test_alertas_de_ausencia(cliente):
    r = comparar(cliente, SQ + 3, SQ + 7, SQ + 9)
    assert r["verificacoes"]["historico_disponivel_para_todos"] is False
    assert r["verificacoes"]["bens_disponiveis_para_todos"] is False
    assert any("Histórico não disponível" in a and "FULANO 7" in a
               and "não significa que nunca tenham concorrido" in a for a in r["alertas"])
    assert any("FULANO 9" in a and "não é zero" in a for a in r["alertas"])


def test_mesma_pessoa(cliente):
    r = comparar(cliente, SQ, SQ + 2, SQ + 3)
    assert any(f"{SQ}, {SQ + 2} são da mesma pessoa" in a for a in r["alertas"])


# ---------------------------------------------------------------- principais diferenças
def test_diferencas_so_fatos(cliente):
    r = comparar(cliente, SQ + 3, SQ + 7, SQ + 9)
    difs = {d["campo"]: d for d in r["diferencas"]["itens"]}
    assert r["diferencas"]["titulo"] == "Principais diferenças encontradas nos dados"
    assert difs["qt_bens"]["texto"] == ("FULANO 3 declarou 2 bens; FULANO 7 declarou 2 bens; "
                                        "FULANO 9: nenhum bem no arquivo do TSE (quantidade não "
                                        "disponível).")
    assert difs["idade_na_posse"]["texto"] == (
        "FULANO 3: 33 anos na data da posse; FULANO 7: 37 anos na data da posse; "
        "FULANO 9: 39 anos na data da posse.")
    assert difs["qt_candidaturas_anteriores"]["texto"] == (
        "FULANO 3 possui 2 candidaturas anteriores identificadas; FULANO 7: histórico não "
        "disponível no dataset utilizado; FULANO 9 possui 2 candidaturas anteriores "
        "identificadas.")
    # mesmo total entre quem tem o dado: não diz que "diferem"
    assert difs["total_bens"]["texto"] == (
        "O patrimônio declarado (soma dos bens) é o mesmo entre os candidatos com o dado (valor "
        "em R$ na lista 'valores'); não disponível no dataset utilizado para: FULANO 9.")
    assert [v["valor"] for v in difs["total_bens"]["valores"]] == [351200.5, 351200.5, None]
    assert "grau_instrucao" not in difs   # igual para todos → não aparece


def test_diferenca_de_patrimonio_sem_formatar_moeda(cliente):
    r = comparar(cliente, SQ + 3, SQ + 11)
    d = next(d for d in r["diferencas"]["itens"] if d["campo"] == "total_bens")
    assert "diferem" in d["texto"] and "R$ na lista" in d["texto"]
    assert not re.search(r"R\$\s*\d", d["texto"])
    assert [v["valor"] for v in d["valores"]] == [351200.5, 350000.5]


def test_sem_diferencas(cliente):
    r = comparar(cliente, SQ + 3, SQ + 6)
    assert {d["campo"] for d in r["diferencas"]["itens"]} == {"idade_na_posse"}


def valores_da_base(obj):
    """Strings que vêm da base do TSE (campo 'valor' e identificação): são DADO, não texto gerado
    — ex.: grau de instrução "SUPERIOR COMPLETO" não é avaliação."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("valor", "nm_urna", "ds_cargo", "sg_partido", "url", "plataforma"):
                yield from textos(v)
            else:
                yield from valores_da_base(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from valores_da_base(v)


def test_neutralidade(cliente, cliente_v3):
    """Critério de aceite: nenhuma frase conclusiva ou avaliativa nos textos gerados pela API
    (os valores vindos da base são retirados antes da checagem)."""
    respostas = [comparar(cliente, SQ + 3, SQ + 7, SQ + 9, SQ + 11, SQ + 15),
                 comparar(cliente, SQ, SQ + 2, SQ + 8, SQ + 13),
                 comparar(cliente_v3, SQ, SQ + 40, SQ + 41)]
    for r in respostas:
        dados = sorted(set(valores_da_base(r)), key=len, reverse=True)
        for t in textos(r):
            if t in dados:
                continue
            for d in dados:
                t = t.replace(d, "")
            assert not TERMOS_PROIBIDOS.search(t), t
