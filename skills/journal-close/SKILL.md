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

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-close`. Exit clean.

### 2. Coleta context

- **Repo basename**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado):
  1. Variável env `PRAGMATIC_ACTIVE_PLAN_SLUG` exposta por `/run-plan` do `pragmatic-dev-toolkit` (gap conhecido — hoje sempre None nesta probe; ADR-001 Sub-decisão 3 + Gatilho 7).
  2. Probe `docs/plans/*.md` modified nas últimas 2 horas (`find docs/plans -name '*.md' -newermt '2 hours ago'`). Múltiplos → mais recente (`ls -t`).
  3. Nenhum → `—` (campo opcional).
- **Mudanças (summary)**: `git log --since="2 hours ago" --oneline --no-merges`. Vazio → string vazia (skill prompto operador no Step 3).
- **Template path**: `~/Notes/logseq/pages/session-close.md`. Ausente → recusa com `Template session-close.md ausente em ~/Notes/logseq/pages/ — feature requer Onda 4 do meta-sistema (Bloco 1 commit 364465e no logseq-notes)`. Exit clean.
- **Journal path**: `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md`.

### 3. Sintetizar rascunhos + confirmação via AskUserQuestion

**Mecânica draft-then-confirm** (per ADR-001 Sub-decisão 3 adendo de 2026-05-28): operator não descreve Decisões/Follow-ups do zero. Skill (agente que executa) tem acesso a session context — conversation history + commits coletados no Step 2 — e **sintetiza rascunhos**, presentando pra confirmação. Reduz friction operacional.

**Pré-passo (síntese pelo agente)**:

- **Topic candidate**: agente propõe 2-3 candidatos curtos baseados em commits + conversation thread (frase única cada). Operator pica ou Others. Caso comum: 1 dos candidates serve direto.
- **Decisões draft**: agente extrai decisões estruturais de session context (commits message body, conversation onde operator autorizou trocas de direção, AskUserQuestion answers prévias da sessão). Output: lista de N bullets curtos (~5-10 palavras cada). Vazio → flag draft como "Sem decisões detectadas".
- **Follow-ups draft**: análogo — extrai capture markers da sessão (TaskCreate com `[capture:*]`, follow-ups capturados em conversation, BACKLOG entries adicionadas). Vazio → "Sem follow-ups detectados".

**Apresentação ao operador**: prosa antes da chamada AskUserQuestion enumera os rascunhos pra leitura (não dentro do enum — enum tem limite de label):

```
**Rascunho de Decisões** (extraído da sessão):
- <decisão 1>
- <decisão 2>
...

**Rascunho de Follow-ups** (extraído da sessão):
- TODO <follow-up 1>
- TODO <follow-up 2>
...
```

**AskUserQuestion única chamada com 3 perguntas** (per CLAUDE.md do `pragmatic-dev-toolkit` → AskUserQuestion mechanics; max 4):

1. **Topic** — header `Topic`. Options: candidates do pré-passo (2-3 enum labels) + Other auto pra free-text override.
2. **Decisões** — header `Decisões`: enum `Confirma rascunho` / `Edita via Other` / `Sem decisões — limpar rascunho`. Other → operator substitui completamente em prosa. `Sem decisões — limpar rascunho` força clear do draft (skill detectou ruído).
3. **Follow-ups** — header `Follow-ups`: enum análogo: `Confirma rascunho` / `Edita via Other` / `Sem follow-ups — limpar rascunho`.

Rascunho vazio (skill detectou "Sem decisões detectadas") → enum cai pra 2 opções: `Confirma "sem decisões"` / `Há decisões — descrever via Other`. Mesma lógica pra Follow-ups.

Sub-coleta inline: mudanças summary vazio do Step 2 → prompto via prosa livre adicional pra operator descrever em 1-2 frases.

### 4. Compor bloco literal seguindo schema

Lê template `session-close.md`. Parseia placeholders (`<topic>`, `<repo-page>`, `<plan-slug>`, `<summary>`), substitui com valores resolvidos.

Linhas que **não** são placeholders (Decisões tomadas e Follow-ups) seguem regras fixas:

- Linha `- **Decisões tomadas:**`: resposta da pergunta 2 = `Confirma rascunho` → append rascunho do Step 3 como sub-bullets indented (`\t- <decisão>`). `Edita via Other` → operator substituiu rascunho; append Other content como sub-bullets. `Sem decisões — limpar rascunho` ou `Confirma "sem decisões"` → preserva linha sem sub-bullets.
- Linha `- **Follow-ups:**`: resposta da pergunta 3 análoga. `Confirma rascunho` ou `Edita via Other` → append cada follow-up como `\t- TODO <item>` substituindo o stub `- TODO ` original. `Sem follow-ups` → preserva linha vazia + remove stub literal `- TODO `.

### 5. Append no journal de hoje

Journal path existe → append do bloco composto sob seção `## Notes` do daily-journal (skill localiza heading via regex estrita `^- ## Notes` — top-level, zero tab — e adiciona bloco como sub-item indented por 1 tab). Heading ausente nesse formato → append no fim do file E **reportar warning explícito no Step 6**: `heading "## Notes" não encontrada com formato canonical em <journal-path>; bloco appended no fim — verificar daily-journal template ou indentação`. Failure-closed per ADR-005 (warning loud, não silent fallback). Regex top-level corresponde ao formato canonical pós-`template-including-parent:: false` do daily-journal template (Logseq auto-apply + `/journal-note` ambos produzem `- ## Notes` no nível raiz, sem indent).

Journal ausente → criar via leitura do daily-journal template (mesma mecânica do `/journal-note`); append do bloco sob `## Notes`.

### 6. Reportar

Path do journal tocado + heading sob qual o bloco foi appended + bullets count. Exit.

## O que NÃO fazer

- Não invocar Logseq CLI ou desktop pra renderizar template — skill opera filesystem markdown só. Block-ref `((session-close))` NÃO é usada (resolve só com desktop aberto — gate fechado per Step 1).
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não tenta detectar todas as sessões CC ativas — skill assume cwd corrente = repo da sessão.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
- Não tenta substituir block-ref Logseq por `((session-close))` ou similar — append literal per ADR-001 Sub-decisão 2.
