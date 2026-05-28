---
name: journal-close
description: Sintetiza sessão CC atual em bloco no journal Logseq de hoje (consome session-close.md schema)
disable-model-invocation: false
---

# journal-close

Sintetiza a sessão CC atual num bloco estruturado no journal Logseq de hoje, seguindo o schema `~/Notes/logseq/pages/session-close.md`. Materializa continuidade cross-session per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 3.

Skill opera **independente** de `CLAUDE.md` / role contract.

## Argumentos

Sem argumentos. Skill coleta context da sessão CC corrente via probe do git + filesystem.

## Passos

### 1. Gates (cheap-first)

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/journal-close exige git repo (skill deriva repo basename do cwd)`. Exit clean.

`pgrep -x logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-close`. Exit clean.

### 2. Coleta context

- **Repo basename**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado):
  1. Variável env `PRAGMATIC_ACTIVE_PLAN_SLUG` exposta por `/run-plan` do `pragmatic-dev-toolkit` (gap conhecido — hoje sempre None nesta probe; ADR-001 Sub-decisão 3 + Gatilho 7).
  2. Probe `docs/plans/*.md` modified nas últimas 2 horas (`find docs/plans -name '*.md' -newermt '2 hours ago'`). Múltiplos → mais recente (`ls -t`).
  3. Nenhum → `—` (campo opcional).
- **Mudanças (summary)**: `git log --since="2 hours ago" --oneline --no-merges`. Vazio → string vazia (skill prompto operador no Step 3).
- **Template path**: `~/Notes/logseq/pages/session-close.md`. Ausente → recusa com `Template session-close.md ausente em ~/Notes/logseq/pages/ — feature requer Onda 4 do meta-sistema (Bloco 1 commit 364465e no logseq-notes)`. Exit clean.
- **Journal path**: `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md`.

### 3. AskUserQuestion — única chamada com 3 perguntas

Batch de 3 perguntas (per CLAUDE.md do `pragmatic-dev-toolkit` → AskUserQuestion mechanics; max 4):

1. **Topic** — header `Topic`, question `Resumo curto da sessão (frase única)`. Sem enum default (free-text é a essência); resposta via Other per ADR-006 do toolkit (enum não cabe).
2. **Decisões tomadas** — header `Decisões`, opcional: enum `Sem decisões nesta sessão` / `Há decisões — descrever`. Other → operador descreve em prosa.
3. **Follow-ups** — header `Follow-ups`, opcional: enum `Sem follow-ups` / `Há follow-ups — descrever`. Other → operador lista em prosa.

Sub-coleta inline (não no enum): mudanças summary vazio do Step 2 → prompto via prosa livre adicional pra operador descrever em 1-2 frases.

### 4. Compor bloco literal seguindo schema

Lê template `session-close.md`. Parseia placeholders (`<topic>`, `<repo-page>`, `<plan-slug>`, `<summary>`), substitui com valores resolvidos.

Linhas que **não** são placeholders (Decisões tomadas e Follow-ups) seguem regras fixas:

- Linha `- **Decisões tomadas:**`: resposta da pergunta 2 = `Sem decisões` ou None → preserva linha sem sub-bullets. `Há decisões — descrever` (Other) → append cada decisão como sub-bullet indented (`\t- <decisão>`).
- Linha `- **Follow-ups:**`: resposta da pergunta 3 = `Sem follow-ups` ou None → preserva linha vazia + remove stub literal `- TODO ` do template. `Há follow-ups — descrever` (Other) → append cada follow-up como `\t- TODO <item>` substituindo o stub `- TODO ` original.

### 5. Append no journal de hoje

Journal path existe → append do bloco composto sob seção `## Notes` do daily-journal (skill localiza heading via regex estrita `^\t- ## Notes` e adiciona bloco como sub-item indented por 1 tab). Heading ausente nesse formato → append no fim do file E **reportar warning explícito no Step 6**: `heading "## Notes" não encontrada com formato canonical em <journal-path>; bloco appended no fim — verificar daily-journal template ou indentação`. Failure-closed per ADR-005 (warning loud, não silent fallback).

Journal ausente → criar via leitura do daily-journal template (mesma mecânica do `/journal-note`); append do bloco sob `## Notes`.

### 6. Reportar

Path do journal tocado + heading sob qual o bloco foi appended + bullets count. Exit.

## O que NÃO fazer

- Não invocar Logseq CLI ou desktop pra renderizar template — skill opera filesystem markdown só. Block-ref `((session-close))` NÃO é usada (resolve só com desktop aberto — gate fechado per Step 1).
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não tenta detectar todas as sessões CC ativas — skill assume cwd corrente = repo da sessão.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
- Não tenta substituir block-ref Logseq por `((session-close))` ou similar — append literal per ADR-001 Sub-decisão 2.
