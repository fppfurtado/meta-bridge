"""Tests para meta_bridge.reconcile_apply (faceta C do reconciler)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from meta_bridge.cli import cli
from meta_bridge.logseq_http import logseq_page_name_candidates as _derive_logseq_page_name
from meta_bridge.reconcile_apply import (
    _find_block_uuid,
    _mark_done,
)


# ---------------------------------------------------------------------------
# logseq_page_name_candidates (formerly _derive_logseq_page_name)
# ---------------------------------------------------------------------------

class TestDeriveLogseqPageName:
    def test_valid_stem_returns_two_candidates(self):
        result = _derive_logseq_page_name("2026_06_27.md")
        assert len(result) == 2
        names = [name for name, _ in result]
        assert names[0] == "2026-06-27"
        assert names[1] == "Jun 27th, 2026"

    def test_ordinal_suffix_variants(self):
        # 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st
        cases = [
            ("2026_06_01.md", "Jun 1st, 2026"),
            ("2026_06_02.md", "Jun 2nd, 2026"),
            ("2026_06_03.md", "Jun 3rd, 2026"),
            ("2026_06_04.md", "Jun 4th, 2026"),
            ("2026_06_11.md", "Jun 11th, 2026"),
            ("2026_06_12.md", "Jun 12th, 2026"),
            ("2026_06_13.md", "Jun 13th, 2026"),
            ("2026_06_21.md", "Jun 21st, 2026"),
        ]
        for path, expected_ordinal in cases:
            result = _derive_logseq_page_name(path)
            assert result[1][0] == expected_ordinal, f"Failed for {path}"

    def test_invalid_stem_returns_empty(self):
        assert _derive_logseq_page_name("not-a-date.md") == []
        assert _derive_logseq_page_name("2026_06.md") == []


# ---------------------------------------------------------------------------
# _find_block_uuid
# ---------------------------------------------------------------------------

class TestFindBlockUuid:
    def test_found_at_top_level(self):
        tree = [
            {"uuid": "abc-1", "content": "TODO task one (#1)", "children": []},
            {"uuid": "abc-2", "content": "TODO task two (#2)", "children": []},
        ]
        assert _find_block_uuid(tree, "TODO task one (#1)") == "abc-1"

    def test_found_nested(self):
        tree = [
            {
                "uuid": "parent",
                "content": "parent block",
                "children": [
                    {"uuid": "child-1", "content": "TODO nested task (#3)", "children": []},
                ],
            }
        ]
        assert _find_block_uuid(tree, "TODO nested task (#3)") == "child-1"

    def test_not_found_returns_none(self):
        tree = [{"uuid": "abc", "content": "something else", "children": []}]
        assert _find_block_uuid(tree, "TODO missing (#99)") is None


# ---------------------------------------------------------------------------
# _mark_done
# ---------------------------------------------------------------------------

class TestMarkDone:
    @pytest.mark.parametrize("marker", ["TODO", "DOING", "WAITING", "NOW", "LATER"])
    def test_replaces_open_marker(self, marker):
        text = f"{marker} fix auth bug (#12)"
        result = _mark_done(text)
        assert result == f"DONE fix auth bug (#12)"

    def test_no_marker_unchanged(self):
        text = "DONE already closed (#5)"
        assert _mark_done(text) == text

    def test_plain_text_unchanged(self):
        text = "fix auth bug (#12)"
        assert _mark_done(text) == text

    def test_preserves_rest_of_text(self):
        text = "TODO implement reconciler faceta C (#48) [[meta-bridge]]"
        assert _mark_done(text) == "DONE implement reconciler faceta C (#48) [[meta-bridge]]"


# ---------------------------------------------------------------------------
# CLI — reconcile-apply
# ---------------------------------------------------------------------------

class TestReconcileApplyCLI:
    def test_invalid_json_exits_nonzero(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "reconcile-apply",
            "--findings-json", "not valid json",
            "--journal-path", "~/Notes/logseq/journals/2026_06_27.md",
        ])
        assert result.exit_code != 0

    def test_empty_findings_returns_empty_json(self):
        runner = CliRunner()
        findings = json.dumps([
            {"check": "notes_encerrada", "entry": "some note", "date": "2026-06-20"},
        ])
        result = runner.invoke(cli, [
            "reconcile-apply",
            "--findings-json", findings,
            "--journal-path", "~/Notes/logseq/journals/2026_06_27.md",
        ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == {"applied": [], "skipped": [], "error": None}

    def test_http_error_returns_error_field_exit_zero(self):
        from meta_bridge.logseq_http import LogseqHTTPError
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": "TODO close issue (#48)", "repo": "meta-bridge", "iid": 48},
        ])
        with patch("meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree") as mock_tree:
            mock_tree.side_effect = LogseqHTTPError("Logseq HTTP server não acessível")
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["error"] is not None
        assert "Logseq" in output["error"]
        assert output["applied"] == []

    def test_apply_marks_task_done(self):
        task_text = "TODO implement reconciler faceta C (#48)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_text, "repo": "meta-bridge", "iid": 48},
        ])
        tree = [{"uuid": "uuid-abc", "content": task_text, "children": []}]
        with (
            patch("meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree", return_value=tree),
            patch("meta_bridge.reconcile_apply.logseq_http.update_block") as mock_update,
        ):
            mock_update.return_value = None
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["error"] is None
        assert task_text in output["applied"]
        mock_update.assert_called_once_with("uuid-abc", "DONE implement reconciler faceta C (#48)")

    def test_fallback_ordinal_us_when_iso_returns_empty(self):
        task_text = "TODO fallback task (#10)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_text, "repo": "meta-bridge", "iid": 10},
        ])
        tree = [{"uuid": "uuid-xyz", "content": task_text, "children": []}]
        # ISO candidate returns [] (page not found), ordinal-US candidate returns tree
        with (
            patch(
                "meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree",
                side_effect=[[], tree],
            ) as mock_tree,
            patch("meta_bridge.reconcile_apply.logseq_http.update_block", return_value=None),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert task_text in output["applied"]
        assert mock_tree.call_count == 2

    def test_page_not_found_all_candidates_skipped(self):
        task_text = "TODO task not found (#7)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_text, "repo": "meta-bridge", "iid": 7},
        ])
        with patch("meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree", return_value=[]):
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["error"] is None
        assert output["applied"] == []
        assert output["skipped"][0]["reason"].startswith("page_not_found:")

    def test_update_block_error_sets_error_field_and_skips(self):
        from meta_bridge.logseq_http import LogseqHTTPError
        task_text = "TODO update will fail (#6)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_text, "repo": "meta-bridge", "iid": 6},
        ])
        tree = [{"uuid": "uuid-fail", "content": task_text, "children": []}]
        with (
            patch("meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree", return_value=tree),
            patch(
                "meta_bridge.reconcile_apply.logseq_http.update_block",
                side_effect=LogseqHTTPError("HTTP 500"),
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["error"] is not None
        assert output["applied"] == []
        assert output["skipped"][0]["reason"].startswith("update_error:")

    def test_block_not_found_in_tree_skipped(self):
        task_text = "TODO this block is gone (#9)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_text, "repo": "meta-bridge", "iid": 9},
        ])
        tree = [{"uuid": "uuid-other", "content": "TODO something else (#99)", "children": []}]
        with patch("meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree", return_value=tree):
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["applied"] == []
        assert output["skipped"][0]["reason"].startswith("block_not_found")

    def test_multiple_findings_partial_apply(self):
        task_ok = "TODO apply this one (#11)"
        task_missing = "TODO missing block (#12)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_ok, "repo": "meta-bridge", "iid": 11},
            {"check": "journal_forge_closed", "task": task_missing, "repo": "meta-bridge", "iid": 12},
        ])
        tree = [{"uuid": "uuid-ok", "content": task_ok, "children": []}]
        with (
            patch("meta_bridge.reconcile_apply.logseq_http.get_page_blocks_tree", return_value=tree),
            patch("meta_bridge.reconcile_apply.logseq_http.update_block", return_value=None),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, [
                "reconcile-apply",
                "--findings-json", findings,
                "--journal-path", "2026_06_27.md",
            ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output["applied"]) == 1
        assert task_ok in output["applied"]
        assert len(output["skipped"]) == 1
        assert output["skipped"][0]["task"] == task_missing

    def test_invalid_journal_path_skips_with_page_name_unresolvable(self):
        task_text = "TODO task with bad path (#13)"
        findings = json.dumps([
            {"check": "journal_forge_closed", "task": task_text, "repo": "meta-bridge", "iid": 13},
        ])
        runner = CliRunner()
        result = runner.invoke(cli, [
            "reconcile-apply",
            "--findings-json", findings,
            "--journal-path", "not-a-date.md",
        ])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["applied"] == []
        assert output["skipped"][0]["reason"] == "page_name_unresolvable"
