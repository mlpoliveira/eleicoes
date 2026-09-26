"""
Universo de candidaturas: o recorte sobre o qual uma busca ou estatística é feita.

Os mesmos filtros servem à busca (/api/candidatos) e às estatísticas (/api/estatisticas), para
que "o grupo" signifique sempre a mesma coisa. Toda estatística comparativa informa o universo
em texto (descricao) e o tamanho (n) — regra 3 do CLAUDE.md.
"""
from dataclasses import dataclass, field

from fastapi import HTTPException, Query

from .db import consultar

ANO_DISPONIVEL = 2026
MIN_N_ESTAVEL = 30   # abaixo disso, avisar que as medidas variam muito


def fmt_n(n: int) -> str:
    """Inteiro no formato pt-BR (1.234)."""
    return f"{n:,}".replace(",", ".")


@dataclass
class Universo:
    uf: list[str] = field(default_factory=list)
    cd_cargo: list[int] = field(default_factory=list)
    sg_partido: list[str] = field(default_factory=list)
    federacao: list[str] = field(default_factory=list)
    situacao: list[str] = field(default_factory=list)
    genero: list[str] = field(default_factory=list)
    cor_raca: list[str] = field(default_factory=list)
    grau_instrucao: list[str] = field(default_factory=list)
    idade_min: int | None = None
    idade_max: int | None = None
    na_urna: bool | None = None

    # parâmetro -> coluna de v_candidato
    LISTAS = {"uf": "sg_uf", "cd_cargo": "cd_cargo", "sg_partido": "sg_partido",
              "federacao": "nm_federacao", "situacao": "situacao_candidatura",
              "genero": "genero", "cor_raca": "cor_raca", "grau_instrucao": "grau_instrucao"}
    ROTULOS = {"sg_partido": "partido", "federacao": "federação", "situacao": "situação",
               "genero": "gênero", "cor_raca": "cor/raça", "grau_instrucao": "grau de instrução"}

    def __post_init__(self):
        self.uf = [u.upper() for u in self.uf]
        for nome in self.LISTAS:
            setattr(self, nome, [v for v in getattr(self, nome) if v not in (None, "")])

    def where(self) -> tuple[list[str], list]:
        where, params = [], []
        for nome, col in self.LISTAS.items():
            valores = getattr(self, nome)
            if valores:
                where.append(f"{col} IN ({', '.join('?' * len(valores))})")
                params.extend(valores)
        if self.idade_min is not None:
            where.append("idade_na_posse >= ?"); params.append(self.idade_min)
        if self.idade_max is not None:
            where.append("idade_na_posse <= ?"); params.append(self.idade_max)
        if self.na_urna is not None:
            where.append("na_urna = ?"); params.append(self.na_urna)
        return where, params

    def sql(self) -> tuple[str, list]:
        """Cláusula WHERE completa (ou vazia) e parâmetros."""
        where, params = self.where()
        return ("WHERE " + " AND ".join(where) if where else ""), params

    def filtros(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [])}

    def descricao(self, cur) -> str:
        """Ex.: 'Candidaturas a Deputado Estadual em RJ — Eleições 2026; filtros: gênero = ...'."""
        if self.cd_cargo:
            rotulos = consultar(cur, f"""
                SELECT cd_cargo, min(ds_cargo) AS ds FROM candidato
                WHERE cd_cargo IN ({', '.join('?' * len(self.cd_cargo))})
                GROUP BY 1 ORDER BY 1""", self.cd_cargo)
            nomes = {r["cd_cargo"]: r["ds"].title() for r in rotulos}
            cargos = " / ".join(nomes.get(c, f"cargo {c}") for c in self.cd_cargo)
        else:
            cargos = "todos os cargos"
        ufs = ", ".join(self.uf) if self.uf else "todas as UFs"
        texto = f"Candidaturas a {cargos} em {ufs} — Eleições {ANO_DISPONIVEL}"
        extras = []
        for nome in ("sg_partido", "federacao", "situacao", "genero", "cor_raca",
                     "grau_instrucao"):
            valores = getattr(self, nome)
            if valores:
                extras.append(f"{self.ROTULOS[nome]} = {' ou '.join(map(str, valores))}")
        if self.idade_min is not None or self.idade_max is not None:
            extras.append(f"idade na posse entre {self.idade_min if self.idade_min is not None else '—'}"
                          f" e {self.idade_max if self.idade_max is not None else '—'}")
        if self.na_urna is not None:
            extras.append("na urna = " + ("sim" if self.na_urna else "não"))
        return texto + (f"; filtros: {'; '.join(extras)}" if extras else "")

    def alertas(self, cur) -> list[str]:
        """Avisos sobre populações que não são diretamente comparáveis ou pequenas demais."""
        clausula, params = self.sql()
        r = consultar(cur, f"""
            SELECT count(*) AS n, count(DISTINCT cd_cargo) AS cargos,
                   count(DISTINCT sg_uf) AS ufs,
                   count(*) FILTER (WHERE cd_cargo <> 1) AS n_nao_presidente
            FROM v_candidato {clausula}""", params)[0]
        alertas = []
        if r["n"] == 0:
            alertas.append("Nenhuma candidatura no universo selecionado.")
        elif r["n"] < MIN_N_ESTAVEL:
            alertas.append(f"Universo pequeno (n = {fmt_n(r['n'])}): média, desvio padrão e "
                           "percentis variam muito com poucos registros.")
        if r["cargos"] > 1:
            alertas.append(f"O universo reúne candidaturas a {r['cargos']} cargos diferentes. "
                           "Algumas comparações estatísticas não são diretamente equivalentes.")
        if r["ufs"] > 1 and r["n_nao_presidente"] > 0:
            alertas.append(f"O universo reúne {r['ufs']} UFs; para cargos estaduais e "
                           "proporcionais cada UF é uma disputa (circunscrição) separada.")
        return alertas

    def bloco(self, cur, n: int) -> dict:
        return {"descricao": self.descricao(cur), "n": n, "filtros": self.filtros(),
                "alertas": self.alertas(cur)}


def universo_dos_parametros(
    ano: int = Query(ANO_DISPONIVEL, description="Somente 2026 está disponível"),
    uf: list[str] | None = Query(None),
    cd_cargo: list[int] | None = Query(None),
    sg_partido: list[str] | None = Query(None),
    federacao: list[str] | None = Query(None, description="nome da federação"),
    situacao: list[str] | None = Query(None, description="situação da candidatura"),
    genero: list[str] | None = Query(None),
    cor_raca: list[str] | None = Query(None),
    grau_instrucao: list[str] | None = Query(None),
    idade_min: int | None = Query(None, ge=0, le=130),
    idade_max: int | None = Query(None, ge=0, le=130),
    na_urna: bool | None = None,
) -> Universo:
    """Dependência FastAPI: monta o Universo a partir dos parâmetros da URL."""
    if ano != ANO_DISPONIVEL:
        raise HTTPException(422, f"Ano {ano} não disponível no dataset utilizado "
                                 f"(somente {ANO_DISPONIVEL}).")
    return Universo(uf=uf or [], cd_cargo=cd_cargo or [], sg_partido=sg_partido or [],
                    federacao=federacao or [], situacao=situacao or [], genero=genero or [],
                    cor_raca=cor_raca or [], grau_instrucao=grau_instrucao or [],
                    idade_min=idade_min, idade_max=idade_max, na_urna=na_urna)
