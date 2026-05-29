---
name: weekly-review
description: Wizard GTD weekly review consumindo task markers cross-journals (TODO/DOING/WAITING top-level)
disable-model-invocation: false
---

# weekly-review

Wizard GTD que itera tasks `TODO`/`DOING`/`WAITING` em buckets `- #<domínio>` de journals recentes, prompto operador a classificar cada item (Manter / Próximo passo / Arquivar / Adiar), aplica mudanças no graph, e escreve bloco semanal no journal de hoje (composição in-skill — sem template).

Mecânica concreta em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 5 (+ Adendo v0.2.0). Consome [ADR-006 do meta-system](https://github.com/fppfurtado/meta-system/blob/main/docs/decisions/ADR-006-logseq-pkm-cross-domain-via-gtd-e-hashtag-buckets.md) + [ADR-002 do logseq-notes](https://github.com/fppfurtado/logseq-notes/blob/master/docs/decisions/ADR-002-retrofit-daily-journal-formato-gtd-hashtag.md).

Skill **não consome papéis canonical do toolkit** (Resolution protocol per ADR-003 do `pragmatic-dev-toolkit`, aplicado vazio). Cutucada de descoberta **não aplica**.

## Argumentos

Sem argumentos. Skill opera sobre `~/Notes/logseq/journals/` cross-files.

## Passos

### 1. Gate Logseq desktop

`pgrep -xi logseq` → truthy: recusa com `Logseq desktop aberto — feche antes de executar /weekly-review (skill escreve direto no filesystem do graph)`. Exit clean.

(Gate de git repo **removido** vs v0.1.x — `/weekly-review` opera sobre journals do graph, não deriva nada do cwd.)

### 2. Coleta tasks via grep cross-journal por markers nativos

Resolve metadata:

- **Journals dir**: `~/Notes/logseq/journals/`. Ausente → recusa com `Logseq journals dir ausente em ~/Notes/logseq/journals/ — graph não configurado`. Exit.
- **Janela temporal**: últimos 7 dias **excluindo journal de hoje** (range `[hoje-7d, hoje-1d]`). Razão: bloco semanal escrito no journal de hoje pode duplicar com tasks de hoje se incluído. Lista: `find ~/Notes/logseq/journals -name '*.md' -newermt '7 days ago' ! -newermt 'today'` (fixo nesta versão per ADR-001 Sub-decisão 5; reabrir via Gatilho 3).

**Coleta via regex strict** (per F1 do /triage do plano `onda-4-5-journal-retrofit-gtd`): tasks válidas são **filhas diretas de bucket `- #<domínio>`** — 1 nível de indentação (1 tab). Markers em sub-bullets (≥2 tabs) **não são capturados** — viram prosa contextual per ADR-006 § Decisão § 3 mental model.

Regex de match: `^\t- (TODO|DOING|WAITING) (.*)$` (1 tab indent + marker + espaço + conteúdo). `DONE` e `CANCELLED` são terminais — não entram no backlog por design (per ADR-002 Sub-decisão 4).

Para cada match enriched, captura:
- **Marker**: `TODO` / `DOING` / `WAITING`
- **Conteúdo**: texto após o marker
- **Bucket pai** (`- #<domínio>` ancestor): tree-walk pra trás na file procurando linha top-level `^- #` mais próxima. Fallback se não houver bucket-pai detectável → `#<orfão>` (raro — captura de pre-retrofit ou edição manual quebrada).
- **Sub-bullets do task** (≥2 tabs imediatamente abaixo, até próximo task ou bucket): coletados como **contexto não-parsed** (prosa pra humano).
- **Source**: file path + line number do match.

**Truncate**: max 20 itens por marker (60 total potencial). Excesso → warning `<marker> tem <N> tasks; truncado em 20. Marker precisa atenção dedicada — invoque /weekly-review novamente após classificar primeiros 20.`

**Listas vazias** (TODO + DOING + WAITING = 0) → recusa silenciosa com mensagem `Sem tasks abertas pra review nos últimos 7 dias de journals. Nada a fazer.`. Exit clean.

### 3. Wizard iterativo de classificação (decisões acumuladas, edits deferred)

Skill **acumula decisões em memória** durante wizard; edits no graph aplicam **somente após** Step 4 compor o bloco semanal (atomic-ish). Crash/cancel mid-wizard → zero side-effect no graph; operador re-invoca sem state parcial.

Para cada item, prosa antes do enum apresenta o contexto:

```
**TODO/DOING/WAITING** em [[<bucket-pai>]] (de <YYYY-MM-DD>):
  <conteúdo do task>
  Sub-bullets (contexto):
    - <sub-bullet 1>
    - <sub-bullet 2>
    ...
```

Em seguida, batch de 4 perguntas por chamada `AskUserQuestion` (cardinality max per CLAUDE.md do toolkit):

- Header: `Task N/M` onde N = índice corrente, M = total geral (não por marker).
- Question: `Como classificar?`
- Options:
  - `Manter aqui` — task permanece intocada (decision = `keep`).
  - `Próximo passo definido` — Other → operador descreve próximo passo em prosa livre (decision = `next_step`, payload = descrição).
  - `Arquivar` — task recebe marker `DONE` ou `CANCELLED` (operador escolhe via sub-prompt; default `DONE` se operador omite). decision = `archive`.
  - `Adiar próxima semana` — task move pra journal de próxima segunda-feira (decision = `defer`).

Após N % 4 == 0 (cada 4 itens), check progresso via `Continuar? <X/M itens restantes>` enum: `Continuar / Pausar e fechar resumo parcial`. Pausa → pula direto pra Step 4 com decisões coletadas; itens não-vistos recebem decision sentinel `not_reviewed` (aparecem no bloco semanal com sufixo `[não-revisado]`, sem edit no source).

**Cálculo "próxima segunda"** pra decisão `defer`: `$(date -u -d 'next Monday' +%Y_%m_%d)`. Comportamento GNU date: `defer` aponta sempre para a próxima ocorrência de segunda-feira; review feito final-de-semana → defer pra próxima segunda (1-2 dias à frente). Em segunda, "next Monday" pula 7 dias (intencional — operador adiando segunda quer next-next monday). Task move pra journal de destino sob **bucket de origem** (`- #<domínio>` mesmo do source). Bucket ausente no journal de destino → find-or-create (mesma mecânica de `/journal-note` Step 4).

**Defer em task órfã** (bucket-pai = `#<orfão>` — raro, sintoma de captura quebrada pre-retrofit): sub-prompt extra via `AskUserQuestion` pedindo bucket de destino. Operador digita `#<tag>` livre (sanitization kebab-case lowercase aplicada per ADR-002 Sub-decisão 3). Cancel/Empty → degrade pra `keep` com warning `task órfã sem bucket de destino; defer abortado, mantida como-está`.

**Sub-bullets do task original**: preservados no defer (acompanham a task pro journal de destino) e no archive (continuam como prosa abaixo do task com marker terminal). No `next_step`, a descrição do próximo passo é appended como sub-bullet adicional.

### 4. Compor bloco semanal in-skill (sem template)

Sem consumer de template — composição direta seguindo formato:

```
- ## Weekly review — <YYYY-MM-DD>
	- ## TODO classificados
		- <task 1> [<sufixo decisão>]
		- <task 2> [<sufixo decisão>]
		...
	- ## DOING classificados
		- <task 1> [<sufixo decisão>]
		...
	- ## WAITING classificados
		- <task 1> [<sufixo decisão>]
		...
	- ## Decisões da semana
	- ## Próxima semana
```

Sufixos por decisão:
- `keep` → sem sufixo
- `archive` → `[arquivado: <marker terminal>]` (DONE ou CANCELLED escolhido no wizard)
- `next_step` → `[próximo passo: <descrição truncada em 80 chars + "..." se exceder>]` (descrição completa permanece no source — Step 5 append como sub-bullet do task)
- `defer` → `[adiado pra <YYYY-MM-DD>]`
- `not_reviewed` → `[não-revisado]`

Headings `## Decisões da semana` e `## Próxima semana` ficam como skeleton vazio — operador edita depois manualmente no Logseq desktop.

Data: `$(date -u +%Y-%m-%d)` literal (UTC, alinhado com journal filename pattern).

### 5. Aplicar edits batch + Append no journal de hoje

**Atomic-ish batch** (deferred do Step 3): para cada decisão acumulada em memória, aplica edit no source file na ordem coletada:

- `archive` → muda marker do task no source de `TODO`/`DOING`/`WAITING` pra terminal escolhido (`DONE` ou `CANCELLED`). Marker change **in-place no journal source** — markers terminais ficam onde a task viveu, sem mover pra journal de hoje (per ADR-002 Sub-decisão 4 do logseq-notes: markers como SSOT in-place). Sub-bullets preservados.
- `next_step` → adiciona linha sub-indented `\t\t- <descrição>` como sub-bloco do task source.
- `defer` → move task (linha + sub-bullets nested) do source file pro journal de destino sob bucket de origem (find-or-create bucket no destino; criar journal se ausente via daily-journal template body copy — mesma mecânica de `/journal-note` Step 3 — scaffold mínimo per ADR-002 Sub-decisão 1).
- `keep` / `not_reviewed` → no-op (source preservado).

Após todos os edits source, **append do bloco semanal** no journal path de hoje (`~/Notes/logseq/journals/$(date -u +%Y_%m_%d).md`):

- Journal existe → append no fim do file (bloco semanal é top-level resultado da review, não tenta find-or-create dentro de bucket).
- Journal ausente → criar via leitura do daily-journal template (mesma mecânica do `/journal-note` Step 3); append do bloco no fim.

### 6. Reportar

Resumo final:
- Total de itens classificados por marker (TODO/DOING/WAITING).
- Distribuição de classificações (`X mantidos, Y arquivados, Z adiados, W com próximo passo`).
- Path do journal tocado.

Exit.

## O que NÃO fazer

- Não filtrar por `status:: active` ou `status::` qualquer — essa property é lifecycle de Project Page per ADR-004 do meta-system; coleta via marker grep é o pattern doutrinário pós-retrofit.
- Não capturar markers em sub-bullets (≥2 tabs) — regex restrita a 1-tab indent per ADR-006 § Decisão § 3 contract (sub-bullets são prosa não-parsed; ADR-002 Sub-decisão 4 confirma — `/weekly-review` v0.2.0+ olha só markers open top-level).
- Não capturar `DONE` ou `CANCELLED` no backlog — markers terminais; audit retrospectivo via leitura direta do journal ou query Logseq Datalog ad-hoc.
- Não rodar queries Logseq Datalog — desktop fechado por gate; grep direto via filesystem markdown é canonical.
- Não persistir state entre invocações — skill é stateless; cada invocação re-parse a janela.
- Não consumir `pages/weekly-review.md` — template descontinuado pós-retrofit (composição in-skill paralelo a `/journal-close` v0.2.0).
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não parametrizar truncate (20) ou janela (7d) hardcoded — flags `--max-items <N>` / `--window-days <N>` reabrem via Gatilho 3 do ADR-001 se sinal real surgir.
- Não tenta escrever em pages/<categoria>.md aggregator-style — review é per-journal aggregation, não materializa view permanente fora do journal de hoje.
- Não incluir journal de hoje na janela de coleta — bloco semanal é appended em journal de hoje; incluí-lo duplicaria items vivos com snapshot.
- Não escrever se Logseq desktop aberto (pgrep gate). Failure-closed.
