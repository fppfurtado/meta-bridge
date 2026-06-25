---
name: wiki-lint
description: Health check cross-domain da knowledge layer (Camada 4) — consome a topologia do kl-score (orphans/gaps) e adiciona 2 checks semânticos LLM-driven (contradições cross-page + stale claims intra-graph), emitindo report no stdout + page Logseq opcional
disable-model-invocation: false
---

# wiki-lint

Skill thin orchestrator para **Camada 4 (health check)** do roadmap knowledge layer block-first do meta-system (Onda 6). LLM-driven, sem sub-tool Python (mesma invariante de `/source-digest`, SD13).

Divide o trabalho em duas naturezas:

- **Topologia (consumida, não reimplementada):** orphans e gaps são métricas determinísticas que o `kl-score` já calcula. `/wiki-lint` **consome** `kl-score score --format json` para essas — anti-duplicação (decisão de sequenciamento cross-repo do kickoff Onda 6).
- **Semântica (o valor distinto da skill):** 2 checks que exigem reasoning LLM cross-page e não cabem em código determinístico — **contradições** (claims que se contradizem entre pages) e **stale claims** (claims que referenciam estado intra-grafo obsoleto).

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 16. Contrato do kl-score consumido: kl-score `docs/decisions/ADR-001` § Adendo 2026-06-24 (`schema_version 1.1`).

## Argumentos

```
/wiki-lint            # roda o health check completo contra ~/Notes/logseq
```

Sem argumentos. (v0 não parametriza graph nem namespace — paths hardcoded per convenção do plugin.)

## Passos

### 1. Gate: kl-score disponível e runnable

`/wiki-lint` depende do CLI externo `kl-score` (v0.3.0+, modo `--format json`). Consumido via subprocess — **não** é dep Python do pacote `meta_bridge`.

O gate tem um único probe barato — `command -v kl-score`. A primeira invocação **real** do kl-score é o Passo 2 (não há dry-run duplo); exit ≠ 0, JSON inválido, ou ausência de `--format json` **lá** retroage a esta recusa fechada.

- `command -v kl-score` falha → recusa fechada:
  > `/wiki-lint` requer o CLI `kl-score` (v0.3.0+) instalado e no PATH — ausente. Instale via `pipx install -e <repo-kl-score>` e re-rode.

  Exit clean.
- `command -v` passa mas a invocação real do Passo 2 retorna exit ≠ 0 / JSON inválido / sem `--format json` (módulo quebrado, versão antiga) → recusa fechada com a stderr concreta + orientação de reinstalar/atualizar kl-score (v0.3.0+). Failure-closed: nunca produzir health check parcial silencioso sobre topologia ausente.

### 2. Topologia consumida (orphans + gaps via kl-score)

Rodar `kl-score score --format json --graph ~/Notes/logseq` e parsear o envelope `schema_version 1.1`:

- **orphans:** `.metrics.orphan_nodes.items[]` — cada item `{page, uuid, excerpt}` (`uuid` pode vir `null`; tratar graciosamente, usar `page` como identificador). `.metrics.orphan_nodes.count` para o sumário.
- **gaps:** `.metrics.gaps_detected.items[]` — strings (nomes de entidade referenciada sem page-alvo). `.metrics.gaps_detected.count` + `.metrics.gaps_detected.filters_applied` (reportar os filtros ativos pra contexto).
- Contexto auxiliar: `.metrics.link_count.total`, `.metrics.enrichment_rate`, `.pages_scanned`.

Surfar essas listas no report (Passo 4) **como vêm do kl-score** — `/wiki-lint` não recomputa nem filtra topologia (a fonte de verdade determinística é o kl-score; reimplementar duplicaria e divergiria — lição cross-módulo da Onda 5).

Esta é a **única** invocação real do kl-score (o gate do Passo 1 só fez `command -v`). Falha aqui (exit ≠ 0 / JSON inválido / sem `--format json`) → recusa fechada do Passo 1.

### 3. Check semântico — contradições (cross-page)

**Escopo v0:** varrer apenas pages em `~/Notes/logseq/pages/*` com `provenance:: #enriched` ou `provenance:: #digested`. Journals e blocos Camada 2a **fora do v0** (espelha o escopo de varredura de SD11 Adendo 2026-06-23).

**Claims** vivem em:
- pages enriquecidas: bullets bold sob `## Notas curadas` (+ gists sob `## Sources digeridas`).
- pages digested: bullets bold sob `## Claims load-bearing absorvidos`.

**Pareamento:** restringir a pares de pages que **compartilham ≥1 entidade** (interseção de `entities::`) — corta o custo O(N²) e reduz falso-positivo (pages sem entidade comum raramente falam da mesma coisa).

**Detecção:** reasoning LLM identificando **contradição proposicional** — página A afirma X, página B afirma ¬X sobre a **mesma proposição** (mesma entidade/decisão/fato). 

**Guard explícito contra falso-positivo** (lição 2f do `/journal-review` + bug `#pje-2.1` da Onda 5): vocabulário/domínio compartilhado **não é** contradição. Exigir oposição afirmação-vs-negação sobre a mesma proposição — não mera co-ocorrência de termos nem ênfases diferentes do mesmo fato. Na dúvida, **não** flagar (conservador; precisão > recall no v0).

Para cada contradição: registrar o par com evidência de cada lado (`<page>: "<claim>"`). **Não auto-resolver** — reportar para julgamento do operador.

### 4. Check semântico — stale claims (intra-graph, escopo v0)

**Escopo v0: apenas stale verificável dentro do grafo.** Detectar claims (mesmas pages/seções do Passo 3) que referenciam alvos intra-grafo obsoletos:

- claim cita `[[ADR-NNN]]`/`[[page]]` cujo alvo tem `status::` superseded/archived/deprecated, `provenance::` que indica obsolescência, ou foi movido para `archive/`.
- claim cita `[[X]]` cujo alvo carrega property explícita de supersessão (`superseded-by::`/`replaced-by::`) apontando pra outro page — sinal mecânico no alvo, não julgamento de prosa livre.

**Fora do v0 (deferido):** stale **extra-graph** — claim sobre código/estrutura do repo real que divergiu. Exige fonte de verdade externa (o repo), não coberto no v0; registrado como pendência de evolução.

Conservador: flag com justificativa (qual alvo, por que stale), operador julga. Não auto-editar claims.

### 5. Output — report stdout + page opcional

**Sempre:** emitir report markdown no stdout, agrupado:

```
# wiki-lint — health check (<N> pages scanned)

## Topologia (kl-score)
- orphans: <count> — <page> · <page> · ...
- gaps: <count> — <entidade> · <entidade> · ... (filtros: <filters_applied>)
- link_count: <total> | enrichment_rate: <rate>

## Contradições (semântico)
- <pageA>: "<claim>" ⨯ <pageB>: "<claim>" — <por que se contradizem>
[ou] _(nenhuma detectada)_

## Stale claims (semântico, intra-graph)
- <page>: "<claim>" — alvo <[[X]]> <razão da staleness>
[ou] _(nenhuma detectada)_
```

**Opcional — page Logseq `pages/wiki-health.md`** (flat; o namespace `wiki/` fica reservado à futura `/wiki-distill`):

- **Gate `pgrep -xi logseq`:** o write de page exige Logseq **fechado** (evita clobber do desktop sobre o arquivo). Logseq aberto → **pular** o write da page (não falhar a skill); reportar `página wiki-health.md não escrita — feche o Logseq e re-rode pra materializar; report acima preservado`. O stdout é sempre a saída garantida.
- Logseq fechado → escrever `~/Notes/logseq/pages/wiki-health.md` com semântica **snapshot/overwrite** (find-or-create + replace do conteúdo — health report reflete o estado atual, não histórico append-only):

```
provenance:: #health
generated:: <hoje YYYY-MM-DD>

# wiki-health

<mesmo conteúdo do report stdout>
```

### 6. Reportar

Confirmar o que rodou:
```
wiki-lint: <N> pages scanned
topologia: <orphans> orphans, <gaps> gaps (kl-score)
semântico: <C> contradições, <S> stale claims
page: ~/Notes/logseq/pages/wiki-health.md  [escrita | pulada (Logseq aberto)]
```

## O que NÃO fazer

- **Não reimplementar orphans/gaps** — são consumidos do `kl-score score --format json` (anti-duplicação; o kl-score é a fonte de verdade determinística da topologia). Reabrir só se o contrato JSON do kl-score deixar de cobrir o necessário.
- **Não criar sub-tool Python** — os 2 checks são reasoning semântico cross-page, sem parte determinística isolável (invariante SD13; o lado determinístico já vive no kl-score, repo separado).
- **Não falhar silenciosamente quando kl-score está indisponível** — gate failure-closed (Passo 1): recusa fechada com orientação, nunca health check parcial sobre topologia ausente.
- **Não flagar contradição por vocabulário compartilhado** — exigir oposição proposicional (afirmação vs negação da mesma proposição), não co-ocorrência de termos do mesmo domínio (lição 2f journal-review / `#pje-2.1`). Conservador: na dúvida, não flagar.
- **Não fazer stale extra-graph no v0** — comparar claims contra código/estrutura do repo real é fora-de-escopo (exige fonte externa); v0 cobre só stale intra-grafo (refs a ADR/page superseded/archived).
- **Não varrer journals nem blocos Camada 2a** — escopo v0 é `pages/*` `#enriched`/`#digested`.
- **Não auto-corrigir nem auto-resolver** claims (contradição ou stale) — só reportar com evidência; o julgamento e a edição são do operador.
- **Não escrever fora de `pages/wiki-health.md`** — não carimbar o namespace `wiki/` (reservado à `/wiki-distill`); não criar concept pages (`provenance:: #concept`, Camada 4 distill).
- **Não escrever a page com Logseq aberto** — gate pgrep pula o write (evita clobber); stdout é a saída garantida.
