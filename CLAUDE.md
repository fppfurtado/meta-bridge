# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this repository is

A **Claude Code plugin** materializing the bridge between CC sessions and a Logseq cognitive graph. Companion to [`pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit); architecture context in [`meta-system`](https://github.com/fppfurtado/meta-system) (private).

Substância de write vive em **`meta_bridge` (Python CLI via Click)** — entry-point `mb` instalável via `pipx install -e .`. 4 subcomandos (`mb journal-note`, `mb journal-close`, `mb journal-review`, `mb init-project`) cobrem o trabalho mecânico das 4 skills substantivas; `/journal-load` permanece markdown-only. As 4 SKILL.md correspondentes viram **thin orchestrators** que delegam writes ao CLI e preservam substância heurístico-semântica (matching, princípios editoriais de síntese, 4 heurísticas detectivas, cluster prompt). Pós-Onda 2 do roadmap knowledge layer block-first do meta-system (2026-06-18), plugin ganha **6ª skill `/wiki-compile`** (knowledge layer Camada 3 — entity pages enriquecidas) com sub-tool Python determinístico standalone em `skills/wiki-compile/sub-tools/compile.py` (pattern orquestrador heurístico + sub-tool determinístico per meta-system ADR-017 § decomposição faceta ii). Pós-Onda 5 Faceta 1 do mesmo roadmap (2026-06-20), plugin ganha **7ª skill `/enrich-blocks`** (Camada 2a Enriched Blocks — properties `provenance::` + `entities::` em sub-bullets de buckets do journal) com sub-tool standalone em `skills/enrich-blocks/sub-tools/enrich.py` + 3º hook bridging `suggest_enrich_blocks` (Stop event, categoria operacional nova per ADR-001 SD12 — hook como trigger de background write substantivo via Popen detached; distinta de SD6 soft notification). Pós-Onda 5 Faceta 2 (2026-06-23), plugin ganha **8ª skill `/source-digest`** (Camada 2b source-flow — digest de clips do journal + arquivos do filesystem) + 4º hook bridging `suggest_source_digest` (Stop event notifier puro; sem Popen dispatch — LLM-dependente per ADR-001 SD13). Plugin ganha também **9ª skill `/inbox-aggregate`** (agrega tasks de repos Forge TJPA via `glab` + capturas PKM-native `#inbox` inline no bucket `#inbox` do journal de hoje; pattern read-N-sources → write-to-logseq análogo a `/wiki-compile` per ADR-001 SD1) com sub-tool determinístico standalone em `skills/inbox-aggregate/sub-tools/inbox_aggregate.py` (parse + dedup exact-match + write) governada por [logseq-notes ADR-004](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-004-inbox-aggregator-schema.md). Plugin ship 4 hooks bridging (Stop sugerindo `/journal-close`; Stop disparando enrichment background quando journal de hoje tem buckets recém-fechados sem provenance; Stop sugerindo `/source-digest` quando journal tem clip não-digerido; SessionStart sugerindo `/journal-load` quando cwd casa com repo owned/active). Validação manual cobre golden path dos subcomandos mecânicos; suite parcial pytest cobre subcomandos/hooks/sub-tools com parsing-complexo (per ADR-002 § Decisão 6 Adendo 2026-06-16 — critério parsing-complexo → pytest; mecânico → manual). Pytest formal pro sub-tool `wiki-compile/sub-tools/compile.py` pendente em BACKLOG ## Próximos; pytest pro sub-tool `enrich-blocks/sub-tools/enrich.py` shipou junto (9 cenários cobrindo idempotência + cross-bucket contamination + canonical property line shape).

## Plugin layout

- `.claude-plugin/plugin.json` — plugin manifest.
- `.claude-plugin/marketplace.json` — exposes the plugin to `/plugin marketplace add`.
- `pyproject.toml` + `meta_bridge/` — Python package (hatchling minimalista; dependência única `click >= 8.0`). Entry-point `mb = meta_bridge.cli:cli`.
- `meta_bridge/{cli.py, journal_note.py, journal_close.py, journal_review.py, init_project.py, _paths.py}` — write engine + 4 subcomandos.
- `skills/<name>/SKILL.md` — 9 skills (`/journal-note`, `/journal-close`, `/journal-load`, `/init-logseq-project`, `/journal-review`, `/wiki-compile`, `/enrich-blocks`, `/source-digest`, `/inbox-aggregate`). 4 são thin orchestrators do CLI; `/journal-load` permanece markdown-only; `/wiki-compile` (Onda 2 do roadmap knowledge layer), `/enrich-blocks` (Onda 5 Faceta 1) e `/inbox-aggregate` seguem pattern orquestrador heurístico + sub-tool standalone em `sub-tools/<name>.py` (per meta-system ADR-017 § decomposição faceta ii; ADR-001 SD11 + SD12; `/inbox-aggregate` governada por logseq-notes ADR-004); `/source-digest` (Onda 5 Faceta 2) é thin orchestrator markdown-only sem sub-tool — digest é LLM-driven (per ADR-001 SD13).
- `hooks/hooks.json` — `Stop` (3 entries separadas) + `SessionStart` event bindings.
- `hooks/suggest_journal_close.py` — Stop hook auto-gated (triple gate: marker + `.claude/local/` + Logseq desktop closed); sugere `/journal-close` pós-`/run-plan`. Lógica independente do CLI.
- `hooks/suggest_enrich_blocks.py` — Stop hook auto-gated (4 itens: `.claude/local/` + `CLAUDE_PLUGIN_ROOT`+sub-tool + Logseq closed + journal de hoje com `closed::` recente sem `provenance::`); dispara `Popen(start_new_session=True)` background invocando `enrich-blocks/sub-tools/enrich.py --journal-today`. Per ADR-001 Sub-decisão 12 (2026-06-20).
- `hooks/suggest_source_digest.py` — Stop hook notifier puro (2 gates: journal de hoje existe + tem bloco com `tags:: clippings` sem `digested::`); sugere `/source-digest`. Sem Popen dispatch — digest é LLM-dependente per ADR-001 Sub-decisão 13 (2026-06-23).
- `hooks/suggest_session_start_tip.py` — SessionStart hook (gate único cwd-matching contra REPOS.md owned/active, filtro NEGATIVO); sugere `/journal-load --days 2 --bucket <repo>`. Per ADR-001 Sub-decisão 6 Adendo v0.2.0 (2026-06-16).
- `tests/test_suggest_session_start_tip.py` + `tests/test_inbox_aggregate.py` — suites pytest parciais sob critério parsing-complexo per ADR-002 § Decisão 6 Adendo (2026-06-16); a de `inbox_aggregate` cobre parse + dedup exact-match + write do sub-tool. Demais subcomandos seguem validação manual.
- `docs/decisions/ADR-001-skills-de-bridge.md` — mechanical ADR (13 sub-decisions covering skill internals; SD11 adicionada em v0.9.0 cobrindo `/wiki-compile` per Onda 2; SD12 (2026-06-20) cobrindo `/enrich-blocks` + hook dispatcher; SD13 (2026-06-23) cobrindo `/source-digest` + hook notifier).
- `docs/decisions/ADR-002-materializacao-cli-mb.md` — materialização do CLI mb substituindo Tier 1 MCP candidato implícito (per `meta-system` ADR-016).

## Hard runtime assumptions (not configurable)

These paths are hardcoded in skills. Changing them requires patching the skills, not config:

- `~/Notes/logseq/` — Logseq graph root.
- `~/Notes/logseq/journals/YYYY_MM_DD.md` — daily journal canonical filename (Logseq's `_` separator + local TZ date — ver ADR-001 § Sub-decisão 1 Adendo v0.2.1).
- `~/Notes/logseq/pages/<basename>.md` — Project Page canonical naming.
- `~/Notes/logseq/pages/sources/<slug>.md` — raw source pages criadas por `/source-digest` modo arquivo (per ADR-001 SD13); `provenance:: #source` + metadados + conteúdo extraído. Page-ref canônica: `[[sources/<slug>]]`.
- `~/Notes/logseq/pages/<slug>-digested.md` — digest pages criadas por `/source-digest` em ambos os modos (per ADR-001 SD13); `provenance:: #digested` + claims + síntese. Page-ref canônica: `[[<slug>-digested]]`.
- `~/Notes/logseq/pages/bucket-hygiene.md` — page agregadora de sugestões de higiene de bucket criadas por `/journal-review` v2 (per ADR-001 SD10 Adendo 2026-06-24); A2-style find-or-create + append forward-only (co-occurrence/rename-implicit/naming-drift). (Nota: o precedente A2 `pages/<categoria>.md` / `archived-buckets` tem o mesmo status hardcoded não-declarado — drift legado.)
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

`plans_dir: local` declarado em 2026-06-12 a partir do refactor `/weekly-review` → `/journal-review` (modo local per [ADR-047](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-047-modo-local-paths-replicacao-cross-mode.md) do toolkit). Refactors substantivos das skills do bridge moram em `.claude/local/plans/` (gitignored — coerente com filosofia personal-tooling do plugin); planos cross-cutting de orquestração multi-repo continuam morando em [`meta-system`](https://github.com/fppfurtado/meta-system). Combinação `backlog: forge + plans_dir: local` declarada em 2026-06-20 via migração das 6 entries de `## Próximos` para [issues abertas sem assignee](https://github.com/fppfurtado/meta-bridge/issues?q=is%3Aopen+is%3Aissue+no%3Aassignee); fica fora da recusa cross-mode do ADR-047 (modo forge é público por construção — ADR-058 § (i)).

## Histórico

Repo bootstrap em 2026-05-28, pivotando 7 commits originalmente landed em `pragmatic-dev-toolkit` (master local de Onda 4 do meta-system) que ficaram com escopo errado pro plugin público. Ver ADR-005 do meta-system → Origem para contexto da pivota.
