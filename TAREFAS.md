# Tarefas — em ordem

Faça uma tarefa por vez. Ao terminar cada uma: testes passando, teste de neutralidade feito,
resumo do que mudou. Prioridade: T1–T6 antes do 1º turno (04/10/2026).

## T1 — Estrutura do repositório
- Pastas: `ingestao/` (scripts atuais), `backend/`, `frontend/`, `tests/`, `docs/`.
- `backend/pyproject.toml` (ou requirements) com fastapi, uvicorn, duckdb, pandas, pytest, httpx, openpyxl.
- Fixture pytest que roda `tests/gerar_dados_sinteticos.py` + `ingestao_tse.py` num diretório temporário
  e entrega um banco de teste. Testar também uma 2ª carga (verifica `alteracao`).
- **Aceite:** `pytest` passa do zero, sem os dados reais.

## T2 — Busca de candidatos: `GET /api/candidatos`
- Parâmetros: `q` (nome completo, nome de urna ou número), filtros `uf`, `cd_cargo`, `sg_partido`,
  `federacao`, `situacao`, `genero`, `cor_raca`, `grau_instrucao`, `idade_min/max`, `na_urna`; paginação; ordenação por coluna.
- Tolerância a erro de digitação e acentos: `strip_accents(lower())` + `ILIKE` e, como reforço,
  `jaro_winkler_similarity` do DuckDB. Resultado exato vem antes do aproximado.
- Pessoas com 2 registros (`qt_outros_registros_2026 > 0`) vêm sinalizadas.
- `GET /api/filtros`: valores distintos para montar os filtros.
- **Aceite:** "bolsonaro", "BOLSONARO", "bolsonar" e "bolsonáro" encontram os mesmos registros no banco real; resposta < 300 ms.

## T3 — Candidato: `GET /api/candidatos/{sq}`
- Seções: identificação, perfil, situação (com `situacao_campo_origem`), patrimônio (total, qtd,
  por tipo, maiores bens), redes, histórico (linha do tempo), fundamentos de indeferimento,
  outros registros da mesma pessoa (só o `sq`, nunca o `pessoa_id`).
- Cada campo com bloco de fonte (ver CLAUDE.md). Histórico indisponível → mensagem explícita.
- `GET /api/fonte?tabela=&sq=&campo=` devolve dataset, arquivo, linha, geração.
- **Aceite:** nenhum campo nulo vira 0 ou texto inventado.

## T4 — Categorias de bens (CÁLCULO documentado)
- Consultar os 49 `tipo` distintos e mapear para: Imóveis, Veículos, Aplicações financeiras,
  Participações societárias, Depósitos/dinheiro, Outros. Mapa num CSV versionado
  (`ingestao/categorias_bens.csv`) e carregado como tabela; nada hardcoded.
- Na UI, a categoria aparece como CÁLCULO com link para o mapa.

## T5 — Estatísticas de grupo: `GET /api/estatisticas`
- Entrada: universo (ano, `cd_cargo`, `uf`, filtros) + métrica (`total_bens`, `idade_na_posse`, ...).
- Saída: n, média, mediana, mín, máx, desvio padrão, percentis (10/25/50/75/90), histograma,
  distribuições categóricas e cruzamentos (ex.: gênero × escolaridade, partido × gênero).
- `GET /api/candidatos/{sq}/posicao?metrica=`: percentil do candidato no universo padrão (mesmo cargo + UF).
- Candidatos que não declararam bens: contar à parte e dizer se entram ou não no cálculo.

## T6 — Comparador: `GET /api/comparar?sq=...` (2 a 5)
- Tabela lado a lado: perfil, eleitoral, patrimônio, histórico, redes.
- Detectar e alertar: mesmo cargo? mesma UF? mesmo partido? histórico disponível para todos?
  Se universos diferentes: "Os candidatos pertencem a cargos/UFs diferentes. Algumas comparações
  estatísticas não são diretamente equivalentes."
- Bloco "Principais diferenças encontradas nos dados", só fatos (ex.: "A declarou 12 bens; B declarou 3").
- **Aceite:** nenhuma frase conclusiva ou avaliativa.

## T7 — Frontend (Next.js)
- Sidebar: Início, Candidatos, Comparar, Partidos, Estados, Patrimônio, Propostas, Histórico,
  Investigar, Pergunte aos dados, Qualidade dos dados, Fontes. Itens ainda não prontos: "em breve".
- Telas nesta tarefa: Dashboard (cards + totais por cargo com filtros), Busca (tabela com filtros,
  ordenação, paginação), Página do candidato, Comparar (seleção de até 5 candidatos, persistida localmente).
- Todo gráfico com título, unidade, universo, período e fonte. Nada de 3D ou decorativo.
- Selo de natureza (DADO/CÁLCULO/...) e botão "Ver fonte" nos campos.
- Rodapé fixo: data/hora da geração TSE da carga atual.

## T8 — Exportação
- CSV e Excel das tabelas (busca, comparação, estatísticas), com aba/cabeçalho de metadados:
  fonte, geração TSE, universo, filtros aplicados, data da consulta.

## T9 — Qualidade e Alterações
- Tela "Qualidade dos dados" lendo `qualidade` e `carga`.
- Tela "Alterações desde a última atualização" lendo `alteracao` (deferido → indeferido, renúncia, novos bens...).

## T10 — Pergunte aos dados (IA)
- Ferramentas = funções do backend: search_candidates, get_candidate, compare_candidates,
  get_candidate_assets, get_candidate_history, get_party_statistics, get_state_statistics,
  calculate_statistics, get_source. Sem acesso direto ao banco.
- Resposta mostra: critério (como a pergunta foi interpretada), dados usados, cálculo, fonte, data da base.
- Recusar pedidos de recomendação de voto, ranking de "melhores" ou inferências pessoais, explicando o motivo e oferecendo a versão factual.
- SQL livre (se um dia existir): só SELECT, read-only, LIMIT, log.

## Depois do MVP
Propostas (PDF → texto → temas, sem avaliar mérito), fotos, evolução patrimonial com bens de
eleições anteriores (usar `historico.sq_candidato` + arquivos `bem_candidato_<ano>`), página de
partidos e mapa, modo Investigar (dossiê factual), relatório PDF, resultados após a apuração,
migração para PostgreSQL.
