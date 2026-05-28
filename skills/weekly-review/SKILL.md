---
name: weekly-review
description: Wizard GTD weekly review consumindo headings de daily-journal cross-journals
disable-model-invocation: false
---

# weekly-review

Wizard GTD que itera Inbox/Doing/Waiting blocks de journals recentes, prompto operador a classificar cada item (Manter / Próximo passo / Arquivar / Adiar), aplica mudanças no graph, e escreve bloco semanal no journal de hoje seguindo schema `~/Notes/logseq/pages/weekly-review.md`.

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 5.

Skill **não consome papéis canonical do toolkit** (Resolution protocol per ADR-003 do `pragmatic-dev-toolkit`, aplicado vazio). Cutucada de descoberta **não aplica**.

## Argumentos

Sem argumentos. Skill opera sobre `~/Notes/logseq/journals/` cross-files.

## Passos

### 1. Gates (cheap-first)

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/weekly-review exige git repo (cwd default é repo do operador; nenhum side-effect crítico mas mantém pattern)`. Exit clean.

`pgrep -x logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /weekly-review (skill escreve direto no filesystem do graph)`. Exit clean.

### 2. Coleta blocks via parsing de headings cross-journals

Resolve metadata:

- **Journals dir**: `~/Notes/logseq/journals/`. Ausente → recusa com `Logseq journals dir ausente em ~/Notes/logseq/journals/ — graph não configurado`. Exit.
- **Janela temporal**: últimos 7 dias **excluindo journal de hoje** (range `[hoje-7d, hoje-1d]`). Razão: bloco semanal escrito no journal de hoje pode duplicar com `## Inbox` de hoje se incluído. Lista: `find ~/Notes/logseq/journals -name '*.md' -newermt '7 days ago' ! -newermt 'today'` (fixo nesta versão per ADR-001 Sub-decisão 5; reabrir via Gatilho 3).
- **Template path**: `~/Notes/logseq/pages/weekly-review.md`. Ausente → recusa com `Template weekly-review.md ausente em ~/Notes/logseq/pages/ — feature requer Onda 4 do meta-sistema (Bloco 1 commit 364465e no logseq-notes)`. Exit.

Para cada journal file na janela, parse 3 listas:

- **Inbox**: blocos descendentes de heading `## Inbox` (regex linha estrita `^\t- ## Inbox`). Coleta blocos imediatamente abaixo até próximo heading sibling (`^\t- ## ` mesma indentação) ou EOF. Filtros (sintaxe Logseq canonical):
  - (a) bloco-pai (heading) sem property `archived:: true` na linha imediatamente subsequente sub-indented por 1 tab adicional (`^\t\tarchived:: true`).
  - (b) bloco-filho sem property `archived:: true` análoga (linha do bloco ou linha imediatamente subsequente sub-indented).
- **Doing / Next Actions**: blocos descendentes de `## Doing` (mesma mecânica).
- **Waiting**: blocos descendentes de `## Waiting` (mesma mecânica).

**NÃO** filtrar por `status:: active` ou `status:: ` qualquer — essa property é lifecycle de Project Page per ADR-004 invariante; colapsar pegaria 18+ Project Pages como falsos Next Actions.

Cada item coletado armazena: source file path, line number, bloco content (texto após `- `).

**Truncate**: max 20 itens por categoria (60 total potencial). Excesso → warning `<categoria> tem <N> blocos; truncado em 20. Categoria precisa atenção dedicada — invoque /weekly-review novamente após classificar primeiros 20.`

**Ambas listas vazias** (Inbox + Doing + Waiting = 0) → recusa silenciosa com mensagem `Sem blocos pra review nos últimos 7 dias de journals. Nada a fazer.`. Exit clean.

### 3. Wizard iterativo de classificação (decisões acumuladas, edits deferred)

Skill **acumula decisões em memória** durante wizard; edits no graph aplicam **somente após** Step 4 compor o bloco semanal (atomic-ish). Crash/cancel mid-wizard → zero side-effect no graph; operador re-invoca sem state parcial.

Para cada item, batch de 4 perguntas por chamada `AskUserQuestion` (cardinality max per CLAUDE.md do toolkit):

- Header: `Item N/M` onde N = índice corrente, M = total da categoria.
- Question: `<categoria>: <bloco content truncado em 80 chars>... — Como classificar?`
- Options:
  - `Manter aqui` — bloco permanece intocado (decision = `keep`).
  - `Próximo passo definido` — Other → operador descreve próximo passo em prosa livre (decision = `next_step`, payload = descrição).
  - `Arquivar` — bloco recebe `archived:: true` no commit batch (decision = `archive`).
  - `Adiar próxima semana` — bloco move pra journal de próxima segunda-feira (decision = `defer`).

Após N % 4 == 0 (cada 4 itens), check progresso via `Continuar? <X/M itens restantes>` enum: `Continuar / Pausar e fechar resumo parcial`. Pausa → pula direto pra Step 4 com decisões coletadas; itens não-vistos recebem decision sentinel `not_reviewed` (aparecem no bloco semanal com sufixo `[não-revisado]`, sem edit no source).

**Cálculo "próxima segunda"** pra decisão `defer`: `$(date -u -d 'next Monday' +%Y_%m_%d)`. Comportamento canonical do GNU date: se hoje é segunda, "next Monday" pula 7 dias (mesmo dia da próxima semana). Aceito — operador adiando segunda intencionalmente quer next-next monday. Bloco move pra journal de destino sob **heading de origem** (Inbox → ## Inbox; Doing → ## Doing; Waiting → ## Waiting). Heading ausente no journal de destino → append no fim do file + warning loud `heading "## <categoria>" não encontrada no journal de destino <path>; bloco appended no fim — verificar daily-journal template ou indentação` (failure-closed paralelo a `/journal-close`).

### 4. Compor bloco semanal literal seguindo schema

Lê template `~/Notes/logseq/pages/weekly-review.md`. Parseia placeholders:

- `<inbox-blocks>` → lista resolved pós-classificação: cada item formatado por sufixo conforme decisão:
  - `keep` → `- <bloco content>` (sem sufixo).
  - `archive` → `- <bloco content> [arquivado]`.
  - `next_step` → `- <bloco content> [próximo passo: <descrição>]`.
  - `defer` → `- <bloco content> [adiado pra <data próxima segunda>]`.
  - `not_reviewed` → `- <bloco content> [não-revisado]` (operador pausou wizard antes de chegar).
- `<doing-blocks>` → análogo.
- `<waiting-blocks>` → análogo.

Headings `## Decisões da semana` e `## Próxima semana` ficam como skeleton vazio no template — operador edita depois manualmente no Logseq desktop.

Date placeholder `<% today %>` do template Logseq → substituir por `$(date -u +%Y-%m-%d)` literal (UTC, alinhado com journal filename pattern).

### 5. Aplicar edits batch + Append no journal de hoje

**Atomic-ish batch** (deferred do Step 3): para cada decisão acumulada em memória, aplica edit no source file na ordem coletada:

- `archive` → adiciona linha sub-indented `\t\tarchived:: true` imediatamente após o bloco source.
- `next_step` → adiciona linha sub-indented `\t\t- <descrição>` como sub-bloco do source.
- `defer` → remove bloco do source file + adiciona no journal de destino sob heading de origem (cálculo per Step 3; criar journal se ausente via daily-journal template body copy).
- `keep` / `not_reviewed` → no-op (source preservado).

Após todos os edits source, **append do bloco semanal** no journal path de hoje (`~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md`):

- Journal existe → append no fim do file (bloco semanal é top-level resultado da review, não tenta heading-aggregator).
- Journal ausente → criar via leitura do daily-journal template (mesma mecânica do `/journal-note`); append do bloco no fim.

### 6. Reportar

Resumo final:
- Total de itens classificados por categoria (Inbox/Doing/Waiting).
- Distribuição de classificações (`X mantidos, Y arquivados, Z adiados, W com próximo passo`).
- Path do journal tocado.

Exit.

## O que NÃO fazer

- Não filtrar por `status:: active` ou `status::` qualquer — essa property é lifecycle de Project Page per ADR-004; coletar via heading-aggregator é o pattern doutrinário.
- Não rodar queries Logseq Datalog — desktop fechado por gate; parsing direto via filesystem markdown é canonical.
- Não persistir state entre invocações — skill é stateless; cada invocação re-parse a janela.
- Não substituir block-ref `((weekly-review))` — schema-only template per ADR-001 Sub-decisão 2; skill faz literal append.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não parametrizar truncate (20) ou janela (7d) hardcoded — flags `--max-items <N>` / `--window-days <N>` reabrem via Gatilho 3 do ADR-001 se sinal real surgir.
- Não tenta escrever em pages/<categoria>.md aggregator-style — review é per-journal aggregation, não materializa view permanente fora do journal de hoje.
- Não tratar headings rebaixados/promovidos manualmente pelo operador no Logseq desktop (`\t\t- ## Inbox` em vez de `\t- ## Inbox`) — regex strict assume indentação canonical de daily-journal template. Recovery é manual via UI. Se journal canonical não tem **nenhum** dos 3 headings em formato estrito, skill reporta warning como sinal de drift.
- Não incluir journal de hoje na janela de coleta — bloco semanal é appended em journal de hoje; incluí-lo duplicaria items vivos com snapshot.
