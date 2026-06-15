# meta-bridge

Claude Code plugin materializing the **bridge between CC sessions and a Logseq cognitive graph**. Personal-workflow plugin — assumes Logseq at `~/Notes/logseq/` with daily-journal hashtag-bucket convention (`- #<domínio>` top-level + native GTD task markers) per [ADR-006 of meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) (v0.2.0+).

Companion to [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit) (referenced from the [meta-system](https://github.com/fppfurtado/meta-system) architecture as Camada 3 — Bridge).

**Public for transparency**, not for general adoption — most users won't have the assumed setup. If you do (Logseq + hashtag-bucket capture convention), feel free to fork.

## What's inside

A partir de v0.7.0, substância de write vive no **CLI `mb`** (Python via Click); 4 das 5 skills viram thin orchestrators que delegam writes ao CLI. Substância heurístico-semântica (matching, princípios editoriais, heurísticas detectivas, cluster prompt) permanece nas skills. Decisão registrada em [ADR-002](docs/decisions/ADR-002-materializacao-cli-mb.md) — materialização por critério target-aware de [`meta-system` ADR-016](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-016-target-aware-packaging-mecanico-substitui-mcp-first.md).

| Component | Type | What it does |
|-----------|------|--------------|
| `/journal-note <content>` | Skill (thin orchestrator) → `mb journal-note` | Skill deriva `--domain` (git toplevel → basename; senão → AskUserQuestion enum); CLI faz find-or-create top-level `- #<domínio>` + append child task. Native GTD marker preservado quando input começa com `TODO`/`DOING`/`WAITING`/`DONE`/`CANCELLED `. Sub-bullets mecânicos: `commit:<hash>`, `plan:<slug>`. Sanitização kebab-case + NFD-strip de acentos PT-BR. Gate `pgrep -xi logseq`. |
| `/journal-close` | Skill (thin orchestrator) → `mb journal-close` | Skill faz matching semântico de TODO/WAITING ↔ DONE da sessão CC + síntese editorial humano-amigável agrupada por bucket; CLI é write engine determinístico recebendo payload markdown via stdin (`## Append` + `## Transitions`). Dedup por `commit:<hash>`, modify-in-place atomic, bootstrap journal. |
| `/journal-load [--days N] [--bucket #X]` | Skill (MD-only) | Read-only — carrega conteúdo de journals na working memory do CC. **Permanece markdown-only** (sem assimetria CLI > MD; ver ADR-002 § Decisão 5). Default = journal de hoje completo; `--days N` estende janela retroativa; `--bucket #X` filtra. Exempt do gate Logseq. |
| `/init-logseq-project` | Skill (thin orchestrator) → `mb init-project` | CLI faz lookup mecânico de cluster (`~/.mrconfig` → `~/Projects/meta-system/REPOS.md`) + bootstrap via Project Template + props mecânicas idempotentes; skill orquestra `AskUserQuestion` enum 9-cluster apenas no fallback. Preserva props humanas (`status::`, `description::`, blocos `##`). |
| `/journal-review [--days N\|--from D --to D] [--interactive] [--write-summary] [--bucket-min-journals N] [--bucket-min-tasks N] [--zombie-days N] [--emerging-min-mentions N]` | Skill (thin orchestrator) → `mb journal-review` | Skill aplica 4 heurísticas semânticas (`task-closure-by-context`, `task-zombie`, `bucket-underused`, `bucket-emerging`) sobre scan estruturado emitido pelo CLI. Preview-first via AskUserQuestion (Aplicar tudo / Cherry-pick / Cancelar). CLI scan emite markers ativos + DONE-tasks + narrativas + inventário de buckets em ordem cronológica; `--apply` aplica transições. Skill retém findings em conversation memory entre invocações. Wizard residual via `--interactive`. 4 flags opcionais de threshold (K=3/M=3/T=21/N=4 defaults) sobrescrevem heurísticas 2b/2c/2d caso-a-caso. Sucessor de `/weekly-review`. |
| `suggest_journal_close` | Hook | `Stop` event hook, auto-gated triplo (canonical marker `[PRAGMATIC: plan-done]` emitted by pragmatic-dev-toolkit's `/run-plan` in its done step + `.claude/local/` in cwd + `~/Notes/logseq/` exists AND Logseq desktop closed). When all pass, prints JSON `{"systemMessage": ...}` to stdout (CC 2.1.x canonical non-blocking soft notification) nudging toward `/journal-close`. Lógica independente do CLI. |

## CLI `mb`

CLI standalone Python instalável via `pipx`:

```bash
pipx install -e /path/to/meta-bridge
mb --help
```

Subcomandos:
- `mb journal-note [--domain <name>] "<content>"` — find-or-create bucket + append child task (sem `--domain`: deriva basename do git toplevel da cwd)
- `mb journal-close` (stdin: `## Append` + `## Transitions`) — write engine pra fechamento de sessão
- `mb journal-review [--days N | --from D1 --to D2]` (scan) ou `mb journal-review --apply` (stdin transitions)
- `mb init-project [--repo-path <path>] [--basename <name>] [--cluster <name>] [--subcluster <name>]`

Sem suite de testes formal — validação manual por subcomando contra graph Logseq real (golden path coberto).

## Installation

CLI:
```bash
pipx install -e /path/to/meta-bridge
```

Plugin Claude Code:
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

`meta-bridge` materializes **Camada 3 (Bridge)** of the operator's [meta-system architecture](https://github.com/fppfurtado/meta-system) — read [ADR-005 of meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) for the cross-cutting "what + why", and [ADR-001 of meta-bridge](docs/decisions/ADR-001-skills-de-bridge.md) for the mechanical "how" (10 sub-decisions covering all skill internals).

The plugin is **unidirectional**: the graph is destination of capture, not source that triggers actions on FS or `.mrconfig`. Inverse flow is out of scope (gatilho de revisão in ADR-005 covers reopening).

## License

MIT — see [LICENSE](LICENSE).
