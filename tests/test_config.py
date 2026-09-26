"""Leitura do .env (backend/app/config.py)."""
import os

from app.config import carregar_env


def test_carrega_sem_sobrescrever(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEICOES_SEM_DOTENV")
    for k in ("T_A", "T_B", "T_C", "T_D", "T_E"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("T_D", "do-terminal")
    arq = tmp_path / ".env"
    arq.write_text('# comentário\nT_A=1\nexport T_B="com aspas"\nT_C=valor # nota\nT_D=do-arquivo\n'
                   "linha sem igual\nT_E=\n", encoding="utf-8")
    assert carregar_env(arq) == ["T_A", "T_B", "T_C"]           # só nomes, nunca valores
    assert (os.environ["T_A"], os.environ["T_B"], os.environ["T_C"]) == ("1", "com aspas", "valor")
    assert os.environ["T_D"] == "do-terminal"                   # terminal tem prioridade
    assert "T_E" not in os.environ                              # vazio não é carregado


def test_desligado_nos_testes(tmp_path):
    arq = tmp_path / ".env"
    arq.write_text("T_X=1\n", encoding="utf-8")
    assert carregar_env(arq) == [] and "T_X" not in os.environ


def test_arquivo_inexistente(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEICOES_SEM_DOTENV")
    assert carregar_env(tmp_path / "nao_existe") == []
