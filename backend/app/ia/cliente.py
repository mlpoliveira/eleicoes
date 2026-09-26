"""
Cliente de modelo de linguagem em formato compatível com OpenAI (chat/completions + tools).

Padrão: API da NVIDIA (build.nvidia.com / NIM). Configuração por variáveis de ambiente:
  NVIDIA_API_KEY (ou IA_API_KEY)  — chave; sem ela a rota /api/perguntar responde 503
  IA_BASE_URL  — padrão https://integrate.api.nvidia.com/v1
  IA_MODELO    — padrão MODELO_PADRAO (precisa suportar tool calling). O catálogo da NVIDIA muda:
                 modelos são aposentados (ex.: meta/llama-3.3-70b-instruct saiu em 26/08/2026).
                 Lista atual: GET {IA_BASE_URL}/models (pública).
O cliente é substituível (app.state.ia_cliente) — os testes usam um cliente simulado.
"""
import os
from typing import Protocol

import httpx


class ClienteIA(Protocol):
    modelo: str

    def completar(self, mensagens: list[dict], ferramentas: list[dict]) -> dict:
        """Devolve a mensagem do assistente: {"content": str|None, "tool_calls": [...]|None}."""


MODELO_PADRAO = "moonshotai/kimi-k2.6"  # confirmar com scripts/testar_modelos_ia.py


class ErroIA(Exception):
    pass


class ClienteOpenAICompativel:
    def __init__(self, chave: str, base_url: str, modelo: str, timeout: float = 90):
        self.chave, self.base_url, self.modelo, self.timeout = chave, base_url.rstrip("/"), modelo, timeout

    def completar(self, mensagens: list[dict], ferramentas: list[dict]) -> dict:
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.chave}", "Accept": "application/json"},
                json={"model": self.modelo, "messages": mensagens, "tools": ferramentas,
                      "tool_choice": "auto", "temperature": 0.1, "max_tokens": 1500},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise ErroIA(f"Falha ao contatar o serviço de IA ({self.base_url}): {e}") from e
        if r.status_code in (404, 410):
            raise ErroIA(f"O modelo '{self.modelo}' não está disponível no serviço de IA "
                         f"({r.status_code}: {r.text[:200]}). Escolha outro modelo com suporte a "
                         f"tool calling na lista {self.base_url}/models e defina IA_MODELO no .env.")
        if r.status_code in (401, 403):
            raise ErroIA(f"O serviço de IA recusou a chave ({r.status_code}). Confira NVIDIA_API_KEY no .env.")
        if r.status_code != 200:
            raise ErroIA(f"Serviço de IA respondeu {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]


def cliente_do_ambiente() -> ClienteIA | None:
    chave = os.environ.get("NVIDIA_API_KEY") or os.environ.get("IA_API_KEY")
    if not chave:
        return None
    return ClienteOpenAICompativel(
        chave,
        os.environ.get("IA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        os.environ.get("IA_MODELO", MODELO_PADRAO),
    )
