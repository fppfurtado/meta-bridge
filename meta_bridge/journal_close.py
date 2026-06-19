"""mb journal-close — write engine determinístico.

Per F3 design-reviewer: matching semântico e síntese vivem na SKILL.md
(`/journal-close`). CLI recebe payload markdown via stdin com 2 seções e aplica
writes atomicamente sem refazer judgment:

    ## Append
    - #bucket-a
        - DONE conceito
            - commit: abc1234
    - #bucket-b
        - TODO próximo passo

    ## Transitions
    - <path>:<lineno> | <before exato> | <after exato>
    - <path>:<lineno> | <before exato> | <after exato>

Ordem de aplicação: transições primeiro (Step 5a do SKILL.md), depois
find-or-create bucket + append (Step 5b). Dedup por `commit:<hash>` aplica em
group level (child + sub-bullets) per ADR-001 Sub-decisão 3.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

import click

from . import _paths
from .cli import cli, fail_if_logseq_open
from .journal_note import bootstrap_journal, find_or_create_bucket


APPEND_HEADER = "## Append"
TRANSITIONS_HEADER = "## Transitions"

BUCKET_RE = re.compile(r"^- #([a-z0-9.-]+)($| )")
COMMIT_HASH_RE = re.compile(r"commit:\s*([a-f0-9]{7,40})\b")
# Separador ` | ` literal (espaço-pipe-espaço) — não usar \s* porque consumiria
# TAB prefix do before/after (children Logseq são `\t- ...`). Body com `|`
# literal deve vir escapado como `\|` (decodificado em _decode_escapes).
TRANSITION_RE = re.compile(r"^- (.+?):(\d+) \| (.+) \| (.+)$")
# Detecta children top-level — aceita TAB OU 4 espaços (normalizado pra TAB
# antes de escrever no journal, que canonical-mente usa \t).
TOP_CHILD_RE = re.compile(r"^(\t|    )- ")
SUB_CHILD_RE = re.compile(r"^(\t\t|        )")


def parse_payload(
    raw: str,
) -> tuple[str, list[tuple[str, int, str, str]]]:
    """Retorna (append_md, transitions). Headers ausentes → seção vazia."""
    sections: dict[str, list[str]] = {APPEND_HEADER: [], TRANSITIONS_HEADER: []}
    current: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped == APPEND_HEADER:
            current = APPEND_HEADER
            continue
        if stripped == TRANSITIONS_HEADER:
            current = TRANSITIONS_HEADER
            continue
        if current is not None:
            sections[current].append(line)

    append_md = "\n".join(sections[APPEND_HEADER]).strip()

    transitions: list[tuple[str, int, str, str]] = []
    for line in sections[TRANSITIONS_HEADER]:
        m = TRANSITION_RE.match(line)
        if m:
            before = _decode_escapes(m.group(3))
            after = _decode_escapes(m.group(4))
            transitions.append(
                (m.group(1).strip(), int(m.group(2)), before, after)
            )
    return append_md, transitions


def _decode_escapes(s: str) -> str:
    r"""Interpreta `\t`, `\n`, `\|` como TAB/newline/pipe literais. Pipe escape
    permite body com ` | ` sem ambiguidade vs separador da transição."""
    return s.replace("\\t", "\t").replace("\\n", "\n").replace("\\|", "|")


def parse_buckets(append_md: str) -> list[tuple[str, list[str]]]:
    """Extrai [(bucket_name, raw_children_lines)] do bloco Append."""
    buckets: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_children: list[str] = []
    for line in append_md.splitlines():
        m = BUCKET_RE.match(line)
        if m:
            if current_name is not None:
                buckets.append((current_name, current_children))
            current_name = m.group(1)
            current_children = []
        elif current_name is not None:
            current_children.append(line)
    if current_name is not None:
        buckets.append((current_name, current_children))

    cleaned: list[tuple[str, list[str]]] = []
    for name, children in buckets:
        while children and children[-1].strip() == "":
            children.pop()
        cleaned.append((name, children))
    return cleaned


def _normalize_indent(line: str) -> str:
    """Cada chunk de 4 espaços no leading whitespace → TAB. Cobre mistos
    (4 spaces + 4 spaces → \\t\\t; \\t + 4 spaces → \\t\\t)."""
    m = re.match(r"^(\s*)", line)
    if not m:
        return line
    ws = m.group(1)
    rest = line[len(ws) :]
    return ws.replace("    ", "\t") + rest


def parse_child_groups(children: list[str]) -> list[list[str]]:
    """Agrupa linhas em [child + sub-bullets aninhados]. Group boundary é
    `\\t- ` ou 4-spaces-` - ` top-level. Normaliza pra TAB no output."""
    groups: list[list[str]] = []
    current: list[str] = []
    for raw in children:
        line = _normalize_indent(raw)
        if TOP_CHILD_RE.match(line) and not SUB_CHILD_RE.match(line):
            if current:
                groups.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        groups.append(current)
    return groups


def existing_commit_hashes_in_bucket(lines: list[str], bucket_idx: int) -> set[str]:
    """Scan da região do bucket — coleta hashes commit:<x> presentes."""
    hashes: set[str] = set()
    for i in range(bucket_idx + 1, len(lines)):
        if lines[i].startswith("- "):
            break
        m = COMMIT_HASH_RE.search(lines[i])
        if m:
            hashes.add(m.group(1))
    return hashes


def group_commit_hashes(group: list[str]) -> set[str]:
    hashes: set[str] = set()
    for line in group:
        m = COMMIT_HASH_RE.search(line)
        if m:
            hashes.add(m.group(1))
    return hashes


def apply_transition(
    path: Path, lineno: int, before: str, after: str
) -> tuple[bool, str]:
    """Retorna (success, motivo_se_skipped). Falha-mole em drift."""
    if not path.exists():
        return False, "source ausente"
    lines = path.read_text().splitlines()
    idx = lineno - 1
    if idx < 0 or idx >= len(lines):
        return False, f"linha {lineno} fora do range (arquivo tem {len(lines)} linhas)"
    if lines[idx] != before:
        return False, "conteúdo da linha não casa 'before' (edit concorrente?)"
    lines[idx] = after
    path.write_text("\n".join(lines) + "\n")
    return True, ""


def append_to_bucket(
    journal_path: Path, bucket: str, children_groups: list[list[str]]
) -> tuple[int, int]:
    """Find-or-create bucket + append groups com dedup por commit hash.
    Retorna (groups_appended, groups_dedup_skipped)."""
    bucket_idx = find_or_create_bucket(journal_path, bucket)
    lines = journal_path.read_text().splitlines()
    existing = existing_commit_hashes_in_bucket(lines, bucket_idx)

    insertion = len(lines)
    for i in range(bucket_idx + 1, len(lines)):
        if lines[i].startswith("- "):
            insertion = i
            break
    while insertion > bucket_idx + 1 and lines[insertion - 1].strip() == "":
        insertion -= 1

    to_insert: list[str] = []
    appended = 0
    skipped = 0
    for group in children_groups:
        hashes = group_commit_hashes(group)
        if hashes and hashes & existing:
            skipped += 1
            continue
        to_insert.extend(group)
        existing |= hashes
        appended += 1

    if to_insert:
        new_lines = lines[:insertion] + to_insert + lines[insertion:]
        journal_path.write_text("\n".join(new_lines) + "\n")

    return appended, skipped


@cli.command("journal-close")
def journal_close_cmd() -> None:
    """Aplica payload de fechamento de sessão lido de stdin (write engine)."""
    fail_if_logseq_open()

    raw = sys.stdin.read()
    if not raw.strip():
        click.echo("payload stdin vazio — nada a aplicar.", err=True)
        sys.exit(1)

    append_md, transitions = parse_payload(raw)

    if not append_md and not transitions:
        click.echo(
            "payload sem '## Append' nem '## Transitions' parseáveis. Formato:",
            err=True,
        )
        click.echo("  ## Append", err=True)
        click.echo("  - #bucket", err=True)
        click.echo("  \t- child", err=True)
        click.echo("  ## Transitions", err=True)
        click.echo("  - <path>:<line> | <before> | <after>", err=True)
        sys.exit(1)

    applied = 0
    skipped: list[tuple[str, int, str]] = []
    for path_str, lineno, before, after in transitions:
        ok, motivo = apply_transition(Path(path_str), lineno, before, after)
        if ok:
            applied += 1
        else:
            skipped.append((path_str, lineno, motivo))

    today = datetime.date.today().strftime("%Y_%m_%d")
    journal_path = _paths.journal_path(today)

    buckets_touched: list[str] = []
    appended_total = 0
    dedup_total = 0

    if append_md:
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        if not journal_path.exists():
            bootstrap_journal(journal_path)
        for bucket_name, children in parse_buckets(append_md):
            groups = parse_child_groups(children)
            if not groups:
                continue
            appended, ded = append_to_bucket(journal_path, bucket_name, groups)
            if appended or ded:
                buckets_touched.append(bucket_name)
            appended_total += appended
            dedup_total += ded

    click.echo(f"journal: {journal_path}")
    if buckets_touched:
        click.echo(f"buckets: {', '.join('#' + b for b in buckets_touched)}")
    else:
        click.echo("buckets: (nenhum — sem ## Append ou children vazios)")
    click.echo(
        f"transitions: {applied} aplicadas, {len(skipped)} skipped"
    )
    for path_str, lineno, motivo in skipped:
        click.echo(f"  skipped {path_str}:{lineno} — {motivo}", err=True)
    click.echo(
        f"children groups: {appended_total} appended, {dedup_total} dedup-skipped"
    )
