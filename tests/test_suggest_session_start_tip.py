"""Tests para hooks/suggest_session_start_tip.py — 2ª trajetória hook bridging.

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest):
- Unit: _load_owned_active com REPOS.md sintético cobrindo filtro NEGATIVO,
  Status filter, cobertura cross-cluster, casos degenerados.
- E2E in-process: main() exercitada com monkeypatch de REPOS_MD + stdin sintético,
  cobrindo stdin malformado, cwd fora de git, match/no-match.
"""
import importlib.util
import io
import json
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "hooks" / "suggest_session_start_tip.py"
_spec = importlib.util.spec_from_file_location("suggest_session_start_tip", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


# ---------- Unit tests: _load_owned_active ----------

def test_load_owned_active_canonical_table(tmp_path):
    """Tabela canonical sob `## <cluster>` sem subsection: extract Status=active."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "# REPOS\n\n"
        "## dev-toolkit\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-bridge` | `~/Projects/meta-bridge` | bridge | active | github |\n"
    )
    assert hook._load_owned_active(repos) == {"meta-bridge"}


def test_load_owned_active_filters_overview_clusters_table(tmp_path):
    """Overview `## Clusters (N)` com tabela `| Cluster | ... |` não vaza."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## Clusters (2)\n\n"
        "| Cluster | Domínio | Owner | Count |\n"
        "|---|---|---|---|\n"
        "| meta | doc | Camada Meta | 1 |\n"
        "| dev-toolkit | wf | Camada 3 | 1 |\n\n"
        "## meta\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-system` | path | doc | active | github |\n"
    )
    assert hook._load_owned_active(repos) == {"meta-system"}


def test_load_owned_active_filters_consumido_externo_subsection(tmp_path):
    """Tabela sob `### Runtime auxiliar consumido externo` é excluída."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "### Owned (doctrine)\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-system` | path | doc | active | github |\n\n"
        "### Runtime auxiliar consumido externo\n\n"
        "| Repo | Upstream | Eixo | Install | License |\n"
        "|---|---|---|---|---|\n"
        "| `splitrail` | github | mcp | tarball | MIT |\n"
    )
    assert hook._load_owned_active(repos) == {"meta-system"}


def test_load_owned_active_status_filter(tmp_path):
    """Status filter: active aceito; archived e external-dep rejeitados."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `active-repo` | path | doc | active | github |\n"
        "| `archived-repo` | path | doc | archived | github |\n"
        "| `external-repo` | path | doc | external-dep | github |\n"
    )
    assert hook._load_owned_active(repos) == {"active-repo"}


def test_load_owned_active_missing_file_returns_empty_set(tmp_path):
    """REPOS.md ausente → set vazio (degradação graciosa)."""
    assert hook._load_owned_active(tmp_path / "absent.md") == set()


def test_load_owned_active_cross_cluster_coverage(tmp_path):
    """≥1 repo por cluster sem `### Owned` é reconhecido (cobertura F3)."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "### Owned\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-system` | x | y | active | z |\n\n"
        "## env-stack\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `dotfiles` | x | y | active | z |\n\n"
        "## dev-toolkit\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-bridge` | x | y | active | z |\n"
    )
    assert hook._load_owned_active(repos) == {"meta-system", "dotfiles", "meta-bridge"}


# ---------- E2E tests: main() in-process via monkeypatch ----------

def _set_stdin(monkeypatch, payload: dict | None) -> None:
    """Inject stdin payload (None = empty)."""
    data = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr("sys.stdin", io.StringIO(data))


def test_main_empty_stdin_exits_silent(monkeypatch, capsys):
    """stdin vazio (JSONDecodeError) → exit 0 sem stdout."""
    _set_stdin(monkeypatch, None)
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_cwd_outside_git_exits_silent(monkeypatch, capsys, tmp_path):
    """cwd fora de git → exit 0 sem stdout."""
    _set_stdin(monkeypatch, {"cwd": str(tmp_path), "hook_event_name": "SessionStart"})
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_missing_repos_md_exits_silent(monkeypatch, capsys, tmp_path):
    """REPOS.md ausente + cwd em git repo → exit 0 sem stdout."""
    monkeypatch.setattr(hook, "REPOS_MD", tmp_path / "absent.md")
    worktree_root = Path(__file__).resolve().parent.parent
    _set_stdin(monkeypatch, {"cwd": str(worktree_root), "hook_event_name": "SessionStart"})
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_match_emits_system_message(monkeypatch, capsys, tmp_path):
    """REPOS.md sintético com basename do worktree → emit JSON systemMessage."""
    worktree_root = Path(__file__).resolve().parent.parent
    basename = worktree_root.name
    synthetic = tmp_path / "REPOS.md"
    synthetic.write_text(
        "## dev-toolkit\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        f"| `{basename}` | x | y | active | z |\n"
    )
    monkeypatch.setattr(hook, "REPOS_MD", synthetic)
    _set_stdin(monkeypatch, {"cwd": str(worktree_root), "hook_event_name": "SessionStart"})

    rc = hook.main()
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "systemMessage" in payload
    assert basename in payload["systemMessage"]
    assert "/journal-load --days 2" in payload["systemMessage"]


def test_main_match_emits_for_subdirectory_of_owned_repo(monkeypatch, capsys, tmp_path):
    """cwd em subdir do repo owned → toplevel basename resolve corretamente."""
    worktree_root = Path(__file__).resolve().parent.parent
    subdir = worktree_root / "hooks"
    assert subdir.is_dir(), "subdir do worktree usado como cwd deve existir"
    basename = worktree_root.name
    synthetic = tmp_path / "REPOS.md"
    synthetic.write_text(
        "## dev-toolkit\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        f"| `{basename}` | x | y | active | z |\n"
    )
    monkeypatch.setattr(hook, "REPOS_MD", synthetic)
    _set_stdin(monkeypatch, {"cwd": str(subdir), "hook_event_name": "SessionStart"})

    rc = hook.main()
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert basename in payload["systemMessage"]
    assert subdir.name not in payload["systemMessage"], (
        "systemMessage deve usar basename do TOPLEVEL, não do subdiretório passado como cwd"
    )


def test_main_no_match_exits_silent(monkeypatch, capsys, tmp_path):
    """REPOS.md sintético sem basename → exit 0 sem stdout."""
    worktree_root = Path(__file__).resolve().parent.parent
    synthetic = tmp_path / "REPOS.md"
    synthetic.write_text(
        "## meta\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `different-repo` | x | y | active | z |\n"
    )
    monkeypatch.setattr(hook, "REPOS_MD", synthetic)
    _set_stdin(monkeypatch, {"cwd": str(worktree_root), "hook_event_name": "SessionStart"})

    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""
