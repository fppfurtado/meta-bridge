# Changelog

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
