#!/usr/bin/env python3
"""Stop hook: suggest /journal-close when /run-plan finishes.

Reads a Stop-event JSON payload from stdin (Claude Code hook). When the
`/run-plan` skill of the `pragmatic-dev-toolkit` plugin ends emitting marker
`[PRAGMATIC: plan-done]` in the transcript tail, emits a non-blocking soft
suggestion via JSON `{"systemMessage": "..."}` on stdout nudging the operator
toward `/journal-close`. Auto-gating triplo per ADR-001 Sub-decisão 6:

1. Marker `[PRAGMATIC: plan-done]` present in last 50 transcript lines.
2. `.claude/local/` exists in cwd (operator uses the toolkit).
3. `~/Notes/logseq/` exists AND Logseq desktop NOT running (`pgrep -xi logseq`
   returns non-zero) — race safety per ADR-005 of meta-system. Case-insensitive
   because the AppImage binary registers as `Logseq` (capital L), not `logseq`.

Any gate fails → exit 0 silent. All pass → print JSON `{"systemMessage": ...}`
to stdout (CC 2.1.x canonical for non-blocking soft notification; stderr would
be silenced unless `--debug` per anthropics/claude-code #34600).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

MARKER = "[PRAGMATIC: plan-done]"
TAIL_LINES = 50


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    transcript_path = event.get("transcript_path")
    cwd = event.get("cwd") or os.getcwd()

    # Gate 1 — marker in transcript tail
    if not transcript_path or not Path(transcript_path).is_file():
        return 0
    try:
        result = subprocess.run(
            ["tail", "-n", str(TAIL_LINES), transcript_path],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, OSError):
        return 0
    if MARKER not in result.stdout:
        return 0

    # Gate 2 — .claude/local/ in cwd
    if not Path(cwd, ".claude", "local").is_dir():
        return 0

    # Gate 3 — ~/Notes/logseq/ exists AND Logseq desktop closed
    if not Path.home().joinpath("Notes", "logseq").is_dir():
        return 0
    try:
        pgrep = subprocess.run(
            ["pgrep", "-xi", "logseq"],
            capture_output=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, OSError):
        return 0
    if pgrep.returncode == 0:
        # Logseq desktop running — race risk; stay silent (skill /journal-close
        # would refuse anyway).
        return 0

    print(json.dumps({
        "systemMessage": "💡 Considere /journal-close pra sintetizar a sessão no journal de hoje."
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
