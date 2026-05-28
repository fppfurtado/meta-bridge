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
   - **Journal path**: `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md` (Logseq canonical com separator `_`, UTC date).
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
5. Append no `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md` sob seção `## Notes` (regex strict `^- ## Notes` — top-level, zero tab; ausência → warning loud + append no fim).
6. Reporta path tocado + bullets count.

Falha clara se `session-close.md` ausente (`Template session-close.md ausente em ~/Notes/logseq/pages/ — feature requer setup do graph`).

**Adendo 2026-05-28 (primeiro uso real)** — duas mecânicas refinadas:

(a) **Regex `^- ## Notes` (zero tab)**: SKILL original tinha `^\t- ## Notes` (1 tab). Primeiro uso real falhou — auto-apply do Logseq via `template-including-parent:: false` E mecânica de `/journal-note` (Sub-decisão 1 step 6) ambos produzem headings top-level (`- ## <heading>`, sem indent). Regex strict atualizada matche formato canonical. Análogo aplicado em Sub-decisão 5 (regex `^- ## Inbox/Doing/Waiting`).

(b) **Synthesis-then-confirm** em vez de interview puro: SKILL original pedia operator descrever Decisões + Follow-ups do zero via AskUserQuestion Other. Operator flagou friction: agente que executa skill TEM acesso a session context — deveria sintetizar rascunhos e pedir confirmação em vez de interview. Topic continua candidate-based (já era). Decisões + Follow-ups viram draft-then-confirm (3 opções: Confirma rascunho / Edita via Other / Sem — limpar). Razão: reduz friction (operator não re-articula coisas já registradas em commits/conversation) e aproveita context disponível ao agente runtime.

Adendo per [ADR-034](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/docs/decisions/ADR-034-criterio-adendo-vs-novo-adr-refinamento-doutrinal.md) critério (todos 4 satisfeitos: decisão central intacta — /journal-close ainda sintetiza sessão em bloco no journal; sem nova categoria; sem restrição externa; caráter explicativo — refinamento de mecânica). Não-trivializa Topic (segue candidate-based via Other override).

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
   - Sequência: (i) `awk -v p="[$REPO_PATH]" '$0==p,/^\[/' $MRCONFIG_PATH | grep -m1 "^tags = "` → cluster/subcluster direto (match literal evita injeção de regex); (ii) parse `REPOS_MD_PATH` por basename do repo; (iii) AskUserQuestion `Cluster` enum com 9 opções de ADR-003 do meta-system.
4. Lê `CLAUDE.md` + `README.md` do cwd (até primeiro `##` OU EOF, max 200 chars). Ambos ausentes/sem-corpo → `description` = vazio (sem populate, sem warning).
5. Resolve Project Page path: `~/Notes/logseq/pages/<basename>.md`.
   - **Ausente**: cria preenchendo `Project Template.md` body. Props (`type:: #project`, `cluster::`, `subcluster::`, `status:: #active`, `repo-path::`, `repo-host::`) + seções (`## Last journal entries`, `## Follow-ups` vazia, `## Decisões locais` vazia).
   - **Presente**: atualização cirúrgica — sobrescreve apenas linhas com props mecânicas (regex `^\s*(cluster|subcluster|repo-path|repo-host)::\s*`). Linhas não-encontradas → adicionar na **ordem canonical** (cluster, subcluster, repo-path, repo-host) após primeira prop existente. Preserva `status::`, blocos sob `## Follow-ups`, `## Decisões locais`, e qualquer prop humana adicional.

**Critério "prop mecânica"**: 4 props fixas exhaustivo. Extensão futura: nova prop mecânica no `Project Template.md` exige adendo neste ADR estendendo a lista.

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
4. Wizard iterativo de classificação. Skill **acumula decisões em memória**; edits no graph aplicam **somente após** Step 5 compor o bloco semanal (atomic-ish — crash mid-wizard = zero side-effect). 4 decisões: `keep`/`next_step` (Other → descrição)/`archive`/`defer` (move pra journal de próxima segunda `date -u -d 'next Monday'`, preservando heading de origem).
5. Aplicar edits batch + compor bloco semanal **literal** seguindo schema `weekly-review.md` (substituição de `<inbox-blocks>`/`<doing-blocks>`/`<waiting-blocks>` com listas formatadas por sufixo de decisão). Append no journal de hoje. Date placeholder `<% today %>` → `$(date -u +%Y-%m-%d)` (UTC alinhado).
6. Reporta totais + distribuição de classificações.

### Sub-decisão 6 — Hook `suggest_journal_close` (Stop event)

Hook `hooks/suggest_journal_close.py` + binding `Stop` event em `hooks/hooks.json`.

Mecânica: hook recebe stdin JSON com `session_id`, `transcript_path`, `cwd`, `hook_event_name`. Auto-gating triplo:

1. Marker `[PRAGMATIC: plan-done]` em `tail -n 50 <transcript_path>` (signal de `/run-plan` do `pragmatic-dev-toolkit` terminou; marker é contract público emitido pelo toolkit ≥ v2.13.0 commit `b8989c2`).
2. `<cwd>/.claude/local/` exists (signal de uso do toolkit no projeto).
3. `~/Notes/logseq/` exists AND `pgrep -xi logseq` retorna não-zero (desktop fechado — pode escrever no graph sem race).

Todos os 3 → print mensagem soft em stderr: `💡 Considere /journal-close pra sintetizar a sessão no journal de hoje.` Qualquer gate falha → exit 0 silente.

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

### Sub-decisão 8 — AskUserQuestion cardinality + frontmatter roles

**Cardinalidade max 4 perguntas** por chamada `AskUserQuestion` per [pragmatic-dev-toolkit CLAUDE.md](https://github.com/fppfurtado/pragmatic-dev-toolkit/blob/main/CLAUDE.md) → AskUserQuestion mechanics.

**Frontmatter roles**:

| Skill | `roles.required` | `roles.informational` |
|---|---|---|
| `/journal-note` | _(roles ausentes — skill não consome papéis canonical)_ |
| `/journal-close` | _(roles ausentes)_ |
| `/init-logseq-project` | _(roles ausentes)_ |
| `/weekly-review` | _(roles ausentes)_ |

Skills da Bridge **não consomem papéis canonical do toolkit** (Resolution protocol per ADR-003 do toolkit, aplicado vazio). Consomem 2 paths absolutos hardcoded fora do path contract — `~/.mrconfig` e `~/Projects/meta-system/REPOS.md` — plus filesystem do graph (`~/Notes/logseq/`). Mudança desses paths exige adendo neste ADR.

Implicação: skills da Bridge **não traversam Resolution protocol step 3** (operador-prompt). Cutucada de descoberta do toolkit **não aplica** — mesmo padrão de `/note` no toolkit (ADR-032).

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

## Implementação

Materialização em Sessão 5 da Onda 4 do meta-sistema (2026-05-28), commit inicial deste plugin contendo:

- ADR-001 (este).
- 4 skills com SKILL.md em `skills/{journal-note,journal-close,init-logseq-project,weekly-review}/`.
- Hook `hooks/suggest_journal_close.py` + binding `Stop` em `hooks/hooks.json`.
- Manifestos `.claude-plugin/{plugin.json,marketplace.json}` versão 0.1.0.
- README.md + CLAUDE.md + LICENSE + .gitignore.

Cross-refs cross-repos: `meta-system` ADR-005 + plano `onda-4-bridge.md` atualizados pra apontar pra este plugin (commit pós-pivot na Sessão 5).
