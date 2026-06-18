---
name: wiki-compile
description: Agrega blocos intra-graph (pages/* + journals/*) numa entity page enriquecida com seções canonical "Notas curadas" + "Sources digeridas" + "Síntese" preservando block-ref trail
disable-model-invocation: false
---

# wiki-compile

Skill orquestrador heurístico-semântica per [ADR-017 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-017-skills-orquestrador-fino-sub-tool-deterministico.md) § decomposição faceta ii. Substância heurístico-semântica (decisão de **o que** agregar — relevância dos blocos-source) vive aqui; substância determinística (find-or-create de section + literal append + dedup por conteúdo) delegada ao sub-tool `sub-tools/compile.py`.

Materializa Camada 3 (entity pages enriquecidas) do roadmap knowledge layer block-first per [Adendo 2026-06-17 ADR-013 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-013-adocao-knowledge-layer-destino-arquitetural-constelacao.md). Onda 2 v0 (manual disparado pelo operador); evolução pra semi-auto / auto deferida pra Ondas 3+.

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Adendo 2026-06-17 (`/wiki-compile` v0 estende escopo Logseq-local) e [`logseq-notes` ADR-003](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-003-knowledge-layer-schema-mecanico.md) (schema mecânico — property canonical `provenance::`, namespace `sources/`, properties subset v0).

## Argumentos

Dois flags obrigatórios.

```
/wiki-compile --entity <entity-name> --blocks <path:block-id,path:block-id,...>
```

- `--entity <entity-name>`: entity alvo (kebab-case lowercase). Ex: `knowledge-layer`, `princípios-fundamentais`. Skill resolve em `~/Notes/logseq/pages/<entity-name>.md`; cria se não existe.
- `--blocks <list>`: 1+ paths **intra-graph** de blocos-source separados por vírgula. Aceita 2 formatos:
  - `<path>:<block-id>` — bloco específico identificado por `id::` Logseq (formato canonical pra block-ref).
  - `<path>` — page inteira (skill agrega heurísticamente blocos canonical, não a page toda).

  Paths restritos a `~/Notes/logseq/pages/*` + `~/Notes/logseq/journals/*`. Paths fora desse scope → rejeita fechada com mensagem clara.

Args ausentes ou inválidos → recusa silenciosa com mensagem específica. Exit clean.

## Passos

### 1. Gate canonical `pgrep -xi logseq`

`pgrep -xi logseq` retorna processo ativo → recusa fechada com `Logseq desktop aberto — feche antes de wiki-compile (race window: ((block-ref)) bookkeeping pode dessincronizar)`. Exit clean.

Gate per [ADR-001 Sub-decisão 7](../../docs/decisions/ADR-001-skills-de-bridge.md) (failure-closed). Skill é write-heavy (file edits cumulativos na entity page); race com desktop reabriria a janela canonical mais larga que a do `/journal-note`.

### 2. Parse args + validate paths

- `--entity <name>`: extrair. Vazio → recusa com `--entity exige nome não-vazio (kebab-case lowercase)`.
- `--blocks <list>`: split por vírgula. Lista vazia → recusa com `--blocks exige ≥1 path intra-graph`.
- Para cada item:
  - Path resolve a `~/Notes/logseq/pages/*` ou `~/Notes/logseq/journals/*` → OK.
  - Path fora desse scope → recusa fechada com `fontes cross-repo exigem captura prévia via /journal-note no journal de hoje; path rejeitado: <path>`. Exit clean.
  - Formato `<path>:<block-id>` com `<block-id>` malformado (não UUID-like 8+ chars) → recusa com `block-id inválido em <path>:<block-id> — Logseq usa UUID 8+ chars`.

### 3. Find-or-create entity page

Entity page mora em `~/Notes/logseq/pages/<entity-name>.md`.

- Page **não existe**: criar com template canonical:

  ```
  provenance:: #enriched
  entities::

  ## Notas curadas

  ## Sources digeridas

  ## Síntese
  ```

  Operador preenche `entities::` depois (skill não infere — eixo heurístico-semântico).

- Page **existe**: ler. Verificar que as 3 seções canonical existem (`## Notas curadas`, `## Sources digeridas`, `## Síntese`); seção ausente → sub-tool cria (responsabilidade determinística). Page existente sem `provenance::` page-level → **NÃO mutar** properties existentes; agente reporta divergência ao operador e segue (operador decide se adiciona `provenance:: #enriched` post-hoc).

### 4. Decisão heurístico-semântica de o que agregar

Agente lê blocos-source apontados em `--blocks`:

- **Formato `<path>:<block-id>`**: ler page, localizar bloco com `id:: <block-id>`, captar conteúdo (linha do bullet + sub-bullets aninhados).
- **Formato `<path>` (page inteira)**: ler page; identificar blocos canonical (substância densa, baixa redundância vs entity page existente). Critério julgamento agente — **NÃO mecânico**.

Critérios de relevância semântica (julgamento agente, não checklist):

- Bloco carrega claim load-bearing canonical sobre a entidade alvo?
- Bloco tem substância densa (não eco do contexto / metadata-only / GTD-marker isolado)?
- Bloco não duplica conteúdo já presente na entity page (skill consulta seção "Notas curadas" existente antes de propor agregação)?

Blocos selecionados → preparar lista de `((block-id))` refs intra-graph com sub-bullet de trilha (`- fonte: journal/<data>` OR `- fonte: pages/<page>`).

### 5. Delega sub-tool determinístico pra agregação mecânica

Invocar sub-tool com 1 chamada por bloco selecionado pra seção "Notas curadas":

```bash
python ${CLAUDE_PLUGIN_ROOT:-~/Projects/meta-bridge}/skills/wiki-compile/sub-tools/compile.py \
  --entity-page ~/Notes/logseq/pages/<entity-name>.md \
  --section "Notas curadas" \
  --content '- {{embed ((<block-id>))}}
  - fonte: <fonte-trilha>'
```

Sub-tool determinístico:

1. **Find-or-create section**: lê entity page; se seção não existe, cria após page-level properties + linha em branco; preserva ordem canonical (`Notas curadas` → `Sources digeridas` → `Síntese`).
2. **Literal append**: append literal no fim da seção alvo (antes da próxima `## ` header ou EOF).
3. **Dedup por conteúdo**: probe via match exato do conteúdo-a-inserir na seção; presente → no-op (idempotência).

Sub-tool exit 0 → bloco agregado OR já presente (idempotência preservada). Exit não-0 → reportar stderr ao operador e parar.

### 6. Síntese (heurístico-semântica, ficar na skill)

Após agregação dos blocos via sub-tool, agente compõe seção `## Síntese` da entity page inline:

- 2-3 parágrafos sintéticos cobrindo os claims load-bearing presentes em "Notas curadas".
- Referenciar block-refs `((block-id))` quando substância caber (preserva trilha auditável).
- Operador audita pós-shipping per critério claim-ausência (cabe ao plano consumidor da skill definir).

Síntese **não vai pelo sub-tool** — substância é judgment agente, não append determinístico. Skill usa `Edit` tool diretamente pra inserir na seção `## Síntese`.

### 7. Reportar ao operador

Output formatado:

```
Entity page: ~/Notes/logseq/pages/<entity-name>.md
Blocos agregados: <N>
  - <block-id-1> (fonte: <trilha-1>) [agregado | já presente]
  - <block-id-2> (fonte: <trilha-2>) [agregado | já presente]
Síntese atualizada: <sim|não>
```

Exit clean.

## O que NÃO fazer

- **Não escrever no graph se Logseq desktop aberto** (gate canonical `pgrep -xi logseq`; per [ADR-001 SD7](../../docs/decisions/ADR-001-skills-de-bridge.md)). Write-heavy implica race window mais larga do que `/journal-note`.
- **Não inferir entity alvo do cwd** (pattern oposto a `/journal-note` que infere `--domain` do basename do repo). `--entity` é arg explícito do operador — knowledge layer cross-domínio independe de cwd da sessão.
- **Não classificar relevância por regex/heurística simples** — cabe ao agente julgar substância semântica; critérios em Passo 4 são guias de julgamento, não checklist mecanizável.
- **Não aceitar paths cross-repo** — constraint upstream de [meta-bridge ADR-001 SD2](../../docs/decisions/ADR-001-skills-de-bridge.md) (literal append, NÃO block-ref resolvido em runtime) + tese block-first do roadmap. Fontes externas exigem captura prévia via `/journal-note` no journal de hoje.
- **Não materializar concept pages** (`provenance:: #concept`) em v0 — deferido pra `/wiki-distill` Onda 3+ per Adendo ADR-013 e ADR-003 SD1 do logseq-notes.
- **Não confundir `type::` (identidade) com `provenance::` (ato editorial)** ao consultar entity page existente. Per [logseq-notes ADR-003 SD1](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-003-knowledge-layer-schema-mecanico.md) os 2 eixos são ortogonais; page pode carregar um, outro, ou ambos.
- **Não tocar properties page-level existentes** — se entity page já tem properties que o operador escolheu (`type::`, `status::`, etc.), preservar intactas. Skill só agrega substância nas 3 seções canonical + Síntese.
- **Não fazer commit em logseq-notes** — repo de notes tem ciclo próprio (Logseq Git plugin OR commits manuais do operador).
- **Não rewrite/remover `id::` de blocos** — invariante Logseq ([ADR-001 SD8](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-001-redesign-doctrine-unificada.md) entity-as-page pattern). Bloco sem `id::` materializado em path intra-graph → reportar, NÃO inferir/criar, segue com demais blocos. Operador volta ao Logseq desktop pra materializar `id::` manual (Cmd+E etc.).
