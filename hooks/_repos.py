"""Helper compartilhado de parsing do `~/Projects/meta-system/REPOS.md`.

Extraído de `suggest_session_start_tip.py` (per ADR-001 SD17 — acionamento do
gatilho de generalização de SD6 Adendo v0.2.0: 2 hooks SessionStart com o mesmo
gate cwd↔REPOS.md). Reusado por `suggest_session_start_tip.py` e
`suggest_reconcile.py` em vez de re-derivar o parser de tabela markdown.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

OVERVIEW_H2_PATTERN = re.compile(r"^Clusters(\b|\s|\()", re.IGNORECASE)
EXCLUDED_H3_TOKEN = "consumido externo"


def _derive_basename(path_str: str) -> str | None:
    """Derive basename from a REPOS.md Path column value.

    Strip pattern `.strip().strip("`").strip()` tolera whitespace + tabs antes E
    depois dos backticks markdown. Tilde expanded via `os.path.expanduser` antes
    do basename. Returns None se path_str fica vazio após cleanup.
    """
    cleaned = path_str.strip().strip("`").strip()
    if not cleaned:
        return None
    return os.path.basename(os.path.expanduser(cleaned))


def _load_owned_active(repos_md_path: Path) -> dict[str, str]:
    """Parse REPOS.md, return dict `match_key → bucket_name` (filtro NEGATIVO).

    Cada entry owned/active gera 1 ou 2 chaves no dict:
    - Sempre: `repo_field → repo_field` (canonical chave = bucket name).
    - Condicionalmente: se a coluna Path existe E `basename(expanduser(path))`
      diverge do Repo field, adiciona `basename → repo_field`.

    Colisão de basename derivado entre 2 entries: last write wins.
    """
    if not repos_md_path.is_file():
        return {}
    text = repos_md_path.read_text(encoding="utf-8")

    owned: dict[str, str] = {}
    current_h2: str | None = None
    current_h3: str | None = None
    repo_col_idx: int | None = None
    status_col_idx: int | None = None
    path_col_idx: int | None = None
    in_table_header_seen = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("## ") and not line.startswith("### "):
            current_h2 = line[3:].strip()
            current_h3 = None
            repo_col_idx = None
            status_col_idx = None
            path_col_idx = None
            in_table_header_seen = False
            continue
        if line.startswith("### "):
            current_h3 = line[4:].strip()
            repo_col_idx = None
            status_col_idx = None
            path_col_idx = None
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
                path_col_idx = lower_cells.index("path") if "path" in lower_cells else None
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
                owned[repo_field] = repo_field
                if path_col_idx is not None and path_col_idx < len(cells):
                    derived = _derive_basename(cells[path_col_idx])
                    if derived and derived != repo_field:
                        owned[derived] = repo_field
            continue

        if in_table_header_seen and not line.startswith("|"):
            in_table_header_seen = False
            repo_col_idx = None
            status_col_idx = None
            path_col_idx = None

    return owned
