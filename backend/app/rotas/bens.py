"""Mapa de categorias de bens (GET /api/categorias-bens) — o "link para o mapa" da T4."""
from fastapi import APIRouter, Depends

from ..db import carga_atual, consultar
from ..dependencias import cursor
from ..metadados import BEM, DATASET

router = APIRouter(prefix="/api", tags=["bens"])


@router.get("/categorias-bens")
def categorias_bens(cur=Depends(cursor)):
    """Mapa tipo de bem -> categoria, com quantos bens da carga atual têm cada tipo."""
    mapa = consultar(cur, """
        SELECT m.categoria, m.tipo, m.observacao, count(b.tipo) AS qt_bens,
               m.fonte_arquivo, m.fonte_linha
        FROM categoria_bem m
        LEFT JOIN bem b ON lower(trim(b.tipo)) = lower(trim(m.tipo))
        GROUP BY ALL ORDER BY m.categoria, m.tipo""")
    fora = consultar(cur, """
        SELECT tipo, count(*) AS qt_bens FROM bem WHERE categoria IS NULL
        GROUP BY tipo ORDER BY tipo""")
    return {
        "natureza": "CALCULO",
        "descricao": "Agrupamento dos tipos de bem do TSE em categorias, definido no arquivo "
                     "versionado ingestao/categorias_bens.csv. O tipo original (DADO) é sempre "
                     "mantido; a categoria é um cálculo documentado. O agrupamento segue a lógica "
                     "dos grupos de bens da declaração de imposto de renda.",
        "geracao_tse": carga_atual(cur)["geracao_tse"],
        "fonte": {"dataset": DATASET, "arquivo": BEM, "campo": "DS_TIPO_BEM_CANDIDATO",
                  "mapa": "ingestao/categorias_bens.csv"},
        "categorias": sorted({m["categoria"] for m in mapa}),
        "mapa": mapa,
        "tipos_fora_do_mapa": fora,
    }
