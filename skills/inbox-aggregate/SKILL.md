---
name: inbox-aggregate
description: Agrega tasks de repos Forge (TJPA GitLab) + tasks PKM-native com #inbox inline no bucket #inbox do journal de hoje
disable-model-invocation: false
---

# inbox-aggregate

Skill orquestrador per [ADR-001 meta-bridge](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 1 (bridge read-N-sources → write-to-logseq; análogo a `/wiki-compile`). View efêmera — cada invocação re-agrega; idempotência via dedup exact-match no sub-tool.

Schema canonical em [logseq-notes ADR-004](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-004-inbox-aggregator-schema.md) (3 sub-decisões: `#inbox` inline Papel 2a, hashtags de fonte inline `#<repo>`, query canonical simple-query). Sub-tool determinístico (parse + dedup + write) em `sub-tools/inbox_aggregate.py` per [ADR-002 Adendo](../../docs/decisions/ADR-002-materializacao-cli-mb.md) critério "parsing-complexo → pytest".

## Argumentos

Sem argumentos. Skill resolve repos e caminhos autonomamente.

```
/inbox-aggregate
```

## Passos

### 1. Gate pgrep — resultado salvo, não aborta aqui

Executar `pgrep -xi logseq`. Salvar resultado booleano `logseq_open`. **Não abortar** — Steps 2-4 são read-only e isentos do gate per [ADR-001 Sub-decisão 9](../../docs/decisions/ADR-001-skills-de-bridge.md) (race window não materializa em leitura concorrente). Gate bloqueia exclusivamente o write do Step 5.

### 2. Descobrir repos TJPA com remote GitLab

Varrer `~/Projects/tjpa/` procurando subdiretórios que são git repos com remote apontando para `gitlab-ca.tjpa.jus.br`. Para cada dir em `~/Projects/tjpa/`:

```bash
git -C ~/Projects/tjpa/<dir> remote -v 2>/dev/null | grep -q "gitlab-ca.tjpa.jus.br"
```

Exit 0 → repo Forge elegível. Derivar source hashtag: `#<dirname>` (e.g., `pje-2.1` → `#pje-2.1`).

Sem repos elegíveis encontrados → reportar aviso e prosseguir com `forge_map = {}`.

### 3. Fetch issues abertas por repo (read-only, isento do gate)

Para cada repo elegível do Step 2:

```bash
cd ~/Projects/tjpa/<dirname> && glab issue list --state opened --output json
```

Capturar output JSON. Falha de glab (exit não-0, `glab` ausente, problema de autenticação) → pular repo + registrar aviso no relatório final; não aborta skill.

Acumular em `forge_map`: `{"#pje-2.1": [<issues>], "#scripts-judiciais": [<issues>], ...}`.

### 4. Grep tasks PKM-native do journal de hoje (read-only, isento do gate)

Resolver path do journal de hoje:

```bash
date +%Y_%m_%d
```

→ `~/Notes/logseq/journals/<YYYY_MM_DD>.md`.

Journal ausente → `pkm_tasks = []` (dia inativo; prosseguir sem PKM tasks).

Journal presente → grep com regex canonical (per logseq-notes ADR-004 Sub-decisão 1):

```bash
grep -P '^\t*- (?:TODO|DOING|WAITING).*#inbox' ~/Notes/logseq/journals/<date>.md
```

Capturar linhas como `pkm_tasks` (lista de strings). Regex captura tasks com marker GTD em qualquer nível de indentação; NÃO captura `^- #inbox` top-level bucket sem marker (Papel 1 puro — filtrado naturalmente pela exigência de marker GTD).

Nota: o grep captura tasks de qualquer posição no journal, incluindo tasks já escritas dentro do bucket `#inbox` por rodadas anteriores. O sub-tool deduplica via exact-match contra os filhos já presentes no bucket — tasks repetidas são descartadas sem acumulação.

### 5. Gate write: invocar sub-tool OU dry-run report

**Se `logseq_open = true`:**

Reportar ao operador: tasks coletadas (`forge_map` counts + `pkm_tasks` count) + aviso:

```
Logseq desktop aberto — write bloqueado (ADR-001 Sub-decisão 7).
Feche Logseq e re-invoque /inbox-aggregate para persistir as tasks abaixo.
[lista prévia das tasks que seriam escritas]
```

Exit clean sem escrever no filesystem do graph.

**Se `logseq_open = false`:**

Invocar sub-tool determinístico:

```bash
python ${CLAUDE_PLUGIN_ROOT:-~/Projects/meta-bridge}/skills/inbox-aggregate/sub-tools/inbox_aggregate.py \
  --journal ~/Notes/logseq/journals/<date>.md \
  --forge-issues '<forge_map_json>' \
  --pkm-tasks '<pkm_tasks_json>'
```

Sub-tool exit não-0 → reportar stderr ao operador; exit clean.

Sub-tool exit 0 → capturar JSON de stdout (`tasks`, `count_forge`, `count_pkm`, `count_new`, `count_deduped`).

### 6. Reportar ao operador

```
Journal: ~/Notes/logseq/journals/<date>.md
Repos Forge: <N repos>  (<lista de repos elegíveis>)
Issues Forge carregadas: <count_forge>
Tasks PKM-native: <count_pkm>
Tasks novas escritas: <count_new>
Tasks deduplicadas (já presentes): <count_deduped>
```

Avisos de repos com falha glab (Step 3) listados abaixo se houver.

Exit clean.

## O que NÃO fazer

- **Não escrever no graph se Logseq desktop aberto** — gate failure-closed per [ADR-001 SD7](../../docs/decisions/ADR-001-skills-de-bridge.md); reads (glab fetch, grep, journal read) são isentos per SD9.
- **Não usar `gh` para repos TJPA** — todos os repos TJPA operam no GitLab `gitlab-ca.tjpa.jus.br`; CLI é `glab`, não `gh`.
- **Não adicionar repos fora de `~/Projects/tjpa/`** — scope v0 restrito aos repos TJPA migrados para Forge; repos secundários (pje2-web, mandamus-fluxos, pje-interfaces) adicionados quando migração Forge prosseguir.
- **Não criar page dedicada** — destino exclusivo é bucket `#inbox` do journal de hoje; page `pages/inbox-aggregated.md` YAGNI (decidido ADR-004 SD3).
- **Não adicionar `task-source::` property** — atribuição de fonte é hashtag inline `#<repo>` preferida a property block-level (per ADR-004 SD2 — ergonômica, idiomatic Logseq, query-friendly); `task-source::` reservada para extensão futura com URL/número exato.
- **Não fazer dedup semântico** — dedup v0 = exact-match normalizado (trim + lowercase); colisões Forge × PKM-native com variação de texto visíveis ao operador que consolida manualmente (YAGNI per ADR-004 SD3).
- **Não fechar/mover issues no Forge** — skill é read-only no Forge; mutações de issues continuam na UI do GitLab.
- **Não commit em logseq-notes** — repo de notes tem ciclo próprio (Git plugin do Logseq ou commits manuais).
