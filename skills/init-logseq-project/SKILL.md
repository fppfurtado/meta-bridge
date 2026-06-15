---
name: init-logseq-project
description: Cria/atualiza Project Page no graph Logseq a partir do CLAUDE.md/README.md do repo (idempotente; preserva props humanas)
disable-model-invocation: false
---

# init-logseq-project

Thin orchestrator do subcomando `mb init-project` (CLI `meta-bridge`). Skill **delega lookup mecânico de cluster** (mrconfig → REPOS.md) ao CLI e oferece **fallback `AskUserQuestion` enum** apenas quando os lookups falham. CLI faz o write substantivo (bootstrap via Project Template, dedent, macro substitution, props mecânicas idempotentes, preservação de props humanas, gate Logseq).

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 4 e [ADR-002](../../docs/decisions/ADR-002-materializacao-cli-mb.md) (cascateamento thin orchestrator). **Nota sobre F1**: implementação relaxa a polaridade estrita "CLI exige `--cluster` ou falha" — CLI tenta lookups primeiro; skill prompt é fallback do fallback. Caminho-comum: CLI resolve sozinho sem skill intervir.

## Argumentos

Sem argumentos. Skill opera no cwd corrente.

## Passos

### 1. Tentar invocação direta — CLI faz lookups primeiro

`Bash mb init-project`. CLI tenta nesta ordem:
1. `~/.mrconfig` lookup (path normalizado).
2. `~/Projects/meta-system/REPOS.md` lookup (tabela markdown).
3. Falha se ambos vazios e `--cluster` ausente.

**Exit code 0** → CLI resolveu cluster sozinho; reportar output ao operador. Fim.

**Exit code 1** com mensagem `cluster ausente: passe --cluster ...` → seguir Step 2.

### 2. Cluster prompt fallback (heurístico-semântico — fica na skill)

`AskUserQuestion`:
- header: `Cluster`
- options: 9 clusters de `meta-system` ADR-003 — `meta`, `env-stack`, `dev-toolkit`, `cognitive`, `finance`, `work`, `pro-bono`, `learning`, `life`.
- "Other" livre.

Operador escolhe. Re-invocar `Bash mb init-project --cluster "<escolhido>"`.

`--cluster` é override absoluto — CLI pula lookups mrconfig/REPOS.md e usa valor passado direto.

Sem subcluster por design — campo vazio é semanticamente válido. Operador edita manualmente se precisar.

### 3. Reportar

Repassar output do CLI ao operador: path da Project Page, modo (criado/atualizado), cluster + source (mrconfig/REPOS.md/flag), repo-host, counts de props.

## O que NÃO fazer

- **Não duplicar substância (bootstrap, dedent, macro, idempotência, preservação de props)** — vive em `meta_bridge.init_project`.
- Não sobrescrever props humanas em update — critério "4 props mecânicas" é exhaustivo per ADR-001 Sub-decisão 4.
- Não atualizar `description::` ou `status::` em re-runs — preservadas como humanas após primeiro setup.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não compor lookup mecânico fora do CLI — ordem fixa `.mrconfig` → REPOS.md vive em `meta_bridge.init_project`; skill só faz prompt de fallback.
- Não inventa `subcluster::` quando probe não retorna — vazio é válido.
- Não toca `Project Template.md` — template é source-of-truth; skill é consumer.
- Não cria entry em `.mrconfig` ou REPOS.md — Bridge unidirecional per ADR-005 do meta-system (graph é destino, não source).
