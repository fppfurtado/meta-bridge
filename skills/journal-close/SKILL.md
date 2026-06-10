---
name: journal-close
description: Sintetiza sessão CC em tasks DONE agrupadas por #domínio no journal Logseq de hoje
disable-model-invocation: false
---

# journal-close

Sintetiza a sessão CC atual em **tasks DONE agrupadas por bucket `- #<repo>`** no journal Logseq de hoje. Find-or-create idempotente com `/journal-note` prévios da mesma sessão. Materializa continuidade cross-session per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) consumindo [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 3 (+ Adendo v0.2.0).

Skill opera **independente** de `CLAUDE.md` / role contract. Compõe in-skill (NÃO consome `pages/session-close.md` — archived pós-retrofit per ADR-002 Sub-decisão 2).

## Argumentos

Sem argumentos. Skill coleta context da sessão CC corrente via probe do git + filesystem + conversation context.

## Passos

### 1. Gates (cheap-first)

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/journal-close exige git repo (skill deriva repo basename do cwd; sessões fora de git capturam via /journal-note direto)`. Exit clean.

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-close`. Exit clean.

### 2. Coleta context da sessão

- **Repo basename principal**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado):
  1. Variável env `PRAGMATIC_ACTIVE_PLAN_SLUG` exposta por `/run-plan` do `pragmatic-dev-toolkit` (gap conhecido — hoje sempre None nesta probe; ADR-001 Sub-decisão 3 § Gatilho 7).
  2. Probe `docs/plans/*.md` modified nas últimas 2 horas (`find docs/plans -name '*.md' -newermt '2 hours ago'`). Múltiplos → mais recente (`ls -t`).
  3. Nenhum → `—` (campo opcional).
- **Commits da sessão (multi-repo)**: probe explícito de 2 fases:
  1. **Lista cwds tocados**: agente (que executa skill) enumera cwds visitados na sessão via inspect do conversation history (toolkit pattern). Inclui cwd corrente + paths absolutos de outros repos onde agente fez Bash/Read/Edit. Único: deduplicar paths.
  2. **`git log` em cada cwd descoberto**: para cada path da lista, `cd <path> && git log --since="<start-of-session>" --oneline --no-merges`. Falha de `git log` (path não é repo, vazio) → skip silente.
- Cada commit captura: subject, hash short (7 chars), repo basename (derivado do `basename` do path). Resultado: lista [(repo, hash, subject), ...] cobrindo todos os repos tocados pela sessão.
- **Fallback se conversation history não expõe cwds visitados**: degradar pra single-repo (cwd corrente apenas), reportar warning `coleta multi-repo degraded — só commits do cwd corrente capturados` no Step 6.
- **Journal path**: `~/Notes/logseq/journals/$(date +%Y_%m_%d).md`.

### 3. Sintetizar rascunho de tasks DONE agrupadas por bucket

Para cada commit identificado no Step 2 (potencialmente em múltiplos repos), agente compõe rascunho:

- **Bucket**: `- #<repo-basename>` (top-level). Múltiplos commits no mesmo repo → 1 bucket único agrupa todos.
- **Child task**: `- DONE <commit subject>` (marker nativo Logseq).
- **Sub-bullets mecânicos** (nested sob o task):
  - `- commit: <short-hash>` (extraído do commit hash, mesma regra de `/journal-note`: 7-40 chars).
  - `- plan: <slug>` — plan slug ativo da sessão (Step 2). Emitido em **toda** task DONE da sessão quando plan slug presente. Omitido se Step 2 retornou `—` (sem plan ativo).
  - `- [[<page>]]` (cross-refs detectados no commit message body — opcional).

Rascunho exemplo (multi-repo):

```
- #drive-sync
	- DONE removido pipx ensurepath do install.sh
		- commit: e56d666
		- plan: install-remover-pipx-ensurepath
- #meta-bridge
	- DONE pgrep -xi gate case-insensitive
		- commit: eaadf07
	- DONE /init-logseq-project Step 5 dedent + macro substitution
		- commit: 4c99c32
```

Rascunho vazio (sessão sem commits) → **recusa silenciosa** com mensagem `/journal-close: sessão sem commits — use /journal-note "<nota>" pra registrar nota livre`. Exit clean. Step 4 não dispara nesse caminho (sem rascunho a confirmar).

### 4. Synthesis-then-confirm via AskUserQuestion

**Apresentação ao operador**: prosa antes da chamada AskUserQuestion enumera o rascunho:

```
**Rascunho de tasks DONE** (extraído da sessão):

- #<repo1>
	- DONE <subject1>
		- commit: <hash1>
		...
- #<repo2>
	- DONE <subject2>
		...
```

**AskUserQuestion única chamada**:

- header: `Rascunho`
- options:
  - `Confirma rascunho` — write executa exatamente como rascunho
  - `Edita via Other` — operator substitui completamente em prosa (descreve novo conteúdo livre)
  - `Sem commits úteis — não escrever` — abort silente, sessão não vai pro journal

(Caminho "rascunho vazio" não dispara Step 4 — ver Step 3 recusa silenciosa.)

### 5. Find-or-create cada bucket + append children (idempotente com `/journal-note`)

Para cada bucket `- #<repo>` do rascunho confirmado:

1. **Probe no journal path** (mesma lógica de `/journal-note` Step 4): linha top-level `^- #<repo>($| )` existe?
   - **Existe** → identificar offset; append children sob essa linha. Preserva tasks já presentes (de `/journal-note` prévios ou de invocações anteriores do `/journal-close` na mesma sessão).
   - **Não existe** → append novo bucket top-level no fim do journal; append children sob ele.
2. **Probe pré-write por dedup de `commit:<hash>`**: para cada task DONE candidata, scan dos children atuais do bucket — se já existe child com sub-bullet `- commit: <hash>` correspondente, **skip** essa task (já foi escrita por invocação anterior do `/journal-close` ou append manual). Chave de dedup: hash short do commit (único na escala da sessão). Garante idempotência intra-skill: 2 invocações de `/journal-close` na mesma sessão não duplicam tasks DONE.
3. **Append children**: tasks DONE remanescentes (após dedup) + sub-bullets indentados sob o bucket. Ordem natural (mais antiga primeiro per ordem de commits no rascunho).

**Idempotência cross-skill** com `/journal-note`: se operador rodou `/journal-note "TODO investigar X"` em `- #drive-sync` antes nesta sessão, e agora `/journal-close` tem `- DONE <something>` no mesmo bucket, **NÃO cria bucket duplicado** — append children DONE abaixo do TODO existente no mesmo bucket. Contract crítico per ADR-006 § Decisão § 1.

**Idempotência intra-skill** (`/journal-close` invocado 2× na mesma sessão): cobertor por dedup de hash no sub-passo 2 acima. Stop hook `suggest_journal_close.py` pode fires múltiplas vezes; operador aceitar 2× é seguro (não duplica writes).

**Bootstrap journal** (mesma mecânica de `/journal-note` Step 3): journal ausente → ler `~/Notes/logseq/pages/daily-journal.md` como template body (scaffold mínimo pós-Onda 4.5).

### 6. Reportar

Path do journal tocado + buckets tocados (criados/identificados) + count de DONE tasks appended. Exit.

## O que NÃO fazer

- Não consumir `pages/session-close.md` — archived per ADR-002 Sub-decisão 2 (compose in-skill).
- Não criar bucket sem antes probar (find-or-create gate idempotência cross-skill com `/journal-note`).
- Não invocar Logseq CLI ou desktop pra renderizar — skill opera filesystem markdown só. Block-ref `((session-close))` NÃO é usada.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não tenta detectar todas as sessões CC ativas — skill assume cwd corrente = repo principal da sessão; multi-repo emerge via conversation context.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
- Não classificar sub-bullets por prefixo — convention ADR-006 § Decisão § 3 é prosa free-form. Captures mecânicos limitados a `commit:`/`plan:`/`[[<page>]]`.
- Não escrever se Logseq desktop aberto (pgrep gate). Failure-closed.
