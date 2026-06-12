# ADR-001: Skills de Bridge — `/journal-note`, `/journal-close`, `/init-logseq-project`, `/weekly-review` + hook `suggest_journal_close`

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

**Oito sub-decisões mecânicas** que materializam as 4 skills + 1 hook da Bridge.

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
- **Derivação de domínio**: probe ordenado novo (cwd git repo → basename; senão → AskUserQuestion enum com sanitização kebab-case lowercase no caminho Other per ADR-002 Sub-decisão 3 — mitigação direta do risco de hashtag proliferation citado em ADR-006 § Limitações).
- **Find-or-create bucket top-level `- #<domínio>`**: substitui o append flat de v0.1.x. Probe regex `^- #<domínio>($| )` restringe a top-level. Idempotente: mesma tag no mesmo dia reusa o bucket existente.
- **Format do child**: input com marker prefix uppercase (`TODO `/`DOING `/`WAITING `/`DONE `/`CANCELLED `) preserva como marker do bloco Logseq nativo per ADR-002 Sub-decisão 4; senão child plain.
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

### Sub-decisão 5 — `/weekly-review` parsing via headings em journals

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

- **Coleta via grep de markers nativos**: substitui parsing de headings `## Inbox`/`## Doing`/`## Waiting` (que saíram do daily-journal template per ADR-002 Sub-decisão 1) por grep de markers Logseq nativos `TODO`/`DOING`/`WAITING` em journals. ADR-002 Sub-decisão 4 estabelece markers nativos como SSOT de estado GTD; Sub-decisão 5 aqui adapta consumer.
- **Regex restrita a top-level** (1-tab indent, filhas diretas de bucket `- #<domínio>`): `^\t- (TODO|DOING|WAITING) (.*)$` per F1 do /triage do plano `onda-4-5-journal-retrofit-gtd`. Markers em sub-bullets (≥2 tabs) ficam como prosa contextual per ADR-006 § Decisão § 3 mental model (sub-bullets = prosa não-parsed).
- **Markers `DONE` e `CANCELLED` não capturados**: terminais por design (per ADR-002 Sub-decisão 4) — não entram no backlog do wizard. Audit retrospectivo via leitura direta do journal.
- **Sub-bullets do task apresentados como contexto não-parsed** (per ADR-006 § Decisão § 3 contract): wizard mostra sub-bullets pro operador classificar mas NÃO infere taxonomia por prefixo. Apresentação como prosa em prelúdio à AskUserQuestion.
- **Bucket de origem preservado em decisão `defer`**: task move pra journal de destino sob `- #<domínio>` mesmo do source. Find-or-create do bucket no destino paralelo a `/journal-note` Step 4.
- **Archive via mudança de marker (não property)**: decisão `archive` muda marker do task no source de `TODO`/`DOING`/`WAITING` pra terminal escolhido (`DONE` ou `CANCELLED`). Substitui adicção de property `archived:: true` da v0.1.x. Razão: per ADR-002 Sub-decisão 4, markers são SSOT; property `archived::` é pra page-level (ADR-001 deste logseq-notes Sub-decisão 7), não block-level.
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

### Sub-decisão 7 — `pgrep` semantics

Probe canonical antes de qualquer write no `~/Notes/logseq/`:

```bash
pgrep -xi logseq
```

- `-x` exige match exato do nome do processo (não substring).
- `-i` torna o match case-insensitive — necessário porque o AppImage do Logseq registra o binário como `Logseq` (capital L), não `logseq`. Sem `-i`, gate retorna falso-negativo (não detecta desktop aberto) e quebra failure-closed.
- Retorna pid(s) se existe; retorna não-zero se ausente.
- Truthy (desktop aberto) → skill recusa com `Logseq desktop aberto — feche antes de executar /<skill>`.

Aplicado a `/journal-note`, `/journal-close`, `/init-logseq-project`, `/weekly-review`.

Substituir por `pidof`, `ps -A | grep`, ou outras variantes **não aceito**. Razão: portability declarada (Linux/macOS; `pgrep` está em coreutils baseline).

**Race window** entre probe e write: milissegundos de ordem (probe → write em mesmo Bash subprocess; não medido empiricamente). Fix-forward via undo do Logseq se materializar.

#### Adendo (2026-05-28) — case-insensitive correction

v0.1.0/0.1.1 declararam canonical `pgrep -x logseq` (case-sensitive). Validação manual da Onda 4 do meta-system (Sessão 6) detectou que o processo real do AppImage Logseq aparece como `Logseq` em `pgrep` — gate retornava falso-negativo com desktop aberto, quebrando a invariante failure-closed que toda a Camada 3 depende. Bug afetava 4 skills + hook (5 arquivos). Fix em v0.1.2: `-x` → `-xi`. Sem ADR novo: refinamento mecânico, sem mudança de critério (probe canonical permanece `pgrep`; portability ainda baseline; aplicação ainda nas 4 skills).

#### Adendo (2026-06-12) — Gate aplica somente onde há side-effect

Sub-decisão 9 introduz `/journal-load`, primeira skill read-only do plugin — Read integral ou bloco-de-bucket dos journals na janela, sem write no graph. Race window que motivou o gate `pgrep -xi logseq` **não materializa em leitura concorrente**: Logseq desktop aberto não corrompe filesystem da leitura externa; pode haver delta no buffer não-flushed do desktop, mas isso vira "ligeiramente stale", não corruption.

Critério canonical refinado: gate aplica somente onde há side-effect no graph. As 4 skills write (`/journal-note`, `/journal-close`, `/init-logseq-project`, `/weekly-review`) mantêm `pgrep -xi logseq` failure-closed; skills read-only (`/journal-load` agora, futuras read-only) ficam isentas.

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
| `/weekly-review` | _(roles ausentes)_ |
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

4. Surface o conteúdo extraído em texto agrupado por data, ordem cronológica reversa (mais recente primeiro):
   ```
   ## Journal YYYY-MM-DD (~/Notes/logseq/journals/<date>.md)
   <conteúdo extraído literal>

   ## Journal YYYY-MM-DD (~/Notes/logseq/journals/<date>.md)
   <conteúdo extraído literal>
   ```
   Output direto no response stream — CC carrega o conteúdo na working memory, disponível para reasoning subsequente na sessão. Sem síntese, sem comentário editorial — load context é primitiva, não interpretação.

5. Reporta sumário pós-output (1-2 linhas): `<M de N journals lidos na janela [hoje-N, hoje]>` + bucket aplicado (se houver).

**Edge cases:**

- Janela inteira sem journals existentes → recusa silenciosa com `nenhum journal encontrado na janela [<hoje-N>, <hoje>]`.
- Janela inteira com `--bucket` mas sem matches em nenhum journal → recusa silenciosa com `bucket #<hashtag> ausente na janela [<hoje-N>, <hoje>]`.
- `--bucket` com hashtag inexistente no histórico não detectado em parse-time; só na fase de matching (recusa silenciosa acima).
- N grande (ex.: `--days 90`) sem `--bucket` pode floodar context window. Aceito sem cap — escolha do operador; `--bucket` é a mitigação canonical pra janelas amplas.

**Skill name `journal-load`** vs alternativas (`journal-read`, `journal-context`, `load-journal`): coerente com o par `journal-note` (append) + `journal-close` (write final). Verbo `load` carrega semântica de "trazer para working memory" mais clara que `read` (sugere display passivo).

**Cross-skill semantics**: `/journal-load` é independente das 4 skills existentes. Não compartilha probe-de-janela com `/weekly-review` (purpose distinto — load context vs classify GTD); não exige ordem com `/journal-note` (read-only não corrompe writes pendentes); pode ser invocada em qualquer ponto da sessão (default = hoje captura state corrente).

## Consequências

### Benefícios

- **8 sub-decisões cobrem 100% da mecânica das 4 skills + hook** — execução fica tradução literal.
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
3. **`/weekly-review` truncate ou janela 7d ficam restritivos**: ≥2 invocações truncam com >30 itens em 4 semanas → parametrizar via flags.
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
- 4 skills com SKILL.md em `skills/{journal-note,journal-close,init-logseq-project,weekly-review}/`.
- Hook `hooks/suggest_journal_close.py` + binding `Stop` em `hooks/hooks.json`.
- Manifestos `.claude-plugin/{plugin.json,marketplace.json}` versão 0.1.0.
- README.md + CLAUDE.md + LICENSE + .gitignore.

Cross-refs cross-repos: `meta-system` ADR-005 + plano `onda-4-bridge.md` atualizados pra apontar pra este plugin (commit pós-pivot na Sessão 5).
