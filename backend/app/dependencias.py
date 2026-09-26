"""Dependências FastAPI compartilhadas pelas rotas."""
from fastapi import HTTPException, Request


def cursor(request: Request):
    try:
        cur = request.app.state.banco.cursor()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    try:
        yield cur
    finally:
        cur.close()
