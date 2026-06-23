---
name: enrich-blocks
description: Enriquece sub-bullets em buckets do journal de hoje com properties Camada 2a (provenance:: + entities::) via matching contra Project Pages canonical — fallback manual ao hook automático suggest_enrich_blocks.py
disable-model-invocation: false
---

# enrich-blocks

Skill orquestrador heurístico-semântica per [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 12 (hook block-flow enrich pós-`/journal-close`). Substância heurístico-semântica (LLM judgment sobre mention substantiva vs ruído incidental + preview-first) vive aqui; substância determinística (find blocks sem `provenance::`, append properties, write idempotente atomic) delegada ao sub-tool `sub-tools/enrich.py`.

Materializa Camada 2a Enriched Blocks per [logseq-notes ADR-003](https://github.com/fppfurtado/logseq-notes) SD2. Onda 5 Faceta 1 do roadmap knowledge layer block-first (substância em meta-system).

Skill é o **fallback manual** ao hook automático `hooks/suggest_enrich_blocks.py` (Stop event, dispatch background detached). Hook usa matching literal mention via sub-tool direto; skill adiciona LLM judgment + preview-first quando operador quer revisar decisões antes do dispatch.

## Argumentos

Sem argumentos. Skill processa journal de hoje.

```
/enrich-blocks
```

## Passos

### 1. Gate canonical `pgrep -xi logseq`

`pgrep -xi logseq` retorna processo ativo (case-insensitive — AppImage registra `Logseq` capital L) → recusa fechada com `Logseq desktop aberto — feche antes de /enrich-blocks (race window: write concorrente pode corromper property region)`. Exit clean.

Gate per [ADR-001 Sub-decisão 7](../../docs/decisions/ADR-001-skills-de-bridge.md) (failure-closed). Skill é write-heavy.

### 2. Read journal de hoje

`~/Notes/logseq/journals/YYYY_MM_DD.md` (local TZ date per [SD1 Adendo v0.2.1](../../docs/decisions/ADR-001-skills-de-bridge.md)). Journal ausente → recusa silenciosa com `journal de hoje ausente — nada a enriquecer`. Exit clean.

### 3. Identificar sub-bullets candidatos

Para cada bucket top-level `- #<bucket>`, walk sub-bullets `\t- ...`. Sub-bullets sem `provenance::` em property region (indented ≥2 tabs sob o sub-bullet) entram na lista de candidatos. Sub-bullets já com `provenance::` saem da consideração (idempotência via sub-tool).

Sem candidatos → recusa silenciosa com `nenhum sub-bullet pendente de enrichment hoje`. Exit clean.

### 4. LLM judgment de mention substantiva (substância heurística)

Listar Project Pages canonical em `~/Notes/logseq/pages/*.md` — filtradas por presença de `repo-path::` no conteúdo (discriminante das props mecânicas escritas por `mb init-project` per ADR-001 SD4; basename = nome de entidade per ADR-005 do meta-system convention).

Para cada candidato, identificar:
- **Mentions literais**: basename presente no texto do sub-bullet OR page-link `[[<basename>]]` inline.
- **Substantividade do mention**: o sub-bullet **discute** a entidade (sujeito/objeto da ação) ou só **referencia incidentalmente** (passing context, nota cross-ref incidental)? LLM judgment **conservador** — incerteza → não enriquecer (mesma postura editorial de SD3 Step 3b).

Resultado: lista de pares `(sub-bullet, [entities matched])` filtrada por judgment.

### 5. Preview informativo via AskUserQuestion (VIEW-only)

Apresentar prosa estruturada: lista de candidatos selecionados pelo Step 4 com entities propostas (formato `<bucket> :: <sub-bullet preview> → entities:: [[X]] [[Y]]`).

`AskUserQuestion` header `Enrich`:
- `Confirma + dispatch sub-tool` — invoca sub-tool determinístico (Step 6).
- `Cancela` — recusa silenciosa. Exit clean.

**Preview é VIEW-only**: operador VÊ o que o sub-tool vai considerar (filtrado pelo LLM judgment do Step 4) e pode cancelar, mas não edita o set. Substância: sub-tool re-aplica matching literal independente; LLM judgment da skill é heurística informativa de "valeria enriquecer este?" — sub-tool decide o que escrever via lógica determinística. Se operador discorda de candidato específico, cancela tudo; refinement de NER vive na Faceta 3 `/wiki-lint`.

### 6. Invocar sub-tool determinístico

`python3 ${CLAUDE_PLUGIN_ROOT}/skills/enrich-blocks/sub-tools/enrich.py --journal-today`.

Sub-tool re-aplica matching literal (mesma lógica do hook automático) e escreve atomic. Pode incluir mentions literais que LLM judgment do Step 4 não destacou (mention sem judgment substantivo) — drift pequeno entre preview e write esperado por design; capturado pela Faceta 3 `/wiki-lint` quando materializar (cardinalidade pages ≥3).

Reportar output: `enriched: N, skipped (already): M`.

## O que NÃO fazer

- Não executar com Logseq desktop aberto — race window de write concorrente per SD7.
- Não enriquecer sub-bullets fora de buckets top-level (nota livre, properties page-level) — escopo SD12 é block-level dentro de buckets.
- Não duplicar mecânica de write (idempotência, parse de property region) — vive integralmente no sub-tool.
- Não fazer NER complexo (Levenshtein, fuzzy, coref resolution) — defer Faceta 3 `/wiki-lint` quando signal real emergir (cardinalidade pages ≥3).
- Não modificar properties `provenance::` já set — read-only; respeito ao operador-curated state.
- Não escrever em journals diferentes do de hoje — `--journal-today` é único entrypoint manual da skill (single canonical path).
- Não dispatcher background como o hook faz — skill é interactive, dispatch sync com preview-first.
- Não sintetizar conteúdo (rewrite do sub-bullet, summary) — apenas append de properties no header do bloco.
