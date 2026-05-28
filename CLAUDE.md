# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this repository is

A **Claude Code plugin** materializing the bridge between CC sessions and a Logseq cognitive graph. Companion to [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit); architecture context in [`meta-system`](https://github.com/fppfurtado/meta-system) (private).

No build, no tests, no runtime in the plugin itself. The "code" is markdown frontmatter (skills) + short Python script (hook). Validation is manual — install the plugin into a project with the assumed Logseq setup and exercise each skill.

## Plugin layout

- `.claude-plugin/plugin.json` — plugin manifest.
- `.claude-plugin/marketplace.json` — exposes the plugin to `/plugin marketplace add`.
- `skills/<name>/SKILL.md` — 4 skills (`/journal-note`, `/journal-close`, `/init-logseq-project`, `/weekly-review`).
- `hooks/hooks.json` — `Stop` event binding for `suggest_journal_close.py`.
- `hooks/suggest_journal_close.py` — auto-gated Python script (triple gate: marker + `.claude/local/` + Logseq desktop closed).
- `docs/decisions/ADR-001-skills-de-bridge.md` — mechanical ADR (8 sub-decisions covering skill internals).

## Hard runtime assumptions (not configurable)

These paths are hardcoded in skills. Changing them requires patching the skills, not config:

- `~/Notes/logseq/` — Logseq graph root.
- `~/Notes/logseq/journals/YYYY_MM_DD.md` — daily journal canonical filename (Logseq's `_` separator + UTC date).
- `~/Notes/logseq/pages/<basename>.md` — Project Page canonical naming.
- `~/Notes/logseq/pages/{session-close,weekly-review,Project Template,daily-journal}.md` — schema templates the skills consume.
- `~/.mrconfig` — `mr` config for cluster lookup in `/init-logseq-project`.
- `~/Projects/meta-system/REPOS.md` — fallback cluster lookup (the operator's [meta-system](https://github.com/fppfurtado/meta-system) repo via the `~/Projects` symlink).

## Conventions

- Skills end with `## O que NÃO fazer` listing scope guards (same convention as pragmatic-dev-toolkit per its philosophy).
- Commit messages follow Conventional Commits in English (toolkit's pattern).
- Skill body in PT-BR (narrative); identifiers, frontmatter keys, and file paths in English (toolkit's pattern).

## What Claude will typically be asked here

- Adjust skill bodies as Logseq setup evolves.
- Add new ADR via direct Write (no `/new-adr` skill installed in this plugin by default — `pragmatic-dev-toolkit` provides that).
- Bump version + push.

## What Claude will NOT be asked here

- Generalize skills to other PKMs (Obsidian, Anytype, etc.). The plugin is intentionally Logseq-specific.
- Change the marker `[PRAGMATIC: plan-done]` — that's a public contract owned by `pragmatic-dev-toolkit`.

## Pragmatic Toolkit

<!-- pragmatic-toolkit:config -->
```yaml
paths:
  decisions_dir: docs/decisions
test_command: null
```

Sem `plans_dir` — plans para este plugin moram em [`meta-system`](https://github.com/fppfurtado/meta-system) (cross-cutting orchestration) ou são ad-hoc. Sem `backlog` — follow-ups são capturados via `/note --local` na pasta `.claude/local/` quando relevante.

## Histórico

Repo bootstrap em 2026-05-28, pivotando 7 commits originalmente landed em `pragmatic-dev-toolkit` (master local de Onda 4 do meta-system) que ficaram com escopo errado pro plugin público. Ver ADR-005 do meta-system → Origem para contexto da pivota.
