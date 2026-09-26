"""
Testa quais modelos do serviço de IA funcionam com o "Pergunte aos dados" (tool calling).

Uso (na raiz do projeto; lê NVIDIA_API_KEY e IA_BASE_URL do .env ou do terminal):
    python scripts/testar_modelos_ia.py
    python scripts/testar_modelos_ia.py moonshotai/kimi-k2.6 z-ai/glm-5.3

Para cada modelo faz UMA pergunta simples que exige a ferramenta de busca e informa se o modelo
chamou a ferramenta com argumentos válidos e quanto tempo levou. Não usa o banco de dados.
Cada teste consome uma chamada da sua cota da API. A chave nunca é impressa.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import carregar_env  # noqa: E402
from app.ia.cliente import ClienteOpenAICompativel, ErroIA  # noqa: E402
from app.ia.ferramentas import DEFINICOES  # noqa: E402

# Resultado em 26/09/2026: todos OK, exceto kimi-k2.6 (404 na conta, apesar de listado).
CANDIDATOS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "z-ai/glm-5.3",
    "deepseek-ai/deepseek-v4.1-flash",
    "mistralai/mistral-nemotron",
    "openai/gpt-oss-20b",
]
PERGUNTA = "Quantas candidaturas existem com o nome Maria da Silva no RJ? Use as ferramentas."


def testar(cliente) -> tuple[str, str]:
    mensagens = [{"role": "system", "content": "Responda usando as ferramentas disponíveis."},
                 {"role": "user", "content": PERGUNTA}]
    msg = cliente.completar(mensagens, DEFINICOES)
    chamadas = msg.get("tool_calls") or []
    if not chamadas:
        return "NÃO chamou ferramenta", (msg.get("content") or "")[:80].replace("\n", " ")
    f = chamadas[0]["function"]
    try:
        args = json.loads(f.get("arguments") or "{}")
    except json.JSONDecodeError:
        return "argumentos inválidos", str(f.get("arguments"))[:80]
    return "OK", f"{f['name']}({json.dumps(args, ensure_ascii=False)})"


def main():
    carregar_env(Path(__file__).resolve().parents[1] / ".env")
    chave = os.environ.get("NVIDIA_API_KEY") or os.environ.get("IA_API_KEY")
    if not chave:
        sys.exit("Defina NVIDIA_API_KEY no .env (ver .env.exemplo).")
    base = os.environ.get("IA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    modelos = sys.argv[1:] or CANDIDATOS
    print(f"Testando {len(modelos)} modelo(s) em {base}\n")
    for modelo in modelos:
        inicio = time.time()
        try:
            resultado, detalhe = testar(ClienteOpenAICompativel(chave, base, modelo, timeout=120))
        except ErroIA as e:
            resultado, detalhe = "ERRO", str(e)[:120]
        print(f"{modelo:42} {resultado:22} {time.time() - inicio:5.1f}s  {detalhe}")
    print("\nUse no .env (IA_MODELO=...) um modelo com resultado OK.")


if __name__ == "__main__":
    main()
