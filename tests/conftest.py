"""
Fixtures de teste: bancos DuckDB gerados do zero a partir de dados SINTÉTICOS
(tests/gerar_dados_sinteticos.py) + ingestao/ingestao_tse.py. Nunca usam os dados reais.

- `banco_v1`: uma carga (geração v1, 40 candidatos).
- `banco_v2`: duas cargas no mesmo banco (v1 e depois v2) — serve para testar `alteracao`.
Os scripts rodam como subprocesso, exatamente como o usuário os roda.
"""
import subprocess
import sys
from pathlib import Path

import os

import duckdb
import pytest

# Testes nunca leem o .env local (onde fica a chave real da IA) — ver backend/app/config.py
os.environ["ELEICOES_SEM_DOTENV"] = "1"

RAIZ = Path(__file__).resolve().parent.parent
GERADOR = RAIZ / "tests" / "gerar_dados_sinteticos.py"
INGESTAO = RAIZ / "ingestao" / "ingestao_tse.py"


def rodar(*args) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, f"falhou: {args}\n{r.stdout}\n{r.stderr}"
    return r


def gerar(pasta: Path, versao: str) -> Path:
    rodar(GERADOR, pasta, versao)
    return pasta


def ingerir(pasta: Path, banco: Path, *extra) -> subprocess.CompletedProcess:
    return rodar(INGESTAO, pasta, "--banco", banco, *extra)


@pytest.fixture(scope="session")
def dados_v1(tmp_path_factory) -> Path:
    return gerar(tmp_path_factory.mktemp("dados_v1"), "v1")


@pytest.fixture(scope="session")
def dados_v2(tmp_path_factory) -> Path:
    return gerar(tmp_path_factory.mktemp("dados_v2"), "v2")


@pytest.fixture(scope="session")
def banco_v1(tmp_path_factory, dados_v1) -> Path:
    banco = tmp_path_factory.mktemp("banco_v1") / "eleicoes.duckdb"
    ingerir(dados_v1, banco)
    return banco


@pytest.fixture(scope="session")
def banco_v2(tmp_path_factory, dados_v1, dados_v2) -> Path:
    banco = tmp_path_factory.mktemp("banco_v2") / "eleicoes.duckdb"
    ingerir(dados_v1, banco)
    ingerir(dados_v2, banco)
    return banco


@pytest.fixture
def con_v1(banco_v1):
    con = duckdb.connect(str(banco_v1), read_only=True)
    yield con
    con.close()


@pytest.fixture
def con_v2(banco_v2):
    con = duckdb.connect(str(banco_v2), read_only=True)
    yield con
    con.close()


@pytest.fixture(scope="session")
def cliente(banco_v1):
    from fastapi.testclient import TestClient
    from app.main import criar_app
    with TestClient(criar_app(banco_v1)) as c:
        yield c


@pytest.fixture(scope="session")
def cliente_v3(tmp_path_factory):
    """Banco v3: v1 + candidatos em outro cargo (40) e outra UF (41)."""
    from fastapi.testclient import TestClient
    from app.main import criar_app
    dados = gerar(tmp_path_factory.mktemp("dados_v3"), "v3")
    banco = tmp_path_factory.mktemp("banco_v3") / "eleicoes.duckdb"
    ingerir(dados, banco)
    with TestClient(criar_app(banco)) as c:
        yield c
