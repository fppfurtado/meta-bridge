---
name: journal-note
description: Append timestampado no journal Logseq de hoje com [[<repo-basename>]] ref auto-detectado
disable-model-invocation: false
---

# journal-note

Append timestampado em `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md` com ref `[[<repo-basename>]]` auto-detectado pelo cwd. Materializa capture com baixo atrito no graph per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 1.

Skill opera **independente** de `CLAUDE.md` / role contract — usável em qualquer git repo. `/note` do `pragmatic-dev-toolkit` cobre o caso NOTES.md local per ADR-032 do toolkit; este skill é o complemento pra capture no graph.

## Argumentos

String com conteúdo da nota.

```
/journal-note "TODO investigar drive-sync bug"
```

Sem argumento → recusa silenciosa com mensagem `/journal-note exige conteúdo; use /journal-note "<nota>"`. Conteúdo final vazio → recusa silenciosa, exit clean.

## Passos

### 1. Gates (cheap-first)

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/journal-note exige git repo pra resolver repo basename`. Exit clean.

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-note (skill escreve direto no filesystem do graph)`. Exit clean.

### 2. Resolve metadata

- **Repo basename**: `basename $(git rev-parse --show-toplevel)`.
- **Journal path**: `~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md` (Logseq canonical filename com separator `_`, UTC date).
- **Timestamp UTC**: `date -u +%Y-%m-%dT%H:%M:%SZ`.

### 3. Append do bloco

Conteúdo final vazio → recusa silenciosa, exit clean.

Caso contrário, append no journal path no formato:

```
- <timestamp UTC> | [[<repo-basename>]]
	- <conteúdo literal>
```

Journal path não existe → ler `~/Notes/logseq/pages/daily-journal.md` como template body, copiar conteúdo (após linhas `- template:: daily-journal` e `  template-including-parent:: false`) para o journal path; append do bloco no fim. Template ausente (logseq-notes não setup) → criar arquivo vazio + append do bloco; reportar warning `template daily-journal.md ausente; journal criado sem estrutura — Logseq apply de template manual ao abrir`.

### 4. Reportar

Journal path + bytes adicionados + repo basename usado como ref. Exit.

## O que NÃO fazer

- Não inferir/sintetizar conteúdo — gravar o argumento literal do operador.
- Não tocar `.claude/local/NOTES.md` — esse store mora no `/note` do `pragmatic-dev-toolkit` (ADR-032 do toolkit). `/journal-note` e `/note` são canais independentes.
- Não auto-buscar contexto em journals de outros projetos — leitura cross-project é fenômeno conversacional via Read nativo do Claude com path absoluto.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não roteia se Logseq desktop aberto (pgrep gate). Falha fechada com mensagem clara.
- Não tenta usar `pidof`, `ps -A | grep` em vez de `pgrep -xi logseq` — canonical fixed per ADR-001 Sub-decisão 7.
