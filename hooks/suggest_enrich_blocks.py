#!/usr/bin/env python3
"""Stop hook: dispatch background block-flow enrichment when today's journal has
`closed::` recent buckets with un-enriched sub-bullets.

Reads Stop-event JSON from stdin (Claude Code hook). When today's journal has
≥1 bucket with `closed:: <ISO recent ≤24h>` AND ≥1 sub-bullet of that bucket
without `provenance::`, dispatches the `enrich-blocks` sub-tool as a detached
background process (`subprocess.Popen(start_new_session=True)`) and exits 0
within ≤5s. Triple gate per ADR-001 Sub-decisão 12:

1. `.claude/local/` exists in cwd (operator uses the toolkit).
2. `~/Notes/logseq/` exists AND Logseq desktop NOT running (`pgrep -xi logseq`
   returns non-zero) — race safety per ADR-001 Sub-decisão 7. Case-insensitive
   because the AppImage binary registers as `Logseq` (capital L).
3. Today's journal exists AND has ≥1 bucket with recent `closed::` AND ≥1
   sub-bullet of that bucket without `provenance::`.

Any gate fails → exit 0 silent. All pass → Popen detached subprocess invoking
sub-tool; parent exits clean.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT")
CLOSED_RECENT_WINDOW_HOURS = 24

BUCKET_RE = re.compile(r"^- #([a-z0-9.-]+)($| )")
CLOSED_RE = re.compile(r"^\tclosed:: (.+)$")
# Property line canonical = indented ≥2 tabs (sob sub-bullet `\t-`); restringe
# match a property real, não menção literal "provenance::" no texto do bullet.
PROVENANCE_RE = re.compile(r"^\t{2,}.*provenance::")


def find_eligible_journal() -> Path | None:
    """Today's journal path if any bucket has recent `closed::` AND ≥1 child
    sub-bullet without `provenance::`. Else None."""
    today = datetime.date.today().strftime("%Y_%m_%d")
    journal = Path.home() / "Notes" / "logseq" / "journals" / f"{today}.md"
    if not journal.is_file():
        return None

    lines = journal.read_text().splitlines()
    now = datetime.datetime.now(datetime.timezone.utc)

    for i, line in enumerate(lines):
        if not BUCKET_RE.match(line):
            continue
        if i + 1 >= len(lines):
            continue
        m = CLOSED_RE.match(lines[i + 1])
        if not m:
            continue
        try:
            ts = datetime.datetime.fromisoformat(m.group(1))
        except ValueError:
            continue
        if (now - ts).total_seconds() > CLOSED_RECENT_WINDOW_HOURS * 3600:
            continue

        # Walk sub-bullets of this bucket until next top-level `- `.
        # Assume Logseq flat tree: bucket > sub-bullet (1 nível). Nested
        # children (`\t\t- ...`) are properties/notes of the parent sub-bullet,
        # not separate groups — varredura cobre property no nível ≥2 sob o
        # sub-bullet imediato; aninhamento mais profundo (raro em journal)
        # cai fora do detection per pattern emitido por /journal-close.
        j = i + 2
        while j < len(lines):
            if lines[j].startswith("- "):
                break
            if lines[j].startswith("\t- "):
                # Scan from j+1 until next sub-bullet OR top-level OR EOF.
                # provenance:: property só conta se indented ≥2 tabs (canonical
                # Logseq property line; menção literal no bullet text não conta).
                has_prov = False
                k = j + 1
                while k < len(lines):
                    if lines[k].startswith("- ") or lines[k].startswith("\t- "):
                        break
                    if PROVENANCE_RE.match(lines[k]):
                        has_prov = True
                        break
                    k += 1
                if not has_prov:
                    return journal
                j = k
            else:
                j += 1
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(event, dict):
        return 0

    cwd = event.get("cwd") or os.getcwd()

    # Cheap gates first — avoid wasted journal walk if these fail.
    if not Path(cwd, ".claude", "local").is_dir():
        return 0

    if not PLUGIN_ROOT:
        return 0
    sub_tool = Path(PLUGIN_ROOT) / "skills" / "enrich-blocks" / "sub-tools" / "enrich.py"
    if not sub_tool.is_file():
        return 0

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
        return 0

    journal = find_eligible_journal()
    if journal is None:
        return 0
    try:
        subprocess.Popen(
            ["python3", str(sub_tool), "--journal-today"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError):
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
