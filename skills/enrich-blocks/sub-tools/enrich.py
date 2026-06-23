#!/usr/bin/env python3
"""Sub-tool determinístico de /enrich-blocks (meta-bridge skill).

Responsabilidades minimal (per ADR-001 SD12 — Sub-decisão 12 pendente):

1. Read journal (--journal-today resolve `~/Notes/logseq/journals/<hoje>.md`,
   ou --journal-path para testes).
2. Para cada bucket top-level `- #<bucket>`, processar sub-bullets `\\t- ...`.
3. Para cada sub-bullet sem `provenance::` em property region (indented ≥2 tabs)
   E mention de entity matching `pages/<basename>.md`: append properties
   `\\t\\tprovenance:: #enriched` + `\\t\\tentities:: [[X]] [[Y]]`.
4. Idempotente: sub-bullet com `provenance::` já set → skip.
5. Errors → log append-only em `~/.claude/local/enrich-errors.log`.

Substância heurística (LLM judgment sobre mention vs noise, decisão semântica)
fica na skill orchestrator `/enrich-blocks`; este sub-tool é write engine
determinístico — matching simples por mention literal de basename.

Não faz: NER complexo (Levenshtein/fuzzy), rewrite de conteúdo, mutação de
outras properties, processamento de seções não-bucket do journal.

Invariantes upstream (per logseq-notes ADR-003 SD2):
- Camada 2a Enriched Blocks: `provenance:: #enriched` + `entities:: [[X]] [[Y]]`
- Property line canonical = indented ≥2 tabs sob o sub-bullet pai

Uso:
    enrich.py --journal-today
    enrich.py --journal-path <path>

Exit codes:
- 0: enrichment applied or no work (idempotência / sem matches)
- 1: erro de I/O ou args inválidos
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

LOGSEQ_ROOT = Path.home() / "Notes" / "logseq"
JOURNALS_DIR = LOGSEQ_ROOT / "journals"
PAGES_DIR = LOGSEQ_ROOT / "pages"
ERROR_LOG = Path.home() / ".claude" / "local" / "enrich-errors.log"

BUCKET_RE = re.compile(r"^- #([a-z0-9.-]+)($| )")
SUB_BULLET_RE = re.compile(r"^\t- ")
PROVENANCE_RE = re.compile(r"^\t{2,}.*provenance::")


def list_project_pages(pages_dir: Path) -> list[str]:
    """List basenames of Project Pages canonical per ADR-005.

    Filter: only pages containing 'repo-path::' property (written exclusively
    by 'mb init-project'; discriminates ~18 project pages from ~199 total pages).
    OSError on individual file read -> silently skip (page not accessible = not a project page).
    """
    if not pages_dir.is_dir():
        return []
    result = []
    for p in pages_dir.glob("*.md"):
        try:
            if "repo-path::" in p.read_text(encoding="utf-8"):
                result.append(p.stem)
        except (OSError, UnicodeDecodeError):
            pass
    return sorted(result)


def find_entity_mentions(text: str, project_pages: list[str]) -> list[str]:
    """Match project pages mentioned in text via literal basename presence.
    Preserves order, dedups. NER simples — refinement (Levenshtein, fuzzy) defer
    per Faceta 3 quando signal real emergir.
    Word-boundary check prevents substring false positives (e.g. 'teste' in 'testes')."""
    mentions: list[str] = []
    seen: set[str] = set()
    for page in project_pages:
        if page not in seen and re.search(r'\b' + re.escape(page) + r'\b', text, re.IGNORECASE):
            mentions.append(page)
            seen.add(page)
    return mentions


def process_journal(journal: Path, project_pages: list[str]) -> tuple[int, int]:
    """Walk journal; enrich eligible sub-bullets. Returns (enriched, skipped).
    Idempotente: sub-bullets com provenance:: já set são contados em skipped."""
    if not journal.is_file():
        return (0, 0)

    lines = journal.read_text().splitlines()
    new_lines: list[str] = []
    in_bucket = False
    enriched = 0
    skipped = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        if BUCKET_RE.match(line):
            in_bucket = True
            new_lines.append(line)
            i += 1
            continue

        if line.startswith("- "):
            in_bucket = False
            new_lines.append(line)
            i += 1
            continue

        if not in_bucket or not SUB_BULLET_RE.match(line):
            new_lines.append(line)
            i += 1
            continue

        # sub-bullet: scan property region until next sub-bullet / top-level / EOF
        prop_end = i + 1
        has_prov = False
        while prop_end < len(lines):
            next_line = lines[prop_end]
            if next_line.startswith("- ") or next_line.startswith("\t- "):
                break
            if PROVENANCE_RE.match(next_line):
                has_prov = True
            prop_end += 1

        new_lines.append(line)

        if has_prov:
            skipped += 1
            new_lines.extend(lines[i + 1 : prop_end])
            i = prop_end
            continue

        scan_text = "\n".join(lines[i:prop_end])
        mentions = find_entity_mentions(scan_text, project_pages)

        if not mentions:
            new_lines.extend(lines[i + 1 : prop_end])
            i = prop_end
            continue

        entities_str = " ".join(f"[[{m}]]" for m in mentions)
        new_lines.append("\t\tprovenance:: #enriched")
        new_lines.append(f"\t\tentities:: {entities_str}")
        new_lines.extend(lines[i + 1 : prop_end])
        i = prop_end
        enriched += 1

    if enriched > 0:
        journal.write_text("\n".join(new_lines) + "\n")
    return (enriched, skipped)


def log_error(msg: str) -> None:
    """Append-only log to ~/.claude/local/enrich-errors.log. Log failure non-fatal."""
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ERROR_LOG.open("a") as f:
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="enrich-blocks sub-tool determinístico")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--journal-today", action="store_true",
                   help="Enrich today's journal at ~/Notes/logseq/journals/<hoje>.md")
    g.add_argument("--journal-path", type=Path,
                   help="Path to journal (for testing)")
    p.add_argument("--pages-dir", type=Path, default=None,
                   help="Override pages dir (for testing); default ~/Notes/logseq/pages/")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.journal_today:
        today = datetime.date.today().strftime("%Y_%m_%d")
        journal = JOURNALS_DIR / f"{today}.md"
    else:
        journal = args.journal_path

    pages_dir = args.pages_dir if args.pages_dir is not None else PAGES_DIR

    try:
        project_pages = list_project_pages(pages_dir)
        enriched, skipped = process_journal(journal, project_pages)
        print(f"enriched: {enriched}, skipped (already): {skipped}")
        return 0
    except Exception as e:
        log_error(f"enrich-blocks: {type(e).__name__}: {e} on {journal}")
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
