# Changelog

## 0.18.0 — 2026-06-24

### Added

- **`/journal-review` v2 — trio de heurísticas estruturais de bucket**: `bucket-co-occurrence` (fusão A∪B), `bucket-rename-implicit` (A→A' + tasks órfãs), `bucket-naming-drift` (Levenshtein); geração de candidatos determinística no CLI + judgment semântico na skill; apply aditivo forward-only em `pages/bucket-hygiene.md` ([#33](https://github.com/fppfurtado/meta-bridge/pull/33)).
- **Contrato de reconciliação `#inbox` em `/journal-close` + `/journal-review`** (ADR-001 SD14): discrimina entries Forge-synced (informacional read-mostly) de PKM-native (SSOT-in-place transicionável) por source hashtag ([#32](https://github.com/fppfurtado/meta-bridge/pull/32)).

## 0.17.0 — 2026-06-23

### Added

- **`/source-digest` modo URL (3º modo)**: artigos via WebFetch + vídeos YouTube via youtube-context (transcript+visual); redirects cross-host; raw source page com `url::`/`type:: web|video`, digested com `source::` ([#31](https://github.com/fppfurtado/meta-bridge/pull/31)).

### Notes

- `/inbox-aggregate` documentada como 9ª skill no CLAUDE.md.

## 0.16.0 — 2026-06-23

### Added

- **`/source-digest` skill + Stop hook notifier** (Onda 5 Faceta 2 — Camada 2b source-flow): digest de clips do journal + arquivos do filesystem ([#22](https://github.com/fppfurtado/meta-bridge/pull/22)).
- **`mb journal-close --date`**: flag CLI para escrever em um dia específico do journal ([#26](https://github.com/fppfurtado/meta-bridge/pull/26)).
- **`/wiki-compile --blocks` opcional**: auto-descoberta de pages-source por `entities::` (Passo 2-bis, pages-only, match literal `[[<entity>]]`); modo cirúrgico preservado ([#28](https://github.com/fppfurtado/meta-bridge/pull/28)).

### Fixed

- **`enrich-blocks` scoping**: `list_project_pages` filtra Project Pages canonical (presença de `repo-path::`) em vez de varrer todas as ~199 páginas do grafo ([#27](https://github.com/fppfurtado/meta-bridge/pull/27)).

## 0.15.0 — 2026-06-22

### Added

- change bucket-underused predicate AND→OR

### Notes

- add SD10 Adendo v0.3.3 documenting AND→OR calibration; bump plugin.json to 0.14.0 for CC cache invalidation

## 0.14.0 — 2026-06-22

### Added

- **`/inbox-aggregate` expansão non-task** (Bloco 2 [#41](https://github.com/fppfurtado/meta-system/issues/41)). Step 4 do SKILL.md ganha grep adicional `^\t+- (?!TODO|DOING|WAITING).*#inbox` (indentação `\t+` exclui Papel 1 top-level). Sub-tool expandido: `parse_pkm_non_tasks`, `content_key` para dedup cross-type (strip marker prefix antes de comparar), campo `type` por item no JSON de saída (`forge`/`pkm_task`/`pkm_non_task`), `--pkm-non-tasks` arg, contadores separados `count_pkm_task` + `count_pkm_non_task` (backward compat via `count_pkm` total). 14 testes novos (cenários 9-11); 44 total.

## 0.13.1 — 2026-06-22

### Fixed

- SKILL.md Step 3 de `/inbox-aggregate`: glab flags corrigidos (`-O json`, `--assignee=@me`), extração slim `iid`+`title` para evitar limite de argumento CLI com `description` multi-MB.

## 0.13.0 — 2026-06-22

### Added

- **`/inbox-aggregate` skill v0 + sub-tool + pytest suite** (Bloco 2 Fase 1 [#18](https://github.com/fppfurtado/meta-system/issues/18)). Skill orquestrador SKILL.md + sub-tool determinístico `inbox_aggregate.py` (parse issues Forge via `glab` + tasks PKM-native `#inbox` inline, dedup exact-match, find-or-create bucket `#inbox`, write ao journal). Gate `pgrep -xi logseq` failure-closed para write; read-only isento per ADR-001 Sub-decisão 9. 30 testes pytest cobrindo parse Forge, parse PKM-native, dedup, find-or-create bucket, edge cases (profundidade 2+, idempotência). Schema per `logseq-notes` ADR-004: hashtag inline `#<repo>` como atribuição de fonte; dedup semântico YAGNI.

## 0.12.1 — 2026-06-22

### Fixed

- isinstance(event, dict) guard em `suggest_journal_close.py` — JSON scalar input (null/string/array) atravessava try/except e quebrava em event.get(). Closes [#17](https://github.com/fppfurtado/meta-bridge/issues/17).

### Notes

- 4 testes pytest em `tests/test_suggest_journal_close.py` cobrindo null/string/array/empty stdin.

## 0.12.0 — 2026-06-21

### Added

- **`/enrich-blocks` skill + `suggest_enrich_blocks` hook + Sub-decisão 12** ([PR #20](https://github.com/fppfurtado/meta-bridge/pull/20)). 7ª skill `/enrich-blocks` (knowledge layer Camada 2a Enriched Blocks) + sub-tool determinístico standalone `skills/enrich-blocks/sub-tools/enrich.py` (pattern SD11 — orquestrador heurístico + sub-tool determinístico) + 3º hook bridging `suggest_enrich_blocks.py` (Stop event categoria operacional nova per ADR-001 SD12: hook como trigger de background write substantivo via `Popen(start_new_session=True)`; distinta de SD6 soft notification). Triple gate auto-gating (`.claude/local/` + `CLAUDE_PLUGIN_ROOT`+sub-tool + Logseq closed) + trigger detection (journal de hoje com bucket `closed::` recente sem `provenance::`). Materializa Onda 5 Faceta 1 do roadmap knowledge-layer block-first do meta-system. ADR-034 mecanicamente forçou SD12 nova (3 de 4 critérios pra Adendo SD6 falham).
- **Property `closed:: <ISO UTC>` emit em `mb journal-close`** (Adendo SD3 ADR-001). Write engine faz upsert de property `closed::` no bucket recém-tocado (appended >0 OR dedup >0). Idempotente (replace se presente, insert senão). Marker SSOT in-place per `logseq-notes` ADR-002 SD4 — consumido pelo hook block-flow enrich downstream.

### Notes

- **9 testes pytest formais** em `tests/test_enrich_blocks.py` cobrindo: idempotência, bucket vazio, journal ausente, matching contra Project Pages, page-link sem double brackets, dedup mention, regression cross-bucket contamination (lição NOTES 2026-06-20), atomic write design.
- **Capturas backlog forge**: #17 (`suggest_journal_close.py` defesa `isinstance`), #18 (Onda 5 Faceta 2 daemon source-flow), #19 (Onda 5 Faceta 3 `/wiki-lint`).
- **`README.md` + `CLAUDE.md`** atualizados: 7 skills + 3 hooks bridging; entries `/enrich-blocks` + `suggest_enrich_blocks` na tabela; `/journal-close` menciona `closed::` emit. ADR-001 § Consequências bumped de "10 sub-decisões / 5 skills + hook" para "12 sub-decisões / 7 skills + 3 hooks bridging".

## 0.11.0 — 2026-06-20

### Added

- **`/journal-review` v0.4.0 — apply estrutural automático (heurísticas 3-4)** ([PR #15](https://github.com/fppfurtado/meta-bridge/pull/15)). Heurísticas `bucket-underused` + `bucket-emerging` saem de report-only e ganham apply estrutural automático per ADR-001 § Sub-decisão 10 Adendo v0.4.0: **A2 aditiva** (`bucket-underused` → page agregadora `pages/<categoria>.md` com section `- ## Buckets arquivados` + entry + children por ref; categoria via critério mecanizável prefixo comum | domínio óbvio | fallback `archived-buckets`; journals históricos intactos — SSOT in-place per `logseq-notes` ADR-002 SD4 preservado) + **B2 forward-only** (`bucket-emerging` → bucket top-level no journal de hoje com naming canonical kebab-case lowercase per `logseq-notes` ADR-002 SD3 + sub-bullet `\t- (origem: ...)` opcional; sem rewrite retroativo). Payload `## Structural` paralelo a `## Transitions` legacy; backward compat preservado (regression test cobre `## Transitions`-only). Snapshot defensivo XDG cache dispensado por construção (apply aditivo + forward-only não-destrutivos); reabertura conjunta com A1/B1 se gatilho destrutivo emergir.

### Fixed

- **`apply_emerging_bucket` dedup origem vazava entre buckets** (qa-reviewer Gap 5 do PR #15). Loop não tinha break ao encontrar próximo top-level — sub-bullets de buckets subsequentes contaminavam dedup do bucket corrente. Fix adiciona break ao encontrar linha não-tab; regression test `test_emerging_origem_dedup_does_not_leak_across_buckets` cobre re-introdução.

### Notes

- **23 testes pytest formais** em `tests/test_journal_review_apply_structural.py` per ADR-002 § Decisão 6 Adendo (parsing-complexo → pytest): parser, apply A2/B2 (idempotência + fail-soft), payload misto, regression `## Transitions`-only legacy, bug Gap 5 regression.
- **README** atualizado mencionando apply estrutural A2/B2 + correção pré-existente de sub-decisões count em `## Architecture context` (10 → 11 pós-Onda 2 `wiki-compile`).

## 0.10.0 — 2026-06-20

### Added

- **`paths.backlog: forge` declarado** — migração das 6 entries de `BACKLOG.md ## Próximos` para issues abertas sem assignee (#8–#13). Combinação `forge + plans_dir: local` fora da recusa cross-mode do ADR-047 (modo forge é público por construção — ADR-058 § (i) do toolkit). `BACKLOG.md ## Concluídos` preservado como histórico append-only.
- **`/journal-close` Step 3c: probe externo cross-repo de "Próximos passos"** ([PR #14](https://github.com/fppfurtado/meta-bridge/pull/14)). Novo sub-step entre 3b e 3d (Caso degenerado renumerado): identificar pares `(entry, repo)` em rascunho via regex em 3 patterns + `git log --since="48 hours ago"` cross-cwd fail-soft + matching semântico conservador in-skill per ADR-002 § Decisão 3 + remoção silente + nota in-prosa segmentada por repo pré-Step 4 preview. Adendo v0.4.4 em ADR-001 § Sub-decisão 3 documenta 4 critérios ADR-034 + trade-off explícito SSOT in-place (remoção não vai em payload `## Transitions` do CLI). Materializa preventivamente a 7ª instância empírica do memory `feedback_probe_estado_externo_antes_framing` — sai do regime "memória resolve" e entra em "skill resolve mecanicamente". 6 findings do prompt-reviewer + 1 do doc-reviewer absorvidos/cutucados pré-commit (drift cross-ref `matching-on-skill → Decisão 3` reconciliado em 3 sites como side-effect).

### Notes

- **Reconciliação editorial pós-migração forge** — prosa do `CLAUDE.md` (Pragmatic Toolkit) atualizada para refletir a combinação `backlog: forge + plans_dir: local` (anteriormente citava `backlog: canonical + plans_dir: local`). Ancora em ADR-058 § (i) que codifica a exceção à recusa cross-mode do ADR-047 para modo forge.

## 0.9.3 — 2026-06-18

### Fixed

**`mb journal-close`: BUCKET_RE aceita buckets com ponto** — regex `^- #([a-z0-9-]+)` excluía buckets versionados (`pje-2.1`, `pje-2.2`). Fix: charset estendido para `[a-z0-9.-]+`. Descoberto in vivo na sessão `pje-2.1` (append manual via Edit como fallback; TODO capturado no journal e materializado em sessão dedicada).

### Changed

**`/journal-load` Step 5: sumário curto em vez de dump verbatim** ([PR #7](https://github.com/fppfurtado/meta-bridge/pull/7)). Step 5 renomeado para "Reportar sumário"; dump verbatim por data removido — conteúdo já entra em working memory CC quando o Read tool retorna no Step 4; re-emitir verbatim adicionava custo O(tamanho\_journal) tokens de output sem ganho ao objetivo declarado (evidência empírica: journal de ~418 linhas → ~13K tokens de output). Skill emite apenas 1 linha de sumário: `<M> de <N> journals carregados na janela [<data-início>, <data-fim>]` (datas `YYYY-MM-DD`). Adendo (2026-06-18) a ADR-001 Sub-decisão 9 codificando invariante "load ≠ surface; primitiva ≠ echo". 3 findings do prompt-reviewer e 1 finding do doc-reviewer absorvidos/cutucados pré-commit.

## 0.9.2 — 2026-06-18

### Fixed

**Hook `session-start-tip`: path-vs-Repo basename mismatch** ([PR #6](https://github.com/fppfurtado/meta-bridge/pull/6)). Hook silenciava indevidamente 3 repos da constelação onde basename do path divergem do campo `Repo` em REPOS.md: `logseq-notes` (Path `~/Notes/logseq` → basename `logseq`), `dotfiles` (Path `~/.local/share/chezmoi` → basename `chezmoi`), `scripts` (Path `~/Scripts` → basename `Scripts`). Refactor de `_load_owned_active` retornando `dict[str, str]` (match_key → bucket_name) em vez de `set[str]`; novo helper `_derive_basename` encapsula strip 3-pattern (`.strip().strip("\`").strip()`) + `os.path.expanduser` + `os.path.basename`. Cada entry owned/active gera chave canonical (Repo field) SEMPRE e chave derivada (basename do Path expandido) CONDICIONALMENTE quando diverge; `main()` passa a usar `dict.get(basename)`; tip cita o bucket name canonical independente da chave que casou. Bug detectado in vivo em `/run-plan §3.2` cenário 8 cross-cluster sanity (2026-06-16); gatilho N≥1 disparado e endereçado aqui.

### Notes

- Suite pytest expandida pra 19 testes (12 existentes atualizados de set→dict + 7 novos: derivação Path quando diverge, expanduser, Path vazio, casing match, colisão last-write-wins, helper isolado, E2E `main()` via fake git repo). 3ª materialização do critério parsing-complexo → pytest do [ADR-002](docs/decisions/ADR-002-materializacao-cli-mb.md) § Decisão 6 Adendo (2026-06-16): suite hook bridging em v0.8.0 + suite sub-tool wiki-compile em v0.9.1 + expansão hook em v0.9.2.
- Decisões F3/F4/F5/F6 do design-reviewer absorvidas pré-commit no `/triage` (strip pattern 3-strip paralelo ao parser corrente da coluna Repo; collision regression test `test_load_owned_active_collision_last_write_wins` protege contra refactor de ordem de iteração; cenário 6 manual delegado a pytest existente; helper isolado com 4 inputs canonical).
- 6 cenários manuais PASS in vivo (Cenário 1 regression canonical em meta-bridge; Cenários 2-4 path basename matching em logseq-notes/dotfiles/scripts; Cenário 5 no-match silent em `/tmp`; Cenário 6 filtro NEGATIVO subsection em splitrail silenciado independente da chave) + Cenário 7 suite pytest 19/19 verde — 7/7 cenários totais validados pré-merge.

## 0.9.1 — 2026-06-18

### Added

**Suite pytest formal pro sub-tool `skills/wiki-compile/sub-tools/compile.py`** via `tests/test_compile.py` — 13 testes (250 linhas) materializando a pré-condição "eficiência" do gatilho intermediário [ADR-021 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-021-mecanismos-de-revisao-formal-2-tipos.md) § auto-crítica permanente. Fecha pendência registrada em v0.9.0 § Notes (linha 14 do CHANGELOG anterior + entry cross-repo em `meta-system/docs/plans/onda-2-knowledge-layer-piloto.md` § Pendências de validação). Cobre 5 cenários enumerados: section order canonical preservada em `find_insert_position` (3 ramos) + `ensure_section` idempotente + dedup multi-line + idempotência de re-runs + edge case section sem trailing newline + edge case page sem properties block. 3 gaps absorvidos do qa-reviewer pré-commit (E2E `main()` validando ordem canonical no output composto + shape de prefix de `append_to_section` + 3 testes `validate()` fail-fast em input inválido). Pattern isomorfo ao precedente `tests/test_suggest_session_start_tip.py` (v0.8.0; importlib.util + monkeypatch sys.argv; sub-tool verificado sem side-effects no module load pelo design-reviewer pré-execução). Regression do bug histórico `find_insert_position` ignorando seções anteriores existentes (descoberto in vivo durante `/run-plan onda-2-knowledge-layer-piloto` do meta-system, 6ª chamada inseriu `Sources digeridas` ANTES de `Notas curadas` violando ordem canonical) cristalizado explicitamente no shape (c) do Cenário 1 como regression test formal.

### Notes

- Aplicação concreta do critério "parsing-complexo → pytest; mecânico → manual" cristalizado em [ADR-002 § Decisão 6 Adendo (2026-06-16)](docs/decisions/ADR-002-materializacao-cli-mb.md). 2ª materialização da exceção (1ª foi `test_suggest_session_start_tip.py` em v0.8.0).
- Documentação meta atualizada (commit `5b2f818`): dual-entry recíproca Onda 2 do roadmap knowledge layer.

## 0.9.0 — 2026-06-18

### Added

**Skill `/wiki-compile` v0 (knowledge layer Onda 2 — escopo Logseq-local estendido)** via `skills/wiki-compile/SKILL.md` orquestrador heurístico-semântica + `skills/wiki-compile/sub-tools/compile.py` sub-tool determinístico. Materializa Camada 3 (entity pages enriquecidas) do roadmap knowledge layer block-first per [Adendo 2026-06-17 ADR-013 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-adocao-knowledge-layer-destino-arquitetural-constelacao.md). Forma técnica per [ADR-017 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-017-skills-orquestrador-fino-sub-tool-deterministico.md) § decomposição faceta ii: substância heurística (decisão de o que agregar — relevância dos blocos-source) vive na skill; substância determinística (find-or-create section preservando ordem canonical `Notas curadas` → `Sources digeridas` → `Síntese` + literal append + dedup por conteúdo) vive no sub-tool reduzido (sem flags `--trail`/`--force`/`--source` per F4 do reviewer; modo único intra-graph). Skill restringe `--blocks` a paths intra-graph (`~/Notes/logseq/pages/*` + `~/Notes/logseq/journals/*`) — fontes cross-repo exigem captura prévia via `/journal-note` antes (preserva invariante SD2 literal append).

**ADR-001 ganha Sub-decisão 11 — `/wiki-compile` mechanics** (pattern matching SD9 que estendeu pra `/journal-load` em v0.4.0). Substância reduzida a `/wiki-compile` v0 apenas per F7 do reviewer (pattern dual-entry escala com substância shipada, não com declaração pré-fato — `/wiki-lint` + `/wiki-distill` ganham Sub-decisões adicionais quando materializarem em Ondas 3+). Cross-refs ao plano Onda 1 + plano Onda 2 + `logseq-notes` ADR-003 (schema mecânico consumido) + ADR-017 (decomposição) + ADR-008 (critério necessidade arquitetural).

### Notes

- **Bug de ordem canonical no sub-tool descoberto em 1ª invocação real + reparado inline.** `find_insert_position` só procurava seções **posteriores**, ignorando anteriores existentes — quando entity page já tinha `## Notas curadas` e sub-tool foi invocado pra `## Sources digeridas`, caía no fallback "após page-level properties" inserindo Sources digeridas ANTES de Notas curadas, violando ordem canonical. Fix: probe reverse das seções anteriores antes do fallback; regression test pré-commit cobrindo ambos cenários (target sem posteriores e com anteriores existentes preserva ordem canonical).
- **Pytest formal pro sub-tool ausente em v0** — meta-bridge ADR-002 Adendo declara critério "parsing-complexo → pytest; mecânico → manual"; sub-tool tem positioning logic não-trivial (validado empiricamente pelo bug acima — 1 escapou smoke). Captura como Pendência de validação no plano Onda 2 do meta-system (`docs/plans/onda-2-knowledge-layer-piloto.md`) — entry cross-repo pra meta-bridge BACKLOG materializa quando operador trabalhar em sessão dedicada cwd `~/Projects/meta-bridge`.
- Skill `/wiki-compile` só vira invocável como slash command após bump + push + tag publicada + `/plugin marketplace update` + `/reload-plugins` + restart CC (per memory `project_cc_plugin_version_pinned_cache` — cache CC é version-pinned). Operação manual via `python3 sub-tools/compile.py` continua disponível.
- **Piloto materializado entidade `knowledge-layer` em `logseq-notes`** (commit `665cc00`): `pages/knowledge-layer.md` enriquecida com 5 block-refs intra-graph cobrindo os 5 claims load-bearing canonical da knowledge layer + Sources digeridas com Andy Matuschak Evergreen Notes ingerida via WebFetch + Síntese 3 parágrafos. Audit empírico claim-ausência (per F5 do reviewer) = 0/5 ausentes → shipped OK. Dogfood do princípio fundamental 4 (auto-crítica permanente) per ADR-021 do meta-system: meta-system doctrine como domínio piloto Onda 2 = auto-referencial baixo-risco.

## 0.8.0 — 2026-06-16

### Added

**2ª trajetória de hook bridging meta-bridge↔CC** via `hooks/suggest_session_start_tip.py`. Hook standalone Python isomorfo a `suggest_journal_close.py` (Sub-decisão 6 v0.1.5), com binding `SessionStart` em `hooks/hooks.json` paralelo ao `Stop` existente. Gate único cwd-matching: resolve cwd via `git rev-parse --show-toplevel | xargs basename`, match contra repos `owned/active` de `~/Projects/meta-system/REPOS.md` (parser markdown aplicando filtro NEGATIVO — exclui overview `## Clusters (N)` e subsection `### Runtime auxiliar consumido externo`). Match → emit JSON `{"systemMessage": "💡 /journal-load --days 2 --bucket <repo> ..."}` em stdout; no-match / falha → exit 0 silente. Decisão registrada em [ADR-001 § Sub-decisão 6 Adendo v0.2.0](docs/decisions/ADR-001-skills-de-bridge.md) — registro factual sem postular pattern de N trajetórias per philosophy YAGNI/Ockham (3ª materialização aguarda confirmação).

**Suite pytest parcial em `tests/test_suggest_session_start_tip.py`** (12 testes — 6 unit em `_load_owned_active` cobrindo filtro NEGATIVO + Status filter + cross-cluster; 6 e2e in-process em `main()` via monkeypatch de `hook.REPOS_MD` + `sys.stdin`). `pyproject.toml` ganha `[project.optional-dependencies] dev = ["pytest>=7"]`. Materialização inaugural do critério "parsing-complexo → pytest" cristalizado em ADR-002 § Decisão 6 Adendo.

### Changed

- **ADR-002 § Decisão 6** ganha Adendo refinando "sem suite de testes formal no MVP" → "suite parcial sob critério parsing-complexo". Decisão central preservada para subcomandos/hooks mecânicos simples (validação manual cobre golden path); nova exceção condicional para parsing-complexo (markdown estruturado, JSON schemas externos). Gatilho 3 reinterpretado: agora dispara migração retroativa total cross-subcomandos quando incidente real emergir.
- **CLAUDE.md** § "What this repository is" passa a mencionar "2 hooks bridging" (Stop sugerindo `/journal-close`; SessionStart sugerindo `/journal-load`) + critério parsing-complexo. § "Plugin layout" lista `hooks/suggest_session_start_tip.py` + `tests/test_suggest_session_start_tip.py` + `hooks/hooks.json` ganha "Stop + SessionStart bindings".
- **README.md** Component table ganha row `suggest_session_start_tip | Hook (SessionStart)` simétrica ao `suggest_journal_close`. § Runtime dependencies desambigua "Hook only" → "Stop hook only" + novo bullet "SessionStart hook only" listando dep de REPOS.md `owned/active`.
- **`plugin.json` + `marketplace.json` descriptions** mencionam ambas trajetórias de hook bridging (Stop sugerindo `/journal-close` + SessionStart sugerindo `/journal-load`).

### Notes

- Hook `suggest_journal_close.py` permanece intacto — Adendo v0.2.0 é refinamento aditivo (2ª trajetória paralela), sem mutação do hook existente.
- Pendência em BACKLOG ## Próximos (gatilho ≥1 report manual): `_load_owned_active` não cobre repos com `Path` basename ≠ `Repo` field em REPOS.md — `logseq-notes` (`~/Notes/logseq` → basename `logseq`), `dotfiles` (`~/.local/share/chezmoi` → basename `chezmoi`), `scripts` (`~/Scripts` → basename `Scripts`) ficam SILENT indevidamente.
- Pendências de validação operacional pós-release (NOTES.md 2026-06-16): Cenário 5 do `## Verificação manual` (mv defensivo `~/Projects/meta-system/REPOS.md{,.bak}; ...`) e Cenário 10 (plugin reinstall + nova sessão CC pra observar SessionStart hook real disparando in vivo).
- Housekeeping BACKLOG: 3 planos locais (`journal-review-refactor`, `materializar-cli-mb`, `calibracao-thresholds-journal-review`) marcados como Concluído via Edit cirúrgico `## Status` no commit `5ec1614`.

## 0.7.0 — 2026-06-16

### Added

**Materialização CLI `mb` substituindo Tier 1 MCP candidato implícito.** Pacote Python `meta_bridge` (Click) com entry-point `mb` instalável via `pipx install -e .`. 4 subcomandos cobrem o write substantivo das 4 skills:
- `mb journal-note --domain <name> "<content>"` — find-or-create bucket + append child task. Sanitização kebab-case + NFD-strip de acentos PT-BR.
- `mb journal-close` (stdin: `## Append` + `## Transitions`) — write engine determinístico. Skill compõe payload com transições in-place já decididas (matching semântico permanece na skill per F3 design-reviewer).
- `mb journal-review [--days N | --from D1 --to D2]` (scan) ou `mb journal-review --apply` (stdin transitions) — scan mecânico emite markdown estruturado consumido pela skill; skill faz 4 heurísticas semânticas + retém findings em conversation memory + re-invoca `--apply` com transições concretas (per F2 design-reviewer).
- `mb init-project [--repo-path <path>] [--basename <name>] [--cluster <name>] [--subcluster <name>]` — lookups mrconfig + REPOS.md; skill orquestra `AskUserQuestion` enum 9-cluster apenas no fallback (per F1 design-reviewer).

Decisão registrada em [ADR-002](docs/decisions/ADR-002-materializacao-cli-mb.md) (9 decisões cobrindo CLI, cascateamento, divisão CLI/skill, manifests PT-BR preservados, sem suite de testes formal). Adendos cirúrgicos em ADR-001 Sub-decisões 1, 3, 4, 10 registram cascateamento per ADR-034 critério.

**`/journal-review` ganha 4 flags semânticos pra override de thresholds detectivos**: `--bucket-min-journals N` (K do 2c bucket-underused), `--bucket-min-tasks N` (M do 2c), `--zombie-days N` (T do 2b task-zombie), `--emerging-min-mentions N` (N do 2d bucket-emerging). Nomes semânticos vs matemáticos auto-documentam qual heurística está sendo overrideada na invocação.

### Changed

- **4 SKILL.md viram thin orchestrators** (`/journal-note`, `/journal-close`, `/journal-review`, `/init-logseq-project`) — preservam frontmatter + scope guards + substância heurístico-semântica (matching, princípios editoriais, 4 heurísticas, cluster prompt); delegam writes ao CLI. `/journal-load` permanece markdown-only (sem assimetria CLI > MD per critério target-aware).
- **CLAUDE.md § "What this repository is"** reescrito refletindo substância em `meta_bridge` CLI + skills como thin orchestrators.
- **CLAUDE.md § "Plugin layout"** ganha entries pra `pyproject.toml`, `meta_bridge/` package, ADR-002.
- **`plugin.json` + `marketplace.json` descriptions** convergem pra PT-BR (alinhado a SKILL.md frontmatter; contradição não-bloqueante com `philosophy.md` § Convenção de idioma reconhecida).
- **README.md** ganha seção `## CLI mb` + tabela de skills realign refletindo divisão thin orchestrator / CLI.
- **`/journal-review` thresholds recalibrados contra densidade pessoal-graph**: T (zombie-days) `14 → 21`; N (emerging-min-mentions) `3 → 4`. Empirical motivation: dogfood 2026-06-13 mostrou ruído com defaults antigos. K=M=2 do `bucket-underused` (2c) preservado após validação contra graph real — a conjunção `<K AND <M` *afrouxa* com K/M maiores (descoberta editorial cristalizada em ADR-001 Sub-decisão 10 § Adendo v0.3.2).
- **`/journal-close` SKILL.md v0.4.3 ganha exemplos inline pra ancorar composição editorial**: Step 3.0 novo (checklist editorial pré-composição com 6 antipadrões v0.4.1 como gatilhos de revisão); Step 3a-bis (exemplo sessão rica canonical — bucket `#meta-system` da `generalizacao-mecanizacao`); Step 3a-ter (exemplo runbook simples — degradação elegante DONE-only flat). Dogfood revelou que princípios apenas em referência cruzada não ancoram composição do agente. Pattern reusable cross-skill.
- **ADR-001 Sub-decisão 10 prose**: bullets descritivos de H1/H2 incluem DOING (estavam só TODO/WAITING — drift textual; SKILL.md já consistente em H1/H2/Step 7 desde v0.3.0).

### Notes

- Sem suite de testes formal — validação manual por subcomando contra graph Logseq real (golden path coberto durante materialização). Gatilho de revisão: incidente reportado pelo operador OU finding `/journal-review` apontando drift correlacionado a invocação CLI.
- Hook `hooks/suggest_journal_close.py` permanece intacto (lógica independente; sem dependência circular com CLI).
- Faceta cross-repo pendente (out-of-scope): atualizar snapshot `TIER_SNAPSHOT_2026_06_11` em `meta-portability-mcp/.../tools.py` — coordenada via plano runbook em `meta-system`.
- BACKLOG editorial cleanup: session-audit signal queue aplicado pós-merge worktree (housekeeping `## Status` em planos locais + gatilho condicional pra revisitar K/M do 2c); cross-ref redundante removido na entry de scan ADR-011; calibração K/M/T/N marcada como concluída.

## 0.6.1 — 2026-06-13

### Notes

**Bootstrap journal fix das skills write.** Drift detectado em 2026-06-13 (Cenário 9 do `## Verificação manual` do refactor `/journal-review`): bootstrap de `/journal-note` + `/journal-close` + `/journal-review` copiava `~/Notes/logseq/pages/daily-journal.md` literal — incluindo property `type:: #template` + wrapper bullets — sem skip nem dedent. Resultado: 3 journals criados pelas skills (`2026_06_10.md`, `2026_06_13.md`, `2026_06_15.md`) ficaram com `type:: #template` literal, indexados pelo Logseq desktop como templates ao invés de journals canonical.

Fix mecânico paralelo a Sub-decisão 4 § Adendo 2026-05-28 (que estabeleceu o pattern pra `/init-logseq-project`): spec das 3 SKILL.md atualizada pra **skipar linhas wrapper** + **dedent 1 tab fixo** no body remanescente. ADR-001 ganha 3 Adendos (Sub-decisão 1 § Adendo v0.2.2 com contexto integral; Sub-decisão 3 § Adendo v0.4.2 e Sub-decisão 10 § Adendo v0.3.1 com cross-ref). Refinamento mecânico per ADR-034 (decisão central intacta — skill ainda bootstrap journal via template; muda como template é consumido). Cleanup retroativo dos 3 journals aplicado em `~/Notes/logseq/journals/` (graph não é git-tracked).

**BACKLOG.md editorial curation** via `/curate-backlog` (5 refinos textuais H2 pós-v0.6.0 — `(a ser criado)` removido das cross-refs Sub-decisão 10; rename `/weekly-review` → `/journal-review` cross-ref histórica do mechanical-skills-scan; sub-comando `mb weekly-review` → `mb journal-review` na entry Tier 1 CLI).

## 0.6.0 — 2026-06-13

### Added

**`/journal-review` v0.3.0 — sucessor de `/weekly-review` v0.2.0; detective-first com heurísticas estruturais sobre janela configurável.** Refactor profundo demandado em sessão CC `refinamento-journal-close` (2026-06-12): operador relatou nunca ter usado `/weekly-review` (GTD wizard linear, janela 7d hardcoded); demandou knowledge garden curation com janela ampla + heurísticas detectivas + operações estruturais de bucket emergindo do contexto revisado. Decidido via `/triage` + design-reviewer (7 findings absorvidos + 1 cutucada-resolvida); refactor materializado via `/run-plan` em worktree isolada com 4 blocos + 3 blocos extras. PR #1 do repo (primeira PR).

Mecânica nova (per ADR-001 Sub-decisão 10):

- **Janela configurável**: `--days N` default 30 (range `[hoje-N, hoje]` inclusivo — paralelo a `/journal-load` Sub-decisão 9); `--from <date> --to <date>` opcional pra range arbitrário (mensal, trimestral). Substitui hardcode 7d de Sub-decisão 5.
- **4 heurísticas MVP** com findings de evidência inline: `task-closure-by-context` (apply: TODO/DOING/WAITING X com match contra DONE Y ou narrativa posterior → fecha in-place); `task-zombie` (apply: marker > 14 dias sem progresso → archive/cancel); `bucket-underused` (report-only: bucket em < 2 journals ou < 2 tasks → sugere archive/fund); `bucket-emerging` (report-only: conceito repetido ≥ 3× sem bucket → sugere criar bucket).
- **Preview-first**: `AskUserQuestion` única (Aplicar tudo / Cherry-pick via Other / Cancelar).
- **Wizard residual opt-in** via `--interactive` (mesma mecânica de Sub-decisão 5 — keep/next_step/archive/defer).
- **Apply task-level no MVP**: marker change in-place; mass modify cross-files (heurísticas 3-4) fica como apply manual. Apply estrutural automático com snapshot defensivo reabre em v0.4.0 sob gatilho N≥2 reports.
- **`--write-summary` opt-in**: bloco no journal de hoje. Default silente — findings deixam trace SSOT in-place.

ADR-001 ganha Sub-decisão 10 (decisão central reformulada per critério ADR-034 do toolkit — Adendo não cabe; rename de skill quebra contract de `name:`); Sub-decisão 5 intacta com cross-ref blockquote no topo apontando 10 como sucessor (histórico v0.1/v0.2 preservado).

### Changed

- **Rename `skills/weekly-review/` → `skills/journal-review/`** via `git mv` preservando history.
- **`README.md` tabela `## What's inside`**: entry de `/journal-load` adicionada (drift retroativo v0.4.0 — skill existia mas não estava na tabela); entry de `/weekly-review` substituída por `/journal-review` com descrição detective-first; "8 sub-decisions" → "10 sub-decisions".
- **`CLAUDE.md`**: inventário "5 skills" atualiza `/weekly-review` → `/journal-review`; "9 sub-decisions" → "10 sub-decisions"; bloco config `plans_dir: null` → `local` (modo local per ADR-047 do toolkit; combinação `backlog: canonical + plans_dir: local` suportada).
- **`plugin.json` + `marketplace.json` descriptions**: rename + descrição rica com 4 heurísticas + opt-in GTD wizard + cross-ref a `/weekly-review` sucessor.

### Notes

- Plano do refactor em modo local (`.claude/local/plans/journal-review-refactor.md`, gitignored). `.worktreeinclude` criado listando `.claude/local/` pra visibilidade do plano em worktrees do `/run-plan`.
- `BACKLOG.md ## Próximos` ganha 6 entries adiadas com gatilhos: 3 heurísticas v2 (`bucket-co-occurrence`, `bucket-rename-implicit`, `bucket-naming-drift`), apply estrutural automático heurísticas 3-4, drift Sub-decisão 10 ADR DOING ausente em H1/H2/Step 7 (SKILL.md já corrigiu), calibração empírica defaults K/M/T/N (dogfood close revelou ruído pra dataset pessoal).
- 15 findings absorvidos pré-commit total (7 design-reviewer no /triage + 4 doc-reviewer Bloco 1 ADR + 5 code-reviewer Bloco 2 SKILL + 1 doc-reviewer Bloco 4 JSONs + 1 doc-reviewer bloco extra README).
- 2 capturas backlog materializadas via `/run-plan §3.5` (drift ADR + calibração thresholds); 1 finding F5 resolvido por modo local em vez de Adendo doutrinal.
- Primeira PR do repo (#1) — cleanup pós-merge cobriu worktree + branch local + branch remota.

## 0.5.2 — 2026-06-12

### Notes

- registra v0.5.1 em ## Concluídos (refactor editorial /journal-close v0.4.1)

## 0.5.1 — 2026-06-12

### Changed

**`/journal-close` v0.4.1 — refinamento editorial dos princípios de síntese.** Diagnóstico empírico pós-v0.4.0: comparação entre bucket `#meta-system` em `~/Notes/logseq/journals/2026_06_11.md` (síntese manual referência) e fechamentos subsequentes produzidos pela skill revelou 3 antipadrões — enumeração de commits 1:1 como DONE separados, "Mudanças finas" capturando detalhe técnico-operacional (version pins de cache, paths absolutos, byte counts), seções operacionais cronológicas como bullets editoriais ("Pre-trabalho que estruturou", "Validações por carregamento manual").

SKILL.md ganha 3 refinamentos editoriais (sem mudança de fluxo, Steps numerados intactos):

- **§3a Granularidade e profundidade**: DONE segue conceito não commit (top-level = movimento conceitual; commits viram sub-bullets quando carregam contexto). Profundidade livre com filtro qualitativo do "próximo nível" (substância vs enumeração). Brevidade vence completude mesmo em sessão rica.
- **§2b Filtros de seleção em "Material editorial"**: insight/pivot 1-2 por sessão; "Mudanças finas" filtra por "isto vai informar futuras decisões?" (pattern semântico passa; detalhe técnico-operacional não); próximos passos só os enunciados pelo operador.
- **3 antipadrões em "O que NÃO fazer"**: commits enumerados como DONEs separados, detalhe técnico-operacional em "Mudanças finas", seções operacionais cronológicas.

ADR-001 Sub-decisão 3 ganha § Adendo v0.4.1 (refinamento editorial per ADR-034: decisão central intacta; muda **princípios editoriais que governam o output**, não mecânica de coleta ou write).

### Notes

- Drift cleanup pós-v0.5.0: `CLAUDE.md` realign (4→5 skills, 8→9 sub-decisões, templates archived flag) + `BACKLOG.md` entries `## Próximos → ## Concluídos` para v0.3.0 + v0.5.0.

## 0.5.0 — 2026-06-12

### Added

**`/journal-close` v0.4.0 — reconciliação prévia com journal pré-existente.** Antes de compor síntese, skill lê buckets já gravados em journals na janela retroativa configurável via flag `--days N` (default 0 = só hoje) e reconcilia transições: TODO/WAITING anteriores fechados pela sessão corrente recebem marker change in-place no journal source (paralelo a `/weekly-review archive`). SSOT in-place per ADR-002 Sub-decisão 4 do logseq-notes preservado — sem annotation extra sob marker original, sem "closure cross-ref bullet" no novo bucket. Vale mesmo-repo e cross-repo (todos os buckets na janela). Matching via judgment semântico do agente (commit/plan/[[]] cross-refs servem como hint quando matching textual ambíguo); critério conservador — quando incerto, não propor transição.

Mudanças mecânicas: Argumento novo (`--days N`); Step 2 split (2a parse + 2b session context); Step 2.5 novo (coleta backlog reconciliável via regex `^\t- (TODO|DOING|WAITING) ` análoga a `/weekly-review`); Step 3 split (3a rascunho v0.3.0 intacto + 3b fase reconciliação + 3c degeneração + 3d/e exemplos); Step 4 estendido (apresenta rascunho + lista de transições propostas); Step 5 split (5a aplica transições in-place + 5b find-or-create v0.3.0 intacto + 5c caso só-transições); Step 6 reporta transições aplicadas + skipped. 5 novos itens em "## O que NÃO fazer" travando decisões doutrinais.

ADR-001 Sub-decisão 3 ganha § Adendo v0.4.0 (refinamento mecânico per ADR-034: decisão central intacta — skill ainda sintetiza sessão CC no journal de hoje; muda **fluxo de coleta** + **scope de write**).

### Notes

- BACKLOG.md: linha nova em `## Próximos` documentando o refactor + bifurcações decididas via `/triage` 2026-06-12 (temporal scope `--days N`; write modify-in-place sem annotation).

## 0.4.0 — 2026-06-12

### Added

**`/journal-load` — read-only carregamento de journal Logseq na sessão CC.** Nova skill que fecha a simetria read-write do bridge (par com `/journal-note` append + `/journal-close` write final). Default = journal de hoje, integral. Flags opcionais: `--days N` estende janela retroativa (N+1 dias inclusive); `--bucket #<hashtag>` restringe a um bucket específico. Surface conteúdo agrupado por data em ordem cronológica reversa. Read-only — primeira skill do plugin isenta do gate `pgrep -xi logseq` (race window não materializa em leitura concorrente).

ADR-001 ganha Sub-decisão 9 (mechanics completa) + Adendo (2026-06-12) a Sub-decisão 7 (critério canonical: gate aplica somente onde há side-effect; read-only é exceção doutrinária). Tabela de Sub-decisão 8 acrescenta linha para `/journal-load`. `marketplace.json` description acrescenta menção da nova skill.

### Notes

- `BACKLOG.md`: cross-ref `/journal-note` + `/init-logseq-project` POSITIVO no mechanical-skills-scan do meta-system (commit `1b33b86`).

## 0.3.0 — 2026-06-11

### Added

**`/journal-close` v0.3.0 — escopo expandido + template humano-amigável.** Refactor demandado em sessão CC `generalizacao-mecanizacao` (no `meta-system`, 2026-06-11): operador produziu síntese manual em formato divergente do v0.2.0 e identificou explicitamente 2 eixos ("template feito mais pra máquinas/sistemas que pra humanos — sensação de abrir o git log"). Decidida opção (a) via `/triage` (refactor `/journal-close` existente; execução independente do item BACKLOG sobre materialização CLI `mb`). Mudanças:

- **Escopo expandido de DONE-only para DONE + TODO/WAITING + narrativa editorial**: incorpora frame de sessão, insights/pivots conceituais, mudanças finas não-codificadas (memory refinada, padrões reconhecidos), próximos passos com markers GTD nativos, e direção emergente. Cada seção opcional — sessão puramente mecânica degrada elegantemente pra padrão DONE-only flat estilo runbook v0.2.0.
- **Template humano-amigável substitui git-log-like flat**: linguagem 2ª pessoa quando faz sentido editorial, bullets aninhados ≥3 níveis quando útil, narrativa fluida, GTD markers Logseq nativos como block markers.
- **Conversation context inspection estendida**: agente runtime inspeciona transcript pra extrair material editorial além de commits (insights, mudanças finas, direção emergente, cross-refs). Julgamento do agente sobre o que vale registrar — não mecânico.
- **Sub-bullets free-form como caso default** (contract ADR-006 § Decisão § 3 preservado, leitura nuanceada): a convenção é que sub-bullets são prose non-parsed pelos consumers, e v0.3.0 obedece (composição interna da skill, não parsing). `commit:<hash>` e `plan:<slug>` continuam suportados como metadata opcional sob DONE tasks, não obrigatórios.
- **Idempotência intra-skill parcial pós-retrofit**: dedup `commit:<hash>` mantido pra children com metadata; children narrativos puros sem dedup mecânica. Operador rodando 2× pode duplicar narrativa — mitigação: `Edita via Other` no 2º run. Trade-off aceito.
- **Princípios editoriais**: brevidade > completude; linguagem 2ª pessoa quando faz sentido; opcionalidade per seção; degradação elegante pra runbook simples quando sessão é magra.

ADR-001 Sub-decisão 3 ganha § Adendo v0.3.0 documentando refinamentos v0.2.0 → v0.3.0 + Gatilho de revisão 13 (cascateamento futuro com materialização CLI `mb` per item 2 do BACKLOG).

**Stop hook `suggest_journal_close.py` permanece intacto** — lógica do hook agnóstica ao formato do bloco que `/journal-close` produz. Mudança de output (v0.2.0 → v0.3.0) é transparente.

### Notes

- `CLAUDE.md` bloco `## Pragmatic Toolkit` realinhado ao estado real do repo via `/init-config`: explicita `paths.plans_dir: null` (alinha YAML à prosa "Sem plans_dir"); remove `decisions_dir: docs/decisions` redundante (canonical default); reconhece `backlog` como canonical implícito (`BACKLOG.md` criado em commit `935e0d8` e operacionalmente usado). Prosa adjacente atualizada removendo declaração stale "Sem `backlog`".
- `BACKLOG.md` linha do item 1 refinada via `/triage`: lock decisional opção (a) + execução independente do item 2; aponta pra artefatos esperados (rewrite SKILL.md + Adendo v0.3.0 ADR-001).

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
