# Changelog

## 0.2.1 — 2026-06-10

### Changed

**Journals em local TZ pra convergência cross-plugin com `tjpa-tools`.** As 3 skills de write no journal (`/journal-note`, `/journal-close`, `/weekly-review`) migram `$(date -u +%Y_%m_%d)` → `$(date +%Y_%m_%d)` em 6 ocorrências. Sub-decisão 1 do ADR-001 ganha Adendo v0.2.1 documentando a migration; `CLAUDE.md` linha 25 atualizada (`UTC date` → `local TZ`).

**Decisão arquitetural cross-plugin:** filename de journal usa local TZ (não UTC). Fecha divergência identificada empiricamente em 2026-06-10 — `tjpa-tools` v0.2.0+ usa local TZ desde 2026-06-02 (per /run-plan `tjpa-report-logseq-page`); na janela 21h-23h59 BRT, os 2 plugins produziam filenames diferentes e bullets caíam em journals distintos (split-brain do journal de "hoje"). 4 razões objetivas pra convergência **local TZ vence** (vs UTC vence): intuição diária BRT load-bearing; decisão mais recente prevalece; cross-máquina é teórico hoje (operador single-machine); match com convention Logseq desktop. Plano canonical: [meta-system `docs/plans/journals-tz-cross-plugin-convergencia.md`](https://github.com/fppfurtado/meta-system/blob/main/docs/plans/journals-tz-cross-plugin-convergencia.md).

**Side-effect coerente em `/weekly-review` defer:** linha 76 da SKILL.md (`date -u -d 'next Monday'`) perde `-u` per coerência com decisão local TZ. Comportamento em borda (review feito domingo 21h-23h59 BRT) muda — defer aponta agora pra segunda **local** do operador, não segunda UTC.

**Linhas históricas ADR-001 46/50/70 NÃO tocadas:** referem-se a "Timestamp UTC removido do bloco" em v0.2.0 — narrativa histórica sobre Timestamp do BLOCO (distinto de filename TZ). Preservar.

## 0.2.0 — 2026-05-28

### Changed

**Schema-breaking change pro daily-journal — formato hashtag-bucket + GTD nativo (Onda 4.5 do meta-system).** Retrofit das 3 skills de capture (`/journal-note`, `/journal-close`, `/weekly-review`) consumindo [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) como constraints. Schema novo: top-level no journal é `- #<domínio>` (hashtag-bucket); estados GTD via task markers nativos (`TODO`/`DOING`/`WAITING`/`DONE`/`CANCELLED`) in-block per ADR-002 Sub-decisão 4; sub-bullets free-form per ADR-006 § Decisão § 3 (skills consomem só markers + cross-refs mecânicos `commit:`/`plan:`/`[[<page>]]`).

**Migration policy: hard cutover from release date forward.** Journals pré-existentes (anteriores a 2026-05-28) ficam intactos no formato Onda 3+4 (headings `## Inbox`/`## Doing`/`## Waiting`/`## Notes` + blocos `## Session close:`). Novo formato aplica a partir de journals com data ≥ 2026-05-28. Sem migration script — convivência permanente dos 2 formats no graph. `/weekly-review` v0.2.0 olha últimos 7 dias — em 1 semana só formato novo na janela ativa.

- **`/journal-note` v0.2.0**: find-or-create bucket `- #<domínio>` top-level + append child task. Domínio derivado por probe ordenado (cwd em git repo → basename; cwd fora → AskUserQuestion enum `#thought`/`#draft`/`#idea` + Other com sanitization kebab-case lowercase). Input com marker prefix uppercase (`TODO `/`DOING `/...`) preserva como marker Logseq nativo. Sub-bullets mecânicos extraídos limitados a `commit:<hash>` e `plan:<slug>`. Drop gate git repo (fora-de-git agora válido). Drop timestamp UTC do bloco (duplicava filename do journal). ADR-001 Sub-decisão 1 ganha § Adendo v0.2.0.
- **`/journal-close` v0.2.0**: sintetiza session context em tasks `- DONE <subject>` agrupadas por bucket `- #<repo>` com sub-bullets mecânicos. Find-or-create cada bucket idempotente cross-skill com `/journal-note` prévios + dedup intra-skill por `commit:<hash>` (Stop hook fires 2× não duplica writes). Coleta multi-repo via probe explícito de cwds tocados na sessão + `git log` em cada (fallback degraded single-repo com warning). Sessão sem commits → recusa silenciosa sugerindo `/journal-note`. Synthesis-then-confirm UX preservado. Drop consumption de `pages/session-close.md` (archived no logseq-notes per ADR-002 Sub-decisão 2). ADR-001 Sub-decisão 3 ganha § Adendo v0.2.0.
- **`/weekly-review` v0.2.0**: coleta via regex strict cross-journal `^\t- (TODO|DOING|WAITING) ` (1-tab indent — filhas diretas de bucket; markers em sub-bullets ≥2 tabs ficam como prosa contextual per F1 cutucada do /triage). `DONE`/`CANCELLED` não capturados (terminais por design). Archive via mudança de marker in-place (não property `archived::`) per ADR-002 Sub-decisão 4 (markers como SSOT). Composição in-skill (drop template `pages/weekly-review.md` consumption — paralelo a `/journal-close` v0.2.0). Drop gate git repo. Defer preserva bucket de origem no destino + sub-prompt pra escolher bucket quando task órfã. ADR-001 Sub-decisão 5 ganha § Adendo v0.2.0.
- **Stop hook `suggest_journal_close.py`**: lógica intacta — 3 gates (marker `[PRAGMATIC: plan-done]` no transcript + `.claude/local/` exists + Logseq desktop fechado). Sugestão "considere /journal-close" continua válida; mudança de output da skill é transparente pro hook. Validação no Bloco 3 do plano `onda-4-5-journal-retrofit-gtd` confirma compatibilidade (sem mudança de código). ADR-001 Adendo v0.2.0 da Sub-decisão 3 registra.

**Cross-repo coordenado**: este release acompanha [commit `9935ae1`](https://github.com/fppfurtado/logseq-notes/commit/9935ae1) no logseq-notes (ADR-002 + page daily-journal substituída por scaffold mínimo + page session-close archived) + [commit `7dc5055`](https://github.com/fppfurtado/logseq-notes/commit/7dc5055) (page weekly-review archived) + commits no meta-system (plano + ADR-006 + ARCHITECTURE).

**Plano de execução**: [`docs/plans/onda-4-5-journal-retrofit-gtd.md` do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/plans/onda-4-5-journal-retrofit-gtd.md).

## 0.1.5 — 2026-05-28

### Fixed

- **`suggest_journal_close` hook output não aparecia ao operador no CLI normal**. v0.1.0-v0.1.4 declararam mecânica de entrega como `sys.stderr.write(msg)` + exit 0. Stop hook stderr com exit 0 é **silenciado por design** pelo Claude Code TUI normal — só visível em `--debug` mode (documentado em [anthropics/claude-code #34600](https://github.com/anthropics/claude-code/issues/34600)). Validação manual da Onda 4 do meta-system (Sessão 6) Cenário 8 detectou via `/debug`: script funcionava standalone (probe com payload sintético via stdin printa em stderr corretamente), mas no fluxo real do CC operador não via nada. Fix: substituir `sys.stderr.write(msg)` por `print(json.dumps({"systemMessage": msg}))` em `hooks/suggest_journal_close.py:72-75`. Mecânica canonical do CC 2.1.x pra hook influenciar UI não-bloqueante (`systemMessage` standalone, sem `decision: "block"` que forçaria CC a continuar). Atualiza docstring + ADR-001 Sub-decisão 6 linha 188 + § Adendo (2026-05-28) documentando root cause e fix. Gates triplos e conteúdo da mensagem preservados.

## 0.1.4 — 2026-05-28

### Fixed

- **`/init-logseq-project` Step 5 create flow — spec não documentava 2 transformações entre template e page raíz**. v0.1.0/0.1.1/0.1.2/0.1.3 declararam Step 5 (Ausente — criar do zero) como "preencher Project Template.md body" sem dizer (a) **dedent**: `Project Template.md` tem props sob `- template:: project` com 1 tab inicial (estrutura wrapper de template Logseq), enquanto page raíz canonical (ex.: `pages/drive-sync.md`) tem essas linhas no nível root sem tab; (b) **macro substitution**: template tem `{{query <% current page %>}}` (macro Logseq que resolve via desktop) mas page raíz canonical tem `{{query [[<basename>]]}}` literal — macro vira string morta no markdown salvo com gate fechando desktop. Gaps detectados na validação manual da Onda 4 do meta-system (Sessão 6) via Cenário 6 (skill em repo dummy `/tmp/test-repo`). Fix: SKILL.md Step 5 ganha sub-steps explícitos (dedent 1 tab fixo no body pós-skip de linhas wrapper; substituir `<% current page %>` por `[[<basename>]]` literal; demais macros Logseq não tocadas) + ADR-001 Sub-decisão 4 linha 123 sumário + § Adendo (2026-05-28) documentando ambos gaps e mecânica de fix.

## 0.1.3 — 2026-05-28

### Fixed

- **`/init-logseq-project` Step 3 probe ordenada sempre falhava nos 2 primeiros fallbacks**, fazendo skill cair invariavelmente pro operator prompt (Step 3.3) — funcional mas violando intent doutrinário de auto-discovery via inventory layer. 3 bugs encadeados: (i) **mrconfig literal mismatch**: `$REPO_PATH` resolvido por `git rev-parse --show-toplevel` (ex.: `/storage/dev/projects/<repo>`) vs `.mrconfig` headers `[$HOME/Projects/<repo>]` literal não-expandido — comparação literal nunca batia; (ii) **awk range pattern single-line bug**: `$0==p,/^\[/` é range begin..end, e o header satisfaz ambos endpoints na mesma linha — `tags = ` da linha seguinte nunca era capturado mesmo se path bate; (iii) **REPOS.md format mismatch**: spec assumia bullet `^- \[<basename>\]` mas REPOS.md usa formato tabela markdown `| \`<basename>\` | ...`. Bug detectado na validação manual da Onda 4 do meta-system (Sessão 6). Fix: (i) iterar headers do mrconfig, expandir `$HOME` via `eval echo`, resolver symlinks via `readlink -f` em ambos lados, comparar paths normalizados; (ii) extrair `tags = ` via flag-pattern awk (`$0==p{flag=1;next} /^\[/{flag=0} flag && /^tags = /{print;exit}`) evitando o range single-line; (iii) grep `^| \`<basename>\`` em REPOS.md + último `^## <cluster>` antes via `head -n LINE | grep "^## " | tail -1`. Atualiza `skills/init-logseq-project/SKILL.md` Step 3 + Step "## O que NÃO fazer" + ADR-001 Sub-decisão 4 linha 120 sumária + § Adendo (2026-05-28) documentando os 3 bugs e mecânica de fix.

## 0.1.2 — 2026-05-28

### Fixed

- **`pgrep` canonical gate quebrava failure-closed com Logseq desktop aberto** (crítico). v0.1.0/0.1.1 declararam `pgrep -x logseq` (case-sensitive, exact-match) em ADR-001 Sub-decisão 7 e aplicavam nas 4 skills + hook. O AppImage do Logseq registra o binário como `Logseq` (capital L), então `pgrep -x logseq` retorna non-zero **mesmo com desktop aberto** — gate retorna falso-negativo, skills escrevem no filesystem do graph durante runtime do Logseq (race condition que Logseq watches file mtime e dispara mid-write). Bug detectado na validação manual da Onda 4 do meta-system (Sessão 6). Fix: `pgrep -x logseq` → `pgrep -xi logseq` (case-insensitive) em `skills/journal-note/SKILL.md`, `skills/journal-close/SKILL.md`, `skills/init-logseq-project/SKILL.md`, `skills/weekly-review/SKILL.md`, `hooks/suggest_journal_close.py` (linha 12 docstring + linha 61 subprocess call), `README.md`. ADR-001 Sub-decisão 7 ganha § Adendo explicando case mismatch + Gatilho 5 atualizado com nota de resolução parcial.

## 0.1.1 — 2026-05-28

### Fixed

- **`/journal-close` Step 5 regex**: was `^\t- ## Notes` (1 tab indent) — Logseq's auto-apply of `template-including-parent:: false` and `/journal-note`'s mechanic both produce headings at top-level (`- ## <heading>`, zero tab). Regex never matched in practice → failure-closed warning + append at end of file (observed in first real-use). Fixed to `^- ## Notes` matching canonical post-template-apply format.
- **`/weekly-review` Step 2 regex**: same fix for `^- ## Inbox`/`Doing`/`Waiting` (Sub-decisão 5 of ADR-001).

### Changed

- **`/journal-close` Step 3 UX**: redesigned from interview-puro to synthesis-then-confirm. The agent executing the skill has access to session context (commits + conversation) and now synthesizes drafts of Decisões and Follow-ups, presenting them for confirmation via AskUserQuestion with 3 options each (`Confirma rascunho` / `Edita via Other` / `Sem — limpar`). Reduces friction (operator no longer re-articulates information already in commits/conversation). Topic remains candidate-based.
- **ADR-001 Sub-decisão 3** ganha § Adendo (2026-05-28) explicando ambas refinements per ADR-034 critério (decisão central intacta, sem nova categoria, sem restrição externa, caráter explicativo).

## 0.1.0 — 2026-05-28

### Added

Initial release. Bridge skills materializing Camada 3 (Bridge) of the meta-system architecture:

- **`/journal-note <content>`** — timestamped append to today's Logseq journal with auto-detected `[[<repo-basename>]]` ref.
- **`/journal-close`** — synthesize CC session into structured block under `## Notes` in today's journal (consumes `session-close.md` schema).
- **`/init-logseq-project`** — idempotently create/update Project Page in graph from `CLAUDE.md`/`README.md` of repo at cwd.
- **`/weekly-review`** — GTD wizard aggregating Inbox/Doing/Waiting blocks from last 7 days of journals (excluding today), with deferred-batch edit semantics.
- **`suggest_journal_close` hook** — Stop event hook, auto-gated triplo (marker + `.claude/local/` + Logseq desktop closed); nudges operator toward `/journal-close` after `pragmatic-dev-toolkit`'s `/run-plan` emits the canonical `[PRAGMATIC: plan-done]` marker.

Requires `pragmatic-dev-toolkit` ≥ v2.13.0 for the marker emission (hook only).

ADR-001 documents 8 sub-decisões covering all skill internals.
