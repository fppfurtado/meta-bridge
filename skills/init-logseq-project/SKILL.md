---
name: init-logseq-project
description: Cria/atualiza Project Page no graph Logseq a partir do CLAUDE.md/README.md do repo (idempotente; preserva props humanas)
disable-model-invocation: false
---

# init-logseq-project

Cria ou re-sincroniza a Project Page no graph Logseq correspondente ao repo no cwd. Preserva edits humanas; sobrescreve apenas props mecânicas. Materializa Camada 3 (Bridge) per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 4.

Skill opera **independente** de `CLAUDE.md` / role contract.

## Argumentos

Sem argumentos. Skill opera no cwd corrente. Manual one-shot per repo — operador invoca quando quer ressincronizar drift ou popular repo novo.

## Passos

### 1. Gates (cheap-first)

**Ordem**: git gate primeiro (sem side-effect, diagnóstico imediato), pgrep depois.

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/init-logseq-project exige git repo (skill deriva basename + path)`. Exit clean.

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /init-logseq-project`. Exit clean.

### 2. Resolve metadata mecânica

- **Repo basename**: `basename $(git rev-parse --show-toplevel)`.
- **Repo path**: `git rev-parse --show-toplevel` (absoluto).
- **Repo host**: `git remote get-url origin` → parse host. Match `github.com` → `#github`. Match `gitlab.com` → `#gitlab`. Match outro `*.*` host → tag literal `#<host>`. Sem remote (`origin` ausente) → `#local`.

### 3. Resolve cluster/subcluster (probe ordenado)

Paths absolutos constants:
- `MRCONFIG_PATH = ~/.mrconfig` (canonical pela convenção do `mr`).
- `REPOS_MD_PATH = ~/Projects/meta-system/REPOS.md` (canonical pela arquitetura meta-system; symlink `~/Projects` → `/storage/dev/projects/` per ADR-002 do meta-system).

Sequência:

1. **mrconfig lookup** (path-normalized iteration): `.mrconfig` headers usam paths não-expandidos (ex.: `[$HOME/Projects/<repo>]`), enquanto `$REPO_PATH` do Step 2 vem resolvido por `git rev-parse --show-toplevel` (ex.: `/storage/dev/projects/<repo>` quando `~/Projects` é symlink). Comparação literal falha — normalizar ambos. Mecânica:
   ```bash
   TARGET=$(readlink -f "$REPO_PATH")
   FOUND_HEADER=""
   while read -r LINE; do
     if [[ "$LINE" =~ ^\[(.+)\]$ ]]; then
       HEADER_PATH=$(eval echo "${BASH_REMATCH[1]}")
       HEADER_RESOLVED=$(readlink -f "$HEADER_PATH" 2>/dev/null)
       [ "$HEADER_RESOLVED" = "$TARGET" ] && { FOUND_HEADER="${BASH_REMATCH[1]}"; break; }
     fi
   done < "$MRCONFIG_PATH"
   ```
   Match → extract `tags = <cluster> [<subcluster>]` via flag-pattern awk (range pattern `$0==p,/^\[/` seria single-line porque header satisfaz ambos endpoints):
   ```bash
   awk -v p="[$FOUND_HEADER]" '$0==p {flag=1; next} /^\[/ {flag=0} flag && /^tags = / {print; exit}' "$MRCONFIG_PATH"
   ```
   Parse cluster (primeiro token após `tags = `) + subcluster (segundo, opcional). Match → cluster/subcluster set, skip pra Step 4.
2. **REPOS.md fallback** (tabela markdown lookup): REPOS.md usa formato tabela (`| \`<basename>\` | <path> | <descrição> | <status> | <host> |`) com heading `## <cluster>` precedendo cada seção tabular. Mecânica:
   ```bash
   LINE_NUM=$(grep -n "^| \`${REPO_BASENAME}\`" "$REPOS_MD_PATH" | head -1 | cut -d: -f1)
   [ -n "$LINE_NUM" ] && CLUSTER=$(head -n "$LINE_NUM" "$REPOS_MD_PATH" | grep "^## " | tail -1 | sed 's/^## //')
   ```
   Match → cluster set, subcluster = vazio. Path ausente OU basename sem entry → skip pra (3).
3. **Operator prompt fallback**: `AskUserQuestion` header `Cluster`, enum com 9 opções de ADR-003 do meta-system (`meta`, `env-stack`, `dev-toolkit`, `cognitive`, `finance`, `work`, `pro-bono`, `learning`, `life`). Sem Recommended (depende do contexto runtime). Operador escolhe. Subcluster = vazio.

### 4. Lê CLAUDE.md + README.md

- `CLAUDE.md` no cwd existe → ler primeira seção após `# <title>` (até primeiro `##` **ou EOF**, max 200 chars). Extrair primeiro parágrafo como `description`.
- `CLAUDE.md` ausente E `README.md` existe → mesma extração no README.
- Ambos ausentes OU presente mas sem corpo extractable (README só com `# <title>` e sem body) → `description` = vazio (preserva sem populate, sem warning).

### 5. Resolve Project Page path

`PAGE_PATH = ~/Notes/logseq/pages/<REPO_BASENAME>.md` (lowercase basename).

Probe existência via `test -f $PAGE_PATH`:

**Ausente — criar do zero**:

1. Lê template body: `~/Notes/logseq/pages/Project Template.md`. Template ausente → recusa com `Template "Project Template.md" ausente em ~/Notes/logseq/pages/ — feature requer setup do graph (Onda 3 do meta-sistema)`.
2. Skip linhas `type:: #template`, `- template:: project`, `template-including-parent:: false`.
3. Body restante (estrutura `- type:: #project` + props + `## Last journal entries` + `## Follow-ups` + `## Decisões locais`).
4. Substitui props vazias com valores resolvidos:
   - `cluster::` → cluster do Step 3.
   - `subcluster::` → subcluster do Step 3 (ou vazio).
   - `status::` → `#active` (default per ADR-004 invariante; primeiro setup).
   - `repo-path::` → REPO_PATH do Step 2.
   - `repo-host::` → repo host do Step 2.
5. Se `description` não-vazio: adicionar bullet `- description:: <description>` antes de `## Last journal entries` (primeira linha sob root).
6. Write em `PAGE_PATH`.

**Presente — atualização cirúrgica idempotente**:

1. Lê body atual.
2. Identifica **4 linhas de prop mecânica** (regex `^\s*(cluster|subcluster|repo-path|repo-host)::\s*`) e sobrescreve cada uma com novo valor. Linhas não-encontradas → adicionar na **ordem canonical** (`cluster`, `subcluster`, `repo-path`, `repo-host`) após a primeira prop existente, preservando ordem relativa entre as faltantes. Garante diff vazio em runs sucessivos (idempotência canonical).
3. **Preserva**:
   - `status::` (operador pode ter ajustado pra `paused`/`archived`).
   - Outras props humanas (`description::`, `description-source::`, etc.).
   - Blocos sob `## Follow-ups`, `## Decisões locais`, ou qualquer outra heading humana.
4. Write em `PAGE_PATH`.

Critério "prop mecânica" é exhaustivo: 4 props fixas. Tudo o mais preservado.

### 6. Reportar

Report inclui:
- Path da Project Page tocada.
- Modo (criado / atualizado).
- Cluster + subcluster set.
- Repo host detectado.
- Diff resumido (linhas adicionadas/sobrescritas/preservadas; específico no modo atualizado).
- Se description não foi extraída (Step 4 ambos ausentes), warning curto.

Exit.

## O que NÃO fazer

- Não sobrescrever props humanas em update — critério "4 props mecânicas" é exhaustivo per ADR-001 Sub-decisão 4.
- Não atualizar `description::` em re-runs — prop é seeded no create do CLAUDE.md/README, depois preservada como humana per critério ADR-001 (4 props mecânicas exhaustivo). Operador edita manual se quiser ressincronizar.
- Não atualizar `status::` em re-runs — operador edita pra `#paused`/`#archived` pós-create se aplicável; create flow hardcoda `#active` como default per ADR-004 (skill assume primeiro setup = repo active).
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não tenta detectar cluster via inferência ad-hoc — probe ordenado é fixo (`.mrconfig` → REPOS.md → operator prompt).
- Não inventa `subcluster::` quando probe não retorna — campo vazio é semanticamente válido (operador edita manual se precisar).
- Não toca `Project Template.md` — template é source-of-truth; skill é consumer.
- Não cria entry em `.mrconfig` ou REPOS.md — Bridge unidirecional per ADR-005 (graph é destino, não source).
- Não usar regex em `$REPO_PATH` ao lookup `.mrconfig` — match é literal-equality entre paths normalizados via `readlink -f` (paths podem conter `[`, `]`, `.`, espaços; iteração + normalização cobre `$HOME` não-expandido em headers).
