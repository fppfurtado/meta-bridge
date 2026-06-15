---
name: journal-close
description: Sintetiza sessão CC no journal Logseq de hoje — narrativa humano-amigável agrupada por #domínio (DONE + TODO/WAITING + insights) + reconciliação prévia (--days N)
disable-model-invocation: false
---

# journal-close

Thin orchestrator do subcomando `mb journal-close` (CLI `meta-bridge`). Skill compõe payload editorial (síntese humano-amigável + transições in-place já decididas) e delega o write determinístico (find-or-create bucket, dedup por commit hash, modify-in-place atomic, bootstrap journal, gate Logseq) ao CLI.

Substância editorial (matching semântico, princípios de granularidade, filtros) é **heurístico-semântica** e **fica integralmente na skill**. CLI vira write engine — recebe payload via stdin e aplica writes sem refazer judgment.

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 3 (+ Adendos v0.3.0/v0.4.0/v0.4.1) e [ADR-002](../../docs/decisions/ADR-002-materializacao-cli-mb.md) § matching-on-skill.

## Argumentos

Flag opcional para janela de reconciliação prévia.

```
/journal-close              # default: só hoje
/journal-close --days 3     # hoje + 3 dias retroativos
/journal-close --days 7     # janela semanal
```

- `--days N`: inteiro N ≥ 0. Default 0 = só hoje. Estende leitura retroativa pra reconciliar TODOs antigos fechados pela sessão. Síntese **sempre** vai no journal de hoje. **Escopo**: `--days N` afeta **apenas** o backlog scan do Step 2.5; coleta de commits no Step 2 sempre usa janela da sessão CC corrente (não estende retroativamente).

## Passos

### 1. Gates editoriais (skill)

`git rev-parse --show-toplevel` falha → recusa com `/journal-close exige git repo`. Exit clean.

(Gate `pgrep -xi logseq` fica no CLI — failure-closed na chamada.)

### 2. Coleta context da sessão (heurístico-semântico — fica na skill)

- **Repo basename principal**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado): env `PRAGMATIC_ACTIVE_PLAN_SLUG` → `find docs/plans -name '*.md' -newermt '2 hours ago'` → omitido.
- **Commits multi-repo**: enumerar cwds visitados na sessão; `git log --since="<start>" --oneline --no-merges` em cada. `<start>` = timestamp do início da sessão CC corrente (não estender por `--days N` — esse afeta só o Step 2.5).
- **Material editorial** via conversation context — filtros de seleção v0.4.1:
  - Frame de sessão (1 linha).
  - Insight/pivot conceitual (1-2 por sessão).
  - Mudanças finas: critério "isto vai informar futuras decisões?".
  - Próximos passos enunciados pelo operador (TODO/WAITING).
  - Direção emergente (1-3 bullets curtos).
  - Cross-refs ([[page]], links).
- Sessão sem substância editorial além de DONE-tasks → degradar elegantemente pra runbook simples.

### 2.5. Coleta backlog reconciliável (regex mecânico — pode ser via Bash)

Pra cada journal na janela `--days N`, scan regex `^\t- (TODO|DOING|WAITING) (.*)$` (1-tab indent). Capturar (marker, conteúdo, bucket-pai, source path/line, sub-bullets). `DONE`/`CANCELLED` não capturados (terminais).

Backlog vazio → skip reconciliação no Step 3b.

### 3. Sintetizar rascunho + matching semântico (skill)

#### 3a. Rascunho narrativa por bucket (template humano-amigável)

Compor in-skill seguindo princípios editoriais v0.3.0 + v0.4.1: linguagem 2ª pessoa, seções opcionais (Frame/Insight/DONE/Mudanças/TODO/Direção), GTD markers nativos, granularidade DONE por conceito (não commit), aprofundamento de árvore livre quanto material sustente, brevidade vence completude.

Exemplo em ADR-001 Sub-decisão 3 § Exemplo (sessão rica).

#### 3b. Matching semântico TODOs ↔ DONEs da sessão (skill)

Pra cada marker do Step 2.5, agente julga se trabalho da sessão fechou:
- Match textual semântico.
- Cross-refs explícitos (`plan:`, `commit:`, `[[page]]`) como hint forte.
- Judgment conservador: incerto → **não** propor transição.

Resultado: lista de transições `(source-path, source-line, marker→DONE|CANCELLED)`.

#### 3c. Caso degenerado

Rascunho vazio + transições vazias → recusa silenciosa.

### 4. Preview-first via AskUserQuestion (skill)

Apresentar rascunho + transições em prosa. `AskUserQuestion` header `Rascunho`:
- `Confirma rascunho + transições`.
- `Edita via Other` — operador descreve ajuste.
- `Sem substância — não escrever`.

**Dispatch por opção**:
- `Confirma` → seguir Step 5.
- `Edita via Other` → re-compor Step 3a/3b absorvendo o ajuste; voltar para Step 4 com rascunho atualizado.
- `Sem substância` → recusa silenciosa, exit clean (Step 5 não dispara).

### 5. Invocar `mb journal-close` (CLI write engine)

Compor payload markdown estruturado e pipe via stdin:

```
## Append

- #<bucket>
	- <rascunho confirmado>

## Transitions

- <source-path>:<line> | \t- TODO X | \t- DONE X
- <source-path>:<line> | \t- WAITING Y | \t- DONE Y
```

`echo "$PAYLOAD" | mb journal-close`. Output reporta journal/buckets/transitions/dedup — repassar ao operador.

CLI faz: ordem fixa transitions → find-or-create + dedup por commit hash → append children. Bootstrap journal se ausente. Sem annotation extra (SSOT in-place per ADR-002 do logseq-notes Sub-decisão 4).

## O que NÃO fazer

- **Não duplicar substância (find-or-create, modify-in-place, dedup, bootstrap)** — vive em `meta_bridge.journal_close`.
- Não anotar sub-bullet `→ closed em sessão X` sob marker original — SSOT in-place per ADR-002 do logseq-notes Sub-decisão 4.
- Não criar bullet `DONE X (closes TODO de YYYY-MM-DD)` no novo bucket — same SSOT logic.
- Não propor transição em matches incertos — judgment conservador.
- Não modificar markers em sub-bullets (≥2 tabs) — prosa contextual.
- Não capturar `DONE`/`CANCELLED` como reconciliáveis — terminais por design (ADR-002 Sub-decisão 4 do logseq-notes).
- **Não enumerar cada commit como DONE separado** (v0.4.1) quando 3-5 commits formaram um movimento conceitual único — agrupar sob **DONE \<conceito\>**.
- **Não capturar detalhes técnicos-operacionais em "Mudanças finas"** — filtrar por "isto vai informar futuras decisões?".
- **Não criar seções operacionais cronológicas** — sessão se descreve pela substância editorial, não pela cronologia.
- Não inflar narrativa — brevidade vence completude quando substância é magra.
- Não 3ª pessoa formal robótica — linguagem 2ª pessoa quando faz sentido editorial.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
