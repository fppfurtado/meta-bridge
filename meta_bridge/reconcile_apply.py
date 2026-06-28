"""meta_bridge.reconcile_apply — Faceta C do reconciler: write-path de reconciliações.

Subcomando `mb reconcile-apply` (ADR-002 padrão mecânico/judgment; ADR-001 SD19).
Recebe findings JSON de `mb reconcile-check` + journal path → aplica writes
`journal_forge_closed` via Logseq HTTP API: marca tasks como `DONE` no journal.

Failure-open: `LogseqHTTPError` → campo `error` no JSON de saída, exit 0.
Tasks não encontradas ou com erro de update → campo `skipped[].reason`, exit 0.
"""

from __future__ import annotations

import calendar
import json
import re
from pathlib import Path

import click

from . import logseq_http
from .cli import cli
from .logseq_http import LogseqHTTPError

_MARKER_RE = re.compile(r"^(TODO|DOING|WAITING|NOW|LATER)\s")


def _ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _derive_logseq_page_name(journal_path: str | Path) -> list[tuple[str, str]]:
    """Retorna lista de candidatos `[(name, label)]` em ordem de tentativa.

    1. ISO `YYYY-MM-DD` — formato padrão mais comum no Logseq.
    2. Ordinal US `Mon DDth, YYYY` — formato alternativo (ex.: `Jun 27th, 2026`).

    O chamador tenta cada candidato via `get_page_blocks_tree`; usa o primeiro
    que retorna lista não-vazia. Lista vazia → página não encontrada no grafo.
    """
    stem = Path(journal_path).expanduser().stem  # ex.: "2026_06_27"
    try:
        year, month, day = (int(p) for p in stem.split("_"))
    except (ValueError, AttributeError):
        return []
    iso = f"{year:04d}-{month:02d}-{day:02d}"
    month_abbr = calendar.month_abbr[month]  # ex.: "Jun"
    ordinal = f"{month_abbr} {day}{_ordinal_suffix(day)}, {year}"
    return [(iso, "ISO"), (ordinal, "ordinal-US")]


def _find_block_uuid(tree: list, task_text: str) -> str | None:
    """Busca recursivamente na árvore de blocos Logseq o UUID do bloco com `task_text`.

    Cada bloco é um dict com campos `uuid`, `content` e `children` (lista aninhada).
    Match por igualdade exata de `content` com `task_text`.
    """
    for block in tree:
        if isinstance(block, dict) and block.get("content") == task_text:
            return block.get("uuid")
        children = (block.get("children") or []) if isinstance(block, dict) else []
        found = _find_block_uuid(children, task_text)
        if found:
            return found
    return None


def _mark_done(task_text: str) -> str:
    """Substitui o marker aberto no início de `task_text` por `DONE`.

    Preserva o resto do texto intacto. Sem marker aberto → retorna sem alteração.
    """
    return _MARKER_RE.sub("DONE ", task_text, count=1)


@cli.command("reconcile-apply")
@click.option(
    "--findings-json",
    required=True,
    help="JSON de findings de `mb reconcile-check`.",
)
@click.option(
    "--journal-path",
    required=True,
    type=click.Path(),
    help="Path do arquivo de journal (ex.: ~/Notes/logseq/journals/2026_06_27.md).",
)
def reconcile_apply(findings_json: str, journal_path: str) -> None:
    """[write] Aplica reconciliações journal_forge_closed via HTTP (marca tasks DONE)."""
    try:
        findings: list[dict] = json.loads(findings_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--findings-json JSON inválido: {exc}")

    targets = [f for f in findings if f.get("check") == "journal_forge_closed"]

    if not targets:
        click.echo(json.dumps({"applied": [], "skipped": [], "error": None}, ensure_ascii=False))
        return

    candidates = _derive_logseq_page_name(journal_path)
    if not candidates:
        click.echo(json.dumps({
            "applied": [],
            "skipped": [{"task": f["task"], "reason": "page_name_unresolvable"} for f in targets],
            "error": None,
        }, ensure_ascii=False))
        return

    # Tentar cada candidato até achar página com blocos.
    tree: list = []
    used_page: str | None = None
    try:
        for name, _label in candidates:
            blocks = logseq_http.get_page_blocks_tree(name)
            if blocks:
                tree = blocks
                used_page = name
                break
    except LogseqHTTPError as exc:
        click.echo(json.dumps({
            "applied": [],
            "skipped": [{"task": f["task"], "reason": "http_error"} for f in targets],
            "error": str(exc),
        }, ensure_ascii=False))
        return

    if not tree:
        page_names = ",".join(n for n, _ in candidates)
        click.echo(json.dumps({
            "applied": [],
            "skipped": [
                {"task": f["task"], "reason": f"page_not_found:{page_names}"}
                for f in targets
            ],
            "error": None,
        }, ensure_ascii=False))
        return

    applied: list[str] = []
    skipped: list[dict] = []
    error_msg: str | None = None

    for finding in targets:
        task_text = finding["task"]
        uuid = _find_block_uuid(tree, task_text)
        if uuid is None:
            skipped.append({"task": task_text, "reason": f"block_not_found (page: {used_page})"})
            continue
        new_content = _mark_done(task_text)
        try:
            logseq_http.update_block(uuid, new_content)
            applied.append(task_text)
        except LogseqHTTPError as exc:
            error_msg = str(exc)
            skipped.append({"task": task_text, "reason": f"update_error: {exc}"})

    click.echo(json.dumps(
        {"applied": applied, "skipped": skipped, "error": error_msg},
        ensure_ascii=False,
    ))
