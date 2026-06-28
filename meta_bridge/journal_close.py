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

from . import _paths, logseq, logseq_http
from .cli import cli, logseq_open
from .journal_note import bootstrap_journal, find_or_create_bucket
from .logseq_http import LogseqHTTPError, logseq_page_name_candidates


APPEND_HEADER = "## Append"
TRANSITIONS_HEADER = "## Transitions"

COMMIT_HASH_RE = re.compile(r"commit:\s*([a-f0-9]{7,40})\b")
# Separador ` | ` literal (espaço-pipe-espaço) — não usar \s* porque consumiria
# TAB prefix do before/after (children Logseq são `\t- ...`). Body com `|`
# literal deve vir escapado como `\|` (decodificado em _decode_escapes).
TRANSITION_RE = re.compile(r"^- (.+?):(\d+) \| (.+) \| (.+)$")


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
        level, rest = logseq.indent_level(line)
        tag = logseq.bucket_tag(logseq.bullet_text(rest)) if (
            level == 0 and logseq.is_bullet(rest)
        ) else None
        if tag is not None:
            if current_name is not None:
                buckets.append((current_name, current_children))
            current_name = tag
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


def parse_child_groups(children: list[str]) -> list[list[str]]:
    """Agrupa linhas em [child + sub-bullets aninhados]. Group boundary é um
    bullet de nível 1 (child top-level do bucket); sub-bullets (nível ≥2) e
    properties seguem no grupo corrente. Normaliza indent pra TAB no output."""
    groups: list[list[str]] = []
    current: list[str] = []
    for raw in children:
        line = logseq.normalize_indent(raw)
        level, rest = logseq.indent_level(line)
        if level == 1 and logseq.is_bullet(rest):
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
    end = logseq.bucket_region_end(lines, bucket_idx)
    for i in range(bucket_idx + 1, end):
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


_BULLET_PREFIX_RE = re.compile(r"^\t+- ")


def _strip_bullet_prefix(s: str) -> str:
    """Remove prefixo `\t+- ` de bullet Logseq para obter o `content` da API.

    Transitions sempre referenciam children indentados (tasks no journal);
    blocos top-level (`- #bucket`) nunca são alvo de Transition — a regex
    `^\t+- ` (≥1 TAB) é adequada por construção do payload do SKILL.md.
    """
    return _BULLET_PREFIX_RE.sub("", s, count=1)


def _find_bucket_block(tree: list, domain: str) -> dict | None:
    """Retorna bloco top-level cujo content é `#domain` (ou `#domain sufixo`)."""
    prefix = f"#{domain}"
    return next(
        (b for b in tree if isinstance(b, dict)
         and (b.get("content") == prefix or b.get("content", "").startswith(prefix + " "))),
        None,
    )


def _find_block_uuid_recursive(tree: list, content: str) -> str | None:
    for block in tree:
        if not isinstance(block, dict):
            continue
        if block.get("content") == content:
            return block.get("uuid")
        found = _find_block_uuid_recursive(block.get("children") or [], content)
        if found:
            return found
    return None


def _close_append_via_http(
    append_md: str, date_str: str, closed_ts: str
) -> tuple[list[str], int]:
    """Aplica seção Append via HTTP. Retorna (buckets_touched, groups_appended)."""
    journal_path = _paths.journal_path(date_str)
    candidates = logseq_page_name_candidates(str(journal_path))
    if not candidates:
        raise LogseqHTTPError(f"não foi possível derivar nome de página para {journal_path!r}.")

    tree: list = []
    page_name = candidates[0][0]
    for name, _label in candidates:
        blocks = logseq_http.get_page_blocks_tree(name)
        if blocks:
            tree = blocks
            page_name = name
            break

    buckets_touched: list[str] = []
    appended_total = 0

    for bucket_name, children in parse_buckets(append_md):
        groups = parse_child_groups(children)
        if not groups:
            continue
        bucket = _find_bucket_block(tree, bucket_name)
        if bucket is None:
            logseq_http.append_block_in_page(page_name, f"#{bucket_name}")
            tree = logseq_http.get_page_blocks_tree(page_name) or []
            bucket = _find_bucket_block(tree, bucket_name)
        if bucket is None:
            raise LogseqHTTPError(f"falha ao criar/encontrar bucket #{bucket_name} em {page_name!r}.")
        bucket_uuid = bucket["uuid"]
        for group in groups:
            child_content = _strip_bullet_prefix(group[0])
            logseq_http.insert_block(bucket_uuid, child_content, sibling=False)
            appended_total += 1
        logseq_http.upsert_block_property(bucket_uuid, "closed", closed_ts)
        buckets_touched.append(bucket_name)

    return buckets_touched, appended_total


def _close_transitions_via_http(
    transitions: list[tuple[str, int, str, str]],
) -> tuple[int, list[tuple[str, int, str]]]:
    """Aplica Transitions via HTTP. Retorna (applied, skipped)."""
    applied = 0
    skipped: list[tuple[str, int, str]] = []

    # Agrupar por path para minimizar chamadas get_page_blocks_tree.
    path_groups: dict[str, list[tuple[int, str, str]]] = {}
    for path_str, lineno, before, after in transitions:
        path_groups.setdefault(path_str, []).append((lineno, before, after))

    for path_str, path_trans in path_groups.items():
        journal_path = Path(path_str).expanduser()
        candidates = logseq_page_name_candidates(str(journal_path))
        if not candidates:
            for lineno, before, after in path_trans:
                skipped.append((path_str, lineno, "page_name_unresolvable"))
            continue
        tree: list = []
        page_name = candidates[0][0]
        for name, _label in candidates:
            blocks = logseq_http.get_page_blocks_tree(name)
            if blocks:
                tree = blocks
                page_name = name
                break
        if not tree:
            page_names = ",".join(n for n, _ in candidates)
            for lineno, before, after in path_trans:
                skipped.append((path_str, lineno, f"page_not_found:{page_names}"))
            continue
        for lineno, before, after in path_trans:
            before_content = _strip_bullet_prefix(before)
            after_content = _strip_bullet_prefix(after)
            uuid = _find_block_uuid_recursive(tree, before_content)
            if uuid is None:
                skipped.append((path_str, lineno, "block_not_found"))
                continue
            try:
                logseq_http.update_block(uuid, after_content)
                applied += 1
            except LogseqHTTPError as exc:
                skipped.append((path_str, lineno, f"update_error: {exc}"))

    return applied, skipped


def upsert_bucket_closed_property(
    journal_path: Path, bucket: str, timestamp: str
) -> None:
    """Inserir ou atualizar property `closed:: <timestamp>` imediatamente após o
    bullet `- #<bucket>`. Idempotente — replace se já presente, insert senão.
    Consumido pelo hook block-flow enrich downstream (SD12) como signal de
    'bucket recém-fechado' (SSOT in-place per logseq-notes ADR-002 SD4)."""
    bucket_idx = find_or_create_bucket(journal_path, bucket)
    lines = journal_path.read_text().splitlines()
    prop_line = f"\tclosed:: {timestamp}"
    next_idx = bucket_idx + 1
    if next_idx < len(lines) and lines[next_idx].startswith("\tclosed:: "):
        lines[next_idx] = prop_line
    else:
        lines.insert(next_idx, prop_line)
    journal_path.write_text("\n".join(lines) + "\n")


def append_to_bucket(
    journal_path: Path, bucket: str, children_groups: list[list[str]]
) -> tuple[int, int]:
    """Find-or-create bucket + append groups com dedup por commit hash.
    Retorna (groups_appended, groups_dedup_skipped)."""
    bucket_idx = find_or_create_bucket(journal_path, bucket)
    lines = journal_path.read_text().splitlines()
    existing = existing_commit_hashes_in_bucket(lines, bucket_idx)

    insertion = logseq.bucket_region_end(lines, bucket_idx)
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
@click.option(
    "--date",
    "date_override",
    default=None,
    metavar="YYYY-MM-DD",
    help="Escrever no journal do dia especificado em vez de hoje.",
)
def journal_close_cmd(date_override: str | None) -> None:
    """Aplica payload de fechamento de sessão lido de stdin (write engine)."""
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

    if date_override is not None:
        try:
            d = datetime.date.fromisoformat(date_override)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="'--date'")
        date_str = d.strftime("%Y_%m_%d")
        closed_ts = datetime.datetime(
            d.year, d.month, d.day, 23, 59, 59
        ).astimezone().isoformat(timespec="seconds")
    else:
        date_str = datetime.date.today().strftime("%Y_%m_%d")
        closed_ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    if logseq_open():
        try:
            # Transitions primeiro (Step 5a), depois Append (Step 5b) — mesma
            # ordem do file-direct path; consistência de contrato per docstring.
            applied, http_skipped = _close_transitions_via_http(transitions)
            buckets_touched: list[str] = []
            appended_total = 0
            if append_md:
                buckets_touched, appended_total = _close_append_via_http(
                    append_md, date_str, closed_ts
                )
        except LogseqHTTPError as exc:
            click.echo(
                f"Logseq HTTP error — fechar o Logseq ou verificar o Local HTTP Server.\n{exc}",
                err=True,
            )
            sys.exit(1)
        journal_path = _paths.journal_path(date_str)
        click.echo(f"journal: {journal_path} (via HTTP)")
        if buckets_touched:
            click.echo(f"buckets: {', '.join('#' + b for b in buckets_touched)}")
        else:
            click.echo("buckets: (nenhum — sem ## Append ou children vazios)")
        click.echo(f"transitions: {applied} aplicadas, {len(http_skipped)} skipped")
        for path_str, lineno, motivo in http_skipped:
            click.echo(f"  skipped {path_str}:{lineno} — {motivo}", err=True)
        click.echo(f"children groups: {appended_total} appended")
        return

    # Caminho file-direct (Logseq fechado)
    applied = 0
    skipped: list[tuple[str, int, str]] = []
    for path_str, lineno, before, after in transitions:
        ok, motivo = apply_transition(Path(path_str), lineno, before, after)
        if ok:
            applied += 1
        else:
            skipped.append((path_str, lineno, motivo))

    journal_path = _paths.journal_path(date_str)
    buckets_touched = []
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
                upsert_bucket_closed_property(journal_path, bucket_name, closed_ts)
            appended_total += appended
            dedup_total += ded

    click.echo(f"journal: {journal_path}")
    if buckets_touched:
        click.echo(f"buckets: {', '.join('#' + b for b in buckets_touched)}")
    else:
        click.echo("buckets: (nenhum — sem ## Append ou children vazios)")
    click.echo(f"transitions: {applied} aplicadas, {len(skipped)} skipped")
    for path_str, lineno, motivo in skipped:
        click.echo(f"  skipped {path_str}:{lineno} — {motivo}", err=True)
    click.echo(f"children groups: {appended_total} appended, {dedup_total} dedup-skipped")
