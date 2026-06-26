# ADR-001: Skills de Bridge — `/journal-note`, `/journal-close`, `/journal-load`, `/journal-review`, `/init-logseq-project` + hook `suggest_journal_close`

**Data:** 2026-05-28
**Status:** Proposto

## Origem

- **Decisão base (meta-system, cross-cutting):** [ADR-005](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) — declara Camada 3 (Bridge) e nomeia este plugin como owner pós-pivot da Sessão 5 (2026-05-28). ADR-005 carrega o quê + por quê arquitetural; este ADR-001 carrega o como concreto.
- **Decisão base (meta-system, cross-cutting):** [ADR-004](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-004-logseq-cognitive-hub.md) — invariantes da Camada 4 (Cognitive) consumidos como contracts. Skills assumem invariantes sem probe defensivo.
- **Direção de produto:** intent declarada pelo operador do meta-sistema em ADR-005 — capture friction reduzido a 1 comando + continuidade cross-session via journal.
- **Investigação:** templates da Onda 3 (`session-close.md`, `weekly-review.md`, `daily-journal.md`, `Project Template.md`) criados como contracts no graph Logseq. Bloco 1 da Onda 4 (commit `364465e` no `logseq-notes`) alinhou templates aos contracts finais. Probe Claude Code (sessão 2026-05-28) confirmou que Stop event é o mecanismo apropriado pra hook pós-`/run-plan` do `pragmatic-dev-toolkit`; matcher por content de tool result não existe; Stop hook recebe `transcript_path` via stdin e pode grep marker canonical do output (marker `[PRAGMATIC: plan-done]` emitido pelo `/run-plan` per commit `b8989c2` no toolkit, contract público pra plugin authors).
- **Histórico de execução:** 7 commits originalmente landed em `pragmatic-dev-toolkit` master local (Sessão 5 da Onda 4 do meta-sistema) foram rollback-ados ao detectar scope mismatch (plugin público vs personal-config). Pivot pra este plugin separado preservou substância das decisões mecânicas; ADR-042 do toolkit (transient) virou ADR-001 aqui (permanente).

## Contexto

ADR-005 cross-cutting fixou shape macro (4 skills + 1 hook), invariantes shared (pgrep gate, contracts ADR-004), fronteiras (Bridge unidirecional). Mas execução das skills exige mecânica concreta:

- **`/journal-note` write**: qual path do journal? Qual formato de bloco? Como o repo é inferido?
- **`/journal-close` synthesis**: como skill agrega session context (commits, plan slug, edits)? Como compõe bloco seguindo `session-close.md` template?
- **`/init-logseq-project` idempotência**: quais props são "mecânicas" (sobrescrevíveis pela skill) vs "humanas" (preservadas)? Como skill identifica cluster sem entry em `.mrconfig`?
- **`/weekly-review` parsing**: como skill agrega blocos sob `## Inbox`/`## Doing`/`## Waiting` cross-journals sem rodar Logseq (desktop fechado por gate)?
- **Hook pós-`/run-plan` (do toolkit)**: qual event do Claude Code? Probe confirmou Stop event + marker; mecânica reusa marker canonical emitido pelo toolkit (contract público).
- **Template insertion**: ref via `((session-close))` (Logseq block-ref) ou literal append? Probe confirmou que block-ref só resolve com desktop aberto; skills com gate fechado precisam literal.
- **`pgrep` semantics**: probe exato. Aplicação por skill.
- **AskUserQuestion cardinality**: max 4 perguntas por chamada (per [pragmatic-dev-toolkit/CLAUDE.md](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/CLAUDE.md) → AskUserQuestion mechanics).

Sem este ADR, mecânica vira convention emergente per-skill (cada uma resolve à sua maneira) — quebra invariante de "contracts shared" declarado em ADR-005.

## Decisão

**Sub-decisões mecânicas** (catálogo incremental — 18 na data corrente) que materializam as skills + hooks da Bridge.

### Sub-decisão 1 — `/journal-note` mechanics

Skill `skills/journal-note/SKILL.md`. Frontmatter:
- `name: journal-note`
- `description: Append timestampado no journal Logseq de hoje com [[<repo-basename>]] ref auto-detectado`
- `disable-model-invocation: false`

Passos:
1. Gate `pgrep -xi logseq` (ver Sub-decisão 7). Falha fechada com mensagem clara.
2. Recusa fora de git repo (`git rev-parse --show-toplevel` retorna não-zero).
3. Resolve metadata:
   - **Repo basename**: `basename $(git rev-parse --show-toplevel)`.
   - **Journal path**: `~/Notes/logseq/journals/$(date +%Y_%m_%d).md` (Logseq canonical com separator `_`, **local TZ** — ver Adendo v0.2.1 abaixo).
   - **Timestamp UTC**: `date -u +%Y-%m-%dT%H:%M:%SZ`.
4. Conteúdo final vazio → recusa silenciosa, exit clean.
5. Append do bloco no formato:
   ```
   - <timestamp UTC> | [[<repo-basename>]]
   	- <conteúdo literal>
   ```
6. Journal path não existe → ler `~/Notes/logseq/pages/daily-journal.md` como template body, copiar conteúdo (após linha `- template:: daily-journal` e `  template-including-parent:: false`) para o journal path; append do bloco no fim. Template ausente → criar arquivo vazio + append do bloco; reportar warning `template daily-journal.md ausente; journal criado sem estrutura — Logseq apply de template manual ao abrir`.

Sem flag `--local`, sem dual mode — `/note` do `pragmatic-dev-toolkit` cobre o caso NOTES.md per ADR-032 do toolkit (não-duplicado aqui).

Sem argumento → recusa silenciosa com mensagem `/journal-note exige conteúdo; use /journal-note "<nota>"`.

#### Adendo v0.2.0 (2026-05-28) — retrofit pra hashtag-bucket + GTD nativo

Materializa [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) (3 invariantes: top-level `- #<domínio>` + markers nativos + sub-bullets free-form) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisões 1, 3, 4, 5. Refinamento mecânico (decisão central intacta — skill ainda escreve no journal de hoje; muda só o **formato** do write).

Refinamentos do diff v0.1.x → v0.2.0 (lista descritiva, não mapeamento 1:1 com Steps da v0.2.0):

- **Step "gate git repo" removido**: cwd fora de git agora cai em prompt enum — domínios não-repo (`#thought`, `#draft`, `#idea`, ad-hoc via Other) são cidadões legítimos per ADR-006 § Decisão § 1.
- **Derivação de domínio**: probe ordenado novo (cwd git repo → basename; senão → AskUserQuestion enum com sanitização kebab-case lowercase no caminho Other per [`logseq-notes` ADR-002](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisão 3 — mitigação direta do risco de hashtag proliferation citado em ADR-006 § Limitações).
- **Find-or-create bucket top-level `- #<domínio>`**: substitui o append flat de v0.1.x. Probe regex `^- #<domínio>($| )` restringe a top-level. Idempotente: mesma tag no mesmo dia reusa o bucket existente.
- **Format do child**: input com marker prefix uppercase (`TODO `/`DOING `/`WAITING `/`DONE `/`CANCELLED `) preserva como marker do bloco Logseq nativo per [`logseq-notes` ADR-002](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisão 4; senão child plain.
- **Sub-bullets mecânicos**: scan limitado por 2 patterns (`commit:<hash>`, `plan:<slug>`) extraídos como nested sub-bullets sem destruir inline reference no body. `[[<page>]]` cross-refs ficam inline. Resto do input é prosa livre per ADR-006 § Decisão § 3.
- **Timestamp UTC removido do bloco**: v0.1.x prepended timestamp ao bloco top-level. Pós-retrofit, top-level é tag (bucket); timestamp por capture vira ruído e duplica metadata do filename do journal.
- **Template ausente warning**: comportamento mantido (bootstrap journal vazio se template ausente). Sem mudança.

Pré-condições v0.2.0 herdadas intactas: `pgrep -xi logseq` gate (Sub-decisão 7 + Adendo v0.1.2), failure-closed; conteúdo vazio → recusa silenciosa.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (skill `/journal-note` escreve no journal de hoje); sem categoria nova (refina mecanismo de write); sem restrição externa nova; caráter explicativo + refinamento.

#### Adendo v0.2.1 (2026-06-10) — Migration UTC → local TZ pra convergência cross-plugin

Filename do journal (`$(date -u +%Y_%m_%d)`) migrado pra **local TZ** (`$(date +%Y_%m_%d)`). Refina mecanismo de write — decisão central intacta (skill ainda escreve no journal de hoje).

**Origem:** `tjpa-tools` v0.2.0 (2026-06-02) bootstrapped `tjpa_tools/report/logseq_write.py` com `date.today()` (local TZ) — escolha deliberada do operador via `/run-plan tjpa-report-logseq-page` per intuição diária BRT. [`tjpa-tools ADR-002`](https://github.com/fppfurtado/tjpa-tools/blob/main/docs/decisions/ADR-002-output-page-logseq.md) § Contexto antecipou explicitamente o gatilho: *"gatilho de Adendo a ADR-001 do `meta-bridge` se padrão de divergência se consolidar (captura em backlog do meta-system)"*. Gatilho disparou em 2026-06-10 (sessão CC `tjpa-tools-backlog`): empiricamente verificado que os 2 plugins produzem filenames diferentes na janela 21h-23h59 BRT (bullets caem em journals distintos).

**Decisão (cross-plugin convergência):** **local TZ vence**. 4 razões objetivas (per plano canonical [`journals-tz-cross-plugin-convergencia.md`](https://github.com/fppfurtado/meta-system/blob/main/docs/plans/journals-tz-cross-plugin-convergencia.md) deste repo `meta-system`):
1. **Intuição diária do operador BRT** — journal de 21h é "hoje" no modelo mental do operador.
2. **Decisão mais recente prevalece** — escolha tjpa-tools (2026-06-02) é mais recente que escolha original meta-bridge UTC (v0.1.x).
3. **Cross-máquina é teórico hoje** — operador single-machine; ganho UTC "estável cross-máquina" sem custo concreto.
4. **Material match com convention Logseq desktop** — Logseq desktop usa local TZ pra `today` template; alinhamento UX.

**Mecânica aplicada:** v0.2.1 troca `date -u +<format>` → `date +<format>` em 6 ocorrências nas 3 SKILL.md (`journal-note/SKILL.md:9+54`, `journal-close/SKILL.md:39`, `weekly-review/SKILL.md:76+111+122`). Linhas mecânicas do ADR-001 (45, 109, 212-213) atualizadas pra refletir estado corrente. Linhas 46/50/70 NÃO tocadas — referem-se a "Timestamp UTC removido do bloco" em v0.2.0 (narrativa histórica sobre Timestamp do bloco, não sobre filename do journal).

**Cross-refs:**
- [`meta-system` ADR-004](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-004-logseq-cognitive-hub.md) — Adendo cristalizando "filename de journal usa local TZ" como invariante cross-plugin canonical da Camada 4.
- [`tjpa-tools` ADR-002](https://github.com/fppfurtado/tjpa-tools/blob/main/docs/decisions/ADR-002-output-page-logseq.md) — Adendo recíproco confirmando convergência cross-plugin.

**Convention "operador é single-machine BRT" assumida.** Multi-máquina cross-fuso no futuro → gatilho de revisão emerge (conflitos visíveis em `~/Notes/logseq/journals/` via drive-sync) e nova `/triage` decide.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta; sem categoria nova; sem restrição externa nova; refinamento mecânico justificado por convergência cross-plugin documentada.

#### Adendo v0.2.2 (2026-06-13) — bootstrap journal: skip wrapper + dedent 1 tab

Materializa fix mecânico de bootstrap detectado em 2026-06-13 (sessão `journal-review-refactor + release v0.6.0`, Cenário 9 do `## Verificação manual` do refactor `/journal-review`). Bootstrap journal das skills `/journal-note` + `/journal-close` + `/journal-review` (`/weekly-review` v0.2.0 também afetada historicamente) copiava `~/Notes/logseq/pages/daily-journal.md` literal — incluindo property `type:: #template` + wrapper bullets (`- template:: daily-journal` + `template-including-parent:: false`) que NÃO deveriam estar no journal real. Resultado: 3 journals criados pelas skills (`2026_06_10.md`, `2026_06_13.md`, `2026_06_15.md`) ficaram com property `type:: #template` literal — Logseq desktop os indexa como template, não como journal canonical.

Fix em v0.2.2 (refinamento mecânico — decisão central intacta; skill ainda bootstrap journal via template):

- Step 3 do SKILL.md atualizado: spec antiga "copiar conteúdo (após linha de `template-including-parent:: false`)" → spec nova **skipar linhas wrapper** (`type:: #template`, `- template:: daily-journal`, `template-including-parent:: false`) + **dedent 1 tab fixo** no body remanescente. Paralelo explícito a Sub-decisão 4 § Adendo 2026-05-28 que estabeleceu o pattern análogo pra `/init-logseq-project` consumindo `Project Template.md`.
- **Resultado pro template atual** (scaffold mínimo `	- `): journal real começa com `- ` (bullet vazio top-level). Sem property `type:: #template`; sem wrapper.
- **Cleanup retroativo dos 3 journals afetados** aplicado na mesma sessão (remoção das linhas 1-4 do wrapper).

Sem ADR novo: refinamento mecânico (decisão central de "skill bootstrap journal via template" intacta; muda **como** template é consumido). Paralelo + cross-ref explícito a Sub-decisão 4 § Adendo 2026-05-28 que solucionou o mesmo problema em outra skill.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério (todos 4 satisfeitos: decisão central intacta; sem categoria nova; sem restrição externa; caráter explicativo + refinamento).

**Cross-refs:** Sub-decisão 3 § Adendo v0.4.2 (mesmo fix em `/journal-close`); Sub-decisão 10 § Adendo v0.3.1 (mesmo fix em `/journal-review`); Sub-decisão 4 § Adendo 2026-05-28 (pattern doutrinal análogo pra `/init-logseq-project`).

#### Adendo (2026-06-15) — CLI thin orchestrator

Substância de write da skill `/journal-note` (find-or-create bucket, bootstrap journal via template, sub-bullets mecânicos `commit:`/`plan:`, sanitização kebab-case + NFD-strip de acentos PT-BR, gate `pgrep -xi logseq`) migra para `meta_bridge.journal_note` (CLI `mb journal-note`).

SKILL.md preserva: frontmatter, `## Argumentos`, scope guards narrativos (`## O que NÃO fazer`), e a heurística de derivação `<domain>` via git toplevel + `AskUserQuestion` fallback (decisão semântica que requer harness CC). Passos do thin orchestrator: derivar `--domain` → `Bash mb journal-note --domain "<X>" "<content>"` → reportar output.

Decisão central da Sub-decisão 1 ("skill escreve no journal de hoje + bucket idempotente") intacta — refinamento mecânico cascateando materialização CLI registrada em ADR-002 (cross-ref aqui). Adendo per ADR-034 do toolkit critério: decisão central intacta; sem categoria nova; sem restrição externa; refinamento.

**Cross-refs:** [`ADR-002`](ADR-002-materializacao-cli-mb.md) § Decisão 2 — Cascateamento (decisão duradoura nova); [`meta-system` ADR-016](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-016-target-aware-packaging-mecanico-substitui-mcp-first.md) (critério target-aware aplicado upstream).

### Sub-decisão 2 — Template insertion: literal append

Skills da Bridge que consomem templates do graph (`session-close.md`, `weekly-review.md`) **lêem o `.md` como filesystem markdown**, parseiam placeholders (regex `<([a-z][a-z0-9-]+)>`), substituem com valores resolvidos, e fazem **append literal** no journal/page destino.

`((session-close))` (Logseq block-ref) **NÃO é usada** — block-ref resolve em runtime DENTRO do Logseq desktop via Datalog lookup; com `pgrep` gate fechando desktop, ref vira string morta no markdown salvo.

**Papéis dos templates** (pós-Onda 4 do meta-sistema):

| Template | Papel | Renderiza em desktop? |
|---|---|---|
| `daily-journal.md` | Contract visual + schema (auto-apply via `config.edn`) | Sim — operador vê `## Inbox`, `## Doing`, `## Waiting`, etc. |
| `Project Template.md` | Contract visual + schema (insertion via `/init-logseq-project`) | Sim — props + headings após apply |
| `session-close.md` | **Schema-only** — consumido pela skill `/journal-close` | Placeholders aparecem como string literal ao clicar `[[session-close]]` no desktop |
| `weekly-review.md` | **Schema-only** — consumido pela skill `/weekly-review` | Placeholders aparecem como string literal ao clicar `[[weekly-review]]` no desktop |

**Razão de `session-close.md` e `weekly-review.md` virarem schema-only**: queries Datalog/simple-query no template renderiam só com desktop aberto (gate fechado por design); mantê-las como queries vivas no graph contradiz Sub-decisão 2 (literal append). Schema-only colapsa o template em consumer-driven da skill — perde rendering desktop, ganha alinhamento com Camada 4 (`status::` lifecycle, não markers GTD). Trade-off concreto: operador consome via skill, não via navegação direta. Documentado em commit `364465e` do `logseq-notes` (Bloco 1 da Onda 4).

### Sub-decisão 3 — `/journal-close` synthesis

Skill `skills/journal-close/SKILL.md`. Frontmatter:
- `name: journal-close`
- `description: Sintetiza sessão CC atual em bloco no journal Logseq de hoje (consome session-close.md schema)`
- `disable-model-invocation: false`

Passos:
1. Gate git repo + Logseq desktop (cheap-first: git antes de pgrep).
2. Coleta session context:
   - **Repo basename**: `git rev-parse --show-toplevel | xargs basename`.
   - **Plan slug ativo**: probe ordenado — (i) variável env `PRAGMATIC_ACTIVE_PLAN_SLUG` exposta por `/run-plan` (gap conhecido — hoje sempre None nesta probe); (ii) probe `docs/plans/*.md` modified nas últimas 2 horas; (iii) None — campo vai como `—`.
   - **Mudanças (summary)**: `git log --since="2 hours ago" --oneline --no-merges`.
3. **Sintetizar rascunhos + confirmação** (adendo 2026-05-28 — ver § Adendo abaixo): skill (agente) extrai rascunhos de Topic candidates, Decisões e Follow-ups de session context (commits + conversation). AskUserQuestion única chamada com 3 enums presentando rascunhos pra confirmação: Topic (candidates + Other), Decisões (`Confirma rascunho` / `Edita via Other` / `Sem decisões — limpar rascunho`), Follow-ups (análogo). Rascunho vazio → enum cai pra binary `Confirma "sem"` / `Há — descrever via Other`.
4. Compõe bloco **literal** seguindo schema de `session-close.md` (parse placeholders + substitui).
5. Append no `~/Notes/logseq/journals/$(date +%Y_%m_%d).md` sob seção `## Notes` (regex strict `^- ## Notes` — top-level, zero tab; ausência → warning loud + append no fim).
6. Reporta path tocado + bullets count.

Falha clara se `session-close.md` ausente (`Template session-close.md ausente em ~/Notes/logseq/pages/ — feature requer setup do graph`).

**Adendo 2026-05-28 (primeiro uso real)** — duas mecânicas refinadas:

(a) **Regex `^- ## Notes` (zero tab)**: SKILL original tinha `^\t- ## Notes` (1 tab). Primeiro uso real falhou — auto-apply do Logseq via `template-including-parent:: false` E mecânica de `/journal-note` (Sub-decisão 1 step 6) ambos produzem headings top-level (`- ## <heading>`, sem indent). Regex strict atualizada matche formato canonical. Análogo aplicado em Sub-decisão 5 (regex `^- ## Inbox/Doing/Waiting`).

(b) **Synthesis-then-confirm** em vez de interview puro: SKILL original pedia operator descrever Decisões + Follow-ups do zero via AskUserQuestion Other. Operator flagou friction: agente que executa skill TEM acesso a session context — deveria sintetizar rascunhos e pedir confirmação em vez de interview. Topic continua candidate-based (já era). Decisões + Follow-ups viram draft-then-confirm (3 opções: Confirma rascunho / Edita via Other / Sem — limpar). Razão: reduz friction (operator não re-articula coisas já registradas em commits/conversation) e aproveita context disponível ao agente runtime.

Adendo per [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério (todos 4 satisfeitos: decisão central intacta — /journal-close ainda sintetiza sessão em bloco no journal; sem nova categoria; sem restrição externa; caráter explicativo — refinamento de mecânica). Não-trivializa Topic (segue candidate-based via Other override).

#### Adendo v0.2.0 (2026-05-28) — retrofit pra tasks DONE em hashtag-buckets

Materializa [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md). Refinamento mecânico (decisão central intacta — skill ainda sintetiza sessão CC no journal de hoje; muda o **formato** do bloco produzido).

Refinamentos do diff v0.1.x → v0.2.0:

- **`session-close.md` template removido como consumer**: ADR-002 Sub-decisão 2 archive o template. `/journal-close` v0.2.0 compõe in-skill — não há mais Step de "lê template, parseia placeholders, substitui". Falha do "Template ausente" eliminada do Step 2.
- **Format do bloco synthesized**: muda de schema (`## Session close: <topic>` com bullets labels `**Repo afetado:**` / `**Plano:**` / `**Mudanças:**` / `**Decisões tomadas:**` / `**Follow-ups:**`) pra **tasks DONE agrupadas por bucket `- #<repo>`** com sub-bullets mecânicos (`- commit: <hash>`, `- plan: <slug>`, `- [[<page>]]`). Bucket per repo coberto pela sessão; multi-repo emerge naturalmente quando commits cruzaram repos.
- **Synthesis-then-confirm preservado** (Adendo de 2026-05-28 acima): agente extrai rascunho de tasks DONE; AskUserQuestion única com 3 opções (Confirma / Edita via Other / Sem commits úteis — não escrever). Topic e Decisões/Follow-ups labels do v0.1.x desaparecem porque schema novo não tem esses campos.
- **Find-or-create cada bucket** (Step 5 da v0.2.0): substitui o append na seção `## Notes` do v0.1.x (regex `^- ## Notes`). Pós-retrofit, template `daily-journal` é scaffold mínimo (ADR-002 Sub-decisão 1) — sem heading `## Notes`. Find-or-create de `- #<repo>` é idempotente cross-skill com `/journal-note` prévios da mesma sessão (contract crítico per ADR-006 § Decisão § 1).
- **Sub-bullets mecânicos**: limitados a `commit:`/`plan:`/`[[<page>]]` per ADR-006 § Decisão § 3 contract (skills consomem só markers + cross-refs mecânicos; sub-bullets ficam não-parsed). Convention fechada herda do Adendo v0.2.0 de Sub-decisão 1.
- **Coleta multi-repo via probe explícito**: Step 2 da v0.2.0 enumera cwds tocados na sessão via inspect do conversation history (agente lista paths visitados), depois roda `git log --since=... --no-merges` em cada cwd descoberto. Mecânica determinística com fallback (degrada pra single-repo se conversation history não expõe cwds, reportando warning). v0.1.x assumia single-repo via cwd; v0.2.0 reconhece que sessões reais cruzam repos (Onda 4.5 atual é exemplo — Blocos 1-6 tocam 3 repos).
- **Idempotência intra-skill via dedup `commit:<hash>`**: Step 5 ganha probe pré-write em cada task DONE candidata; se `commit:` sub-bullet com mesmo hash já existe sob o bucket, skip. Cobre cenário Stop hook fires múltiplas vezes (Sub-decisão 6 Limitações reconhecida) — operator aceitar `/journal-close` 2× é seguro.

Pré-condições v0.2.0 herdadas intactas: `pgrep -xi logseq` gate (Sub-decisão 7 + Adendo v0.1.2), failure-closed; gate git repo preservado (skill deriva basename do cwd como repo principal).

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (skill `/journal-close` sintetiza sessão no journal de hoje); sem categoria nova; sem restrição externa nova; caráter explicativo + refinamento.

**Stop hook `suggest_journal_close.py` permanece intacto** — lógica do hook (3 gates: marker `[PRAGMATIC: plan-done]` no transcript + `.claude/local/` exists + Logseq fechado) é agnóstica ao formato do bloco que `/journal-close` produz. Sugestão "considere /journal-close" continua válida; mudança de output da skill é transparente pro hook. Validação no Bloco 3 do plano `onda-4-5-journal-retrofit-gtd` confirma compatibilidade (sem mudança de código).

#### Adendo v0.3.0 (2026-06-11) — escopo expandido + template humano-amigável

Materializa demanda emergida na sessão CC `generalizacao-mecanizacao` (no `meta-system`, 2026-06-11): operador produziu síntese manual de fechamento em formato divergente do v0.2.0 e identificou explicitamente 2 eixos de divergência ("template feito mais pra máquinas/sistemas que pra humanos — sensação de abrir o git log"). Decidida via `/triage` 2026-06-11 (opção (a) — refactor `/journal-close` existente; execução independente do item BACKLOG sobre materialização CLI `mb`). Refinamento mecânico (decisão central intacta — skill ainda sintetiza sessão CC no journal de hoje; muda **escopo** + **template** do bloco produzido).

Refinamentos do diff v0.2.0 → v0.3.0:

- **Escopo expandido de DONE-only para DONE + TODO/WAITING + narrativa editorial**: v0.2.0 limitava ao trabalho mecânico fechado (DONE-tasks + commit/plan metadata). v0.3.0 incorpora também: frame de sessão (1 linha situando), insights/pivots conceituais (header + sub-bullets de prosa), mudanças finas não-codificadas (memory refinada, padrões reconhecidos, notas operacionais), próximos passos com markers GTD nativos (TODO/WAITING), e direção emergente (síntese reflexiva). Cada seção opcional — sessão puramente mecânica degrada elegantemente pra padrão DONE-only flat estilo runbook (preserva caso de uso "fechei trabalho mecânico" da v0.2.0 como sub-caso).
- **Template humano-amigável substitui git-log-like flat**: v0.2.0 produzia bullets flat estilo `- DONE <commit subject>` + `- commit: <hash>` + `- plan: <slug>` (operador metáfora literal: "sensação de abrir o git log"). v0.3.0 usa linguagem humana 2ª pessoa quando faz sentido editorial, bullets aninhados ≥3 níveis quando útil, narrativa fluida, GTD markers Logseq nativos (DONE/TODO/WAITING como block markers, não prefixos prosa).
- **Conversation context inspection estendida (novo)**: agente runtime inspeciona transcript da sessão pra extrair material editorial além de commits (insights, mudanças finas, próximos passos enunciados pelo operador, direção emergente, cross-refs). Julgamento do agente sobre o que vale registrar — não mecânico. v0.2.0 inspecionava conversation context só pra enumerar cwds tocados (multi-repo); v0.3.0 estende escopo da inspeção a substância editorial.
- **Sub-bullets free-form (contract ADR-006 § Decisão § 3 preservado, leitura nuanceada)**: v0.2.0 declarava sub-bullets "limitados a `commit:`/`plan:`/`[[<page>]]`" porque a skill só PRODUZIA esses tipos de metadata mecânica. v0.3.0 produz prose livre como caso default — mas o contract ADR-006 ("sub-bullets free-form prose, non-parsed pelos consumers") está intacto: a convenção é sobre o que consumers parseiam, e v0.3.0 obedece (composição interna da skill, não parsing). `commit:<hash>` e `plan:<slug>` continuam suportados como metadata opcional sob DONE tasks (rastreabilidade quando material), não obrigatórios.
- **Idempotência intra-skill via dedup `commit:<hash>` (parcial pós-retrofit)**: v0.2.0 garantia idempotência intra-skill via dedup de hash em pré-write. v0.3.0 mantém esse mecanismo pra children com metadata `commit:`, mas children narrativos puros (frame, insight, mudanças finas, próximos passos, direção) **não têm dedup mecânica** — operador rodando `/journal-close` 2× pode duplicar conteúdo narrativo. Mitigação: aceitar `Edita via Other` no 2º run pra revisar/consolidar. Trade-off aceito conscientemente (escopo expandido sacrifica idempotência intra-skill perfeita; Stop hook fires múltiplas vezes deixa de ser totalmente coberto por hash dedup).
- **Brevidade > completude como princípio editorial**: v0.3.0 explicita que sessão simples (1 fix pequeno) não deve inflar pra inventar insight/direção. Degradação elegante pro padrão runbook v0.2.0 é caso legítimo, não fallback de emergência.
- **Linguagem 2ª pessoa quando faz sentido editorial**: operador é o leitor do journal; prosa de manual ("o sistema realizou X") fica esquisita. Convenção editorial nova, não rule rígida — "quando faz sentido" preserva julgamento.
- **Frontmatter `description` atualizada**: v0.2.0 dizia "Sintetiza sessão CC em tasks DONE agrupadas por #domínio no journal Logseq de hoje" (DONE-only); v0.3.0 diz "Sintetiza sessão CC no journal Logseq de hoje — narrativa humano-amigável agrupada por #domínio (DONE + TODO/WAITING + insights)".
- **Coleção de princípios editoriais documentada no SKILL.md Step 3**: 2ª pessoa, bullets aninhados, opcionalidade per seção, GTD markers nativos, sub-bullets free-form, brevidade > completude. Substitui a lista compacta da v0.2.0 ("buckets, sub-bullets mecânicos limitados") por mental model rico que o agente runtime aplica como editor.

Pré-condições v0.3.0 herdadas intactas: `pgrep -xi logseq` gate (Sub-decisão 7 + Adendo v0.1.2), failure-closed; gate git repo preservado (skill deriva basename do cwd como repo principal); coleta multi-repo via probe explícito + fallback single-repo; find-or-create idempotente cross-skill com `/journal-note` (contract ADR-006 § Decisão § 1); bootstrap journal via `daily-journal.md` template.

**Referência editorial concreta (forma do dado real)**: bucket `- #meta-system` em `~/Notes/logseq/journals/2026_06_11.md` linhas 11-51 — síntese manual da sessão `generalizacao-mecanizacao` é o exemplo canônico do template humano-amigável esperado. Operador produziu manualmente, identificou divergência do v0.2.0, demandou refactor.

**Stop hook `suggest_journal_close.py` permanece intacto** (re-confirmado em v0.3.0) — lógica do hook (3 gates: marker `[PRAGMATIC: plan-done]` + `.claude/local/` + Logseq fechado) é agnóstica ao formato do bloco que `/journal-close` produz. Mudança de output da skill (v0.2.0 → v0.3.0) é transparente pro hook; sem mudança de código no `hooks/suggest_journal_close.py`.

**Gatilho de revisão v0.3.0 → futuro v0.4.0** (registrado nos gatilhos gerais da § Gatilhos de revisão; ver gatilho 13 abaixo): se item 2 do BACKLOG (materialização CLI `mb`) for executado, template humano-amigável pode mover pra módulo Python (Click/Typer) com flag `--reflective` vs `--mechanical`, colapsando v0.3.0 + degradação runbook em flag explícita. Adendo v0.4.0 (ou ADR novo se decisão central muda) materializa.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (skill `/journal-close` sintetiza sessão CC no journal de hoje); sem categoria nova; sem restrição externa nova; caráter explicativo + refinamento (forma de produção, não objeto produzido).

Cross-refs:
- `BACKLOG.md` linha item 1 (refinada em commit `da01637`, lock decisional via `/triage` 2026-06-11).
- `.claude/local/NOTES.md § 2026-06-11` — pedido literal integral do operador + análise dual-eixo.
- `meta-system` BACKLOG commit `5294c0f` — entry recíproca upstream (dual-entry pattern reconhecido nesta sessão como mitigação F3).

#### Adendo v0.4.0 (2026-06-12) — reconciliação prévia com journal pré-existente

Materializa refinamento decidido via `/triage` 2026-06-12: antes de compor síntese, skill consulta conteúdo prévio gravado em journals (sessões anteriores mesmo-dia + janela retroativa configurável) e reconcilia transições — TODO/WAITING anteriores fechados pela sessão corrente recebem marker change in-place no journal source. Refinamento mecânico (decisão central intacta — skill ainda sintetiza sessão CC no journal de hoje; muda **fluxo de coleta** + **scope de write** pra incluir update de markers em journals prévios).

Refinamentos do diff v0.3.0 → v0.4.0:

- **Janela retroativa de leitura prévia (novo)**: flag `--days N` (default 0 = só journal de hoje). N=0 cobre sessões anteriores mesmo-dia; N>0 estende pra dias passados. Paralelo doutrinal a `/journal-load` (Sub-decisão 9) — mesmo mecanismo de janela `--days N` per Adendo v0.2.1 (local TZ).

- **Step novo entre coleta de session context e síntese (Step 2.5)**: ler buckets pré-existentes na janela cross-repo (todos os buckets em todos os journals lidos). Para cada bucket, coletar markers `TODO`/`DOING`/`WAITING` ativos via regex análoga a `/weekly-review` Sub-decisão 5 § Adendo v0.2.0 (`^\t- (TODO|DOING|WAITING) (.*)$`, 1-tab indent restrita). Estes formam o **backlog reconciliável** da invocação.

- **Reconciliação na fase de synthesis (Step 3 refinado)**: agente confronta backlog reconciliável com session context. Match via judgment semântico (DONE/commit/plan atual fecha TODO/WAITING anterior?); cross-refs explícitos (`commit:<hash>`, `plan:<slug>`, `[[<page>]]`) em prior content servem como hint forte quando matching textual ambíguo.

- **Modify-in-place no source quando match confirmado (Step 5 refinado)**: marker change `TODO`/`DOING`/`WAITING` → `DONE` no journal source onde foi capturado. Sub-bullets preservados. Mecânica idêntica a `/weekly-review archive`. **Sem annotation extra** sob o marker original — SSOT in-place per ADR-002 Sub-decisão 4 do logseq-notes ("markers nativos como SSOT in-place"). Operador escolheu opção pura via `/triage` (rejeitou annotation cross-ref e append-only alternativas).

- **Synthesis pós-reconciliação**: rascunho do novo bucket reflete trabalho da sessão corrente (DONE tasks + frame/insight/etc per v0.3.0); reconciliação aparece **implicitamente** — DONE no novo bucket é o registro do trabalho, marker change no source materializa a transição. Sem "closure cross-ref bullet" no novo bucket — redundância natural elimina-se.

- **Synthesis-then-confirm estendido**: `AskUserQuestion` única apresenta (a) rascunho do novo bucket per v0.3.0 + (b) lista de transições in-place propostas (paths + linhas + before→after). Operador confirma ambos juntos, edita via Other, ou recusa.

- **Cross-repo escopo do scan**: per decisão `/triage`, todos os buckets na janela entram no scan (mesmo-repo `#<basename>` + cross-repo `#<outro-domínio>`). Sessão de meta-bridge pode fechar TODO em `#meta-system` se conexão material existe.

- **Window vazia ou sem matches reconciliáveis**: degrada elegantemente. Sem prior content → flow v0.3.0 puro (rascunho do novo bucket + write append). Prior content sem matches reconciliáveis → idem (Step novo lê contexto sem trigger de modify-in-place).

- **Idempotência intra-skill preservada parcial** (já era parcial em v0.3.0): dedup por `commit:<hash>` continua; modify-in-place é idempotente per natureza (marker já DONE não muda na 2ª execução).

- **Gate `pgrep -xi logseq` mantido**: skill v0.4.0 segue write (incluindo modify-in-place em journals prévios) — gate failure-closed permanece. Skill **não** se torna read-only — caso da exceção Sub-decisão 7 Adendo (2026-06-12) não aplica.

Pré-condições v0.4.0 herdadas intactas: gates Sub-decisão 7; gate git repo preservado; coleta multi-repo per probe explícito + fallback single-repo; find-or-create idempotente cross-skill com `/journal-note`; bootstrap journal via `daily-journal.md` template.

**Frontmatter `description` atualizada**: v0.3.0 era "Sintetiza sessão CC no journal Logseq de hoje — narrativa humano-amigável agrupada por #domínio (DONE + TODO/WAITING + insights)"; v0.4.0 acrescenta sufixo "+ reconciliação prévia (--days N)".

**Cross-refs:**
- `/weekly-review` Sub-decisão 5 § Adendo v0.2.0 — paralelo mecânico (markers in-place SSOT, archive).
- `/journal-load` Sub-decisão 9 — paralelo de flag `--days N`.
- ADR-002 Sub-decisão 4 do logseq-notes — invariante "markers nativos como SSOT in-place" preservada.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (skill `/journal-close` sintetiza sessão CC no journal de hoje); sem categoria nova; sem restrição externa nova; caráter explicativo + refinamento (fluxo de coleta + scope de write expandidos).

#### Adendo v0.4.1 (2026-06-12) — refinamento editorial dos princípios de síntese

Materializa diagnóstico empírico pós-v0.4.0: operador comparou o bucket `- #meta-system` em `~/Notes/logseq/journals/2026_06_11.md` (síntese manual referência, satisfatória — agrupamento conceitual, "Mudanças finas" capturando pattern semântico) com fechamentos subsequentes produzidos pela skill v0.3.0/v0.4.0 nos journals `2026_06_12.md` e identificou queda de qualidade: enumeração de commits 1:1 como DONE separados (em vez de agrupamento conceitual), "Mudanças finas" capturando detalhe técnico-operacional (version pins de cache, paths absolutos, byte counts), seções operacionais cronológicas aparecendo como bullets editoriais ("Pre-trabalho que estruturou a sessão", "Validações por carregamento manual"). Refinamento editorial (decisão central intacta — skill segue sintetizando sessão CC no journal de hoje; muda **princípios editoriais que governam o output** da composição in-skill).

Refinamentos do diff v0.4.0 → v0.4.1 (todos em SKILL.md, sem mudança de fluxo ou estrutura de Steps):

- **Granularidade DONE refinada (Step 3a § Granularidade e profundidade)**: regra explícita "DONE granularidade segue conceito, não commit". Top-level descreve movimento (cristalização, migração, ship, refactor); commits e atomic tasks moram em sub-bullets quando carregam contexto, não como DONE separados. Quando 3-5 commits formaram um movimento conceitual único, agrupar sob **DONE \<conceito\>** com os relevantes (não todos) abaixo.
- **Profundidade livre + critério qualitativo do "próximo nível"**: regra v0.3.0 "bullets aninhados ≥3 níveis quando útil" reformulada — não há teto. Sinal de degradação não é profundidade, é o que aparece no próximo nível. Filtro mental por nível ao descer: "adiciona substância (alternativa rebatida, consequência fina, ressalva) ou só enumeração (mais commits, mais cenários, mais atomic tasks)?". Substância → desce. Enumeração → para.
- **Brevidade vence completude mesmo em sessão rica**: refinamento da v0.3.0 ("brevidade > completude quando substância é magra") — agora regra aplica também a sessão rica. Sessão de 15 commits provavelmente comporta 4-6 DONE top-level conceituais, não 15.
- **Filtros de seleção em "Material editorial via conversation context" (Step 2b)**: cada bloco editorial ganha filtro explícito de inclusão:
  - **Insight/pivot**: 1-2 por sessão (raramente 3), mesmo em sessão longa.
  - **Mudanças finas**: critério "isto vai informar futuras decisões?". Pattern semântico passa; detalhes técnicos-operacionais (version pins, paths absolutos, byte counts, contagens de cenários de smoke test, IDs de memory entries) quase sempre falham.
  - **Próximos passos**: só os enunciados pelo operador ou que emergiram com clareza — não inflar com extrapolações.
- **3 itens novos em "O que NÃO fazer"** correspondendo aos antipadrões observados nos fechamentos pós-v0.3.0: enumerar commits como DONEs separados; detalhes técnicos-operacionais em "Mudanças finas"; seções operacionais cronológicas.

Pré-condições v0.4.1 herdadas intactas: todos os gates e mecânicas de v0.4.0 preservados; sem mudança de fluxo, Steps numerados intactos, frontmatter `description` inalterada (escopo de produção segue v0.4.0).

**Referência editorial reforçada**: bucket `- #meta-system` em `~/Notes/logseq/journals/2026_06_11.md` (linhas 11-51) continua sendo o exemplo canônico — Adendo v0.4.1 codifica o que esse exemplo encarna implicitamente (agrupamento conceitual, "Mudanças finas" como pattern, ausência de seções operacionais cronológicas).

**Stop hook `suggest_journal_close.py` permanece intacto** (re-confirmado em v0.4.1) — refinamento é editorial, sem mudança de mecânica.

**Cross-refs:**
- Diagnóstico empírico: comparação manual do operador entre `~/Notes/logseq/journals/2026_06_11.md` linha 11+ (referência satisfatória) e `~/Notes/logseq/journals/2026_06_12.md` linha 1+ (regressão pós-v0.4.0).

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (skill `/journal-close` sintetiza sessão CC no journal de hoje); sem categoria nova; sem restrição externa nova; caráter explicativo + refinamento (princípios editoriais que governam o output, não mecânica de coleta ou write).

#### Adendo v0.4.2 (2026-06-13) — bootstrap journal: skip wrapper + dedent 1 tab

Materializa mesmo fix mecânico de bootstrap do Adendo v0.2.2 da Sub-decisão 1 (detectado em 2026-06-13; ver contexto integral + lista de journals afetados lá). Bootstrap journal de `/journal-close` Step 5b copiava `~/Notes/logseq/pages/daily-journal.md` literal — incluindo property `type:: #template` + wrapper bullets — sem skip nem dedent.

Fix em v0.4.2 (refinamento mecânico — decisão central intacta):

- Step 5b § Bootstrap journal atualizado: spec antiga "ler ... como template body (scaffold mínimo pós-Onda 4.5)" → spec nova **skipar linhas wrapper** + **dedent 1 tab fixo** no body remanescente. Paralelo explícito a Sub-decisão 4 § Adendo 2026-05-28.

Sem ADR novo. Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério.

**Cross-refs:** Sub-decisão 1 § Adendo v0.2.2 (contexto integral + lista de journals afetados); Sub-decisão 10 § Adendo v0.3.1 (mesmo fix em `/journal-review`); Sub-decisão 4 § Adendo 2026-05-28 (pattern doutrinal análogo).

#### Adendo (2026-06-15) — CLI thin orchestrator

Substância de write da skill `/journal-close` (find-or-create bucket, dedup por commit hash, modify-in-place atomic das transições, bootstrap journal, gate Logseq) migra para `meta_bridge.journal_close` (CLI `mb journal-close` consumindo payload markdown via stdin com `## Append` + `## Transitions`).

SKILL.md preserva integralmente a substância **heurístico-semântica** (Adendos v0.3.0/v0.4.0/v0.4.1 inalterados): matching semântico TODO ↔ DONE, princípios editoriais de síntese humano-amigável (granularidade DONE por conceito, filtros "isto vai informar futuras decisões?", 3 antipadrões editoriais, brevidade vence completude), composição in-skill do payload. Passos do thin orchestrator: coletar session context → sintetizar rascunho → matching semântico → `AskUserQuestion` com dispatch — `Confirma | Edita | Sem substância` → pipe payload pra `mb journal-close`.

Decisão F3 design-reviewer absorvida no `/triage` (2026-06-15): matching semântico fica na skill MD; CLI vira write engine determinístico recebendo transições já decididas.

Decisão central da Sub-decisão 3 ("skill compõe síntese humano-amigável + reconciliação prévia in-place") intacta — refinamento mecânico cascateando materialização CLI registrada em ADR-002 (cross-ref aqui). Adendo per ADR-034 critério: decisão central intacta; sem categoria nova; sem restrição externa; refinamento.

**Cross-refs:** [`ADR-002`](ADR-002-materializacao-cli-mb.md) § Decisão 3 — Divisão CLI/skill por F3/F2; Sub-decisão 1 § Adendo (2026-06-15) (mesmo cascateamento em `/journal-note`); Sub-decisão 4 § Adendo (2026-06-15) (mesmo em `/init-logseq-project`); Sub-decisão 10 § Adendo (2026-06-15) (mesmo em `/journal-review`).

#### Adendo v0.4.3 (2026-06-15 II) — thin orchestrator preserva exemplos inline pra ancorar composição editorial

**Origem:** dogfood do CLI `/journal-close` na própria sessão `materializar-cli-mb` (2026-06-15) revelou que a SKILL.md thin orchestrator enxuta (~117 linhas pós-cascateamento) carregava princípios editoriais v0.4.1 **apenas em referência cruzada** (Adendos v0.3.0/v0.4.0/v0.4.1) sem exemplos inline. Resultado: composição editorial pelo agente drift do padrão dos fechamentos pure-skill prévios.

Comparação documentada (operador conduziu análise side-by-side de 4 buckets pure-skill anteriores vs bucket recém-composto):

- Frame perdeu trajetória X→Y; virou metadata-at-end ("8 blocos, 11 commits, PR mergeado")
- Insight enunciou resultado em vez de momento-de-descoberta ("foi a divisão CLI/skill via F3/F2 absorvidas")
- Antipadrão v0.4.1 enumeração inline em DONE reapareceu ("DONE `mb subA` + `subB` + `subC` + `subD`")
- 2ª pessoa caiu de 5-8 ocorrências por bucket pra 1 ocorrência em 30+ linhas
- Repetição inter-seções entre `DONE Realign` e `Direção que emerge`
- Mudanças finas 2-3 linhas com explicação interna em vez de 1-2 linhas densas

**Hipótese de causa**: refatoração para thin orchestrator removeu Steps 3d (exemplo sessão rica) e 3e (exemplo runbook simples) que ancoravam composição em shot-distance. Princípios em referência cruzada não compensam exemplos canonical inline.

Fix em v0.4.3 (refinamento mecânico — decisão central intacta):

- **Step 3.0 novo (Checklist editorial pré-composição)**: 6 antipadrões v0.4.1 explicitados como gatilhos de revisão durante composição (não checklist mecânico pós-fato). Inclui 2ª pessoa como sinal de quality (4-8 ocorrências por bucket em sessão rica).
- **Step 3a-bis novo (Exemplo sessão rica)**: bucket `#meta-system` canonical da sessão `generalizacao-mecanizacao` (2026-06-11) com sinais editoriais anotados — Frame em 2 linhas, Insight com 2ª pessoa, DONE conceitual, Mudanças finas densas, Direção sem repetição.
- **Step 3a-ter novo (Exemplo runbook simples)**: degradação elegante DONE-only flat — anchor pra sessão sem substância editorial rica.

Sem ADR novo. Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério (todos 4 satisfeitos: decisão central de "skill compõe síntese humano-amigável" intacta; sem categoria nova; sem restrição externa; refinamento + explicativo).

**Pattern reusable**: thin orchestrator de skill que carrega substância heurístico-semântica precisa de exemplos canonical inline em shot-distance. Princípios apenas em referência cruzada não ancoram composição do agente. Cross-skill se ≥2 instâncias similares emergirem (`/journal-review` é candidato natural — também é thin orchestrator carregando substância semântica via 4 heurísticas).

**Cross-refs:** Adendo (2026-06-15) anterior — CLI thin orchestrator (mecanismo); este Adendo v0.4.3 — anchor editorial pra preservar quality da composição pós-cascateamento. `.claude/local/NOTES.md` § 2026-06-15 entry "Pattern thin orchestrator sem exemplos inline drifta composição editorial" (captura do padrão emergente).

#### Adendo v0.4.4 (2026-06-20) — Step 3c: probe externo cross-repo de "Próximos passos"

**Motivação:** drift in vivo na sessão `remote-control` 2026-06-19 — rascunho do `/journal-close` listou `WAITING re-calibração thresholds kl-score ADR-001 (Onda 4 parte ii) — cwd kl-score` em "Próximos passos" sem probe; entry já estava stale (sessão paralela `kl-score` shipou ~3h antes via `fc41cba`). Gap: Step 2.5 + Step 3b probam TODOs prévios do journal contra DONEs da sessão CC (matching de TODOs antigos), mas WAITINGs/TODOs cross-repo recém-compostos pelo Step 3a NÃO eram probed contra estado dos repos cross-ref'd. 7ª instância empírica do memory `feedback_probe_estado_externo_antes_framing` (cross-repo `meta-system/.claude/local/NOTES.md`).

**Mecânica do novo Step 3c** (entre Step 3b e o atual Step 3d Caso degenerado):

1. **Identificar pares `(entry, repo)`** no rascunho recém-composto — para cada WAITING/TODO cuja linha (ou cujo sub-bullet imediato) contém ref cross-repo casando um de 3 patterns alternativos: `cwd <repo>`, `~/Projects/<repo>`, `[[fppfurtado/<repo>...]]`. Entries sem ref cross-repo ficam fora do probe.
2. **Para cada repo identificado** (lista de-duplicada dos pares) rodar `git log --since="48 hours ago" --oneline -15` com cwd absoluto `$HOME/Projects/<repo>`. **Fail-soft** em falha (cwd inexistente, não-git, permissão etc.): emitir bullet in-prosa pré-Step 4 `git log falhou em <repo>: <erro literal> — prosseguindo sem probe deste repo`; sem skip silente nem interrupção (operador ciente sem bloqueio).
3. **Matching semântico** in-skill (per [ADR-002](ADR-002-materializacao-cli-mb.md) § Decisão 3) entre cada WAITING/TODO cross-repo do rascunho e os commit subjects retornados. Judgment **conservador** (alinhado a Step 3b: "incerto → não propor transição"); cross-refs explícitos no sub-bullet do WAITING (commit hash, plan slug, `[[page]]`) valem como hint forte.
4. **Match found → remoção silente** da entry do rascunho + **nota in-prosa** emitida pré-`AskUserQuestion` do Step 4 como bloco único, ordem `falhas primeiro → remoções depois`, 1 bullet por evento. Multi-repo segmenta a remoção por repo (`[<repo-a>] <entryA> [fechada por commit <hashA>: <subjectA>]; [<repo-b>] <entryB> [fechada por commit <hashB>: <subjectB>]`).

Step 4 prompt-statement atualizado pra apresentar **3 substantivos**: rascunho (Step 3a), transições (Step 3b), nota in-prosa do Step 3c (quando presente). Operador inspeciona e pode reverter via `Edita via Other` (ex.: "reincluir entry X — o commit não fechou de fato"). **Step 3c não re-roda na re-composição** do `Edita via Other` — probe é one-shot por invocação; entries reintroduzidas via Other ficam preservadas mesmo casando commits cross-repo (operador já viu a nota in-prosa e decidiu).

**Renumeração**: o que era `#### 3c. Caso degenerado` virou `#### 3d. Caso degenerado`, preservando ordem lexicográfica `3a < 3b < 3c < 3d`. Definição operacional de "rascunho vazio" no novo Step 3d explicitada: "sem nenhum bullet de substância editorial — DONE/Frame/Insight/TODO/WAITING/Mudanças/Direção; entries removidas pelo Step 3c não contam contra".

**Alternativa rejeitada**: annotation marker `(probed YYYY-MM-DDTHH:MMZ)` em cada WAITING — visual mas não preventivo (operador veria marker mas teria que decidir manualmente; surface paralela à do probe atual sem ganho real).

**Trade-off explícito do SSOT in-place** (paralelo a Adendo v0.4.0): a remoção silente da entry **não** entra como `## Transitions` no payload do CLI; write engine (`mb journal-close`) não recebe a remoção como transição mecânica. Auditabilidade pós-fato (re-run, dedup, retroatividade) depende inteiramente da nota in-prosa pré-preview + judgment do operador no `AskUserQuestion`. Trade-off aceito conscientemente — entries WAITING/TODO no rascunho recém-composto são state efêmero pré-write, não merecem footprint bidirecional cross-repo coerente com a filosofia "SSOT in-place do journal não recebe footprint do probe cross-repo".

Sem ADR novo. Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério, **4 critérios satisfeitos**: (i) decisão central da Sub-decisão 3 — "skill `/journal-close` sintetiza sessão CC em bloco no journal de hoje" — intacta; (ii) sem categoria nova de decisão — refinamento aditivo dentro do fluxo de composição (Step 3.x) sem alterar Steps 1/2/4/5; (iii) sem restrição externa nova — probe interno via `git log` padrão em cwds locais já versionados; (iv) refinamento explicativo + mecânico (forma de validação pré-preview, não objeto produzido).

**Cross-ref:** issue [`#8`](../../../issues/8) (linha original do `BACKLOG.md ## Próximos` migrada para forge per [ADR-058 § (i)](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-058-role-backlog-aceitar-forge.md) do toolkit em 2026-06-20, commit `2c31302`); cross-repo `meta-system/.claude/local/NOTES.md` § 2026-06-19T16:02:54Z (6ª instância) + § 2026-06-20 (probe completo kl-score com verificação retroativa).

**Adendo (2026-06-20) — Property `closed:: <ISO UTC>` emit no bucket recém-tocado (mensageiro pro hook block-flow enrich):** write engine (`mb journal-close`) passa a fazer upsert da property `closed:: <ISO UTC>` imediatamente após o bullet `- #<bucket>` ao final do processamento de cada bucket tocado (appended >0 OR dedup >0). Idempotente — replace se já presente, insert senão. Substância: marker SSOT in-place per logseq-notes ADR-002 § Sub-decisão 4 (markers nativos como SSOT in-place); consumido pelo hook downstream (Sub-decisão 12 nova — hook block-flow enrich pós-`/journal-close`) como signal de "bucket recém-fechado, candidato a enrichment Camada 2a". Substância editorial da skill `/journal-close` inalterada — property é metadata mecânica do write engine, não enunciado editorial. Adendo per [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md), 4 critérios satisfeitos: (i) decisão central da Sub-decisão 3 ("skill `/journal-close` sintetiza sessão CC em bloco no journal de hoje") intacta; (ii) sem categoria nova — refinamento aditivo do write engine determinístico no Step 5; (iii) sem restrição externa nova — property é internal contract entre `/journal-close` e Sub-decisão 12 (hook block-flow); (iv) refinamento mecânico (emit de metadata) + explicativo (mensageiro contractual). **Cross-ref:** Sub-decisão 12 (hook block-flow enrich) — consumer side.

**Adendo (2026-06-23) — Flag `--date YYYY-MM-DD` + normalização `closed::` UTC → tz local:** (i) `mb journal-close` ganha flag `--date YYYY-MM-DD` que redireciona o write para o journal da data especificada em vez de sempre hoje. Caso de uso principal: sessão que terminou depois da meia-noite, ou write retroativo do dia anterior. Skill `/journal-close` SKILL.md atualizada em `## Argumentos` documentando a flag e sua ortogonalidade com `--days N` — `--date` controla destino do write; `--days` controla janela do backlog scan; ambas podem ser combinadas (quando combinadas, scan do Step 2.5 ancora na `--date`, não em hoje). (ii) Property `closed::` normalizada de UTC (`datetime.timezone.utc`) para tz local do sistema (`astimezone()`): sem `--date`, `closed:: <now() com offset local>`; com `--date`, `closed:: 23:59:59 da data especificada com offset local` (EOD convention — write retroativo tipicamente encerra o dia). Consumer (`suggest_enrich_blocks.py` + `datetime.fromisoformat()` downstream) suporta ambos UTC e offset local (Python stdlib 3.7+ — sem quebra). Decisão central da Sub-decisão 3 ("skill `/journal-close` sintetiza sessão CC em bloco no journal") intacta — `--date` estende **destino** do write sem mudar escopo de coleta (commits referem-se à sessão CC corrente, independente de `--date`). Adendo per [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md), 4 critérios satisfeitos: (i) decisão central intacta; (ii) sem categoria nova — refinamento aditivo do write engine + normalização de timezone; (iii) sem restrição externa nova; (iv) refinamento mecânico aditivo. **Cross-ref:** forge issue [#24](https://github.com/fppfurtado/meta-bridge/issues/24).

**Cross-ref → Sub-decisão 14 (contrato `#inbox` federado):** o probe de tasks em aberto do Step 2.5 (introduzido no Adendo v0.4.0 acima, não no Adendo `--date`) passa a tratar o bucket `#inbox` (materializado por `/inbox-aggregate`) como superfície consolidada, discriminando entries Forge-synced (informacionais, read-mostly) de PKM-native (SSOT-in-place transicionável). Regras de discriminação canonical em Sub-decisão 14 § Regras de discriminação.

### Sub-decisão 4 — `/init-logseq-project` extraction + idempotência

Skill `skills/init-logseq-project/SKILL.md`. Frontmatter:
- `name: init-logseq-project`
- `description: Cria/atualiza Project Page no graph Logseq a partir do CLAUDE.md/README.md do repo (idempotente; preserva props humanas)`
- `disable-model-invocation: false`

Passos:
1. Gate git repo + Logseq desktop (cheap-first).
2. Resolve metadata mecânica:
   - **basename**: `basename $(git rev-parse --show-toplevel)`.
   - **remote host**: `git remote get-url origin` → parse host (`github.com` → `#github`, `gitlab.com` → `#gitlab`, outro → `#<host>`). Sem remote → `#local`.
   - **repo-path**: path absoluto.
3. Resolve cluster/subcluster. **Paths absolutos hardcoded**:
   - `MRCONFIG_PATH = ~/.mrconfig` (canonical pela convenção do `mr`).
   - `REPOS_MD_PATH = ~/Projects/meta-system/REPOS.md` (canonical pela arquitetura meta-system).
   - Sequência: (i) iterar headers `[<path>]` do mrconfig, expandir `$HOME` via `eval echo`, resolver symlinks via `readlink -f` em ambos lados, comparar paths normalizados; match → extract `tags = ...` via flag-pattern awk; (ii) parse `REPOS_MD_PATH` por basename via grep tabela markdown (`^| \`<basename>\``) + último `^## <cluster>` antes; (iii) AskUserQuestion `Cluster` enum com 9 opções de ADR-003 do meta-system. Mecânica concreta no SKILL.md Step 3.
4. Lê `CLAUDE.md` + `README.md` do cwd (até primeiro `##` OU EOF, max 200 chars). Ambos ausentes/sem-corpo → `description` = vazio (sem populate, sem warning).
5. Resolve Project Page path: `~/Notes/logseq/pages/<basename>.md`.
   - **Ausente**: cria preenchendo `Project Template.md` body. Props (`type:: #project`, `cluster::`, `subcluster::`, `status:: #active`, `repo-path::`, `repo-host::`) + seções (`## Last journal entries`, `## Follow-ups` vazia, `## Decisões locais` vazia). 2 transformações sobre body: (a) **dedent 1 tab fixo** removendo indent wrapper de template-children; (b) **substituir macro `<% current page %>`** por `[[<basename>]]` literal (macro Logseq resolve só com desktop aberto). Mecânica concreta no SKILL.md Step 5.
   - **Presente**: atualização cirúrgica — sobrescreve apenas linhas com props mecânicas (regex `^\s*(cluster|subcluster|repo-path|repo-host)::\s*`). Linhas não-encontradas → adicionar na **ordem canonical** (cluster, subcluster, repo-path, repo-host) após primeira prop existente. Preserva `status::`, blocos sob `## Follow-ups`, `## Decisões locais`, e qualquer prop humana adicional.

**Critério "prop mecânica"**: 4 props fixas exhaustivo. Extensão futura: nova prop mecânica no `Project Template.md` exige adendo neste ADR estendendo a lista.

#### Adendo (2026-05-28) — probe ordenada de cluster: correção do Step 3

v0.1.0/0.1.1/0.1.2 declararam Step 3 sequência como (i) `awk -v p="[$REPO_PATH]" '$0==p,/^\[/' $MRCONFIG_PATH | grep -m1 "^tags = "`; (ii) grep `^- \[<basename>\]` em REPOS.md; (iii) operator prompt. Validação manual da Onda 4 do meta-system (Sessão 6) detectou que (i) e (ii) **sempre falhavam**, fazendo skill cair invariavelmente pro fallback (iii) — funcional mas violando intent doutrinário de auto-discovery via inventory layer. Bugs:

1. **mrconfig literal mismatch**: `$REPO_PATH` vem resolvido por `git rev-parse --show-toplevel` (`/storage/dev/projects/<repo>`), enquanto `.mrconfig` headers usam `[$HOME/Projects/<repo>]` literal (não-expandido). Comparação literal awk nunca bate quando `~/Projects` é symlink pra `/storage/dev/projects/`.
2. **awk range pattern single-line bug**: pattern `$0==p,/^\[/` é range begin..end. Header satisfaz `$0==p` E `/^\[/` na mesma linha — range fecha imediatamente. Mesmo se path comparison batesse, `tags = ` da linha seguinte nunca seria capturado.
3. **REPOS.md format mismatch**: spec assume bullet `^- \[<basename>\]` mas REPOS.md atual usa formato tabela markdown `| \`<basename>\` | <path> | ...`. Grep pattern nunca bate.

Fix em v0.1.3 (refinamento mecânico — decisão central intacta, probe permanece 3-fases ordenadas + fallback prompt):

1. mrconfig: iterar headers via shell loop, expandir `$HOME` via `eval echo`, resolver symlinks via `readlink -f` em ambos lados, comparar paths normalizados. Match → extract `tags = ...` via flag-pattern awk (`$0==p{flag=1;next} /^\[/{flag=0} flag && /^tags = /{print;exit}`) que evita o range single-line bug.
2. REPOS.md: `grep -n "^| \`<basename>\`"` localiza linha + `head -n LINE | grep "^## " | tail -1` pega último cluster heading antes.
3. Operator prompt: inalterado.

Sem ADR novo: a decisão estrutural (probe ordenada 3-fases, fallback prompt) está intacta — só a implementação dos probes (i) e (ii) é corrigida. Linha 120 deste ADR atualizada com sequência sumária correta; mecânica concreta no SKILL.md Step 3.

#### Adendo (2026-05-28) — Step 5 create flow: dedent + macro substitution

v0.1.0/0.1.1/0.1.2/0.1.3 declararam Step 5 (Ausente — criar do zero) como "preencher Project Template.md body" sem documentar 2 transformações necessárias entre template e page raíz. Validação manual da Onda 4 (Sessão 6) detectou os gaps via Cenário 6 (`/init-logseq-project` em repo dummy `/tmp/test-repo`). Gaps:

1. **Indent wrapper**: `Project Template.md` tem props sob `- template:: project` com 1 tab inicial (`\t- type:: #project`, `\t  cluster::`, etc.) — estrutura wrapper de template Logseq. Page raíz canonical (ex.: `pages/drive-sync.md`) tem essas linhas no nível root, sem tab. Spec não dizia "dedent".
2. **Macro Logseq**: template tem `{{query <% current page %>}}` (linha 12). Page raíz canonical tem `{{query [[<basename>]]}}` literal — macro resolveria via Logseq desktop em runtime, mas gate fecha desktop. Spec não dizia "substituir macro".

Fix em v0.1.4 (refinamento mecânico — decisão central intacta):

1. **Dedent 1 tab fixo** no body restante pós-skip de linhas wrapper (`type:: #template`, `- template:: project`, `template-including-parent:: false`). Remove exatamente 1 tab do começo de cada linha (linhas sem tab inicial passam inalteradas). Sub-bullets aninhados mantêm tab relativo.
2. **Macro substitution** literal: `<% current page %>` → `[[<basename>]]`. Demais macros Logseq (`<% today %>`, `<% yesterday %>`, etc.) **não tocadas** — Project Template não usa hoje; expandir só se template ganhar nova macro (esta sub-decisão estende a lista por adendo se acontecer).

Sem ADR novo: refinamento mecânico de "skill consome template como contract dual-papel (schema declarativo pra skill + insertion visual via desktop)" decidida em Sub-decisão 2. Linha 123 atualizada com sumário; mecânica concreta no SKILL.md Step 5.

#### Adendo (2026-06-15) — CLI thin orchestrator

Substância de write da skill `/init-logseq-project` (lookups `~/.mrconfig` + `~/Projects/meta-system/REPOS.md`, bootstrap via Project Template, dedent + macro substitution, props mecânicas idempotentes, preservação de props humanas, gate Logseq) migra para `meta_bridge.init_project` (CLI `mb init-project`).

SKILL.md preserva: frontmatter, `## O que NÃO fazer`, e o **fallback de cluster prompt** via `AskUserQuestion` enum 9-cluster (per `meta-system` ADR-003) — decisão semântica que requer harness CC. CLI faz lookups primeiro; skill prompt dispara só quando ambos lookups falham e `--cluster` não foi passado.

Decisão F1 design-reviewer absorvida no `/triage` (2026-06-15): skill orquestra cluster prompt enum; CLI exige `--cluster` quando lookups falham. Implementação **relaxa** F1 — CLI tenta lookups primeiro (caminho-comum resolve sem skill intervir). Nota registrada em ADR-002 § Decisão 4.

Decisão central da Sub-decisão 4 ("4 props mecânicas exhaustivo + preservação de props humanas + probe ordenado de cluster") intacta — refinamento mecânico cascateando materialização CLI. Adendo per ADR-034 critério: decisão central intacta; sem categoria nova; sem restrição externa; refinamento.

**Cross-refs:** [`ADR-002`](ADR-002-materializacao-cli-mb.md) § Decisão 4 — `mb init-project` cluster resolution; Sub-decisões 1/3/10 § Adendos (2026-06-15) (mesmo cascateamento nas demais skills).

### Sub-decisão 5 — `/weekly-review` parsing via headings em journals

> **Sucessor (2026-06-13):** [Sub-decisão 10](#sub-decisão-10--journal-review-v030--detective-first-com-heurísticas-estruturais) substitui a decisão central desta Sub-decisão. `/weekly-review` v0.2.0 (GTD wizard linear sobre tasks em janela 7d fixa) → `/journal-review` v0.3.0 (detective-first com 4 heurísticas estruturais sobre janela configurável + wizard residual opt-in). Critério ADR-034 do toolkit falha (decisão central muda + rename de skill quebra contract de `name:` no frontmatter — vs Adendos v0.2.0/v0.3.0/v0.4.0/v0.4.1 de `/journal-close` que preservaram skill identity); Adendo não cabe. Conteúdo desta Sub-decisão 5 fica intacto preservando o histórico v0.1/v0.2.

Skill `skills/weekly-review/SKILL.md`. Frontmatter:
- `name: weekly-review`
- `description: Wizard GTD weekly review consumindo headings de daily-journal cross-journals`
- `disable-model-invocation: false`

Passos:
1. Gate git repo + Logseq desktop (cheap-first).
2. Coleta state via **parsing de headings padronizados** cross-journals:
   - **Janela**: `find ~/Notes/logseq/journals -name '*.md' -newermt '7 days ago' ! -newermt 'today'` (range [hoje-7d, hoje-1d]; exclui hoje pra evitar duplicação com bloco semanal appended em journal de hoje).
   - **Inbox**: blocos sob heading `## Inbox` (regex linha estrita `^- ## Inbox` — top-level, zero tab; coberto pelo adendo 2026-05-28 de Sub-decisão 3); filtros archived:: true sintaxe Logseq canonical (linha sub-indented).
   - **Doing / Next Actions**: blocos sob `## Doing`.
   - **Waiting**: blocos sob `## Waiting`.
   - **NÃO** filtrar por `status:: active` (essa property é lifecycle de Project Page per ADR-004 invariante; colapsar pegaria 18+ Project Pages como falsos Next Actions).
3. Truncate max 20 itens por categoria (= 5 chamadas AskUserQuestion seriadas com batch de 4). Ambas listas vazias → recusa silenciosa.
4. Wizard iterativo de classificação. Skill **acumula decisões em memória**; edits no graph aplicam **somente após** Step 5 compor o bloco semanal (atomic-ish — crash mid-wizard = zero side-effect). 4 decisões: `keep`/`next_step` (Other → descrição)/`archive`/`defer` (move pra journal de próxima segunda `date -d 'next Monday'`, preservando heading de origem).
5. Aplicar edits batch + compor bloco semanal **literal** seguindo schema `weekly-review.md` (substituição de `<inbox-blocks>`/`<doing-blocks>`/`<waiting-blocks>` com listas formatadas por sufixo de decisão). Append no journal de hoje. Date placeholder `<% today %>` → `$(date +%Y-%m-%d)` (local TZ alinhado).
6. Reporta totais + distribuição de classificações.

#### Adendo v0.2.0 (2026-05-28) — retrofit pra parsing de task markers + composição in-skill

Materializa [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md). Refinamento mecânico (decisão central intacta — wizard GTD que classifica tasks de janela 7 dias; muda **como** as tasks são identificadas).

Refinamentos do diff v0.1.x → v0.2.0:

- **Coleta via grep de markers nativos**: substitui parsing de headings `## Inbox`/`## Doing`/`## Waiting` (que saíram do daily-journal template per [`logseq-notes` ADR-002](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisão 1) por grep de markers Logseq nativos `TODO`/`DOING`/`WAITING` em journals. `logseq-notes` ADR-002 Sub-decisão 4 estabelece markers nativos como SSOT de estado GTD; Sub-decisão 5 aqui adapta consumer.
- **Regex restrita a top-level** (1-tab indent, filhas diretas de bucket `- #<domínio>`): `^\t- (TODO|DOING|WAITING) (.*)$` per F1 do /triage do plano `onda-4-5-journal-retrofit-gtd`. Markers em sub-bullets (≥2 tabs) ficam como prosa contextual per ADR-006 § Decisão § 3 mental model (sub-bullets = prosa não-parsed).
- **Markers `DONE` e `CANCELLED` não capturados**: terminais por design (per [`logseq-notes` ADR-002](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisão 4) — não entram no backlog do wizard. Audit retrospectivo via leitura direta do journal.
- **Sub-bullets do task apresentados como contexto não-parsed** (per ADR-006 § Decisão § 3 contract): wizard mostra sub-bullets pro operador classificar mas NÃO infere taxonomia por prefixo. Apresentação como prosa em prelúdio à AskUserQuestion.
- **Bucket de origem preservado em decisão `defer`**: task move pra journal de destino sob `- #<domínio>` mesmo do source. Find-or-create do bucket no destino paralelo a `/journal-note` Step 4.
- **Archive via mudança de marker (não property)**: decisão `archive` muda marker do task no source de `TODO`/`DOING`/`WAITING` pra terminal escolhido (`DONE` ou `CANCELLED`). Substitui adicção de property `archived:: true` da v0.1.x. Razão: per [`logseq-notes` ADR-002](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) Sub-decisão 4, markers são SSOT; property `archived::` é pra page-level (`logseq-notes` ADR-001 Sub-decisão 7), não block-level.
- **Composição in-skill**: drop consumption de `pages/weekly-review.md` template. Compose direto no Step 4 (paralelo a `/journal-close` v0.2.0). Template `pages/weekly-review.md` deixa de ser consumer da skill — destino do arquivo no graph fica a critério do operador do logseq-notes (fora do escopo deste ADR).
- **Wizard pacing pós-retrofit**: iteração global cross-marker (M = total geral, não per-marker), batch de 4 perguntas por chamada `AskUserQuestion`. Truncate max 20 por marker (60 total potencial) → até 15 chamadas seriadas no pior caso. Substitui o cálculo "5 chamadas × batch de 4" da v0.1.x (que era per-categoria).
- **Drop gate git repo**: v0.1.x exigia git repo no cwd (sem razão funcional — skill opera sobre `~/Notes/logseq/journals/`). v0.2.0 dropa o gate; pgrep continua canonical.

Pré-condições v0.2.0 herdadas intactas: `pgrep -xi logseq` gate (Sub-decisão 7 + Adendo v0.1.2), failure-closed; truncate max 20 por marker; janela 7 dias excluindo hoje.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (wizard GTD que classifica tasks de janela temporal); sem categoria nova; sem restrição externa nova; caráter explicativo + refinamento.

### Sub-decisão 6 — Hook `suggest_journal_close` (Stop event)

Hook `hooks/suggest_journal_close.py` + binding `Stop` event em `hooks/hooks.json`.

Mecânica: hook recebe stdin JSON com `session_id`, `transcript_path`, `cwd`, `hook_event_name`. Auto-gating triplo:

1. Marker `[PRAGMATIC: plan-done]` em `tail -n 50 <transcript_path>` (signal de `/run-plan` do `pragmatic-dev-toolkit` terminou; marker é contract público emitido pelo toolkit ≥ v2.13.0 commit `b8989c2`).
2. `<cwd>/.claude/local/` exists (signal de uso do toolkit no projeto).
3. `~/Notes/logseq/` exists AND `pgrep -xi logseq` retorna não-zero (desktop fechado — pode escrever no graph sem race).

Todos os 3 → emit JSON `{"systemMessage": "💡 Considere /journal-close pra sintetizar a sessão no journal de hoje."}` em stdout (mecânica canonical não-bloqueante do CC 2.1.x; stderr seria silenciado salvo `--debug`). Qualquer gate falha → exit 0 silente.

Binding:
```json
{
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/suggest_journal_close.py",
          "timeout": 5
        }
      ]
    }
  ]
}
```

**Refinamento futuro de marker stale** (se materializar): hook grava `<session_id>:<timestamp>` em `~/.claude/.hook-last-marker-seen.json` ao fires; próxima invocação ignora marker em `tail -n 50` se já consumido para mesmo session_id. Não implementado nesta versão. Gatilho: ≥2 reports de sugestão soft fora de contexto pós-`/run-plan`.

#### Adendo (2026-05-28) — output mechanism: stderr → JSON systemMessage stdout

v0.1.0/0.1.1/0.1.2/0.1.3/0.1.4 declararam "print mensagem soft em stderr" como mecânica de entrega ao operador. Validação manual da Onda 4 (Sessão 6) Cenário 8 esperava ver mensagem no CLI ao fim do turn em que marker era emitido — script validado standalone funcionou (stderr conteúdo correto), mas operador **não viu nada**. `/debug` isolou root cause via pesquisa em docs do Claude Code (`code.claude.com/docs/en/hooks`) + GitHub issue [anthropics/claude-code #34600](https://github.com/anthropics/claude-code/issues/34600): Stop hook stderr com exit 0 é **silenciado por design** no CLI TUI normal — só visível em `--debug` mode.

Mecânica canonical pra hook influenciar UI em CC 2.1.x: JSON na stdout com fields documentados. Pra notify-style não-bloqueante (sem reabrir turn), o field correto é `systemMessage` standalone (sem `decision: "block"`, que forçaria CC a continuar — anti-pattern pra sugestão soft).

Fix em v0.1.5 (refinamento mecânico — decisão central intacta, gates triplos preservados, conteúdo da mensagem inalterado):

- `hooks/suggest_journal_close.py:72-75`: `sys.stderr.write(msg)` → `print(json.dumps({"systemMessage": msg}))`.
- Docstring atualizada (linhas 5-6 + 15-17) refletindo mecânica nova e citando o issue.

Sem ADR novo: decisão estrutural (Stop event hook, gates triplos, marker contract) intacta — só forma de output muda. Linha 188 atualizada com sumário.

#### Adendo v0.2.0 (2026-06-16) — 2ª trajetória de hook bridging: SessionStart sugerindo `/journal-load`

Plugin ganha 2º hook: `hooks/suggest_session_start_tip.py`. Sub-decisão 6 original (Stop event hook `suggest_journal_close.py` sugerindo `/journal-close` quando `/run-plan` do `pragmatic-dev-toolkit` termina) permanece como trajetória 1 intacta — versionamento v0.1.5 + Adendo (2026-05-28) preservados; nada muda no hook existente.

**Trajetória 2 — SessionStart event:**

- **Gate único:** `cwd` (do payload stdin do CC) resolve via `git -C <cwd> rev-parse --show-toplevel | xargs basename` para um basename; basename é procurado em set extraído de `~/Projects/meta-system/REPOS.md`. Match → tip emitida; no-match / falha de resolução (cwd fora de git, REPOS.md ausente) → exit 0 silente (degradação graciosa).
- **Parser REPOS.md aplica filtro NEGATIVO:** exclui overview `## Clusters (N)` e tabelas sob subsection `### Runtime auxiliar consumido externo`; nas demais tabelas com colunas `Repo` + `Status`, aceita linhas cujo campo `Status` contém `active` (substring lowercase). Discrimina contra `external-dep` (third-party docs) e `archived`. Cobertura cross-cluster: todos os 9 clusters da constelação onde houver tabela com schema `Repo|...|Status|...`.
- **Output:** JSON `{"systemMessage": "💡 /journal-load --days 2 --bucket <basename> traz contexto cross-sessão deste repo."}` em stdout — mesma mecânica do Stop hook per Adendo v0.1.5 acima (CC 2.1.x canonical para soft notification não-bloqueante).
- **Binding em `hooks/hooks.json`:** seção `SessionStart` paralela ao `Stop` existente, mesmo timeout 5s.
- **Cobertura de teste:** suite pytest em `tests/test_suggest_session_start_tip.py` (12 testes — 6 unit em `_load_owned_active` cobrindo filtro NEGATIVO + Status + cross-cluster; 6 e2e in-process em `main()` via monkeypatch de `hook.REPOS_MD` + `sys.stdin`). Suite parcial introduzida sob critério ADR-002 § Decisão 6 Adendo (2026-06-16) — "parsing complexo → pytest".

Gate da trajetória 2 (cwd-matching contra inventário externo read-only) é estruturalmente diferente do gate da trajetória 1 (3 gates situacionais: transcript marker + `.claude/local/` + Logseq closed). 2 instâncias com gates de natureza distinta — generalização do pattern de "hook event suggestion" aguarda 3ª materialização per `philosophy.md` § "Quando YAGNI termina"; este Adendo registra a 2ª trajetória de forma factual sem postular invariante prospectiva.

**Decisão de home — hook standalone vs CLI sub-comando `mb`:** alternativa originalmente apontada pelo `/triage` upstream em `meta-system` (entry-mensageira em `meta-system/BACKLOG.md § "Hook bridging SessionStart"`) era `mb session-start-tip` sub-comando CLI + wiring chezmoi para hooks user-settings. Revisitada via design-reviewer em `/triage` aqui (2026-06-16): hook standalone Python isomorfo a `suggest_journal_close.py` é precedente direto Sub-decisão 6 v0.1.5 — wiring automático via `hooks/hooks.json` no plugin install elimina coupling cross-repo chezmoi. Discoverability manual do CLI `mb` (cf. Adendo CLI thin orchestrator em Sub-decisão 1, 2026-06-15) não se aplica a `session-start-tip` — invocação manual fora de SessionStart context emite tip redundante.

**Cross-ref bidirecional:** ADR-002 § Decisão 6 Adendo (2026-06-16) — refinamento "sem suite de testes formal no MVP" → "suite parcial sob critério parsing-complexo".

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério: decisão central intacta (hook existente não modificado); refinamento aditivo (2º hook paralelo); sem categoria nova de decisão; sem restrição externa nova.

### Sub-decisão 7 — `pgrep` semantics

Probe canonical antes de qualquer write no `~/Notes/logseq/`:

```bash
pgrep -xi logseq
```

- `-x` exige match exato do nome do processo (não substring).
- `-i` torna o match case-insensitive — necessário porque o AppImage do Logseq registra o binário como `Logseq` (capital L), não `logseq`. Sem `-i`, gate retorna falso-negativo (não detecta desktop aberto) e quebra failure-closed.
- Retorna pid(s) se existe; retorna não-zero se ausente.
- Truthy (desktop aberto) → skill recusa com `Logseq desktop aberto — feche antes de executar /<skill>`.

Aplicado a `/journal-note`, `/journal-close`, `/init-logseq-project`, `/journal-review`.

Substituir por `pidof`, `ps -A | grep`, ou outras variantes **não aceito**. Razão: portability declarada (Linux/macOS; `pgrep` está em coreutils baseline).

**Race window** entre probe e write: milissegundos de ordem (probe → write em mesmo Bash subprocess; não medido empiricamente). Fix-forward via undo do Logseq se materializar.

#### Adendo (2026-05-28) — case-insensitive correction

v0.1.0/0.1.1 declararam canonical `pgrep -x logseq` (case-sensitive). Validação manual da Onda 4 do meta-system (Sessão 6) detectou que o processo real do AppImage Logseq aparece como `Logseq` em `pgrep` — gate retornava falso-negativo com desktop aberto, quebrando a invariante failure-closed que toda a Camada 3 depende. Bug afetava 4 skills + hook (5 arquivos). Fix em v0.1.2: `-x` → `-xi`. Sem ADR novo: refinamento mecânico, sem mudança de critério (probe canonical permanece `pgrep`; portability ainda baseline; aplicação ainda nas 4 skills).

#### Adendo (2026-06-12) — Gate aplica somente onde há side-effect

Sub-decisão 9 introduz `/journal-load`, primeira skill read-only do plugin — Read integral ou bloco-de-bucket dos journals na janela, sem write no graph. Race window que motivou o gate `pgrep -xi logseq` **não materializa em leitura concorrente**: Logseq desktop aberto não corrompe filesystem da leitura externa; pode haver delta no buffer não-flushed do desktop, mas isso vira "ligeiramente stale", não corruption.

Critério canonical refinado: gate aplica somente onde há side-effect no graph. As 4 skills write (`/journal-note`, `/journal-close`, `/init-logseq-project`, `/journal-review`) mantêm `pgrep -xi logseq` failure-closed; skills read-only (`/journal-load` agora, futuras read-only) ficam isentas.

Trade-off do bypass aceito: leitura com desktop aberto pode mostrar conteúdo ligeiramente stale (último write do operador no desktop ainda não persistiu em disco). Mitigação: operador que precisa garantir freshness fecha o desktop antes de invocar. Default permissivo evita friction no caso comum (consulta rápida ao journal sem reabrir hábitos de fechar Logseq).

Sem ADR novo: refinamento mecânico do critério de aplicação. Decisão central intacta (`pgrep` permanece probe canonical; failure-closed permanece para writes; portability baseline preservada). Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério.

### Sub-decisão 8 — AskUserQuestion cardinality + frontmatter roles

**Cardinalidade max 4 perguntas** por chamada `AskUserQuestion` per [pragmatic-dev-toolkit CLAUDE.md](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/CLAUDE.md) → AskUserQuestion mechanics.

**Frontmatter roles**:

| Skill | `roles.required` | `roles.informational` |
|---|---|---|
| `/journal-note` | _(roles ausentes — skill não consome papéis canonical)_ |
| `/journal-close` | _(roles ausentes)_ |
| `/init-logseq-project` | _(roles ausentes)_ |
| `/journal-review` | _(roles ausentes)_ |
| `/journal-load` | _(roles ausentes)_ |

Skills da Bridge **não consomem papéis canonical do toolkit** (Resolution protocol per ADR-003 do toolkit, aplicado vazio). Consomem 2 paths absolutos hardcoded fora do path contract — `~/.mrconfig` e `~/Projects/meta-system/REPOS.md` — plus filesystem do graph (`~/Notes/logseq/`). Mudança desses paths exige adendo neste ADR.

Implicação: skills da Bridge **não traversam Resolution protocol step 3** (operador-prompt). Cutucada de descoberta do toolkit **não aplica** — mesmo padrão de `/note` no toolkit (ADR-032).

### Sub-decisão 9 — `/journal-load` mechanics

Skill `skills/journal-load/SKILL.md`. Frontmatter:
- `name: journal-load`
- `description: Carrega conteúdo de journals Logseq na sessão CC (read-only) — default journal de hoje; flags --days N retroativo + --bucket #<hashtag>`
- `disable-model-invocation: false`

Skill **read-only** sem efeito no graph. Sem gate `pgrep -xi logseq` per Adendo a Sub-decisão 7. Sem gate git repo — operador invoca de qualquer cwd; `--bucket` é hashtag literal explicitada pelo operador, não derivada de repo basename. Materializa o gatilho 9 deste ADR ("Skill nova emerge necessária na Bridge").

Passos:

1. Parse args:
   - `--days N` (opcional, default 0): inteiro N ≥ 0. Janela = [hoje-N, hoje] inclusive (N+1 dias). N < 0 ou não-inteiro → recusa com `--days exige N >= 0`.
   - `--bucket <hashtag>` (opcional, default = sem filtro): aceita com ou sem `#` prefix (`#meta-bridge` ou `meta-bridge`); sanitização kebab-case lowercase aplicada per convention de Sub-decisão 1 Adendo v0.2.0.
   - Args mutuamente compatíveis. Sem args → default = journal de hoje, conteúdo integral.

2. Resolve paths dos journals na janela:
   - Shell: `for i in $(seq 0 N); do date -d "$i days ago" +%Y_%m_%d; done` → cada item formatado como `~/Notes/logseq/journals/<date>.md`.
   - Local TZ alinhado per Adendo v0.2.1 a Sub-decisão 1 (consumer da convergência cross-plugin).
   - Paths ausentes → silent skip (journal não criado pra aquele dia é comportamento esperado em dias inativos).

3. Read filemask:
   - **Sem `--bucket`**: Read integral de cada journal existente na janela.
   - **Com `--bucket <hashtag>`**: extrair APENAS o bloco do bucket por journal — regex inicial `^- #<hashtag>($| )` (top-level, zero tab; análogo ao probe de bucket em Sub-decisão 1 Adendo v0.2.0); leitura sequencial até próxima linha matching `^- ` (próximo top-level — bucket, nota livre, ou outra entrada) ou EOF. Sub-bullets aninhados (≥1 tab) preservados como parte do bloco extraído. Bucket ausente naquele dia → silent skip.

4. Conteúdo de cada journal existente na janela entra na working memory CC pelo retorno do Read tool (Step 3). Sem output adicional neste passo.

5. Reporta sumário pós-output (1-2 linhas): `<M de N journals lidos na janela [hoje-N, hoje]>` + bucket aplicado (se houver).

**Adendo (2026-06-18) — Invariante "load ≠ surface":** Step 5 da SKILL.md ("Surface conteúdo + reportar sumário") teve o dump verbatim removido — conteúdo entra na working memory CC quando o Read tool retorna na fase Read filemask (Step 4 da SKILL.md, Step 3 do ADR); re-emitir verbatim é custo O(tamanho_journal) tokens de output sem ganho ao objetivo declarado (evidência empírica: journal de ~418 linhas → ~13K tokens de output, latência percebida = geração token-by-token, não disco). Invariante resultante: `load` é primitiva; consumidor do conteúdo é o reasoning subsequente do modelo, não o operador. Step 5 da SKILL.md renomeado para "Reportar sumário"; sumário curto permanece como único output canônico.

**Edge cases:**

- Janela inteira sem journals existentes → recusa silenciosa com `nenhum journal encontrado na janela [<hoje-N>, <hoje>]`.
- Janela inteira com `--bucket` mas sem matches em nenhum journal → recusa silenciosa com `bucket #<hashtag> ausente na janela [<hoje-N>, <hoje>]`.
- `--bucket` com hashtag inexistente no histórico não detectado em parse-time; só na fase de matching (recusa silenciosa acima).
- N grande (ex.: `--days 90`) sem `--bucket` pode floodar context window. Aceito sem cap — escolha do operador; `--bucket` é a mitigação canonical pra janelas amplas.

**Skill name `journal-load`** vs alternativas (`journal-read`, `journal-context`, `load-journal`): coerente com o par `journal-note` (append) + `journal-close` (write final). Verbo `load` carrega semântica de "trazer para working memory" mais clara que `read` (sugere display passivo).

**Cross-skill semantics**: `/journal-load` é independente das 4 skills existentes. Não compartilha probe-de-janela com `/weekly-review` (purpose distinto — load context vs classify GTD); não exige ordem com `/journal-note` (read-only não corrompe writes pendentes); pode ser invocada em qualquer ponto da sessão (default = hoje captura state corrente).

### Sub-decisão 10 — `/journal-review` v0.3.0 — detective-first com heurísticas estruturais

Skill `skills/journal-review/SKILL.md` (sucessor de `/weekly-review` per cross-ref no topo da Sub-decisão 5). Frontmatter:
- `name: journal-review`
- `description: Detective-first review com 4 heurísticas estruturais sobre janela configurável de journals; wizard GTD opt-in (sucessor de /weekly-review v0.2.0)`
- `disable-model-invocation: false`

Materializa demanda emergida na sessão CC `refinamento-journal-close` (2026-06-12): operador relatou nunca ter usado `/weekly-review`; demandou refactor profundo pra knowledge garden curation com janela ampla, heurísticas detectivas e operações estruturais de bucket emergindo do contexto revisado. Decidido via `/triage` 2026-06-12 (decisão central reformulada — critério ADR-034 do toolkit falha; Adendo não cabe).

Há overlap conceitual com `/journal-close` v0.4.1 (ambos fecham TODOs por evidência), mas eixos distintos: `/journal-close` confronta backlog com **session context** (commits da sessão CC corrente — Sub-decisão 3 Adendo v0.4.0); `/journal-review` confronta com **conteúdo da janela inteira de journals** (correlação inter-journal). Complementares, não substitutos.

**Argumentos:**

- `--days N` (opcional, default 30): inteiro N ≥ 0. Janela `[hoje-N, hoje]` inclusiva (N+1 dias). Paralelo doutrinal a `/journal-load` (Sub-decisão 9). Substitui hardcode 7d herdado de Sub-decisão 5.
- `--from <YYYY-MM-DD> --to <YYYY-MM-DD>` (opcional, mutuamente exclusivos com `--days`): range arbitrário pra revisões mensal-pré-natal, trimestral, etc.
- `--interactive` (opcional, default off): ativa wizard residual após análise detectiva — tasks abertas que não geraram finding entram em wizard linear estilo Sub-decisão 5 (keep/next_step/archive/defer).
- `--write-summary` (opcional, default off): escreve bloco `## Journal review — YYYY-MM-DD` no journal de hoje com findings aplicados + decisões cherry-pick. Default off porque curation é meta-operação invisível (findings deixam trace SSOT via marker change in-place; bloco extra seria redundância editorial).

**Passos:**

1. **Gates (cheap-first)**: `pgrep -xi logseq` → truthy: recusa. Skill é write em Heurísticas 1-2 apply + write opcional do summary (per critério Sub-decisão 7 Adendo 2026-06-12: gate aplica onde há side-effect; `/journal-review` write-capable mantém gate). Sem gate git repo — análoga a Sub-decisão 5 Adendo v0.2.0 § Drop gate git repo (opera sobre `~/Notes/logseq/journals/`, não deriva nada do cwd).

2. **Parse args + resolve janela**: `--days N` → range `[hoje-N, hoje]` inclusivo. `--from/--to` → range explícito (validar `from ≤ to`; usar como mutuamente exclusivos com `--days`). Resolver paths dos journals via shell loop análogo a Sub-decisão 9 Step 2; paths ausentes → silent skip.

3. **Coleta cross-journals** (paralelo a `/journal-close` Sub-decisão 3 Adendo v0.4.0 Step 2.5):
   - Markers `TODO`/`DOING`/`WAITING` top-level (regex `^\t- (TODO|DOING|WAITING) (.*)$`, 1-tab indent restrita — herda de Sub-decisão 5 Adendo v0.2.0).
   - DONE-tasks recentes (regex `^\t- DONE (.*)$`) como material correlacionável.
   - Narrativas (frames, insights, mudanças finas, direção emergente) sob mesma indent top-level dos buckets.
   - Bucket-pai via tree-walk per Sub-decisão 5 e 3 Adendo v0.4.0.
   - Sub-bullets do task (≥2 tabs) como contexto não-parsed.

4. **Análise detectiva — 4 heurísticas MVP**:
   - **Heurística 1 `task-closure-by-context` (task-level, apply)**: TODO/DOING/WAITING X tem match semântico com DONE Y posterior ou narrativa Z na janela → finding propõe close in-place (marker change → DONE). Matching via judgment semântico do agente; cross-refs explícitos (`commit:`, `plan:`, `[[]]`) são hint forte. Princípio conservador: incerto → não propõe (paralelo a `/journal-close` Sub-decisão 3 Adendo v0.4.0).
   - **Heurística 2 `task-zombie` (task-level, apply)**: TODO/DOING/WAITING aberto > T dias sem progresso correlato (zero DONE relacionado, zero referência em narrativa na janela) → finding propõe archive (DONE) ou cancel (CANCELLED). T default = 14 (calibrável; ajustar via gatilho se sinal real emergir).
   - **Heurística 3 `bucket-underused` (structural, report-only)**: bucket aparece em < K journals da janela ou tem < M tasks totais → finding emite evidência detalhada ("bucket #X aparece em K'/N journals com M' tasks abertas; considerar archive ou fund com bucket #Y") sem apply automático — operador aplica manualmente via Edit/Write em sessão dedicada. K default = 2, M default = 2.
   - **Heurística 4 `bucket-emerging` (structural, report-only)**: hashtag/conceito X repetido ≥ N vezes em narrativas (não como bucket top-level) → finding emite evidência ("conceito #X mencionado N' vezes em narrativas dos buckets #A/#B; considerar criar bucket dedicado") sem apply automático. N default = 3.

5. **Apresentação preview-first**: `AskUserQuestion` única ao fim da análise enumera todos os findings agrupados por tipo com evidência inline (source path/linha + contexto que motivou). Opções: `Aplicar tudo` / `Cherry-pick via Other` (operador descreve subset em prosa) / `Cancelar`. Findings report-only (heurísticas 3-4) aparecem como "informativos" — sem apply, só leitura. Zero findings em qualquer heurística → recusa silenciosa.

6. **Wizard residual opt-in (`--interactive`)**: tasks abertas que não geraram finding detectivo (zero matches em heurísticas 1-2) viram input do wizard linear — mesma mecânica de Sub-decisão 5 Adendo v0.2.0 (4 opções keep/next_step/archive/defer; batch de 4 perguntas por chamada). Default off — skill termina após Step 5 sem entrar no wizard.

7. **Apply task-level**: pra cada finding confirmado das heurísticas 1-2, edit cirúrgico no source path — marker change `TODO`/`DOING`/`WAITING` → `DONE` ou `CANCELLED` (paralelo a `/journal-close` Sub-decisão 3 Adendo v0.4.0 Step 5a). Heurísticas 3-4 são report-only — sem apply automatizado no MVP; operador aplica manualmente. Snapshot defensivo é YAGNI no MVP (marker change é single-line atomic, idempotente, reversível via grep + sed manual; canal de falha é matching errado, capturado no preview-first com evidência inline). Apply estrutural automático reabre em v0.4.0 sob gatilho.

8. **`--write-summary` opcional**: flag ativa escreve bloco `## Journal review — YYYY-MM-DD` no journal de hoje (após bucket existente ou no fim) com findings aplicados + decisões cherry-pick. Default off.

9. **Reportar**: path(s) tocado(s); findings emitidos por heurística; findings aplicados vs report-only vs rejeitados; transições aplicadas (heurísticas 1-2) com source path/linha.

**Asymmetry de write retroativo da Heurística 1 vs `/journal-close` v0.4.0**: `/journal-close` v0.4.0 (Sub-decisão 3 Adendo v0.4.0) escreve só no journal de hoje + reconciliação retroativa gated por session context (commits da sessão CC corrente). `/journal-review` v0.3.0 Heurística 1 escreve marker change retroativo em journal histórico (até N dias atrás) baseado em matching textual cross-journal. Asymmetry intencional porque (i) marker change é single-line atomic e idempotente — re-aplicar = no-op; (ii) preview-first com evidência inline é o gate real — operador inspeciona match antes do apply; (iii) snapshot defensivo seria YAGNI: canal de falha é matching errado, capturado no preview. SSOT in-place per ADR-002 Sub-decisão 4 do logseq-notes preservado.

**Interaction matrix com `/journal-close` v0.4.1**: ambas skills usam SSOT in-place via marker change → idempotência natural. Cenários:

- `/journal-review` apresenta finding "fechar X", operador rejeita; `/journal-close` corrente pode fechar X via session context (evidência forte > matching textual cross-journal).
- `/journal-review --days N` aplica fechamento em journal de N dias atrás; `/journal-close --days N` posterior vê marker já DONE durante coleta Step 2.5 → no-op natural.
- Conflito de evidência ambígua: invariante de tie-breaking documentada — "session context > matching textual cross-journal" como heurística semântica (operador tem palavra final via Other no preview).

**Pré-condições herdadas:**

- `pgrep -xi logseq` gate (Sub-decisão 7) — failure-closed; skill é write.
- Regex top-level restrita a 1-tab indent (Sub-decisão 5 Adendo v0.2.0; same em `/journal-close` Sub-decisão 3 Adendo v0.4.0).
- Markers `DONE`/`CANCELLED` terminais — não capturados como reconciliáveis (ADR-002 Sub-decisão 4 do logseq-notes).
- Local TZ (Sub-decisão 1 Adendo v0.2.1).
- Find-or-create de bucket idempotente cross-skill com `/journal-note` (contract ADR-006 § Decisão § 1) — só relevante em `--write-summary` que escreve no journal de hoje.

**Falsos-positivos heading-style** (ex.: `WAITING Próximos passos` capturado pela regex mas é heading textual): pattern reconhecido em fechamento `/journal-close` de 2026-06-12. Judgment do agente deve filtrar antes de emitir finding. Gatilho de revisão: N ≥ 2 reports adicionais → adicionar regra de blacklist textual no Step 4.

**Cross-refs:**

- Sub-decisão 5 (predecessor v0.1/v0.2 — `/weekly-review`; histórico intacto com cross-ref de sucessor no topo).
- Sub-decisão 3 Adendos v0.3.0/v0.4.0/v0.4.1 (`/journal-close` — paralelo de reconciliação prévia + princípios editoriais detective).
- Sub-decisão 9 (`/journal-load` — paralelo de janela `--days N`).
- ADR-006 do meta-system (hashtag-buckets).
- ADR-002 do logseq-notes (SSOT in-place de markers).
- ADR-034 do toolkit (critério Adendo vs Sub-decisão nova — invocado pra justificar Sub-decisão 10 nova vs Adendo a 5).
- ADR-047 do toolkit (modo local de `plans_dir` — usado pra plano deste refactor em `.claude/local/plans/journal-review-refactor.md`).

**Gatilhos de revisão futuros** (paralelos aos gerais da § Gatilhos de revisão deste ADR):

- **Apply estrutural automático heurísticas 3-4**: N ≥ 2 reports manuais do operador de findings report-only que mereceriam apply automático → reabrir como v0.4.0 com snapshot defensivo per-finding-type (snapshot path canonical fora do graph — XDG cache).
- **Heurística `bucket-co-occurrence`**: N ≥ 2 reports manuais de buckets coocorrentes sem fusão proposta. → **Materializada** (Adendo 2026-06-24; issue #9).
- **Heurística `bucket-rename-implicit`**: N ≥ 2 incidentes de bucket sumir/renomear sem propagation. → **Materializada** (Adendo 2026-06-24; issue #10).
- **Heurística `bucket-naming-drift`**: N ≥ 2 reports de variantes do mesmo bucket coexistindo. → **Materializada** (Adendo 2026-06-24; issue #11).
- **Wizard residual `--interactive` precisa virar default**: ≥ 2 reports de findings detectivos zero-cover em janelas grandes → flag muda pra opt-out (`--no-interactive`).

#### Adendo v0.3.1 (2026-06-13) — bootstrap journal: skip wrapper + dedent 1 tab

Materializa mesmo fix mecânico de bootstrap do Adendo v0.2.2 da Sub-decisão 1 (detectado em 2026-06-13; ver contexto integral + lista de journals afetados lá). Bootstrap journal de `/journal-review` Step 8 (`--write-summary`) copiava template via "scaffold (paralelo a `/journal-close`)" — herdando o mesmo drift do `/journal-close` pré-fix.

Fix em v0.3.1 (refinamento mecânico — decisão central intacta):

- Step 8 § Bootstrap journal atualizado: spec antiga "ler ... como scaffold (paralelo a `/journal-close`)" → spec nova **skipar linhas wrapper** + **dedent 1 tab fixo** no body remanescente. Paralelo explícito a `/journal-close` Sub-decisão 3 § Adendo v0.4.2 e Sub-decisão 4 § Adendo 2026-05-28.

Sem ADR novo. Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério.

**Cross-refs:** Sub-decisão 1 § Adendo v0.2.2 (contexto integral + lista de journals afetados); Sub-decisão 3 § Adendo v0.4.2 (fix em `/journal-close`); Sub-decisão 4 § Adendo 2026-05-28 (pattern doutrinal análogo).

#### Adendo (2026-06-15) — CLI thin orchestrator

Substância de scan + apply da skill `/journal-review` (regex top-level cross-journals para markers ativos + DONE-tasks + narrativas + inventário de buckets; modify-in-place atomic; bootstrap journal; gate Logseq) migra para `meta_bridge.journal_review` (CLI `mb journal-review` em dois modos: scan default + `--apply` via stdin transitions).

SKILL.md preserva integralmente: as **4 heurísticas detectivas** (`task-closure-by-context`, `task-zombie`, `bucket-underused`, `bucket-emerging`) com critérios semânticos de match e thresholds (K/M/T/N defaults); o `AskUserQuestion` preview-first com dispatch por opção; o wizard residual `--interactive`; a composição do payload para `--apply` traduzindo cherry-pick. Passos do thin orchestrator: `Bash mb journal-review --days N` → análise detectiva via heurísticas → `AskUserQuestion` → traduzir seleção em transições concretas → `Bash mb journal-review --apply` com payload.

Decisão F2 design-reviewer absorvida no `/triage` (2026-06-15): CLI emite scan em markdown estruturado (Active markers / DONE tasks / Narratives / Bucket inventory) em ordem cronológica ascendente; skill retém findings em conversation memory entre invocações; re-invoca CLI passando paths/linhas/transições concretas (**não IDs opacos**).

Decisão central da Sub-decisão 10 ("detective-first com 4 heurísticas estruturais sobre janela configurável + wizard residual opt-in") intacta — refinamento mecânico cascateando materialização CLI. Adendo per ADR-034 critério: decisão central intacta; sem categoria nova; sem restrição externa; refinamento.

**Cross-refs:** [`ADR-002`](ADR-002-materializacao-cli-mb.md) § Decisão 3 — Divisão CLI/skill por F3/F2; Sub-decisões 1/3/4 § Adendos (2026-06-15) (mesmo cascateamento nas demais skills).

#### Adendo v0.3.2 (2026-06-15) — recalibração T/N + flags opcionais semânticos + descoberta editorial sobre 2c

Refinamento dos defaults T (heurística 2b `task-zombie`) e N (heurística 2d `bucket-emerging`), mais materialização de 4 flags opcionais semânticos pra override caso-a-caso de todos os 4 thresholds K/M/T/N. Defaults K e M (heurística 2c `bucket-underused`) **mantidos em K=2 ∧ M=2** após reexame empírico (ver descoberta editorial abaixo).

Valores novos:

- T = 21 dias (era 14) na heurística 2b — afrouxa o critério zombie pra reduzir falsos positivos em tasks legítimas que demoram > 14 dias mas < 21.
- N = 4 menções (era 3) na heurística 2d — exige mais sinal de emergência antes de propor bucket novo; reduz ruído de hashtag acidentais isoladas.
- K e M mantidos em 2 cada na heurística 2c.

Flags opcionais semânticos materializados na seção `## Argumentos` da SKILL.md, override caso-a-caso: `--bucket-min-journals N` (alias K), `--bucket-min-tasks N` (alias M), `--zombie-days N` (alias T), `--emerging-min-mentions N` (alias N). Nomes semânticos vs. matemáticos (`--threshold-K/M/T/N`) escolhidos pra auto-documentar a invocação — operador não precisa lembrar do mapping letra→heurística meses depois. Defaults aplicam quando flag ausente; flag presente substitui o default da heurística correspondente.

**Descoberta editorial sobre 2c.** BACKLOG entry consumida afirmava que defaults antigos K=2 ∧ M=2 dispariam em "5/6 buckets" do graph (`#meta-bridge`, `#pragmatic-dev-toolkit`, `#meta-portability`, `#h3-finance-agent`, `#dotfiles`, todos com M'≤1). Validação manual deste plano (2026-06-15) contra inventory real do graph revelou que a contagem 5/6 era inferida **ignorando a conjunção** `<K AND <M` da própria heurística: em K=2/M=2 só 4 buckets disparam (`#chezmoi`, `#logseq-notes`, `#meta-portability-mcp`, `#youtube-context`, todos em 1 journal com 0 tasks), e os buckets nomeados no BACKLOG entry têm K' ≥ 3 ou M' ≥ 2 (não disparam em K=M=2). Implicação aritmética da conjunção: aumentar K e M alarga o conjunto "underused" (mais buckets caem abaixo de ambos os cortes); recalibração pra K=3/M=3 produziria 8 findings, não menos. Calibração de K/M na direção certa exigiria rebaixar os thresholds, mas K=M=1 deixa a heurística inerte (`K'<1` impossível pra bucket inventoriado). Conclusão: 4 findings com K=M=2 já é o piso útil da heurística no graph atual; recalibração de 2c **não se justifica empiricamente** neste momento.

T e N saem deste Adendo com calibração validada (relaxam o critério, reduzem ruído na direção certa); K e M ficam preservados em 2/2. Gatilho de revisão futura pra 2c: emerge se a operação real produzir > 4 findings num graph com densidade dobrada (≥ 30 journals na janela default), ou se a doutrina pretender refinar a semântica da conjunção (ex.: trocar AND→OR per opção rebatida no `/run-plan`).

Adendo per ADR-034 do toolkit critério "refinamento doutrinal", **4 critérios satisfeitos**: (i) decisão central da Sub-decisão 10 — "detective-first com 4 heurísticas estruturais sobre janela configurável + wizard residual opt-in" — intacta; (ii) sem categoria nova (refinamento de valores numéricos + parametrização); (iii) sem restrição externa (calibração interna ao plugin); (iv) refinamento mecânico de 2 dos 4 defaults + adição de 4 flags. Alinha com prática dos Adendos vizinhos v0.4.1/v0.4.3 da Sub-decisão 3 de **explicitar os 4 critérios ADR-034** (v0.4.1/v0.4.3 enunciam em prosa corrida; este Adendo numera pra densificar a inspeção).

**Cross-refs:** Sub-decisão 5 (predecessor `/weekly-review` v0.2.0 — herdou K/M/T/N implicitamente sem calibração); Adendos vizinhos v0.4.1 e v0.4.3 da Sub-decisão 3 (estilo editorial análogo de Adendo materializando refinamento mecânico com 4 critérios ADR-034 explícitos); Adendo (2026-06-15) "CLI thin orchestrator" desta Sub-decisão 10 (cascateamento prévio que confirmou doutrinariamente que thresholds K/M/T/N permanecem na SKILL.md, não migram pro CLI — `meta_bridge.journal_review` emite counts mecânicos; judgment heurístico aplica thresholds).

#### Adendo v0.3.3 (2026-06-22) — Refinamento semântico AND→OR na heurística 2c

Materializa o segundo gatilho de revisão documentado no Adendo v0.3.2 acima: "doutrina pretender refinar a semântica da conjunção (ex.: trocar AND→OR)". Heurística 2c `bucket-underused` passa a flagrar buckets com `< K journals OU < M tasks abertas` (antes: conjunção `E`). Defaults K=M=2 inalterados — cada threshold opera independentemente sob OR.

**Motivação (gatilho doctrinal).** Mudança especulativa/preventiva: o primeiro gatilho (densidade dobrada ≥30 journals) não disparou. O segundo gatilho (doutrina refinar AND→OR) foi materializado como opção expressamente prevista. A semântica OR é mais correta: um bucket que aparece em muitos journals mas tem zero tasks abertas é candidato a arquivamento, assim como um bucket com tasks ativas mas pouca menção em journals.

**Impacto aritmético.** Delta concreto: buckets com K'≥2 E M'<2 (presença OK, tasks escassas) ou K'<2 E M'≥2 (menções escassas, tasks ativas) passam a ser flagrados. Na operação real do graph em 2026-06-20 (6 findings listados no Adendo v0.4.0), todos os buckets satisfaziam ambos os eixos (K'<2 E M'<2); o delta pode ser zero no graph corrente. A mudança é semanticamente correta e produtiva sob graph com densidade maior.

**Adendo per [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md), 4 critérios satisfeitos:** (i) decisão central da Sub-decisão 10 — "detective-first com 4 heurísticas estruturais sobre janela configurável + wizard residual opt-in" — intacta; (ii) sem categoria nova — AND→OR é refinamento do operador lógico dentro da mesma heurística `bucket-underused`; output da heurística (`bucket-name`, `categoria-page-proposta`, `refs`) inalterado; (iii) sem restrição externa — ajuste interno ao predicado da SKILL; (iv) refinamento explicativo + mecânico — troca E→OU + documentação da justificativa semântica.

**Efeito colateral no kill-switch.** Flag `--bucket-min-journals 1 --bucket-min-tasks 1` com AND produzia zero findings (K'<1 impossível para bucket inventoriado). Com OR, a condição M'<1 (zero tasks abertas) pode ser satisfeita por buckets com ≥1 aparição em journals — o par de flags não mata a heurística completamente. Comentário da seção `## Argumentos` da SKILL.md atualizado de "mata 2c em janela curta (zero findings)" para "reduz 2c (com OR, só zero findings se nenhum bucket tiver 0 tasks abertas)".

**Cross-refs:** Adendo v0.3.2 desta Sub-decisão (calibração K/M mantida em AND + gatilho de revisão AND→OR explicitado — este Adendo materializa o gatilho); Adendo v0.4.0 desta Sub-decisão (apply estrutural A2/B2 — ortogonal, não afetado pela mudança AND→OR).

#### Adendo v0.4.0 (2026-06-20) — Apply estrutural aditivo (heurísticas 3-4)

**(a) Motivação.** Scan real do graph em 2026-06-20 (`mb journal-review --days 30`) revelou 6 findings atuais de `bucket-underused` formando padrão claro de **família temática fragmentada**: cluster judiciário `#tjpa` + `#tjpa-pje` + `#connector-pje-mandamus-tjpa`; nome velho pós-rename `#meta-portability-mcp` (vira `#meta-portability` ativo per journal 2026-06-12); `#chezmoi` vs `#dotfiles`; `#logseq-notes`. State concreto destrancou decisão sobre **forma do apply** que o gatilho original (linha 701) deixara em aberto.

**(b) Decisão A2 aditiva** (`bucket-underused` → apply). Skill julga categoria-page agregadora via critério mecanizável: (i) prefixo comum (≥2 buckets `tjpa-*`/`meta-*`/etc.); (ii) domínio semântico óbvio sem prefixo (judgment do agente); (iii) ambíguo → fallback `archived-buckets`. Apply em `pages/<categoria>.md`: find-or-create section `- ## Buckets arquivados` + append entry `\t- #<bucket>` com children `\t\t- <journal-path>:<line>` per ref. **Journals históricos intactos** — SSOT in-place per ADR-002 SD4 logseq-notes preservado. Operador override de categoria via cherry-pick em Step 3.

**(c) Decisão B2 forward-only** (`bucket-emerging` → apply). Skill propõe naming canonical do bucket emergente (kebab-case lowercase per [ADR-002 SD3 do `logseq-notes`](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md); NFD-strip de acentos PT-BR realizado pela implementação em `meta_bridge/journal_note.py:sanitize_domain` sem ADR doutrinal próprio; ex.: "captação prévia" → `captacao-previa`). Apply no journal de hoje: find-or-create bucket top-level + sub-bullet `\t- (origem: <narrativa>)` opcional. **Sem rewrite retroativo** de menções históricas em narrativas — preserva progressão temporal (hashtag categoriza forward; menções anteriores em prosa foram intencionais sem categoria). Naming sanitização vive na skill; CLI consome literal.

**(d) Divergência da intenção original** (snapshot defensivo XDG cache). Gatilho original na linha 701 prescreveu "apply estrutural automático com snapshot defensivo per-finding-type — snapshot path canonical fora do graph — XDG cache". State concreto do graph destrancou solução **aditiva** (A2 + B2) que dispensa snapshot — apply não é destrutivo cross-file. **Snapshot defensivo XDG cache não é decisão independente — é função de apply ser destrutivo. Se gatilho original (apply A1/B1 destrutivo) reabrir no futuro sob critério real (N≥2 reports de "queria rewrite cross-file" empírico), snapshot reabre conjuntamente como invariante mecânico, não decisão nova.** Não é regressão da intenção; é refinamento informado pela materialização vs especulação pré-fato.

**(e) 4 critérios [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md)** explicitamente: (i) **decisão central da Sub-decisão 10** — "detective-first com 4 heurísticas estruturais sobre janela configurável + wizard residual opt-in" — intacta; (ii) **sem categoria nova** — apply structural já estava prefigurado em **linha 701 como gatilho de revisão futura** ("reabrir como v0.4.0 com snapshot defensivo per-finding-type"); este Adendo materializa o gatilho com forma aditiva (A2/B2) divergente da forma original especulada (destrutiva + snapshot), mas dentro do escopo prefigurado — apply mechanism heterogêneo per-finding-type é refinamento *previsto*, não *inventado*; (iii) **sem restrição externa nova** — append em pages canonical já estabelecidas + find-or-create em journal de hoje (mesma mecânica de `/journal-note`); (iv) **refinamento explicativo + mecânico** (apply per-heurística com forma específica per A2/B2; payload markdown `## Structural` paralelo a `## Transitions` legacy).

Sem ADR novo. Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério "refinamento doutrinal".

**(f) Interaction matrix com `/journal-close` v0.4.4** (atualização da seção linha 673-677). Step 3c do `/journal-close` (shipped em 2026-06-20 via PR #14, commit squash `b4bb3a5`) faz probe externo cross-repo do rascunho recém-composto, com remoção silente de entries WAITING/TODO stale. Ortogonal ao apply estrutural de `/journal-review` v0.4.0 — Step 3c toca rascunho efêmero pré-write da sessão CC corrente; apply estrutural toca page agregadora (A2) + journal de hoje (B2). Race window mínima; gate `pgrep -xi logseq` compartilhado. **Sequência típica `/journal-review → /journal-close`** na mesma sessão: bucket emergente criado por B2 no journal de hoje fica visível para Step 3a do `/journal-close` como bucket válido (forward-only propaga naturalmente). Sem race; sem footprint cruzado precisar mecanizar.

**(g) Cross-ref.** Issue [`#12`](https://github.com/fppfurtado/meta-bridge/issues/12) (linha original do BACKLOG migrada para forge per [ADR-058 § (i)](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-058-role-backlog-aceitar-forge.md) do toolkit em 2026-06-20, será fechada via `/run-plan §3.4` no encerramento deste plano corrente). Decisão A2+B2 documentada também em `.claude/local/NOTES.md` § 2026-06-20 (transient — Adendo é o registro canonical).

**Cross-refs:** Adendo v0.3.2 desta Sub-decisão (calibração T/N + recalibração K/M preservada em K=M=2; predicado AND→OR refinado pelo Adendo v0.3.3 — apply estrutural deste Adendo ortogonal à mudança de conjunção); ADR-002 § Decisão 3 (matching-on-skill — judgment de categoria-page A2 + naming canonical B2 ficam integralmente na skill, CLI consome literal); [ADR-002 SD3 do `logseq-notes`](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) (sanitização kebab-case lowercase); [ADR-058 § (i)](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-058-role-backlog-aceitar-forge.md) do `pragmatic-dev-toolkit` (modo forge backlog).

**Cross-ref → Sub-decisão 14 (contrato `#inbox` federado):** a heurística 1 (`task-closure-by-context`) passa a usar o bucket `#inbox` (materializado por `/inbox-aggregate`) como superfície de reconciliação intencional, discriminando entries Forge-synced (finding informacional não-selecionável pra apply, read-mostly) de PKM-native (finding de transição normal). Regras de discriminação canonical em Sub-decisão 14 § Regras de discriminação.

#### Adendo (2026-06-24) — Trio de heurísticas v2 estruturais de bucket (co-occurrence + rename-implicit + naming-drift)

Materializa as 3 heurísticas detectivas v2 deferidas em § Gatilhos de revisão futuros (linhas 708-710 — co-occurrence, rename-implicit, naming-drift), levando a skill de 4 para 7 heurísticas. As 3 operam sobre o **inventário/nomes/temporalidade de buckets** (não sobre markers de task), detectando entropia de curadoria do knowledge garden:

- **`bucket-co-occurrence`** (issue #9): dois buckets que coocorrem em ≥ N journals da janela → sugestão de fusão A∪B.
- **`bucket-rename-implicit`** (issue #10): bucket A para de aparecer e A' (semanticamente similar) começa em journals posteriores (gap ≥ G), deixando tasks órfãs sob A.
- **`bucket-naming-drift`** (issue #11): nomes de bucket com distância de Levenshtein ≤ D coexistindo (variantes/typos do mesmo bucket).

**Apply aditivo forward-only** (paralelo direto ao A2/B2 do Adendo v0.4.0): as 3 emitem sugestões materializadas aditivamente em `pages/bucket-hygiene.md` (find-or-create + append com block-refs aos journals de evidência). **Nenhuma reescreve journals históricos** — a fusão/rename de fato permanece **manual** (read-mostly preservado per [logseq-notes ADR-002 SD4](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md)). Merge estrutural histórico **descartado** (destrutivo; contradiz SSOT-in-place). **Sem snapshot defensivo** — apply aditivo por construção, snapshot YAGNI'd-out (mesmo racional do item (d) do Adendo v0.4.0: snapshot é função mecânica de destrutividade).

**Fence read-mostly crítico** (junção com apply task-level pré-existente): `/journal-review` JÁ tem apply task-level destrutivo-in-place (heurísticas 1-2, marker change TODO→DONE em journal histórico, Step 7). As tasks órfãs detectadas por `bucket-rename-implicit` entram **exclusivamente como evidência (block-refs)** na sugestão da hygiene page — **nunca** como transição task-level (o apply destrutivo-in-place das heurísticas 1-2). O operador migra/fecha manualmente.

**Mecânica** — a divisão CLI/skill segue o pattern de 2c (**CLI faz o trabalho mecânico/aritmético; skill aplica judgment semântico**), per ADR-002 § Decisão 3:
- **Geração determinística de candidatos (no CLI)** (`compute_candidates` — função pura): o counting de co-occurrence, o **Levenshtein** de naming-drift e o filtro de gap+órfãs de rename-implicit são **mecânicos** e ficam no CLI (não na skill — um LLM contando pares combinatoriais ou computando Levenshtein "na mão" é não-confiável; é exatamente o que a filosofia `mecânico → código + pytest` manda extrair). O CLI emite 3 seções: `### Co-occurrence candidates` (`#A #B | shared-journals: N`, count ≥ threshold), `### Naming-drift candidates` (`#A #B | distance: D`, Levenshtein ≤ threshold + coexistem), `### Rename-implicit candidates` (`#A | last: <date> | orphans: <refs> | successors: #X #Y`, A com órfãs + sucessores com gap ≥ threshold). + `first`/`last` seen por bucket no `### Bucket inventory`. Flags **CLI-level**: `--cooccur-min-journals N` (2), `--namedrift-max-distance D` (2), `--rename-gap-journals G` (2). (Estende a enumeração de seções do scan descrita no Adendo CLI thin orchestrator desta Sub-decisão — não-exaustiva pós-2026-06-24. Nome `### Co-occurrence candidates` distinto da subsection `### Co-occurrence` do payload de apply abaixo.)
- **Judgment semântico (na skill)**: a skill consome os candidatos e aplica só o judgment — fusão-faz-sentido (co-occurrence); rename plausível dentre os `successors` por similaridade **semântica, não léxica** (rename-implicit — ex.: `weekly-review`→`journal-review` tem Levenshtein grande mas é rename óbvio; **por isso 2f não usa Levenshtein**, ao contrário de 2g); variante-real + escolha de canonical (naming-drift). **Discriminação 2f-vs-2g garantida mecanicamente no CLI** (naming-drift = coexistem; rename-implicit = gap temporal; o mesmo par nunca aparece nas duas seções).
- **Apply** (`parse_hygiene` + `apply_hygiene`): nova seção de payload `## Hygiene` com subsections `### Co-occurrence` / `### Rename-implicit` / `### Naming-drift` → append em `pages/bucket-hygiene.md` sob heading por tipo, idempotente (dedup), forward-only.

**4 critérios [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md)** (Adendo, não sub-decisão nova): (i) decisão central de SD10 ("`/journal-review` detective-first com heurísticas estruturais + apply") **intacta** — trio amplia o conjunto detectivo sem mudar o framework; (ii) **sem categoria nova** — heurística detectiva estrutural com apply aditivo é exatamente a categoria estabelecida pelo Adendo v0.4.0 (A2/B2); (iii) sem restrição externa nova — `pages/bucket-hygiene.md` é page interna do graph (declarada em CLAUDE.md § Hard runtime assumptions); (iv) refinamento aditivo. **Cross-refs:** Adendo v0.4.0 (precedente A2/B2 + snapshot-as-function-of-destructiveness); ADR-002 § Decisão 3 (matching-on-skill); logseq-notes ADR-002 SD4 (SSOT-in-place preservado). Issues #9/#10/#11 cobertas por este Adendo.

### Sub-decisão 11 — `/wiki-compile` mechanics (knowledge layer Onda 2 — escopo Logseq-local estendido)

Skill `skills/wiki-compile/SKILL.md` + sub-tool `skills/wiki-compile/sub-tools/compile.py`. Frontmatter:
- `name: wiki-compile`
- `description: Agrega blocos intra-graph (pages/* + journals/*) numa entity page enriquecida com seções canonical "Notas curadas" + "Sources digeridas" + "Síntese" preservando block-ref trail`
- `disable-model-invocation: false`

**Escopo Logseq-local estendido pra knowledge layer.** ADR-001 originalmente cobria 4 skills (`/journal-note` + `/journal-close` + `/init-logseq-project` + `/weekly-review`) + 1 hook; Sub-decisão 9 estendeu pra 5 skills com `/journal-load`. Pós-Onda 1 do roadmap knowledge layer block-first ([Adendo 2026-06-17 a ADR-013 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-adocao-knowledge-layer-destino-arquitetural-constelacao.md)), escopo Logseq-local de `meta-bridge` estende pra incluir a 1ª skill da knowledge layer materializada nesta onda:

- **`/wiki-compile`** (Onda 2 materializa v0): enrich blocos in-place + agregação em entity pages com seções canonical preservando block-ref trail intra-graph. Necessidade arquitetural per [ADR-008 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-008-skills-meta-reflexivas-categoria.md) § Decisão = bridge Logseq-local agentic que escreve no graph como filesystem markdown (paralelo direto a `/journal-close`). Forma técnica per [ADR-017 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-017-skills-orquestrador-fino-sub-tool-deterministico.md) § decomposição faceta ii: skill orquestrador heurístico-semântica (decisão de **o que** agregar — relevância dos blocos) + sub-tool determinístico (find-or-create section + literal append + dedup por conteúdo).

Passos do orquestrador:
1. Gate `pgrep -xi logseq` (per Sub-decisão 7) — failure-closed; write-heavy implica race window mais larga.
2. Parse `--entity <name>` + `--blocks <path:block-id,...>`; rejeita paths fora de `~/Notes/logseq/pages/*` + `~/Notes/logseq/journals/*` com mensagem `fontes cross-repo exigem captura prévia via /journal-note no journal de hoje`.
3. Find-or-create entity page com template canonical (`provenance:: #enriched` + seções "Notas curadas" / "Sources digeridas" / "Síntese") per [`logseq-notes` ADR-003 SD1+SD2](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-003-knowledge-layer-schema-mecanico.md).
4. Decisão heurístico-semântica de o que agregar (julgamento agente — relevância dos blocos-source) → prepara lista de `((block-refs))` intra-graph com sub-bullet de trilha.
5. Delega ao sub-tool determinístico (1 chamada por bloco selecionado): `python sub-tools/compile.py --entity-page <path> --section <header> --content <markdown>` — find-or-create section + literal append + dedup por conteúdo.
6. Compõe `## Síntese` inline (substância é judgment agente, não append determinístico) via Edit tool.

**Constraint upstream preservado.** Skill restringe `--blocks` a paths intra-graph porque [Sub-decisão 2 deste ADR](#sub-decisão-2--template-insertion-literal-append) (literal append, NÃO block-ref) dimensiona block-ref `((id))` apenas onde `id::` Logseq já materializou — fontes cross-repo (meta-system ADRs, ARCHITECTURE, roadmap) exigem captura prévia via `/journal-note` no journal de hoje pra ganhar `id::` antes de virar input do `/wiki-compile` (dogfood do pipeline meta-bridge; preserva tese block-first do roadmap).

**Modelo evolutivo de disparo (per roadmap pattern "manual → semi-auto → auto").** Onda 2 materializa apenas `/wiki-compile` v0 manual disparado pelo operador; auto-trigger decidido Onda 5 do roadmap. Cabe reabrir homing pra skill local meta-reflexiva (per [ADR-008 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-008-skills-meta-reflexivas-categoria.md)) ou daemon separado quando auto-disparo materializar — decisão deferida sob princípio 4 fundamental "auto-crítica permanente" per [ADR-021 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-021-auto-critica-permanente-4o-principio-fundamental.md).

**Homing canonical das 3 skills da knowledge layer declarado em [Adendo 2026-06-17 a ADR-013 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-adocao-knowledge-layer-destino-arquitetural-constelacao.md).** Esta Sub-decisão materializa `/wiki-compile` v0 apenas — `/wiki-lint` (health checks cross-graph) e `/wiki-distill` (síntese de concept page cross-entidade Camada 4) ganham Sub-decisões adicionais quando materializarem (Onda 3+); declaração pré-fato evitada per princípio YAGNI editorial — pattern dual-entry escala com substância shipada, não com declaração pré-fato (per ajuste F7 do `@design-reviewer` Onda 2).

**Invariantes preservados:**
- Gate `pgrep -xi logseq` aplica à `/wiki-compile` (per Sub-decisão 7 + Adendo v0.1.2). Write-heavy + bookkeeping de block-refs dispara race window mais larga que `/journal-note` — gate failure-closed é canonical.
- Hashtag-bucket pattern preservado em journal (raw sources NÃO interferem com captura via `/journal-note` per `logseq-notes` ADR-002 retrofit) — raw sources moram em namespace canonical `sources/` separado per `logseq-notes` ADR-003 SD3.
- Skills assumem contracts de ADR-004/006/013 do meta-system + ADR-001/002/003 do logseq-notes sem fallback defensivo.
- **Invariante SD2 (literal append, NÃO block-ref) preservada** — `/wiki-compile` insere `((block-id))` apenas pra blocos intra-graph com `id::` já materializado; rejeita inputs cross-repo. Sub-tool determinístico aplica literal append no fim da seção alvo (sem block-ref resolvido em runtime).
- Sub-tool NÃO rewrite ou remove `id::` de blocos (invariante Logseq — entity-as-page pattern). Bloco sem `id::` materializado → reporta, NÃO infere/cria, segue.

**Tensão menor com [ADR-005 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) § fronteiras.** Estado pré-Onda 2 = "5 skills + 1 hook" (Sub-decisão 9 estendeu pra `/journal-load`); estado pós-Onda 2 = "6 skills + 1 hook" (`/wiki-compile` v0 ship). Cardinalidade exata não fixada em ADR-005; extensão cabe editorialmente per ADR-005 § Critério de erosão auditável (skills permanecem intra-Logseq — `/wiki-compile` opera estritamente sobre `~/Notes/logseq/` no graph filesystem).

**Cross-refs:**
- [Adendo 2026-06-17 a ADR-013 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-adocao-knowledge-layer-destino-arquitetural-constelacao.md) (substância nuclear do roadmap knowledge layer + homing canonical das 3 skills + vocabulário canonical fixado).
- [Plano Onda 1 do roadmap](https://github.com/fppfurtado/meta-system/blob/main/docs/plans/onda-1-knowledge-layer-doctrine.md) (PR #17 squash `b1afceb` — doctrine shipped).
- [Plano Onda 2 do roadmap](https://github.com/fppfurtado/meta-system/blob/main/docs/plans/onda-2-knowledge-layer-piloto.md) (este plano consumidor — Blocos 2 + 3 materializam aqui).
- [`logseq-notes` ADR-003](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-003-knowledge-layer-schema-mecanico.md) (schema mecânico — property canonical `provenance::` + namespace `sources/` + properties subset v0; contract concreto consumido pelo `/wiki-compile`).
- [ADR-017 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-017-skills-orquestrador-fino-sub-tool-deterministico.md) § decomposição faceta ii (pattern orquestrador heurístico-semântica + sub-tool determinístico aplicado).
- [ADR-008 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-008-skills-meta-reflexivas-categoria.md) (critério "necessidade arquitetural" aplicado no homing da skill em `meta-bridge`, precedendo decisão de forma técnica per ADR-016).

Sub-decisão per [ADR-034 do `pragmatic-dev-toolkit`](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério "expansão de escopo": (i) decisão central deste ADR — "bridge Logseq-local materializa skills agentic com gate `pgrep` failure-closed + literal append + AskUserQuestion idiomática" — intacta; (ii) categoria nova (knowledge layer Camada 3 entity pages) **justifica** Sub-decisão própria (não Adendo) per pattern de Sub-decisão 9 que estendeu pra `/journal-load` em v0.4.0 (precedente de skill nova → Sub-decisão nova); (iii) sem restrição externa nova; (iv) caráter expansivo + cross-ref recíproco ao meta-system.

#### Adendo 2026-06-23 — `--blocks` opcional com auto-descoberta por `entities::`

`--blocks` deixa de ser obrigatório (issue [#23](https://github.com/fppfurtado/meta-bridge/issues/23)). Dois modos resultantes:

- **Auto-descoberta** (`--entity <name>` sozinho, caso de uso principal): novo Passo 2-bis varre `~/Notes/logseq/pages/*.md` por `entities::` page-level contendo o token literal `[[<entity-name>]]` (brackets fechados — evita falso-positivo substring), exclui a própria entity page, confirma candidatos via `AskUserQuestion`, e os aprovados alimentam o Passo 4 como entradas page-inteira.
- **Cirúrgico** (`--entity <name> --blocks <list>`): comportamento original 100% preservado — único caminho para `journals/*` e block-ids específicos.

**Decisão de escopo:** auto-descoberta varre **só `pages/*`** (fiel à issue). `entities::` block-level de journals (saída do `/enrich-blocks` per SD12) só entra via `--blocks` explícito — auto-descoberta é page-level scoped. **Match literal** por token `[[<name>]]`, sem NER/fuzzy (preserva doutrina anti-regex-mágica do SKILL.md § O que NÃO fazer; relevância semântica fica no agente no Passo 4). **Degradação `id::`**: candidatos cujo bloco canonical não tem `id::` materializado caem na degradação canonical do Passo 4 (reporta, não infere, segue) — sem pré-filtro (reuso do caminho já existente para o formato `<path>` page-inteira; consistente com o modo cirúrgico).

Decisão central de SD11 intacta — orquestrador heurístico + sub-tool determinístico; `--blocks` continua existindo; `compile.py` **não muda** (recebe `--content` pronto). A auto-descoberta adiciona um passo de descoberta upstream do Passo 4, todo no orquestrador MD.

Adendo per [ADR-034 do pragmatic-dev-toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério (todos 4 satisfeitos: decisão central de SD11 intacta; sem categoria nova — refina o contrato de parse de `--blocks`; sem restrição externa nova; caráter explicativo + refinamento mecânico de contrato documentado).

### Sub-decisão 12 — Hook block-flow enrich pós-`/journal-close` (categoria operacional nova: hook como trigger de background write substantivo)

Materializa Onda 5 Faceta 1 do roadmap knowledge layer block-first do meta-system. Plugin ganha 3ª trajetória de hook bridging + 7ª skill `/enrich-blocks` + 4º sub-tool determinístico. Operacionaliza Camada 2a Enriched Blocks ([`logseq-notes` ADR-003](https://github.com/fppfurtado/logseq-notes) SD2) — property canonical `provenance:: #enriched` + `entities:: [[X]] [[Y]]` em sub-bullets de buckets do journal de hoje.

**Categoria operacional nova vs Sub-decisão 6**: SD6 v0.1.5 + Adendo v0.2.0 cobrem hook como **soft notification** (Stop emitindo JSON systemMessage não-bloqueante; SessionStart sugerindo tip). SD12 cobre hook como **trigger de background write substantivo** — Stop event invoca subprocess detached que muta state do graph Logseq. Per [ADR-034 do toolkit](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md), 3 dos 4 critérios para Adendo SD6 falham: (i) decisão central muda (notification → background write); (ii) categoria nova (write engine mediado vs surface UX-only); (iii) caráter estrutural não-explicativo (cria novo hook + nova skill + novo sub-tool + nova property contract). Sub-decisão 12 nova mecanicamente forçada — não default-conservador por densidade editorial. Precedente local SD9/SD11 (skill nova → Sub-decisão nova) confirmam.

**Mecanismo trigger — marker SSOT in-place no journal**: write engine `mb journal-close` passa a emitir property `closed:: <ISO UTC>` no bucket recém-tocado (per Adendo 2026-06-20 a Sub-decisão 3 acima). Hook `hooks/suggest_enrich_blocks.py` lê journal de hoje em todo Stop event e detecta condição "≥1 bucket com `closed::` recente AND ≥1 sub-bullet daquele bucket sem `provenance::`". **Janela "recente" = `datetime.now(UTC) - datetime.fromisoformat(closed::) ≤ 86400s` (24h)** — ambos em UTC, sem ambiguidade TZ vs filename canonical local-TZ de Sub-decisão 1 Adendo v0.2.1 (journal filename é local TZ, mas property timestamp interna é UTC; window calculation usa UTC consistente). Marker no graph (SSOT in-place) — não no transcript — alinha com doutrina cross-plugin de markers nativos como SSOT (paralelo a [`logseq-notes` ADR-002 SD4](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md)). Zero contract público novo entre skills (hook lê estado canonical do graph, não transcript). Auditabilidade gratuita no Logseq desktop.

**Pattern implementação — orquestrador heurístico + sub-tool determinístico**: replica SD11 (`/wiki-compile`). Sub-tool standalone `skills/enrich-blocks/sub-tools/enrich.py` (argparse, sem deps `meta_bridge.*`) faz substância determinística — find blocks sem `provenance::` em property region (regex `^\t{2,}.*provenance::` ancorado em ≥2 tabs per logseq-notes SD2), matching literal de entities contra `pages/<basename>.md`, append properties `\t\tprovenance:: #enriched` + `\t\tentities:: [[X]] [[Y]]`, write atomic in-memory→single-write. Skill orquestrador `/enrich-blocks` (fallback manual ao hook) adiciona LLM judgment de mention substantiva vs ruído + preview informativo VIEW-only (`AskUserQuestion` Confirma/Cancela; sub-tool re-aplica matching literal independente — drift entre preview e write esperado por design, capturado pela Faceta 3 deferida).

**Async mecanismo — Popen detached**: hook timeout 5s não acomoda enrichment com LLM (~10-60s). Probe empírico in-session comparou `os.fork()` vs `subprocess.Popen(start_new_session=True)` vs sync sleep: fork + Popen ambos exit parent ~22ms; sync bloqueia ~3s. Popen adotado per idiomático cross-platform; `start_new_session=True` desacopla via session leader, `stdout/stderr=DEVNULL` silencia output em CC session. Parent exits 0 dentro do timeout; child sobrevive.

**Auto-gating em 4 itens — 3 gates de ambiente + 1 trigger detection** (paralelo a SD6 v0.1.5 + SD7 failure-closed). Gates de ambiente: (i) `.claude/local/` exists em cwd (signal de repo da constelação); (ii) `CLAUDE_PLUGIN_ROOT` setado AND sub-tool path existe (hook é no-op em ambientes parciais); (iii) `~/Notes/logseq/` exists AND Logseq desktop closed (`pgrep -xi logseq` non-zero — case-insensitive AppImage). Trigger detection: (iv) journal de hoje tem ≥1 bucket com `closed::` recente sem `provenance::` (work to do). Qualquer item falha → exit 0 silent.

**Idempotência por property `provenance::` já set**: sub-tool walk + skip block já com `provenance::` (regex ancorado em ≥2 tabs cobre canonical property line per logseq-notes SD2; menção literal `provenance::` no texto do bullet não conta como property). Re-invocação só processa pendentes.

**Invariantes operacionais**:
- **Observability**: sub-tool captura exceções no top-level e loga append-only em `~/.claude/local/enrich-errors.log` (operador trunca via `truncate -s 0` quando crescer; sem rotação automática — YAGNI, file growth N=0 hoje).
- **Recovery atomic-write**: sub-tool constrói new_lines in-memory + single write no fim. Pre-write I/O failure → zero persistido (journal intacto); sucesso → all-or-nothing. Próxima invocação re-processa via idempotência. Sem "N-1 enriched + restante pendente" — sempre estado consistente.
- **Drift cumulativo via NER mismatch**: defer Faceta 3 `/wiki-lint`. Gatilho de probe automatizado: cardinalidade de pages enriquecidas ≥3 OR signal manual de drift emergir. Pré-shipping (N pequeno) o ganho marginal de health check cross-domínio não paga o overhead.
- **Race window com `/wiki-compile` paralelo**: hook é silencioso por design (Popen detached, DEVNULL); operador NÃO tem visibility de quando hook está running. Race é probabilística baixa — `/wiki-compile` é skill interactive de uso esporádico, hook dispara em Stop events específicos com gate de journal eligibility. Race materializa apenas quando ambos coincidem temporalmente E ambos escrevem na mesma região do journal. Gate `pgrep` cobre Logseq desktop mas não 2 processos meta-bridge concorrentes; revisita quando race materializar empiricamente (signal queue, não preventivo).

**Cross-refs**: Sub-decisão 3 § Adendo 2026-06-20 (produtor da property `closed::`); Sub-decisão 6 (precedente Stop hook + auto-gating — categoria distinta de soft notification preservada); Sub-decisão 7 (gate `pgrep` failure-closed write-side); Sub-decisão 11 (pattern orquestrador heurístico + sub-tool determinístico — replicado); [Adendo 2026-06-17 a ADR-013 do meta-system](https://github.com/fppfurtado/meta-system) (Camada 2a definida); [logseq-notes ADR-003](https://github.com/fppfurtado/logseq-notes) SD2 (schema `provenance::` Camada 2a — consumer side); roadmap `~/Projects/meta-system/docs/plans/roadmap-knowledge-layer-logseq-block-first.md` § Onda 5 (origem).

**Cross-ref forge**: issue [`#16`](../../../issues/16) (Onda 5 Faceta 1 — hook block-flow enrich, materializada nesta Sub-decisão).

### Sub-decisão 13 — Skill `/source-digest` + hook notifier (source-flow Camada 2b)

Materializa Onda 5 Faceta 2 do roadmap knowledge layer block-first do meta-system. Plugin ganha 4ª trajetória de hook bridging + 8ª skill `/source-digest`. Operacionaliza Camada 2b source-flow — digest LLM-driven de fontes externas (web clips do journal + arquivos do filesystem) em páginas estruturadas no grafo Logseq.

**Discriminação vs Sub-decisão 12 — notifier puro vs dispatcher**: SD12 usa Popen detached porque a substância determinística (`enrich.py`) pode executar standalone sem CC ativa. SD13 usa **notifier puro** (JSON `systemMessage` sem Popen) porque digest de fontes é **LLM-dependente**: extração de claims load-bearing, cross-refs a ADRs/entidades do grafo, e síntese de relevância pra knowledge layer requerem reasoning do modelo — não há sub-tool Python que capte isso deterministicamente. Hook sugere; operador decide quando invocar com CC ativa.

**Dois modos da skill `/source-digest`** (thin orchestrator markdown-only sem sub-tool — LLM-driven end-to-end):
- **Modo journal** (sem arg): detecta clips com `tags:: clippings` sem `digested::` no journal de hoje; extrai metadados (`title::`, `source::`, `author::`, `published::`, `description::`, bullets `* ` como conteúdo); cria `pages/<slug>-digested.md`; adiciona `digested:: [[<slug>-digested]]` ao bloco no journal.
- **Modo arquivo** (arg = path): lê arquivo via `Read` tool (integral para texto/PDFs ≤50p; truncado `pages: "1-50"` para PDFs >50p com marker explícito); cria `pages/sources/<slug>.md` (raw source page) + `pages/<slug>-digested.md`.

**Gate Logseq desktop obrigatório** (inverso de SD7 Adendo read-only): `/source-digest` é write (cria pages + edita journal); Logseq desktop deve estar aberto para o file watcher detectar novas pages e journal edit não dessincronizar com estado do desktop. `pgrep -xi logseq` zero → recusa fechada.

**Hook notifier `suggest_source_digest` — 2 gates simples**: (i) journal de hoje existe (`~/Notes/logseq/journals/YYYY_MM_DD.md`); (ii) journal tem ≥1 bloco top-level com `tags:: clippings` sem `digested::`. Qualquer gate falha → exit 0 silent. Ambos pass → `print(json.dumps({"systemMessage": "..."}))` sugerindo `/source-digest` (canonical CC 2.1.x non-blocking per SD6). Sem `pgrep` gate no hook — notifier puro não muta state; operador invoca skill quando conveniente.

**Namespace `pages/sources/`** — raw source pages com `provenance:: #source`: canonical Logseq page-ref `[[sources/<slug>]]`; seguem padrão dos arquivos pré-existentes (karpathy-wiki-gist, matuschak-evergreen-notes). Conteúdo extraído integral para ≤50p; truncado com `<!-- truncado: lido até p.50 de N -->` para PDFs >50p. Não é diretório do filesystem para deposit manual — é namespace de pages do grafo; arquivo fonte permanece no path original.

**Discriminação de exit messages no modo journal**: dois casos distintos têm mensagens discriminadas — "nenhum clip (`tags:: clippings`) no journal de hoje" (zero clips) vs "todos os clips de hoje já foram digeridos" (clips presentes mas todos com `digested::`). Sem colapso em mensagem única — operador precisa distinguir para rastrear estado do grafo.

**Invariantes operacionais**:
- **Idempotência modo arquivo**: slug inferido → check `pages/sources/<slug>.md` antes de criar; se existe → `AskUserQuestion` re-digerir ou sair.
- **Não mover arquivo fonte**: `pages/sources/<slug>.md` é representação extraída no grafo; arquivo fonte permanece no path original.
- **Não criar concept pages** (`provenance:: #concept`) — escopo é Camada 2b; Camada 4 é skill futura.
- **Cross-refs fabricados proibidos**: claims e cross-refs a ADRs/entidades do grafo só quando convergência verificável no conteúdo da source.

**Cross-refs**: Sub-decisão 6 (precedente hook notifier — categoria soft notification reutilizada; gates simplificados vs SD6 triplo-gate porque notifier não precisa de `.claude/local/` nem `pgrep`); Sub-decisão 7 (gate `pgrep` failure-closed write-side — replicado na skill, não no hook); Sub-decisão 12 (discriminação notifier vs dispatcher); [logseq-notes ADR-003](https://github.com/fppfurtado/logseq-notes) (schema `provenance::` Camada 2b — consumer side); roadmap `~/Projects/meta-system/docs/plans/roadmap-knowledge-layer-logseq-block-first.md` § Onda 5 Faceta 2 (origem).

**Cross-ref forge**: issue [`#18`](../../../issues/18) (Onda 5 Faceta 2 — sources digestion Camada 2b, materializada nesta Sub-decisão).

**Adendo (2026-06-23) — 3º modo URL via tools de fetch:** a enumeração "Dois modos da skill" acima ganha aditivamente um **terceiro modo**. **Modo URL** (arg casa `^https?://`): faz fetch da fonte (artigos via tool `WebFetch`; vídeos YouTube via `fetch_youtube_context` do plugin youtube-context — ver sub-caminho de vídeo abaixo), extrai o conteúdo em markdown, e cria `pages/sources/<slug>.md` (raw source page, `url:: <url>` no lugar de `file::`, `type:: web` ou `video`) + `pages/<slug>-digested.md` (digested page com **só** `source:: [[sources/<slug>]]` — paridade total com modo arquivo; a URL vive na raw source page, não é repetida na digested). Modo URL não edita o journal (sem bloco de origem; paridade com modo arquivo).

- **Sub-caminho de vídeo (YouTube):** host casa `youtube.com`/`youtu.be`/`m.youtube.com` → roteia para a tool MCP `fetch_youtube_context` (Gemini processa o vídeo nativo — transcript + visual), não WebFetch (que só pegaria metadata). Decisão emergiu da validação 2026-06-23 (dois `youtu.be` no corpus). Dependência soft no plugin youtube-context + `OPENROUTER_API_KEY`; ausente → recusa graciosa.
- **Redirects cross-host:** WebFetch retorna redirects cross-host em vez de segui-los (encurtadores, AMP, tracking); modo URL re-fetcha com a redirect URL (limite ~3 hops). Também emergiu da validação (`youtu.be` 303 → `youtube.com`).
- **Gate de falha graciosa (failure-closed):** página é recurso externo não-controlado. WebFetch erro/timeout/conteúdo vazio (incl. bot-block 403, rate-limit 429) → recusa fechada (`fetch falhou para <url> — página inacessível, bloqueio de bot (403) ou conteúdo JS-only`). URL malformada que passa o regex mas o WebFetch rejeita → mesma recusa (catch-all). Conteúdo parcial/paywall → prossegue + marker `<!-- truncado: paywall/fetch parcial -->`; nunca digest silenciosamente incompleto.
- **Fallback content-filter (escopo: modo URL):** o invariante "conteúdo extraído integral" é relido como "integral quando a content policy permite, senão estruturado-denso". Write verbatim bloqueado pela content filtering policy da API → reescrever estruturado-denso seção-por-seção. Formaliza para o modo URL o workaround antes só anotado em NOTES 2026-06-23 (modo arquivo). **Não generaliza ao modo arquivo nesta revisão** — generalização fica deferida ao gatilho ≥2 fontes confirmando o pattern.

**4 critérios ADR-034 (Adendo vs Sub-decisão nova):** (i) **decisão central da SD13 intacta** — digest LLM-driven sem sub-tool + gate Logseq obrigatório + hook notifier permanecem; modo URL produz o mesmo objeto (raw source + digested pages); (ii) **introduz I/O de rede via `WebFetch` — fronteira externa nova em superfície, mas NÃO nova categoria de substância nem novo write engine** (≠ SD12, promovida a Sub-decisão nova por novo write engine mediado por Popen); o gate de falha graciosa é o contrato que contém a fronteira; (iii) **sem restrição externa nova no pacote** — `WebFetch` é tool pré-existente do harness; o sub-caminho de vídeo usa `fetch_youtube_context` (plugin youtube-context já instalado) como **dependência soft com recusa graciosa** se ausente. Nenhuma dependência adicionada ao pacote Python nem sub-tool em `sub-tools/`; (iv) **refinamento aditivo** (3º modo + gate) **+ explicativo** (relê o invariante "integral"). Adendo cabe.

### Sub-decisão 14 — Contrato de reconciliação contra `#inbox` federado (view-only augment)

Skills `skills/journal-close/SKILL.md` (Step 2.5 + preview) e `skills/journal-review/SKILL.md` (heurística 1 `task-closure-by-context`). Materializa demanda do par coeso de issues forge **meta-system#42** (`/journal-close` → probe de tasks em aberto) + **meta-system#43** (`/journal-review` → reconciliação), triada via `/triage` 2026-06-23. Estende Sub-decisão 3 (`/journal-close` synthesis) e Sub-decisão 10 (`/journal-review`) — ambas reconciliam tasks por evidência; esta sub-decisão define como tratam o bucket `#inbox` materializado por `/inbox-aggregate` v0 (shipado 2026-06-22).

**Problema.** Pós-`/inbox-aggregate`, o `#inbox` é uma **view federada efêmera** (não persiste cross-dia) com 2 procedências discrimináveis pelo **source hashtag** que `/inbox-aggregate` injeta:
- **PKM-native** (`#pkm-native`, ou task nativa originada no próprio journal) → o marker no journal **é** a fonte da verdade (SSOT-in-place per [logseq-notes ADR-002 SD4](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md)).
- **Forge-synced** (`#<repo>` casando um repo `role: backlog: forge` conhecido) → **cópia, não-SSOT**: o SSOT é a issue no Forge; marcar DONE na cópia do `#inbox` **não fecha a issue**.

As 2 skills reconciliam tasks via modify-in-place do marker nativo — mecânica correta para PKM-native, **inaplicável** a cópias Forge-synced (a entry Forge-synced é estruturalmente idêntica a um TODO PKM, 1-tab marker, e já é capturada hoje pela regex `^\t- (TODO|DOING|WAITING)`).

**Decisão: augment (não replace).** O `#inbox` vira superfície consolidada de reconciliação intencional, com discriminação por source hashtag contra o set de repos `role: backlog: forge` conhecidos:
- **PKM-native** → SSOT-in-place (mecânica SD3/SD10 intacta — marker → DONE/transição in-place no journal).
- **Forge-synced** → **informacional** (reportado, sem auto-mutação): o `#inbox` permanece read-mostly per a decisão recém-shipada `inbox-agregador-fase-1` do meta-system (*"view read-mostly; mutação continua no canonical — UI do Forge, edits diretos no graph"*). Auto-fechar Forge issues a partir do journal contradiria essa decisão e mexeria na invariante SSOT-in-place — descartado em favor do augment (Ockham basilar, princípio 3 do ARCHITECTURE.md do meta-system).

**§ Regras de discriminação** (invariante central — a entry Forge-synced é estruturalmente idêntica a um TODO PKM; o único discriminador é a hashtag, daí regras explícitas; derivação `#<dirname>` igual à do `/inbox-aggregate`, [logseq-notes ADR-004](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-004-inbox-aggregator-schema.md) SD2):
- **Forge-synced** sse a entry carrega um `#<forge-repo>` casando o set de repos `role: backlog: forge` conhecidos (reforço: entries do `/inbox-aggregate` carregam também suffix `(#<iid>)` no título). **Qualquer** `#<forge-repo>` presente **domina** sobre `#pkm-native` coexistente (conservador contra mutação remota — resolve multi-hashtag).
- **PKM-native** (SSOT-in-place, transicionável) em **todos os outros casos** — incluindo entry `#inbox` **manual** sem hashtag de fonte. Racional: o risco de mutação remota só existe quando há repo Forge casado; ausência de repo-hashtag não é cópia (resolve colisão de nome — `#scripts` PKM sem repo-hashtag-conhecida-exata permanece PKM).
- **Default-safe**: o classificador Forge-synced é **estreito e explícito** (exige repo-hashtag conhecida); na dúvida, PKM-native. Como toda cópia Forge sempre carrega repo-hashtag + `(#N)`, nenhuma é transicionada por acidente — sem bloquear reconciliação de tasks PKM legítimas.

**Trade-off / Goodhart guard.** Read-mostly do `#inbox` é invariante herdada; v0 não muta canonical (Forge/graph) a partir do journal. A cutuca-de-close opcional (fechar a issue no Forge quando a sessão fecha uma entry Forge-synced) é deferida como incremento pós-v0 sob cutucada explícita (policy [ADR-058 § (e)](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-058-role-backlog-aceitar-forge.md) do toolkit) — v0 é informacional puro.

**Cross-refs:** Sub-decisão 3 (`/journal-close` synthesis — Step 2.5 ganha filtro de exclusão Forge-synced + linha informacional no preview) e Sub-decisão 10 (`/journal-review` — heurística 1 ganha finding informacional não-selecionável), ambas estendidas com nota apontando pra esta sub-decisão (cross-ref bidirecional); [logseq-notes ADR-002 SD4](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) (SSOT-in-place preservada) + [ADR-004](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-004-inbox-aggregator-schema.md) (schema `#inbox` + source hashtags); `inbox-agregador-fase-1` do meta-system (decisão read-mostly herdada); ADR-002 § Decisão 3 (matching-on-skill — discriminação por hashtag fica na skill; gatilho de promoção a sub-tool `discriminate_inbox_source()` + pytest se as regras ganharem ≥3 ramos com precedência/colisão materializados em código, per critério parsing-complexo do Adendo ADR-002 2026-06-16).

**Sub-decisão nova (não Adendo a SD3/SD10) per critério [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) do toolkit:** introduz **categoria nova** — contrato de uma skill × superfície federada não-SSOT, com regras de discriminação por procedência que nenhuma das 2 sub-decisões existentes contém. Toca 2 sub-decisões (lar único pro contrato cross-skill, com cross-ref bidirecional preservando navegabilidade) em vez de Adendo-gêmeo duplicado.

### Sub-decisão 15 — `/journal-review` heurística 8 `phantom-tag-glued` + extensão de scope para `pages/` (apply in-place mínimo)

Skill `skills/journal-review/SKILL.md` (`#### 2h`) + motor `meta_bridge/journal_review.py` (`detect_phantom_tags`/`emit_phantom_candidates`/`parse_phantom`/`apply_phantom`). Materializa issue forge **meta-bridge#35** (triada via `/triage` 2026-06-24, sessão `remote-control`). Estende Sub-decisão 10 (`/journal-review` detective-first) com a 8ª heurística.

**Problema.** Escrever `(... #tag)` em prosa free-form do grafo cola o `)` na hashtag — o Logseq parseia a tag incluindo o delimitador e materializa uma **phantom page** `#tag)` (nó de referência sem arquivo), poluindo busca e fragmentando backlinks (`#enriched)` separa o backlink do `#enriched` real consumido pelo dashboard `quality-score::`/`provenance::`). Causa raiz é prosa humana, **não** output de skill (skills emitem `- #domain` top-level, sem cola) — guard write-time não cobre. 7 ocorrências reais corrigidas manualmente na descoberta (todas `)`).

**Decisão.** Heurística detective nova (mesmo pattern CLI-detecta/skill-julga das 5-7), com 2 desvios deliberados das anteriores:
- **Detecção determinística no CLI** (regex `#[\w/-]*[a-zA-Z][\w/-]*[)\]}]` — `)`/`]`/`}`; namespaced `#a/b` coberto; **exige ≥1 letra** para excluir refs GitHub puramente-numéricas em prosa (`(#11)`, `(PR #83)`) — falso-positivo revelado no smoke contra o grafo real, sessão de execução 2026-06-24; `#[[...]]` fora de escopo pois `[` não está no charset → falso-negativo aceito; `;`/`,` deferidos, conservador). Judgment da skill é **leve** — high-precision mecânica, não exige leitura de conteúdo (≠ 2f/2g).
- **Scan estende para `pages/`** (full-dir recursivo, sem janela temporal) **além** dos journals da janela. Primeiro consumo de `pages/` como **fonte de scan** no `/journal-review` (as 7 heurísticas anteriores operam só sobre a janela de journals).
- **Apply in-place mínimo**: `#tag)` → `#tag )` (insere espaço antes do delimitador), **uniforme em prosa e `{{query}}`**. O espaço mata a phantom page sem reclassificar `#tag`→`[[tag]]` (preserva semântica de tag inclusive em queries). Decisão pós-design-review (F1/F5): forma mínima escolhida sobre a conversão idiomática `[[tag]])` para reduzir a superfície de write destrutivo.

**§ Dispensa de snapshot.** O apply cruza para `pages/` **in-place** — superfície destrutiva nova vs o fence forward-only/aditivo das heurísticas 5-7 (Adendo v0.4.0 § (d) + Adendo 2026-06-24 § Hygiene). Snapshot é dispensado mesmo assim: o fix é **single-char insertion idempotente e reversível** (o espaço quebra o re-match do regex → re-apply é no-op; reverter = remover o espaço), e o gate real é **preview-first + cherry-pick**. Raciocínio paralelo à SD10 § asymmetry da heurística 1 (write retroativo single-line atomic dispensa snapshot porque o canal de falha — matching errado — é capturado no preview).

**Sub-decisão nova (não Adendo a SD10) per critério [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) do toolkit:** o trio v2 (Adendo 2026-06-24) passou nos 4 critérios por ser "mais heurísticas, mesma superfície (journals), apply aditivo (Hygiene)". Esta heurística quebra **dois** desses eixos: (i) **forma/lugar de persistência muda** — apply destrutivo in-place em `pages/`, gatilho explícito de ADR; (ii) **superfície de scan nova** — `pages/` como fonte, não só journals. A decisão central da SD10 ("detective-first sobre janela configurável de **journals**") é tocada, não só refinada → Sub-decisão, não Adendo.

**Cross-refs:** Sub-decisão 10 (`/journal-review` — heurística 8 soma-se às 7; fence forward-only das 5-7 explicitamente **não** reivindicado por 2h, que declara superfície distinta); SD10 § asymmetry (precedente de apply in-place dispensando snapshot — heurística 1); ADR-002 § matching-on-skill (detecção determinística no CLI, judgment na skill); [logseq-notes ADR-002 SD4](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) (SSOT-in-place — o fix preserva o conteúdo, só insere espaço). Pytest cobre o substrato mecânico (19 cenários: detecção/parse/apply/idempotência/não-colisão) per critério parsing-complexo do Adendo ADR-002 2026-06-16.

### Sub-decisão 16 — Skill `/wiki-lint` (knowledge layer Camada 4 — health check cross-domain)

Materializa Onda 6 do roadmap knowledge layer block-first do meta-system. Plugin ganha 10ª skill `/wiki-lint` — o health check da knowledge layer. Homed em meta-bridge per ADR-008 (homing das skills da knowledge layer, declarado na Onda 1; confirmado, não reaberto) + ADR-016 (forma target-aware). Gate da Onda 6 (`≥3 domínios enriquecidos`) atingido — 3 pages `provenance:: #enriched` (meta-bridge, knowledge-layer, pragmatic-dev-toolkit).

**Forma: thin orchestrator LLM-driven, sem sub-tool Python** (precedente SD13 `/source-digest`). Supera o esboço original do corpo da issue [#19](../../../issues/19) ("orquestrador heurístico-semântica + sub-tool determinístico replica SD11+SD12"), revertido no kickoff triage de sequenciamento cross-repo (2026-06-24): os 2 checks distintos são **reasoning semântico cross-page, não parsing determinístico** — sem parte determinística isolável em sub-tool, ≡ critério SD13.

**Duas naturezas de trabalho (decisão de sequenciamento cross-repo — anti-duplicação):**
- **Topologia (consumida, não reimplementada):** orphans + gaps são métricas determinísticas que o CLI externo `kl-score` já calcula. `/wiki-lint` **consome** `kl-score score --format json` (`schema_version 1.1`: `.metrics.orphan_nodes.items[]` `{page,uuid,excerpt}`, `.metrics.gaps_detected.items[]`, `.filters_applied`) — não recomputa nem filtra topologia. A fonte de verdade determinística é o kl-score (repo separado); reimplementar duplicaria e divergiria (lição cross-módulo da Onda 5 — bug `#pje-2.1`).
- **Semântica (o valor distinto da skill):** 2 checks LLM cross-page sem isolável determinístico — **contradições** (claims que se contradizem entre pages, escopo `pages/*` `#enriched`/`#digested`, pareamento por entidade compartilhada, guard proposicional contra falso-positivo de vocabulário compartilhado per lição 2f journal-review) + **stale claims intra-graph v0** (claim cita `[[ADR/page]]` com `status::` superseded/archived ou property `superseded-by::`/`replaced-by::`). Stale **extra-graph** (claim vs código/estrutura do repo real) deferido — exige fonte de verdade externa.

**Output:** report markdown stdout (sempre) + page Logseq `pages/wiki-health.md` opcional (**flat** — não carimba o namespace `wiki/` reservado à futura `/wiki-distill`; semântica **snapshot/overwrite**, não append). **Gate `pgrep` invertido vs SD13:** o write exige Logseq **fechado** (evita clobber do desktop sobre o arquivo overwrite); aberto → pula o write, stdout preservado (não falha a skill). Distinto de SD13 (`/source-digest` exige Logseq aberto pro file watcher detectar pages novas) — aqui a page é overwrite de snapshot, não criação dependente de watcher.

**Gate kl-score failure-closed:** `command -v kl-score` é o único probe barato; a 1ª invocação real é a do consumo de topologia — exit ≠ 0 / JSON inválido / sem `--format json` → recusa fechada. Nunca health check parcial sobre topologia ausente.

**Cross-refs:** Sub-decisão 13 (precedente forma thin-orchestrator LLM-driven sem sub-tool; gate `pgrep` **contrastado** — SD13 exige Logseq aberto pro file watcher, aqui exige fechado pra evitar clobber do overwrite); Sub-decisão 11 § Adendo 2026-06-23 (escopo de varredura só `pages/*`, espelhado aqui; homing canonical das skills da knowledge layer); ADR-008 (homing meta-bridge); ADR-016 (forma target-aware); ADR-002 § Adendo 2026-06-24 (postura de dependência build-vs-adopt — aqui 3ª categoria: consumir CLI externo); kl-score `docs/decisions/ADR-001` § Adendo 2026-06-24 (contrato JSON `schema_version 1.1` consumido); roadmap `~/Projects/meta-system/docs/plans/roadmap-knowledge-layer-logseq-block-first.md` § Onda 6 (origem).

**Cross-ref forge:** issue [`#19`](../../../issues/19) (Onda 6 / Camada 4 `/wiki-lint`, materializada nesta Sub-decisão).

**4 critérios ADR-034 (Sub-decisão nova, não Adendo):** (i) **decisão central de SD10/SD13 intacta** — `/wiki-lint` não toca journal-review nem source-digest; é skill nova; (ii) **categoria nova justifica Sub-decisão própria** (paralelo a SD11/SD13) — health-check cross-page consumindo contrato cross-repo versionado é superfície que nenhuma sub-decisão existente cobre; (iii) **sem restrição externa nova no pacote** — kl-score é CLI externo consumido via subprocess (`kl-score score --format json`), **não** dep Python do `pyproject.toml` (3ª categoria de dependência — nem build nem pip-adopt; análoga à dep-soft de SD13 `WebFetch`/`fetch_youtube_context` com recusa graciosa via gate failure-closed); nenhum sub-tool em `sub-tools/`; (iv) **sem nova categoria de decisão** doutrinária — é materialização de skill no padrão estabelecido.

### Sub-decisão 17 — Reconciler faceta A: verify-state cross-store em load-time (skill `/reconcile` + hook + subcomando)

Materializa a **faceta A** de 3 do reconciler ([#42](https://github.com/fppfurtado/meta-bridge/issues/42), epic; decomposto em /triage 2026-06-26 nas facetas #46/#47/#48). O reconciler é o **ritual de abertura** de sessão (espelho do `/journal-close`, que é o fim-de-sessão): reusa o primitivo verify-state-before-materialize (pragmatic-dev-toolkit ADR-069, hoje só em materialize-time) em **load-time**, surfando inconsistências cross-store (Forge + annotations/NOTES + Journal) **antes de orientar**, pra não empurrar o operador a um item já resolvido. Filho meta-bridge do contrato de coerência cross-store (meta-system#54 / ADR-025); a faceta A **não** toca as regras dual-entry/SSOT de ADR-025 (essas são a faceta B, #47).

**Forma: skill `/reconcile` (11ª skill) + subcomando determinístico `mb reconcile-check` + hook SessionStart `suggest_reconcile.py` (5º hook bridging).** Decomposição mecânico/judgment (padrão SD1 / `inbox_aggregate`): o subcomando é **puramente determinístico** (parse journal/NOTES + match), recebe as issues fechadas via `--closed-issues` JSON; a **skill** orquestra o fetch forge (resolve `#<repo>` → forge+ref via cluster lookup `~/.mrconfig`/REPOS.md; `gh`/`glab`) + a apresentação editorial. Refinamento vs esboço do plano (subprocess `gh` no subcomando): o fetch forge mora na skill — core sem rede, testável; heterogeneidade gh-vs-glab + degradação graciosa (failure-**open**) vivem na skill.

**Read-only:** a faceta A surfa findings, **não muta** o grafo — sem gate `pgrep` (não há write). A escrita das reconciliações (marcar `DONE`, properties) é a faceta C (#48, via write-path HTTP ADR-003). 2 checks v0: `journal_forge_closed` (task aberta em bucket Forge-synced `#<repo>`/`#inbox` carregando `(#<iid>)` cuja issue está fechada; match por **iid** drift-proof) + `notes_encerrada` (entry NOTES com marcador `Encerrada YYYY-MM-DD` ancorado a início de bullet/linha).

**Hook gate-barato (precedente SD6 Adendo v0.2.0, não SD13):** `suggest_reconcile.py` é SessionStart com gate local sem rede (cwd casa REPOS.md owned/active + journal de hoje existe) → sugere `/reconcile`; a checagem cross-store real roda na skill. Mesma trajetória SessionStart cwd↔REPOS.md de SD6 — **aciona o gatilho de generalização** que SD6 Adendo deixou pendente para a 3ª materialização: o parser REPOS.md (`_load_owned_active`/`_derive_basename`) é extraído pra `hooks/_repos.py` compartilhado entre os 2 hooks SessionStart, em vez de re-derivado.

**Granularidade SD-no-catálogo vs ADR próprio:** a faceta A isolada é skill-shaped → cabe no catálogo ADR-001 como SD (padrão SD9/11/13/16). **Se** as facetas B/C trouxerem decisão estrutural de SSOT/dual-entry (B depende de ADR-025) ou de write-modality, o conceito reconciler pode ser promovido a ADR próprio então (simetria com ADR-003, irmão habilitador de #42) — SD17 deixa esse caminho aberto.

**Cross-refs:** Sub-decisão 14 (contrato `#inbox` — discriminação Forge-synced vs PKM-native reusada no check 1; o reconciler **generaliza** a reconciliação além do `#inbox`, que a faceta B amplia; mecânica de match exact-title/iid vem de `inbox_aggregate` / logseq-notes ADR-004, não de SD14); Sub-decisão 6 Adendo v0.2.0 (precedente do hook SessionStart + gatilho de generalização acionado); Sub-decisão 1 (decomposição mecânico/judgment); ADR-002 (subcomando `mb` determinístico; parsing-complexo → pytest); ADR-003 (write-path HTTP — substrato da faceta C, não usado em A); pragmatic-dev-toolkit ADR-069 (primitivo verify-state-before-materialize reusado em load-time); meta-system#54 / ADR-025 (contrato pai cross-store).

**Cross-ref forge:** issues [`#42`](https://github.com/fppfurtado/meta-bridge/issues/42) (epic reconciler), [`#46`](https://github.com/fppfurtado/meta-bridge/issues/46) (faceta A, materializada nesta SD); #47/#48 (facetas B/C, deferidas).

**4 critérios ADR-034 (Sub-decisão nova):** (i) **decisão central de SDs existentes intacta** — `/reconcile` é skill nova, não toca journal-close/review nem o `#inbox` aggregate; (ii) **categoria nova justifica SD própria** — ritual de abertura verify-state-at-load é superfície que nenhuma SD cobre (espelho do journal-close end-of-session); (iii) **sem restrição externa nova no pacote** — `gh`/`glab` consumidos pela skill (não pelo pacote); subcomando é stdlib + click, sem dep Python nova; (iv) **sem nova categoria doutrinária** — materialização de skill+hook+subcomando no padrão estabelecido (SD1 mecânico/judgment + SD6 hook SessionStart).

### Sub-decisão 18 — Reconciler faceta B: dedup cross-store read-only local-first (check `cross_store_dedup`)

Materializa a **faceta B** de 3 do reconciler ([#47](https://github.com/fppfurtado/meta-bridge/issues/47)), sobre o esqueleto de SD17. Materializa o componente **dedup cross-store** do contrato pai meta-system#54 / ADR-025: na abertura, surfar quando o **mesmo item de pendência está co-rastreado em ≥2 stores**, orientando ao SSOT canonical por domínio (Forge = code, Journal GTD = life, NOTES = scratch non-SSOT) — sem mutar.

**Forma: 3º check `cross_store_dedup` no subcomando `mb reconcile-check` + grupo de apresentação novo na skill `/reconcile` + pytest.** Sem skill/hook novo — estende os de SD17. Read-only (sem gate `pgrep`); a escrita/consolidação que muta é a faceta C (#48).

**Escopo v0 — read-only local-first (decidido em /triage 2026-06-26 + corte do design-review):** o check casa **só os 2 stores locais** (NOTES↔Journal) por título — exact + fallback fuzzy `rapidfuzz` `normalized_similarity ≥ 0.85`. `canonical_ssot` por **heurística barata derivada do próprio dado**: task com `(#<iid>)` → Forge (forge-synced, confirmado); sem iid → Journal (SSOT default; NOTES é scratch non-SSOT per ADR-054). **Nunca afirma Forge para item não-confirmado** (refinamento F7 do design-review — não orientar consolidação a store não-checado). Puramente local — sem forge/listing/cluster-lookup; roda mesmo offline.

**Deferido (corte deliberado):** as legs que tocam o Forge (`stale_cross_ref` NOTES→issue-fechada, `NOTES↔Forge` por iid) nasceriam quase no-op — o `closed_issues` de SD17 é montado grepando só o journal, e a forma da citação de iid em NOTES + a resolução de repo de um `#<iid>` nu não estão travadas; cortadas como a faceta A cortou o ex-Check 3 sub-suportado. O **dedup canônico Journal↔Forge** (item de vida nascido no Journal, invisível ao `/next` — a dor central de ADR-025) exige listar issues abertas, fora da disciplina targeted de SD17 — deferido a incremento de listing. O ex-Check 3 "reaparecer" (estado cross-sessão) e a escrita (faceta C) seguem deferidos.

**Classificação code-vs-life = critério deferido por ADR-025 aterrissando aqui (F6):** ADR-025 §1 fixa a regra de desempate (entrada canonical no domínio do resultado pretendido) mas **defere a mecânica de detecção aos filhos**. A heurística bucket→domínio derivada do iid **é** esse critério de classificação explicitado — e sua deriva (falso-positivo/negativo de SSOT) alimenta o **critério de erosão (iii)** de ADR-025 (zona cinzenta code-vs-life). O gap de listing (item que vazou Journal↔Forge sem reconciliação) alimenta o critério de erosão **(i)**, não o (iii) — loop pai→filho fechado.

**Promoção a ADR próprio NÃO disparou (cf. SD17/F8):** a faceta B v0 não trouxe decisão estrutural de SSOT/dual-entry — read-only, local, **sem persistência nova**, heurística barata derivada do dado. O caminho aberto por SD17 **permanece** para a faceta C (write-modality) ou um v1 da B com estado persistido ("reaparecer") / listing.

**Cross-refs:** Sub-decisão 17 (esqueleto skill+hook+subcomando que B estende; faceta A read-only); Sub-decisão 14 (contrato `#inbox`/bucket — discriminação de domínio reusada; mecânica de match exact-title vem de `inbox_aggregate`); ADR-002 (subcomando determinístico; parsing-complexo → pytest, 17 cenários novos — 15 diretos + 2 CLI — cobrindo match exact/fuzzy + borda do threshold + `canonical_ssot` por iid); meta-system#54 / ADR-025 (contrato pai — componente dedup + dual-entry + desempate code-vs-life que esta SD materializa parcialmente).

**Cross-ref forge:** issue [`#47`](https://github.com/fppfurtado/meta-bridge/issues/47) (faceta B, materializada nesta SD); #48 (faceta C, deferida).

**4 critérios ADR-034 (Sub-decisão nova):** (i) **decisão central de SDs intacta** — estende SD17 (mesma skill/subcomando), não toca outras SDs; (ii) **categoria justifica SD** — dedup cross-store é check novo sobre o ritual de abertura, no padrão de catálogo (SD9/11/13/16/17); (iii) **sem restrição externa nova no pacote** — reusa `rapidfuzz` (dep já adotada para naming-drift de `journal-review`), sem dep Python nova nem subprocess; (iv) **sem nova categoria doutrinária** — materialização no padrão SD17 (mecânico/judgment; read-only).

## Consequências

### Benefícios

- **15 sub-decisões cobrem 100% da mecânica das 9 skills + 4 hooks bridging** — execução fica tradução literal.
- **Critérios "prop mecânica vs humana", "stop event + marker", "exclusão de hoje da janela" são exhaustivos** — sem decisões emergentes que diluem invariantes.
- **Marker é contract público do toolkit** — qualquer plugin author pode reagir ao fim de `/run-plan` sem fork.
- **Frontmatter roles vazio é honesto**: skills não inventam dependências em papéis.
- **Sub-decisão 2 (literal append) elimina trade-off oculto**: template = schema + literal write é design previsível.
- **Separação correta de público vs pessoal**: este plugin assume Logseq + setup do operador; `pragmatic-dev-toolkit` permanece stack-agnostic.

### Trade-offs

- **Hook depende de `pragmatic-dev-toolkit` ≥ v2.13.0 estar instalado**: silent fail se ausente (gate 1 não encontra marker). Documentado em README.
- **`/journal-close` plan slug detection é frágil**: probe (i) variável env não existe hoje (gap em toolkit). Mitigação: campo opcional, operador preenche manual via Other.
- **Idempotência de `/init-logseq-project` falha se humano editar prop mecânica inline**: skill sobrescreve. Mitigação: critério exhaustivo (4 props), gatilho de revisão se padrão emergir.
- **`/weekly-review` parsing de headings é frágil a sintaxe atípica**: blocos sob `## Inbox` que usem formatação não-padrão. Mitigação: skill falha clara com path do file que confundiu; parser conservador.

### Limitações

- **Hook stale marker**: Stop dispara em TODO encerramento de turn (inclusive cancelamentos, errors). Hook script greps últimas 50 linhas — pode pegar marker antigo se transcript longo + plano fechou há horas. Mitigação: tail -n 50 cobre most cases.
- **Hardcode de paths**: `~/Notes/logseq/`, `~/.mrconfig`, `~/Projects/meta-system/REPOS.md` são fixos. Operador em outra máquina sem esses paths precisa fork + patch (documentado em CLAUDE.md). Não há gate `Path contract` ao estilo `pragmatic-dev-toolkit` — escopo personal-tooling.
- **`/init-logseq-project` em repo sem `.mrconfig` E sem REPOS.md cai no fallback prompt**: requer interação. Aceito.

### Mitigações

- **Stop event é o mecanismo correto pra Bridge hook** (probe confirmado em sessão 2026-05-28).
- **Race window do pgrep gate documentada em ADR-005 trade-offs**: mitigação via fix-forward.
- **Hardcode de paths é intencional**: scope personal-tooling deliberadamente fora de path contract.

## Alternativas consideradas

### Manter as 4 skills + hook no `pragmatic-dev-toolkit`

Original plano da Onda 4 do meta-sistema. Skills + hook landed em 7 commits no toolkit master local.

**Descarte**: mid-execução, operador detectou que o toolkit é plugin PÚBLICO sem dependência de Logseq + assume setup pessoal específico (templates do operador, paths hardcoded de `~/Notes/logseq/` e `~/Projects/meta-system/REPOS.md`). Toolkit users que não usem Logseq receberiam:
- `/journal-close` que recusa com "Template session-close.md ausente".
- `/init-logseq-project` que prompto cluster dos 9 do ADR-003 (taxonomia pessoal sem significado pra eles).
- `/weekly-review` que recusa com "journals dir ausente".
- Hook que silent-fails (auto-gating triplo protege user de ruído, mas presença no `What's inside` declara propósito que não bate).

Mais grave: `/note` foi extendido com `--local` flag inverttendo default (journal Logseq vs `.claude/local/NOTES.md`). **Breaking change** pra users existentes do toolkit que invocam `/note "..."` esperando NOTES.md per ADR-032 do toolkit.

Pivot pra plugin separado preserva substância das decisões mecânicas sem poluir o plugin público. 7 commits rollback-ados (commits transient; nada pushed).

### Move só 3 skills + hook; manter `/note` extension no toolkit

Compromisso: drop `/journal-close`, `/init-logseq-project`, `/weekly-review` do toolkit, mas manter `/note --local` extension.

**Descarte**: o problema principal de `/note` é breaking compat pra users do toolkit que NÃO usam Logseq. Manter a extension não resolve o issue. Pivot completo (todas as 4 skills + hook movem) é coerente.

### Plugin privado em vez de público

Repo `meta-bridge` privado no GitHub (similar a `meta-system`).

**Descarte**: público traz benefícios (exemplo concreto pra outros plugin authors de como compor com toolkit via marker canonical) sem custos (operador não tem segredos no repo; setup é nicho mas legível). README declara explicitamente que é personal-tooling, baixa expectativa de adoption externa.

### Generalize skills pra outros PKMs (Obsidian, Anytype, etc.)

Skills com `--pkm <type>` flag e backend per-PKM.

**Descarte**: scope creep. Operador usa Logseq; sem demand concreto pra outros PKMs. YAGNI. Gatilho de revisão: se ≥2 reports de usuários querendo Obsidian, reabre.

## Gatilhos de revisão

1. **Marker canonical `[PRAGMATIC: plan-done]` colide com outro plugin** ou toolkit muda formato: revisar Sub-decisão 6.
2. **Stop event API muda** (Claude Code release breaks compat): refazer probe.
3. **`/weekly-review` truncate ou janela 7d ficam restritivos**: ≥2 invocações truncam com >30 itens em 4 semanas → parametrizar via flags. *Resolvido empírico (2026-06-13)*: refactor profundo `/weekly-review` → `/journal-review` v0.3.0 materializou parametrização (`--days N` default 30 + `--from/--to`) + shift detective-first per Sub-decisão 10.
4. **AskUserQuestion cardinality 4 fica gargalo**: ≥3 chamadas seriadas em ≥2 invocações → negociar com toolkit core.
5. **Probe `pgrep -xi logseq` falha em ambiente do operador**: adicionar fallback `ps -A | grep -c logseq`. (Atualizado v0.1.2: gatilho original disparou parcialmente — case-sensitive `-x` quebrou em AppImage `Logseq` capital-L; resolvido via `-xi`. Reabre se `pgrep -xi` falhar por outro motivo.)
6. **`/init-logseq-project` idempotência quebra** (operador reporta perda de dado em ≥1 incidente): revisar critério "prop mecânica".
7. **Plan slug detection em `/journal-close` falha consistentemente**: probe (i)+(ii) retorna None em ≥3 invocações → refatorar `/run-plan` do toolkit pra expor variável env (adendo aqui).
8. **Hook stale marker materializa**: ≥2 reports de sugestão soft fora de contexto → implementar refinamento `~/.claude/.hook-last-marker-seen.json`.
9. **Skill nova emerge necessária na Bridge**: este ADR ganha sub-decisão.
10. **Paths absolutos hardcoded mudam**: revisar Sub-decisão 4 + CLAUDE.md.
11. **Project Template ganha prop mecânica nova**: adendo aqui estendendo a lista de 4 props.
12. **Demand concreto por outros PKMs** (≥2 reports): reabrir Alternativa "Generalize" + criar abstração mínima.
13. **Item 2 do BACKLOG (materialização CLI `mb`) executado**: template humano-amigável de `/journal-close` v0.3.0 pode mover pra módulo Python (Click/Typer) com flag `--reflective` vs `--mechanical`, colapsando v0.3.0 + degradação runbook em flag explícita. Adendo v0.4.0 (ou ADR novo se decisão central muda) materializa.

## Implementação

Materialização em Sessão 5 da Onda 4 do meta-sistema (2026-05-28), commit inicial deste plugin contendo:

- ADR-001 (este).
- 4 skills com SKILL.md em `skills/{journal-note,journal-close,init-logseq-project,weekly-review}/` (`/journal-load` adicionada em 2026-06-12 v0.4.0 per Sub-decisão 9; `/weekly-review` renomeada pra `/journal-review` em 2026-06-13 v0.3.0 da skill per Sub-decisão 10).
- Hook `hooks/suggest_journal_close.py` + binding `Stop` em `hooks/hooks.json`.
- Manifestos `.claude-plugin/{plugin.json,marketplace.json}` versão 0.1.0.
- README.md + CLAUDE.md + LICENSE + .gitignore.

Cross-refs cross-repos: `meta-system` ADR-005 + plano `onda-4-bridge.md` atualizados pra apontar pra este plugin (commit pós-pivot na Sessão 5).
