from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

import click

from . import _paths
from .cli import cli, fail_if_logseq_open


DAILY_JOURNAL_TEMPLATE = _paths.PAGES_DIR / "daily-journal.md"

MARKER_RE = re.compile(r"^(TODO|DOING|WAITING|DONE|CANCELLED) ")
COMMIT_RE = re.compile(r"\bcommit:([a-f0-9]{7,40})\b")
PLAN_RE = re.compile(r"\bplan:([a-z0-9-]+)\b")
SANITIZE_REMOVE_RE = re.compile(r"[^a-z0-9-]")


def sanitize_domain(raw: str) -> str:
    s = raw.strip().lower().replace(" ", "-").replace("_", "-")
    return SANITIZE_REMOVE_RE.sub("", s)


def derive_domain_from_git(cwd: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).name


def bootstrap_journal(journal_path: Path) -> None:
    """Cria journal de hoje a partir de daily-journal.md template per
    ADR-001 Sub-decisão 1 Adendo v0.2.2: skip wrapper + dedent 1 tab fixo."""
    if not DAILY_JOURNAL_TEMPLATE.exists():
        journal_path.write_text("")
        return
    raw = DAILY_JOURNAL_TEMPLATE.read_text().splitlines()
    body: list[str] = []
    for line in raw:
        stripped = line.lstrip()
        if (
            stripped.startswith("type::")
            or stripped.startswith("- template::")
            or stripped.startswith("template-including-parent::")
        ):
            continue
        if line.startswith("\t"):
            line = line[1:]
        body.append(line)
    while body and body[0].strip() == "":
        body.pop(0)
    journal_path.write_text("\n".join(body) + "\n")


def find_or_create_bucket(journal_path: Path, domain: str) -> int:
    """Retorna offset (0-indexed) da linha do bucket. Cria no fim se ausente.

    Probe regex `^- #<domínio>($| )` cobre Cluster Hub opt-in (ADR-002 Sub-decisão 7
    do logseq-notes — bucket = single tag + opcional espaço + sufixo).
    """
    lines = journal_path.read_text().splitlines() if journal_path.exists() else []
    bucket_re = re.compile(rf"^- #{re.escape(domain)}($| )")
    for idx, line in enumerate(lines):
        if bucket_re.match(line):
            return idx
    if lines and lines[-1] != "":
        lines.append("")
    lines.append(f"- #{domain}")
    journal_path.write_text("\n".join(lines) + "\n")
    return len(lines) - 1


def extract_sub_bullets(content: str) -> list[str]:
    out: list[str] = []
    for m in COMMIT_RE.finditer(content):
        out.append(f"\t\t- commit: {m.group(1)}")
    for m in PLAN_RE.finditer(content):
        out.append(f"\t\t- plan: {m.group(1)}")
    return out


def append_child(
    journal_path: Path, bucket_idx: int, content: str
) -> tuple[str, list[str]]:
    """Insere child + sub-bullets no fim da região do bucket (antes do próximo
    top-level ou EOF). Retorna (marker_or_plain, sub_bullets)."""
    lines = journal_path.read_text().splitlines()

    marker_match = MARKER_RE.match(content)
    marker_label = marker_match.group(1) if marker_match else "plain"

    child_line = f"\t- {content}"
    sub_bullets = extract_sub_bullets(content)

    insertion = len(lines)
    for i in range(bucket_idx + 1, len(lines)):
        if lines[i].startswith("- "):
            insertion = i
            break

    new_block = [child_line, *sub_bullets]
    new_lines = lines[:insertion] + new_block + lines[insertion:]
    journal_path.write_text("\n".join(new_lines) + "\n")
    return marker_label, sub_bullets


def _final_content_empty(content: str) -> bool:
    """SKILL.md spec: 'conteúdo final' = input após trim E após remoção do
    marker prefix. Cobre input só whitespace e input 'TODO ' (marker sem body)."""
    lstripped = content.lstrip()
    m = MARKER_RE.match(lstripped)
    body = lstripped[len(m.group(0)) :] if m else lstripped
    return not body.strip()


@cli.command("journal-note")
@click.argument("content", required=True)
@click.option(
    "--domain",
    help=(
        "Hashtag-bucket sem prefixo '#'. Default: basename do git toplevel da cwd. "
        "Falha se cwd fora de git repo e --domain ausente (skill /journal-note "
        "orquestra prompt AskUserQuestion antes per F1 design-reviewer)."
    ),
)
def journal_note_cmd(content: str, domain: str | None) -> None:
    """Find-or-create hashtag-bucket no journal de hoje + append child task."""
    fail_if_logseq_open()

    if _final_content_empty(content):
        click.echo(
            "conteúdo final vazio (whitespace puro ou só marker sem body) — recusado.",
            err=True,
        )
        sys.exit(1)

    if domain:
        resolved_domain = sanitize_domain(domain)
    else:
        derived = derive_domain_from_git(Path.cwd())
        if derived is None:
            click.echo(
                "cwd fora de git repo: passe --domain <name>.",
                err=True,
            )
            sys.exit(1)
        resolved_domain = sanitize_domain(derived)

    if not resolved_domain:
        click.echo(
            "domínio resolveu vazio após sanitização — passe --domain válido.",
            err=True,
        )
        sys.exit(1)

    today = datetime.date.today().strftime("%Y_%m_%d")
    journal_path = _paths.journal_path(today)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    if not journal_path.exists():
        bootstrap_journal(journal_path)

    bucket_idx = find_or_create_bucket(journal_path, resolved_domain)
    marker_label, sub_bullets = append_child(journal_path, bucket_idx, content)

    click.echo(f"journal: {journal_path}")
    click.echo(f"bucket: #{resolved_domain}")
    click.echo(f"marker: {marker_label}")
    if sub_bullets:
        click.echo(f"sub-bullets: {len(sub_bullets)} mecânicos extraídos")
