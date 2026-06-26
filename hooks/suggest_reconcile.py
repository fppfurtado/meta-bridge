#!/usr/bin/env python3
"""SessionStart hook: suggest /reconcile when cwd matches an owned/active repo
and today's journal exists.

Gate **barato** (sem rede), per ADR-001 SD17 (faceta A do reconciler #46;
precedente SD6 Adendo v0.2.0 — mesma trajetória SessionStart cwd↔REPOS.md, gate
reusado via `_repos._load_owned_active`). A checagem cross-store real (fetch
forge gh/glab + match) roda dentro da skill `/reconcile` quando invocada — o hook
só sugere, mantendo o SessionStart rápido.

Gates (todos locais, sem rede):
1. `cwd` resolve a um git toplevel basename (else exit 0 silent).
2. basename casa entry owned/active em REPOS.md (else exit 0 silent).
3. journal de hoje (`~/Notes/logseq/journals/<YYYY_MM_DD>.md`) existe — só vale
   sugerir reconciliação de abertura quando há um journal do dia (else exit 0).

Match → print JSON `{"systemMessage": ...}` em stdout (soft notification não-
bloqueante, mesmo mecanismo de suggest_session_start_tip.py).
"""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repos import _load_owned_active  # noqa: E402

REPOS_MD = Path.home() / "Projects" / "meta-system" / "REPOS.md"
JOURNALS_DIR = Path.home() / "Notes" / "logseq" / "journals"


def _journal_today_exists() -> bool:
    return (JOURNALS_DIR / f"{datetime.date.today():%Y_%m_%d}.md").is_file()


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

    # Gate 2 — basename matches owned/active entry
    if _load_owned_active(REPOS_MD).get(basename) is None:
        return 0

    # Gate 3 — today's journal exists
    if not _journal_today_exists():
        return 0

    print(json.dumps({
        "systemMessage": (
            "💡 /reconcile checa estado cross-store (Forge + NOTES + Journal) "
            "na abertura — surfa itens já resolvidos antes de orientar."
        )
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
