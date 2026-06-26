"""Tests para hooks/suggest_session_start_tip.py — 2ª trajetória hook bridging.

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest):
- Unit: _load_owned_active com REPOS.md sintético cobrindo filtro NEGATIVO,
  Status filter, cobertura cross-cluster, casos degenerados, derivação Path
  column basename (path-vs-Repo divergence fix), colisão last-write-wins.
- Unit: _derive_basename helper isolado (strip 3-pattern + expanduser + basename).
- E2E in-process: main() exercitada com monkeypatch de REPOS_MD + stdin sintético,
  cobrindo stdin malformado, cwd fora de git, match canonical, match via Path
  basename derivado.
"""
import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "hooks" / "suggest_session_start_tip.py"
_spec = importlib.util.spec_from_file_location("suggest_session_start_tip", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

# Parser extraído para hooks/_repos.py (ADR-001 SD17); o hook acima já inseriu
# hooks/ no sys.path ao executar, então `_repos` resolve aqui.
from _repos import _derive_basename  # noqa: E402


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
    assert hook._load_owned_active(repos) == {"meta-bridge": "meta-bridge"}


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
        "| `meta-system` | `~/Projects/meta-system` | doc | active | github |\n"
    )
    assert hook._load_owned_active(repos) == {"meta-system": "meta-system"}


def test_load_owned_active_filters_consumido_externo_subsection(tmp_path):
    """Tabela sob `### Runtime auxiliar consumido externo` é excluída."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "### Owned (doctrine)\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-system` | `~/Projects/meta-system` | doc | active | github |\n\n"
        "### Runtime auxiliar consumido externo\n\n"
        "| Repo | Upstream | Eixo | Install | License |\n"
        "|---|---|---|---|---|\n"
        "| `splitrail` | github | mcp | tarball | MIT |\n"
    )
    assert hook._load_owned_active(repos) == {"meta-system": "meta-system"}


def test_load_owned_active_status_filter(tmp_path):
    """Status filter: active aceito; archived e external-dep rejeitados."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `active-repo` | `~/path/active-repo` | doc | active | github |\n"
        "| `archived-repo` | `~/path/archived-repo` | doc | archived | github |\n"
        "| `external-repo` | `~/path/external-repo` | doc | external-dep | github |\n"
    )
    assert hook._load_owned_active(repos) == {"active-repo": "active-repo"}


def test_load_owned_active_missing_file_returns_empty_dict(tmp_path):
    """REPOS.md ausente → dict vazio (degradação graciosa)."""
    assert hook._load_owned_active(tmp_path / "absent.md") == {}


def test_load_owned_active_cross_cluster_coverage(tmp_path):
    """≥1 repo por cluster sem `### Owned` é reconhecido (cobertura F3)."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "### Owned\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-system` | `~/Projects/meta-system` | y | active | z |\n\n"
        "## env-stack\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `dotfiles` | `~/.local/share/dotfiles` | y | active | z |\n\n"
        "## dev-toolkit\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-bridge` | `~/Projects/meta-bridge` | y | active | z |\n"
    )
    assert hook._load_owned_active(repos) == {
        "meta-system": "meta-system",
        "dotfiles": "dotfiles",
        "meta-bridge": "meta-bridge",
    }


# ---------- Unit tests: derivação Path basename (bug fix path-vs-Repo) ----------

def test_load_owned_active_extracts_path_basename_when_diverges(tmp_path):
    """Path basename ≠ Repo field → dict adiciona chave derivada apontando pro Repo canonical."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## cognitive\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `logseq-notes` | `~/Notes/logseq` | notes | active | github |\n"
    )
    result = hook._load_owned_active(repos)
    assert result == {"logseq-notes": "logseq-notes", "logseq": "logseq-notes"}


def test_load_owned_active_uses_repo_only_when_basename_matches(tmp_path):
    """Path basename == Repo field → só canonical key (derivation skipped)."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## dev-toolkit\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `meta-bridge` | `~/Projects/meta-bridge` | bridge | active | github |\n"
    )
    result = hook._load_owned_active(repos)
    assert result == {"meta-bridge": "meta-bridge"}
    assert len(result) == 1, "basename igual ao Repo não deve adicionar chave derivada"


def test_load_owned_active_handles_tilde_expansion(tmp_path):
    """Path com `~/` é expandido via os.path.expanduser antes do basename."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## env-stack\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `dotfiles` | `~/.local/share/chezmoi` | dotfiles | active | github |\n"
    )
    result = hook._load_owned_active(repos)
    assert result == {"dotfiles": "dotfiles", "chezmoi": "dotfiles"}


def test_load_owned_active_skips_when_path_column_empty(tmp_path):
    """Path field vazio/whitespace → só canonical Repo key (derivation skipped graceful)."""
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `repo-empty-path` |  | doc | active | github |\n"
        "| `repo-whitespace-path` |    | doc | active | github |\n"
    )
    result = hook._load_owned_active(repos)
    assert result == {
        "repo-empty-path": "repo-empty-path",
        "repo-whitespace-path": "repo-whitespace-path",
    }


def test_load_owned_active_collision_last_write_wins(tmp_path):
    """Colisão de basename derivado: última entry parsed vence (dict overwrite).

    Comportamento determinístico via ordem de iteração do parser; regression test
    protege contra refactor futuro de ordem de iteração mudar resultado silently.
    """
    repos = tmp_path / "REPOS.md"
    repos.write_text(
        "## meta\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        "| `repo-a` | `~/some/foo` | x | active | z |\n"
        "| `repo-b` | `~/other/foo` | y | active | z |\n"
    )
    result = hook._load_owned_active(repos)
    # Ambas canonical keys presentes
    assert result["repo-a"] == "repo-a"
    assert result["repo-b"] == "repo-b"
    # Collision key: last write wins (repo-b parsed após repo-a)
    assert result["foo"] == "repo-b"


# ---------- Unit test: _derive_basename helper isolado ----------

def test_derive_basename_strips_backticks_and_expands_tilde():
    """Helper _derive_basename: strip 3-pattern + expanduser + basename."""
    # Backticks ao redor do path
    assert _derive_basename("`~/Notes/logseq`") == "logseq"
    # Sem backticks
    assert _derive_basename("~/Scripts") == "Scripts"
    # Tilde expansion + path com mais segmentos
    assert _derive_basename("~/.local/share/chezmoi") == "chezmoi"
    # Whitespace fora dos backticks (3-strip pattern tolera)
    assert _derive_basename("  `~/Notes/logseq`  ") == "logseq"
    # Empty/whitespace-only retorna None
    assert _derive_basename("") is None
    assert _derive_basename("   ") is None
    assert _derive_basename("`  `") is None


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
        f"| `{basename}` | `~/path/{basename}` | y | active | z |\n"
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
        f"| `{basename}` | `~/path/{basename}` | y | active | z |\n"
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
        "| `different-repo` | `~/path/different-repo` | y | active | z |\n"
    )
    monkeypatch.setattr(hook, "REPOS_MD", synthetic)
    _set_stdin(monkeypatch, {"cwd": str(worktree_root), "hook_event_name": "SessionStart"})

    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_match_via_path_basename(monkeypatch, capsys, tmp_path):
    """cwd basename casa chave derivada da Path column (não Repo field direto) → tip cita Repo canonical."""
    # Real git repo com basename que diverge do Repo field em REPOS.md
    fake_repo_dir = tmp_path / "logseq"  # basename = `logseq`
    fake_repo_dir.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=str(fake_repo_dir),
        check=True,
        capture_output=True,
    )

    # Synthetic REPOS.md: Repo=`logseq-notes` Path resolve pra basename `logseq`
    synthetic = tmp_path / "REPOS.md"
    synthetic.write_text(
        "## cognitive\n\n"
        "| Repo | Path | Propósito | Status | Host |\n"
        "|---|---|---|---|---|\n"
        f"| `logseq-notes` | `{fake_repo_dir}` | notes | active | github |\n"
    )
    monkeypatch.setattr(hook, "REPOS_MD", synthetic)
    _set_stdin(monkeypatch, {"cwd": str(fake_repo_dir), "hook_event_name": "SessionStart"})

    rc = hook.main()
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "systemMessage" in payload
    assert "--bucket logseq-notes " in payload["systemMessage"], (
        "tip deve citar Repo field canonical (logseq-notes), não cwd basename (logseq)"
    )
