---
name: journal-review
description: Detective-first review com 4 heurísticas estruturais sobre janela configurável de journals; wizard GTD opt-in (sucessor de /weekly-review v0.2.0)
disable-model-invocation: false
---

# journal-review

Thin orchestrator do subcomando `mb journal-review` (CLI `meta-bridge`). Skill consome o **scan mecânico** do CLI (markers ativos + DONE-tasks + narrativas + inventário de buckets em janela `--days N`), aplica **4 heurísticas semânticas** detectivas, opera preview-first + cherry-pick, e re-invoca CLI em modo `--apply` com transições concretas.

Substância semântica (heurísticas, judgment, cherry-pick interpretation) é **heurístico-semântica** e **fica integralmente na skill**. CLI faz só scan + write engine.

Sucessor de `/weekly-review` v0.2.0. Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 10 e [ADR-002](../../docs/decisions/ADR-002-materializacao-cli-mb.md) § matching-on-skill.

Overlap conceitual com `/journal-close`: ambos fecham TODOs por evidência, mas eixos distintos — `/journal-close` confronta com **session context** (commits da sessão CC); `/journal-review` confronta com **conteúdo da janela inteira de journals** (correlação inter-journal). Complementares; idempotência natural via SSOT in-place de markers.

## Argumentos

```
/journal-review                    # default: --days 30 detective-only
/journal-review --days 7           # janela semanal
/journal-review --from 2026-05-01 --to 2026-05-31  # range arbitrário
/journal-review --interactive      # detective + wizard residual após
/journal-review --write-summary    # detective + bloco summary no journal de hoje
```

- `--days N` ou `--from/--to`: passados ao CLI (validação lá; mensagens claras).
- `--interactive`: wizard residual GTD após análise detective. Default off.
- `--write-summary`: bloco `## Journal review` no journal de hoje. Default off.

## Passos

### 1. Invocar `mb journal-review` scan mode

`Bash mb journal-review [--days N | --from D1 --to D2]` → emite markdown estruturado em stdout com 4 seções (Active markers, DONE tasks, Narratives, Bucket inventory).

Janela vazia → CLI reporta `nenhum journal encontrado` + exit 0 → skill termina.

CLI valida args (mutual exclusion `--days` vs `--from/--to`); skill repassa erros.

### 2. Análise detectiva (heurístico-semântico — fica na skill)

Skill consome scan output e aplica 4 heurísticas:

#### 2a. Heurística 1 — `task-closure-by-context` (apply)

Pra cada marker ativo, confronta com DONE-tasks e narrativas **posteriores** na janela (ordem cronológica preservada por contrato do CLI). Match semântico + hint forte de cross-refs (`plan:`, `commit:`, `[[page]]`). Judgment conservador.

Finding: `(source-path, source-line, marker original → DONE)`.

#### 2b. Heurística 2 — `task-zombie` (apply)

Pra cada marker ativo: idade > T dias (T=14 default) + zero DONE relacionado + zero referência em narrativa. Finding: archive (DONE) ou cancel (CANCELLED) — operador escolhe.

#### 2c. Heurística 3 — `bucket-underused` (report-only)

Pra cada bucket no inventário: aparece em < K journals (K=2) E < M tasks abertas (M=2). Finding com sugestão archive/fund — apply manual via Edit/Write.

#### 2d. Heurística 4 — `bucket-emerging` (report-only)

Hashtag/conceito em narrativas (≥ N=3 menções) que NÃO existe como bucket top-level. Finding com sugestão criar bucket — apply manual.

**Falsos-positivos heading-style** (ex.: `WAITING Próximos passos`): judgment filtra antes de emitir finding.

**Análise vazia** (zero findings) → recusa silenciosa.

### 3. Preview-first via AskUserQuestion (skill mantém estado em conversation memory)

Skill apresenta findings agrupados por tipo + evidência inline em prosa. `AskUserQuestion` header `Findings`:
- `Aplicar tudo`.
- `Cherry-pick via Other` — operador descreve subset em prosa; skill interpreta.
- `Cancelar`.

**Dispatch por opção**:
- `Aplicar tudo` → todas as transições das heurísticas 1-2 entram no payload do Step 5.
- `Cherry-pick via Other` → skill interpreta seleção, monta subset; transições selecionadas entram no Step 5.
- `Cancelar` → pular Steps 5 e 6 do fluxo de heurísticas (Step 4 wizard residual ainda pode rodar se `--interactive`).

Estado dos findings vive em conversation memory entre a apresentação e a invocação de apply. Skill traduz seleção em transições concretas (paths/linhas/before/after) — **não passa IDs opacos pro CLI** (per F2 design-reviewer absorvido).

### 4. Wizard residual opt-in (`--interactive`)

Skill processa tasks abertas que **não** geraram finding nas heurísticas 1-2 via wizard linear (truncate 20/marker, batch de 4 perguntas por AskUserQuestion, 4 opções):
- `Manter aqui` — sem transição.
- `Próximo passo definido` (Other → descrição) — sem transição (operador anota manualmente depois).
- `Arquivar` — transição `TODO|DOING|WAITING → DONE` (ou `CANCELLED` se irrelevante).
- `Adiar próxima semana` — transição `TODO|DOING|WAITING → WAITING` preservando body (per ADR-001 Sub-decisão 5 Adendo v0.2.0).

Mecânica idêntica a `/weekly-review` v0.2.0. `--interactive` ausente → skip.

Transições do wizard residual (Arquivar/Adiar) entram no **mesmo payload** do Step 5, unificadas com transições das heurísticas 1-2.

### 5. Invocar `mb journal-review --apply` (CLI write engine)

Compor payload unificado contendo (a) transições das heurísticas 1-2 confirmadas no Step 3 + (b) transições do wizard residual do Step 4 (se `--interactive` ativo). Chamada **única** ao CLI:

```
- <source-path>:<line> | \t- TODO X | \t- DONE X
- <source-path>:<line> | \t- WAITING Y | \t- DONE Y
```

`echo "$PAYLOAD" | mb journal-review --apply`. CLI aplica modify-in-place atomic (mesmo TRANSITION_RE + drift detection do `mb journal-close`). Output: count aplicadas + skipped.

Heurísticas 3-4 não disparam apply automático no MVP.

### 6. `--write-summary` opcional (skill compõe + invoca `mb journal-close` write)

**Ordering**: Step 6 executa **após** Step 5; usa as contagens reais reportadas pelo CLI (aplicados/skipped). Step 5 falha total → Step 6 ainda pode rodar com count vazio (operador decide). Re-invocação cria bullet duplicado — sem dedup automático pra summary (não tem `commit:` hash); operador edita manual se necessário.

`--write-summary` ativo → skill compõe bloco e pipe pra `mb journal-close` Append:

```
## Append

- #journal-review
	- ## Journal review — YYYY-MM-DD
		- Janela: <range> (<N> journals)
		- Heurística 1: <X aplicados, Y rejeitados>
		- ...
```

Append no journal de hoje via CLI. Default off — curation é meta-operação invisível.

### 7. Reportar

Repassar output do `--apply` ao operador + agregado de findings emitidos por heurística + wizard residual count (se `--interactive`).

## O que NÃO fazer

- **Não duplicar substância de scan/apply** — vive em `meta_bridge.journal_review`.
- Não fazer apply estrutural de bucket no MVP — heurísticas 3-4 são report-only.
- Não criar snapshot pré-write no MVP — marker change é single-line atomic idempotente.
- Não propor finding em matches incertos — judgment conservador.
- Não modificar markers em sub-bullets (≥2 tabs) — prosa contextual.
- Não capturar `DONE`/`CANCELLED` como reconciliáveis — terminais (ADR-002 do logseq-notes Sub-decisão 4).
- Não escrever bloco summary por default — `--write-summary` é opt-in.
- Não anotar sub-bullet `→ closed via finding` — SSOT in-place.
- Não rodar wizard residual por default — `--interactive` é opt-in.
- Não derivar bucket do cwd — opera cross-files.
- Não inflar análise quando substância é magra — recusa silenciosa elegante.
- Não fazer commit em logseq-notes.
- Não estender janela default — N=30 é coerente com curation mensal.
- Não confundir com `/journal-close` v0.4.1 — eixos distintos (session context vs janela cross-journal).
- **Não passar IDs opacos pro CLI** (per F2 absorvido): skill mantém findings em conversation memory + envia paths/linhas/transições concretas.
