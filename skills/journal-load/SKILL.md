---
name: journal-load
description: Carrega conteúdo de journals Logseq na sessão CC (read-only) — default journal de hoje; flags --days N retroativo + --bucket #<hashtag>
disable-model-invocation: false
---

# journal-load

Read-only bridge skill. Carrega conteúdo de journals Logseq (`~/Notes/logseq/journals/`) na working memory da sessão CC. Default = journal de hoje, integral. Flag `--days N` estende janela retroativa; `--bucket #<hashtag>` restringe a um bucket específico.

Complemento ao par `journal-note` (append) + `journal-close` (write final) — fecha a simetria read-write do bridge.

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 9. Adendo (2026-06-12) a Sub-decisão 7 isenta read-only do gate `pgrep -xi logseq`.

Skill **não consome papéis canonical do toolkit** (Resolution protocol per ADR-003 do `pragmatic-dev-toolkit`, aplicado vazio). Cutucada de descoberta **não aplica**.

## Argumentos

Dois flags opcionais, mutuamente compatíveis. Sem args → default = journal de hoje, integral.

```
/journal-load                                  # journal de hoje, integral
/journal-load --days 7                         # últimos 7 dias + hoje, integral
/journal-load --bucket #meta-bridge            # journal de hoje, só bucket meta-bridge
/journal-load --days 30 --bucket #tjpa-tools   # 30 dias retroativos, só bucket tjpa-tools
```

- `--days N`: inteiro N ≥ 0. Janela = [hoje-N, hoje] inclusive (N+1 dias). N < 0 ou não-inteiro → recusa com `--days exige N >= 0`.
- `--bucket <hashtag>`: hashtag aceita com ou sem `#` prefix (`#meta-bridge` ou `meta-bridge`). Sanitização kebab-case lowercase aplicada (trim, lowercase, espaços/underscores → `-`, remoção de não-alfanuméricos exceto `-`) per convention de [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 1 Adendo v0.2.0.

## Passos

### 1. Sem gate Logseq desktop

Skill **read-only** — Adendo (2026-06-12) a [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 7 isenta read-only do gate `pgrep -xi logseq`. Race window não materializa em leitura concorrente; pior caso é conteúdo ligeiramente stale (último write do desktop não persistiu em disco).

Gate de git repo **não aplica** — operador invoca de qualquer cwd; `--bucket` é hashtag literal explicitada, não derivada de basename.

### 2. Parse args

- `--days N`: extrair N como inteiro. N inválido (não-numérico, negativo) → recusa com `--days exige N >= 0`. Exit clean.
- `--bucket <hashtag>`: extrair string, strip leading `#` se presente, aplicar sanitização kebab-case lowercase. Resultado vazio → recusa com `--bucket exige hashtag não-vazia`. Exit clean.
- Args ausentes → defaults: `N=0`, `bucket=None`.

### 3. Resolve paths dos journals na janela

**Journals dir ausente** (`~/Notes/logseq/journals/`): recusa com `Logseq journals dir ausente em ~/Notes/logseq/journals/ — graph não configurado`. Exit clean.

Gerar lista de datas:

```bash
for i in $(seq 0 N); do
  date -d "$i days ago" +%Y_%m_%d
done
```

Cada item → path `~/Notes/logseq/journals/<date>.md`. Local TZ alinhado per Adendo v0.2.1 a [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 1 (consumer da convergência cross-plugin).

Paths individuais ausentes na janela → silent skip (dia inativo é comportamento esperado).

**Nenhum journal existente na janela** (todos os paths ausentes) → recusa silenciosa com `nenhum journal encontrado na janela [<hoje-N>, <hoje>]`. Exit clean.

### 4. Read filemask

**Sem `--bucket`**: para cada journal existente na janela, usar Read tool. Conteúdo integral entra na working memory.

**Com `--bucket <hashtag>`**: para cada journal existente, Read + extrair APENAS o bloco do bucket:

- **Match de abertura**: regex `^- #<hashtag>($| )` — top-level, zero tab. Análogo ao probe de bucket em `/journal-note` Step 4 (Sub-decisão 1 Adendo v0.2.0).
- **Terminação**: linhas sequenciais até próxima linha matching `^- ` (próximo top-level — bucket, nota livre, ou outra entrada) ou EOF.
- **Sub-bullets aninhados** (≥1 tab) preservados como parte do bloco extraído.
- Bucket ausente naquele journal → silent skip.

**Nenhum journal com match do bucket** → recusa silenciosa com `bucket #<hashtag> ausente na janela [<hoje-N>, <hoje>]`. Exit clean.

### 5. Surface conteúdo + reportar sumário

Compose output agrupado por data, **ordem cronológica reversa** (mais recente primeiro):

```
## Journal YYYY-MM-DD (~/Notes/logseq/journals/<date>.md)

<conteúdo lido literal>

---

## Journal YYYY-MM-DD (~/Notes/logseq/journals/<date>.md)

<conteúdo lido literal>
```

Sem síntese, sem comentário editorial — **load context é primitiva, não interpretação**. Operador (ou prompt subsequente da mesma sessão) consome o conteúdo carregado.

Pós-output, 1 linha de sumário:

- Sem `--bucket`: `<M> de <N> journals lidos na janela [hoje-N, hoje]`.
- Com `--bucket`: `<M> de <N> journals com matches do bucket #<hashtag> na janela [hoje-N, hoje]`.

Exit.

## O que NÃO fazer

- Não sintetizar nem comentar o conteúdo carregado — `load` é primitiva read-only; síntese cabe à reasoning subsequente da sessão (ou ao operador).
- Não aplicar gate `pgrep -xi logseq` — read-only é exceção doutrinária per Adendo (2026-06-12) a ADR-001 Sub-decisão 7. UX intencional: operador frequentemente trabalha com Logseq aberto.
- Não inferir bucket do cwd — `--bucket` exige hashtag explícita do operador. Diferente de `/journal-note` que deriva `#<basename>` do repo (write tem contexto único; load pode ser cross-domínio independente do cwd).
- Não classificar, mover, nem editar tasks lidas — escopo é load. Classificação GTD é `/journal-review` (sucessor de `/weekly-review` per ADR-001 Sub-decisão 10).
- Não escrever no journal — read-only absoluto.
- Não compor síntese estilo `/journal-close` — close é write-final-da-sessão; load é input pra sessão. Direções opostas, propósitos opostos.
- Não filtrar por marker GTD (TODO/DOING/WAITING) inline — load surface integral; filter por marker reabre via gatilho de revisão futura se demand emergir (não YAGNI hoje).
- Não cachear conteúdo entre invocações — skill é stateless; cada invocação re-Read os files na janela.
- Não cap em N grande — operador escolhe; `--bucket` é a mitigação canonical pra janelas amplas.
