"""Pergunte aos dados (POST /api/perguntar) — T10. Ver backend/app/ia/."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..dependencias import cursor
from ..ia.agente import perguntar
from ..ia.cliente import ErroIA

router = APIRouter(prefix="/api", tags=["ia"])


class Pergunta(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=500)


@router.get("/perguntar/status")
def status(request: Request):
    cliente = request.app.state.ia_cliente
    return {"configurada": cliente is not None, "modelo": getattr(cliente, "modelo", None)}


@router.post("/perguntar")
def perguntar_rota(corpo: Pergunta, request: Request, cur=Depends(cursor)):
    cliente = request.app.state.ia_cliente
    try:
        return perguntar(corpo.pergunta.strip(), cliente, cur)
    except RuntimeError:
        raise HTTPException(503, "IA não configurada: defina a variável de ambiente NVIDIA_API_KEY "
                                 "(e opcionalmente IA_MODELO e IA_BASE_URL) e reinicie a API.")
    except ErroIA as e:
        raise HTTPException(502, str(e))
