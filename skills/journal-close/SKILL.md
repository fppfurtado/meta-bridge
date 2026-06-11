---
name: journal-close
description: Sintetiza sessão CC no journal Logseq de hoje — narrativa humano-amigável agrupada por #domínio (DONE + TODO/WAITING + insights)
disable-model-invocation: false
---

# journal-close

Sintetiza a sessão CC atual em **narrativa humano-amigável agrupada por bucket `- #<repo>`** no journal Logseq de hoje. Find-or-create idempotente com `/journal-note` prévios da mesma sessão. Materializa continuidade cross-session per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) consumindo [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 3 (+ Adendo v0.3.0).

Skill opera **independente** de `CLAUDE.md` / role contract. Compõe in-skill (NÃO consome `pages/session-close.md` — archived pós-retrofit per ADR-002 Sub-decisão 2).

## Argumentos

Sem argumentos. Skill coleta context da sessão CC corrente via probe do git + filesystem + conversation context (inclusive material editorial — insights, mudanças finas, próximos passos, direção emergente).

## Passos

### 1. Gates (cheap-first)

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/journal-close exige git repo (skill deriva repo basename do cwd; sessões fora de git capturam via /journal-note direto)`. Exit clean.

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-close`. Exit clean.

### 2. Coleta context da sessão

- **Repo basename principal**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado):
  1. Variável env `PRAGMATIC_ACTIVE_PLAN_SLUG` exposta por `/run-plan` do `pragmatic-dev-toolkit` (gap conhecido — hoje sempre None nesta probe).
  2. Probe `docs/plans/*.md` modified nas últimas 2 horas (`find docs/plans -name '*.md' -newermt '2 hours ago'`). Múltiplos → mais recente (`ls -t`).
  3. Nenhum → omitido (campo opcional).
- **Commits da sessão (multi-repo)**: probe explícito de 2 fases:
  1. **Lista cwds tocados**: agente que executa skill enumera cwds visitados na sessão via inspect do conversation history (toolkit pattern). Inclui cwd corrente + paths absolutos de outros repos onde agente fez Bash/Read/Edit. Único: deduplicar paths.
  2. **`git log` em cada cwd descoberto**: para cada path, `cd <path> && git log --since="<start-of-session>" --oneline --no-merges`. Falha (path não é repo, vazio) → skip silente.
- Cada commit captura: subject, hash short (7 chars), repo basename. Resultado: lista [(repo, hash, subject), ...] cobrindo todos os repos tocados.
- **Material editorial via conversation context** (novo em v0.3.0): agente inspeciona o transcript da sessão pra extrair além de commits:
  - **Frame de sessão**: como começou + para onde virou (ex.: "Começou querendo X, desembocou em Y").
  - **Insight/pivot conceitual**: o momento que mudou direção, quando há um.
  - **Mudanças finas**: memory refinada, padrões reconhecidos, notas operacionais não-codificadas em commits.
  - **Próximos passos enunciados pelo operador** com markers GTD (TODO/WAITING).
  - **Direção emergente**: síntese reflexiva sobre onde a constelação está indo.
  - **Cross-refs** ([[page]], links markdown) que emergem do contexto.
  - **Julgamento do agente** sobre o que vale registrar — não mecânico. Sessão sem substância editorial além de DONE-tasks degrada elegantemente pra padrão runbook simples (ver Step 3).
- **Journal path**: `~/Notes/logseq/journals/$(date +%Y_%m_%d).md`.

**Fallback** se conversation history não expõe cwds visitados → degradar pra single-repo (cwd corrente apenas), reportar warning `coleta multi-repo degraded — só commits do cwd corrente capturados` no Step 6.

### 3. Sintetizar rascunho de narrativa por bucket

Para cada repo/domínio identificado no Step 2, agente compõe rascunho seguindo template humano-amigável. Estrutura geral (cada seção opcional):

```
- #<repo-basename>
	- <Frame de sessão> — 1 linha situando (ex.: "Sessão `<slug>`" ou "Começou X, desembocou em Y")
	- <Insight central>
		- <sub-bullet de prosa explicando o pivot>
	- DONE <agrupamento conceitual>
		- DONE <task específica>
			- commit: <hash> (opcional)
			- plan: <slug> (opcional)
	- Mudanças finas que ficaram registradas
		- <bullet descrevendo mudança não-codificada>
	- TODO/WAITING Próximos passos
		- TODO <task> — <contexto>
		- WAITING <task> — aguarda <gate>
	- Direção que emerge
		- <bullet de prosa reflexiva>
```

**Princípios editoriais**:

- **Linguagem humana 2ª pessoa quando faz sentido editorial** ("você decidiu X", "você rebateu argumento Y") — evitar 3ª pessoa formal robótica.
- **Bullets aninhados ≥3 níveis quando útil** — narrativa fluida, não flat git-log.
- **Cada seção opcional** — sessão sem insight pivot omite o bloco; sessão sem TODOs omite; sessão puramente mecânica degrada elegantemente pra DONE-only flat estilo runbook.
- **GTD markers Logseq nativos** (DONE/TODO/WAITING) preservados como block markers, não prefixos prosa.
- **Sub-bullets free-form** per ADR-006 § Decisão § 3 — convenção contract intacta (sub-bullets são prose não-parsed pelos consumers); v0.3.0 PRODUZ prose em vez de só metadata mecânica.
- **`commit:<hash>`/`plan:<slug>` continuam suportados** como metadata opcional sob DONE tasks (rastreabilidade material), não obrigatórios.
- **Cross-refs inline** ([[page]], links markdown) emergem do contexto.
- **Brevidade > completude** — não inflar narrativa quando substância é magra; sessão de 1 fix pequeno fica `- DONE <subject>` + `- commit: <hash>` e basta.

Rascunho exemplo (sessão rica, narrativa fluida):

```
- #meta-system
	- Sessão `generalizacao-mecanizacao`
	- Começou querendo decompor `/mechanical-skills-scan` e desembocou em reflexão fundacional sobre packaging mecânico
	- O insight que virou o leme
		- A doutrina assumia MCP-first sem comparar com CLI — assumption camuflada de decisão
		- CLI atende ~igualmente bem em substância mecânica + ganha em ergonomia
	- DONE Duas cristalizações doutrinais
		- DONE [ADR-016](docs/decisions/...) substitui § "Adoção MCP-first" por critério target-aware
			- commit: abc1234
		- DONE [ADR-017](docs/decisions/...) decompõe `/mechanical-skills-scan`
			- commit: def5678
	- TODO Próximos passos — cada um vira sessão própria no repo respectivo
		- TODO `/triage` em `pragmatic-dev-toolkit` materializando núcleo universal
		- WAITING `/triage` em `meta-system` refactorando `/mechanical-skills-scan` — aguarda Faceta 2
	- Direção que emerge
		- Knowledge layer fica mais nuanceada — MCP canonical pra cross-agente; CLI pra runtime auxiliar
```

Rascunho exemplo (sessão simples, degradação para padrão runbook):

```
- #drive-sync
	- DONE removido pipx ensurepath do install.sh
		- commit: e56d666
		- plan: install-remover-pipx-ensurepath
```

Rascunho vazio (sessão sem commits **e** sem narrativa editorial relevante) → **recusa silenciosa** com mensagem `/journal-close: sessão sem substância pra sintetizar — use /journal-note "<nota>" pra registrar nota livre`. Exit clean. Step 4 não dispara nesse caminho.

### 4. Synthesis-then-confirm via AskUserQuestion

**Apresentação ao operador**: prosa antes da chamada AskUserQuestion enumera o rascunho completo (multi-repo se aplicável).

**AskUserQuestion única chamada**:

- header: `Rascunho`
- options:
  - `Confirma rascunho` — write executa exatamente como rascunho
  - `Edita via Other` — operador substitui completamente em prosa (descreve novo conteúdo livre, mantendo estrutura humano-amigável)
  - `Sem substância — não escrever` — abort silente, sessão não vai pro journal

(Caminho "rascunho vazio" não dispara Step 4 — ver Step 3 recusa silenciosa.)

### 5. Find-or-create cada bucket + append children (idempotente com `/journal-note`)

Para cada bucket `- #<repo>` do rascunho confirmado:

1. **Probe no journal path**: linha top-level `^- #<repo>($| )` existe?
   - **Existe** → identificar offset; append children sob essa linha. Preserva tasks/bullets já presentes (de `/journal-note` prévios ou invocações anteriores do `/journal-close` na mesma sessão).
   - **Não existe** → append novo bucket top-level no fim do journal; append children sob ele.

2. **Dedup intra-skill (parcial em v0.3.0)**:
   - **Children com `- commit: <hash>` sub-bullet**: probe pré-write — se mesmo hash já presente sob o bucket, skip esse child. Mesma mecânica determinística da v0.2.0.
   - **Children sem metadata `commit:`** (frame, insight, mudanças finas, próximos passos, direção): **sem dedup mecânica**. Operador rodando 2× pode duplicar conteúdo narrativo — mitigação: aceitar `Edita via Other` no 2º run pra revisar/consolidar. Trade-off aceito (escopo expandido sacrifica idempotência intra-skill perfeita; ver Adendo v0.3.0 do ADR-001).

3. **Append children**: bullets remanescentes (após dedup parcial) sob o bucket, preservando indentação hierárquica do rascunho. Ordem natural do rascunho.

**Idempotência cross-skill com `/journal-note`**: contract crítico mantido per ADR-006 § Decisão § 1 — se operador rodou `/journal-note "TODO X"` em `- #drive-sync` antes nesta sessão, e agora `/journal-close` tem narrativa no mesmo bucket, **NÃO cria bucket duplicado** — append children abaixo dos prévios no mesmo bucket.

**Bootstrap journal**: journal ausente → ler `~/Notes/logseq/pages/daily-journal.md` como template body (scaffold mínimo pós-Onda 4.5).

### 6. Reportar

Path do journal tocado + buckets tocados (criados/identificados) + count de bullets appended (subdivididos: DONE tasks, TODO/WAITING markers, blocos narrativos). Exit.

## O que NÃO fazer

- Não consumir `pages/session-close.md` — archived per ADR-002 Sub-decisão 2 (compose in-skill).
- Não criar bucket sem antes probar (find-or-create gate idempotência cross-skill com `/journal-note`).
- Não invocar Logseq CLI ou desktop pra renderizar — skill opera filesystem markdown só. Block-ref `((session-close))` NÃO é usada.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não tenta detectar todas as sessões CC ativas — skill assume cwd corrente = repo principal da sessão; multi-repo emerge via conversation context.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
- Não escrever se Logseq desktop aberto (pgrep gate). Failure-closed.
- Não forçar estrutura template rígida — cada seção (frame, insight, mudanças finas, próximos passos, direção) é opcional; sessão simples degrada elegantemente pra DONE-only flat estilo runbook.
- Não 3ª pessoa formal robótica — linguagem 2ª pessoa quando faz sentido editorial (operador é o leitor; evita prosa de manual).
- Não inflar narrativa — brevidade vence completude quando substância é magra; sessão de 1 fix pequeno é `- DONE <subject>` + metadata, sem inventar insight.
