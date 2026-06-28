---
name: reconcile
description: Ritual de abertura de sessão — verify-state + dedup cross-store (Forge + NOTES + Journal) em load-time, surfando inconsistências antes de orientar. Oferece escrita de reconciliações journal_forge_closed via HTTP (faceta C).
disable-model-invocation: false
---

# reconcile

Skill orquestrador per [ADR-001 meta-bridge](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 17 — **ritual de abertura** de sessão (espelho do `/journal-close`, que é o fim-de-sessão). Reusa o primitivo verify-state-before-materialize (pragmatic-dev-toolkit ADR-069, hoje só em materialize-time) em **load-time**: checa o estado real dos 3 stores (Forge, annotations/NOTES, Journal) e surfa inconsistências **antes de orientar**, pra não empurrar o operador a um item já resolvido.

Facetas A (#46) + B (#47) do reconciler fazem o **verify-state + dedup** (read-only). A faceta C (#48, ADR-001 SD19) fecha o loop: após surfar os findings, a skill oferece aplicar automaticamente as reconciliações `journal_forge_closed` — marcando tasks `DONE` no journal via `mb reconcile-apply` (write-path HTTP, ADR-003). Writes de `cross_store_dedup` (manipulação de NOTES) ficam deferidos. A faceta B adiciona o **dedup cross-store local** (NOTES↔Journal), materializando o componente dedup do contrato [ADR-025](../../docs/decisions/ADR-001-skills-de-bridge.md) (meta-system); o dedup canônico Journal↔Forge (via listing) e as legs forge ficam deferidos a incremento futuro.

Decomposição mecânico/judgment (ADR-002, padrão `/inbox-aggregate`): o subcomando determinístico `mb reconcile-check` faz parse + match; esta skill orquestra o **fetch forge** (forge-auto-detect → `gh`/`glab`) e a **apresentação editorial**. 3 checks v0, referenciados por número nos Steps abaixo: **Check 1** = `journal_forge_closed` (depende do fetch forge), **Check 2** = `notes_encerrada` (local), **Check 3** = `cross_store_dedup` (local — NOTES↔Journal, independe do fetch forge).

## Argumentos

Sem argumentos. Skill resolve caminhos e repos autonomamente.

```
/reconcile
```

## Passos

### 1. Resolver journal de hoje + NOTES

Journal: `~/Notes/logseq/journals/<YYYY_MM_DD>.md` (`date +%Y_%m_%d`). Ausente → só o Check 2 (único que não depende do journal) roda; Checks 1 e 3 pulados; seguir.

NOTES: `.claude/local/NOTES.md` no cwd (annotation store local). Ausente → Checks 2 e 3 (dependentes de NOTES) pulados; seguir.

### 2. Descobrir os pares `(repo, iid)` Forge-synced do journal

Se o journal de hoje existe (Step 1; ausente → pular para o Step 4 com `closed_issues = {}`). Grep as tasks abertas em bucket Forge-synced carregando `(#<iid>)`:

```bash
grep -nP '^\t*- (?:TODO|DOING|WAITING|NOW|LATER).*\(#\d+\)' ~/Notes/logseq/journals/<date>.md
```

Para cada linha, o **repo** é: o bucket `#<repo>` que a contém, ou — se a task está no bucket `#inbox` — a hashtag inline `#<repo>` (contrato [SD14](../../docs/decisions/ADR-001-skills-de-bridge.md)). Acumular os pares `(repo, iid)` distintos. Sem pares → `closed_issues = {}` (Check 1 vira no-op; os Checks 2 e 3, locais, rodam normalmente).

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
- **`cross_store_dedup`** — "Estes itens estão sendo rastreados em mais de um store — consolide no SSOT canonical:" listando `<item>` + `canonical_ssot` + a evidência (entry de NOTES ↔ task do journal, `match` exact/fuzzy). Orientar por domínio: `canonical_ssot: Journal` → a NOTES é scratch non-SSOT (ADR-054) → **promover-ou-descartar** a NOTES; `canonical_ssot: Forge` → a NOTES duplica um item já canonical no Forge → consolidar nele. **Nunca afirmar que existe issue no Forge sem o `(#<iid>)` confirmá-lo** (a heurística só marca Forge quando o iid está presente).

Orientar: sugerir as ações (marcar a task `DONE`, fechar/arquivar, ignorar, consolidar). Listar `checks_skipped` + avisos de forge ao final. Sem findings → "Nenhuma inconsistência cross-store na abertura — estado coerente." **Sempre seguir para o Step 6** (independentemente de findings — o Step 6 verifica internamente se há `journal_forge_closed` para agir).

### 6. Aplicar reconciliações `journal_forge_closed` (faceta C)

Se não há findings `journal_forge_closed` → skip silente.

**Gate config HTTP:** verificar se `~/.config/meta-bridge/config.json` existe. Ausente → informar ("Local HTTP Server não configurado — aplicar manualmente via UI do Logseq") + skip; não abortar.

**Confirmar por grupo:** listar as tasks candidatas e perguntar via `AskUserQuestion` (header `Aplicar reconciliações`, opções `Aplicar (marcar DONE)` / `Pular (aplicar depois)`).

`Aplicar`: invocar o subcomando determinístico passando o **array `findings`** da saída do Step 4 (não o objeto completo — o subcomando espera uma lista de dicts de finding) e o path do journal:

```bash
mb reconcile-apply \
  --findings-json '<saída_step4.findings como JSON array>' \
  --journal-path ~/Notes/logseq/journals/<date>.md
```

**Apresentar resultado:** ler os campos `applied`, `skipped` e `error` do JSON de stdout:

- Se `error` não-null ou `skipped` não-vazio → exibir bloco de alerta **antes** do resumo: "⚠ N task(s) não aplicada(s) — verifique se Logseq está aberto com o Local HTTP Server habilitado e o token válido." Listar o campo `skipped[].reason` por task quando disponível.
- Resumir `applied` apenas se não-vazio: "Marcadas como DONE: [lista de tasks]."
- Se `applied` vazio, `skipped` vazio e `error` null → reportar: "Nenhuma task aplicada — nenhum finding `journal_forge_closed` filtrado pelo subcomando. Verificar se o JSON passado continha os findings esperados."

`Pular` → encerrar sem mutação.

## O que NÃO fazer

- **Não escrever via file-direct** — a faceta C usa **exclusivamente** o write-path HTTP (`mb reconcile-apply`); não há gate `pgrep` porque o Logseq precisa estar aberto para o HTTP funcionar.
- **Não fechar/editar issues no Forge** — read-only no Forge; mutações de issue seguem na UI/CLI do operador.
- **Não aplicar writes de `cross_store_dedup`** — descarte/promoção de entries de NOTES é destrutivo e exige decisão por item; deferido a incremento futuro.
- **Não fazer o dedup canônico Journal↔Forge nem aplicar regras dual-entry/SSOT que exijam listing de issues** — o `cross_store_dedup` v0 é **local** (NOTES↔Journal); o dedup canônico exige listar issues abertas, fora da disciplina targeted — deferido.
- **Não usar `gh` para repos TJPA** — operam no GitLab; CLI é `glab` (como em `/inbox-aggregate`).
- **Não listar todas as issues de um repo** — checar só os iids referenciados no journal (targeted); listar tudo é caro e desnecessário.
- **Não abortar quando o forge falha** — failure-open: o Check 2 (NOTES local) roda independente; reportar o forge pulado como aviso.
