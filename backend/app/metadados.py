"""
Dicionário de campos expostos pela API: natureza da informação e origem no TSE.

Toda resposta que traz dado ou métrica usa este dicionário para montar o bloco
{"natureza", "fonte": {"dataset", "arquivo", "linha", "campo"}, "geracao_tse"} (ver CLAUDE.md).
"""
DATASET = "candidatos-2026 (TSE — https://dadosabertos.tse.jus.br/dataset/candidatos-2026)"

CAND = "consulta_cand_2026_BRASIL.csv"
COMPL = "consulta_cand_complementar_2026_BRASIL.csv"
BEM = "bem_candidato_2026_BRASIL.csv"
HIST = "historico_candidatura_2026_BRASIL.csv"

# campo da API -> (natureza, arquivo, campo(s) do TSE, observação)
CAMPOS = {
    "sq_candidato": ("DADO", CAND, "SQ_CANDIDATO", None),
    "nr_candidato": ("DADO", CAND, "NR_CANDIDATO", None),
    "nm_candidato": ("DADO", CAND, "NM_CANDIDATO", None),
    "nm_urna": ("DADO", CAND, "NM_URNA_CANDIDATO", None),
    "nm_social": ("DADO", CAND, "NM_SOCIAL_CANDIDATO", None),
    "sg_uf": ("DADO", CAND, "SG_UF", None),
    "cd_cargo": ("DADO", CAND, "CD_CARGO", None),
    "ds_cargo": ("DADO", CAND, "DS_CARGO", None),
    "sg_partido": ("DADO", CAND, "SG_PARTIDO", None),
    "nm_partido": ("DADO", CAND, "NM_PARTIDO", None),
    "nm_federacao": ("DADO", CAND, "NM_FEDERACAO", None),
    "genero": ("DADO", CAND, "DS_GENERO", None),
    "cor_raca": ("DADO", CAND, "DS_COR_RACA", None),
    "grau_instrucao": ("DADO", CAND, "DS_GRAU_INSTRUCAO", None),
    "ocupacao": ("DADO", CAND, "DS_OCUPACAO", None),
    "idade_na_posse": ("DADO", COMPL, "NR_IDADE_DATA_POSSE", None),
    "situacao_candidatura": (
        "DADO", COMPL, "DS_SITUACAO_CANDIDATO_TOT | DS_SITUACAO_JULGAMENTO",
        "Vem de DS_SITUACAO_CANDIDATO_TOT; quando esse campo é nulo (candidatura fora da urna), "
        "de DS_SITUACAO_JULGAMENTO. O campo usado está em situacao_campo_origem."),
    "situacao_campo_origem": ("CALCULO", COMPL, None,
                              "Indica de qual campo do TSE a situação foi lida."),
    "na_urna": ("DADO", COMPL, "ST_CANDIDATO_INSERIDO_URNA", None),
    "qt_bens": ("CALCULO", BEM, "NR_ORDEM_BEM_CANDIDATO",
                "Contagem de bens declarados. Nulo = nenhum bem no arquivo (não é zero)."),
    "total_bens": ("CALCULO", BEM, "VR_BEM_CANDIDATO",
                   "Soma dos valores declarados. Nulo = nenhum bem no arquivo (não é zero)."),
    "historico_disponivel": (
        "CALCULO", HIST, "SQ_CANDIDATO_ATUAL",
        "FALSE = candidato ausente do arquivo de histórico do TSE (histórico não disponível "
        "no dataset utilizado; não significa que nunca concorreu)."),
    "qt_outros_registros_2026": (
        "CALCULO", CAND, None,
        "Outros registros de candidatura em 2026 da mesma pessoa (ligados por identificador "
        "interno derivado do CPF, que não é armazenado nem exposto)."),
    "outros_registros_2026": ("CALCULO", CAND, "SQ_CANDIDATO",
                              "sq_candidato dos outros registros da mesma pessoa em 2026."),
}


def bloco_campos(nomes, geracao_tse) -> dict:
    """Metadados por campo para respostas em lista (a linha de cada registro vai no item)."""
    saida = {}
    for n in nomes:
        if n not in CAMPOS:
            continue
        natureza, arquivo, campo, obs = CAMPOS[n]
        saida[n] = {"natureza": natureza,
                    "fonte": {"dataset": DATASET, "arquivo": arquivo, "campo": campo},
                    "geracao_tse": geracao_tse}
        if obs:
            saida[n]["observacao"] = obs
    return saida
