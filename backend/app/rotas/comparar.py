"""
Comparador de 2 a 5 candidaturas (GET /api/comparar?sq=...&sq=...).

- Tabela lado a lado: perfil, eleitoral, patrimônio, histórico e redes — cada campo com natureza e
  fonte (mesmo formato da página do candidato).
- Verificações e alertas: mesmo cargo? mesma UF? mesmo partido? histórico disponível para todos?
  registros da mesma pessoa?
- "Principais diferenças encontradas nos dados": só fatos (ex.: "A declarou 12 bens; B declarou 3").
  Nenhuma frase conclui, avalia ou ordena candidatos. Valores em R$ não são formatados aqui
  (formatação de moeda só no frontend): para eles o texto diz apenas que diferem, e os valores
  vão em `valores`.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import carga_atual, consultar
from ..dependencias import cursor
from ..metadados import CAMPOS, DATASET, NAO_DISPONIVEL, campo_com_fonte
from ..universo import fmt_n

router = APIRouter(prefix="/api", tags=["comparar"])

MIN_CANDIDATOS, MAX_CANDIDATOS = 2, 5

SECOES = {
    "eleitoral": ["nr_candidato", "nm_urna", "cd_cargo", "ds_cargo", "sg_uf", "nm_ue",
                  "sg_partido", "nm_federacao", "situacao_candidatura", "situacao_campo_origem",
                  "na_urna", "limite_gastos"],
    "perfil": ["idade_na_posse", "genero", "cor_raca", "grau_instrucao", "estado_civil",
               "ocupacao", "uf_nascimento", "nacionalidade"],
    "patrimonio": ["declarou_bens", "qt_bens", "total_bens"],
    "historico": ["historico_disponivel", "qt_candidaturas_anteriores", "qt_vezes_eleito",
                  "ultimo_cargo_eleito"],
}

ALERTA_UNIVERSOS = ("Os candidatos pertencem a cargos/UFs diferentes. Algumas comparações "
                    "estatísticas não são diretamente equivalentes.")


def _ler_sqs(sq: list[str]) -> list[int]:
    """Aceita ?sq=1&sq=2 e também ?sq=1,2."""
    try:
        sqs = [int(x) for item in sq for x in item.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "sq deve conter apenas números (sq_candidato).")
    if len(set(sqs)) != len(sqs):
        raise HTTPException(422, "sq repetido na comparação.")
    if not MIN_CANDIDATOS <= len(sqs) <= MAX_CANDIDATOS:
        raise HTTPException(422, f"Informe de {MIN_CANDIDATOS} a {MAX_CANDIDATOS} candidatos "
                                 f"(recebidos: {len(sqs)}).")
    return sqs


def _nome(c: dict) -> str:
    return c["nm_urna"] or c["nm_candidato"]


def _lista_fatos(itens: list[str]) -> str:
    texto = "; ".join(itens)
    return texto[:1].upper() + texto[1:] + "."


def _diferencas(cands: list[dict], redes: dict) -> list[dict]:
    """Fatos sobre campos cujos valores diferem entre as candidaturas comparadas."""
    difs = []

    def adicionar(campo, rotulo, natureza, valores, texto):
        if len({repr(v) for v in valores}) > 1:
            difs.append({"campo": campo, "rotulo": rotulo, "natureza": natureza, "texto": texto,
                         "valores": [{"sq_candidato": c["sq_candidato"], "nm_urna": _nome(c),
                                      "valor": v} for c, v in zip(cands, valores)]})

    def txt_bens(c):
        if c["qt_bens"] is None:
            return f"{_nome(c)}: nenhum bem no arquivo do TSE (quantidade não disponível)"
        return f"{_nome(c)} declarou {fmt_n(c['qt_bens'])} " + ("bem" if c["qt_bens"] == 1 else "bens")
    adicionar("qt_bens", "Quantidade de bens declarados", "CALCULO",
              [c["qt_bens"] for c in cands], _lista_fatos([txt_bens(c) for c in cands]))

    total = [c["total_bens"] for c in cands]
    distintos = {v for v in total if v is not None}
    sem_total = [_nome(c) for c in cands if c["total_bens"] is None]
    partes = []
    if len(distintos) > 1:
        partes.append("Os valores de patrimônio declarado (soma dos bens) diferem entre os "
                      "candidatos com o dado (valores em R$ na lista 'valores')")
    elif len(distintos) == 1 and sem_total:
        partes.append("O patrimônio declarado (soma dos bens) é o mesmo entre os candidatos com "
                      "o dado (valor em R$ na lista 'valores')")
    if sem_total:
        partes.append(f"não disponível no dataset utilizado para: {', '.join(sem_total)}")
    adicionar("total_bens", "Patrimônio declarado (soma dos bens)", "CALCULO", total,
              _lista_fatos(partes) if partes else "")

    def txt_idade(c):
        if c["idade_na_posse"] is None:
            return f"{_nome(c)}: idade não disponível no dataset utilizado"
        return f"{_nome(c)}: {c['idade_na_posse']} anos na data da posse"
    adicionar("idade_na_posse", "Idade na data da posse", "DADO",
              [c["idade_na_posse"] for c in cands], _lista_fatos([txt_idade(c) for c in cands]))

    for campo, rotulo in (("grau_instrucao", "Grau de instrução declarado"),
                          ("ocupacao", "Ocupação declarada"),
                          ("situacao_candidatura", "Situação da candidatura")):
        adicionar(campo, rotulo, "DADO", [c[campo] for c in cands], _lista_fatos(
            [f"{_nome(c)}: {c[campo] if c[campo] is not None else NAO_DISPONIVEL.rstrip('.').lower()}"
             for c in cands]))

    def txt_hist(c, campo, singular, plural):
        if not c["historico_disponivel"]:
            return f"{_nome(c)}: histórico não disponível no dataset utilizado"
        v = c[campo]
        return f"{_nome(c)} possui {fmt_n(v)} {singular if v == 1 else plural}"
    adicionar("qt_candidaturas_anteriores", "Candidaturas anteriores identificadas (desde 2004)",
              "CALCULO",
              [c["qt_candidaturas_anteriores"] if c["historico_disponivel"] else None for c in cands],
              _lista_fatos([txt_hist(c, "qt_candidaturas_anteriores",
                                     "candidatura anterior identificada",
                                     "candidaturas anteriores identificadas") for c in cands]))
    adicionar("qt_vezes_eleito", "Candidaturas anteriores com resultado 'Eleito'", "CALCULO",
              [c["qt_vezes_eleito"] if c["historico_disponivel"] else None for c in cands],
              _lista_fatos([txt_hist(c, "qt_vezes_eleito",
                                     "candidatura anterior com resultado 'Eleito'",
                                     "candidaturas anteriores com resultado 'Eleito'")
                            for c in cands]))

    qt_redes = [len(redes.get(c["sq_candidato"], [])) for c in cands]
    adicionar("qt_redes", "Endereços de redes sociais/sites informados ao TSE", "CALCULO", qt_redes,
              _lista_fatos([f"{_nome(c)} informou {fmt_n(n)} "
                            + ("endereço" if n == 1 else "endereços")
                            for c, n in zip(cands, qt_redes)]))
    return difs


@router.get("/comparar")
def comparar(sq: list[str] = Query(..., description="2 a 5 sq_candidato (?sq=1&sq=2 ou ?sq=1,2)"),
             cur=Depends(cursor)):
    sqs = _ler_sqs(sq)
    regs = consultar(cur, f"""SELECT * FROM v_candidato
                              WHERE sq_candidato IN ({', '.join('?' * len(sqs))})""", sqs)
    por_sq = {r["sq_candidato"]: r for r in regs}
    faltando = [s for s in sqs if s not in por_sq]
    if faltando:
        raise HTTPException(404, f"Candidato(s) não encontrado(s) na carga atual: {faltando}")
    cands = [por_sq[s] for s in sqs]          # mantém a ordem pedida pelo usuário
    carga = carga_atual(cur)
    g = carga["geracao_tse"]

    marcadores = ", ".join("?" * len(sqs))
    redes = {}
    for r in consultar(cur, f"""SELECT sq_candidato, plataforma, url FROM rede_social
                               WHERE sq_candidato IN ({marcadores}) ORDER BY nr_ordem""", sqs):
        redes.setdefault(r["sq_candidato"], []).append({"plataforma": r["plataforma"],
                                                         "url": r["url"]})
    categorias = {}
    for r in consultar(cur, f"""SELECT sq_candidato, categoria, count(*) AS qt, sum(valor) AS total
                               FROM bem WHERE sq_candidato IN ({marcadores})
                               GROUP BY ALL ORDER BY categoria NULLS LAST""", sqs):
        categorias.setdefault(r["sq_candidato"], []).append(
            {"categoria": r["categoria"], "qt": r["qt"], "total": r["total"]})

    # ---- verificações de comparabilidade
    def todos_iguais(campo):
        return len({c[campo] for c in cands}) == 1
    pessoas = {}
    for c in cands:
        if c["pessoa_id"] is not None:
            pessoas.setdefault(c["pessoa_id"], []).append(c["sq_candidato"])
    mesma_pessoa = [grupo for grupo in pessoas.values() if len(grupo) > 1]
    sem_hist = [_nome(c) for c in cands if not c["historico_disponivel"]]
    sem_bens = [_nome(c) for c in cands if c["qt_bens"] is None]
    verificacoes = {
        "mesmo_cargo": todos_iguais("cd_cargo"),
        "mesma_uf": todos_iguais("sg_uf"),
        "mesmo_partido": todos_iguais("sg_partido"),
        "historico_disponivel_para_todos": not sem_hist,
        "bens_disponiveis_para_todos": not sem_bens,
    }
    alertas = []
    if not (verificacoes["mesmo_cargo"] and verificacoes["mesma_uf"]):
        alertas.append(ALERTA_UNIVERSOS)
    if sem_hist:
        alertas.append("Histórico não disponível no dataset utilizado para: "
                       f"{', '.join(sem_hist)}. As comparações de histórico não incluem "
                       "esse(s) registro(s) — não significa que nunca tenham concorrido.")
    if sem_bens:
        alertas.append("Nenhum bem no arquivo do TSE para: "
                       f"{', '.join(sem_bens)}. Patrimônio não disponível (não é zero).")
    for grupo in mesma_pessoa:
        alertas.append("Os registros " + ", ".join(map(str, grupo)) + " são da mesma pessoa "
                       "(mais de um registro de candidatura em 2026).")

    # ---- tabela lado a lado (linhas = campos, colunas = candidatos)
    linhas = []
    for secao, nomes in SECOES.items():
        for nome in nomes:
            natureza, arquivo, campo_tse, obs = CAMPOS[nome]
            linhas.append({"secao": secao, "campo": nome, "natureza": natureza,
                           "valores": [campo_com_fonte(nome, c, g) for c in cands],
                           "iguais": len({repr(c[nome]) for c in cands}) == 1})
    linhas.append({"secao": "patrimonio", "campo": "por_categoria", "natureza": "CALCULO",
                   "valores": [{"valor": categorias.get(c["sq_candidato"], []),
                                "natureza": "CALCULO", "mapa": "/api/categorias-bens"}
                               for c in cands]})
    linhas.append({"secao": "redes", "campo": "redes", "natureza": "DADO",
                   "valores": [{"valor": redes.get(c["sq_candidato"], []), "natureza": "DADO",
                                "fonte": {"dataset": DATASET,
                                          "arquivo": "rede_social_candidato_2026_BRASIL.csv",
                                          "campo": "DS_URL"}}
                               for c in cands]})

    return {
        "natureza": "DADO",
        "geracao_tse": g,
        "carga_id": carga["carga_id"],
        "fonte": {"dataset": DATASET, "arquivo": None, "linha": None, "campo": None,
                  "observacao": "Fonte de cada valor no bloco 'fonte' do próprio valor."},
        "candidatos": [{"sq_candidato": c["sq_candidato"], "nm_urna": _nome(c),
                        "nr_candidato": c["nr_candidato"], "ds_cargo": c["ds_cargo"],
                        "sg_uf": c["sg_uf"], "sg_partido": c["sg_partido"]} for c in cands],
        "verificacoes": verificacoes,
        "alertas": alertas,
        "tabela": linhas,
        "diferencas": {
            "titulo": "Principais diferenças encontradas nos dados",
            "descricao": "Somente campos cujos valores diferem entre os candidatos, descritos "
                         "como fatos. Nenhuma diferença indica qualidade ou preferência.",
            "itens": _diferencas(cands, redes),
        },
    }
