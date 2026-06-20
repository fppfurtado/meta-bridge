# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this repository is

A **Claude Code plugin** materializing the bridge between CC sessions and a Logseq cognitive graph. Companion to [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit); architecture context in [`meta-system`](https://github.com/fppfurtado/meta-system) (private).

Substância de write vive em **`meta_bridge` (Python CLI via Click)** — entry-point `mb` instalável via `pipx install -e .`. 4 subcomandos (`mb journal-note`, `mb journal-close`, `mb journal-review`, `mb init-project`) cobrem o trabalho mecânico das 4 skills substantivas; `/journal-load` permanece markdown-only. As 4 SKILL.md correspondentes viram **thin orchestrators** que delegam writes ao CLI e preservam substância heurístico-semântica (matching, princípios editoriais de síntese, 4 heurísticas detectivas, cluster prompt). Pós-Onda 2 do roadmap knowledge layer block-first do meta-system (2026-06-18), plugin ganha **6ª skill `/wiki-compile`** (knowledge layer Camada 3 — entity pages enriquecidas) com sub-tool Python determinístico standalone em `skills/wiki-compile/sub-tools/compile.py` (pattern orquestrador heurístico + sub-tool determinístico per meta-system ADR-017 § decomposição faceta ii; alternativa ao pattern thin orchestrator + CLI `mb` das 4 skills legacy). Plugin ship também 2 hooks bridging (Stop event sugerindo `/journal-close`; SessionStart event sugerindo `/journal-load` quando cwd casa com repo owned/active da constelação). Validação manual cobre golden path dos subcomandos mecânicos; suite parcial pytest cobre subcomandos/hooks com parsing-complexo (per ADR-002 § Decisão 6 Adendo 2026-06-16 — critério parsing-complexo → pytest; mecânico → manual). Pytest formal pro sub-tool `wiki-compile/sub-tools/compile.py` pendente em BACKLOG ## Próximos (gatilho intermediário ADR-021 § auto-crítica permanente do meta-system).

## Plugin layout

- `.claude-plugin/plugin.json` — plugin manifest.
- `.claude-plugin/marketplace.json` — exposes the plugin to `/plugin marketplace add`.
- `pyproject.toml` + `meta_bridge/` — Python package (hatchling minimalista; dependência única `click >= 8.0`). Entry-point `mb = meta_bridge.cli:cli`.
- `meta_bridge/{cli.py, journal_note.py, journal_close.py, journal_review.py, init_project.py, _paths.py}` — write engine + 4 subcomandos.
- `skills/<name>/SKILL.md` — 6 skills (`/journal-note`, `/journal-close`, `/journal-load`, `/init-logseq-project`, `/journal-review`, `/wiki-compile`). 4 são thin orchestrators do CLI; `/journal-load` permanece markdown-only; `/wiki-compile` (Onda 2 do roadmap knowledge layer) delega ao sub-tool Python standalone em `skills/wiki-compile/sub-tools/compile.py` (pattern distinto — per meta-system ADR-017 § decomposição faceta ii).
- `hooks/hooks.json` — `Stop` + `SessionStart` event bindings.
- `hooks/suggest_journal_close.py` — Stop hook auto-gated (triple gate: marker + `.claude/local/` + Logseq desktop closed); sugere `/journal-close` pós-`/run-plan`. Lógica independente do CLI.
- `hooks/suggest_session_start_tip.py` — SessionStart hook (gate único cwd-matching contra REPOS.md owned/active, filtro NEGATIVO); sugere `/journal-load --days 2 --bucket <repo>`. Per ADR-001 Sub-decisão 6 Adendo v0.2.0 (2026-06-16).
- `tests/test_suggest_session_start_tip.py` — suite pytest parcial (12 testes) sob critério parsing-complexo per ADR-002 § Decisão 6 Adendo (2026-06-16). Demais subcomandos seguem validação manual.
- `docs/decisions/ADR-001-skills-de-bridge.md` — mechanical ADR (11 sub-decisions covering skill internals; SD11 adicionada em v0.9.0 cobrindo `/wiki-compile` per Onda 2 do roadmap knowledge layer do meta-system).
- `docs/decisions/ADR-002-materializacao-cli-mb.md` — materialização do CLI mb substituindo Tier 1 MCP candidato implícito (per `meta-system` ADR-016).

## Hard runtime assumptions (not configurable)

These paths are hardcoded in skills. Changing them requires patching the skills, not config:

- `~/Notes/logseq/` — Logseq graph root.
- `~/Notes/logseq/journals/YYYY_MM_DD.md` — daily journal canonical filename (Logseq's `_` separator + local TZ date — ver ADR-001 § Sub-decisão 1 Adendo v0.2.1).
- `~/Notes/logseq/pages/<basename>.md` — Project Page canonical naming.
- `~/Notes/logseq/pages/{Project Template,daily-journal}.md` — schema templates the skills consume. (`session-close.md` archived per ADR-001 Sub-decisão 3 § Adendo v0.2.0; `weekly-review.md` archived per Sub-decisão 5 § Adendo v0.2.0 — composição in-skill substituiu consumo de template.)
- `~/.mrconfig` — `mr` config for cluster lookup in `/init-logseq-project`.
- `~/Projects/meta-system/REPOS.md` — fallback cluster lookup (the operator's [meta-system](https://github.com/fppfurtado/meta-system) repo via the `~/Projects` symlink).

## Conventions

- Skills end with `## O que NÃO fazer` listing scope guards (same convention as pragmatic-dev-toolkit per its philosophy).
- Commit messages follow Conventional Commits in English (toolkit's pattern).
- Skill body in PT-BR (narrative); identifiers, frontmatter keys, and file paths in English (toolkit's pattern).

## What Claude will typically be asked here

- Adjust skill bodies (thin orchestrators) ou módulos `meta_bridge.*` (write engine) as Logseq setup evolves.
- Add new ADR via direct Write (no `/new-adr` skill installed in this plugin by default — `pragmatic-dev-toolkit` provides that).
- Bump version (sincroniza `meta_bridge/__init__.py:__version__` + `plugin.json` + `marketplace.json` via `/release` skill) + push.

## What Claude will NOT be asked here

- Generalize skills to other PKMs (Obsidian, Anytype, etc.). The plugin is intentionally Logseq-specific.
- Change the marker `[PRAGMATIC: plan-done]` — that's a public contract owned by `pragmatic-dev-toolkit`.

## Pragmatic Toolkit

<!-- pragmatic-toolkit:config -->
```yaml
paths:
  backlog: forge  # GitHub issues sem assignee; BACKLOG.md ## Concluídos preservado como histórico (per ADR-058 + migração 2026-06-20)
  version_files: [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "pyproject.toml", "meta_bridge/__init__.py"]
  changelog: CHANGELOG.md
  plans_dir: local
test_command: null
```

`plans_dir: local` declarado em 2026-06-12 a partir do refactor `/weekly-review` → `/journal-review` (modo local per [ADR-047](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-047-modo-local-paths-replicacao-cross-mode.md) do toolkit). Refactors substantivos das skills do bridge moram em `.claude/local/plans/` (gitignored — coerente com filosofia personal-tooling do plugin); planos cross-cutting de orquestração multi-repo continuam morando em [`meta-system`](https://github.com/fppfurtado/meta-system). Combinação `backlog: canonical + plans_dir: local` suportada per ADR-047.

## Histórico

Repo bootstrap em 2026-05-28, pivotando 7 commits originalmente landed em `pragmatic-dev-toolkit` (master local de Onda 4 do meta-system) que ficaram com escopo errado pro plugin público. Ver ADR-005 do meta-system → Origem para contexto da pivota.
