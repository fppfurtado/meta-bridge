"""Tests para meta_bridge/reconcile_check.py — faceta A do reconciler (#46).

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest):
- check_journal_forge_closed: bucket #<repo> + #inbox via hashtag; match por
  (#<iid>); marker aberto vs DONE; sem iid; repo desconhecido; task aninhada.
- check_notes_encerrada: marcador ancorado (bullet/bold/linha) vs prosa
  incidental; um finding por entry.
- CLI: integração full, failure-open (closed-issues vazio), journal/NOTES
  ausentes, JSON inválido. Forge não é chamado (skill orquestra) — sem mock de rede.
"""
import json

import pytest
from click.testing import CliRunner

from meta_bridge import logseq, reconcile_check
from meta_bridge.cli import cli


def _blocks(text: str):
    _, blocks = logseq.parse_document(text)
    return blocks


# --- check_journal_forge_closed ---


def test_forge_closed_repo_bucket():
    blocks = _blocks("- #meta-bridge\n\t- TODO encerrar substrato (#41)\n")
    f = reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]})
    assert len(f) == 1
    assert f[0]["repo"] == "meta-bridge" and f[0]["iid"] == 41
    assert f[0]["task"] == "TODO encerrar substrato (#41)"  # shape do payload pra skill


@pytest.mark.parametrize("marker", ["DOING", "NOW", "LATER"])
def test_forge_open_markers_yield_finding(marker):
    blocks = _blocks(f"- #meta-bridge\n\t- {marker} algo (#41)\n")
    assert len(reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]})) == 1


@pytest.mark.parametrize("marker", ["CANCELLED", "CANCELED"])
def test_forge_cancelled_no_finding(marker):
    blocks = _blocks(f"- #meta-bridge\n\t- {marker} desistido (#41)\n")
    assert reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]}) == []


def test_forge_iid_closed_in_other_repo_no_finding():
    # iid 41 fechado em repo-a, mas a task está no bucket #repo-b → não casa.
    blocks = _blocks("- #repo-b\n\t- TODO x (#41)\n")
    closed = {"repo-a": [41], "repo-b": [99]}
    assert reconcile_check.check_journal_forge_closed(blocks, closed) == []


def test_forge_inbox_iid_belongs_to_other_known_repo_no_finding():
    # task #inbox tagueada #meta-bridge com (#45), mas 45 está fechado em other-repo.
    blocks = _blocks("- #inbox\n\t- TODO x (#45)  #inbox #meta-bridge\n")
    closed = {"meta-bridge": [99], "other-repo": [45]}
    assert reconcile_check.check_journal_forge_closed(blocks, closed) == []


def test_forge_open_issue_no_finding():
    blocks = _blocks("- #meta-bridge\n\t- TODO algo (#99)\n")
    assert reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]}) == []


def test_forge_done_task_no_finding():
    blocks = _blocks("- #meta-bridge\n\t- DONE feito (#41)\n")
    assert reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]}) == []


def test_forge_no_iid_no_finding():
    blocks = _blocks("- #meta-bridge\n\t- TODO sem iid\n")
    assert reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]}) == []


def test_forge_inbox_hashtag_match():
    blocks = _blocks("- #inbox\n\t- WAITING revisar (#45)  #inbox #meta-bridge\n")
    f = reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [45]})
    assert len(f) == 1 and f[0]["iid"] == 45 and f[0]["repo"] == "meta-bridge"


def test_forge_inbox_unknown_repo_no_finding():
    blocks = _blocks("- #inbox\n\t- TODO x (#5)  #inbox #other-repo\n")
    assert reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [5]}) == []


def test_forge_bucket_not_in_closed_set():
    blocks = _blocks("- #random-bucket\n\t- TODO x (#41)\n")
    assert reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]}) == []


def test_forge_nested_task_attributed_to_bucket():
    blocks = _blocks("- #meta-bridge\n\t- agrupamento\n\t\t- TODO nested (#41)\n")
    f = reconcile_check.check_journal_forge_closed(blocks, {"meta-bridge": [41]})
    assert len(f) == 1 and f[0]["iid"] == 41


# --- check_notes_encerrada ---


def test_notes_encerrada_bullet_bold():
    f = reconcile_check.check_notes_encerrada("## entry\n\t- **Encerrada 2026-06-24: PASS.**\n")
    assert len(f) == 1 and f[0]["entry"] == "entry" and f[0]["date"] == "2026-06-24"


def test_notes_encerrada_plain_line():
    assert len(reconcile_check.check_notes_encerrada("## e\nEncerrada 2026-06-23: ok\n")) == 1


def test_notes_incidental_prose_no_finding():
    assert reconcile_check.check_notes_encerrada("## e\nalgo (smoke Encerrada 2026-06-14).\n") == []


def test_notes_one_finding_per_entry():
    txt = "## e1\n- Encerrada 2026-06-01\n- Encerrada 2026-06-02\n## e2\n- Encerrada 2026-06-03\n"
    f = reconcile_check.check_notes_encerrada(txt)
    assert [x["entry"] for x in f] == ["e1", "e2"]


def test_notes_encerrada_before_any_header():
    f = reconcile_check.check_notes_encerrada("- Encerrada 2026-06-01\n## e1\n")
    assert len(f) == 1 and f[0]["entry"] == "(sem header)"


# --- CLI (CliRunner) ---


def test_cli_full(tmp_path):
    journal = tmp_path / "j.md"
    journal.write_text("- #meta-bridge\n\t- TODO x (#41)\n\t- DONE y (#42)\n")
    notes = tmp_path / "NOTES.md"
    notes.write_text("## e\n- Encerrada 2026-06-20: ok\n")
    r = CliRunner().invoke(
        cli,
        ["reconcile-check", "--journal", str(journal), "--notes", str(notes),
         "--closed-issues", '{"meta-bridge": [41]}'],
    )
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert {f["check"] for f in out["findings"]} == {"journal_forge_closed", "notes_encerrada"}
    assert out["checks_run"] == ["journal_forge_closed", "notes_encerrada", "cross_store_dedup"]


def test_cli_failure_open_empty_closed(tmp_path):
    journal = tmp_path / "j.md"
    journal.write_text("- #meta-bridge\n\t- TODO x (#41)\n")
    notes = tmp_path / "NOTES.md"
    notes.write_text("## e\n- Encerrada 2026-06-20\n")
    r = CliRunner().invoke(
        cli,
        ["reconcile-check", "--journal", str(journal), "--notes", str(notes),
         "--closed-issues", "{}"],
    )
    out = json.loads(r.output)
    assert any("journal_forge_closed (sem --closed-issues)" in s for s in out["checks_skipped"])
    assert "notes_encerrada" in out["checks_run"]
    assert all(f["check"] == "notes_encerrada" for f in out["findings"])


def test_cli_journal_absent(tmp_path):
    notes = tmp_path / "NOTES.md"
    notes.write_text("## e\n- Encerrada 2026-06-20\n")
    r = CliRunner().invoke(
        cli,
        ["reconcile-check", "--journal", str(tmp_path / "nope.md"), "--notes", str(notes),
         "--closed-issues", '{"meta-bridge":[41]}'],
    )
    out = json.loads(r.output)
    assert any("journal ausente" in s for s in out["checks_skipped"])


def test_cli_notes_absent(tmp_path):
    journal = tmp_path / "j.md"
    journal.write_text("- #meta-bridge\n\t- TODO x (#41)\n")
    r = CliRunner().invoke(
        cli,
        ["reconcile-check", "--journal", str(journal), "--notes", str(tmp_path / "nope.md"),
         "--closed-issues", '{"meta-bridge":[41]}'],
    )
    out = json.loads(r.output)
    assert any("NOTES.md ausente" in s for s in out["checks_skipped"])


def test_cli_invalid_closed_json(tmp_path):
    journal = tmp_path / "j.md"
    journal.write_text("- #x\n")
    r = CliRunner().invoke(
        cli, ["reconcile-check", "--journal", str(journal), "--closed-issues", "{not json"]
    )
    assert r.exit_code != 0
    assert "JSON inválido" in r.output
