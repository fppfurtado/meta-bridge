# meta-bridge

Claude Code plugin materializing the **bridge between CC sessions and a Logseq cognitive graph**. Personal-workflow plugin — assumes Logseq at `~/Notes/logseq/` with daily-journal hashtag-bucket convention (`- #<domínio>` top-level + native GTD task markers) per [ADR-006 of meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) (v0.2.0+).

Companion to [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit) (referenced from the [meta-system](https://github.com/fppfurtado/meta-system) architecture as Camada 3 — Bridge).

**Public for transparency**, not for general adoption — most users won't have the assumed setup. If you do (Logseq + hashtag-bucket capture convention), feel free to fork.

## What's inside

| Component | Type | What it does |
|-----------|------|--------------|
| `/journal-note <content>` | Skill | Find-or-create top-level `- #<domínio>` bucket in today's Logseq journal + append child task. Domain derived from cwd (git repo → basename; outside git → AskUserQuestion enum `#thought`/`#draft`/`#idea` + Other with kebab-case sanitization). Native GTD marker preserved when input starts with `TODO `/`DOING `/`WAITING `/`DONE `/`CANCELLED `. Mechanical sub-bullets extracted: `commit:<hash>`, `plan:<slug>`. Requires Logseq desktop closed (`pgrep -xi logseq` gate). |
| `/journal-close` | Skill | Synthesizes the current CC session into `- DONE <subject>` tasks grouped by bucket `- #<repo>` with mechanical sub-bullets. Find-or-create idempotent cross-skill with prior `/journal-note` calls + intra-skill dedup by `commit:<hash>` (Stop hook firing twice doesn't duplicate). Multi-repo collection via explicit probe of cwds touched in session + `git log` per cwd. Synthesis-then-confirm UX via AskUserQuestion. |
| `/init-logseq-project` | Skill | Creates or re-syncs the Project Page in the Logseq graph for the repo at cwd. Idempotent: preserves human-edited `status::`, `description::`, `## Follow-ups`, `## Decisões locais`; overwrites only 4 mechanical props (`cluster`, `subcluster`, `repo-path`, `repo-host`). Cluster resolution probes `~/.mrconfig` → `~/Projects/meta-system/REPOS.md` → operator enum. |
| `/weekly-review` | Skill | GTD wizard collecting open task markers (`TODO`/`DOING`/`WAITING`) cross-journals of the last 7 days via strict regex `^\t- (TODO\|DOING\|WAITING) ` (1-tab indent — direct children of buckets only). Classification (Keep/Next step/Archive/Defer next Monday) batched 4-per-AskUserQuestion. Archive changes marker in-place to terminal (`DONE`/`CANCELLED`); defer moves task to destination journal preserving origin bucket. Decisions accumulate in memory; edits apply atomically. |
| `suggest_journal_close` | Hook | `Stop` event hook, auto-gated triplo (canonical marker `[PRAGMATIC: plan-done]` emitted by pragmatic-dev-toolkit's `/run-plan` in its done step + `.claude/local/` in cwd + `~/Notes/logseq/` exists AND Logseq desktop closed). When all pass, prints JSON `{"systemMessage": ...}` to stdout (CC 2.1.x canonical non-blocking soft notification) nudging toward `/journal-close`. |

## Installation

```
/plugin marketplace add fppfurtado/meta-bridge
/plugin install meta-bridge@fppfurtado-meta-bridge
```

## Runtime dependencies

- **Logseq** desktop installed at `~/Notes/logseq/` (path is hardcoded — change requires patching skills).
- The operator's daily-journal template (scaffold mínimo pós-v0.2.0; from the [logseq-notes](https://github.com/fppfurtado/logseq-notes) repo per [ADR-002 of logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisão 1).
- Active templates in `~/Notes/logseq/pages/`: `Project Template.md`, `daily-journal.md` (from `logseq-notes`). Templates `session-close.md` and `weekly-review.md` are archived in v0.2.0+ — skills compose in-skill.
- **Hook only**: [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit) ≥ v2.13.0 installed (for the `[PRAGMATIC: plan-done]` marker emission by `/run-plan`). Hook gates silent if marker absent.

Skills fail closed with clear messages when dependencies are missing — no silent corruption.

## Architecture context

`meta-bridge` materializes **Camada 3 (Bridge)** of the operator's [meta-system architecture](https://github.com/fppfurtado/meta-system) — read [ADR-005 of meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) for the cross-cutting "what + why", and [ADR-001 of meta-bridge](docs/decisions/ADR-001-skills-de-bridge.md) for the mechanical "how" (8 sub-decisions covering all skill internals).

The plugin is **unidirectional**: the graph is destination of capture, not source that triggers actions on FS or `.mrconfig`. Inverse flow is out of scope (gatilho de revisão in ADR-005 covers reopening).

## License

MIT — see [LICENSE](LICENSE).
