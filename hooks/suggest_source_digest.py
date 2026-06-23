#!/usr/bin/env python3
"""Stop hook: suggest /source-digest when today's journal has undigested web clips.

Reads Stop-event JSON from stdin (Claude Code hook). When today's journal has
≥1 top-level block with `tags:: clippings` and no `digested::` property,
prints a suggestion to run /source-digest. Notifier-only (no Popen dispatch)
because digest is LLM-dependent and requires an active CC session.

Gates per ADR-001 Sub-decisão 13:
1. Today's journal exists.
2. Journal has ≥1 block with `tags:: clippings` without `digested::`.
"""
import json
import sys
from datetime import date
from pathlib import Path


def today_journal() -> Path:
    return (
        Path.home() / "Notes" / "logseq" / "journals"
        / f"{date.today().strftime('%Y_%m_%d')}.md"
    )


def has_undigested_clips(journal: Path) -> bool:
    if not journal.is_file():
        return False

    lines = journal.read_text().splitlines()
    in_block = False
    block_has_clippings = False
    block_has_digested = False

    for line in lines:
        if line.startswith("- "):
            if in_block and block_has_clippings and not block_has_digested:
                return True
            in_block = True
            block_has_clippings = False
            block_has_digested = False
        elif in_block:
            if "tags:: clippings" in line:
                block_has_clippings = True
            if "digested::" in line:
                block_has_digested = True

    return in_block and block_has_clippings and not block_has_digested


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(event, dict):
        return 0

    if not has_undigested_clips(today_journal()):
        return 0

    print(json.dumps({
        "systemMessage": (
            "Ha clip(s) nao-digerido(s) no journal de hoje. "
            "Rode /source-digest para criar paginas digested no Logseq."
        )
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
