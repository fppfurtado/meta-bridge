---
name: journal-close
description: Sintetiza sessão CC no journal Logseq de hoje — narrativa humano-amigável agrupada por #domínio (DONE + TODO/WAITING + insights) + reconciliação prévia (--days N)
disable-model-invocation: false
---

# journal-close

Thin orchestrator do subcomando `mb journal-close` (CLI `meta-bridge`). Skill compõe payload editorial (síntese humano-amigável + transições in-place já decididas) e delega o write determinístico (find-or-create bucket, dedup por commit hash, modify-in-place atomic, bootstrap journal, gate Logseq) ao CLI.

Substância editorial (matching semântico, princípios de granularidade, filtros) é **heurístico-semântica** e **fica integralmente na skill**. CLI vira write engine — recebe payload via stdin e aplica writes sem refazer judgment.

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 3 (+ Adendos v0.3.0/v0.4.0/v0.4.1) e [ADR-002](../../docs/decisions/ADR-002-materializacao-cli-mb.md) § Decisão 3.

## Argumentos

Flag opcional para janela de reconciliação prévia.

```
/journal-close              # default: só hoje
/journal-close --days 3     # hoje + 3 dias retroativos
/journal-close --days 7     # janela semanal
```

- `--days N`: inteiro N ≥ 0. Default 0 = só hoje. Estende leitura retroativa pra reconciliar TODOs antigos fechados pela sessão. Síntese **sempre** vai no journal de hoje. **Escopo**: `--days N` afeta **apenas** o backlog scan do Step 2.5; coleta de commits no Step 2 sempre usa janela da sessão CC corrente (não estende retroativamente).

## Passos

### 1. Gates editoriais (skill)

`git rev-parse --show-toplevel` falha → recusa com `/journal-close exige git repo`. Exit clean.

(Gate `pgrep -xi logseq` fica no CLI — failure-closed na chamada.)

### 2. Coleta context da sessão (heurístico-semântico — fica na skill)

- **Repo basename principal**: `basename $(git rev-parse --show-toplevel)`.
- **Plan slug ativo** (probe ordenado): env `PRAGMATIC_ACTIVE_PLAN_SLUG` → `find docs/plans -name '*.md' -newermt '2 hours ago'` → omitido.
- **Commits multi-repo**: enumerar cwds visitados na sessão; `git log --since="<start>" --oneline --no-merges` em cada. `<start>` = timestamp do início da sessão CC corrente (não estender por `--days N` — esse afeta só o Step 2.5).
- **Material editorial** via conversation context — filtros de seleção v0.4.1:
  - Frame de sessão (1 linha).
  - Insight/pivot conceitual (1-2 por sessão).
  - Mudanças finas: critério "isto vai informar futuras decisões?".
  - Próximos passos enunciados pelo operador (TODO/WAITING).
  - Direção emergente (1-3 bullets curtos).
  - Cross-refs ([[page]], links).
- Sessão sem substância editorial além de DONE-tasks → degradar elegantemente pra runbook simples.

### 2.5. Coleta backlog reconciliável (regex mecânico — pode ser via Bash)

Pra cada journal na janela `--days N`, scan regex `^\t- (TODO|DOING|WAITING) (.*)$` (1-tab indent). Capturar (marker, conteúdo, bucket-pai, source path/line, sub-bullets). `DONE`/`CANCELLED` não capturados (terminais).

Backlog vazio → skip reconciliação no Step 3b.

### 3. Sintetizar rascunho + matching semântico (skill)

#### 3.0. Checklist editorial pré-composição (v0.4.3)

Antes de compor, internalizar os 6 antipadrões v0.4.1 + sinais de 2ª pessoa. Cada item é gatilho de revisão durante a composição — não checklist mecânico pós-fato.

1. **Frame como trajetória X→Y, não metadata-at-end** — "Sessão atravessou A → B → C" ou "Começou querendo X, desembocou em Y". *Antipadrão*: "Sessão `slug` cristalizou Z — 8 blocos, 11 commits, PR mergeado" (metadata-end soa runbook).
2. **Insight ancorado em momento-de-descoberta, não em enunciado de resultado** — "A doutrina assumia X sem comparar com Y — assumption camuflada de decisão"; "O loop fechou sobre si mesmo". *Antipadrão*: "O insight central foi a divisão A/B via F3/F2 absorvidas" (enuncia resultado, não evoca virada).
3. **DONE granularidade segue conceito, não commit** — quando 3-5 commits formaram um movimento, agrupar sob `DONE <conceito>` com sub-bullets que carregam contexto. *Antipadrão*: "DONE `mb subA` + `subB` + `subC` + `subD`" (enumeração inline em uma linha).
4. **Sem repetição inter-seções** — se "filosofia X revogada" aparece em `DONE Realign`, não repetir em `Direção que emerge`. Cada seção carrega substância distinta; redundância dilui.
5. **Mudanças finas: 1-2 linhas densas por bullet**, não 2-3 linhas com explicação interna. *Antipadrão*: bullet que entrega rationale embedded — promover pra `Insight` ou condensar.
6. **2ª pessoa como sinal de quality** — 4-8 ocorrências por bucket em sessão rica ("você decidiu", "você rebateu", "você escolheu", "você optou"). 1 ocorrência em 30+ linhas é sinal de drift procedural. Não é meta a bater — é tom dialógico do exchange operator↔agente.

#### 3a. Rascunho narrativa por bucket (template humano-amigável)

Compor in-skill seguindo princípios editoriais v0.3.0 + v0.4.1: linguagem 2ª pessoa, seções opcionais (Frame/Insight/DONE/Mudanças/TODO/Direção), GTD markers nativos, granularidade DONE por conceito (não commit), aprofundamento de árvore livre quanto material sustente, brevidade vence completude.

#### 3a-bis. Exemplo de sessão rica (anchor inline)

```
- #meta-system
	- Sessão `generalizacao-mecanizacao` (antes `mechanical-skills-scan-decomposition`)
	- Começou querendo decompor `/mechanical-skills-scan` e desembocou em reflexão fundacional sobre como temos packagado mecânica na constelação
	- O insight que virou o leme
		- A doutrina assumia MCP-first sem ter comparado com CLI — assumption camuflada de decisão
		- CLI atende ~igualmente bem em substância mecânica determinística e ganha em ergonomia
		- Você rebateu meu argumento de "custo > benefício"; qualidade ganha
	- DONE Duas cristalizações doutrinais
		- DONE [ADR-016](docs/decisions/...) substitui § "Adoção MCP-first" por critério target-aware
			- commit: abc1234
		- DONE [ADR-017](docs/decisions/...) decompõe `/mechanical-skills-scan` em duas camadas
			- commit: def5678
	- Mudanças finas que ficaram registradas
		- Feedback memory refinada: "custo de migração isolado é argumento epistemicamente fraco; precisa ser pesado contra ganho de qualidade tangível"
		- Dual-entry pattern pra fronteira cross-repo BACKLOGs reconhecido explicitamente
	- TODO Próximos passos
		- TODO `/triage` em `pragmatic-dev-toolkit` materializando núcleo universal (Faceta 2 — precedente das demais)
		- WAITING `/triage` em `meta-system` refactorando `/mechanical-skills-scan` (Faceta 3) — aguarda Faceta 2
	- Direção que emerge
		- Knowledge layer fica mais nuanceada — MCP canonical pra interfaces cross-agente; CLI pra runtime auxiliar
		- O maior beneficiário operacional é o `prompt.py` do h3-finance-agent — análise mecanicidade finalmente fica acionável
```

Sinais editoriais a observar no exemplo: Frame em 2 linhas (slug + X→Y); Insight com 3 sub-bullets onde 1 é 2ª pessoa ("você rebateu"); DONE conceitual agrupando 2 cristalizações; Mudanças finas em 2 linhas densas; Direção que emerge não repete substância dos DONEs.

#### 3a-ter. Exemplo de sessão simples runbook (degradação elegante)

```
- #drive-sync
	- DONE removido pipx ensurepath do install.sh
		- commit: e56d666
		- plan: install-remover-pipx-ensurepath
```

Sessão sem insight pivot, sem mudanças finas, sem direção emergente — degrada pra DONE-only flat. Não inflar; nem todo fechamento merece narrativa rica.

#### 3b. Matching semântico TODOs ↔ DONEs da sessão (skill)

Pra cada marker do Step 2.5, agente julga se trabalho da sessão fechou:
- Match textual semântico.
- Cross-refs explícitos (`plan:`, `commit:`, `[[page]]`) como hint forte.
- Judgment conservador: incerto → **não** propor transição.

Resultado: lista de transições `(source-path, source-line, marker→DONE|CANCELLED)`.

#### 3c. Probe externo cross-repo de "Próximos passos"

Refinamento preventivo contra entries WAITING/TODO forward-looking stale no rascunho recém-composto. Step 2.5 + Step 3b probam TODOs do journal contra DONEs da sessão; este step proba WAITINGs/TODOs cross-repo **do rascunho** contra estado **atual** dos repos cross-ref'd. Gap original surfou via drift in vivo (sessão `remote-control` 2026-06-19) — ver ADR-001 § Sub-decisão 3 Adendo v0.4.4.

1. **Identificar pares `(entry, repo)`** no rascunho — para cada WAITING/TODO cuja linha (ou cujo sub-bullet imediato) contém ref cross-repo casando um dos 3 patterns alternativos:
   - `cwd <repo>` (forma comum em "Próximos passos" do template humano-amigável)
   - `~/Projects/<repo>` (path-explícito)
   - `[[fppfurtado/<repo>...]]` (page-link Logseq)

   Entries sem ref cross-repo ficam fora do probe. Lista de repos derivada dos pares é de-duplicada para o sub-passo 2.

2. **Para cada repo identificado** rodar `git log --since="48 hours ago" --oneline -15` com cwd absoluto `$HOME/Projects/<repo>`.
   - **Fail-soft** (cwd inexistente, não-git, permissão etc.): reportar in-prosa pré-Step 4 `git log falhou em <repo>: <erro literal> — prosseguindo sem probe deste repo` e seguir. Sem skip silente — operador ciente sem bloqueio.

3. **Matching semântico in-skill** (per ADR-002 § Decisão 3) entre cada WAITING/TODO cross-repo do rascunho e os commit subjects retornados. Judgment **conservador** (alinhado a Step 3b: "incerto → não propor transição"); cross-refs explícitos no sub-bullet do WAITING (commit hash, plan slug, `[[page]]`) valem como hint forte.

4. **Match found → remoção silente da entry do rascunho** + **nota in-prosa pré-Step 4 preview**, segmentada por repo quando multi-repo:
   - Single repo, 1 entry: `Step 3c removeu 1 entry cross-repo stale: <entry literal> [fechada por <repo> commit <hash>: <subject>]`.
   - Multi-repo: `Step 3c removeu N entries cross-repo stale: [<repo-a>] <entryA> [fechada por commit <hashA>: <subjectA>]; [<repo-b>] <entryB> [fechada por commit <hashB>: <subjectB>]`.

**Composição das notas in-prosa do Step 3c**: emitidas como bloco único pré-`AskUserQuestion` do Step 4, na ordem `falhas primeiro → remoções depois`, cada evento como bullet separado. Sessão multi-repo onde 1 repo falha e outro tem match gera 2 bullets no mesmo bloco; sessões com múltiplas falhas ou múltiplos matches preservam 1 bullet por evento.

Step 4 preview vê rascunho já resolvido (entries stale ausentes) e recebe explicitamente a nota in-prosa do 3c como terceiro substantivo apresentado; operador inspeciona a nota e pode reverter via `Edita via Other` se discordar (ex.: "reincluir entry X — o commit não fechou de fato").

**Trade-off explícito do SSOT in-place** (paralelo a Adendo v0.4.0): a remoção **não** entra como `## Transitions` no payload do CLI; write engine não vê a remoção como transição mecânica. Auditabilidade pós-fato depende inteiramente da nota in-prosa + judgment do operador no AskUserQuestion. Coerente com filosofia "SSOT in-place do journal não recebe footprint do probe cross-repo".

#### 3d. Caso degenerado

Rascunho vazio (sem nenhum bullet de substância editorial — DONE/Frame/Insight/TODO/WAITING/Mudanças/Direção) + transições vazias → recusa silenciosa. Entries removidas pelo Step 3c não contam contra (já saíram do rascunho).

### 4. Preview-first via AskUserQuestion (skill)

Apresentar 3 substantivos em prosa antes do enum: (a) rascunho composto pelo Step 3a, (b) transições do Step 3b, (c) **nota in-prosa do Step 3c** quando presente (probe externo cross-repo emitiu falhas ou remoções). `AskUserQuestion` header `Rascunho`:
- `Confirma rascunho + transições`.
- `Edita via Other` — operador descreve ajuste.
- `Sem substância — não escrever`.

**Dispatch por opção**:
- `Confirma` → seguir Step 5.
- `Edita via Other` → re-compor Step 3a/3b absorvendo o ajuste; **Step 3c não re-roda na re-composição** (probe é one-shot por invocação — operador já viu a nota in-prosa e decidiu; entries reintroduzidas via Other ficam preservadas mesmo casando commits cross-repo); voltar para Step 4 com rascunho atualizado.
- `Sem substância` → recusa silenciosa, exit clean (Step 5 não dispara).

### 5. Invocar `mb journal-close` (CLI write engine)

Compor payload markdown estruturado e pipe via stdin:

```
## Append

- #<bucket>
	- <rascunho confirmado>

## Transitions

- <source-path>:<line> | \t- TODO X | \t- DONE X
- <source-path>:<line> | \t- WAITING Y | \t- DONE Y
```

`echo "$PAYLOAD" | mb journal-close`. Output reporta journal/buckets/transitions/dedup — repassar ao operador.

CLI faz: ordem fixa transitions → find-or-create + dedup por commit hash → append children. Bootstrap journal se ausente. Sem annotation extra (SSOT in-place per ADR-002 do logseq-notes Sub-decisão 4).

## O que NÃO fazer

- **Não duplicar substância (find-or-create, modify-in-place, dedup, bootstrap)** — vive em `meta_bridge.journal_close`.
- Não anotar sub-bullet `→ closed em sessão X` sob marker original — SSOT in-place per ADR-002 do logseq-notes Sub-decisão 4.
- Não criar bullet `DONE X (closes TODO de YYYY-MM-DD)` no novo bucket — same SSOT logic.
- Não propor transição em matches incertos — judgment conservador.
- Não modificar markers em sub-bullets (≥2 tabs) — prosa contextual.
- Não capturar `DONE`/`CANCELLED` como reconciliáveis — terminais por design (ADR-002 Sub-decisão 4 do logseq-notes).
- **Não enumerar cada commit como DONE separado** (v0.4.1) quando 3-5 commits formaram um movimento conceitual único — agrupar sob **DONE \<conceito\>**.
- **Não capturar detalhes técnicos-operacionais em "Mudanças finas"** — filtrar por "isto vai informar futuras decisões?".
- **Não criar seções operacionais cronológicas** — sessão se descreve pela substância editorial, não pela cronologia.
- Não inflar narrativa — brevidade vence completude quando substância é magra.
- Não 3ª pessoa formal robótica — linguagem 2ª pessoa quando faz sentido editorial.
- **Não bloquear o fluxo em falha de `git log` cross-repo no Step 3c** — fail-soft com warning visível pré-Step 4 preserva probe parcial sem custo de interrupção. Operador ciente do gap de cobertura sem perder a síntese de hoje.
- Não fazer commit em logseq-notes — repo de notes tem ciclo próprio.
- Não auto-fechar plan ativo (`/run-plan`-style done) — `/journal-close` é registro de sessão, não fechamento de plano.
