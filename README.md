# meta-bridge

Claude Code plugin materializing the **bridge between CC sessions and a Logseq cognitive graph**. Personal-workflow plugin — assumes Logseq at `~/Notes/logseq/` with the operator's daily-journal heading convention (Inbox / Doing / Waiting / Notes / Decisions).

Companion to [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit) (referenced from the [meta-system](https://github.com/fppfurtado/meta-system) architecture as Camada 3 — Bridge).

**Public for transparency**, not for general adoption — most users won't have the assumed setup. If you do (Logseq + the operator's heading convention), feel free to fork.

## What's inside

| Component | Type | What it does |
|-----------|------|--------------|
| `/journal-note <content>` | Skill | Appends a timestamped block to today's Logseq journal (`~/Notes/logseq/journals/YYYY_MM_DD.md`) with auto-detected `[[<repo-basename>]]` ref. Requires Logseq desktop closed (`pgrep -xi logseq` gate). |
| `/journal-close` | Skill | Synthesizes the current CC session into a structured block appended under `## Notes` in today's journal, following the `session-close.md` schema. Probes git log since 2h + plan slug + repo basename; prompts operator for topic + decisions + follow-ups via batched AskUserQuestion. |
| `/init-logseq-project` | Skill | Creates or re-syncs the Project Page in the Logseq graph for the repo at cwd. Idempotent: preserves human-edited `status::`, `description::`, `## Follow-ups`, `## Decisões locais`; overwrites only 4 mechanical props (`cluster`, `subcluster`, `repo-path`, `repo-host`). Cluster resolution probes `~/.mrconfig` → `~/Projects/meta-system/REPOS.md` → operator enum. |
| `/weekly-review` | Skill | GTD wizard aggregating Inbox/Doing/Waiting blocks from journals of the last 7 days (excluding today), prompting classification (Keep/Next step/Archive/Defer next Monday) batched 4-per-AskUserQuestion. Decisions accumulate in memory; edits apply atomically after composing the weekly block (failure-closed under crash mid-wizard). |
| `suggest_journal_close` | Hook | `Stop` event hook, auto-gated triplo (canonical marker `[PRAGMATIC: plan-done]` emitted by pragmatic-dev-toolkit's `/run-plan` in its done step + `.claude/local/` in cwd + `~/Notes/logseq/` exists AND Logseq desktop closed). When all pass, prints a soft suggestion to stderr nudging toward `/journal-close`. |

## Installation

```
/plugin marketplace add fppfurtado/meta-bridge
/plugin install meta-bridge@fppfurtado-meta-bridge
```

## Runtime dependencies

- **Logseq** desktop installed at `~/Notes/logseq/` (path is hardcoded — change requires patching skills).
- The operator's daily-journal template with `## Inbox`, `## Doing`, `## Waiting`, `## Notes`, `## Decisions` headings (defined in the [logseq-notes](https://github.com/fppfurtado/logseq-notes) repo template).
- Schema templates in `~/Notes/logseq/pages/`: `session-close.md`, `weekly-review.md`, `Project Template.md`, `daily-journal.md` (also from `logseq-notes`).
- **Hook only**: [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit) ≥ v2.13.0 installed (for the `[PRAGMATIC: plan-done]` marker emission by `/run-plan`). Hook gates silent if marker absent.

Skills fail closed with clear messages when dependencies are missing — no silent corruption.

## Architecture context

`meta-bridge` materializes **Camada 3 (Bridge)** of the operator's [meta-system architecture](https://github.com/fppfurtado/meta-system) — read [ADR-005 of meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) for the cross-cutting "what + why", and [ADR-001 of meta-bridge](docs/decisions/ADR-001-skills-de-bridge.md) for the mechanical "how" (8 sub-decisions covering all skill internals).

The plugin is **unidirectional**: the graph is destination of capture, not source that triggers actions on FS or `.mrconfig`. Inverse flow is out of scope (gatilho de revisão in ADR-005 covers reopening).

## License

MIT — see [LICENSE](LICENSE).
