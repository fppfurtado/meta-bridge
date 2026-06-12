---
name: journal-close
description: Sintetiza sessão CC no journal Logseq de hoje — narrativa humano-amigável agrupada por #domínio (DONE + TODO/WAITING + insights) + reconciliação prévia (--days N)
disable-model-invocation: false
---

# journal-close

Sintetiza a sessão CC atual em **narrativa humano-amigável agrupada por bucket `- #<repo>`** no journal Logseq de hoje + **reconcilia TODO/WAITING anteriores** (mesmo-repo e cross-repo) que foram fechados pela sessão corrente, via marker change in-place no source. Find-or-create idempotente com `/journal-note` prévios da mesma sessão. Materializa continuidade cross-session per [ADR-005 cross-cutting do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-005-bridge-via-pragmatic-toolkit.md) consumindo [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 3 (+ Adendos v0.3.0 + v0.4.0).

Skill opera **independente** de `CLAUDE.md` / role contract. Compõe in-skill (NÃO consome `pages/session-close.md` — archived pós-retrofit per ADR-002 Sub-decisão 2).

## Argumentos

Flag opcional. Sem args → default = só journal de hoje na janela de reconciliação.

```
/journal-close              # default: lê só hoje pra reconciliar; síntese vai pra hoje
/journal-close --days 3     # lê hoje + 3 dias retroativos pra reconciliar
/journal-close --days 7     # janela semanal de reconciliação
```

- `--days N`: inteiro N ≥ 0. Janela retroativa de leitura pra reconciliação. Default 0 = só hoje (cobre sessões anteriores mesmo-dia). N>0 estende pra dias passados — útil quando TODO/WAITING ficou aberto por mais de um dia e a sessão corrente fechou. N < 0 ou não-inteiro → recusa com `--days exige N >= 0`. Exit clean.

A síntese **sempre** é appendada no journal de hoje — janela retroativa afeta só leitura pra reconciliação.

## Passos

### 1. Gates (cheap-first)

`git rev-parse --show-toplevel` retorna não-zero → recusa com `/journal-close exige git repo (skill deriva repo basename do cwd; sessões fora de git capturam via /journal-note direto)`. Exit clean.

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /journal-close`. Exit clean.

### 2. Parse args + coleta context da sessão

#### 2a. Parse args

- `--days N`: extrair N como inteiro. N inválido → recusa com `--days exige N >= 0`. Exit clean.
- Sem flag → N=0.

#### 2b. Coleta session context

- **Repo basename principal**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado):
  1. Variável env `PRAGMATIC_ACTIVE_PLAN_SLUG` exposta por `/run-plan` do `pragmatic-dev-toolkit` (gap conhecido — hoje sempre None nesta probe).
  2. Probe `docs/plans/*.md` modified nas últimas 2 horas (`find docs/plans -name '*.md' -newermt '2 hours ago'`). Múltiplos → mais recente (`ls -t`).
  3. Nenhum → omitido (campo opcional).
- **Commits da sessão (multi-repo)**: probe explícito de 2 fases:
  1. **Lista cwds tocados**: agente que executa skill enumera cwds visitados na sessão via inspect do conversation history (toolkit pattern). Inclui cwd corrente + paths absolutos de outros repos onde agente fez Bash/Read/Edit. Único: deduplicar paths.
  2. **`git log` em cada cwd descoberto**: para cada path, `cd <path> && git log --since="<start-of-session>" --oneline --no-merges`. Falha (path não é repo, vazio) → skip silente.
- Cada commit captura: subject, hash short (7 chars), repo basename. Resultado: lista [(repo, hash, subject), ...] cobrindo todos os repos tocados.
- **Material editorial via conversation context**: agente inspeciona o transcript da sessão pra extrair além de commits. Filtros de seleção (v0.4.1) aplicados em cada bloco — capturar não é enumerar, é selecionar.
  - **Frame de sessão**: como começou + para onde virou (ex.: "Começou querendo X, desembocou em Y"). Sempre 1 linha — frame longo vira insight.
  - **Insight/pivot conceitual**: o momento que mudou direção, quando há um. **Selecionar 1-2 por sessão** (raramente 3), mesmo em sessão longa — o leitor humano não absorve 5 insights numa releitura rápida. Sessão sem pivot claro omite o bloco.
  - **Mudanças finas**: memory refinada, padrões reconhecidos, notas operacionais não-codificadas em commits. **Critério de inclusão: "isto vai informar futuras decisões?"**. Pattern semântico ("dual-entry pattern reconhecido", "feedback memory X refinada porque Y") passa. Detalhes técnicos-operacionais (version pins de cache, paths absolutos, byte counts, contagens de cenários de smoke test, IDs de memory entries) quase sempre falham o critério — são debug notes de um momento, não substância que orienta o futuro.
  - **Próximos passos enunciados pelo operador** com markers GTD (TODO/WAITING). **Só os enunciados pelo operador ou que emergiram com clareza da sessão** — não inflar com "próximos passos potenciais" que o agente extrapolaria.
  - **Direção emergente**: síntese reflexiva sobre onde a constelação está indo. 1-3 bullets curtos; síntese, não enumeração de consequências.
  - **Cross-refs** ([[page]], links markdown) que emergem do contexto.
  - **Julgamento do agente** sobre o que vale registrar — não mecânico. Sessão sem substância editorial além de DONE-tasks degrada elegantemente pra padrão runbook simples (ver Step 3).
- **Journal path (destino da síntese)**: `~/Notes/logseq/journals/$(date +%Y_%m_%d).md`.

**Fallback** se conversation history não expõe cwds visitados → degradar pra single-repo (cwd corrente apenas), reportar warning `coleta multi-repo degraded — só commits do cwd corrente capturados` no Step 6.

### 2.5. Coleta backlog reconciliável (novo em v0.4.0)

Antes de compor síntese, scanear journals na janela retroativa pra identificar markers `TODO`/`DOING`/`WAITING` ativos — input pra fase de reconciliação no Step 3. Mecânica paralela a `/weekly-review` Sub-decisão 5 § Adendo v0.2.0.

#### 2.5.1. Resolve paths dos journals na janela

Shell loop análogo a `/journal-load`:

```bash
for i in $(seq 0 N); do
  date -d "$i days ago" +%Y_%m_%d
done
```

Cada item → path `~/Notes/logseq/journals/<date>.md`. Local TZ alinhado per Adendo v0.2.1 a Sub-decisão 1. Paths ausentes → silent skip (dia inativo).

#### 2.5.2. Coleta de markers ativos por journal

Pra cada journal existente na janela, aplicar regex análoga a `/weekly-review`:

- Regex: `^\t- (TODO|DOING|WAITING) (.*)$` — 1-tab indent, filhas diretas de bucket.
- `DONE`/`CANCELLED` **não** capturados (terminais por design per ADR-002 Sub-decisão 4).
- Markers em sub-bullets (≥2 tabs) **não** capturados — prosa contextual.

Pra cada match capturar:
- Marker (TODO/DOING/WAITING).
- Conteúdo (texto após marker).
- Bucket-pai (`- #<domínio>` ancestor — tree-walk pra trás até linha top-level `^- #` mais próxima).
- Source: path absoluto do journal + line number (referência estável pra modify-in-place no Step 5a).
- Sub-bullets do marker (≥2 tabs imediatamente abaixo até próximo marker ou bucket): contexto não-parsed pra ajudar judgment.

Resultado: **backlog reconciliável** = lista [(marker, conteúdo, bucket, source-path, source-line, sub-bullets), ...] cross-repo.

**Backlog reconciliável vazio** (zero markers na janela): skip fase de reconciliação no Step 3; flow segue v0.3.0 puro (rascunho de novo bucket sem confronto).

### 3. Sintetizar rascunho + fase de reconciliação

#### 3a. Rascunho de narrativa por bucket (v0.3.0 intacto)

Para cada repo/domínio identificado no Step 2b, agente compõe rascunho seguindo template humano-amigável. Estrutura geral (cada seção opcional):

```
- #<repo-basename>
	- <Frame de sessão> — 1 linha situando (ex.: "Sessão `<slug>`" ou "Começou X, desembocou em Y")
	- <Insight central>
		- <sub-bullet de prosa explicando o pivot>
	- DONE <agrupamento conceitual>
		- DONE <task específica>
			- commit: <hash> (opcional)
			- plan: <slug> (opcional)
	- Mudanças finas que ficaram registradas
		- <bullet descrevendo mudança não-codificada>
	- TODO/WAITING Próximos passos
		- TODO <task> — <contexto>
		- WAITING <task> — aguarda <gate>
	- Direção que emerge
		- <bullet de prosa reflexiva>
```

**Princípios editoriais** (v0.3.0 + refinamentos v0.4.1):

- **Linguagem humana 2ª pessoa quando faz sentido editorial** ("você decidiu X", "você rebateu argumento Y").
- **Cada seção opcional** — sessão sem insight pivot omite o bloco; sessão puramente mecânica degrada elegantemente pra DONE-only flat estilo runbook.
- **GTD markers Logseq nativos** (DONE/TODO/WAITING) preservados como block markers, não prefixos prosa.
- **Sub-bullets free-form** per ADR-006 § Decisão § 3 — produzem prose, não só metadata mecânica.
- **`commit:<hash>`/`plan:<slug>` continuam suportados** como metadata opcional sob DONE tasks, não obrigatórios.
- **Cross-refs inline** ([[page]], links markdown) emergem do contexto.

**Granularidade e profundidade** (v0.4.1):

- **DONE granularidade segue conceito, não commit**. Top-level descreve um *movimento* (cristalização doutrinal, migração, ship, refactor); commits e sub-tasks aparecem em sub-bullets só quando carregam contexto. Quando 3-5 commits formaram um movimento conceitual único, agrupar sob **DONE \<conceito\>** com os commits relevantes (não todos) abaixo.
- **Aprofundamento de árvore livre** — leve fundo quanto o material editorial sustentar (insights aninhados, alternativas rejeitadas, sub-tradeoffs, contexto de decisão). Não há teto de profundidade.
- **Sinal de degradação não é profundidade — é o que aparece no próximo nível**. Filtro mental por nível ao descer: "adiciona substância (alternativa rebatida, consequência fina, ressalva) ou só enumeração (mais commits, mais cenários, mais atomic tasks)?". Substância → desce. Enumeração → para; o material já está dito acima.
- **Brevidade vence completude mesmo em sessão rica** — fechamento humano-amigável seleciona; o leitor humano não relê o trabalho inteiro, releme a substância. Sessão rica que produziu 15 commits provavelmente comporta 4-6 DONE top-level conceituais, não 15.

#### 3b. Fase de reconciliação (novo em v0.4.0)

Backlog reconciliável vazio (Step 2.5) → skip esta fase; salta direto pro Step 4.

Backlog reconciliável não-vazio → agente confronta cada entrada com session context (commits + material editorial do Step 2b). Pra cada marker no backlog:

**Critério de match (judgment semântico)** — agente julga se o trabalho da sessão fechou o marker. Sinais:

- **Match textual semântico**: conteúdo do marker corresponde a DONE-task da sessão (ex.: `TODO refactor /journal-close` ↔ `DONE refactor /journal-close v0.4.0`).
- **Cross-ref explícito como hint forte**: marker tem sub-bullet `plan:<slug>` que casa com plan slug da sessão; `commit:<hash>` que casa com commit recente; ou `[[<page>]]` que casa com page tocada.
- **Judgment de domínio**: agente usa contexto da conversa pra decidir se o trabalho fechou o item — não é mecânico. Quando incerto, **não propor** transição (operador pode invocar `/weekly-review` depois pra revisão dedicada).

**Resultado da reconciliação**: lista [(source-path, source-line, marker-original, conteúdo, ação)], onde ação é `→ DONE` (caso comum), `→ CANCELLED` (raro — agente julga que o item virou irrelevante por pivot), ou nenhuma transição (item não foi fechado).

Esta lista alimenta o Step 4 (confirm) e Step 5a (apply).

#### 3c. Caso degenerado

Rascunho vazio (Step 3a) **e** reconciliação vazia (Step 3b) → **recusa silenciosa** com `/journal-close: sessão sem substância pra sintetizar — use /journal-note "<nota>" pra registrar nota livre`. Exit clean. Step 4 não dispara.

Rascunho vazio + reconciliação não-vazia (caso raro — sessão de "fechamento puro" sem DONE-task nova mas TODO antigo cumprido) → prossegue só com transições. Step 4 apresenta lista de transições sem rascunho. Step 5a executa; 5b é no-op.

#### 3d. Rascunho exemplo (sessão rica)

```
- #meta-system
	- Sessão `generalizacao-mecanizacao`
	- Começou querendo decompor `/mechanical-skills-scan` e desembocou em reflexão fundacional sobre packaging mecânico
	- O insight que virou o leme
		- A doutrina assumia MCP-first sem comparar com CLI — assumption camuflada de decisão
		- CLI atende ~igualmente bem em substância mecânica + ganha em ergonomia
	- DONE Duas cristalizações doutrinais
		- DONE [ADR-016](docs/decisions/...) substitui § "Adoção MCP-first" por critério target-aware
			- commit: abc1234
		- DONE [ADR-017](docs/decisions/...) decompõe `/mechanical-skills-scan`
			- commit: def5678
	- TODO Próximos passos
		- TODO `/triage` em `pragmatic-dev-toolkit` materializando núcleo universal
		- WAITING `/triage` em `meta-system` refactorando `/mechanical-skills-scan` — aguarda Faceta 2
	- Direção que emerge
		- Knowledge layer fica mais nuanceada — MCP canonical pra cross-agente; CLI pra runtime auxiliar
```

#### 3e. Rascunho exemplo (sessão simples, runbook)

```
- #drive-sync
	- DONE removido pipx ensurepath do install.sh
		- commit: e56d666
		- plan: install-remover-pipx-ensurepath
```

### 4. Synthesis-then-confirm via AskUserQuestion (estendido em v0.4.0)

**Apresentação ao operador**: prosa antes da chamada enumera (a) rascunho do novo bucket per Step 3a + (b) lista de transições in-place propostas per Step 3b:

```
## Rascunho do novo bucket
<conteúdo per Step 3a>

## Transições in-place propostas
- <source-path>:<source-line> — TODO X → DONE (bucket #Y)
- <source-path>:<source-line> — WAITING Z → DONE (bucket #W)
```

(Reconciliação vazia → omitir seção `## Transições in-place propostas`; comportamento equivalente ao v0.3.0.)

**AskUserQuestion única chamada**:

- header: `Rascunho`
- options:
  - `Confirma rascunho + transições` — write executa rascunho + aplica transições. (Sem transições → label simplifica pra `Confirma rascunho`.)
  - `Edita via Other` — operador descreve em prosa o ajuste. Pode alterar texto do rascunho E/OU rejeitar transições específicas ("aplica só a transição da linha 23, descarta a outra") E/OU reescrever completamente.
  - `Sem substância — não escrever` — abort silente, sessão não vai pro journal.

(Caminho "rascunho vazio + reconciliação vazia" não dispara Step 4 — ver Step 3c recusa silenciosa.)

### 5. Aplicar transições + Find-or-create bucket + append children (atomic-ish em v0.4.0)

Aplicação em ordem fixa:

#### 5a. Aplicar transições in-place (novo em v0.4.0)

Pra cada transição confirmada no Step 4, edit cirúrgico no source path:

- **Localizar linha exata** via (source-path, source-line, marker-original). Match estrito do conteúdo da linha contra captura do Step 2.5.2 — protege contra drift se journal foi editado manualmente entre Step 2.5 e Step 5 (raríssimo dado pgrep gate, mas defensivo).
- **Replace marker**: `\t- TODO <conteúdo>` → `\t- DONE <conteúdo>` (preservar sub-bullets, indent, conteúdo após marker). Mecânica idêntica a `/weekly-review` Sub-decisão 5 § Adendo v0.2.0 archive.
- **Sem annotation extra** sob o marker original — SSOT in-place per ADR-002 Sub-decisão 4 do logseq-notes ("markers nativos como SSOT"). Operador escolheu opção pura via `/triage` 2026-06-12.

**Falha de match** (linha não corresponde mais ao marker esperado por edit concorrente) → skip esta transição com warning `transição abortada: source <path>:<line> não casa marker esperado (edit manual concorrente?)`. Demais transições prosseguem. Reportar count de transições skipped no Step 6.

#### 5b. Find-or-create bucket + append children (v0.3.0 intacto)

Para cada bucket `- #<repo>` do rascunho confirmado:

1. **Probe no journal de hoje**: linha top-level `^- #<repo>($| )` existe?
   - **Existe** → identificar offset; append children sob essa linha. Preserva tasks/bullets já presentes (de `/journal-note` prévios ou invocações anteriores do `/journal-close` na mesma sessão).
   - **Não existe** → append novo bucket top-level no fim do journal; append children sob ele.

2. **Dedup intra-skill (parcial em v0.3.0+)**:
   - **Children com `- commit: <hash>` sub-bullet**: probe pré-write — se mesmo hash já presente sob o bucket, skip esse child.
   - **Children sem metadata `commit:`** (frame, insight, mudanças finas, próximos passos, direção): **sem dedup mecânica**. Operador rodando 2× pode duplicar narrativa — mitigação: `Edita via Other` no 2º run pra revisar.

3. **Append children**: bullets remanescentes (após dedup parcial) sob o bucket, preservando indentação hierárquica do rascunho.

**Idempotência cross-skill com `/journal-note`**: contract crítico mantido per ADR-006 § Decisão § 1 — bucket compartilhado entre skills não duplica.

**Bootstrap journal**: journal de hoje ausente → ler `~/Notes/logseq/pages/daily-journal.md` como template body (scaffold mínimo pós-Onda 4.5).

#### 5c. Caso rascunho vazio + reconciliação não-vazia

Step 5b vira no-op (sem rascunho pra appendar). Step 5a executa transições normalmente. Step 6 reporta só transições aplicadas.

### 6. Reportar

- Path do journal de hoje tocado.
- Buckets tocados (criados/identificados).
- Count de bullets appended (subdivididos: DONE tasks, TODO/WAITING markers, blocos narrativos).
- **Count de transições aplicadas + skipped** (novo em v0.4.0). Skipped lista paths/linhas que abortaram com motivo.

Exit.

## O que NÃO fazer

- Não consumir `pages/session-close.md` — archived per ADR-002 Sub-decisão 2 (compose in-skill).
- Não criar bucket sem antes probar (find-or-create gate idempotência cross-skill com `/journal-note`).
- Não invocar Logseq CLI ou desktop pra renderizar — skill opera filesystem markdown só. Block-ref `((session-close))` NÃO é usada.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não tenta detectar todas as sessões CC ativas — skill assume cwd corrente = repo principal da sessão; multi-repo emerge via conversation context.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
- Não escrever se Logseq desktop aberto (pgrep gate). Failure-closed.
- Não forçar estrutura template rígida — cada seção (frame, insight, mudanças finas, próximos passos, direção) é opcional; sessão simples degrada elegantemente pra DONE-only flat estilo runbook.
- Não 3ª pessoa formal robótica — linguagem 2ª pessoa quando faz sentido editorial.
- Não inflar narrativa — brevidade vence completude quando substância é magra.
- **Não enumerar cada commit como DONE separado** (v0.4.1) quando 3-5 commits formaram um movimento conceitual único — agrupar sob **DONE \<conceito\>** com os commits que carregam contexto em sub-bullets (não todos). Árvore DONE que ao descer só revela mais commits é runbook disfarçado de narrativa; ao descer revelando alternativas rejeitadas, consequências finas ou ressalvas, é narrativa legítima.
- **Não capturar detalhes técnicos-operacionais em "Mudanças finas"** (v0.4.1) — version pins de cache, paths absolutos, workarounds shell, byte counts, contagens de cenários de smoke test, IDs de memory entries. Filtrar por critério "isto vai informar futuras decisões?" — debug notes de um momento quase sempre falham. Pattern semântico passa; trace de execução não.
- **Não criar seções operacionais cronológicas** (v0.4.1) — "Pre-trabalho que estruturou a sessão", "Validações por carregamento manual", "Allowlist X — N classificados". Sessão se descreve pela substância editorial (insights, decisões, direção), não pela cronologia das fases que ela atravessou. Substância de QA/pre-trabalho cabe sob DONE conceitual relevante (sub-bullet "validado em N cenários" se valer) ou desaparece se não passar o filtro de inclusão.
- **Não anotar sub-bullet `→ closed em sessão X` sob marker original quando aplica modify-in-place** (novo em v0.4.0) — SSOT in-place per ADR-002 Sub-decisão 4 (transição = marker change; trail explícito vira redundância). Operador rejeitou opção "annotation cross-ref" via `/triage` 2026-06-12.
- **Não criar bullet `DONE X (closes TODO de YYYY-MM-DD)` no novo bucket** (novo em v0.4.0) — same SSOT logic (DONE no novo bucket é registro novo do trabalho; closure de antigo é marker change in-place; redundância elimina-se naturalmente).
- **Não estender janela retroativa default sem `--days N`** (novo em v0.4.0) — N=0 é o caso comum (sessões mesmo-dia); N>0 é opt-in explícito.
- **Não propor transição em matches incertos** (novo em v0.4.0) — quando judgment não confirma fechamento, deixar marker intocado. `/weekly-review` cobre revisão dedicada de itens ambíguos.
- **Não modificar markers em sub-bullets** (≥2 tabs) — regex restrita a 1-tab indent per Sub-decisão 5 § Adendo v0.2.0; markers nested são prosa contextual.
- Não capturar `DONE`/`CANCELLED` como reconciliáveis — terminais por design (ADR-002 Sub-decisão 4); não re-abrem.
