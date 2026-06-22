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
_ITEM_PREFIX_RE = re.compile(r"^\t*-\s+(?:(?:TODO|DOING|WAITING)\s+)?")


def normalize(text: str) -> str:
    return text.strip().lower()


def content_key(line: str) -> str:
    """Dedup key para comparação cross-type: strip indent + bullet + marker opcional, normalize."""
    return _ITEM_PREFIX_RE.sub("", line).strip().lower()


def parse_forge_issues(issues: list[dict], source_tag: str) -> list[dict]:
    """Formata issues Forge como task lines Logseq (Papel 2a per ADR-004 SD1+SD2)."""
    tasks = []
    for issue in issues:
        title = (issue.get("title") or "").strip()
        iid = issue.get("iid") or ""
        if not title:
            continue
        suffix = f" (#{iid})" if iid else ""
        tasks.append(
            {"line": f"\t- TODO {title}{suffix}  #inbox {source_tag}", "type": "forge"}
        )
    return tasks


def parse_pkm_tasks(raw_lines: list[str]) -> list[dict]:
    """Normaliza tasks PKM-native com marker GTD; adiciona #pkm-native se ausente (ADR-004 SD2)."""
    result = []
    for line in raw_lines:
        t = line.rstrip()
        if not t:
            continue
        if "#pkm-native" not in t:
            t = t + "  #pkm-native"
        result.append({"line": t, "type": "pkm_task"})
    return result


def parse_pkm_non_tasks(raw_lines: list[str]) -> list[dict]:
    """Normaliza capturas PKM-native sem marker GTD (ADR-004 SD1 Adendo 2026-06-22)."""
    result = []
    for line in raw_lines:
        t = line.rstrip()
        if not t:
            continue
        result.append({"line": t, "type": "pkm_non_task"})
    return result


def dedup(new_tasks: list[dict], existing_pool: set[str]) -> list[dict]:
    """Remove tasks já presentes — content_key normalizado, cross-type (ADR-004 SD3)."""
    seen: set[str] = set()
    result = []
    for task in new_tasks:
        key = content_key(task["line"])
        if key not in existing_pool and key not in seen:
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
        help="JSON array de task lines grep-adas do journal (com marker GTD)",
    )
    parser.add_argument(
        "--pkm-non-tasks",
        default="[]",
        help="JSON array de non-task lines grep-adas do journal (sem marker GTD, indentadas)",
    )
    args = parser.parse_args()

    journal = Path(args.journal).expanduser()

    try:
        forge_map: dict[str, list[dict]] = json.loads(args.forge_issues)
        pkm_raw: list[str] = json.loads(args.pkm_tasks)
        pkm_non_task_raw: list[str] = json.loads(args.pkm_non_tasks)
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
    existing_pool = {content_key(t) for t in existing_children}

    all_tasks: list[dict] = []
    for source_tag, issues in forge_map.items():
        all_tasks.extend(parse_forge_issues(issues, source_tag))
    pkm_tasks = parse_pkm_tasks(pkm_raw)
    pkm_non_tasks = parse_pkm_non_tasks(pkm_non_task_raw)
    all_tasks.extend(pkm_tasks)
    all_tasks.extend(pkm_non_tasks)

    count_forge = sum(len(v) for v in forge_map.values())
    count_pkm_task = len(pkm_tasks)
    count_pkm_non_task = len(pkm_non_tasks)

    new_tasks = dedup(all_tasks, existing_pool)
    count_new = len(new_tasks)
    count_deduped = len(all_tasks) - count_new

    if new_tasks:
        task_lines = [t["line"] for t in new_tasks]
        lines, bucket_idx = find_or_create_bucket(lines)
        lines = insert_tasks_after_bucket(lines, bucket_idx, task_lines)
        try:
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"falha de write: {exc}\n")
            return 1

    result = {
        "tasks": [{"line": t["line"], "type": t["type"]} for t in new_tasks],
        "count_forge": count_forge,
        "count_pkm_task": count_pkm_task,
        "count_pkm_non_task": count_pkm_non_task,
        "count_pkm": count_pkm_task + count_pkm_non_task,
        "count_new": count_new,
        "count_deduped": count_deduped,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
