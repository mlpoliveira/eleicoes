"""
Busca de candidatos (GET /api/candidatos) e valores para filtros (GET /api/filtros).

Busca por nome (completo, de urna ou social) ou número:
  - nome e termo são normalizados: minúsculas, sem acentos, pontuação vira espaço;
  - correspondência "exata": todas as palavras do termo aparecem no nome (como trecho);
  - correspondência "aproximada": cada palavra do termo aparece como trecho OU tem similaridade
    Jaro-Winkler >= LIMIAR_SIMILARIDADE com alguma palavra do nome (tolera erro de digitação);
  - número: termo só com dígitos compara com nr_candidato e sq_candidato;
  - resultado exato vem antes do aproximado; dentro de cada grupo vale a ordenação escolhida.
A ordenação é sempre por uma coluna escolhida pelo usuário — não existe ordenação "por relevância
do candidato", só pelo tipo de correspondência com o termo buscado.
"""
import re
import unicodedata
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import carga_atual, consultar
from ..dependencias import cursor
from ..metadados import DATASET, bloco_campos
from ..universo import Universo, universo_dos_parametros

router = APIRouter(prefix="/api", tags=["candidatos"])

LIMIAR_SIMILARIDADE = 0.90   # Jaro-Winkler; abaixo disso a palavra não conta como aproximada
MIN_LETRAS_APROXIMADA = 4    # palavras curtas ("da", "de", "jr") só casam como trecho
MAX_PALAVRAS = 8

# colunas devolvidas na busca (pessoa_id NUNCA sai da API)
COLUNAS = [
    "sq_candidato", "nr_candidato", "nm_candidato", "nm_urna", "nm_social", "sg_uf",
    "cd_cargo", "ds_cargo", "sg_partido", "nm_partido", "nm_federacao",
    "situacao_candidatura", "situacao_campo_origem", "na_urna", "genero", "cor_raca",
    "grau_instrucao", "idade_na_posse", "qt_bens", "total_bens", "historico_disponivel",
    "qt_outros_registros_2026", "fonte_arquivo", "fonte_linha",
    "fonte_arquivo_compl", "fonte_linha_compl",
]
ORDENAVEIS = [
    "nm_urna", "nm_candidato", "nr_candidato", "sg_uf", "cd_cargo", "sg_partido",
    "nm_federacao", "situacao_candidatura", "genero", "cor_raca", "grau_instrucao",
    "idade_na_posse", "qt_bens", "total_bens",
]

# expressão SQL que normaliza um texto do mesmo jeito que normalizar() faz em Python
NORMALIZA_SQL = "trim(regexp_replace(strip_accents(lower({})), '[^a-z0-9]+', ' ', 'g'))"


def eh_numero(termo: str) -> bool:
    return termo.isascii() and termo.isdigit()


def normalizar(texto: str) -> str:
    sem_acento = "".join(ch for ch in unicodedata.normalize("NFKD", texto.lower())
                         if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


@router.get("/candidatos")
def buscar_candidatos(
    q: str | None = Query(None, max_length=120,
                          description="Nome completo, nome de urna, nome social ou número"),
    universo: Universo = Depends(universo_dos_parametros),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
    ordenar_por: Literal[tuple(ORDENAVEIS)] = "nm_urna",
    ordem: Literal["asc", "desc"] = "asc",
    cur=Depends(cursor),
):
    where, params = universo.where()

    # ---- termo de busca
    # params_select: usados na expressão de correspondência (SELECT); params: usados no WHERE
    termo = (q or "").strip()
    correspondencia_sql, params_select = "NULL", []
    if eh_numero(termo):
        where.append("(nr_candidato = ? OR sq_candidato::VARCHAR = ?)")
        params.extend([termo, termo])
        correspondencia_sql = "'numero'"
    elif termo:
        palavras = normalizar(termo).split()[:MAX_PALAVRAS]
        if not palavras:
            raise HTTPException(422, "O termo de busca não contém letras nem números.")
        exatas, aproximadas = [], []
        for p in palavras:
            exatas.append("contains(_busca, ?)")
            params_select.append(p)
            if len(p) >= MIN_LETRAS_APROXIMADA:
                aproximadas.append(
                    "(contains(_busca, ?) OR list_max(list_transform(_palavras, "
                    "lambda x: jaro_winkler_similarity(x, ?))) >= ?)")
                params.extend([p, p, LIMIAR_SIMILARIDADE])
            else:
                aproximadas.append("contains(_busca, ?)")
                params.append(p)
        correspondencia_sql = f"CASE WHEN {' AND '.join(exatas)} THEN 'exata' ELSE 'aproximada' END"
        where.append(f"({' AND '.join(aproximadas)})")

    nome_normalizado = NORMALIZA_SQL.format("concat_ws(' ', nm_candidato, nm_urna, nm_social)")
    sql = f"""
        WITH base AS (
            SELECT {', '.join(COLUNAS)},
                   {nome_normalizado} AS _busca,
                   string_split({nome_normalizado}, ' ') AS _palavras
            FROM v_candidato
        ),
        achados AS (
            SELECT *, {correspondencia_sql} AS correspondencia
            FROM base
            {'WHERE ' + ' AND '.join(where) if where else ''}
        )
        SELECT {', '.join(COLUNAS)}, correspondencia, count(*) OVER () AS _total
        FROM achados
        ORDER BY CASE correspondencia WHEN 'aproximada' THEN 1 ELSE 0 END,
                 {ordenar_por} {ordem.upper()} NULLS LAST, nm_urna, sq_candidato
        LIMIT ? OFFSET ?"""
    todos = params_select + params + [por_pagina, (pagina - 1) * por_pagina]
    itens = consultar(cur, sql, todos)

    total = itens[0]["_total"] if itens else 0
    _anexar_outros_registros(cur, itens)
    for it in itens:
        del it["_total"]
        it["possui_outro_registro_2026"] = (it["qt_outros_registros_2026"] or 0) > 0

    geracao = carga_atual(cur)["geracao_tse"]
    return {
        "natureza": "DADO",
        "geracao_tse": geracao,
        "fonte": {"dataset": DATASET, "arquivo": None, "linha": None, "campo": None,
                  "observacao": "Arquivo e linha de cada registro estão em fonte_arquivo/"
                                "fonte_linha (consulta_cand) e fonte_arquivo_compl/"
                                "fonte_linha_compl (consulta_cand_complementar)."},
        "campos": bloco_campos(COLUNAS + ["outros_registros_2026"], geracao),
        "consulta": {"q": q, "ordenar_por": ordenar_por, "ordem": ordem,
                     "criterio_busca": _criterio(termo)},
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "itens": itens,
    }


def _criterio(termo: str) -> str | None:
    if not termo:
        return None
    if eh_numero(termo):
        return "Número do candidato (nr_candidato) ou sequencial (sq_candidato) igual ao termo."
    return ("Nome completo, de urna ou social contendo todas as palavras do termo, sem diferenciar "
            "maiúsculas e acentos (correspondência 'exata'); depois, nomes em que cada palavra "
            f"com {MIN_LETRAS_APROXIMADA}+ letras tem similaridade Jaro-Winkler >= "
            f"{LIMIAR_SIMILARIDADE:.2f} com alguma palavra do nome (correspondência 'aproximada').")


def _anexar_outros_registros(cur, itens):
    """Lista os sq_candidato dos outros registros da mesma pessoa, sem expor pessoa_id."""
    com_outros = [it["sq_candidato"] for it in itens if it["qt_outros_registros_2026"]]
    mapa = {}
    if com_outros:
        linhas = consultar(cur, f"""
            SELECT c.sq_candidato, list(o.sq_candidato ORDER BY o.sq_candidato) AS outros
            FROM candidato c JOIN candidato o
              ON o.pessoa_id = c.pessoa_id AND o.sq_candidato <> c.sq_candidato
            WHERE c.sq_candidato IN ({', '.join('?' * len(com_outros))})
            GROUP BY 1""", com_outros)
        mapa = {l["sq_candidato"]: l["outros"] for l in linhas}
    for it in itens:
        it["outros_registros_2026"] = mapa.get(it["sq_candidato"], [])


# ---------------------------------------------------------------- filtros
FILTROS = {  # parâmetro da busca -> coluna
    "uf": "sg_uf", "sg_partido": "sg_partido", "federacao": "nm_federacao",
    "situacao": "situacao_candidatura", "genero": "genero", "cor_raca": "cor_raca",
    "grau_instrucao": "grau_instrucao",
}


@router.get("/filtros")
def valores_filtros(cur=Depends(cursor)):
    """Valores distintos (em ordem alfabética) e contagem de candidatos por valor."""
    geracao = carga_atual(cur)["geracao_tse"]
    saida = {}
    for param, col in FILTROS.items():
        extra = ", min(nm_partido) AS rotulo" if col == "sg_partido" else ""
        valores = consultar(cur, f"""
            SELECT {col} AS valor{extra}, count(*) AS n FROM candidato
            WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY {col}""")
        nao_disp = consultar(cur, f"SELECT count(*) AS n FROM candidato WHERE {col} IS NULL")[0]["n"]
        saida[param] = {"coluna": col, "valores": valores, "n_nao_disponivel": nao_disp}
    # cargo: DS_CARGO muda de grafia entre arquivos — sempre agrupar por cd_cargo
    saida["cd_cargo"] = {
        "coluna": "cd_cargo",
        "valores": consultar(cur, """
            SELECT cd_cargo AS valor, min(ds_cargo) AS rotulo, count(*) AS n
            FROM candidato GROUP BY cd_cargo ORDER BY cd_cargo"""),
        "n_nao_disponivel": 0,
    }
    saida["na_urna"] = {
        "coluna": "na_urna",
        "valores": consultar(cur, """
            SELECT na_urna AS valor, count(*) AS n FROM candidato
            WHERE na_urna IS NOT NULL GROUP BY 1 ORDER BY 1 DESC"""),
        "n_nao_disponivel": consultar(
            cur, "SELECT count(*) AS n FROM candidato WHERE na_urna IS NULL")[0]["n"],
    }
    idade = consultar(cur, """SELECT min(idade_na_posse) AS min, max(idade_na_posse) AS max,
                                     count(*) FILTER (WHERE idade_na_posse IS NULL) AS n_nd
                              FROM candidato""")[0]
    saida["idade"] = {"coluna": "idade_na_posse", "min": idade["min"], "max": idade["max"],
                      "n_nao_disponivel": idade["n_nd"]}
    return {
        "natureza": "CALCULO",
        "descricao": "Valores distintos de cada campo e número de candidatos com cada valor.",
        "geracao_tse": geracao,
        "universo": {"descricao": "Todos os registros de candidatura 2026 da carga atual",
                     "n": consultar(cur, "SELECT count(*) AS n FROM candidato")[0]["n"]},
        "fonte": {"dataset": DATASET, "arquivo": "consulta_cand_2026_BRASIL.csv | "
                  "consulta_cand_complementar_2026_BRASIL.csv", "linha": None, "campo": None},
        "filtros": saida,
    }
