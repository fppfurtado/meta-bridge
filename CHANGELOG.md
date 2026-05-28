# Changelog

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
