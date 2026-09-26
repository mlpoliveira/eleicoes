"""
Ingestão versionada dos dados do TSE (Eleições 2026) em DuckDB.

Uso:
    pip install duckdb pandas
    python ingestao_tse.py "C:\\caminho\\da\\pasta_dos_datasets" [--banco eleicoes.duckdb] [--forcar]

Princípios:
  - lê SOMENTE os arquivos *_BRASIL.csv (os por UF são subconjuntos e duplicariam dados);
  - descarta CPF, título eleitoral e e-mail já na leitura (o app não precisa deles);
  - cada execução é uma CARGA versionada; tabelas raw_* guardam todas as cargas,
    com arquivo e linha de origem de cada registro (base do "Ver fonte");
  - tabelas finais (candidato, bem, rede_social, historico, ...) são reconstruídas
    a partir da carga mais recente;
  - a tabela `alteracao` registra o que mudou em relação à carga anterior;
  - a tabela `qualidade` registra verificações — problemas são medidos, nunca "corrigidos" em silêncio.
"""
import argparse
import hashlib
import hmac
import secrets
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

DATASETS = [  # prefixo do arquivo -> tabela raw
    "consulta_cand", "consulta_cand_complementar", "bem_candidato",
    "rede_social_candidato", "historico_candidatura", "motivo_cassacao",
    "consulta_vagas", "consulta_coligacao",
]
DESCARTAR = {"NR_CPF_CANDIDATO", "NR_TITULO_ELEITORAL_CANDIDATO", "DS_EMAIL"}


# ---------------------------------------------------------------- localização dos arquivos
def localizar_arquivos(raiz: Path) -> dict:
    """Acha <prefixo>_<ano>_BRASIL.csv; se só houver ZIP, extrai apenas esse arquivo."""
    encontrados = {}
    for prefixo in DATASETS:
        padrao = re.compile(rf"^{prefixo}_(\d{{4}})_BRASIL\.csv$", re.I)
        csvs = [p for p in raiz.rglob("*.csv") if padrao.match(p.name)]
        if not csvs:
            for z in raiz.rglob(f"{prefixo}_*.zip"):
                with zipfile.ZipFile(z) as zf:
                    for m in zf.namelist():
                        if padrao.match(Path(m).name):
                            alvo = raiz / "_extraido" / z.stem / Path(m).name
                            alvo.parent.mkdir(parents=True, exist_ok=True)
                            alvo.write_bytes(zf.read(m))
                            csvs.append(alvo)
        if csvs:
            encontrados[prefixo] = max(csvs, key=lambda p: p.stat().st_mtime)
    return encontrados


def chave_local(banco: str) -> bytes:
    """Chave secreta local para o pessoa_id. Fica ao lado do banco; NUNCA versionar no Git."""
    arq = Path(banco).with_suffix(".chave")
    if not arq.exists():
        arq.write_text(secrets.token_hex(32))
    return bytes.fromhex(arq.read_text().strip())


def ler_csv(arquivo: Path, chave: bytes) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(arquivo, sep=";", encoding="latin-1", dtype=str,
                     keep_default_na=False, quotechar='"')
    metricas = {}
    if "NR_CPF_CANDIDATO" in df.columns:  # mede duplicidade sem guardar o dado
        cpfs = df["NR_CPF_CANDIDATO"]
        cpfs = cpfs[~cpfs.isin(["", "#NULO", "#NE", "-4", "NÃO DIVULGÁVEL"])]
        metricas["pessoas_com_mais_de_um_registro"] = int((cpfs.value_counts() > 1).sum())
        # identificador opaco da pessoa: estável entre cargas, irreversível sem a chave local
        df["_PESSOA_ID"] = [hmac.new(chave, v.encode(), hashlib.sha256).hexdigest()[:16]
                            if v in set(cpfs) else None for v in df["NR_CPF_CANDIDATO"]]
    df = df.drop(columns=[c for c in df.columns if c in DESCARTAR])
    df.insert(0, "_linha", range(2, len(df) + 2))       # linha 1 é o cabeçalho
    df.insert(0, "_arquivo", arquivo.name)
    return df, metricas


# ---------------------------------------------------------------- carga raw
def gravar_raw(con, tabela: str, df: pd.DataFrame, carga_id: int):
    df = df.copy()
    df.insert(0, "_carga_id", carga_id)
    con.register("df_tmp", df)
    existe = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name=?",
                         [tabela]).fetchone()[0]
    if not existe:
        con.execute(f"CREATE TABLE {tabela} AS SELECT * FROM df_tmp")
    else:
        atuais = {r[0] for r in con.execute(f"DESCRIBE {tabela}").fetchall()}
        for col in df.columns:
            if col not in atuais:  # TSE incluiu coluna nova: acomoda e registra
                con.execute(f'ALTER TABLE {tabela} ADD COLUMN "{col}" VARCHAR')
                print(f"  [aviso] coluna nova em {tabela}: {col}")
        con.execute(f"INSERT INTO {tabela} BY NAME SELECT * FROM df_tmp")
    con.unregister("df_tmp")


# ---------------------------------------------------------------- modelo final
# Funções auxiliares (macros): marcadores de ausência do TSE viram NULL.
MACROS = r"""
CREATE OR REPLACE MACRO nz(v) AS CASE WHEN trim(v) IN ('', '#NULO', '#NULO#', '#NE', '#NE#') THEN NULL ELSE trim(v) END;
CREATE OR REPLACE MACRO nzcod(v) AS CASE WHEN trim(v) IN ('', '-1', '-3', '#NULO', '#NE') THEN NULL ELSE trim(v) END;
CREATE OR REPLACE MACRO dt(v) AS try_strptime(nz(v), '%d/%m/%Y')::DATE;
CREATE OR REPLACE MACRO valor(v) AS try_cast(
    CASE WHEN nz(v) LIKE '%,%' THEN replace(replace(nz(v), '.', ''), ',', '.') ELSE nz(v) END
    AS DECIMAL(18,2));
"""

MODELO = r"""
CREATE OR REPLACE TABLE candidato AS
WITH c AS (SELECT * FROM raw_consulta_cand WHERE _carga_id = $carga),
     k AS (SELECT * FROM raw_consulta_cand_complementar WHERE _carga_id = $carga)
SELECT
    c.SQ_CANDIDATO::BIGINT                    AS sq_candidato,
    c._PESSOA_ID                              AS pessoa_id,       -- liga registros da mesma pessoa
    c.ANO_ELEICAO::INT                        AS ano_eleicao,
    c.CD_ELEICAO::INT                         AS cd_eleicao,
    c.DS_ELEICAO                              AS ds_eleicao,
    dt(c.DT_ELEICAO)                          AS dt_eleicao,
    c.SG_UF                                   AS sg_uf,
    c.NM_UE                                   AS nm_ue,
    c.CD_CARGO::INT                           AS cd_cargo,
    c.DS_CARGO                                AS ds_cargo,
    c.NR_CANDIDATO                            AS nr_candidato,
    c.NM_CANDIDATO                            AS nm_candidato,
    c.NM_URNA_CANDIDATO                       AS nm_urna,
    nz(c.NM_SOCIAL_CANDIDATO)                 AS nm_social,
    c.NR_PARTIDO::INT                         AS nr_partido,
    c.SG_PARTIDO                              AS sg_partido,
    c.NM_PARTIDO                              AS nm_partido,
    c.TP_AGREMIACAO                           AS tp_agremiacao,
    nz(c.NM_FEDERACAO)                        AS nm_federacao,
    nz(c.SG_FEDERACAO)                        AS composicao_federacao,
    c.SQ_COLIGACAO::BIGINT                    AS sq_coligacao,
    nz(c.NM_COLIGACAO)                        AS nm_coligacao,
    nz(c.DS_COMPOSICAO_COLIGACAO)             AS composicao_coligacao,
    dt(c.DT_NASCIMENTO)                       AS dt_nascimento,
    try_cast(nzcod(k.NR_IDADE_DATA_POSSE) AS INT) AS idade_na_posse,
    c.SG_UF_NASCIMENTO                        AS uf_nascimento,
    nz(k.NM_MUNICIPIO_NASCIMENTO)             AS municipio_nascimento,
    k.DS_NACIONALIDADE                        AS nacionalidade,
    c.DS_GENERO                               AS genero,
    c.DS_COR_RACA                             AS cor_raca,
    c.DS_GRAU_INSTRUCAO                       AS grau_instrucao,
    c.DS_ESTADO_CIVIL                         AS estado_civil,
    c.DS_OCUPACAO                             AS ocupacao,
    k.ST_QUILOMBOLA = 'S'                     AS quilombola,
    nz(k.DS_ETNIA_INDIGENA)                   AS etnia_indigena,
    -- situação: vem do COMPLEMENTAR (no consulta_cand está 100% #NE). Candidaturas fora da urna
    -- (renúncia, indeferimento...) têm o campo TOT = #NULO; aí vale o DS_SITUACAO_JULGAMENTO.
    coalesce(nz(k.DS_SITUACAO_CANDIDATO_TOT), nz(k.DS_SITUACAO_JULGAMENTO)) AS situacao_candidatura,
    CASE WHEN nz(k.DS_SITUACAO_CANDIDATO_TOT) IS NOT NULL THEN 'DS_SITUACAO_CANDIDATO_TOT'
         WHEN nz(k.DS_SITUACAO_JULGAMENTO) IS NOT NULL THEN 'DS_SITUACAO_JULGAMENTO' END AS situacao_campo_origem,
    nz(k.DS_SITUACAO_JULGAMENTO)              AS situacao_julgamento,
    nz(k.NM_TIPO_DESTINACAO_VOTOS)            AS destinacao_votos,
    k.ST_CANDIDATO_INSERIDO_URNA = 'SIM'      AS na_urna,
    k.ST_SUBSTITUIDO = 'S'                    AS substituido,
    try_cast(nzcod(k.SQ_SUBSTITUIDO) AS BIGINT) AS sq_substituido,
    nz(k.ST_DECLARAR_BENS)                    AS declarou_bens,
    CASE WHEN valor(k.VR_DESPESA_MAX_CAMPANHA) > 0
         THEN valor(k.VR_DESPESA_MAX_CAMPANHA) END AS limite_gastos,
    nz(k.NR_PROCESSO)                         AS nr_processo,
    nz(c.DS_SIT_TOT_TURNO)                    AS resultado,       -- vazio até a apuração
    c._arquivo AS fonte_arquivo, c._linha AS fonte_linha,
    k._arquivo AS fonte_arquivo_compl, k._linha AS fonte_linha_compl
FROM c LEFT JOIN k USING (SQ_CANDIDATO);

CREATE OR REPLACE TABLE bem AS
SELECT SQ_CANDIDATO::BIGINT AS sq_candidato,
       NR_ORDEM_BEM_CANDIDATO::INT AS nr_ordem,
       DS_TIPO_BEM_CANDIDATO AS tipo, nz(DS_BEM_CANDIDATO) AS descricao,
       valor(VR_BEM_CANDIDATO) AS valor, VR_BEM_CANDIDATO AS valor_original,
       dt(DT_ULT_ATUAL_BEM_CANDIDATO) AS dt_atualizacao,
       _arquivo AS fonte_arquivo, _linha AS fonte_linha
FROM raw_bem_candidato WHERE _carga_id = $carga;

CREATE OR REPLACE TABLE rede_social AS
SELECT SQ_CANDIDATO::BIGINT AS sq_candidato, NR_ORDEM_REDE_SOCIAL::INT AS nr_ordem,
       trim(DS_URL) AS url,
       CASE WHEN DS_URL ILIKE '%instagram.%' THEN 'Instagram'
            WHEN DS_URL ILIKE '%facebook.%' OR DS_URL ILIKE '%fb.com%' THEN 'Facebook'
            WHEN DS_URL ILIKE '%tiktok.%' THEN 'TikTok'
            WHEN DS_URL ILIKE '%youtube.%' OR DS_URL ILIKE '%youtu.be%' THEN 'YouTube'
            WHEN DS_URL ILIKE '%x.com%' OR DS_URL ILIKE '%twitter.%' THEN 'X/Twitter'
            WHEN DS_URL ILIKE '%linkedin.%' THEN 'LinkedIn'
            WHEN DS_URL ILIKE '%kwai%' THEN 'Kwai'
            WHEN DS_URL ILIKE '%threads.%' THEN 'Threads'
            WHEN DS_URL ILIKE '%wa.me%' OR DS_URL ILIKE '%whatsapp%' THEN 'WhatsApp'
            ELSE 'Site/outro' END AS plataforma,
       _arquivo AS fonte_arquivo, _linha AS fonte_linha
FROM raw_rede_social_candidato WHERE _carga_id = $carga;

CREATE OR REPLACE TABLE historico AS
SELECT SQ_CANDIDATO_ATUAL::BIGINT AS sq_candidato_atual,
       SQ_CANDIDATO::BIGINT AS sq_candidato, ANO_ELEICAO::INT AS ano_eleicao,
       NR_TURNO::INT AS turno, DS_ELEICAO AS ds_eleicao, dt(DT_ELEICAO) AS dt_eleicao,
       SG_UF AS sg_uf, NM_UE AS nm_ue, CD_CARGO::INT AS cd_cargo, DS_CARGO AS ds_cargo,
       NR_CANDIDATO AS nr_candidato, NM_URNA_CANDIDATO AS nm_urna, SG_PARTIDO AS sg_partido,
       nz(DS_SITUACAO_CANDIDATURA) AS situacao_candidatura,
       nz(DS_SITUACAO_JULGAMENTO) AS situacao_julgamento,
       nz(DS_SIT_TOT_TURNO) AS resultado,
       coalesce(nz(DS_SIT_TOT_TURNO) ILIKE 'eleito%', false) AS eleito,
       _arquivo AS fonte_arquivo, _linha AS fonte_linha
FROM raw_historico_candidatura WHERE _carga_id = $carga;

CREATE OR REPLACE TABLE fundamento_indeferimento AS   -- arquivo "motivo_cassacao" do TSE
SELECT SQ_CANDIDATO::BIGINT AS sq_candidato, DS_TP_MOTIVO AS tipo, DS_MOTIVO AS motivo,
       _arquivo AS fonte_arquivo, _linha AS fonte_linha
FROM raw_motivo_cassacao WHERE _carga_id = $carga;

CREATE OR REPLACE TABLE vaga AS
SELECT SG_UF AS sg_uf, NM_UE AS nm_ue, CD_CARGO::INT AS cd_cargo, QT_VAGA::INT AS qt_vaga,
       dt(DT_POSSE) AS dt_posse, _arquivo AS fonte_arquivo, _linha AS fonte_linha
FROM raw_consulta_vagas WHERE _carga_id = $carga;

CREATE OR REPLACE TABLE coligacao AS
SELECT SQ_COLIGACAO::BIGINT AS sq_coligacao, SG_UF AS sg_uf, CD_CARGO::INT AS cd_cargo,
       TP_AGREMIACAO AS tp_agremiacao, nz(NM_COLIGACAO) AS nm_coligacao,
       DS_COMPOSICAO_COLIGACAO AS composicao, NR_PARTIDO::INT AS nr_partido,
       SG_PARTIDO AS sg_partido, nz(NM_FEDERACAO) AS nm_federacao,
       DS_SITUACAO AS situacao_legenda, _arquivo AS fonte_arquivo, _linha AS fonte_linha
FROM raw_consulta_coligacao WHERE _carga_id = $carga;

-- Visão de trabalho do app: candidato + totais derivados
CREATE OR REPLACE VIEW v_candidato AS
SELECT c.*,
       b.qt_bens, b.total_bens,
       h.sq_hist IS NOT NULL AS historico_disponivel,   -- FALSE = sem dado, NÃO "nunca concorreu"
       h.qt_candidaturas_anteriores, h.qt_vezes_eleito, h.ultimo_cargo_eleito,
       (SELECT count(*) FROM candidato o WHERE o.pessoa_id = c.pessoa_id
          AND o.sq_candidato <> c.sq_candidato) AS qt_outros_registros_2026
FROM candidato c
LEFT JOIN (SELECT sq_candidato, count(*) qt_bens, sum(valor) total_bens
           FROM bem GROUP BY 1) b USING (sq_candidato)
LEFT JOIN (SELECT sq_candidato_atual AS sq_candidato,
                  sq_candidato_atual AS sq_hist,
                  count(*) FILTER (WHERE ano_eleicao < 2026) qt_candidaturas_anteriores,
                  count(*) FILTER (WHERE ano_eleicao < 2026 AND eleito) qt_vezes_eleito,
                  arg_max(ds_cargo || ' (' || ano_eleicao || ')', ano_eleicao)
                      FILTER (WHERE ano_eleicao < 2026 AND eleito) ultimo_cargo_eleito
           FROM historico GROUP BY 1) h USING (sq_candidato);
"""

QUALIDADE = [
    ("candidatos", "SELECT count(*) FROM candidato"),
    ("candidatos sem registro no complementar",
     "SELECT count(*) FROM candidato WHERE fonte_linha_compl IS NULL"),
    ("candidatos sem situação da candidatura",
     "SELECT count(*) FROM candidato WHERE situacao_candidatura IS NULL"),
    ("situação obtida de DS_SITUACAO_JULGAMENTO (fora da urna)",
     "SELECT count(*) FROM candidato WHERE situacao_campo_origem = 'DS_SITUACAO_JULGAMENTO'"),
    ("pessoas com mais de um registro (via pessoa_id)",
     "SELECT count(*) FROM (SELECT pessoa_id FROM candidato WHERE pessoa_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1)"),
    ("bens de candidato inexistente", "SELECT count(*) FROM bem WHERE sq_candidato NOT IN (SELECT sq_candidato FROM candidato)"),
    ("bens com valor ilegível", "SELECT count(*) FROM bem WHERE valor IS NULL"),
    ("bens com valor zero", "SELECT count(*) FROM bem WHERE valor = 0"),
    ("declarou bens = S mas sem bens no arquivo",
     "SELECT count(*) FROM candidato WHERE declarou_bens='S' AND sq_candidato NOT IN (SELECT sq_candidato FROM bem)"),
    ("declarou bens = N mas tem bens no arquivo",
     "SELECT count(*) FROM candidato WHERE declarou_bens='N' AND sq_candidato IN (SELECT sq_candidato FROM bem)"),
    ("redes sociais de candidato inexistente",
     "SELECT count(*) FROM rede_social WHERE sq_candidato NOT IN (SELECT sq_candidato FROM candidato)"),
    ("candidatos ausentes do arquivo de histórico (histórico indisponível, não 'estreantes')",
     "SELECT count(*) FROM candidato WHERE sq_candidato NOT IN (SELECT sq_candidato_atual FROM historico)"),
    ("data de nascimento ilegível", "SELECT count(*) FROM candidato WHERE dt_nascimento IS NULL"),
]


def registrar_alteracoes(con, carga: int):
    """Snapshot de campos que mudam até a eleição + diff com a carga anterior."""
    con.execute("""CREATE TABLE IF NOT EXISTS snapshot_candidato (
        carga_id INT, sq_candidato BIGINT, nm_urna VARCHAR, situacao_candidatura VARCHAR,
        situacao_julgamento VARCHAR, na_urna BOOLEAN, total_bens DECIMAL(18,2),
        qt_redes INT, resultado VARCHAR)""")
    con.execute("DELETE FROM snapshot_candidato WHERE carga_id = ?", [carga])
    con.execute("""INSERT INTO snapshot_candidato
        SELECT ?, c.sq_candidato, c.nm_urna, c.situacao_candidatura, c.situacao_julgamento,
               c.na_urna, c.total_bens,
               (SELECT count(*) FROM rede_social r WHERE r.sq_candidato = c.sq_candidato),
               c.resultado
        FROM v_candidato c""", [carga])
    anterior = con.execute("SELECT max(carga_id) FROM snapshot_candidato WHERE carga_id < ?",
                           [carga]).fetchone()[0]
    con.execute("""CREATE TABLE IF NOT EXISTS alteracao (
        carga_id INT, sq_candidato BIGINT, campo VARCHAR, antes VARCHAR, depois VARCHAR)""")
    con.execute("DELETE FROM alteracao WHERE carga_id = ?", [carga])
    if anterior is None:
        return 0
    campos = ["situacao_candidatura", "situacao_julgamento", "na_urna", "total_bens",
              "qt_redes", "resultado", "nm_urna"]
    for campo in campos:
        con.execute(f"""INSERT INTO alteracao
            SELECT ?, n.sq_candidato, '{campo}', a.{campo}::VARCHAR, n.{campo}::VARCHAR
            FROM snapshot_candidato n JOIN snapshot_candidato a
              ON a.sq_candidato = n.sq_candidato AND a.carga_id = ?
            WHERE n.carga_id = ? AND a.{campo} IS DISTINCT FROM n.{campo}""",
                    [carga, anterior, carga])
    con.execute("""INSERT INTO alteracao
        SELECT ?, sq_candidato, 'candidato', NULL, 'novo' FROM snapshot_candidato
        WHERE carga_id = ? AND sq_candidato NOT IN
              (SELECT sq_candidato FROM snapshot_candidato WHERE carga_id = ?)""",
                [carga, carga, anterior])
    con.execute("""INSERT INTO alteracao
        SELECT ?, sq_candidato, 'candidato', 'existia', 'removido' FROM snapshot_candidato
        WHERE carga_id = ? AND sq_candidato NOT IN
              (SELECT sq_candidato FROM snapshot_candidato WHERE carga_id = ?)""",
                [carga, anterior, carga])
    return con.execute("SELECT count(*) FROM alteracao WHERE carga_id = ?", [carga]).fetchone()[0]


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--banco", default="eleicoes.duckdb")
    ap.add_argument("--forcar", action="store_true", help="recarrega mesmo se a geração já foi carregada")
    args = ap.parse_args()

    raiz = Path(args.pasta).expanduser().resolve()
    arquivos = localizar_arquivos(raiz)
    faltando = [d for d in DATASETS if d not in arquivos]
    if faltando:
        sys.exit(f"Arquivos obrigatórios não encontrados: {faltando}")

    dfs, metricas = {}, {}
    chave = chave_local(args.banco)
    for prefixo, arq in arquivos.items():
        print(f"Lendo {arq.name} ...")
        dfs[prefixo], m = ler_csv(arq, chave)
        metricas.update({f"{prefixo}: {k}": v for k, v in m.items()})

    base = dfs["consulta_cand"]
    geracao = f"{base['DT_GERACAO'].iloc[0]} {base['HH_GERACAO'].iloc[0]}"

    con = duckdb.connect(args.banco)
    con.execute("""CREATE TABLE IF NOT EXISTS carga (
        carga_id INT PRIMARY KEY, executada_em TIMESTAMP, geracao_tse VARCHAR,
        pasta VARCHAR, arquivos VARCHAR)""")
    ja = con.execute("SELECT carga_id FROM carga WHERE geracao_tse = ?", [geracao]).fetchone()
    if ja and not args.forcar:
        print(f"A geração {geracao} já foi carregada (carga {ja[0]}). Use --forcar para recarregar.")
        return

    carga = con.execute("SELECT coalesce(max(carga_id), 0) + 1 FROM carga").fetchone()[0]
    con.execute("BEGIN")
    try:
        con.execute("INSERT INTO carga VALUES (?, ?, ?, ?, ?)",
                    [carga, datetime.now(), geracao, str(raiz),
                     ", ".join(sorted(p.name for p in arquivos.values()))])
        for prefixo, df in dfs.items():
            gravar_raw(con, f"raw_{prefixo}", df, carga)
        con.execute(MACROS)
        con.execute(MODELO.replace("$carga", str(carga)))
        n_alt = registrar_alteracoes(con, carga)

        con.execute("""CREATE TABLE IF NOT EXISTS qualidade (
            carga_id INT, verificacao VARCHAR, quantidade BIGINT)""")
        for nome, sql in QUALIDADE:
            con.execute("INSERT INTO qualidade VALUES (?, ?, ?)",
                        [carga, nome, con.execute(sql).fetchone()[0]])
        for nome, v in metricas.items():
            con.execute("INSERT INTO qualidade VALUES (?, ?, ?)", [carga, nome, v])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    print(f"\nCarga {carga} concluída (geração TSE {geracao}). Alterações vs. carga anterior: {n_alt}")
    print("\nVerificações de qualidade:")
    for nome, qtd in con.execute("SELECT verificacao, quantidade FROM qualidade WHERE carga_id=?",
                                 [carga]).fetchall():
        print(f"  {qtd:>8,}  {nome}")


if __name__ == "__main__":
    main()
