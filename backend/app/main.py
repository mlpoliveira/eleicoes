"""
API do Laboratório de Análise Eleitoral — Eleições 2026.

Rodar (na raiz do repositório):
    ELEICOES_DB=eleicoes.duckdb uvicorn app.main:app --app-dir backend --reload
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .db import Banco, caminho_banco
from .rotas import bens, candidato, candidatos, carga, comparar, estatisticas


def criar_app(banco: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI):
        yield
        app.state.banco.fechar()

    app = FastAPI(title="Laboratório de Análise Eleitoral — Eleições 2026",
                  description="Dados abertos do TSE. A API expõe dados e cálculos; "
                              "não faz recomendação de voto nem classificação de candidatos.",
                  lifespan=ciclo)
    app.state.banco = Banco(banco or caminho_banco())
    app.include_router(estatisticas.router)
    app.include_router(candidatos.router)
    app.include_router(candidato.router)
    app.include_router(bens.router)
    app.include_router(comparar.router)
    app.include_router(carga.router)
    return app


app = criar_app()
