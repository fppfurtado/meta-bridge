# ADR-003: write-path HTTP via Logseq Local HTTP Server (modalidade aditiva ao file-direct)

**Data:** 2026-06-25
**Status:** Proposto

**Próxima revisão:** 2026-12-25
**Cadência:** trimestral
**Critério de erosão auditável:** Reabrir se a Logseq HTTP API local (porta 12315) for descontinuada ou instabilizar a ponto de exigir reversão ao write file-direct como único caminho; OU se pragmatic-dev-toolkit#154 materializar a abstração de backend de forma que absorva/torne redundante este substrato thin.

## Origem

- **Decisão base:** [ADR-002](ADR-002-materializacao-cli-mb.md) — materialização do CLI `mb` com write engine file-direct. Este ADR **estende** ADR-002: HTTP é modalidade aditiva, não substituição.
- **Contrato pai:** meta-system#54 / ADR-025 (coerência cross-store, em vigor) — define semântica SSOT/dual-entry. Este ADR é materialização-filho local, não redefine o contrato pai.
- **Investigação:** issue [#41](https://github.com/fppfurtado/meta-bridge/issues/41); validação empírica da API 2026-06-24 (`appendBlockInPage`, datascript query, `upsertBlockProperty` confirmados com Logseq aberto).

## Contexto

O write engine atual do `meta_bridge` escreve markdown direto no filesystem (`~/Notes/logseq/`), com gate `pgrep` que exige o **Logseq fechado** para evitar corrupção de escrita concorrente com o app. Esse gate impede escrita enquanto o operador usa o Logseq — fricção real para fluxos de abertura/fechamento de sessão.

A constelação de coerência cross-store (meta-system#54 / ADR-025) precisa de um caminho de escrita que opere com o **Logseq aberto**: o backend `logseq` do role `annotations` (pragmatic-dev-toolkit#154) e o reconciler (meta-bridge#42) ambos escrevem reconciliações/anotações no grafo em tempo de sessão. Sem um substrato HTTP comum, cada consumidor reimplementaria o acesso à Logseq Local HTTP Server.

A Logseq Local HTTP Server expõe a SDK de plugin sobre HTTP em `127.0.0.1:12315` com auth bearer-token. A superfície necessária é pequena (append de bloco, upsert de property, datascript query) e já foi validada empiricamente.

## Decisão

Adicionar ao `meta_bridge` um **substrato thin de write-path HTTP** (`meta_bridge/logseq_http.py`) que expõe os primitivos validados sobre a Logseq Local HTTP Server, **aditivo** ao write engine file-direct (que permanece inalterado e mantém seu gate `pgrep`).

Razões objetivas:

- **Aditivo, não substituto:** file-direct continua o caminho default das skills do plugin; HTTP é capacidade nova consumível. O gate-kill das skills do próprio plugin (passar a escrever via HTTP com Logseq aberto) é follow-up separável, fora deste escopo.
- **Build thin client (não adotar lib):** wrappers Python da Logseq HTTP API existem mas são finos e majoritariamente não-mantidos; a superfície é 3-4 métodos. Construir sobre `urllib` stdlib honra a filosofia minimalista de deps (hoje só `click` + `rapidfuzz`) — zero dep nova.
- **Config de token em arquivo dedicado:** token lido de `~/.config/meta-bridge/config.json` (path canonical novo, hardcoded como os demais runtime paths), desacoplado do `settings.json` do Claude Code; endpoint default `http://127.0.0.1:12315`. Token nunca logado.
- **Substrato reutilizável cross-process:** superfície CLI mínima — `mb logseq-append` + `mb logseq-set-prop` (escrita) e `mb logseq-query` (leitura, **experimental/não-congelada** até #42 fixar a forma da query que precisa) — permite que toolkit#154 (repo separado, não importa `meta_bridge`) e o reconciler #42 consumam sem reimplementar. Uma vez que #154/#42 dependam dela, a assinatura de **escrita** `mb logseq-append`/`mb logseq-set-prop` vira **contrato cross-repo estável** — mudanças de assinatura exigem coordenação cross-repo, não são refactor local livre (análogo ao marker `[PRAGMATIC: plan-done]` que o `CLAUDE.md` trata como contrato público). A superfície de query fica fora desse congelamento até #42 confirmar.

## Consequências

### Benefícios

- Escrita no grafo com Logseq aberto — destrava os fluxos de coerência cross-store (#154, #42).
- Substrato único e testado, evitando reimplementação do acesso HTTP em cada consumidor.
- Zero dep nova; aderente à filosofia minimalista.

### Trade-offs

- Nova superfície de erro (Logseq fechado, server desabilitado, token inválido) que precisa de tradução clara para o operador, não stacktrace.
- Novo runtime path hardcoded (`~/.config/meta-bridge/config.json`) e dependência operacional do operador habilitar o Local HTTP Server + configurar token forte.
- **Relação com o gate `pgrep` (ADR-001 SD7 + Adendo 2026-06-12):** o write HTTP é uma **3ª categoria** de relação com o gate failure-closed — não é write file-direct (gated, exige Logseq fechado) nem skill read-only (isenta por ausência de side-effect no graph); é write-via-API-do-Logseq, seguro com o desktop **aberto** porque a serialização da escrita é responsabilidade do próprio Logseq, não do filesystem. Não **inverte** a SD7 — a estende com uma categoria que a redação original não contemplava. O gate-kill follow-up das skills do plugin herda essa articulação.
- **Coexistência de dois write-paths ao mesmo grafo:** file-direct (Logseq fechado) e HTTP (Logseq aberto) são **mutuamente exclusivos pelo estado do ambiente** — o gate `pgrep` garante que file-direct só roda com o app fechado, então não há janela de escrita simultânea conflitante. File-direct permanece o caminho canônico das skills do plugin per § Decisão; fecha a faceta SSOT que o contrato pai ADR-025 vigia.
- **Blast radius do token:** o token concede, via API de plugin do Logseq, **read (datascript) + write do grafo inteiro** — vazamento expõe todo o cognitive hub. Daí config dedicado com permissão frouxa **avisada no load** (warning em stderr no check `0o077`, não bloqueio), e a exigência de token forte — o que também reforça objetivamente o descarte da alternativa `settings.json` (acoplaria esse secret de alto privilégio ao runtime do Claude Code).

### Limitações

- Não mata o gate `pgrep` das skills do plugin — isso é follow-up explícito (caminho backend-switch deferido na bifurcação do /triage).
- A abstração de backend selecionável genérica não vive aqui; vive em toolkit#154.

### Mitigações

- Higiene de segurança: o smoke 2026-06-24 usou token fraco `teste` — rotacionar/desabilitar antes de uso real (capturado em backlog).
- Suite pytest cobre parsing de resposta HTTP + carregamento de config + caminhos de erro (critério parsing-complexo per ADR-002).

## Alternativas consideradas

### Adotar lib de client Logseq HTTP existente

Descartada: wrappers disponíveis são finos e não-mantidos; adicionar dep contraria a filosofia minimalista para uma superfície de 3-4 métodos já validada.

### Backend-switch imediato no write engine (matar o gate `pgrep` agora)

Descartada para o escopo original deste ADR: refatorar `journal_close`/`journal_note`/`logseq.py` atrás de abstração de backend acopla o substrato à migração das skills do plugin. Deferido como follow-up — o substrato thin prova o primitivo primeiro. Follow-up materializado em [#43](https://github.com/fppfurtado/meta-bridge/issues/43) (ver **Adendo 2026-06-28** abaixo).

### Token via `settings.json` env (precedente do secret MCP)

Descartada: reusa precedente mas acopla o token de escrita do grafo ao runtime do Claude Code. Arquivo de config dedicado mantém o secret desacoplado e legível por qualquer consumidor cross-process do `mb`.

## Adendo 2026-06-28 — Gate-kill das 4 skills do plugin (#43)

Issue [#43](https://github.com/fppfurtado/meta-bridge/issues/43) materializa o follow-up deferido na alternativa "Backend-switch imediato" acima: os 4 subcomandos de write das skills do plugin (`mb journal-note`, `mb journal-close`, `mb journal-review --apply`, `mb init-project`) ganham **dual-path automático** — HTTP quando Logseq aberto, file-direct quando fechado. Gate `fail_if_logseq_open()` removido de todos os 4.

**Padrão de implementação (ADR-001 SD20):** cada command-handler verifica `logseq_open()` (wrapper em `cli.py` sobre `pgrep -xi logseq`):

```python
if logseq_open():
    try:
        _cmd_via_http(...)
    except LogseqHTTPError as exc:
        click.echo(f"Logseq HTTP error — fechar o Logseq ou verificar o Local HTTP Server.\n{exc}", err=True)
        sys.exit(1)
    return
# caminho file-direct inalterado abaixo
```

**Failure-closed no HTTP error**: `LogseqHTTPError` → mensagem clara + exit 1 (sem fallback file-direct). Rationale: fallback file-direct com Logseq aberto arriscaria escrita concorrente — exatamente o que o gate original protegia. O operador deve fechar o Logseq ou corrigir o Local HTTP Server antes de retentar.

**`journal_review --apply` ungated no scan mode**: `--apply` recebe o dual-path; scan mode (sem flag) é read-only e nunca foi gated. Removido o `fail_if_logseq_open()` que aplicava gate indiscriminado.

**`init-project` HTTP: YAGNI flat layout**: HTTP path usa `get_page_blocks_tree(base)` para detectar create vs update; `append_block_in_page` para criar a página se ausente; `upsert_block_property` no primeiro bloco para as 4 props mecânicas (cluster, subcluster, repo-path, repo-host). **Sem** replicação de template (sem bootstrap_from_template), sem macro substitution, sem description, sem preservação de props humanas in-place — escopo YAGNI; file-direct path permanece o caminho canônico com template para creates ricos.

**Paridade de integridade do append (`journal-close` + `journal-note`)**: o append HTTP **não** é YAGNI-flat — espelha a integridade do file-direct, porque essas skills viram o caminho default (Logseq normalmente aberto) e a perda seria silenciosa. (i) **Sub-bullets preservados**: `logseq_http.insert_block_group(parent_uuid, group_lines)` reconstrói via `insertBlock` a árvore que o file-direct escreveria como linhas indentadas — child nível 1 sob o bucket, sub-bullets `commit:`/`plan:` nível 2 sob o child (uuid retornado por `insertBlock`; sem uuid → ancora no parent, degrada nesting mas não perde dado). Sem isso, só `group[0]` chegaria ao grafo. (ii) **Dedup por commit hash**: `_close_append_via_http` coleta os hashes `commit:<x>` da subárvore do bucket (`_bucket_commit_hashes`) e pula grupos já presentes — paridade com `existing_commit_hashes_in_bucket`; o contador `dedup-skipped` volta ao output. **Matching de transitions** permanece por conteúdo exato do bloco (a API não expõe nº de linha) — divergência inerente vs. o `:line` do file-direct, aceitável.

**`journal-review --apply` HTTP: idempotência sim, estrutura de seção não**: archived e hygiene ganham o guard barato de idempotência (skip se `#bucket` já mencionado na category page / sugestão já presente em `bucket-hygiene.md` — paridade com `apply_archived_bucket`/`apply_hygiene`), evitando duplicação em re-run. O que permanece YAGNI é só a **estrutura de seção** (`## Buckets arquivados`, headings por tipo de higiene): o HTTP path faz append flat. Emerging já checava presença antes deste fix.

**Limitação SD12 (enrich-blocks hook persiste com gate)**: o hook `suggest_enrich_blocks` mantém sua gate (iii) "Logseq fechado" — o sub-tool `enrich.py` escreve file-direct; executá-lo com Logseq aberto arriscaria corrupção. Esta limitação é conhecida e documentada: o hook não dispara quando Logseq está aberto, mesmo após o gate-kill das skills. Mitigação futura: HTTP path para `enrich.py` (deferido a backlog).
