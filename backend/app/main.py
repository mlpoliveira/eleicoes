"""
API do Laboratório de Análise Eleitoral — Eleições 2026.

Rodar (na raiz do repositório):
    ELEICOES_DB=eleicoes.duckdb uvicorn app.main:app --app-dir backend --reload
Variáveis (ELEICOES_DB, NVIDIA_API_KEY, IA_MODELO...) podem ficar no arquivo .env da raiz
(ver .env.exemplo); o terminal tem prioridade.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .config import carregar_env
from .db import RAIZ, Banco, caminho_banco
from .ia.cliente import ClienteIA, cliente_do_ambiente
from .rotas import bens, candidato, candidatos, carga, comparar, estatisticas, exportar, perguntar, qualidade


def criar_app(banco: Path | None = None, ia_cliente: ClienteIA | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI):
        yield
        app.state.banco.fechar()

    app = FastAPI(title="Laboratório de Análise Eleitoral — Eleições 2026",
                  description="Dados abertos do TSE. A API expõe dados e cálculos; "
                              "não faz recomendação de voto nem classificação de candidatos.",
                  lifespan=ciclo)
    app.state.banco = Banco(banco or caminho_banco())
    app.state.ia_cliente = ia_cliente if ia_cliente is not None else cliente_do_ambiente()
    app.include_router(estatisticas.router)
    app.include_router(candidatos.router)
    app.include_router(candidato.router)
    app.include_router(bens.router)
    app.include_router(comparar.router)
    app.include_router(carga.router)
    app.include_router(qualidade.router)
    app.include_router(exportar.router)
    app.include_router(perguntar.router)
    return app


# A aplicação servida pelo uvicorn lê o .env da raiz antes de criar a conexão e o cliente de IA.
carregar_env(RAIZ / ".env")
app = criar_app()
