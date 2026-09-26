"""
Inventário dos datasets do TSE — Eleições 2026 (passo 0 da ingestão)

Uso:
    pip install duckdb
    python inventario_tse.py "C:\\caminho\\para\\pasta_dos_datasets"

O que faz:
  - percorre a pasta (inclusive subpastas);
  - extrai de cada .zip SOMENTE os .csv/.txt para <pasta>/_extraido (PDFs e fotos não são extraídos);
  - para cada CSV: detecta encoding, conta linhas, lista colunas, % de nulos
    e, para colunas de poucos valores distintos (códigos/categorias), mostra os valores;
  - gera inventario_tse.md (para enviar ao Claude) e inventario_tse.json.

Não altera nenhum arquivo original. Não copia nomes, CPFs ou outros dados individuais
para o relatório: só estrutura, contagens e valores de colunas categóricas.
"""
import json
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import duckdb

MAX_DISTINTOS = 30          # até quantos valores distintos a coluna é tratada como categórica
NULOS_TSE = ("#NULO", "#NULO#", "#NE", "#NE#", "")   # marcadores de ausência usados pelo TSE


def extrair_zips(raiz: Path) -> Path:
    destino = raiz / "_extraido"
    destino.mkdir(exist_ok=True)
    for z in raiz.rglob("*.zip"):
        try:
            with zipfile.ZipFile(z) as zf:
                for membro in zf.namelist():
                    if membro.lower().endswith((".csv", ".txt")):
                        alvo = destino / z.stem / Path(membro).name
                        if not alvo.exists():
                            alvo.parent.mkdir(parents=True, exist_ok=True)
                            alvo.write_bytes(zf.read(membro))
        except zipfile.BadZipFile:
            print(f"[aviso] ZIP corrompido: {z}")
    return destino


def detectar_encoding(arquivo: Path) -> str:
    amostra = arquivo.read_bytes()[:200_000]
    try:
        amostra.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def perfilar_csv(con, arquivo: Path) -> dict:
    enc = detectar_encoding(arquivo)
    origem = (f"read_csv('{arquivo.as_posix()}', delim=';', header=true, quote='\"', "
              f"all_varchar=true, encoding='{enc}', ignore_errors=false)")
    info = {"arquivo": str(arquivo), "tamanho_mb": round(arquivo.stat().st_size / 1e6, 2),
            "encoding": enc, "linhas": None, "colunas": [], "erro": None}
    try:
        info["linhas"] = con.execute(f"SELECT count(*) FROM {origem}").fetchone()[0]
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {origem}").fetchall()]
        marcadores = ", ".join(f"'{m}'" for m in NULOS_TSE)
        for c in cols:
            q = f'"{c}"'
            nulos, distintos = con.execute(
                f"SELECT count(*) FILTER (WHERE {q} IS NULL OR trim({q}) IN ({marcadores})), "
                f"count(DISTINCT {q}) FROM {origem}").fetchone()
            col = {"nome": c, "pct_nulos": round(100 * nulos / max(info["linhas"], 1), 1),
                   "distintos": distintos}
            if distintos <= MAX_DISTINTOS:
                col["valores"] = [r[0] for r in con.execute(
                    f"SELECT {q}, count(*) n FROM {origem} GROUP BY 1 ORDER BY n DESC").fetchall()]
            info["colunas"].append(col)
    except Exception as e:  # registra o problema em vez de "corrigir" silenciosamente
        info["erro"] = str(e)[:500]
    return info


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python inventario_tse.py "caminho/da/pasta"')
    raiz = Path(sys.argv[1]).expanduser().resolve()
    print(f"Inventariando {raiz} ...")

    extensoes = Counter(p.suffix.lower() for p in raiz.rglob("*") if p.is_file()
                        and "_extraido" not in p.parts)
    zips = sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*.zip"))
    extraido = extrair_zips(raiz)

    csvs = sorted({p for p in raiz.rglob("*") if p.suffix.lower() in (".csv", ".txt")})
    con = duckdb.connect()
    perfis = []
    for i, arq in enumerate(csvs, 1):
        print(f"  [{i}/{len(csvs)}] {arq.name}")
        perfis.append(perfilar_csv(con, arq))

    relatorio = {"gerado_em": datetime.now().isoformat(timespec="seconds"),
                 "pasta": str(raiz), "extensoes": dict(extensoes), "zips": zips,
                 "csvs": perfis}
    Path("inventario_tse.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1),
                                            encoding="utf-8")

    # Markdown compacto: arquivos do mesmo layout (ex.: um por UF) aparecem agrupados
    linhas = [f"# Inventário TSE — {relatorio['gerado_em']}", "",
              f"Extensões: {dict(extensoes)}", "", "## ZIPs", *[f"- {z}" for z in zips], ""]
    por_layout = {}
    for p in perfis:
        chave = tuple(c["nome"] for c in p["colunas"]) or ("ERRO", p["arquivo"])
        por_layout.setdefault(chave, []).append(p)
    for n, (chave, grupo) in enumerate(por_layout.items(), 1):
        total = sum(g["linhas"] or 0 for g in grupo)
        linhas.append(f"## Layout {n} — {len(grupo)} arquivo(s), {total:,} linhas no total")
        for g in grupo:
            linhas.append(f"- `{Path(g['arquivo']).name}` — {g['linhas']} linhas, "
                          f"{g['tamanho_mb']} MB, {g['encoding']}"
                          + (f" — **ERRO:** {g['erro']}" if g["erro"] else ""))
        base = max(grupo, key=lambda g: g["linhas"] or 0)
        linhas.append("")
        for c in base["colunas"]:
            extra = f" → {c['valores']}" if "valores" in c else ""
            linhas.append(f"  - {c['nome']} ({c['pct_nulos']}% nulos, {c['distintos']} distintos){extra}")
        linhas.append("")
    Path("inventario_tse.md").write_text("\n".join(linhas), encoding="utf-8")
    print("\nPronto: inventario_tse.md e inventario_tse.json gerados na pasta atual.")


if __name__ == "__main__":
    main()
