"""meta_bridge.reconcile_check — verify-state cross-store em load-time (read-only).

Faceta A do reconciler (#46, ADR-001 SD17). Surfa inconsistências cross-store na
abertura de sessão **antes de orientar**, reusando o primitivo verify-state-
before-materialize (toolkit ADR-069) em load-time. **Read-only:** emite findings
JSON; não muta o grafo (escrita é a faceta C, #48) — por isso sem gate `pgrep`.

2 checks v0:
- `journal_forge_closed`: task aberta (`TODO`/`DOING`/`WAITING`/`NOW`/`LATER`) em
  bucket Forge-synced (`#<repo>`, ou `#inbox` tagueada `#<repo>`) carregando
  `(#<iid>)` cuja issue está fechada — candidato a reconciliar.
- `notes_encerrada`: entry de NOTES.md com o marcador `Encerrada YYYY-MM-DD` no
  início de um bullet/linha — não re-orientar para ela.

**Decomposição mecânico/judgment (ADR-002, padrão `inbox_aggregate`):** o
subcomando é puramente determinístico — recebe as issues fechadas via
`--closed-issues` (JSON); a **skill `/reconcile`** orquestra o fetch forge
(forge-auto-detect → `gh`/`glab`). Sem subprocess aqui — toda a heterogeneidade
de forge (gh vs glab) e a degradação graciosa vivem na skill. Match por `(#<iid>)`
(drift-proof); o iid vem do suffix que entries Forge-synced carregam (SD14).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import click

from . import logseq
from .cli import cli

_IID_RE = re.compile(r"\(#(\d+)\)")
_HASHTAG_RE = re.compile(r"#([a-z0-9.-]+)")
# Marcador deliberado: início de bullet/linha (tolera `- `, `**` de bold), não
# menção incidental em prosa no meio da linha.
_ENCERRADA_RE = re.compile(r"^[\t ]*[-*]?\s*\*{0,2}Encerrada (\d{4}-\d{2}-\d{2})")
# Markers "abertos" (não-resolvidos) — task já DONE/CANCELLED não vira finding.
_OPEN_MARKERS = {"TODO", "DOING", "WAITING", "NOW", "LATER"}
_INBOX = "inbox"


def _iter_tasks(block: logseq.Block):
    """Yield recursivamente os blocos descendentes que têm marker GTD."""
    for child in block.children:
        if child.marker:
            yield child
        yield from _iter_tasks(child)


def check_journal_forge_closed(
    blocks: list[logseq.Block], closed_by_repo: dict[str, list[int]]
) -> list[dict]:
    """Findings de tasks abertas em bucket Forge-synced cuja issue está fechada.

    `closed_by_repo`: `{"<repo>": [<iid>, ...]}` — issues fechadas por repo,
    fornecidas pela skill. Em bucket `#<repo>` o repo é o próprio bucket; em
    `#inbox` o repo é a hashtag inline que casa uma chave conhecida (SD14).
    """
    closed_sets = {repo: set(iids) for repo, iids in closed_by_repo.items()}
    findings: list[dict] = []
    for block in blocks:
        bucket = block.bucket
        if bucket is None:
            continue
        for task in _iter_tasks(block):
            if task.marker not in _OPEN_MARKERS:
                continue
            iid_m = _IID_RE.search(task.text)
            if not iid_m:
                continue
            iid = int(iid_m.group(1))
            if bucket == _INBOX:
                repos = [h for h in _HASHTAG_RE.findall(task.content) if h in closed_sets]
            elif bucket in closed_sets:
                repos = [bucket]
            else:
                repos = []
            for repo in repos:
                if iid in closed_sets[repo]:
                    findings.append(
                        {
                            "check": "journal_forge_closed",
                            "repo": repo,
                            "iid": iid,
                            "task": task.text,
                        }
                    )
                    break
    return findings


def check_notes_encerrada(notes_text: str) -> list[dict]:
    """Findings (um por entry) de NOTES.md marcadas `Encerrada YYYY-MM-DD`."""
    findings: list[dict] = []
    seen_headers: set[str] = set()
    current_header = "(sem header)"
    for line in notes_text.splitlines():
        if line.startswith("## "):
            current_header = line[3:].strip()
        m = _ENCERRADA_RE.match(line)
        if m and current_header not in seen_headers:
            seen_headers.add(current_header)
            findings.append(
                {"check": "notes_encerrada", "entry": current_header, "date": m.group(1)}
            )
    return findings


@cli.command("reconcile-check")
@click.option("--journal", required=True, type=click.Path(), help="Path do journal a checar.")
@click.option(
    "--notes",
    type=click.Path(),
    default=None,
    help="Path do NOTES.md (default: .claude/local/NOTES.md no cwd).",
)
@click.option(
    "--closed-issues",
    default="{}",
    help='JSON {"<repo>": [<iid>, ...]} de issues fechadas (skill fornece via forge-auto-detect).',
)
def reconcile_check(journal: str, notes: str | None, closed_issues: str) -> None:
    """[read-only] Surfa inconsistências cross-store na abertura (verify-state em load-time)."""
    try:
        closed_by_repo: dict[str, list[int]] = json.loads(closed_issues)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--closed-issues JSON inválido: {exc}")

    findings: list[dict] = []
    checks_run: list[str] = []
    checks_skipped: list[str] = []

    journal_path = Path(journal).expanduser()
    if journal_path.exists():
        _, blocks = logseq.parse_document(journal_path.read_text(encoding="utf-8"))
        if closed_by_repo:
            findings.extend(check_journal_forge_closed(blocks, closed_by_repo))
            checks_run.append("journal_forge_closed")
        else:
            # failure-open: sem dados de issue fechada (forge indisponível / skill
            # não passou) → pula Check 1, Check 2 local ainda roda.
            checks_skipped.append("journal_forge_closed (sem --closed-issues)")
    else:
        checks_skipped.append("journal_forge_closed (journal ausente)")

    notes_path = (
        Path(notes).expanduser()
        if notes
        else Path.cwd() / ".claude" / "local" / "NOTES.md"
    )
    if notes_path.exists():
        findings.extend(check_notes_encerrada(notes_path.read_text(encoding="utf-8")))
        checks_run.append("notes_encerrada")
    else:
        checks_skipped.append("notes_encerrada (NOTES.md ausente)")

    click.echo(
        json.dumps(
            {"findings": findings, "checks_run": checks_run, "checks_skipped": checks_skipped},
            ensure_ascii=False,
        )
    )
