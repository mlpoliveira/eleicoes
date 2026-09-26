"""
Dicionário de campos expostos pela API: natureza da informação e origem no TSE.

Toda resposta que traz dado ou métrica usa este dicionário para montar o bloco
{"natureza", "fonte": {"dataset", "arquivo", "linha", "campo"}, "geracao_tse"} (ver CLAUDE.md).
"""
DATASET = "candidatos-2026 (TSE — https://dadosabertos.tse.jus.br/dataset/candidatos-2026)"
NAO_DISPONIVEL = "Não disponível no dataset utilizado."

CAND = "consulta_cand_2026_BRASIL.csv"
COMPL = "consulta_cand_complementar_2026_BRASIL.csv"
BEM = "bem_candidato_2026_BRASIL.csv"
REDE = "rede_social_candidato_2026_BRASIL.csv"
HIST = "historico_candidatura_2026_BRASIL.csv"
FUND = "motivo_cassacao_2026_BRASIL.csv"

# arquivo do TSE -> tabela raw_* que guarda o conteúdo original (todas as cargas)
RAW = {CAND: "raw_consulta_cand", COMPL: "raw_consulta_cand_complementar",
       BEM: "raw_bem_candidato", REDE: "raw_rede_social_candidato",
       HIST: "raw_historico_candidatura", FUND: "raw_motivo_cassacao"}

# campo da API -> (natureza, arquivo, campo(s) do TSE separados por " | ", observação)
CAMPOS = {
    # identificação
    "sq_candidato": ("DADO", CAND, "SQ_CANDIDATO", None),
    "nr_candidato": ("DADO", CAND, "NR_CANDIDATO", None),
    "nm_candidato": ("DADO", CAND, "NM_CANDIDATO", None),
    "nm_urna": ("DADO", CAND, "NM_URNA_CANDIDATO", None),
    "nm_social": ("DADO", CAND, "NM_SOCIAL_CANDIDATO", None),
    "ds_eleicao": ("DADO", CAND, "DS_ELEICAO", None),
    "dt_eleicao": ("DADO", CAND, "DT_ELEICAO", None),
    "sg_uf": ("DADO", CAND, "SG_UF", None),
    "nm_ue": ("DADO", CAND, "NM_UE", None),
    "cd_cargo": ("DADO", CAND, "CD_CARGO", None),
    "ds_cargo": ("DADO", CAND, "DS_CARGO", None),
    "nr_partido": ("DADO", CAND, "NR_PARTIDO", None),
    "sg_partido": ("DADO", CAND, "SG_PARTIDO", None),
    "nm_partido": ("DADO", CAND, "NM_PARTIDO", None),
    "tp_agremiacao": ("DADO", CAND, "TP_AGREMIACAO", None),
    "nm_federacao": ("DADO", CAND, "NM_FEDERACAO", None),
    "composicao_federacao": ("DADO", CAND, "SG_FEDERACAO", None),
    "sq_coligacao": ("DADO", CAND, "SQ_COLIGACAO", None),
    "nm_coligacao": ("DADO", CAND, "NM_COLIGACAO", None),
    "composicao_coligacao": ("DADO", CAND, "DS_COMPOSICAO_COLIGACAO", None),
    # perfil
    "dt_nascimento": ("DADO", CAND, "DT_NASCIMENTO", None),
    "idade_na_posse": ("DADO", COMPL, "NR_IDADE_DATA_POSSE", None),
    "uf_nascimento": ("DADO", CAND, "SG_UF_NASCIMENTO", None),
    "municipio_nascimento": ("DADO", COMPL, "NM_MUNICIPIO_NASCIMENTO", None),
    "nacionalidade": ("DADO", COMPL, "DS_NACIONALIDADE", None),
    "genero": ("DADO", CAND, "DS_GENERO", None),
    "cor_raca": ("DADO", CAND, "DS_COR_RACA", None),
    "grau_instrucao": ("DADO", CAND, "DS_GRAU_INSTRUCAO", None),
    "estado_civil": ("DADO", CAND, "DS_ESTADO_CIVIL", None),
    "ocupacao": ("DADO", CAND, "DS_OCUPACAO", None),
    "quilombola": ("DADO", COMPL, "ST_QUILOMBOLA", None),
    "etnia_indigena": ("DADO", COMPL, "DS_ETNIA_INDIGENA", None),
    # situação
    "situacao_candidatura": (
        "DADO", COMPL, "DS_SITUACAO_CANDIDATO_TOT | DS_SITUACAO_JULGAMENTO",
        "Vem de DS_SITUACAO_CANDIDATO_TOT; quando esse campo é nulo (candidatura fora da urna), "
        "de DS_SITUACAO_JULGAMENTO. O campo usado está em situacao_campo_origem."),
    "situacao_campo_origem": ("CALCULO", COMPL, "DS_SITUACAO_CANDIDATO_TOT | DS_SITUACAO_JULGAMENTO",
                              "Indica de qual campo do TSE a situação foi lida."),
    "situacao_julgamento": ("DADO", COMPL, "DS_SITUACAO_JULGAMENTO", None),
    "na_urna": ("DADO", COMPL, "ST_CANDIDATO_INSERIDO_URNA", None),
    "destinacao_votos": ("DADO", COMPL, "NM_TIPO_DESTINACAO_VOTOS", None),
    "substituido": ("DADO", COMPL, "ST_SUBSTITUIDO", None),
    "sq_substituido": ("DADO", COMPL, "SQ_SUBSTITUIDO", None),
    "nr_processo": ("DADO", COMPL, "NR_PROCESSO", None),
    "limite_gastos": ("DADO", COMPL, "VR_DESPESA_MAX_CAMPANHA",
                      "Valores menores ou iguais a zero no arquivo são tratados como não informados."),
    "resultado": ("DADO", CAND, "DS_SIT_TOT_TURNO", "Vazio até a apuração."),
    # patrimônio e derivados
    "declarou_bens": ("DADO", COMPL, "ST_DECLARAR_BENS", None),
    "qt_bens": ("CALCULO", BEM, "NR_ORDEM_BEM_CANDIDATO",
                "Contagem de bens declarados. Nulo = nenhum bem no arquivo (não é zero)."),
    "total_bens": ("CALCULO", BEM, "VR_BEM_CANDIDATO",
                   "Soma dos valores declarados. Nulo = nenhum bem no arquivo (não é zero)."),
    "historico_disponivel": (
        "CALCULO", HIST, "SQ_CANDIDATO_ATUAL",
        "FALSE = candidato ausente do arquivo de histórico do TSE (histórico não disponível "
        "no dataset utilizado; não significa que nunca concorreu)."),
    "qt_candidaturas_anteriores": (
        "CALCULO", HIST, "ANO_ELEICAO",
        "Registros do arquivo de histórico com ano anterior a 2026. Nulo = histórico indisponível."),
    "qt_vezes_eleito": (
        "CALCULO", HIST, "DS_SIT_TOT_TURNO",
        "Registros anteriores a 2026 cujo resultado começa com 'Eleito'. "
        "Nulo = histórico indisponível."),
    "ultimo_cargo_eleito": ("CALCULO", HIST, "DS_CARGO | ANO_ELEICAO | DS_SIT_TOT_TURNO", None),
    "qt_outros_registros_2026": (
        "CALCULO", CAND, None,
        "Outros registros de candidatura em 2026 da mesma pessoa (ligados por identificador "
        "interno derivado do CPF, que não é armazenado nem exposto)."),
    "outros_registros_2026": ("CALCULO", CAND, "SQ_CANDIDATO",
                              "sq_candidato dos outros registros da mesma pessoa em 2026."),
}

# tabelas com vários registros por candidato: campo da API -> (natureza, campo TSE, observação)
CAMPOS_BEM = {
    "nr_ordem": ("DADO", "NR_ORDEM_BEM_CANDIDATO", None),
    "tipo": ("DADO", "DS_TIPO_BEM_CANDIDATO", None),
    "descricao": ("DECLARACAO_CANDIDATO", "DS_BEM_CANDIDATO",
                  "Texto declarado pelo candidato à Justiça Eleitoral."),
    "valor": ("DADO", "VR_BEM_CANDIDATO",
              "Valor declarado; convertido para número (aceita vírgula ou ponto decimal). "
              "O texto original está em valor_original."),
    "valor_original": ("DADO", "VR_BEM_CANDIDATO", None),
    "dt_atualizacao": ("DADO", "DT_ULT_ATUAL_BEM_CANDIDATO", None),
}
CAMPOS_REDE = {
    "nr_ordem": ("DADO", "NR_ORDEM_REDE_SOCIAL", None),
    "url": ("DADO", "DS_URL", None),
    "plataforma": ("CALCULO", "DS_URL", "Plataforma identificada pelo domínio do endereço."),
}
CAMPOS_HIST = {
    "ano_eleicao": ("DADO", "ANO_ELEICAO", None),
    "turno": ("DADO", "NR_TURNO", None),
    "ds_eleicao": ("DADO", "DS_ELEICAO", None),
    "sg_uf": ("DADO", "SG_UF", None),
    "nm_ue": ("DADO", "NM_UE", None),
    "cd_cargo": ("DADO", "CD_CARGO", None),
    "ds_cargo": ("DADO", "DS_CARGO", None),
    "nr_candidato": ("DADO", "NR_CANDIDATO", None),
    "nm_urna": ("DADO", "NM_URNA_CANDIDATO", None),
    "sg_partido": ("DADO", "SG_PARTIDO", None),
    "situacao_candidatura": ("DADO", "DS_SITUACAO_CANDIDATURA", None),
    "situacao_julgamento": ("DADO", "DS_SITUACAO_JULGAMENTO", None),
    "resultado": ("DADO", "DS_SIT_TOT_TURNO", None),
    "eleito": ("CALCULO", "DS_SIT_TOT_TURNO", "Verdadeiro quando o resultado começa com 'Eleito'."),
}
CAMPOS_FUND = {
    "tipo": ("DADO", "DS_TP_MOTIVO", None),
    "motivo": ("DADO", "DS_MOTIVO", None),
}

# tabela final -> (arquivo do TSE, dicionário de campos)
TABELAS_MULTIPLAS = {
    "bem": (BEM, CAMPOS_BEM),
    "rede_social": (REDE, CAMPOS_REDE),
    "historico": (HIST, CAMPOS_HIST),
    "fundamento_indeferimento": (FUND, CAMPOS_FUND),
}


def bloco_campos(nomes, geracao_tse, campos=None, arquivo=None) -> dict:
    """Metadados por campo para respostas em lista (a linha de cada registro vai no item)."""
    saida = {}
    for n in nomes:
        if campos is None:
            if n not in CAMPOS:
                continue
            natureza, arq, campo, obs = CAMPOS[n]
        else:
            if n not in campos:
                continue
            natureza, campo, obs = campos[n]
            arq = arquivo
        saida[n] = {"natureza": natureza,
                    "fonte": {"dataset": DATASET, "arquivo": arq, "campo": campo},
                    "geracao_tse": geracao_tse}
        if obs:
            saida[n]["observacao"] = obs
    return saida


def linha_de(arquivo: str, registro: dict):
    """Linha de origem de um campo da tabela candidato, conforme o arquivo do TSE."""
    if arquivo == CAND:
        return registro.get("fonte_linha")
    if arquivo == COMPL:
        return registro.get("fonte_linha_compl")
    return None


def campo_com_fonte(nome: str, registro: dict, geracao_tse) -> dict:
    """Valor de um campo da tabela candidato com natureza e fonte (arquivo, linha, campo)."""
    natureza, arquivo, campo, obs = CAMPOS[nome]
    valor = registro.get(nome)
    saida = {"valor": valor, "natureza": natureza,
             "fonte": {"dataset": DATASET, "arquivo": arquivo,
                       "linha": linha_de(arquivo, registro), "campo": campo},
             "geracao_tse": geracao_tse}
    if obs:
        saida["observacao"] = obs
    if valor is None:
        saida["disponivel"] = False
        saida["mensagem"] = NAO_DISPONIVEL
    return saida
