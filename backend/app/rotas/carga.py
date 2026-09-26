"""Informações da carga atual (GET /api/carga) — usadas no rodapé e no painel inicial."""
from fastapi import APIRouter, Depends

from ..db import consultar
from ..dependencias import cursor
from ..metadados import DATASET

router = APIRouter(prefix="/api", tags=["carga"])


@router.get("/carga")
def carga(cur=Depends(cursor)):
    atual = consultar(cur, """SELECT carga_id, geracao_tse, executada_em FROM carga
                              ORDER BY carga_id DESC LIMIT 1""")
    if not atual:
        return {"carga_id": None, "geracao_tse": None, "mensagem": "Nenhuma carga no banco."}
    a = atual[0]
    return {
        "natureza": "DADO",
        "dataset": DATASET,
        "carga_id": a["carga_id"],
        "geracao_tse": a["geracao_tse"],
        "carregada_em": a["executada_em"],
        "qt_cargas": consultar(cur, "SELECT count(*) AS n FROM carga")[0]["n"],
        "qt_candidaturas": consultar(cur, "SELECT count(*) AS n FROM candidato")[0]["n"],
    }
