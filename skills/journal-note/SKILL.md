---
name: journal-note
description: Find-or-create hashtag-bucket no journal Logseq de hoje + append child task com marker GTD opcional
disable-model-invocation: false
---

# journal-note

Thin orchestrator do subcomando `mb journal-note` (CLI `meta-bridge`). Skill prepara argumentos a partir do contexto CC e delega o write substantivo (find-or-create bucket idempotente, bootstrap journal via template, sub-bullets mecânicos `commit:`/`plan:`) ao CLI. CLI roteia automaticamente: HTTP via Logseq Local HTTP Server quando Logseq aberto, file-direct quando fechado (ADR-003).

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 1 (+ Adendos) e [ADR-002](../../docs/decisions/ADR-002-materializacao-cli-mb.md) (cascateamento thin orchestrator).

## Argumentos

String com conteúdo da nota.

```
/journal-note "TODO investigar drive-sync bug"
/journal-note "DOING refactor do gate pgrep"
/journal-note "DONE removido pipx ensurepath commit:e56d666"
```

Sem argumento → recusa silenciosa com `/journal-note exige conteúdo; use /journal-note "<nota>"`. Exit clean.

## Passos

### 1. Derivar `--domain` (heurístico-semântico — fica na skill)

Probe ordenado:

1. **`git rev-parse --show-toplevel`** retorna 0 → `<domain> = $(basename <toplevel>)`. Skip Step 2.
2. **Step 1 retornou exit não-0** (sem toplevel resolvido — fora de git repo, detached, etc.) → `AskUserQuestion`:
   - header: `Domain`
   - options: `#thought`, `#draft`, `#idea`
   - "Other" livre — operador digita tag arbitrária.

Convention de naming em [ADR-002 do logseq-notes Sub-decisão 3](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md). CLI faz a sanitização final (kebab-case lowercase + NFD-strip acentos).

### 2. Invocar `mb journal-note`

`Bash mb journal-note --domain "<domain>" "<conteúdo>"`. Output reporta journal/bucket/marker/sub-bullets — repassar ao operador.

Exit code não-zero → reportar mensagem stderr ao operador (content vazio, erro HTTP etc.).

## O que NÃO fazer

- Não inferir/sintetizar conteúdo — gravar o body literal do operador. Apenas tag (Step 1) e sub-bullets mecânicos (CLI) são derivados.
- Não tocar `.claude/local/NOTES.md` — esse store mora no `/note` do `pragmatic-dev-toolkit` (ADR-032 do toolkit). `/journal-note` e `/note` são canais independentes.
- Não auto-buscar contexto em journals de outros projetos — leitura cross-project é fenômeno conversacional via Read nativo do Claude com path absoluto.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não classificar sub-bullets por prefixo (yagni:/validação:/etc.) — convention ADR-006 § Decisão § 3 é prosa free-form, não schema. Captures mecânicos limitados a `commit:`/`plan:`.
- Não tentar agregar dados cross-bucket no momento do append — bucket é apenas localidade de escrita.
- Não duplicar lógica substantiva (find-or-create, bootstrap journal, sanitização) — substância vive em `meta_bridge.journal_note`.
