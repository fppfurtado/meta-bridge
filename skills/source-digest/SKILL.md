---
name: source-digest
description: Digere sources de dois tipos — web clips do journal (tags:: clippings) ou arquivos do filesystem (PDF, txt, md, html, etc.) — criando páginas digested estruturadas no grafo Logseq
disable-model-invocation: false
---

# source-digest

Skill thin orchestrator para Camada 2b (source-flow) do roadmap knowledge layer block-first do meta-system. Opera em dois modos:

- **Modo journal** (sem args): detecta web clips não-digeridos no journal de hoje (`tags:: clippings` sem `digested::`) e cria `pages/<slug>-digested.md`.
- **Modo arquivo** (`/source-digest <path>`): lê arquivo em qualquer path do filesystem, cria `pages/sources/<slug>.md` (raw source page) e `pages/<slug>-digested.md`.

Substância em [ADR-001](../../docs/decisions/ADR-001-skills-de-bridge.md) Sub-decisão 13. Para o padrão de pages digested, ver `karpathy-wiki-gist-digested.md` e `matuschak-evergreen-notes.md` em `~/Notes/logseq/pages/`.

## Argumentos

```
/source-digest                             # modo journal: clips de hoje
/source-digest /storage/documents/foo.pdf  # modo arquivo: path absoluto ou relativo
```

- Sem args → modo journal.
- Arg = path → modo arquivo. Path pode ser `.pdf`, `.txt`, `.md`, `.html`, `.json`, `.xml`, `.csv` ou qualquer formato suportado pelo `Read` tool. Path inexistente ou ilegível → recusa fechada com mensagem de gate.

## Passos

### 1. Gate: Logseq desktop aberto

`pgrep -xi logseq` deve retornar processo ativo. Se Logseq **não** estiver rodando → recusa fechada:

> Logseq desktop fechado — abra antes de rodar /source-digest (novas pages precisam ser detectadas pelo file watcher do grafo).

Exit clean.

### 2. Detectar modo e resolver entrada

**Modo journal:**

Ler `~/Notes/logseq/journals/<hoje>.md`. Percorrer top-level bullets (`- ` no início da linha); cada bloco abrange o bullet principal + linhas subsequentes até o próximo `- ` de nível zero ou EOF. Propriedades do bloco = linhas aninhadas com formato `<chave>:: <valor>` (indentadas com ≥1 espaço ou tab); bullets de conteúdo (`* `) estão no mesmo nível de indentação das propriedades e não são propriedades. Bloco elegível = tem `tags:: clippings` e NÃO tem `digested::`.

- Nenhum clip encontrado no journal → exit limpo: `nenhum clip (tags:: clippings) no journal de hoje`.
- Clips encontrados mas todos com `digested::` → exit limpo: `todos os clips de hoje já foram digeridos`.
- Um clip elegível → prosseguir diretamente.
- Múltiplos elegíveis → listar por `title::` e pedir ao operador para escolher antes de prosseguir.

Extrair do bloco selecionado: `title::`, `source::` (URL), `author::`, `published::`, `description::`, bullets `* ` como conteúdo.

**Modo arquivo:**

Gate: path existe e é legível via `Read` tool. Falha → recusa fechada.

Ler arquivo via `Read` tool:
- Arquivos texto (`.txt`, `.md`, `.html`, `.json`, `.xml`, `.csv`): ler integral.
- PDFs até 50 páginas: ler integral com `pages: "1-N"`.
- PDFs >50 páginas: ler as primeiras 50 páginas com `pages: "1-50"`; marcar truncamento explicitamente no Passo 4 ao criar a source page.

### 3. Inferir slug e metadados

**Modo journal:** gerar slug a partir de `title::` extraído:
- Lowercase; espaços e underscores → `-`; remover não-alfanuméricos exceto `-`; colapsar múltiplos hifens; truncar a 60 chars.
- Exemplo: `"Agentic Programming: A Roadmap"` → `agentic-programming-a-roadmap`.

**Modo arquivo:** inferir via LLM a partir do conteúdo lido:
- Título: do header principal, metadados ou primeira seção relevante.
- Autor: se discernível no conteúdo.
- Tipo: extensão do arquivo (ex: `pdf`, `txt`).
- Slug: mesmas regras acima a partir do título inferido.

Após inferência do slug em modo arquivo, checar idempotência de `pages/sources/<slug>.md`. Se existe → perguntar ao operador se quer re-digerir ou sair.

### 4. [Modo arquivo] Criar raw source page

Escrever `~/Notes/logseq/pages/sources/<slug>.md` com o padrão estabelecido pelos arquivos existentes em `pages/sources/`:

```
provenance:: #source
file:: <path-absoluto-do-arquivo>
title:: "<título inferido>"
author:: [[<autor inferido>]]
type:: <extensão>
created:: <hoje YYYY-MM-DD>

# <Título inferido>

<texto extraído do arquivo como markdown>
```

- `file::` sempre com path absoluto.
- `author::` como page-ref Logseq se o nome é discernível; omitir se desconhecido.
- Conteúdo extraído: texto integral para arquivos até 50 páginas. Para PDFs >50 páginas (leitura truncada no Passo 2), inserir linha `<!-- truncado: lido até p.50 de N -->` após o conteúdo extraído.

### 5. Reasoning LLM — claims e relevância

Com o conteúdo disponível (clip do journal ou arquivo lido), extrair:

**Claims load-bearing** (3–7 claims por source):
- Cada claim = insight substancial, não trivialidade ou resumo superficial.
- Formular em prosa densa com cross-refs explícitos a ADRs, entidades ou conceitos do graph quando convergência for real (ex: "Materializa a tese central da knowledge layer (ADR-013 § Decisão)").
- Não fabricar cross-refs — omitir se a convergência não for clara.

**Relevância pra knowledge layer:**
- 1-2 parágrafos sintetizando como a source se encaixa no modelo arquitetural 4-camadas × 2-fluxos.
- Identificar entidades do grafo tocadas pela source (`[[entity-name]]`).

### 6. Criar página digested

Escrever `~/Notes/logseq/pages/<slug>-digested.md`. O template de properties difere por modo:

**Modo arquivo** (`source::` referencia a raw source page):
```
provenance:: #digested
source:: [[sources/<slug>]]
entities:: [[<entidade1>]], [[<entidade2>]]
created:: <hoje YYYY-MM-DD>
```

**Modo journal** (`source-url::` carrega a URL do clip; sem raw source page):
```
provenance:: #digested
source-url:: <url extraída da prop source:: do bloco>
entities:: [[<entidade1>]], [[<entidade2>]]
created:: <hoje YYYY-MM-DD>
```

Corpo comum a ambos os modos (após properties):
```
# Digested — <Título>

<Descrição de uma linha do que a source cobre>

## Claims load-bearing absorvidos

- **<Claim 1>** — <elaboração com cross-refs>
- **<Claim 2>** — <elaboração>
[...]

## Relevância pra knowledge layer

<Síntese de 1-2 parágrafos>
```

### 7. Finalizar ciclo

**Modo journal:** adicionar `digested:: [[<slug>-digested]]` como propriedade ao bloco do clip no journal. Inserir após a última propriedade existente do bloco (antes do primeiro bullet `* `).

**Modo arquivo:** raw source page já criada no Passo 4. Sem edição de journal.

### 8. Reportar

```
[Modo journal]
Clip digerido: "<título>"
Digested page: ~/Notes/logseq/pages/<slug>-digested.md
Journal atualizado: digested:: [[<slug>-digested]]

[Modo arquivo]
Source page: ~/Notes/logseq/pages/sources/<slug>.md
Digested page: ~/Notes/logseq/pages/<slug>-digested.md
```

## O que NÃO fazer

- **Não rodar com Logseq fechado** — novas pages não serão detectadas pelo grafo; journal edit pode desencontrar com estado do desktop.
- **Não processar clip com `digested::` já presente** — bloco individual com `digested::` é filtrado na varredura do Passo 2 (não elegível). Se todos os clips do dia já têm `digested::`, exit com mensagem discriminada "todos os clips de hoje já foram digeridos" (não confundir com "nenhum clip encontrado").
- **Não mover ou copiar o arquivo original** em modo arquivo — `pages/sources/<slug>.md` é a representação extraída no grafo; o arquivo permanece onde está.
- **Não criar sub-tool Python** — digest é LLM-driven (claims, cross-refs, síntese); sem parte determinística isolável no v0.
- **Não inferir path de arquivo a partir de propriedades do journal** — os dois modos são mutuamente exclusivos: sem arg = journal, com arg = arquivo. Nunca combinar.
- **Não fabricar cross-refs** — citar ADRs ou entidades do grafo só quando convergência for real e verificável no conteúdo da source.
- **Não criar concept pages** (`provenance:: #concept`) — escopo desta skill é Camada 2b; Camada 4 é `/wiki-lint` Onda 5 Faceta 3.
