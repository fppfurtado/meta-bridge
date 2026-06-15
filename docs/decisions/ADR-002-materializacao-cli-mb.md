# ADR-002: Materialização CLI `mb` substituindo Tier 1 MCP candidato implícito

**Data:** 2026-06-15
**Status:** Proposto

## Origem

- **Decisão base (meta-system, cross-cutting):** [`meta-system` ADR-016](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-016-target-aware-packaging-mecanico-substitui-mcp-first.md) — substitui doutrina pré-existente "MCP-first para knowledge layer" por **critério target-aware** (MCP-1/2/3 vs CLI-1/2/3/4) aplicado caso-a-caso.
- **Decisão base (meta-system, cross-cutting):** [`meta-system` ADR-013](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-arquitetura-meta-sistema-cinco-camadas.md) § Princípios herdados refinado por ADR-016 — *"MCP canonical para knowledge layer"* passa a ser princípio **condicionado a assimetria substantiva**, não default automático.
- **Investigação:** revisitação retroativa do `meta-system` (Bloco 4 de `revisitacao-retroativa-materializacoes-pre-adr-016.md`, commit `6586e5a`) aplicou critério target-aware às 5 materializações pré-ADR-016. Para `meta-bridge`:
  - **MCP-1/2/3 = 0/3**: ops filesystem atomic (sem state long-running); sem state in-memory necessário (skills são one-shot); sem mid-turn discovery essencial (operador invoca skills explicitamente, não há discovery automático).
  - **CLI-1/2/3/4 = 4/4**: uniformidade de invocação cross-stack; standalone-vs-orchestrated (skills MD podem ser thin orchestrators); teste em isolamento trivial (subprocess + verificação de filesystem); menos sobrecarga runtime que MCP server stay-alive.
- **Histórico de execução:** plano `materializar-cli-mb` em `.claude/local/plans/` (modo local per ADR-047 do toolkit) executado nesta sessão CC (2026-06-15) sob a worktree `materializar-cli-mb`. 6 blocos materializaram o CLI + cascataram skills.

## Contexto

ADR-001 (2026-05-28) bootstrapped o plugin com 5 skills markdown + 1 hook Python curto. Filosofia em CLAUDE.md à época: *"No build, no tests, no runtime in the plugin itself. The 'code' is markdown frontmatter (skills) + short Python script (hook)."*

Esta filosofia foi formulada **implicitamente sob doutrina `meta-system` pré-ADR-016** (MCP-first para knowledge layer). Naquela doutrina, `meta-bridge` figurava como **Tier 1 MCP candidato implícito** no snapshot doutrinal `TIER_SNAPSHOT_2026_06_11` em `meta-portability-mcp`.

Decisões duradouras a materializar agora:

- **(a) Materializar CLI standalone**: pacote Python `meta_bridge` com entry-point `mb` instalável via `pipx install -e .`. 4 subcomandos cobrem as 4 skills substantivas (`journal-note`, `journal-close`, `journal-review`, `init-project`); `/journal-load` permanece MD-only.
- **(b) Cascateamento das skills**: 2 caminhos candidatos no `/triage` — (i) thin orchestrators invocando CLI internamente vs (ii) skills descontinuadas, operador roda `mb` direto. Operador escolheu (i) preservando UX dual `/slash-command` (CC) + `mb <subcomando>` (Bash).
- **(c) Divisão substância CLI/skill**: per F3/F2 design-reviewer absorvidas, matching semântico e síntese editorial **ficam na skill**; CLI vira **write engine determinístico**.
- **(d) `--cluster` flag em `mb init-project`**: per F1 design-reviewer, skill MD orquestra cluster prompt; CLI exige flag ou falha. Implementação relaxa: CLI tenta lookups mrconfig → REPOS.md antes de exigir flag (caminho-comum sem skill intervir).
- **(e) Sem suite de testes formal**: validação manual por subcomando cobre golden path no MVP.
- **(f) Manifests `plugin.json`/`marketplace.json` em PT-BR**: descriptions seguem convenção pré-existente das SKILL.md em PT-BR. Contradição não-bloqueante com `pragmatic-dev-toolkit/philosophy.md` § Convenção de idioma (default EN para marketplace) reconhecida — plugin é personal-tooling, audiência efetiva é o operador.

Sem este ADR, materialização CLI vira convention emergente; doutrina cross-cutting upstream fica sem registro local.

## Decisão

### Decisão 1 — Materializar CLI `mb` como pacote Python standalone

Pacote `meta_bridge`:
- `pyproject.toml` com build system `hatchling` minimalista.
- Dependência única: `click >= 8.0`.
- Entry-point: `mb = meta_bridge.cli:cli`.
- Layout: `meta_bridge/{__init__.py, cli.py, _paths.py, journal_note.py, journal_close.py, journal_review.py, init_project.py}`.
- Versão sincronizada com `plugin.json`/`marketplace.json` via `/release` skill (duplicação consciente; alternativa `importlib.metadata` rejeitada por dependência runtime de instalação correta).

Subcomandos:
- `mb journal-note --domain <name> "<content>"` — find-or-create bucket + append child task.
- `mb journal-close` (stdin) — write engine recebendo `## Append` + `## Transitions`.
- `mb journal-review [--days N | --from D1 --to D2]` (scan) ou `mb journal-review --apply` (stdin transitions).
- `mb init-project [--repo-path <path>] [--basename <name>] [--cluster <name>] [--subcluster <name>]`.

Gate `pgrep -xi logseq` (failure-closed) reusado entre os 4 subcomandos via `fail_if_logseq_open()` em `cli.py`.

### Decisão 2 — Cascateamento: 4 SKILL.md viram thin orchestrators

4 skills (`/journal-note`, `/journal-close`, `/journal-review`, `/init-logseq-project`) refatoradas pra **thin orchestrators**:
- Preservam `frontmatter` (name, description), `## Argumentos`, `## O que NÃO fazer`, scope guards narrativos.
- Substância de write (find-or-create, bootstrap, modify-in-place, regex scan, lookups mrconfig/REPOS.md, sanitização) migra para `meta_bridge.*`.
- Substância **heurístico-semântica** (matching TODO ↔ DONE, 4 heurísticas detectivas, princípios editoriais de síntese, cluster prompt fallback) **permanece na skill**.

`/journal-load` permanece **inalterada** (pure file-read; sem assimetria substantiva CLI > MD; rebatida ver § Decisão 5 abaixo).

Hook `hooks/suggest_journal_close.py` permanece intacto (lógica independente do CLI; sem dependência circular).

### Decisão 3 — Divisão substância CLI/skill por F3/F2 design-reviewer

- **F3 `journal-close`**: skill compõe payload com transições in-place já decididas (paths/linhas/before→after); CLI recebe via stdin e aplica writes atomicamente sem refazer matching semântico.
- **F2 `journal-review`**: CLI scan emite markdown estruturado (Active markers / DONE tasks / Narratives / Bucket inventory) em ordem cronológica ascendente; skill retém findings em conversation memory entre invocações e re-invoca `mb journal-review --apply` com instruções concretas (não IDs opacos).

### Decisão 4 — `mb init-project` cluster resolution per F1 absorption

Ordem:
1. `--cluster <name>` passado → usar direto (override absoluto, pula lookups).
2. `~/.mrconfig` lookup (path normalizado via `readlink`).
3. `~/Projects/meta-system/REPOS.md` lookup (tabela markdown + walk-back pra heading `## <cluster>`).
4. Sem nenhum → exit non-zero orientando setup.

Skill `/init-logseq-project` orquestra `AskUserQuestion` enum 9-cluster (per `meta-system` ADR-003) **apenas no fallback do fallback** — caminho-comum resolve sem skill intervir. Nota sobre F1: implementação relaxa a polaridade estrita "CLI exige `--cluster` ou falha"; CLI tenta lookups primeiro.

### Decisão 5 — `/journal-load` permanece MD-only

Skill é pure file-read (composição inline na sessão CC via `Read` nativo do Claude de N journals). Sem heavy lifting Python, sem matching contra dado real, sem decisão algorítmica.

Migrar para CLI quebraria o modelo: subcomando precisaria *retornar conteúdo dos journals* para o operador colar — pior UX que `Read` direto. Critério target-aware ADR-016: assimetria substantiva CLI > MD **não dispara**.

### Decisão 6 — Sem suite de testes formal no MVP

Plugin permanece sem `tests/` formal. Validação manual `## Verificação manual` por subcomando cobre golden path. Validação contra graph Logseq real executada nesta sessão CC (Blocos 2-5) confirmou comportamento para casos comuns.

**Gatilho de revisão refinado** (per F6 design-reviewer): incidente reportado pelo operador **OU** finding de `/journal-review` apontando para drift correlacionado a invocação CLI — regressão silenciosa em write idempotente pode ficar invisível por semanas em journals rotacionais.

### Decisão 7 — Manifests preservam PT-BR

`plugin.json` e `marketplace.json` descriptions seguem PT-BR convencional (alinhado a SKILL.md frontmatter em PT-BR). Contradição não-bloqueante com `pragmatic-dev-toolkit/philosophy.md` § Convenção de idioma (default EN para marketplace) **reconhecida**: plugin é personal-tooling, audiência efetiva é o operador. Canonical EN reservado para revisitação se adoção externa emergir.

### Decisão 8 — Filosofia CLAUDE.md revisitada (a materializar no Bloco 8)

CLAUDE.md § "What this repository is" será reescrito no Bloco 8 do plano `materializar-cli-mb`:
- Substituir *"No build, no tests, no runtime in the plugin itself. The 'code' is markdown frontmatter (skills) + short Python script (hook)."*
- Por formulação refletindo CLI: substância vive em `meta_bridge` (Python CLI via Click) + frontmatter de skills (thin orchestrators) + hook curto.
- Sem suite de testes formal; validação manual por subcomando.

§ "Plugin layout" ganha bullet `pyproject.toml` + `meta_bridge/` package. § "What Claude will NOT be asked here" preservado intacto.

### Decisão 9 — Invariantes mecânicos herdados de ADR-001 preservados na CLI (per F4 design-reviewer)

Os 3 invariantes mecânicos cristalizados em Adendos de ADR-001 ao longo de Ondas anteriores são **preservados** pelos módulos `meta_bridge.*` correspondentes:

- **Bootstrap journal via `daily-journal.md` template** com skip wrapper + dedent 1 tab fixo (Sub-decisão 1 Adendo v0.2.2 + Sub-decisão 3 Adendo v0.4.2 + Sub-decisão 10 Adendo v0.3.1) — implementado em `meta_bridge.journal_note.bootstrap_journal()` (reusado por `journal_close` via import).
- **Macro substitution `<% current page %>` → `[[<basename>]]`** em `init-project` (Sub-decisão 4 Adendo 2026-05-28) — implementado em `meta_bridge.init_project.bootstrap_from_template()`.
- **Find-or-create idempotente cross-skill do bucket** (paralelo a [`meta-system` ADR-006](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) § Decisão § 1) — implementado em `meta_bridge.journal_note.find_or_create_bucket()` (reusado por `journal_close` via import).

Decisão F4 design-reviewer absorvida no `/triage` (2026-06-15): invariantes herdados explicitados como contrato preservado — não re-derivados ad-hoc por cada módulo do CLI.

## Consequências

**Positivas:**
- CLI `mb` direto via Bash em qualquer ambiente Python ≥ 3.10 — ergonomia uniforme.
- Skills MD ficam finas (≤55 linhas para `/journal-note` e `/init-logseq-project`; `/journal-close` e `/journal-review` retêm substância semântica genuína).
- Substância de write testável em isolamento via `click.testing.CliRunner` + `tempfile` (validado nos Blocos 2-5).
- Filosofia plugin clarificada: CLI determinístico + skill heurístico-semântica + hook curto. Divisão coerente com critério target-aware ADR-016.
- Materialização CLI ergonomicamente alinhada com demais plugins do meta-sistema pós-ADR-016 (uniformidade cross-stack).

**Negativas:**
- 2 superfícies pra sincronizar (CLI Python + SKILL.md narrativa) — mitigado por skills enxutas + escopo limitado da SKILL.md a substância semântica.
- Filosofia "no build, no tests, no runtime" do CLAUDE.md fica obsoleta — substituída pela formulação revisada (Decisão 8).
- Operador precisa rodar `pipx install -e .` no setup inicial; sem CI/CD pra automatizar (out-of-scope).

**Neutras:**
- `/journal-load` permanece MD-only — divergência consciente do princípio "cascatear todas as 4 skills"; coerente com critério target-aware.
- Hook `suggest_journal_close.py` permanece intacto — divergência consciente; sem dependência circular justifica.

## Alternativas consideradas

- **(A) Manter MCP candidato em vez de migrar pra CLI**: rejeitada por critério target-aware ADR-016 (MCP-1/2/3 = 0/3).
- **(B) Skills descontinuadas, operador roda `mb` direto**: rejeitada — quebra ergonomia `/slash-command` que operador valoriza no CC.
- **(C) ADR-002 carrega todo o cascateamento sem Adendos em ADR-001**: rejeitada — viola ADR-034 critério de Adendo do toolkit (mudança não invalida decisão central de cada Sub-decisão; é refinamento mecânico). Adendos cirúrgicos preservam histórico de Sub-decisões 1/3/4/10.
- **(D) Importlib.metadata para versão single-source**: rejeitada — adiciona dependência runtime de instalação correta para resolver version; rodar `mb` de checkout não-instalado quebraria.
- **(E) Suite de testes formal `tests/` desde MVP**: rejeitada por YAGNI — validação manual cobre golden path; testes formais ativam só sob gatilho concreto.

## Cross-refs cross-repos

- [`meta-system` ADR-016](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-016-target-aware-packaging-mecanico-substitui-mcp-first.md) — critério target-aware aplicado.
- [`meta-system` ADR-013](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-arquitetura-meta-sistema-cinco-camadas.md) § Princípios herdados refinado por ADR-016.
- `meta-system/docs/plans/revisitacao-retroativa-materializacoes-pre-adr-016.md` Bloco 4 (commit `6586e5a` no meta-system) — onde a decisão de materializar `meta-bridge` como CLI foi cristalizada.
- [`pragmatic-dev-toolkit` ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) — critério de Adendo aplicado em ADR-001 Sub-decisões 1/3/4/10.
- ADR-001 deste repo — 4 Sub-decisões (1, 3, 4, 10) ganham Adendo cirúrgico registrando `CLI thin orchestrator: substância write migra para meta_bridge.<modulo>; SKILL.md preserva frontmatter + scope guards + princípios editoriais; decisão central intacta`.

**Faceta cross-repo pendente**: atualizar snapshot `TIER_SNAPSHOT_2026_06_11` em `meta-portability-mcp/.../tools.py` removendo `meta-bridge` da lista Tier 1 MCP candidato. Coordenada via plano runbook em `meta-system` (per `meta-system` ADR-016 § Gatilho 5 + Mitigações) — out-of-scope deste plano local.

## Gatilhos de revisão

1. **Operador prefere descontinuar skills MD** (≥1 incidente real de fricção `/slash-command` invocation): refatorar pra Decisão alternativa (B); skill MD vira docs-only ou removida.
2. **Substância heurístico-semântica fica trivial** (refinamentos editoriais convergem pra schema mecânico estável): reabrir migração da síntese editorial de `/journal-close` pra CLI com flag (`--reflective` vs `--mechanical`).
3. **Incidente real de regressão silenciosa em write CLI** (operador reporta drift correlacionado): adicionar suite `tests/` por subcomando — gatilho refinado per F6 design-reviewer.
4. **Faceta cross-repo (c) executada**: atualizar referência ao snapshot `TIER_SNAPSHOT_2026_06_11` aqui; cross-ref pra plano runbook materializado.
5. **Click vs Typer**: ergonomia Click incomoda em manutenção ou contribuidor externo pede Typer: revisitar dependência (impacta `pyproject.toml`).
6. **Versão single-source via `importlib.metadata`**: incidente real de drift entre `__init__.py` e `plugin.json` revela custo da duplicação: reabrir Alternativa (D).
7. **Adoção externa emerge** (≥1 report de terceiro querendo usar `mb` standalone fora do plugin CC): revisitar manifests EN per `philosophy.md` § Convenção de idioma + considerar publicação PyPI.

## Implementação

Materialização em sessão CC `materializar-cli-mb` (2026-06-15) no working dir `meta-bridge/.worktrees/materializar-cli-mb`. Commits (skeleton + 4 subcomandos CLI + skills thin orchestrators + ADR doutrinal + realign editorial) + Adendos em ADR-001 Sub-decisões 1, 3, 4, 10.
