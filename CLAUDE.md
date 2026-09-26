# Laboratório de Análise Eleitoral — Eleições 2026

Aplicação web para explorar, comparar e analisar candidaturas das Eleições Gerais 2026
(1º turno em 04/10/2026) a partir dos dados abertos oficiais do TSE
(https://dadosabertos.tse.jus.br/dataset/candidatos-2026).

**Regra principal:** o app responde "quais são os dados e o que se observa objetivamente neles",
nunca "em quem votar". Fluxo: PERGUNTA → DADOS → CRUZAMENTO → CÁLCULO → CONTEXTO → FONTE → usuário conclui.

## Regras inegociáveis (aplicam-se a código, textos da UI, endpoints e prompts de IA)

1. **Neutralidade.** Não criar: melhor/pior candidato, candidato ideal, scores (qualidade, honestidade,
   competência), ranking de candidatos ou partidos, recomendação de voto. Ordenar uma tabela por uma
   coluna escolhida pelo usuário é permitido; um endpoint ou tela de "ranking" não é.
   - Permitido: "Patrimônio declarado acima da mediana do grupo." / "Possui 3 candidaturas anteriores identificadas."
   - Proibido: "Candidato financeiramente mais preparado." / "É um político experiente."
2. **Rótulo de natureza da informação.** Toda informação exibida é de um tipo:
   `DADO` (direto da base), `CALCULO` (métrica derivada), `ANALISE` (interpretação estatística),
   `FONTE_EXTERNA`, `DECLARACAO_CANDIDATO`, `CONTEXTO`. Nunca apresentar interpretação como fato.
3. **Universo explícito.** Toda estatística comparativa informa o universo
   (ex.: "percentil entre candidatos a Deputado Federal no RJ em 2026, n = 1.234"). Nunca comparar
   populações incompatíveis sem alerta.
4. **Ausência ≠ zero.** Dado ausente aparece como "não disponível no dataset utilizado", nunca como
   estimativa, zero ou "provavelmente não". Ver `historico_disponivel` abaixo.
5. **Rastreabilidade.** Toda informação relevante tem "Ver fonte": dataset, arquivo, linha, campo,
   data/hora de geração do TSE. Todas as tabelas finais têm `fonte_arquivo` e `fonte_linha`.
6. **Nunca corrigir dado oficial em silêncio.** Transformações ficam documentadas no código (SQL
   comentado) e medidas na tabela `qualidade`.
7. **Privacidade.** Não inferir personalidade, caráter, honestidade, saúde, religião, orientação
   sexual, intenções. Processo/indeferimento não é culpa: mostrar exatamente o dado e sua situação,
   sem linguagem acusatória. Preferências salvas pelo usuário nunca são usadas para inferir preferência política.
8. **IA só com dados.** A camada de IA usa ferramentas (funções da API) e só explica o que elas
   retornaram. SQL gerado por IA: somente SELECT, conexão read-only, LIMIT obrigatório, consulta registrada em log.

## Estado atual

- `ingestao/inventario_tse.py`: perfila os CSVs/ZIPs do TSE (estrutura, sem dados pessoais).
- `ingestao/ingestao_tse.py`: carga versionada em DuckDB (`eleicoes.duckdb`). Uso:
  `python ingestao/ingestao_tse.py "<pasta dos zips>"`. Rodar de novo com nova geração do TSE
  cria nova carga e registra diferenças em `alteracao`.
- Estrutura: `ingestao/`, `backend/`, `frontend/`, `tests/`, `docs/`
  (`docs/inventario_tse.md` = saída do inventário).
- API (`backend/app/`): `ELEICOES_DB=eleicoes.duckdb uvicorn app.main:app --app-dir backend`.
  `db.py` (conexão read-only, cursor por requisição), `metadados.py` (natureza + fonte TSE de cada
  campo exposto), `rotas/candidatos.py` (`GET /api/candidatos`, `GET /api/filtros`),
  `rotas/candidato.py` (`GET /api/candidatos/{sq}` com seções, cada campo com natureza + fonte;
  `GET /api/fonte?tabela=&sq=&campo=[&nr_ordem=|&linha=]` devolve arquivo, linha e o texto
  original do CSV lido das tabelas `raw_*`), `rotas/bens.py` (`GET /api/categorias-bens`),
  `rotas/estatisticas.py` (`GET /api/estatisticas`, `GET /api/estatisticas/metricas`,
  `GET /api/candidatos/{sq}/posicao`). `universo.py` define o recorte (filtros comuns à busca e às
  estatísticas), gera a descrição em texto e os alertas (cargos/UFs misturados, n < 30).
  Estatísticas: registros sem o dado ficam fora do cálculo e são contados em `n_sem_dado` com o
  motivo; posição do candidato = percentil (posição média) + relação com a mediana, nunca "nº X de Y".
  `rotas/comparar.py` (`GET /api/comparar?sq=1&sq=2` ou `?sq=1,2`, 2 a 5): tabela lado a lado com
  fonte por valor, verificações (mesmo cargo/UF/partido, histórico e bens disponíveis, mesma pessoa),
  alertas e "Principais diferenças encontradas nos dados" (só fatos; moeda não formatada no texto).
- Frontend (`frontend/`, Next.js 16 + React 19 + Tailwind 4 + ECharts): `npm install`, `npm run build`,
  `npm start` (porta 3000; `API_URL` = backend, padrão http://localhost:8000 — `/api/*` é repassado
  pelo `next.config.ts`). Telas: Início (cartões + candidaturas por cargo + patrimônio, com filtros),
  Candidatos (busca com filtros/ordenação/paginação na URL), Candidato (`/candidatos/[sq]`) e Comparar
  (seleção de até 5 no localStorage). `components/FiguraGrafico` exige título, unidade, universo,
  período e fonte e oferece "Ver tabela"; `SeloNatureza` + `VerFonte` em cada campo; cores como
  tokens em `app/globals.css` (claro/escuro). Moeda formatada só em `lib/formato.ts`; códigos
  (sq_/nr_/cd_) nunca ganham separador de milhar. Checagem: `npm run typecheck` e `npm run build`.
  `GET /api/carga` (backend) alimenta o rodapé com a geração TSE da carga atual.
- T9: `rotas/qualidade.py` — `GET /api/cargas`, `GET /api/qualidade[?carga_id=]` (verificações da
  carga + valor da carga anterior + explicação em texto de cada verificação em `EXPLICACOES`; nova
  verificação na ingestão exige explicação, há teste) e `GET /api/alteracoes[?carga_id=&campo=&uf=&cd_cargo=]`
  (resumo por campo, transições de situação, itens; candidato removido usa dados da carga anterior).
  Telas `/qualidade` e `/alteracoes` no frontend.
- Teste de neutralidade automatizado em `tests/test_api_comparar.py` (regex de termos avaliativos
  sobre o texto gerado; valores vindos da base são retirados antes). Gerador `v3` = v1 + candidatos
  em outro cargo (40) e outra UF (41).
- Categorias de bens: mapa versionado `ingestao/categorias_bens.csv` (tipo;categoria;observacao,
  UTF-8) carregado na ingestão como tabela `categoria_bem`; `bem.categoria` é CÁLCULO. Tipo fora do
  mapa fica com categoria NULL e é medido em `qualidade`. Mudou o mapa? Rodar a ingestão com `--forcar`.
  A busca normaliza nome e termo (minúsculas, sem acento, sem pontuação); correspondência
  "exata" (trecho) vem antes da "aproximada" (Jaro-Winkler >= 0,90 por palavra de 4+ letras).
  A API trava o arquivo do DuckDB: pare-a antes de rodar nova carga.
- Testes: `pip install -e "backend[dev]"` e `pytest` na raiz. Fixtures em `tests/conftest.py`
  (`banco_v1` = 1 carga; `banco_v2` = cargas v1+v2 no mesmo banco). O gerador sintético cobre as
  armadilhas abaixo (casos por índice documentados no topo de `tests/gerar_dados_sinteticos.py`).
- Banco real validado: 20.987 candidatos; 19.156 com histórico; 14.670 já concorreram antes;
  5.597 já foram eleitos alguma vez; 266 bens com valor zero; 11 redes órfãs.

## Modelo de dados (DuckDB)

Controle: `carga` (versões), `raw_*` (todas as cargas, colunas do TSE como VARCHAR + `_carga_id`,
`_arquivo`, `_linha`), `snapshot_candidato`, `alteracao`, `qualidade`.

Tabelas finais (reconstruídas a partir da última carga):
- `candidato` — PK `sq_candidato`. Inclui `pessoa_id`, cargo (`cd_cargo`, `ds_cargo`), UF, partido,
  federação, coligação, perfil (gênero, cor_raca, grau_instrucao, estado_civil, ocupacao,
  dt_nascimento, idade_na_posse, nacionalidade), `situacao_candidatura` + `situacao_campo_origem`,
  `situacao_julgamento`, `na_urna`, `substituido`, `declarou_bens`, `limite_gastos`, `resultado`
  (vazio até a apuração), `fonte_*`.
- `bem` (sq_candidato, nr_ordem, tipo, categoria, descricao, valor DECIMAL, valor_original, dt_atualizacao)
- `rede_social` (sq_candidato, nr_ordem, url, plataforma)
- `historico` (sq_candidato_atual → candidaturas desde 2004, com `eleito`, resultado, cargo, partido)
- `fundamento_indeferimento` (vem do arquivo `motivo_cassacao` do TSE — ver armadilhas)
- `vaga` (sg_uf, cd_cargo, qt_vaga), `coligacao`
- `v_candidato` (TABELA materializada na ingestão — antes era VIEW): candidato + `qt_bens`, `total_bens`, `historico_disponivel`,
  `qt_candidaturas_anteriores`, `qt_vezes_eleito`, `ultimo_cargo_eleito`, `qt_outros_registros_2026`.

## Armadilhas já descobertas nos dados do TSE (não redescobrir)

- Cada dataset vem por UF + `_BR` + `_BRASIL`; **`_BRASIL` = soma de todos**. Ingerir só `_BRASIL`.
- CSVs em latin-1, `;`, tudo entre aspas. Ausência: `#NULO`, `#NE` → NULL. "NÃO DIVULGÁVEL" é informação, manter.
- `DS_SITUACAO_CANDIDATURA` do `consulta_cand` é 100% `#NE`. Situação real está no complementar:
  `DS_SITUACAO_CANDIDATO_TOT`; para quem saiu da urna (renúncia, indeferido, cancelado...) esse campo
  é `#NULO` e a situação está em `DS_SITUACAO_JULGAMENTO` (1.070 casos). Já tratado com coalesce.
- `ST_REELEICAO` vem vazio: reeleição/experiência deriva do `historico`.
- **1.831 candidatos não aparecem no arquivo de histórico** (nem a linha de 2026). Isso é
  "histórico indisponível", NÃO "estreante". Usar `historico_disponivel`; métricas de histórico
  devem excluir esse grupo e dizer isso.
- ~107 pessoas têm 2 registros (normalmente renunciou e registrou de novo, às vezes outro cargo).
  Ligar por `pessoa_id` (HMAC do CPF com chave local). Busca deve agrupar/indicar isso.
- **`historico` tem uma linha por turno**: quem foi ao 2º turno aparece 2 vezes no mesmo ano/cargo
  (turno 1 = "2º turno", turno 2 = resultado final; 637 casos no banco real). Contagens de
  candidaturas usam ano + `cd_cargo` + UF + UE e "eleito" = algum turno eleito (já feito em `v_candidato`).
- Arquivo `motivo_cassacao` contém **fundamentos legais de indeferimento**, não cassações. Rotular assim.
- `DS_CARGO` muda de grafia entre arquivos ("DEPUTADO FEDERAL", "Deputado Federal", "2. Suplente").
  **Juntar sempre por `cd_cargo`.** Em `historico` há 18 grafias para 13 códigos.
- Valores de bens podem vir com vírgula ou ponto decimal; macro `valor()` trata os dois.
- Proporcionais (Dep. Federal/Estadual/Distrital): circunscrição é a UF, não o município.
- O TSE regera os arquivos várias vezes ao dia até a eleição; situações mudam.
- Certidões criminais, fotos e propostas vêm como ZIP de PDFs/JPEGs (ainda não ingeridos).
  Certidões: só link/arquivo original; IA nunca resume ou interpreta certidão.

## Privacidade de dados

CPF, título eleitoral e e-mail são descartados na leitura e não existem no banco.
O arquivo `eleicoes.chave` (chave do `pessoa_id`) **nunca** vai para o Git (ver `.gitignore`).
Nunca expor `pessoa_id` na UI ou em exportações.

## Stack

- Dados: DuckDB (MVP), SQL portável para PostgreSQL depois.
- Backend: Python 3.11+, FastAPI, conexão DuckDB **read_only=True** na API.
- Frontend: Next.js + React + TypeScript, Tailwind, Apache ECharts. Português (pt-BR) na UI.
- Testes: pytest com banco gerado por `tests/gerar_dados_sinteticos.py` (nunca depender dos dados reais).

## Convenções

- Toda resposta de API que traz dado ou métrica inclui um bloco:
  `{"natureza": "DADO|CALCULO|...", "fonte": {"dataset", "arquivo", "linha", "campo"}, "geracao_tse": "...",
    "universo": {"descricao", "n"} (quando houver comparação)}`.
- Nomes em português, snake_case. Moeda em BRL formatada só no frontend.
- Nenhum texto gerado (UI ou IA) usa adjetivos avaliativos sobre candidatos.
- Antes de concluir uma tarefa: rodar testes e rodar um "teste de neutralidade" (grep por termos
  como "melhor", "pior", "ranking", "score", "ideal", "experiente", "rico" em textos da UI e prompts).
