---
name: journal-note
description: Find-or-create hashtag-bucket no journal Logseq de hoje + append child task com marker GTD opcional
disable-model-invocation: false
---

# journal-note

Find-or-create bucket `- #<domínio>` top-level no journal `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md` + append child task com marker GTD nativo opcional. Materializa capture cross-domain com baixo atrito no graph per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) consumindo [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 1 (+ Adendo v0.2.0).

Skill opera **independente** de `CLAUDE.md` / role contract — usável em qualquer cwd. `/note` do `pragmatic-dev-toolkit` cobre o caso NOTES.md local per ADR-032 do toolkit; este skill é o complemento pra capture no graph.

## Argumentos

String com conteúdo da nota.

```
/journal-note "TODO investigar drive-sync bug"
/journal-note "DOING refactor do gate pgrep"
/journal-note "thought: gtd não precisa de schema rígido"
/journal-note "DONE removido pipx ensurepath commit:e56d666"
```

Sem argumento → recusa silenciosa com mensagem `/journal-note exige conteúdo; use /journal-note "<nota>"`. **Conteúdo final** vazio → recusa silenciosa, exit clean.

**"Conteúdo final"** = input após trim de whitespace E após remoção do marker prefix (se aplicável per Step 5). Casos cobertos: input só whitespace; input `TODO ` só com marker sem body. Recusar antes evita criar bullet semanticamente vazio (`- TODO ` sem descrição) no journal.

## Passos

### 1. Gate Logseq desktop (cheap-first)

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-note (skill escreve direto no filesystem do graph)`. Exit clean.

(Gate de git repo **removido** vs v0.1.x — cwd fora de git agora cai em prompt de domínio per Step 2.)

### 2. Derivar `#<domínio>`

Probe ordenado:

1. **`git rev-parse --show-toplevel`** retorna 0 → `<domínio> = $(basename <toplevel>)`. Skip Step 2.2.
2. **Fora de git repo** → `AskUserQuestion`:
   - header: `Domain`
   - options: `#thought`, `#draft`, `#idea`
   - "Other" livre — operador digita tag arbitrária. Sanitization aplicada: trim, lowercase, espaços/underscores → `-`, remoção de caracteres não-alfanuméricos exceto `-`. Ex: `Fiap Aula 3` → `fiap-aula-3` → `#fiap-aula-3`. Resultado sanitizado vira `<domínio>`.

Convention de naming definida em [ADR-002 do logseq-notes Sub-decisão 3](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md) (kebab-case lowercase; basename de Project Page quando repo; reservadas `#thought`/`#draft`/`#idea`/`#inbox` pra rascunhos).

**Nota sobre SSOT**: regra de sanitização inline acima **duplica intencionalmente** ADR-002 Sub-decisão 3 — spec executável tem prioridade sobre DRY doutrinário (agente runtime precisa de regra concreta, não link a seguir). Mudança requer sync nos 2 lugares.

### 3. Resolver journal path + bootstrap se ausente

- **Journal path**: `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md` (Logseq canonical filename com separator `_`, UTC date).
- Journal path **não existe** → ler `~/Notes/logseq/pages/daily-journal.md` como template body; copiar conteúdo (após linha de `template-including-parent:: false`) pro journal path. Template ausente (logseq-notes não setup) → criar arquivo vazio.

Template pós-Onda 4.5 é scaffold mínimo (1 bullet vazio) per ADR-002 Sub-decisão 1; não há headings GTD fixos.

### 4. Find-or-create bucket top-level `- #<domínio>`

Probe no journal path: existe linha top-level começando exatamente com `- #<domínio>` ou `- #<domínio> ` (com espaço — case de tag com sufixo Cluster Hub per ADR-002 Sub-decisão 7 opt-in)?

- **Existe** → identificar o offset (linha + indentation) do bucket; append child sob essa linha (Step 5).
- **Não existe** → append novo bucket top-level no fim do journal: `- #<domínio>` em linha própria. Em seguida append child sob ele (Step 5).

**Probe regex**: `^- #<domínio>($| )` — restringir a top-level (sem indentation prefix). Bucket idempotência: mesma tag não cria duplicado.

**Premissa single-tag**: probe assume bucket = single tag, opcionalmente seguida de espaço + sufixo (caso Cluster Hub opt-in de ADR-002 Sub-decisão 7: `- #dev-toolkit #drive-sync`). Bucket multi-tag arbitrário (3+ tags top-level) está fora de escopo; ADR-002 governa qualquer extensão.

### 5. Compose + append child task

Input do operador determina formato do child:

- **Marker prefix detect**: input começa com `TODO ` / `DOING ` / `WAITING ` / `DONE ` / `CANCELLED ` (uppercase exato, com espaço) → marker preservado no child block (formato Logseq nativo `\t- TODO <resto>`).
- **Sem marker prefix** → child plain (`\t- <conteúdo>`).
- **Sanitization de input**: nenhuma — operador escreve o que quiser; apenas a TAG (Step 2.2) é sanitizada, não o conteúdo do task.

**Sub-bullets mecânicos opcionais**: scan no input por 2 patterns extraíveis sem perder semântica:

- `commit:<hash>` (regex `\bcommit:([a-f0-9]{7,40})\b`) → captura hash, gera sub-bullet `\t\t- commit: <hash>`. Hash original permanece no body do task (inline). **Hash <7 chars não extrai** — alinhado com default git short hash; operador que digitar `commit:abc` (3 chars) verá token inline sem sub-bullet correspondente.
- `plan:<slug>` (regex `\bplan:([a-z0-9-]+)\b`) → captura slug, gera sub-bullet `\t\t- plan: <slug>`. Slug original permanece inline.

`[[<page>]]` cross-refs ficam **inline no body** (não extraídos pra sub-bullet — Logseq nativo já trata como backlink).

Sub-bullets free-form digitados pelo operador na própria linha de input não são parseados — vão pra prosa do body. Operador que quiser sub-bullet explícito invoca `/journal-note` separado pra cada (ou edita o journal manual depois).

**Append final**:

```
\t- [TODO|DOING|WAITING|DONE|CANCELLED]? <conteúdo>
\t\t- commit: <hash>     (se aplicável)
\t\t- plan: <slug>       (se aplicável)
```

Sob o bucket `- #<domínio>` identificado no Step 4.

### 6. Reportar

Journal path + bucket usado + marker (ou "plain") + sub-bullets mecânicos extraídos. Exit.

## O que NÃO fazer

- Não inferir/sintetizar conteúdo — gravar o body literal do operador. Apenas tag (Step 2.2) e sub-bullets mecânicos (Step 5) são derivados.
- Não tocar `.claude/local/NOTES.md` — esse store mora no `/note` do `pragmatic-dev-toolkit` (ADR-032 do toolkit). `/journal-note` e `/note` são canais independentes.
- Não auto-buscar contexto em journals de outros projetos — leitura cross-project é fenômeno conversacional via Read nativo do Claude com path absoluto.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não criar bucket sem antes probar (find-or-create gate idempotência).
- Não escrever se Logseq desktop aberto (pgrep gate). Failure-closed com mensagem clara.
- Não tenta usar `pidof`, `ps -A | grep` em vez de `pgrep -xi logseq` — canonical fixed per ADR-001 Sub-decisão 7.
- Não classificar sub-bullets por prefixo (yagni:/validação:/etc.) — convention ADR-006 § Decisão § 3 é prosa free-form, não schema. Captures mecânicos limitados a `commit:`/`plan:`.
- Não tentar agregar dados cross-bucket no momento do append — bucket é apenas localidade de escrita.
