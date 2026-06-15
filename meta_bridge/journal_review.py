"""mb journal-review — scan mecânico + write engine.

Per F2 design-reviewer absorption: heurísticas semânticas (task-closure,
task-zombie, bucket-underused, bucket-emerging) vivem na SKILL.md
`/journal-review`. CLI faz só:

1. **Scan mode** (default): resolve janela `--days N` ou `--from/--to`, scaneia
   journals, emite saída markdown estruturada com 4 seções (markers ativos,
   DONE tasks, narrativas, inventário de buckets). Skill consome pra análise.

2. **Apply mode** (`--apply`): lê transições in-place de stdin (mesmo formato
   de `mb journal-close` Transitions) e aplica. Skill compõe transições após
   análise semântica + cherry-pick do operador.

CLI permanece stateless. Toda decisão semântica é re-derivada pela skill em
cada invocação (per F2 contract).
"""

from __future__ import annotations

import datetime
import re
import sys
from collections import defaultdict
from pathlib import Path

import click

from . import _paths
from .cli import cli, fail_if_logseq_open
from .journal_close import (
    TRANSITION_RE,
    _decode_escapes,
    apply_transition,
)


BUCKET_TOP_RE = re.compile(r"^- #([a-z0-9-]+)($| )")
# CANCELLED é terminal mas não emitido na saída (skill MD não consome) —
# omitido do regex pra cair em NARRATIVE_RE como linha qualquer ou ignorado.
MARKER_RE = re.compile(r"^\t- (TODO|DOING|WAITING|DONE) (.+)$")
NARRATIVE_RE = re.compile(r"^\t- (?!TODO |DOING |WAITING |DONE )(.+)$")
SUB_BULLET_RE = re.compile(r"^\t\t")


def resolve_window(
    days: int | None, from_: str | None, to: str | None
) -> list[datetime.date]:
    """Retorna lista de date objects pra janela. Validação mutual-exclusion
    via raise click.UsageError pra mensagem clara."""
    if days is not None and (from_ or to):
        raise click.UsageError("--days e --from/--to são mutuamente exclusivos")
    if (from_ and not to) or (to and not from_):
        raise click.UsageError("--from e --to exigem ambos")
    if from_ and to:
        try:
            d1 = datetime.date.fromisoformat(from_)
            d2 = datetime.date.fromisoformat(to)
        except ValueError:
            raise click.UsageError("--from/--to exigem YYYY-MM-DD")
        if d1 > d2:
            raise click.UsageError("--from > --to")
        span = (d2 - d1).days
        return [d1 + datetime.timedelta(days=i) for i in range(span + 1)]

    days_back = days if days is not None else 30
    if days_back < 0:
        raise click.UsageError("--days exige N >= 0")
    today = datetime.date.today()
    return [today - datetime.timedelta(days=i) for i in range(days_back + 1)][::-1]


def date_to_filename(d: datetime.date) -> str:
    return d.strftime("%Y_%m_%d")


def scan_journal(path: Path, date_iso: str) -> dict[str, list]:
    """Scan single journal — retorna dict com 4 listas:
    markers_open, dones, narratives, buckets (top-level encountered)."""
    out: dict[str, list] = {
        "markers_open": [],
        "dones": [],
        "narratives": [],
        "buckets": [],
    }
    if not path.exists():
        return out
    lines = path.read_text().splitlines()
    current_bucket: str | None = None
    last_top_line_idx: int | None = None

    def collect_sub_bullets(start_idx: int) -> list[str]:
        subs = []
        for j in range(start_idx + 1, len(lines)):
            if SUB_BULLET_RE.match(lines[j]):
                subs.append(lines[j])
            else:
                break
        return subs

    for i, line in enumerate(lines):
        bm = BUCKET_TOP_RE.match(line)
        if bm:
            current_bucket = bm.group(1)
            if current_bucket not in out["buckets"]:
                out["buckets"].append(current_bucket)
            last_top_line_idx = i
            continue

        if current_bucket is None:
            continue

        mm = MARKER_RE.match(line)
        if mm:
            marker = mm.group(1)
            content = mm.group(2)
            sub_bullets = collect_sub_bullets(i)
            entry = {
                "path": str(path),
                "line": i + 1,
                "date": date_iso,
                "bucket": current_bucket,
                "marker": marker,
                "content": content,
                "sub_bullets": sub_bullets,
            }
            if marker == "DONE":
                out["dones"].append(entry)
            elif marker in ("TODO", "DOING", "WAITING"):
                out["markers_open"].append(entry)
            continue

        nm = NARRATIVE_RE.match(line)
        if nm:
            out["narratives"].append(
                {
                    "path": str(path),
                    "line": i + 1,
                    "date": date_iso,
                    "bucket": current_bucket,
                    "content": nm.group(1),
                }
            )
    return out


def emit_scan_output(
    window: list[datetime.date],
    journals_found: int,
    aggregate: dict[str, list],
) -> None:
    """Imprime markdown estruturado consumido pela SKILL.md.

    Entradas dentro de cada seção (Active markers / DONE tasks / Narratives)
    saem em **ordem cronológica ascendente** — heurística 1 da SKILL.md
    confia nessa ordem para identificar evidência posterior ao marker."""
    d1, dN = window[0], window[-1]
    click.echo(
        f"## journal-review scan (window {d1.isoformat()} to {dN.isoformat()}, "
        f"{journals_found} journals)\n"
    )

    click.echo("### Active markers\n")
    if aggregate["markers_open"]:
        for m in aggregate["markers_open"]:
            click.echo(
                f"- {m['path']}:{m['line']} | {m['date']} | #{m['bucket']} | "
                f"{m['marker']} {m['content']}"
            )
            for sb in m["sub_bullets"]:
                click.echo(f"  sub: {sb}")
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### DONE tasks\n")
    if aggregate["dones"]:
        for d in aggregate["dones"]:
            click.echo(
                f"- {d['path']}:{d['line']} | {d['date']} | #{d['bucket']} | "
                f"DONE {d['content']}"
            )
            for sb in d["sub_bullets"]:
                click.echo(f"  sub: {sb}")
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### Narratives\n")
    if aggregate["narratives"]:
        for n in aggregate["narratives"]:
            click.echo(
                f"- {n['path']}:{n['line']} | {n['date']} | #{n['bucket']} | "
                f"{n['content']}"
            )
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### Bucket inventory\n")
    bucket_data: dict[str, dict[str, int]] = defaultdict(
        lambda: {"journals": 0, "open_tasks": 0, "done_tasks": 0}
    )
    bucket_seen_per_journal: dict[str, set[str]] = defaultdict(set)
    for m in aggregate["markers_open"]:
        bucket_data[m["bucket"]]["open_tasks"] += 1
        bucket_seen_per_journal[m["bucket"]].add(m["date"])
    for d in aggregate["dones"]:
        bucket_data[d["bucket"]]["done_tasks"] += 1
        bucket_seen_per_journal[d["bucket"]].add(d["date"])
    for n in aggregate["narratives"]:
        bucket_seen_per_journal[n["bucket"]].add(n["date"])
    for bucket_name in aggregate["buckets_all"]:
        bucket_data[bucket_name]["journals"] = len(
            bucket_seen_per_journal[bucket_name]
        )
    if bucket_data:
        for bucket_name in sorted(bucket_data):
            d = bucket_data[bucket_name]
            click.echo(
                f"- #{bucket_name} | journals: {d['journals']} | "
                f"open_tasks: {d['open_tasks']} | done_tasks: {d['done_tasks']}"
            )
    else:
        click.echo("_(none)_")


def run_apply_mode() -> None:
    """Read transitions from stdin (same format as journal-close), apply."""
    raw = sys.stdin.read()
    transitions: list[tuple[str, int, str, str]] = []
    for line in raw.splitlines():
        m = TRANSITION_RE.match(line)
        if m:
            transitions.append(
                (
                    m.group(1).strip(),
                    int(m.group(2)),
                    _decode_escapes(m.group(3)),
                    _decode_escapes(m.group(4)),
                )
            )

    if not transitions:
        click.echo(
            "--apply: nenhuma transição parseável (stdin vazio ou formato inválido). Formato:",
            err=True,
        )
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

    click.echo(f"transitions: {applied} aplicadas, {len(skipped)} skipped")
    for path_str, lineno, motivo in skipped:
        click.echo(f"  skipped {path_str}:{lineno} — {motivo}", err=True)


@cli.command("journal-review")
@click.option("--days", type=int, default=None, help="Janela retroativa (default 30 se nem --from/--to).")
@click.option("--from", "from_", type=str, default=None, help="Início da janela YYYY-MM-DD.")
@click.option("--to", "to", type=str, default=None, help="Fim da janela YYYY-MM-DD.")
@click.option("--apply", "apply_mode", is_flag=True, default=False, help="Apply mode: lê transições de stdin.")
def journal_review_cmd(
    days: int | None,
    from_: str | None,
    to: str | None,
    apply_mode: bool,
) -> None:
    """Scan mecânico de markers/DONE/narrativas/buckets em janela; apply via stdin."""
    fail_if_logseq_open()

    if apply_mode:
        run_apply_mode()
        return

    window = resolve_window(days, from_, to)

    aggregate: dict[str, list] = {
        "markers_open": [],
        "dones": [],
        "narratives": [],
        "buckets_all": [],
    }
    journals_found = 0
    for d in window:
        fname = date_to_filename(d)
        path = _paths.journal_path(fname)
        if not path.exists():
            continue
        journals_found += 1
        scanned = scan_journal(path, d.isoformat())
        aggregate["markers_open"].extend(scanned["markers_open"])
        aggregate["dones"].extend(scanned["dones"])
        aggregate["narratives"].extend(scanned["narratives"])
        for b in scanned["buckets"]:
            if b not in aggregate["buckets_all"]:
                aggregate["buckets_all"].append(b)

    if journals_found == 0:
        click.echo(
            f"nenhum journal encontrado na janela "
            f"{window[0].isoformat()} a {window[-1].isoformat()}.",
            err=True,
        )
        sys.exit(0)

    emit_scan_output(window, journals_found, aggregate)
