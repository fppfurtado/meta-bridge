#!/usr/bin/env python3
"""SessionStart hook: suggest /journal-load when cwd matches an owned/active
constellation repo from `~/Projects/meta-system/REPOS.md`.

Reads a SessionStart-event JSON payload from stdin (Claude Code hook). When the
session starts in a cwd that resolves (via `git rev-parse --show-toplevel`) to
a repo basename listed as owned and `active` in REPOS.md, emits a non-blocking
soft suggestion via JSON `{"systemMessage": "..."}` on stdout nudging the
operator toward `/journal-load --days 2 --bucket <repo>` to pull cross-session
context. Auto-gating per ADR-001 Sub-decisão 6 Adendo (2ª trajetória — registro
factual, sem generalização prematura):

1. `cwd` resolves to a git toplevel basename (else exit 0 silent).
2. basename is in the owned/active set parsed from REPOS.md (else exit 0
   silent). Filtro NEGATIVO: parser inclui todas as tabelas markdown sob
   `## <cluster>` headings EXCETO o overview top-level `## Clusters (N)` e
   tabelas sob subsection `### Runtime auxiliar consumido externo`. Filtro
   positivo por Status: aceita apenas linhas com `active`.

Gate falha em qualquer ponto → exit 0 silent. Match → print JSON
`{"systemMessage": ...}` em stdout (CC 2.1.x canonical para soft notification
não-bloqueante; mesmo mecanismo da 1ª trajetória `suggest_journal_close.py`).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPOS_MD = Path.home() / "Projects" / "meta-system" / "REPOS.md"
OVERVIEW_H2_PATTERN = re.compile(r"^Clusters(\b|\s|\()", re.IGNORECASE)
EXCLUDED_H3_TOKEN = "consumido externo"


def _load_owned_active(repos_md_path: Path) -> set[str]:
    """Parse REPOS.md, return owned/active repo basenames (filtro NEGATIVO)."""
    if not repos_md_path.is_file():
        return set()
    text = repos_md_path.read_text(encoding="utf-8")

    owned: set[str] = set()
    current_h2: str | None = None
    current_h3: str | None = None
    repo_col_idx: int | None = None
    status_col_idx: int | None = None
    in_table_header_seen = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("## ") and not line.startswith("### "):
            current_h2 = line[3:].strip()
            current_h3 = None
            repo_col_idx = None
            status_col_idx = None
            in_table_header_seen = False
            continue
        if line.startswith("### "):
            current_h3 = line[4:].strip()
            repo_col_idx = None
            status_col_idx = None
            in_table_header_seen = False
            continue

        if current_h2 is None:
            continue
        if OVERVIEW_H2_PATTERN.match(current_h2):
            continue
        if current_h3 and EXCLUDED_H3_TOKEN in current_h3.lower():
            continue

        if line.startswith("|") and not in_table_header_seen:
            cells = [c.strip() for c in line.strip("|").split("|")]
            lower_cells = [c.lower() for c in cells]
            if "repo" in lower_cells and "status" in lower_cells:
                repo_col_idx = lower_cells.index("repo")
                status_col_idx = lower_cells.index("status")
                in_table_header_seen = True
            continue

        if in_table_header_seen and line.startswith("|"):
            if "---" in line and not any(ch.isalnum() for ch in line.replace("-", "").replace("|", "").replace(":", "")):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if repo_col_idx is None or status_col_idx is None:
                continue
            if max(repo_col_idx, status_col_idx) >= len(cells):
                continue
            repo_field = cells[repo_col_idx].strip("`").strip()
            status_field = cells[status_col_idx].lower()
            if repo_field and "active" in status_field:
                owned.add(repo_field)
            continue

        if in_table_header_seen and not line.startswith("|"):
            in_table_header_seen = False
            repo_col_idx = None
            status_col_idx = None

    return owned


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    cwd = event.get("cwd") or os.getcwd()

    # Gate 1 — cwd resolves to a git toplevel basename
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, OSError):
        return 0
    if result.returncode != 0 or not result.stdout.strip():
        return 0
    basename = Path(result.stdout.strip()).name

    # Gate 2 — basename in REPOS.md owned/active set
    if basename not in _load_owned_active(REPOS_MD):
        return 0

    print(json.dumps({
        "systemMessage": (
            f"💡 /journal-load --days 2 --bucket {basename} "
            "traz contexto cross-sessão deste repo."
        )
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
