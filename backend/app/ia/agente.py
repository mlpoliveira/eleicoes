"""
Agente "Pergunte aos dados" (T10).

Fluxo: guarda de recusa (sem chamar o modelo) -> laço modelo <-> ferramentas (no máximo
MAX_RODADAS) -> resposta em JSON {criterio, resposta, calculo} -> checagem de termos avaliativos
(uma reescrita; se persistir, a resposta é retida e só os dados usados são mostrados) -> log.

A resposta da IA é ANALISE (texto gerado); os dados usados são os resultados das ferramentas,
mostrados junto, com fonte e geração TSE (regras 2, 5 e 8).
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from ..db import RAIZ, carga_atual
from . import ferramentas
from .cliente import ClienteIA
from .neutralidade import pedido_recusado, termos_avaliativos

MAX_RODADAS = 6

PROMPT_SISTEMA = """Você é o assistente "Pergunte aos dados" do Laboratório de Análise Eleitoral —
Eleições 2026, que usa os dados abertos oficiais do TSE. Responda em português do Brasil.

REGRAS OBRIGATÓRIAS
1. Use SOMENTE informações devolvidas pelas ferramentas. Nunca use conhecimento próprio sobre
   candidatos, partidos ou política. Se as ferramentas não trazem o dado, diga
   "não disponível no dataset utilizado". Nunca estime, nunca preencha lacunas, nunca trate
   ausência como zero.
2. Neutralidade: não recomende voto, não diga quem é melhor ou pior, não crie ranking de
   candidatos ou partidos, não use adjetivos avaliativos (ex.: experiente, preparado, rico,
   honesto, forte). Descreva fatos: "declarou 12 bens", "possui 3 candidaturas anteriores
   identificadas", "patrimônio declarado acima da mediana do grupo".
3. Toda estatística comparativa informa o universo e o n (ex.: "entre candidaturas a Deputado
   Federal no RJ em 2026, n = 1.234"). Repita os alertas de universo que as ferramentas trouxerem.
4. Histórico indisponível NÃO significa que a pessoa nunca concorreu. Fundamentos de indeferimento
   não são cassação nem culpa: mostre o dado como registrado, sem linguagem acusatória.
5. Não infira personalidade, caráter, honestidade, saúde, religião, orientação sexual ou intenções.
6. Cite a geração TSE dos dados usados. Valores em reais: escreva "R$" com vírgula decimal.
7. Se a pergunta for ambígua (ex.: nome com vários resultados), diga quais registros encontrou.

FORMATO DA RESPOSTA FINAL (depois de usar as ferramentas): somente um objeto JSON, sem texto fora dele:
{"criterio": "como a pergunta foi interpretada e quais filtros/universo foram usados",
 "resposta": "resposta factual, curta, citando números, universo e n",
 "calculo": "como os números foram obtidos (ferramentas e medidas usadas) ou vazio"}"""


def _sem_raciocinio(texto: str) -> str:
    """Modelos de raciocínio podem mandar o pensamento em <think>...</think> antes da resposta."""
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    return texto.split("</think>")[-1].strip()


def _extrair_json(texto: str) -> dict | None:
    """Primeiro objeto JSON com a chave 'resposta' (tolera texto ou ```json em volta)."""
    texto = _sem_raciocinio(texto)
    decodificador = json.JSONDecoder()
    for i, ch in enumerate(texto):
        if ch != "{":
            continue
        try:
            dados, _ = decodificador.raw_decode(texto[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(dados, dict) and "resposta" in dados:
            return dados
    return None


def _registrar(entrada: dict):
    """Log de cada pergunta (arquivo JSONL local; não vai para o Git)."""
    arquivo = Path(os.environ.get("IA_LOG", RAIZ / "logs" / "ia.jsonl"))
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def perguntar(pergunta: str, cliente: ClienteIA | None, cur) -> dict:
    inicio = time.time()
    carga = carga_atual(cur)
    base = {"pergunta": pergunta, "geracao_tse": carga["geracao_tse"], "carga_id": carga["carga_id"],
            "natureza": "ANALISE",
            "aviso": "Texto gerado por IA a partir exclusivamente dos dados listados em 'dados_usados'. "
                     "Confira os números nos dados e na fonte."}
    log = {"quando": datetime.now().isoformat(timespec="seconds"), "pergunta": pergunta,
           "modelo": getattr(cliente, "modelo", None), "ferramentas": []}

    recusa = pedido_recusado(pergunta)
    if recusa:
        log.update(recusa=recusa["motivo"], duracao_s=round(time.time() - inicio, 2))
        _registrar(log)
        return {**base, "natureza": "CONTEXTO", "recusada": True, "recusa": recusa,
                "criterio": None, "resposta": None, "calculo": None, "dados_usados": []}
    if cliente is None:
        raise RuntimeError("IA não configurada")

    mensagens = [{"role": "system", "content": PROMPT_SISTEMA},
                 {"role": "user", "content": pergunta}]
    dados_usados, valores_base, final = [], set(), None
    for _ in range(MAX_RODADAS):
        msg = cliente.completar(mensagens, ferramentas.DEFINICOES)
        chamadas = msg.get("tool_calls") or []
        mensagens.append({"role": "assistant", "content": msg.get("content") or "",
                          **({"tool_calls": chamadas} if chamadas else {})})
        if not chamadas:
            final = _sem_raciocinio(msg.get("content") or "")
            break
        for ch in chamadas:
            nome = ch["function"]["name"]
            try:
                args = json.loads(ch["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            resultado = ferramentas.executar(nome, args, cur)
            dados_usados.append({"ferramenta": nome, "argumentos": args, "resultado": resultado})
            valores_base |= ferramentas.strings_da_base(resultado)
            log["ferramentas"].append({"nome": nome, "argumentos": args, "erro": resultado.get("erro")})
            mensagens.append({"role": "tool", "tool_call_id": ch.get("id", nome),
                              "content": ferramentas.para_json(resultado)})

    if final is None:
        saida = {"criterio": None, "calculo": None,
                 "resposta": "Não foi possível concluir a resposta dentro do limite de consultas. "
                             "Veja abaixo os dados obtidos."}
    else:
        saida = _extrair_json(final) or {"criterio": None, "resposta": final.strip(), "calculo": None}
        termos = termos_avaliativos(" ".join(str(saida.get(k) or "") for k in ("criterio", "resposta", "calculo")),
                                    valores_base)
        if termos:
            mensagens.append({"role": "user", "content":
                              f"Reescreva a resposta final sem os termos avaliativos {termos}, descrevendo "
                              "só fatos dos dados. Mesmo formato JSON."})
            msg = cliente.completar(mensagens, [])
            nova = _extrair_json(msg.get("content") or "") or {"criterio": saida.get("criterio"),
                                                              "resposta": _sem_raciocinio(msg.get("content") or ""),
                                                              "calculo": saida.get("calculo")}
            termos2 = termos_avaliativos(" ".join(str(nova.get(k) or "") for k in ("criterio", "resposta", "calculo")),
                                         valores_base)
            log["reescrita"] = {"termos": termos, "persistiram": termos2}
            saida = nova if not termos2 else {
                "criterio": None, "calculo": None,
                "resposta": "A resposta gerada continha termos avaliativos e foi retida pelo filtro de "
                            "neutralidade. Os dados consultados estão listados abaixo."}

    log["duracao_s"] = round(time.time() - inicio, 2)
    _registrar(log)
    return {**base, "recusada": False, "recusa": None,
            "criterio": saida.get("criterio"), "resposta": saida.get("resposta"),
            "calculo": saida.get("calculo"), "dados_usados": dados_usados}
