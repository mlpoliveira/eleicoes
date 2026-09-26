"""
Leitura do arquivo .env da raiz do projeto (sem dependência externa).

- Formato: CHAVE=valor por linha; '#' inicia comentário; aspas simples/duplas em volta do valor
  são removidas; aceita o prefixo "export ".
- Nunca sobrescreve variável já definida no ambiente (o terminal tem prioridade).
- ELEICOES_SEM_DOTENV=1 desliga a leitura (usado pelos testes, que nunca devem ver a chave real).
- O .env contém segredos e está no .gitignore; modelo sem segredos: .env.exemplo.
"""
import os
from pathlib import Path


def carregar_env(arquivo: Path) -> list[str]:
    """Carrega variáveis do arquivo; devolve os NOMES carregados (nunca os valores)."""
    if os.environ.get("ELEICOES_SEM_DOTENV") or not arquivo.is_file():
        return []
    carregadas = []
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        if linha.startswith("export "):
            linha = linha[len("export "):]
        chave, valor = (p.strip() for p in linha.split("=", 1))
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        elif " #" in valor:
            valor = valor.split(" #", 1)[0].rstrip()
        if chave and valor and chave not in os.environ:
            os.environ[chave] = valor
            carregadas.append(chave)
    return carregadas
