---
name: journal-review
description: Detective-first review com 8 heurísticas estruturais sobre janela configurável de journals (+ pages para phantom-tags); wizard GTD opt-in (sucessor de /weekly-review v0.2.0)
disable-model-invocation: false
---

# journal-review

Thin orchestrator do subcomando `mb journal-review` (CLI `meta-bridge`). Skill consome o **scan mecânico** do CLI (markers ativos + DONE-tasks + narrativas + inventário de buckets + **candidatos determinísticos do trio v2** em janela `--days N` + **candidatos phantom-tag** em journals da janela **e pages full-dir** — o CLI faz counting/Levenshtein/gap/regex, a skill aplica só o judgment semântico), aplica **8 heurísticas semânticas** detectivas, opera preview-first + cherry-pick, e re-invoca CLI em modo `--apply` com transições concretas.

Substância semântica (heurísticas, judgment, cherry-pick interpretation) é **heurístico-semântica** e **fica integralmente na skill**. CLI faz só scan + write engine.

Sucessor de `/weekly-review` v0.2.0. Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 10 e [ADR-002](../../docs/decisions/ADR-002-materializacao-cli-mb.md) § matching-on-skill.

Overlap conceitual com `/journal-close`: ambos fecham TODOs por evidência, mas eixos distintos — `/journal-close` confronta com **session context** (commits da sessão CC); `/journal-review` confronta com **conteúdo da janela inteira de journals** (correlação inter-journal). Complementares; idempotência natural via SSOT in-place de markers.

## Argumentos

```
/journal-review                    # default: --days 30 detective-only
/journal-review --days 7           # janela semanal
/journal-review --from 2026-05-01 --to 2026-05-31  # range arbitrário
/journal-review --interactive      # detective + wizard residual após
/journal-review --write-summary    # detective + bloco summary no journal de hoje
/journal-review --bucket-min-journals 1 --bucket-min-tasks 1  # reduz 2c (com OR, só zero findings se nenhum bucket tiver 0 tasks abertas)
/journal-review --cooccur-min-journals 3   # 2e: fusão só com co-occurrence ≥3 journals
/journal-review --namedrift-max-distance 1 # 2g: drift só com Levenshtein ≤1
/journal-review --rename-gap-journals 3    # 2f: rename só com gap ≥3 journals
```

- `--days N` ou `--from/--to`: passados ao CLI (validação lá; mensagens claras).
- `--interactive`: wizard residual GTD após análise detective. Default off.
- `--write-summary`: bloco `## Journal review` no journal de hoje. Default off.
- `--bucket-min-journals N`: override do threshold K da heurística 2c `bucket-underused`. Default aplica quando ausente (K=2).
- `--bucket-min-tasks N`: override do threshold M da heurística 2c `bucket-underused`. Default aplica quando ausente (M=2).
- `--zombie-days N`: override do threshold T da heurística 2b `task-zombie`. Default aplica quando ausente (T=21).
- `--emerging-min-mentions N`: override do threshold N da heurística 2d `bucket-emerging`. Default aplica quando ausente (N=4).
- `--cooccur-min-journals N`: threshold N da heurística 2e `bucket-co-occurrence`. **Flag CLI-level** (default N=2) — **passada ao CLI**, que conta os pares e emite candidatos.
- `--namedrift-max-distance D`: threshold D (Levenshtein) da heurística 2g `bucket-naming-drift`. **Flag CLI-level** (default D=2) — **passada ao CLI**, que computa Levenshtein e emite candidatos.
- `--rename-gap-journals G`: threshold G (gap mínimo entre A.last e A'.first) da heurística 2f `bucket-rename-implicit`. **Flag CLI-level** (default G=2) — **passada ao CLI**, que filtra sucessores por gap + órfãs.

## Passos

### 1. Invocar `mb journal-review` scan mode

`Bash mb journal-review [--days N | --from D1 --to D2] [--cooccur-min-journals N] [--namedrift-max-distance D] [--rename-gap-journals G]` → emite markdown estruturado em stdout com **4 seções base** (Active markers, DONE tasks, Narratives, Bucket inventory com `first`/`last`) + **3 seções de candidatos v2** geradas **deterministicamente pelo CLI** (`### Co-occurrence candidates`, `### Naming-drift candidates`, `### Rename-implicit candidates`, per ADR-001 SD10 Adendo 2026-06-24) + **1 seção `### Phantom-tag candidates`** (heurística 8, per SD15 — regex determinístico sobre journals da janela **e todas as pages**). As 3 flags de threshold do trio são **CLI-level** — o CLI faz o counting, o Levenshtein e o filtro de gap; a skill recebe candidatos e aplica só o **judgment semântico**.

Janela vazia → CLI reporta `nenhum journal encontrado` + exit 0 → skill termina.

CLI valida args (mutual exclusion `--days` vs `--from/--to`); skill repassa erros.

### 2. Análise detectiva (heurístico-semântico — fica na skill)

Skill consome scan output e aplica 8 heurísticas (1-2 apply task-level; 3-4 apply estrutural A2/B2; 5-7 apply Hygiene aditivo forward-only; 8 apply in-place mínimo em journals+pages):

#### 2a. Heurística 1 — `task-closure-by-context` (apply)

Pra cada marker ativo, confronta com DONE-tasks e narrativas **posteriores** na janela (ordem cronológica preservada por contrato do CLI). Match semântico + hint forte de cross-refs (`plan:`, `commit:`, `[[page]]`). Judgment conservador.

Finding: `(source-path, source-line, marker original → DONE)`.

**Filtro `#inbox` Forge-synced** (per [ADR-001 SD14](../../docs/decisions/ADR-001-skills-de-bridge.md) § Regras de discriminação). As entries Forge-synced do bucket `#inbox` (materializado por `/inbox-aggregate`) já são confrontadas como markers ativos (1-tab TODO) — adicionar **exclusão explícita**: classificar cada entry cujo bucket-pai é `#inbox` **antes** de gerar findings de transição:
- **Forge-synced** sse carrega `#<forge-repo>` casando o set de repos `role: backlog: forge` conhecidos (reforço: suffix `(#<iid>)` no título; qualquer `#<forge-repo>` presente **domina** `#pkm-native` coexistente) → **finding informacional** (categoria nova no preview, **não-selecionável** pra apply): `#inbox Forge-synced: <repo>#<N> "<título>" parece fechada na janela — verificar no Forge`. **Nunca** entra no payload `## Transitions` do Step 5.
- **PKM-native** (incl. entry `#inbox` **manual** sem hashtag de fonte; default conservador na ausência de repo-hashtag conhecida) → finding de transição normal (marker → DONE).

Entries fora do bucket `#inbox` seguem o fluxo normal de transição.

#### 2b. Heurística 2 — `task-zombie` (apply)

Pra cada marker ativo: idade > T dias (T=21 default, override via `--zombie-days N`) + zero DONE relacionado + zero referência em narrativa. Finding: archive (DONE) ou cancel (CANCELLED) — operador escolhe.

#### 2c. Heurística 3 — `bucket-underused` (apply A2 aditiva)

Pra cada bucket no inventário: aparece em < K journals (K=2 default, override via `--bucket-min-journals N`) OU < M tasks abertas (M=2 default, override via `--bucket-min-tasks N`).

**Apply A2 aditiva** (per ADR-001 SD10 Adendo v0.4.0): skill julga **categoria-page agregadora** via critério mecanizável: (i) ≥2 buckets compartilham **prefixo comum** (ex.: `tjpa-*`, `meta-*`) → categoria = prefixo; (ii) buckets compartilham **domínio semântico óbvio sem prefixo** (ex.: `#tjpa` + `#scripts-judiciais` + `#connector-pje-mandamus-tjpa` → `judiciario`) → categoria nomeada pelo agente; (iii) **ambíguo** (bucket isolado, sem família ou domínio claro) → fallback `archived-buckets` (catch-all). Operador override via cherry-pick em Step 3.

Finding emite `(bucket-name, categoria-page-proposta, refs cross-journals)`. Apply em `pages/<categoria>.md`: find-or-create + append entry com block-refs aos journals onde bucket aparece. **Journals históricos intactos** — SSOT in-place per ADR-002 SD4 logseq-notes preservado.

Naming canonical da categoria-page: kebab-case lowercase.

#### 2d. Heurística 4 — `bucket-emerging` (apply B2 forward-only)

Hashtag/conceito em narrativas (≥ N=4 menções default, override via `--emerging-min-mentions N`) que NÃO existe como bucket top-level.

**Apply B2 forward-only** (per ADR-001 SD10 Adendo v0.4.0): skill propõe **naming canonical** do bucket emergente (kebab-case lowercase + NFD-strip acentos PT-BR per ADR-002 SD3 do meta-system; ex.: "captação prévia" → `captacao-previa`). Finding emite `(canonical-name, origem-narrativa opcional)`. Apply no journal de hoje: find-or-create bucket top-level + sub-bullet `\t- (origem: <narrativa>)` opcional. **Sem rewrite retroativo** de menções históricas em narrativas — preserva progressão temporal (hashtag categoriza forward; menções anteriores em prosa foram intencionais sem categoria).

Naming sanitização é responsabilidade da skill — CLI consome literal sem re-sanitizar.

**Falsos-positivos heading-style** (ex.: `WAITING Próximos passos`): judgment filtra antes de emitir finding.

#### 2e. Heurística 5 — `bucket-co-occurrence` (apply Hygiene aditivo)

Per [ADR-001 SD10 Adendo 2026-06-24](../../docs/decisions/ADR-001-skills-de-bridge.md). Consome a seção `### Co-occurrence candidates` do scan — o CLI **já fez o counting** (par `#A #B | shared-journals: <count>`, só pares com count ≥ N). A skill aplica **só o judgment semântico**: a fusão A∪B faz sentido (buckets do mesmo domínio/tema)? Coocorrência alta sem afinidade (ex.: dois projetos paralelos ativos no mesmo período) → **descartar candidato**. Sobreviventes viram finding.

**Apply Hygiene** (forward-only): sugestão em `pages/bucket-hygiene.md` § Co-occurrence — a fusão de fato é **manual** (read-mostly).

#### 2f. Heurística 6 — `bucket-rename-implicit` (apply Hygiene aditivo)

Per [ADR-001 SD10 Adendo 2026-06-24](../../docs/decisions/ADR-001-skills-de-bridge.md). Consome a seção `### Rename-implicit candidates` do scan — o CLI **já fez o filtro mecânico** (bucket A com tasks órfãs + lista de `successors` que surgiram com gap ≥ G após A sumir): `#A | last: <date> | orphans: <refs> | successors: #X #Y`. A skill aplica **só o judgment semântico — e a partir do CONTEÚDO dos buckets, NÃO do nome**: dentre os `successors`, qual é o **rename plausível** de A? **Ler o conteúdo** do bucket A e dos `successors` no journal e avaliar *"é a MESMA obra/tópico continuado sob outro nome?"*. A similaridade é **semântica de conteúdo, não léxica nem de vocabulário de domínio** — `weekly-review → journal-review` tem Levenshtein grande mas é rename óbvio (por isso 2f não usa Levenshtein); **inversamente**, `#tjpa-pje` e `#connector-pje-mandamus-tjpa` compartilham vocabulário PJe/TJPA mas **não** são rename (um é sessão de diagnóstico VPN, o outro um repo de código).

**Guards conservadores (precisão > recall — falso-positivo de rename sugere fundir coisas distintas, pior que silêncio):**
- **Vocabulário de domínio compartilhado ≠ rename.** `pje`/`tjpa`/`meta` no nome **não basta** — exige sameness de conteúdo, não sobreposição de palavras.
- **Buckets de sessão pontual** (journal-close de uma sessão CC: um tópico diagnóstico/discussão que apareceu uma vez, com `## ...`/insights/`Direção que emerge`) **não** são projetos renomeáveis → descartar.
- **Na dúvida → descartar** (nenhum successor plausível). Não emitir finding por similaridade superficial.

Finding emite `(A, A' escolhido, tasks órfãs)`.

**Apply Hygiene** (forward-only): sugestão em § Rename-implicit. **Fence read-mostly crítico**: as tasks órfãs entram **só como evidência** (refs/page-refs) na sugestão — **nunca** como transição task-level (não vão pro `## Transitions`). O operador migra/fecha manual. (Junção com o apply task-level destrutivo das heurísticas 1-2: o trio v2 **não** cruza essa fronteira.)

#### 2g. Heurística 7 — `bucket-naming-drift` (apply Hygiene aditivo)

Per [ADR-001 SD10 Adendo 2026-06-24](../../docs/decisions/ADR-001-skills-de-bridge.md). Consome a seção `### Naming-drift candidates` do scan — o CLI **já computou Levenshtein** e filtrou pares com distância ≤ D, não-idênticos, **coexistindo na janela** (`#A #B | distance: <D>`). **Discriminação vs 2f garantida no CLI**: drift = coexistem (sobreposição temporal); rename-implicit = gap temporal — o mesmo par nunca aparece nas duas seções. A skill aplica **só o judgment leve**: são mesmo variantes do mesmo bucket (não dois buckets legitimamente próximos no nome)? + sugerir o **canonical** (o mais frequente/recente). Finding emite `(A, A', distância, canonical)`.

**Apply Hygiene** (forward-only): sugestão em § Naming-drift.

#### 2h. Heurística 8 — `phantom-tag-glued` (apply in-place mínimo)

Per [ADR-001 SD15](../../docs/decisions/ADR-001-skills-de-bridge.md). Consome a seção `### Phantom-tag candidates` do scan — o CLI **já fez a detecção determinística** (regex `#tag` colada a delimitador de enclosure `)`/`]`/`}` em journals da janela **e em todas as pages**): `<path>:<line> | <raw-match> | #<tag>`. Cada candidato é uma `#tag` colada que o Logseq parseia incluindo o delimitador → materializa uma **phantom page** (`#enriched)` etc.), poluindo busca e fragmentando backlinks.

A skill aplica **judgment leve** (≠ heurísticas 5-7, aqui não precisa ler conteúdo — detecção é high-precision mecânica): descartar apenas falso-positivo óbvio se houver (ex.: trecho literal de código/regex onde a cola é intencional). Sobreviventes viram finding `(path, line, raw-match)`.

**Escopo do regex** (per SD15): `#[\w/-]+` cobre tags namespaced (`#a/b`); `#[[tag com espaço]])` fica **fora de escopo** (falso-negativo aceito). Delimitadores `;`/`,` não cobertos (conservador).

**Apply in-place mínimo**: `#tag)` → `#tag )` (insere espaço antes do delimitador), **uniforme em prosa e dentro de `{{query}}`** — o espaço mata a phantom page sem reclassificar `#tag`→`[[tag]]` (preserva semântica de tag, inclusive em queries). Idempotente (o espaço quebra o re-match). **Cruza para `pages/` in-place** (superfície destrutiva nova vs o fence forward-only das heurísticas 5-7) — por isso o gate é preview-first + cherry-pick; o fix é single-char reversível.

**Análise vazia** (zero findings) → recusa silenciosa.

### 3. Preview-first via AskUserQuestion (skill mantém estado em conversation memory)

Skill apresenta findings agrupados por tipo + evidência inline em prosa. Findings das **8 heurísticas** entram no preview (heurísticas 1-2 apply task-level via marker change; heurísticas 3-4 apply estrutural via A2/B2 per ADR-001 SD10 Adendo v0.4.0; heurísticas 5-7 apply Hygiene aditivo via `## Hygiene` per ADR-001 SD10 Adendo 2026-06-24 — sugestões selecionáveis, forward-only; heurística 8 apply in-place mínimo via `## Phantom fixes` per SD15 — selecionável, espaço uniforme prosa/query). **Findings informacionais `#inbox` Forge-synced** (heurística 1, per [SD14](../../docs/decisions/ADR-001-skills-de-bridge.md)) aparecem **agrupados à parte, não-selecionáveis** pra apply (read-only por construção: **nenhuma das 3 opções do enum os transforma em transição** — `Aplicar tudo` e `Cherry-pick` os ignoram, `Cancelar` trivialmente não aplica nada; nunca entram no payload `## Transitions`). `AskUserQuestion` header `Findings`:
- `Aplicar tudo`.
- `Cherry-pick via Other` — operador descreve subset em prosa; skill interpreta.
- `Cancelar`.

**Dispatch por opção**:
- `Aplicar tudo` → transições task-level das heurísticas 1-2 + entries estruturais das heurísticas 3-4 + sugestões de higiene das heurísticas 5-7 + fixes phantom da heurística 8 entram no payload do Step 5.
- `Cherry-pick via Other` → skill interpreta seleção, monta subset (task-level, estrutural, hygiene e/ou phantom, qualquer combinação) — **excluindo sempre os findings informacionais `#inbox` Forge-synced, mesmo se o operador os descrever** (read-only por construção, per SD14); selecionadas entram no Step 5. **Cherry-pick com seleção vazia** (operador descreve "nenhuma" ou equivalente) → equivalente a `Cancelar`.
- `Cancelar` → pular Steps 5 e 6 do fluxo de heurísticas. **Se `--interactive` ativo e wizard residual (Step 4) gerou transições**, Step 5 ainda executa com payload restrito ao wizard (sem heurísticas 1-2 nem estrutural). Sem wizard → Step 5 não dispara.

Estado dos findings vive em conversation memory entre a apresentação e a invocação de apply. Skill traduz seleção em transições concretas (paths/linhas/before/after) + entries estruturais concretas (bucket/categoria-page/refs; canonical-name/origem) — **não passa IDs opacos pro CLI** (per F2 design-reviewer absorvido).

### 4. Wizard residual opt-in (`--interactive`)

Skill processa tasks abertas que **não** geraram finding nas heurísticas 1-2 via wizard linear (truncate 20/marker, batch de 4 perguntas por AskUserQuestion, 4 opções):
- `Manter aqui` — sem transição.
- `Próximo passo definido` (Other → descrição) — sem transição (operador anota manualmente depois).
- `Arquivar` — transição `TODO|DOING|WAITING → DONE` (ou `CANCELLED` se irrelevante).
- `Adiar próxima semana` — transição `TODO|DOING|WAITING → WAITING` preservando body (per ADR-001 Sub-decisão 5 Adendo v0.2.0).

Mecânica idêntica a `/weekly-review` v0.2.0. `--interactive` ausente → skip.

Transições do wizard residual (Arquivar/Adiar) entram no **mesmo payload** do Step 5, unificadas com transições das heurísticas 1-2.

### 5. Invocar `mb journal-review --apply` (CLI write engine)

**Apply task-level + estrutural + hygiene + phantom** unificados em chamada única. Compor payload contendo (a) transições task-level das heurísticas 1-2 confirmadas no Step 3 + (b) transições do wizard residual do Step 4 (se `--interactive` ativo) + (c) entries estruturais das heurísticas 3-4 confirmadas no Step 3 (per ADR-001 SD10 Adendo v0.4.0) + (d) sugestões de higiene das heurísticas 5-7 confirmadas no Step 3 (per Adendo 2026-06-24) + (e) fixes phantom da heurística 8 confirmados no Step 3 (per SD15). Chamada única ao CLI:

```
## Transitions

- <source-path>:<line> | \t- TODO X | \t- DONE X
- <source-path>:<line> | \t- WAITING Y | \t- DONE Y

## Structural

### Archived buckets
- <bucket-name> | <categoria-page> | <journal-path>:<line>;<journal-path>:<line>

### Emerging buckets
- <canonical-name> | <origem-narrativa-opcional>

## Hygiene

### Co-occurrence
- [[A]] ∪ [[B]] coocorrem em <N> journals — considerar fusão

### Rename-implicit
- [[A]] → [[A']] (tasks órfãs: [[<journal-date>]] ...) — verificar rename

### Naming-drift
- [[A]] ~ [[A']] (Levenshtein <D>) — canonical sugerido: <X>

## Phantom fixes

- <source-path>:<line> | <raw-match>
```

**Contrato do `## Phantom fixes`**: `<raw-match>` é o texto literal colado (ex.: `#enriched)`) — 1 pipe só, não colide com `TRANSITION_RE` (2 pipes). O CLI insere espaço antes do delimitador in-place (`#enriched)` → `#enriched )`), uniforme em prosa e `{{query}}`. Fail-soft: `raw-match` ausente na linha (drift/já-corrigido) → skip.

**Heading `## Transitions` é opcional** — CLI aceita transitions bullets top-level sem heading para backward compat de payload v0.3.0 (`## Transitions`-only legacy). Adicionar heading explícito é forma canonical v0.4.0+ para simetria com `## Structural`.

**Contrato forward-only do `## Hygiene`** (load-bearing): as sugestões usam page-refs `[[...]]` e **nunca** o shape `<path>:<linha> | <a> | <b>` de transição. O CLI parseia transições de **toda** linha do payload via `TRANSITION_RE` — uma sugestão de higiene com aquele shape casaria e viraria **write destrutivo num journal**. Page-refs `[[...]]` não colidem (sem `:linha | a | b`). As órfãs do rename-implicit entram como `[[journal-date]]` evidência, **não** como `path:line` transicionável.

`echo "$PAYLOAD" | mb journal-review --apply`. CLI aplica em ordem fixa: transitions primeiro (modify-in-place atomic, mesmo TRANSITION_RE + drift detection do `mb journal-close`); structural depois (A2 = append em `pages/<categoria>.md`; B2 = find-or-create bucket no journal de hoje); hygiene em seguida (append forward-only em `pages/bucket-hygiene.md`, idempotente); phantom por último (in-place mínimo em journals+pages, idempotente). Output: `transitions: X aplicadas` + `structural: A archived + B emerging` + `hygiene: K sugestões aplicadas (S skipped)` + `phantom: P fixes aplicados (S skipped)`.

Sem heurística selecionada via `Cherry-pick` → seção respectiva omitida do payload (vazia silente). Payload completamente vazio → tratado upstream em Step 3 dispatch (short-circuit; não chega aqui).

### 6. `--write-summary` opcional (skill compõe + invoca `mb journal-close` write)

**Ordering**: Step 6 executa **após** Step 5; usa as contagens reais reportadas pelo CLI (aplicados/skipped). Step 5 falha total → Step 6 ainda pode rodar com count vazio (operador decide). Re-invocação cria bullet duplicado — sem dedup automático pra summary (não tem `commit:` hash); operador edita manual se necessário.

`--write-summary` ativo → skill compõe bloco e pipe pra `mb journal-close` Append:

```
## Append

- #journal-review
	- ## Journal review — YYYY-MM-DD
		- Janela: <range> (<N> journals)
		- Heurística 1 (task-closure-by-context): <X aplicados, Y rejeitados>
		- Heurística 2 (task-zombie): <X aplicados, Y rejeitados>
		- Heurística 3 (bucket-underused): <A archived em pages/<categoria>.md>
		- Heurística 4 (bucket-emerging): <B emerging no journal de hoje>
```

Append no journal de hoje via CLI. Default off — curation é meta-operação invisível. O summary cobre **intencionalmente só as heurísticas 1-4** (transição task-level/estrutural); heurísticas 5-8 (Hygiene + phantom) são omitidas por design — apply aditivo/in-place sem narrativa de fechamento de task.

### 7. Reportar

Repassar output do `--apply` ao operador (transitions + structural + hygiene + phantom counts) + agregado de findings emitidos por heurística + wizard residual count (se `--interactive`). Em apply estrutural A2, mencionar page agregadora criada/atualizada; em B2, mencionar bucket emergente no journal de hoje; em phantom, mencionar quantos fixes in-place foram aplicados em journals/pages.

## O que NÃO fazer

- **Não duplicar substância de scan/apply** — vive em `meta_bridge.journal_review`.
- **Não criar snapshot defensivo XDG cache** — A2 aditiva (append em page agregadora) + B2 forward-only (find-or-create no journal de hoje) + Hygiene aditivo (append em `pages/bucket-hygiene.md`, heurísticas 5-7) são safe-by-construction, sem touch em journals históricos. Transitions task-level (heurísticas 1-2) usam modify-in-place atomic (TRANSITION_RE + drift detection do `mb journal-close`, idempotente single-line); também não precisam de snapshot. Phantom (heurística 8) é in-place cross-file (journals **e** pages) mas **recuperável** — fix single-char (`#tag )`), idempotente, reversível — portanto também dispensa snapshot. Snapshot só faria sentido se apply fosse destrutivo cross-file **e não-recuperável** (per ADR-001 SD10 Adendo v0.4.0 + SD15).
- Não propor finding em matches incertos — judgment conservador.
- Não modificar markers em sub-bullets (≥2 tabs) — prosa contextual.
- Não capturar `DONE`/`CANCELLED` como reconciliáveis — terminais (ADR-002 do logseq-notes Sub-decisão 4).
- Não escrever bloco summary por default — `--write-summary` é opt-in.
- Não anotar sub-bullet `→ closed via finding` — SSOT in-place.
- Não rodar wizard residual por default — `--interactive` é opt-in.
- Não derivar bucket do cwd — opera cross-files.
- Não inflar análise quando substância é magra — recusa silenciosa elegante.
- **Não fundir/renomear buckets em journals históricos** (heurísticas 5-7) — apply Hygiene é aditivo forward-only (sugestão em `pages/bucket-hygiene.md`); a curadoria de fato (fusão/rename) é **manual** (read-mostly, SD10 Adendo 2026-06-24).
- **Não transicionar tasks órfãs detectadas por `rename-implicit`** — entram **só como evidência** na sugestão de higiene, **nunca** como transição task-level (não cruzam pra `## Transitions`; junção com o apply destrutivo das heurísticas 1-2 fenced).
- **Não compor sugestões de `## Hygiene` com o shape `path:line | a | b`** — usa page-refs `[[...]]`; senão o CLI casaria `TRANSITION_RE` e faria write destrutivo num journal (contrato forward-only load-bearing).
- **Não aplicar transição em entry Forge-synced do `#inbox`** — cópia não-SSOT; o SSOT é a issue no Forge (ADR-001 SD14). Finding informacional não-selecionável; nunca entra em `## Transitions`.
- **Não reclassificar `#tag`→`[[tag]]` no fix phantom (heurística 8)** — o apply é mínimo (insere espaço `#tag )`), preserva semântica de tag inclusive em `{{query}}` (per SD15). Converter para page-ref mudaria o tipo do nó no grafo.
- **Não tentar cobrir `#[[tag com espaço]])` na heurística 8** — fora de escopo do regex (falso-negativo aceito, deferido a backlog). Delimitadores `;`/`,` idem (conservador `)`/`]`/`}`).
- Não fazer commit em logseq-notes.
- Não estender janela default — 30 dias é coerente com curation mensal.
- Não confundir com `/journal-close` v0.4.1 — eixos distintos (session context vs janela cross-journal).
- **Não passar IDs opacos pro CLI** (per F2 absorvido): skill mantém findings em conversation memory + envia paths/linhas/transições concretas.
