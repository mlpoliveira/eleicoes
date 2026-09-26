"""
Conexão com o banco DuckDB gerado por ingestao/ingestao_tse.py.

A API abre o banco SEMPRE em modo somente leitura (read_only=True). Caminho do banco:
variável de ambiente ELEICOES_DB (padrão: eleicoes.duckdb na raiz do repositório).
Observação: com a API aberta, o DuckDB mantém o arquivo travado; pare a API antes de
rodar uma nova carga.
"""
import os
import threading
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]


def caminho_banco() -> Path:
    return Path(os.environ.get("ELEICOES_DB", RAIZ / "eleicoes.duckdb"))


class Banco:
    """Uma conexão read-only por processo; cada requisição usa um cursor próprio."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self._con = None
        self._trava = threading.Lock()

    def conexao(self) -> duckdb.DuckDBPyConnection:
        with self._trava:
            if self._con is None:
                if not self.caminho.exists():
                    raise FileNotFoundError(
                        f"Banco não encontrado: {self.caminho}. Rode ingestao/ingestao_tse.py "
                        "ou defina ELEICOES_DB.")
                self._con = duckdb.connect(str(self.caminho), read_only=True)
            return self._con

    def cursor(self) -> duckdb.DuckDBPyConnection:
        return self.conexao().cursor()

    def fechar(self):
        with self._trava:
            if self._con is not None:
                self._con.close()
                self._con = None


def consultar(cur, sql: str, params=None) -> list[dict]:
    cur.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def carga_atual(cur) -> dict:
    """Carga mais recente = base das tabelas finais."""
    r = consultar(cur, "SELECT carga_id, geracao_tse FROM carga ORDER BY carga_id DESC LIMIT 1")
    return r[0] if r else {"carga_id": None, "geracao_tse": None}
