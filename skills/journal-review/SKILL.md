---
name: journal-review
description: Detective-first review com 4 heurísticas estruturais sobre janela configurável de journals; wizard GTD opt-in (sucessor de /weekly-review v0.2.0)
disable-model-invocation: false
---

# journal-review

Detective-first review de janela configurável (default 30 dias) sobre os journals Logseq do operador. Skill analisa cross-journals via 4 heurísticas estruturais (`task-closure-by-context`, `task-zombie`, `bucket-underused`, `bucket-emerging`) que emitem findings agrupados com evidência inline. Preview-first apresenta tudo numa única `AskUserQuestion`; operador aplica tudo, cherry-pick via Other, ou cancela. Tasks abertas que não geraram finding opcional viram input do wizard residual via `--interactive` (mesma mecânica linear de `/weekly-review` v0.2.0).

Sucessor de `/weekly-review` v0.2.0 — substitui GTD wizard linear hardcoded 7d por knowledge garden curation com janela configurável + análise estrutural detective. Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 10; Sub-decisão 5 preservada como histórico v0.1/v0.2 com cross-ref de sucessor.

Há overlap conceitual com `/journal-close` v0.4.1 (ambos fecham TODOs por evidência), mas eixos distintos: `/journal-close` confronta backlog com **session context** (commits da sessão CC corrente); `/journal-review` confronta com **conteúdo da janela inteira de journals** (correlação inter-journal). Complementares, não substitutos — idempotência natural via SSOT in-place de markers.

Skill opera **independente** de `CLAUDE.md` / role contract. Compõe in-skill (sem template de page Logseq).

## Argumentos

Todos opcionais. Sem args → janela default 30 dias + análise detective sem wizard residual + sem write-summary.

```
/journal-review                    # default: --days 30 detective-only
/journal-review --days 7           # janela semanal
/journal-review --days 90          # janela trimestral
/journal-review --from 2026-05-01 --to 2026-05-31  # range arbitrário (mensal)
/journal-review --interactive      # detective + wizard residual após
/journal-review --write-summary    # detective + bloco summary no journal de hoje
```

- `--days N`: inteiro N ≥ 0. Janela `[hoje-N, hoje]` inclusiva (N+1 dias). Default 30. Mutuamente exclusivo com `--from/--to`. N < 0 ou não-inteiro → recusa com `--days exige N >= 0`. Exit clean.
- `--from <YYYY-MM-DD> --to <YYYY-MM-DD>`: range explícito (mutuamente exclusivo com `--days`). Validar `from ≤ to`. Datas fora do formato ISO → recusa com `--from/--to exigem YYYY-MM-DD`. Exit clean.
- `--interactive`: ativa wizard residual após análise detective. Tasks abertas que não geraram finding nas heurísticas 1-2 viram input do wizard linear (keep/next_step/archive/defer per Sub-decisão 5). Default off.
- `--write-summary`: escreve bloco `## Journal review — YYYY-MM-DD` no journal de hoje com findings aplicados + decisões cherry-pick. Default off — curation é meta-operação invisível por design.

## Passos

### 1. Gates (cheap-first)

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-review`. Exit clean. Skill é write em apply de heurísticas 1-2 + write opcional do summary — gate failure-closed per Sub-decisão 7.

Sem gate git repo — skill opera sobre `~/Notes/logseq/journals/`, não deriva nada do cwd (paralelo a Sub-decisão 5 Adendo v0.2.0 § Drop gate git repo).

### 2. Parse args + resolve janela

#### 2a. Parse args

- `--days N` E `--from/--to` declarados simultaneamente → recusa com `--days e --from/--to são mutuamente exclusivos`. Exit clean.
- `--from` sem `--to` ou vice-versa → recusa com `--from e --to exigem ambos`. Exit clean.
- `--days N` válido → janela = `[hoje-N, hoje]`.
- `--from/--to` válidos → janela = `[from, to]`.
- Nenhum → default `--days 30`.

#### 2b. Resolve paths dos journals

Shell loop análogo a `/journal-load` (Sub-decisão 9). Pra `--days N`:

```bash
for i in $(seq 0 N); do date -d "$i days ago" +%Y_%m_%d; done
```

Pra `--from <D1> --to <D2>`: iterar dia a dia entre D1 e D2 inclusivo via mesmo idiom `date -d "$d + 1 day" +%Y_%m_%d` partindo de D1 até atingir D2.

Cada item → path `~/Notes/logseq/journals/<date>.md`. Local TZ alinhado per Adendo v0.2.1 a Sub-decisão 1. Paths ausentes → silent skip (dia inativo).

Janela vazia (zero journals existentes) → recusa silenciosa com `nenhum journal encontrado na janela <range>`. Exit clean.

### 3. Coleta cross-journals

Pra cada journal existente na janela, extrair material correlacionável (paralelo a `/journal-close` Sub-decisão 3 Adendo v0.4.0 § coleta de reconciliação):

#### 3a. Markers ativos (TODO/DOING/WAITING)

- Regex: `^\t- (TODO|DOING|WAITING) (.*)$` — 1-tab indent, filhas diretas de bucket.
- `DONE`/`CANCELLED` **não** capturados como markers ativos (terminais por design per ADR-002 Sub-decisão 4 do logseq-notes).
- Markers em sub-bullets (≥2 tabs) **não** capturados — prosa contextual.

Pra cada match capturar:
- Marker (TODO/DOING/WAITING).
- Conteúdo (texto após marker).
- Bucket-pai (`- #<domínio>` ancestor — tree-walk pra trás até linha top-level `^- #` mais próxima).
- Source: path absoluto do journal + line number.
- Sub-bullets do marker (≥2 tabs imediatamente abaixo até próximo marker ou bucket).
- Data do journal source (extraída do filename `YYYY_MM_DD`).

#### 3b. DONE-tasks recentes (material correlacionável)

- Regex: `^\t- DONE (.*)$` (1-tab indent).
- Pra cada match capturar: conteúdo, bucket-pai, sub-bullets (commit/plan refs), data do journal source.
- Input pra Heurística 1 (`task-closure-by-context`) — match semântico contra markers ativos abertos.

#### 3c. Narrativas (contexto editorial)

- Bullets top-level (1-tab indent) sob buckets `- #<domínio>` que NÃO são markers GTD (não começam com `TODO`/`DOING`/`WAITING`/`DONE`/`CANCELLED`).
- Capturam frames de sessão, insights, mudanças finas, direção emergente (per `/journal-close` Sub-decisão 3 Adendos v0.3.0/v0.4.1).
- Input pra Heurística 1 (match contra texto) + Heurística 4 (`bucket-emerging` — hashtags emergentes em narrativas).

#### 3d. Inventário de buckets

- Buckets `- #<domínio>` top-level (regex `^- #([a-z0-9-]+)`).
- Pra cada bucket: contagem de journals em que aparece (K'), contagem de tasks abertas associadas (M'), contagem de DONE-tasks associadas.
- Input pra Heurísticas 3 (`bucket-underused`) e 4 (`bucket-emerging`).

Resultado da coleta: 4 conjuntos estruturados (markers ativos, DONE-tasks, narrativas, inventário de buckets) cross-journals na janela.

### 4. Análise detectiva — 4 heurísticas

Pra cada heurística, agente compõe lista de findings com evidência inline.

#### 4a. Heurística 1 — `task-closure-by-context` (task-level, apply)

Pra cada marker ativo (TODO/DOING/WAITING) na janela, agente confronta com:
- DONE-tasks posteriores na janela (Step 3b).
- Narrativas posteriores na janela (Step 3c).

**Critério de match (judgment semântico)**:
- Match textual semântico: conteúdo do marker corresponde a DONE-task ou narrativa posterior.
- Cross-refs explícitos como hint forte: marker tem sub-bullet `plan:<slug>` que casa com plan slug de DONE posterior; `commit:<hash>` que casa com commit recente; ou `[[<page>]]` que casa com page tocada.
- Judgment conservador: incerto → **não** emite finding. Operador pode rodar `--interactive` ou processar manualmente.

**Finding emitido** (apply):
```
[task-closure-by-context] TODO/DOING/WAITING X em #<bucket> (journal YYYY-MM-DD:linha)
  → fechar in-place (marker → DONE)
  Evidência: DONE Y em #<bucket> (journal YYYY-MM-DD:linha) [+ commit:hash | plan:slug | [[page]] se aplicável]
  Contexto: <2-3 linhas explicando o match>
```

#### 4b. Heurística 2 — `task-zombie` (task-level, apply)

Pra cada marker ativo (TODO/DOING/WAITING) na janela, agente verifica:
- Idade (dia atual - data do journal source) > T dias. T default = 14.
- Zero DONE-tasks relacionados na janela (Step 3b).
- Zero referência em narrativas posteriores (Step 3c).

**Finding emitido** (apply, operador escolhe ação):
```
[task-zombie] TODO/DOING/WAITING X em #<bucket> (journal YYYY-MM-DD:linha)
  → archive (DONE) ou cancel (CANCELLED) — operador escolhe
  Evidência: aberto há <N> dias sem progresso correlato (zero DONE relacionado, zero menção em narrativa).
  Contexto: <bucket> usage geral na janela: <K'/N journals, M' tasks abertas>
```

#### 4c. Heurística 3 — `bucket-underused` (structural, report-only)

Pra cada bucket no inventário (Step 3d), agente verifica:
- Aparece em < K journals na janela. K default = 2.
- Tem < M tasks abertas totais. M default = 2.

**Finding emitido** (report-only — sem apply automático):
```
[bucket-underused] Bucket #<X> usage baixo na janela
  → considerar archive (mover pra page agregadora) ou fund com bucket relacionado #<Y>
  Evidência: aparece em K'/N journals, M' tasks abertas, M'' DONE-tasks no período.
  Buckets relacionados sugeridos (similaridade textual): #<Y>, #<Z>.
  Apply manual: operador inspeciona e aplica via Edit/Write em sessão dedicada.
```

#### 4d. Heurística 4 — `bucket-emerging` (structural, report-only)

Pra cada hashtag/conceito X que aparece em narrativas (Step 3c) mas NÃO existe como bucket top-level:
- Contagem de menções ≥ N. N default = 3.

**Finding emitido** (report-only):
```
[bucket-emerging] Conceito #<X> mencionado em narrativas sem bucket dedicado
  → considerar criar bucket dedicado #<X>
  Evidência: mencionado N' vezes em narrativas dos buckets #<A> (journal YYYY-MM-DD), #<B> (journal YYYY-MM-DD), ...
  Apply manual: operador cria bucket no journal de hoje + opcional migra referências.
```

**Falsos-positivos heading-style** (ex.: `WAITING Próximos passos` capturado pela regex mas é heading textual): judgment do agente filtra antes de emitir finding em qualquer heurística. Gatilho de revisão registrado na Sub-decisão 10 § Gatilhos futuros: N ≥ 2 reports adicionais → adicionar regra de blacklist textual.

**Análise vazia** (zero findings em todas as 4 heurísticas): recusa silenciosa com `nenhum finding emitido na janela <range>; nada a propor`. Exit clean. Step 5 não dispara (exceto se `--interactive` ativo — wizard residual pode ainda processar markers abertos).

### 5. Apresentação preview-first

Prosa antes da chamada enumera findings agrupados por tipo, com evidência inline:

```
## Findings detective (janela <range>)

### task-closure-by-context (apply)
1. TODO X em #<bucket> (journal YYYY-MM-DD:linha) → DONE
   Evidência: ...
   Contexto: ...
2. ...

### task-zombie (apply)
N. TODO Y em #<bucket> (journal YYYY-MM-DD:linha) → archive/cancel
   ...

### bucket-underused (report-only)
M. Bucket #<X> → archive ou fund com #<Y>
   ...

### bucket-emerging (report-only)
P. Conceito #<X> → criar bucket
   ...
```

**`AskUserQuestion` única**:
- header: `Findings`
- options:
  - `Aplicar tudo` — write executa heurísticas 1-2 (apply); heurísticas 3-4 ficam só registradas no summary (se `--write-summary` ativo).
  - `Cherry-pick via Other` — operador descreve subset em prosa ("aplica só findings 1 e 3; rejeita 2"; ou "apply heurística 1 inteira, ignora 2"). Skill parsea e aplica subset.
  - `Cancelar` — abort silente. Sem write.

**Gatilho de revisão** (registrado na Sub-decisão 10 § Gatilhos futuros): cherry-pick via Other em prosa funciona até ~15-20 findings totais; janela grande (mensal/trimestral) com 30+ findings vira frágil (operador conta números no preview; agente parsea texto livre). Se ≥ 2 invocações reais emitirem > 30 findings → adicionar batched cherry-pick (paralelo a Step 6 batch de 4) ou truncate per-tipo. Por ora aceitar prosa pura — janela default 30 com analisador conservador típico emite poucos findings.

### 6. Wizard residual opt-in (`--interactive`)

`--interactive` ativo → tasks abertas que **não** geraram finding nas heurísticas 1-2 entram em wizard linear. Mecânica idêntica a Sub-decisão 5 Adendo v0.2.0:

- Truncate max 20 tasks por marker (60 total potencial).
- 4 opções per task: `Manter aqui` / `Próximo passo definido` (Other → descrição) / `Arquivar` (DONE/CANCELLED) / `Adiar próxima semana` (move pra journal de `next Monday` preservando bucket).
- Batch de 4 perguntas por `AskUserQuestion`. Pause: enum `Continuar` / `Pausar e fechar`.

`--interactive` ausente → skip; skill termina após apply de findings detective.

### 7. Apply task-level

Pra cada finding confirmado das heurísticas 1-2 (Step 5), edit cirúrgico no source path:

- **Localizar linha exata** via (source-path, source-line, marker-original). Match estrito do conteúdo da linha contra captura do Step 3a — protege contra drift se journal foi editado manualmente entre Step 3 e Step 7 (raríssimo dado pgrep gate, mas defensivo).
- **Replace marker**:
  - Heurística 1 → `TODO`/`DOING`/`WAITING` → `DONE`.
  - Heurística 2 archive → `TODO`/`DOING`/`WAITING` → `DONE`.
  - Heurística 2 cancel → `TODO`/`DOING`/`WAITING` → `CANCELLED`.
- **Preservar sub-bullets, indent, conteúdo após marker**. Mecânica idêntica a `/journal-close` Sub-decisão 3 Adendo v0.4.0 Step 5a e `/weekly-review` Sub-decisão 5 Adendo v0.2.0 archive.

**Falha de match** (linha não corresponde mais ao marker esperado por edit concorrente) → skip esta transição com warning `apply abortado: source <path>:<line> não casa marker esperado (edit manual concorrente?)`. Demais apply prosseguem. Reportar count de skipped no Step 9.

**Heurísticas 3-4 (report-only)**: NÃO aplicam — findings ficam só no preview/summary. Operador inspeciona evidência e decide apply manual via Edit/Write em sessão dedicada. Apply estrutural automático reabre em v0.4.0 sob gatilho (registrado na Sub-decisão 10 § Gatilhos futuros: N ≥ 2 reports de report-only findings que mereceriam apply automatizado).

**Snapshot defensivo**: YAGNI no MVP. Marker change é single-line atomic, idempotente (re-aplicar = no-op), reversível via grep + sed manual. Canal real de falha é matching errado, capturado no preview-first com evidência inline. Apply estrutural quando reabrir trará snapshot per-finding-type em XDG cache path fora do graph.

### 8. `--write-summary` opcional

`--write-summary` ativo → escrever bloco no journal de hoje (`~/Notes/logseq/journals/$(date +%Y_%m_%d).md`):

```
- ## Journal review — YYYY-MM-DD
	- Janela analisada: <range> (<N> journals)
	- Heurística 1 (task-closure-by-context): <X aplicados, Y rejeitados>
		- DONE X em #<bucket> (journal YYYY-MM-DD:linha) — closed via finding
		- ...
	- Heurística 2 (task-zombie): <X archived, Y cancelled, Z rejeitados>
		- ...
	- Heurística 3 (bucket-underused): <N findings report-only> (apply manual)
		- Bucket #<X> sugerido archive — pendente decisão manual
		- ...
	- Heurística 4 (bucket-emerging): <N findings report-only>
		- ...
	- Wizard residual (--interactive): <N tasks classificadas> (se --interactive ativo)
```

Append no journal de hoje (find-or-create bloco `## Journal review — YYYY-MM-DD` — se já existe, append children; senão, append novo bloco top-level no fim). Bootstrap journal: ausente → ler `~/Notes/logseq/pages/daily-journal.md` como scaffold (paralelo a `/journal-close`).

`--write-summary` ausente → skip; skill termina após apply.

### 9. Reportar

- Path(s) tocado(s): journals modificados via apply + journal de hoje (se `--write-summary` ativo).
- Findings emitidos por heurística (count): H1 / H2 / H3 / H4.
- Findings aplicados vs report-only vs rejeitados.
- Transições aplicadas (heurísticas 1-2) com source path/linha (subdivididos: archive, cancel).
- Skipped apply com motivo (falha de match concorrente).
- Wizard residual count (se `--interactive` ativo).

Exit.

## O que NÃO fazer

- Não fazer apply estrutural de bucket no MVP — heurísticas 3-4 são report-only. Operador inspeciona evidência detalhada e aplica manualmente. Apply estrutural automático com snapshot defensivo reabre em v0.4.0 sob gatilho N ≥ 2 reports.
- Não criar snapshot pré-write no MVP — marker change (heurísticas 1-2) é single-line atomic idempotente; canal real de falha é matching errado capturado no preview-first.
- Não propor finding em matches incertos — quando judgment não confirma fechamento/zombie/structural pattern, deixar marker intocado. Princípio conservador idêntico ao `/journal-close` Sub-decisão 3 Adendo v0.4.0.
- Não modificar markers em sub-bullets (≥2 tabs) — regex restrita a 1-tab indent per Sub-decisão 5 Adendo v0.2.0; markers nested são prosa contextual.
- Não capturar `DONE`/`CANCELLED` como markers reconciliáveis — terminais por design (ADR-002 Sub-decisão 4); não re-abrem.
- Não escrever bloco summary por default — `--write-summary` é opt-in. Curation é meta-operação invisível; findings deixam trace SSOT via marker change in-place (heurísticas 1-2); duplicar em bloco no journal de hoje é redundância editorial.
- Não anotar sub-bullet `→ closed via finding` sob marker original quando aplica modify-in-place — SSOT in-place per ADR-002 Sub-decisão 4. Trace fica em `--write-summary` quando ativo.
- Não rodar wizard residual por default — `--interactive` é opt-in. Skill é detective-first; wizard linear vira fallback pra quem quer processo GTD clássico.
- Não escrever se Logseq desktop aberto (pgrep gate per Sub-decisão 7). Failure-closed.
- Não derivar bucket do cwd — skill opera sobre `~/Notes/logseq/journals/` cross-files; bucket inventory emerge da coleta cross-journals, não do cwd onde foi invocada.
- Não inflar análise quando substância é magra — janela com 1-2 markers, zero DONE-tasks, zero narrativas: heurísticas naturalmente emitem zero findings (judgment conservador). Recusa silenciosa elegante.
- Não invocar Logseq CLI ou desktop pra renderizar/query — skill opera filesystem markdown só. Sem block-refs, sem Datalog queries.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não estender janela default sem `--days N` ou `--from/--to` — 30 dias é o default coerente com knowledge garden curation mensal; N>30 é opt-in explícito.
- Não capear janela grande (N ≥ 90 ou range > 3 meses) — escolha do operador per paralelo a `/journal-load` Sub-decisão 9 § Edge cases. Sem `--bucket` mitigation por design (review é cross-bucket — bucket inventory é input das heurísticas 3-4). Skill pode floodar context window em janelas extremas; operador balanceia.
- Não confundir `/journal-review` com `/journal-close` v0.4.1 — apesar de ambas usarem regex top-level + modify-in-place marker, eixos distintos: `/journal-close` confronta backlog com session context da sessão CC corrente; `/journal-review` confronta com conteúdo da janela inteira de journals (correlação inter-journal). Ver Sub-decisão 10 § Interaction matrix.
