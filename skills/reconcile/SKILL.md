---
name: reconcile
description: Ritual de abertura de sessão — verify-state cross-store (Forge + NOTES + Journal) em load-time, surfando inconsistências antes de orientar. Read-only.
disable-model-invocation: false
---

# reconcile

Skill orquestrador per [ADR-001 meta-bridge](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 17 — **ritual de abertura** de sessão (espelho do `/journal-close`, que é o fim-de-sessão). Reusa o primitivo verify-state-before-materialize (pragmatic-dev-toolkit ADR-069, hoje só em materialize-time) em **load-time**: checa o estado real dos 3 stores (Forge, annotations/NOTES, Journal) e surfa inconsistências **antes de orientar**, pra não empurrar o operador a um item já resolvido.

Faceta A do reconciler (#46) — **read-only**: surfa findings, **não muta** o grafo. A escrita das reconciliações é a faceta C (#48). O dedup cross-store amplo (regras dual-entry de ADR-025) é a faceta B (#47).

Decomposição mecânico/judgment (ADR-002, padrão `/inbox-aggregate`): o subcomando determinístico `mb reconcile-check` faz parse + match; esta skill orquestra o **fetch forge** (forge-auto-detect → `gh`/`glab`) e a **apresentação editorial**. 2 checks v0: `journal_forge_closed` + `notes_encerrada`.

## Argumentos

Sem argumentos. Skill resolve caminhos e repos autonomamente.

```
/reconcile
```

## Passos

### 1. Resolver journal de hoje + NOTES

Journal: `~/Notes/logseq/journals/<YYYY_MM_DD>.md` (`date +%Y_%m_%d`). Ausente → só o Check 2 (NOTES) roda; seguir.

NOTES: `.claude/local/NOTES.md` no cwd (annotation store local). Ausente → Check 2 pulado; seguir.

### 2. Descobrir os pares `(repo, iid)` Forge-synced do journal

Se o journal de hoje existe (Step 1; ausente → pular para o Step 4 com `closed_issues = {}`). Grep as tasks abertas em bucket Forge-synced carregando `(#<iid>)`:

```bash
grep -nP '^\t*- (?:TODO|DOING|WAITING|NOW|LATER).*\(#\d+\)' ~/Notes/logseq/journals/<date>.md
```

Para cada linha, o **repo** é: o bucket `#<repo>` que a contém, ou — se a task está no bucket `#inbox` — a hashtag inline `#<repo>` (contrato [SD14](../../docs/decisions/ADR-001-skills-de-bridge.md)). Acumular os pares `(repo, iid)` distintos. Sem pares → `closed_issues = {}` (Check 1 vira no-op; só o Check 2 roda).

### 3. Fetch do estado das issues referenciadas (read-only)

Para cada `repo` distinto do Step 2, resolver o forge + a referência completa e checar o estado **só dos iids referenciados** (não listar todas as issues — targeted, barato):

- **Resolver `repo` (nome nu do bucket) → forge + ref completa** via o cluster lookup de `/init-logseq-project` (`~/.mrconfig` → `~/Projects/meta-system/REPOS.md`):
  - repo da constelação GitHub → forge `gh`, ref `<owner>/<repo>` (owner do remote/REPOS.md).
  - repo TJPA (GitLab `gitlab-ca.tjpa.jus.br`, descoberto como em `/inbox-aggregate` Step 2) → forge `glab`, ref = project-path completo do remote.
  - repo sem entry no cluster lookup → pular (não vira finding; reportar no aviso final).
- Para cada iid daquele repo, checar estado: `gh issue view <iid> -R <owner/repo> --json state -q '.state'` (gh) ou `cd <repo-path> && glab issue view <iid> -O json | jq -r .state` (glab). Estado `CLOSED`/`closed` → acumular o iid.

Construir `closed_issues = {"<repo>": [<iid fechado>, ...], ...}` (chave = nome nu do bucket, sem `#` — o subcomando casa por essa chave). **Failure-open:** falha de forge (CLI ausente, auth, offline) → pular aquele repo + registrar aviso; **não abortar** — o Check 2 (NOTES, local) independe do forge.

### 4. Invocar o subcomando determinístico

```bash
mb reconcile-check \
  --journal ~/Notes/logseq/journals/<date>.md \
  --notes <cwd>/.claude/local/NOTES.md \
  --closed-issues '<closed_issues_json>'
```

Capturar o JSON de stdout: `findings` (lista, cada um com `check`), `checks_run`, `checks_skipped`. Exit não-0 / stderr → reportar ao operador; seguir.

### 5. Apresentar e orientar (sem mutar)

Agrupar os `findings` por `check` e apresentar humano-amigável:

- **`journal_forge_closed`** — "Estas tasks apontam issues já fechadas no Forge — candidatas a marcar `DONE`/reconciliar:" listando `<task>` + `#<repo> (#<iid>)`.
- **`notes_encerrada`** — "Estas entries de NOTES já estão encerradas — não re-orientar para elas:" listando `<entry>` + `<date>`.

Orientar: sugerir as ações (marcar a task `DONE`, fechar/arquivar, ignorar) — mas **o operador (ou a faceta C, #48) executa a escrita**; esta skill não muta. Listar `checks_skipped` + avisos de forge ao final. Sem findings → "Nenhuma inconsistência cross-store na abertura — estado coerente." Exit clean.

## O que NÃO fazer

- **Não escrever/mutar o grafo** — a faceta A é read-only; surfa findings e orienta, mas a escrita das reconciliações (marcar `DONE`, properties) é a faceta C (#48). Sem gate `pgrep` aqui justamente porque não há write.
- **Não fechar/editar issues no Forge** — read-only no Forge; mutações de issue seguem na UI/CLI do operador.
- **Não fazer dedup cross-store amplo nem aplicar regras dual-entry/SSOT** — isso é a faceta B (#47), que depende do contrato ADR-025; aqui só os 2 checks v0.
- **Não usar `gh` para repos TJPA** — operam no GitLab; CLI é `glab` (como em `/inbox-aggregate`).
- **Não listar todas as issues de um repo** — checar só os iids referenciados no journal (targeted); listar tudo é caro e desnecessário.
- **Não abortar quando o forge falha** — failure-open: o Check 2 (NOTES local) roda independente; reportar o forge pulado como aviso.
