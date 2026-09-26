"""
Guardas de neutralidade da IA (regras 1 e 7 do CLAUDE.md), aplicadas FORA do modelo:
  - antes: perguntas que pedem recomendação de voto, ranking de "melhores" ou inferência pessoal
    são recusadas sem chamar o modelo, com a explicação e uma versão factual sugerida;
  - depois: a resposta gerada é checada contra termos avaliativos (os valores vindos da base,
    como "SUPERIOR COMPLETO", são retirados antes da checagem).
"""
import re

PEDIDOS_RECUSADOS = [
    (re.compile(r"\b(em\s+quem|qual\s+candidat\w*|quem)\b.{0,40}\b(votar|voto)\b|"
                r"\bdevo\s+votar\b|\bvale\s+a\s+pena\s+votar\b|\brecomend\w*\b.{0,30}\b(voto|votar|candidat)",
                re.I | re.S),
     "recomendação de voto",
     "Posso mostrar os dados das candidaturas que você quiser comparar (patrimônio declarado, "
     "histórico de candidaturas, situação do registro), para você tirar suas conclusões."),
    (re.compile(r"\b(melhor(es)?|pior(es)?|mais\s+(preparad|competent|honest|confi[aá]ve|qualificad|"
                r"experiente|corrupt)\w*|ranking)\b", re.I),
     "classificação de candidatos como melhores ou piores",
     "Posso listar candidaturas ordenadas por um dado objetivo que você escolher (ex.: patrimônio "
     "declarado ou quantidade de candidaturas anteriores), sempre com o universo e a fonte."),
    (re.compile(r"\b(honest\w*|desonest\w*|corrupt\w*|ladr[aã]o|car[aá]ter|personalidade|"
                r"religi[aã]o|orienta[cç][aã]o\s+sexual|[eé]\s+gay|doen[cç]a|sa[uú]de\s+mental|"
                r"inten[cç][aã]o|confi[aá]vel)\b", re.I),
     "inferência sobre características pessoais",
     "A base do TSE não permite inferir caráter, honestidade, saúde, religião, orientação sexual ou "
     "intenções. Posso mostrar exatamente o que está registrado (ex.: situação do registro e "
     "fundamentos de indeferimento informados pelo TSE)."),
]

TERMOS_AVALIATIVOS = re.compile(
    r"\b(melhor|pior|ideal|preparad|experiente|inexperiente|qualificad|competente|incompetente|"
    r"honest|desonest|confi[aá]vel|ric[oa]s?|pobre|forte|fraco|vantagem|desvantagem|recomend|"
    r"vot[ea]\s+em|superior|inferior|destaca-se|lidera|corrupt|suspeit|culpad)\w*", re.I)


def pedido_recusado(pergunta: str) -> dict | None:
    for padrao, motivo, alternativa in PEDIDOS_RECUSADOS:
        if padrao.search(pergunta):
            return {"motivo": motivo,
                    "explicacao": f"Este laboratório não faz {motivo}: ele mostra dados oficiais do "
                                  "TSE e cálculos sobre eles, e as conclusões são de quem consulta.",
                    "alternativa": alternativa}
    return None


def termos_avaliativos(texto: str, valores_da_base: set[str]) -> list[str]:
    limpo = texto
    for v in sorted(valores_da_base, key=len, reverse=True):
        if len(v) >= 3:
            limpo = limpo.replace(v, " ")
    return sorted({m.group(0).lower() for m in TERMOS_AVALIATIVOS.finditer(limpo)})
