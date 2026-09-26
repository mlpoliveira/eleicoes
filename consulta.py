import duckdb
con = duckdb.connect("eleicoes.duckdb", read_only=True)
for v, q in con.execute("""SELECT verificacao, quantidade FROM qualidade
                    WHERE carga_id = (SELECT max(carga_id) FROM carga)""").fetchall():
    print(f"{q:>8}  {v}")