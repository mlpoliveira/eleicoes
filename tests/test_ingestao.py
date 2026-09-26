"""Testes da ingestão (ingestao/ingestao_tse.py) sobre dados sintéticos."""
from decimal import Decimal

import duckdb

from conftest import ingerir

SQ = 190000000000  # sq_candidato do candidato de índice 0 no gerador

TABELAS_FINAIS = ["candidato", "bem", "rede_social", "historico",
                  "fundamento_indeferimento", "vaga", "coligacao"]


def um(con, sql, params=None):
    return con.execute(sql, params or []).fetchone()[0]


def linha(con, sq):
    cur = con.execute("SELECT * FROM v_candidato WHERE sq_candidato = ?", [sq])
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, cur.fetchone()))


# ---------------------------------------------------------------- estrutura e privacidade
def test_tabelas_criadas(con_v1):
    tabelas = {r[0] for r in con_v1.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    esperadas = {"carga", "qualidade", "alteracao", "snapshot_candidato", "v_candidato",
                 *TABELAS_FINAIS}
    assert esperadas <= tabelas
    assert um(con_v1, "SELECT count(*) FROM candidato") == 40


def test_dados_pessoais_descartados(con_v1):
    """CPF, título eleitoral e e-mail não existem em nenhuma tabela do banco."""
    colunas = {r[0].upper() for r in con_v1.execute(
        "SELECT column_name FROM information_schema.columns").fetchall()}
    assert not colunas & {"NR_CPF_CANDIDATO", "NR_TITULO_ELEITORAL_CANDIDATO", "DS_EMAIL"}


def test_chave_fica_fora_do_banco(banco_v1):
    assert banco_v1.with_suffix(".chave").exists()


def test_fonte_em_todas_as_tabelas_finais(con_v1):
    for t in TABELAS_FINAIS:
        cols = {r[0] for r in con_v1.execute(f"DESCRIBE {t}").fetchall()}
        assert {"fonte_arquivo", "fonte_linha"} <= cols, t
        assert um(con_v1, f"SELECT count(*) FROM {t} WHERE fonte_arquivo IS NULL "
                          f"OR fonte_linha IS NULL") == 0, t
        assert um(con_v1, f"SELECT count(*) FROM {t} WHERE fonte_arquivo NOT LIKE '%_BRASIL.csv'") == 0, t


def test_so_arquivos_brasil(con_v1):
    """Os ZIPs trazem _BRASIL e _RJ; ingerir os dois duplicaria candidatos."""
    assert um(con_v1, "SELECT count(DISTINCT _arquivo) FROM raw_consulta_cand") == 1
    assert um(con_v1, "SELECT count(*) - count(DISTINCT sq_candidato) FROM candidato") == 0


def test_fonte_linha_aponta_para_o_csv(con_v1):
    # linha 1 é o cabeçalho; o candidato 0 é o primeiro registro
    assert um(con_v1, "SELECT fonte_linha FROM candidato WHERE sq_candidato = ?", [SQ]) == 2


# ---------------------------------------------------------------- transformações
def test_valores_com_virgula_e_ponto(con_v1):
    valores = dict(con_v1.execute(
        "SELECT valor_original, valor FROM bem WHERE sq_candidato = ?", [SQ]).fetchall())
    assert valores == {"350000,50": Decimal("350000.50"), "1200.00": Decimal("1200.00")}


def test_texto_com_ponto_e_virgula_e_aspas(con_v1):
    assert um(con_v1, "SELECT descricao FROM bem WHERE sq_candidato = ? AND nr_ordem = 1",
              [SQ]) == 'APTO; "centro"'


def test_marcadores_de_ausencia_viram_null(con_v1):
    c = linha(con_v1, SQ)
    assert c["nm_social"] is None           # veio "#NULO"
    assert c["resultado"] is None           # vazio até a apuração
    assert c["etnia_indigena"] is None


def test_situacao_do_complementar(con_v1):
    c = linha(con_v1, SQ)
    assert c["situacao_candidatura"] == "DEFERIDO"
    assert c["situacao_campo_origem"] == "DS_SITUACAO_CANDIDATO_TOT"
    assert c["na_urna"] is True


def test_situacao_de_quem_saiu_da_urna(con_v1):
    """TOT = #NULO → a situação vem de DS_SITUACAO_JULGAMENTO, e isso fica registrado."""
    c = linha(con_v1, SQ + 8)
    assert c["situacao_candidatura"] == "RENÚNCIA"
    assert c["situacao_campo_origem"] == "DS_SITUACAO_JULGAMENTO"
    assert c["na_urna"] is False
    assert um(con_v1, "SELECT quantidade FROM qualidade WHERE carga_id = 1 AND verificacao = "
                      "'situação obtida de DS_SITUACAO_JULGAMENTO (fora da urna)'") == 1


def test_pessoa_com_mais_de_um_registro(con_v1):
    """Candidatos 0, 1 e 2 têm o mesmo CPF: mesmo pessoa_id, sem expor o CPF."""
    ids = [r[0] for r in con_v1.execute(
        "SELECT pessoa_id FROM candidato WHERE sq_candidato IN (?, ?, ?)",
        [SQ, SQ + 1, SQ + 2]).fetchall()]
    assert len(set(ids)) == 1 and ids[0] is not None and ids[0] != "111"
    assert linha(con_v1, SQ)["qt_outros_registros_2026"] == 2
    assert linha(con_v1, SQ + 3)["qt_outros_registros_2026"] == 0


def test_pessoa_id_estavel_entre_cargas(con_v2):
    ids = con_v2.execute("SELECT count(DISTINCT _PESSOA_ID) FROM raw_consulta_cand "
                         "WHERE SQ_CANDIDATO = ?", [str(SQ)]).fetchone()[0]
    assert ids == 1


# ---------------------------------------------------------------- ausência ≠ zero
def test_historico_indisponivel_nao_e_estreante(con_v1):
    ausente = linha(con_v1, SQ + 7)
    assert ausente["historico_disponivel"] is False
    assert ausente["qt_candidaturas_anteriores"] is None   # desconhecido, não 0
    assert ausente["qt_vezes_eleito"] is None

    sem_anteriores = linha(con_v1, SQ + 10)
    assert sem_anteriores["historico_disponivel"] is True
    assert sem_anteriores["qt_candidaturas_anteriores"] == 0
    assert sem_anteriores["ultimo_cargo_eleito"] is None

    assert um(con_v1, "SELECT quantidade FROM qualidade WHERE carga_id = 1 AND verificacao LIKE "
                      "'candidatos ausentes do arquivo de histórico%'") == 1


def test_historico_conta_candidaturas(con_v1):
    c = linha(con_v1, SQ)
    assert c["qt_candidaturas_anteriores"] == 2
    assert c["qt_vezes_eleito"] == 1
    assert c["ultimo_cargo_eleito"] == "Deputado Estadual (2022)"


def test_sem_bens_nao_vira_zero(con_v1):
    c = linha(con_v1, SQ + 9)
    assert c["declarou_bens"] == "N"
    assert c["qt_bens"] is None and c["total_bens"] is None


def test_bem_com_valor_zero_medido(con_v1):
    assert um(con_v1, "SELECT quantidade FROM qualidade WHERE carga_id = 1 "
                      "AND verificacao = 'bens com valor zero'") == 1
    assert linha(con_v1, SQ + 11)["total_bens"] == Decimal("350000.50")


def test_fundamento_indeferimento(con_v1):
    r = con_v1.execute("SELECT sq_candidato, motivo FROM fundamento_indeferimento").fetchall()
    assert r == [(SQ + 5, "Ausência de quitação eleitoral (Lei 9.504/97)")]


# ---------------------------------------------------------------- cargas versionadas
def test_carga_registrada(con_v1):
    assert con_v1.execute("SELECT carga_id, geracao_tse FROM carga").fetchall() == [
        (1, "26/09/2026 08:31:16")]
    assert um(con_v1, "SELECT count(*) FROM alteracao") == 0


def test_mesma_geracao_nao_recarrega(tmp_path, dados_v1):
    banco = tmp_path / "e.duckdb"
    ingerir(dados_v1, banco)
    r = ingerir(dados_v1, banco)
    assert "já foi carregada" in r.stdout
    con = duckdb.connect(str(banco), read_only=True)
    assert um(con, "SELECT count(*) FROM carga") == 1
    con.close()


def test_segunda_carga_registra_alteracoes(con_v2):
    assert um(con_v2, "SELECT count(*) FROM carga") == 2
    assert um(con_v2, "SELECT count(*) FROM candidato") == 41
    # raw_* guardam todas as cargas; tabelas finais só a última
    assert um(con_v2, "SELECT count(DISTINCT _carga_id) FROM raw_consulta_cand") == 2
    alt = set(con_v2.execute(
        "SELECT sq_candidato, campo, antes, depois FROM alteracao WHERE carga_id = 2").fetchall())
    assert alt == {
        (SQ + 5, "situacao_candidatura", "DEFERIDO", "INDEFERIDO"),
        (SQ + 5, "situacao_julgamento", "DEFERIDO", "INDEFERIDO"),
        (SQ + 40, "candidato", None, "novo"),
    }


def test_qualidade_por_carga(con_v2):
    assert um(con_v2, "SELECT quantidade FROM qualidade WHERE carga_id = 2 "
                      "AND verificacao = 'candidatos'") == 41
    assert um(con_v2, "SELECT quantidade FROM qualidade WHERE carga_id = 1 "
                      "AND verificacao = 'candidatos'") == 40


def test_booleano_ausente_continua_nulo(con_v1):
    assert linha(con_v1, SQ + 13)["quilombola"] is None
    assert linha(con_v1, SQ)["quilombola"] is False
