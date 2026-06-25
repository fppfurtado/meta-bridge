"""meta_bridge.logseq — parser block-model de arquivos Logseq.

Centraliza o parsing estrutural (indentação, buckets, block properties, markers
GTD, hierarquia de bullets) antes espalhado em regex/`startswith`/`split`
inconsistentes pelos módulos do write engine — em particular o tratamento de
indentação, que divergia entre módulos (TAB rígido em `journal_note`/`journal_review`,
TAB-ou-4-espaços em `journal_close`). Aqui a leitura é normalizada: 1 TAB OU 1
grupo de 4 espaços = 1 nível.

Modela a estrutura outline do Logseq:
- **bullets** aninhados por indentação (`- conteúdo`);
- **block properties** (`key:: value` como linha-filha de um bullet);
- **page properties** (`key:: value` no nível 0 antes do 1º bullet, em pages);
- **markers GTD** (`TODO`/`DONE`/...) como prefixo do conteúdo do bullet.

Escopo: SÓ arquivos Logseq (journals + pages). NÃO cobre o formato de relatório
emitido pelo próprio `mb journal-review` nem formatos externos (`~/.mrconfig`,
REPOS.md, CLAUDE.md/README.md) — esses seguem com parsing próprio nos consumidores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Superset de markers GTD reconhecidos. Cada consumidor decide em quais AGIR
# (ex.: o scan de journal-review age só em TODO/DOING/WAITING/DONE); este módulo
# só os identifica estruturalmente.
GTD_MARKERS = (
    "TODO",
    "DOING",
    "NOW",
    "LATER",
    "WAITING",
    "DONE",
    "CANCELLED",
    "CANCELED",
)

_LEADING_WS_RE = re.compile(r"^[\t ]*")
# Bucket = bullet top-level cujo conteúdo é uma única hashtag (opt sufixo após
# espaço). Charclass [a-z0-9.-] é superset seguro do uso real [a-z0-9-]; `.` tolerado.
_BUCKET_TAG_RE = re.compile(r"^#([a-z0-9.-]+)($| )")
_PROPERTY_RE = re.compile(r"^([A-Za-z][\w-]*):: ?(.*)$")
_MARKER_RE = re.compile(r"^(" + "|".join(GTD_MARKERS) + r") (.*)$")


# --- primitivas de linha (substrato determinístico) ------------------------

def indent_level(line: str) -> tuple[int, str]:
    """`(nível, resto)` — `resto` é a linha sem o leading whitespace.

    1 TAB = 1 nível; cada grupo de 4 espaços = 1 nível (espaços avulsos <4 são
    ruído ignorado). Unifica a divergência TAB-vs-4-espaços de leitura.
    """
    ws = _LEADING_WS_RE.match(line).group(0)
    rest = line[len(ws):]
    level = ws.count("\t") + (ws.replace("\t", "").count(" ") // 4)
    return level, rest


def normalize_indent(line: str) -> str:
    """Reescreve o leading whitespace para TAB canonical (cada `    ` → `\\t`;
    TABs preservados). Para escrita no journal, que canonical-mente usa TAB.
    Substitui o `_normalize_indent` antes local a `journal_close`."""
    ws = _LEADING_WS_RE.match(line).group(0)
    rest = line[len(ws):]
    return ws.replace("    ", "\t") + rest


def dedent_one_level(line: str) -> str:
    """Remove 1 nível de indent inicial (1 TAB, ou 4 espaços se não houver TAB).
    Usado pelo bootstrap de templates (dedent 1 tab fixo)."""
    if line.startswith("\t"):
        return line[1:]
    if line.startswith("    "):
        return line[4:]
    return line


def is_bullet(rest: str) -> bool:
    """True se `rest` (linha já dedentada) é um bullet `- ...`."""
    return rest.startswith("- ")


def bullet_text(rest: str) -> str:
    """Conteúdo após `- ` de um bullet (assume `is_bullet(rest)`)."""
    return rest[2:]


def bucket_tag(text: str) -> str | None:
    """Nome da tag se o texto do bullet é um bucket `#<tag>` (opt sufixo); senão
    None. Aplicar a `bullet_text(rest)` de um bullet top-level."""
    m = _BUCKET_TAG_RE.match(text)
    return m.group(1) if m else None


def parse_marker(text: str) -> tuple[str, str] | None:
    """`(marker, resto)` se o texto do bullet começa com um marker GTD seguido
    de espaço; senão None."""
    m = _MARKER_RE.match(text)
    return (m.group(1), m.group(2)) if m else None


def parse_property(rest: str) -> tuple[str, str] | None:
    """`(key, value)` se a linha dedentada é uma property `key:: value`; senão
    None. Bullets (`- ...`) nunca casam — `^[A-Za-z]` exclui o `-`."""
    m = _PROPERTY_RE.match(rest)
    return (m.group(1), m.group(2)) if m else None


# --- navegação line-based para os write paths (idempotência forward-only) ---

def find_bucket_line(lines: list[str], tag: str) -> int | None:
    """Índice 0-based da linha do bucket top-level `- #<tag>` (opt sufixo); None
    se ausente. Probe equivalente ao `^- #<tag>($| )` antes local."""
    target = re.compile(rf"^- #{re.escape(tag)}($| )")
    for idx, line in enumerate(lines):
        if target.match(line):
            return idx
    return None


def bucket_region_end(lines: list[str], bucket_idx: int) -> int:
    """Índice exclusivo do fim da região do bucket em `bucket_idx`: o 1º bullet
    top-level (`- ...`, nível 0) após ele, ou `len(lines)`."""
    for i in range(bucket_idx + 1, len(lines)):
        if lines[i].startswith("- "):
            return i
    return len(lines)


# --- modelo block-tree (parsing de leitura: pages + journals) --------------

@dataclass
class Block:
    """Um bullet Logseq com seus block properties e filhos aninhados."""

    level: int
    text: str  # conteúdo após `- ` (inclui o marker GTD quando presente)
    line_index: int  # 0-based no texto original
    marker: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    prop_line_indices: list[int] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)

    @property
    def content(self) -> str:
        """Texto sem o prefixo de marker GTD (== text quando não há marker)."""
        if self.marker:
            return self.text[len(self.marker) + 1:]
        return self.text

    @property
    def bucket(self) -> str | None:
        """Nome da tag se este bloco é um bucket `- #<tag>`; senão None."""
        return bucket_tag(self.text)


def parse_document(text: str) -> tuple[dict[str, str], list[Block]]:
    """`(page_properties, top_level_blocks)`.

    `page_properties`: properties no nível 0 antes do 1º bullet (forma de page).
    Linhas em branco e linhas non-bullet/non-property são ignoradas na árvore
    (estrutura, não fidelidade byte-a-byte — write paths preservam raw via
    line surgery).
    """
    lines = text.splitlines()
    page_props: dict[str, str] = {}
    roots: list[Block] = []
    stack: list[Block] = []
    seen_first_bullet = False

    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        level, rest = indent_level(line)

        if not is_bullet(rest):
            kv = parse_property(rest)
            if kv is None:
                continue
            key, value = kv
            if not seen_first_bullet and level == 0:
                page_props[key] = value
            else:
                owner = next((b for b in reversed(stack) if b.level < level), None)
                if owner is not None:
                    owner.properties[key] = value
                    owner.prop_line_indices.append(idx)
            continue

        seen_first_bullet = True
        text_after = bullet_text(rest)
        mk = parse_marker(text_after)
        block = Block(
            level=level,
            text=text_after,
            line_index=idx,
            marker=mk[0] if mk else None,
        )
        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            stack[-1].children.append(block)
        else:
            roots.append(block)
        stack.append(block)

    return page_props, roots


def serialize(page_props: dict[str, str], blocks: list[Block]) -> str:
    """Reserializa em TAB canonical. Round-trippável sobre entrada TAB-canonical
    sem linhas em branco: `serialize(*parse_document(text)) == text`."""
    out: list[str] = []
    for key, value in page_props.items():
        out.append(f"{key}:: {value}")

    def emit(block: Block) -> None:
        out.append("\t" * block.level + "- " + block.text)
        prop_indent = "\t" * (block.level + 1)
        for key, value in block.properties.items():
            out.append(f"{prop_indent}{key}:: {value}")
        for child in block.children:
            emit(child)

    for b in blocks:
        emit(b)
    return "\n".join(out) + "\n" if out else ""
