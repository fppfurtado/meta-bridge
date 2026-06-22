#!/usr/bin/env python3
"""Sub-tool determinístico de /inbox-aggregate.

Parse + dedup + write do bucket #inbox do journal Logseq (logseq-notes ADR-004).
"""

import argparse
import json
import re
import sys
from pathlib import Path

INBOX_BUCKET_RE = re.compile(r"^- #inbox($| )")


def normalize(text: str) -> str:
    return text.strip().lower()


def parse_forge_issues(issues: list[dict], source_tag: str) -> list[str]:
    """Formata issues Forge como task lines Logseq (Papel 2a per ADR-004 SD1+SD2)."""
    tasks = []
    for issue in issues:
        title = (issue.get("title") or "").strip()
        iid = issue.get("iid") or ""
        if not title:
            continue
        suffix = f" (#{iid})" if iid else ""
        tasks.append(f"\t- TODO {title}{suffix}  #inbox {source_tag}")
    return tasks


def parse_pkm_tasks(raw_lines: list[str]) -> list[str]:
    """Normaliza tasks PKM-native; adiciona #pkm-native se ausente (ADR-004 SD2)."""
    result = []
    for line in raw_lines:
        t = line.rstrip()
        if not t:
            continue
        if "#pkm-native" not in t:
            t = t + "  #pkm-native"
        result.append(t)
    return result


def dedup(new_tasks: list[str], existing_normalized: set[str]) -> list[str]:
    """Remove tasks já presentes — exact-match normalizado (ADR-004 SD3)."""
    seen: set[str] = set()
    result = []
    for task in new_tasks:
        key = normalize(task)
        if key not in existing_normalized and key not in seen:
            seen.add(key)
            result.append(task)
    return result


def read_bucket_children(lines: list[str]) -> tuple[list[str], int | None]:
    """Retorna (child_lines, bucket_start_idx) ou ([], None) se bucket ausente.

    Blank lines dentro do bucket são ignoradas na coleta (preservadas no arquivo).
    Scanning encerra na primeira linha não-indentada não-vazia após o bucket.
    """
    bucket_start: int | None = None
    for idx, line in enumerate(lines):
        if INBOX_BUCKET_RE.match(line):
            bucket_start = idx
            break
    if bucket_start is None:
        return [], None
    children = []
    for line in lines[bucket_start + 1 :]:
        if line.startswith("\t"):
            children.append(line.rstrip())
        elif line.strip() == "":
            continue
        else:
            break
    return children, bucket_start


def find_or_create_bucket(lines: list[str]) -> tuple[list[str], int]:
    """Garante que bucket '- #inbox' existe; retorna (lines, bucket_idx)."""
    for idx, line in enumerate(lines):
        if INBOX_BUCKET_RE.match(line):
            return lines, idx
    new_lines = list(lines)
    if new_lines and new_lines[-1].rstrip():
        new_lines.append("\n")
    new_lines.append("- #inbox\n")
    return new_lines, len(new_lines) - 1


def find_bucket_end(lines: list[str], bucket_idx: int) -> int:
    """Retorna índice de inserção após o último filho do bucket (antes de blanks finais).

    Blank lines após filhos mas antes do próximo top-level são preservadas no
    arquivo; novos tasks são inseridos antes delas para manter agrupamento visual.
    """
    last_child_at = bucket_idx
    for idx in range(bucket_idx + 1, len(lines)):
        line = lines[idx]
        if line.startswith("\t"):
            last_child_at = idx
        elif line.strip() == "":
            continue
        else:
            break
    return last_child_at + 1


def insert_tasks_after_bucket(
    lines: list[str], bucket_idx: int, tasks: list[str]
) -> list[str]:
    """Insere tasks como filhos diretos do bucket após filhos existentes."""
    insert_at = find_bucket_end(lines, bucket_idx)
    task_lines = [t + "\n" for t in tasks]
    return lines[:insert_at] + task_lines + lines[insert_at:]


def main() -> int:
    parser = argparse.ArgumentParser(description="inbox-aggregate sub-tool")
    parser.add_argument("--journal", required=True, help="Path absoluto do journal de hoje")
    parser.add_argument(
        "--forge-issues",
        default="{}",
        help='JSON object {"#repo": [{"iid": N, "title": "..."}, ...], ...}',
    )
    parser.add_argument(
        "--pkm-tasks",
        default="[]",
        help="JSON array de task lines grep-adas do journal",
    )
    args = parser.parse_args()

    journal = Path(args.journal).expanduser()

    try:
        forge_map: dict[str, list[dict]] = json.loads(args.forge_issues)
        pkm_raw: list[str] = json.loads(args.pkm_tasks)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"JSON inválido: {exc}\n")
        return 1

    if journal.exists():
        raw = journal.read_text(encoding="utf-8")
        lines = raw.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
    else:
        lines = []

    existing_children, _ = read_bucket_children(lines)
    existing_normalized = {normalize(t) for t in existing_children}

    all_tasks: list[str] = []
    for source_tag, issues in forge_map.items():
        all_tasks.extend(parse_forge_issues(issues, source_tag))
    all_tasks.extend(parse_pkm_tasks(pkm_raw))

    count_forge = sum(len(v) for v in forge_map.values())
    count_pkm = len(pkm_raw)

    new_tasks = dedup(all_tasks, existing_normalized)
    count_new = len(new_tasks)
    count_deduped = len(all_tasks) - count_new

    if new_tasks:
        lines, bucket_idx = find_or_create_bucket(lines)
        lines = insert_tasks_after_bucket(lines, bucket_idx, new_tasks)
        try:
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"falha de write: {exc}\n")
            return 1

    result = {
        "tasks": new_tasks,
        "count_forge": count_forge,
        "count_pkm": count_pkm,
        "count_new": count_new,
        "count_deduped": count_deduped,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
