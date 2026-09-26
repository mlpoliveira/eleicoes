"""
Qualidade dos dados (GET /api/qualidade), cargas (GET /api/cargas) e alterações entre cargas
(GET /api/alteracoes) — T9.

A tabela `qualidade` guarda, por carga, contagens de verificações feitas na ingestão: problemas
são medidos, nunca corrigidos em silêncio (regra 6). A tabela `alteracao` guarda o que mudou em
relação à carga anterior (o TSE regera os arquivos várias vezes ao dia). Mudança de situação
(ex.: deferido -> indeferido) é mostrada exatamente como o TSE registra, sem juízo (regra 7).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import consultar
from ..dependencias import cursor
from ..metadados import DATASET

router = APIRouter(prefix="/api", tags=["qualidade"])

# O que cada verificação significa (chave = início do nome gravado na ingestão)
EXPLICACOES = {
    "candidatos": "Total de registros de candidatura na carga.",
    "linhas do histórico que repetem": "O arquivo de histórico traz uma linha por turno; candidaturas "
        "com 2º turno aparecem duas vezes. As contagens de candidaturas anteriores contam uma vez.",
    "tipos de bem sem categoria": "Tipos de bem que não estão no mapa ingestao/categorias_bens.csv; "
        "ficam sem categoria (não são jogados em 'Outros').",
    "bens sem categoria": "Bens cujo tipo não está no mapa de categorias.",
    "candidatos sem registro no complementar": "Candidaturas sem linha no arquivo "
        "consulta_cand_complementar (situação, idade na posse e outros campos ficam não disponíveis).",
    "candidatos sem situação": "Candidaturas sem situação em DS_SITUACAO_CANDIDATO_TOT nem em "
        "DS_SITUACAO_JULGAMENTO.",
    "situação obtida de DS_SITUACAO_JULGAMENTO": "Candidaturas fora da urna (renúncia, indeferimento, "
        "cancelamento...) têm DS_SITUACAO_CANDIDATO_TOT nulo; a situação vem de DS_SITUACAO_JULGAMENTO.",
    "pessoas com mais de um registro": "Pessoas com mais de um registro de candidatura em 2026 "
        "(ligadas por identificador interno derivado do CPF, que não é armazenado).",
    "bens de candidato inexistente": "Bens cujo sq_candidato não está no arquivo de candidatos.",
    "bens com valor ilegível": "Valores de bens que não puderam ser lidos como número; o texto "
        "original fica em valor_original.",
    "bens com valor zero": "Bens declarados com valor 0,00 no arquivo (mantidos como declarados).",
    "declarou bens = S mas sem bens": "Candidaturas com ST_DECLARAR_BENS = S e nenhum bem no arquivo "
        "de bens.",
    "declarou bens = N mas tem bens": "Candidaturas com ST_DECLARAR_BENS = N e bens no arquivo de bens.",
    "redes sociais de candidato inexistente": "Endereços de redes cujo sq_candidato não está no "
        "arquivo de candidatos.",
    "candidatos ausentes do arquivo de histórico": "Candidaturas que não aparecem no arquivo de "
        "histórico: histórico não disponível — não significa que a pessoa nunca concorreu.",
    "data de nascimento ilegível": "Datas de nascimento ausentes ou fora do formato dd/mm/aaaa.",
    "consulta_cand: pessoas_com_mais_de_um_registro": "Mesma medida, calculada na leitura do CSV "
        "(antes de montar as tabelas).",
}

CAMPOS_ALTERACAO = {
    "candidato": "Registro novo ou removido",
    "situacao_candidatura": "Situação da candidatura",
    "situacao_julgamento": "Situação do julgamento",
    "na_urna": "Na urna",
    "total_bens": "Patrimônio declarado (soma dos bens)",
    "qt_redes": "Quantidade de endereços de redes sociais",
    "resultado": "Resultado",
    "nm_urna": "Nome de urna",
}


def _explicar(verificacao: str) -> str | None:
    for chave in sorted(EXPLICACOES, key=len, reverse=True):
        if verificacao.startswith(chave):
            return EXPLICACOES[chave]
    return None


def _cargas(cur) -> list[dict]:
    return consultar(cur, """SELECT carga_id, geracao_tse, executada_em AS carregada_em, arquivos
                             FROM carga ORDER BY carga_id DESC""")


@router.get("/cargas")
def cargas(cur=Depends(cursor)):
    """Cargas registradas (versões da base), da mais recente para a mais antiga."""
    return {"natureza": "DADO", "dataset": DATASET, "itens": _cargas(cur)}


@router.get("/qualidade")
def qualidade(carga_id: int | None = None, cur=Depends(cursor)):
    """Verificações de qualidade de uma carga (padrão: a atual), com o valor da carga anterior."""
    todas = _cargas(cur)
    if not todas:
        raise HTTPException(404, "Nenhuma carga no banco.")
    ids = [c["carga_id"] for c in todas]
    atual = carga_id if carga_id is not None else ids[0]
    if atual not in ids:
        raise HTTPException(404, f"Carga {atual} não encontrada.")
    anterior = next((i for i in ids if i < atual), None)
    linhas = consultar(cur, """
        SELECT q.verificacao, q.quantidade, a.quantidade AS quantidade_anterior
        FROM qualidade q
        LEFT JOIN qualidade a ON a.verificacao = q.verificacao AND a.carga_id = ?
        WHERE q.carga_id = ? ORDER BY q.rowid""", [anterior, atual])
    for l in linhas:
        l["explicacao"] = _explicar(l["verificacao"])
        l["variacao"] = (None if l["quantidade_anterior"] is None
                         else l["quantidade"] - l["quantidade_anterior"])
    info = next(c for c in todas if c["carga_id"] == atual)
    return {
        "natureza": "CALCULO",
        "descricao": "Contagens feitas na ingestão para medir problemas e particularidades dos "
                     "arquivos do TSE. Nada é corrigido em silêncio: o que foi transformado está "
                     "documentado no código da ingestão e medido aqui.",
        "dataset": DATASET,
        "carga": info,
        "carga_anterior": next((c for c in todas if c["carga_id"] == anterior), None),
        "verificacoes": linhas,
    }


@router.get("/alteracoes")
def alteracoes(
    carga_id: int | None = Query(None, description="Carga (padrão: a atual); compara com a anterior"),
    campo: str | None = Query(None, description=f"Um de: {', '.join(CAMPOS_ALTERACAO)}"),
    uf: str | None = None,
    cd_cargo: int | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(100, ge=1, le=500),
    cur=Depends(cursor),
):
    """O que mudou na carga em relação à carga anterior (situação, na urna, bens, redes...)."""
    todas = _cargas(cur)
    if not todas:
        raise HTTPException(404, "Nenhuma carga no banco.")
    ids = [c["carga_id"] for c in todas]
    atual = carga_id if carga_id is not None else ids[0]
    if atual not in ids:
        raise HTTPException(404, f"Carga {atual} não encontrada.")
    if campo is not None and campo not in CAMPOS_ALTERACAO:
        raise HTTPException(422, f"Campo inválido: {campo}. Use: {', '.join(CAMPOS_ALTERACAO)}")
    anterior = next((i for i in ids if i < atual), None)
    base = {
        "natureza": "CALCULO",
        "descricao": "Comparação campo a campo entre duas gerações dos arquivos do TSE. Os valores "
                     "'antes' e 'depois' são os registrados pelo TSE em cada geração.",
        "dataset": DATASET,
        "carga": next(c for c in todas if c["carga_id"] == atual),
        "carga_anterior": next((c for c in todas if c["carga_id"] == anterior), None),
        "campos": CAMPOS_ALTERACAO,
    }
    if anterior is None:
        return {**base, "total": 0, "resumo": [], "transicoes": [], "itens": [],
                "mensagem": "Esta é a primeira carga do banco: não há carga anterior para comparar."}

    # candidato removido não está mais em `candidato`: dados vêm do snapshot da carga anterior
    where, params = ["a.carga_id = ?"], [atual]
    if campo:
        where.append("a.campo = ?"); params.append(campo)
    if uf:
        where.append("coalesce(c.sg_uf, r.sg_uf) = ?"); params.append(uf.upper())
    if cd_cargo is not None:
        where.append("coalesce(c.cd_cargo, r.cd_cargo) = ?"); params.append(cd_cargo)
    fonte = f"""
        FROM alteracao a
        LEFT JOIN candidato c ON c.sq_candidato = a.sq_candidato
        LEFT JOIN (SELECT SQ_CANDIDATO::BIGINT AS sq_candidato, SG_UF AS sg_uf,
                          CD_CARGO::INT AS cd_cargo, DS_CARGO AS ds_cargo, SG_PARTIDO AS sg_partido
                   FROM raw_consulta_cand WHERE _carga_id = {int(anterior)}) r
               ON r.sq_candidato = a.sq_candidato
        LEFT JOIN snapshot_candidato s ON s.sq_candidato = a.sq_candidato AND s.carga_id = {int(anterior)}
        WHERE {' AND '.join(where)}"""
    total = consultar(cur, f"SELECT count(*) AS n {fonte}", params)[0]["n"]
    resumo = consultar(cur, f"""SELECT a.campo, count(*) AS n {fonte}
                                GROUP BY 1 ORDER BY 1""", params)
    transicoes = consultar(cur, f"""
        SELECT a.campo, a.antes, a.depois, count(*) AS n {fonte}
          AND a.campo IN ('situacao_candidatura', 'situacao_julgamento', 'na_urna', 'candidato')
        GROUP BY ALL ORDER BY a.campo, a.antes NULLS FIRST, a.depois NULLS FIRST""", params)
    itens = consultar(cur, f"""
        SELECT a.sq_candidato, a.campo, a.antes, a.depois,
               coalesce(c.nm_urna, s.nm_urna) AS nm_urna,
               coalesce(c.ds_cargo, r.ds_cargo) AS ds_cargo, coalesce(c.cd_cargo, r.cd_cargo) AS cd_cargo,
               coalesce(c.sg_uf, r.sg_uf) AS sg_uf, coalesce(c.sg_partido, r.sg_partido) AS sg_partido,
               c.sq_candidato IS NOT NULL AS na_carga_atual
        {fonte}
        ORDER BY a.campo, nm_urna, a.sq_candidato
        LIMIT ? OFFSET ?""", params + [por_pagina, (pagina - 1) * por_pagina])
    for r in resumo:
        r["rotulo"] = CAMPOS_ALTERACAO.get(r["campo"], r["campo"])
    return {**base, "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "resumo": resumo, "transicoes": transicoes, "itens": itens, "mensagem": None}
