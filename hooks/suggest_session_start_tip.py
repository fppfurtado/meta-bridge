#!/usr/bin/env python3
"""SessionStart hook: suggest /journal-load when cwd matches an owned/active
constellation repo from `~/Projects/meta-system/REPOS.md`.

Reads a SessionStart-event JSON payload from stdin (Claude Code hook). When the
session starts in a cwd that resolves (via `git rev-parse --show-toplevel`) to
a basename matching an owned/active entry in REPOS.md — either via Repo field
directly or via Path column basename derivation (covers cases like
`logseq-notes` with Path `~/Notes/logseq` → basename `logseq` ≠ Repo field) —
emits a non-blocking soft suggestion via JSON `{"systemMessage": "..."}` on
stdout nudging the operator toward `/journal-load --days 2 --bucket <repo>` to
pull cross-session context. Auto-gating per ADR-001 Sub-decisão 6 Adendo (2ª
trajetória — registro factual, sem generalização prematura):

1. `cwd` resolves to a git toplevel basename (else exit 0 silent).
2. basename matches an owned/active entry parsed from REPOS.md — either Repo
   field direct or Path column basename (else exit 0 silent). Bucket name on
   the tip is always the Repo field (canonical bucket name). Filtro NEGATIVO:
   parser inclui todas as tabelas markdown sob `## <cluster>` headings EXCETO o
   overview top-level `## Clusters (N)` e tabelas sob subsection `### Runtime
   auxiliar consumido externo`. Filtro positivo por Status: aceita apenas linhas
   com `active`.

Gate falha em qualquer ponto → exit 0 silent. Match → print JSON
`{"systemMessage": ...}` em stdout (CC 2.1.x canonical para soft notification
não-bloqueante; mesmo mecanismo da 1ª trajetória `suggest_journal_close.py`).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Parser de REPOS.md compartilhado com suggest_reconcile.py (ADR-001 SD17 —
# generalização de SD6). `sys.path` insert garante `import _repos` tanto quando
# o hook roda direto (`python hooks/suggest_session_start_tip.py`) quanto sob
# importlib no pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repos import _load_owned_active  # noqa: E402

REPOS_MD = Path.home() / "Projects" / "meta-system" / "REPOS.md"


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

    # Gate 2 — basename matches owned/active entry (via Repo field direct or
    # via Path column basename derivation). Bucket name = Repo field canonical.
    bucket = _load_owned_active(REPOS_MD).get(basename)
    if bucket is None:
        return 0

    print(json.dumps({
        "systemMessage": (
            f"💡 /journal-load --days 2 --bucket {bucket} "
            "traz contexto cross-sessão deste repo."
        )
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
