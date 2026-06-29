"""Tests para o dual-path gate-kill (ADR-003 Adendo 2026-06-28, ADR-001 SD20).

Para cada subcomando de write valida:
- Logseq aberto → roteia para a função HTTP correspondente
- Logseq aberto + HTTP error → exit não-zero (failure-closed, sem fallback file-direct)
- Logseq fechado → função HTTP NÃO chamada (routing correto)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from meta_bridge.cli import cli
from meta_bridge.logseq_http import LogseqHTTPError


# ---------------------------------------------------------------------------
# journal-note
# ---------------------------------------------------------------------------

class TestJournalNoteGate:
    def test_open_routes_to_http(self):
        with (
            patch("meta_bridge.journal_note.logseq_open", return_value=True),
            patch("meta_bridge.journal_note._note_via_http") as mock_http,
        ):
            result = CliRunner().invoke(cli, ["journal-note", "--domain", "test", "TODO fix"])
        assert result.exit_code == 0
        mock_http.assert_called_once()

    def test_http_error_exits_nonzero(self):
        with (
            patch("meta_bridge.journal_note.logseq_open", return_value=True),
            patch("meta_bridge.journal_note._note_via_http", side_effect=LogseqHTTPError("err")),
        ):
            result = CliRunner().invoke(cli, ["journal-note", "--domain", "test", "TODO fix"])
        assert result.exit_code != 0

    def test_closed_does_not_call_http(self):
        with (
            patch("meta_bridge.journal_note.logseq_open", return_value=False),
            patch("meta_bridge.journal_note._note_via_http") as mock_http,
            patch("meta_bridge.journal_note.find_or_create_bucket", return_value=0),
            patch("meta_bridge.journal_note.append_child", return_value=("plain", [])),
            patch("meta_bridge.journal_note._paths") as mock_paths,
        ):
            mock_j = MagicMock()
            mock_j.exists.return_value = True
            mock_j.parent.mkdir.return_value = None
            mock_paths.journal_path.return_value = mock_j
            result = CliRunner().invoke(cli, ["journal-note", "--domain", "test", "TODO fix"])
        mock_http.assert_not_called()


# ---------------------------------------------------------------------------
# journal-close
# ---------------------------------------------------------------------------

class TestJournalCloseGate:
    # Payload mínimo com uma transição — suficiente para passar a validação
    # do parse_payload (não requer ## Append).
    _PAYLOAD = "## Transitions\n- /tmp/j.md:1 | \tTODO old | \tDONE old\n"

    def test_open_routes_to_http(self):
        with (
            patch("meta_bridge.journal_close.logseq_open", return_value=True),
            patch("meta_bridge.journal_close._close_transitions_via_http", return_value=(1, [])) as mock_tr,
            patch("meta_bridge.journal_close._close_append_via_http", return_value=([], 0, 0)),
        ):
            result = CliRunner().invoke(cli, ["journal-close"], input=self._PAYLOAD)
        assert result.exit_code == 0
        mock_tr.assert_called_once()

    def test_http_error_exits_nonzero(self):
        with (
            patch("meta_bridge.journal_close.logseq_open", return_value=True),
            patch(
                "meta_bridge.journal_close._close_transitions_via_http",
                side_effect=LogseqHTTPError("server error"),
            ),
        ):
            result = CliRunner().invoke(cli, ["journal-close"], input=self._PAYLOAD)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# journal-close HTTP append — paridade de sub-bullets + dedup por commit hash
# ---------------------------------------------------------------------------

class TestCloseAppendViaHttp:
    # append_md = corpo do `## Append` (sem header): bucket + child + commit hash.
    _APPEND = "- #dev\n\t- DONE fix parser\n\t\t- commit: abc1234\n"

    def _run(self, bucket_block):
        from meta_bridge import journal_close

        inserted = []
        with (
            patch(
                "meta_bridge.journal_close.logseq_http.find_or_create_bucket_block",
                return_value=("2026/06/28", bucket_block),
            ),
            patch(
                "meta_bridge.journal_close.logseq_http.insert_block_group",
                side_effect=lambda uuid, group: inserted.append((uuid, group)),
            ),
            patch("meta_bridge.journal_close.logseq_http.upsert_block_property"),
        ):
            result = journal_close._close_append_via_http(
                self._APPEND, "2026_06_28", "2026-06-28T10:00:00"
            )
        return result, inserted

    def test_inserts_full_group_not_just_first_line(self):
        # Bucket #dev existe, sem nenhum commit hash → grupo inteiro é inserido.
        bucket = {"uuid": "bkt", "content": "#dev", "children": []}
        (buckets, appended, dedup), inserted = self._run(bucket)
        assert buckets == ["dev"]
        assert (appended, dedup) == (1, 0)
        uuid, group = inserted[0]
        assert uuid == "bkt"
        # sub-bullet commit: preservado (não só a primeira linha do grupo)
        assert any("commit: abc1234" in line for line in group)

    def test_dedup_skips_existing_commit_hash(self):
        # Bucket #dev já tem o commit hash abc1234 como child → dedup-skip.
        bucket = {
            "uuid": "bkt",
            "content": "#dev",
            "children": [{"uuid": "c1", "content": "commit: abc1234", "children": []}],
        }
        (buckets, appended, dedup), inserted = self._run(bucket)
        assert (appended, dedup) == (0, 1)
        assert inserted == []


# ---------------------------------------------------------------------------
# journal-review --apply
# ---------------------------------------------------------------------------

class TestJournalReviewApplyGate:
    # Uma linha de transição parseable por TRANSITION_RE — basta para superar
    # a checagem "nenhuma entry parseável" do apply mode.
    _PAYLOAD = "- /tmp/j.md:1 | \tTODO old | \tDONE old\n"

    def test_open_routes_to_http(self):
        with (
            patch("meta_bridge.journal_review.logseq_open", return_value=True),
            patch("meta_bridge.journal_review._run_apply_via_http") as mock_apply,
        ):
            result = CliRunner().invoke(cli, ["journal-review", "--apply"], input=self._PAYLOAD)
        assert result.exit_code == 0
        mock_apply.assert_called_once()

    def test_http_error_exits_nonzero(self):
        with (
            patch("meta_bridge.journal_review.logseq_open", return_value=True),
            patch(
                "meta_bridge.journal_review._run_apply_via_http",
                side_effect=LogseqHTTPError("server error"),
            ),
        ):
            result = CliRunner().invoke(cli, ["journal-review", "--apply"], input=self._PAYLOAD)
        assert result.exit_code != 0

    def test_scan_mode_no_gate_needed(self):
        """Scan mode (sem --apply) é read-only — não chama logseq_open nem HTTP."""
        with (
            patch("meta_bridge.journal_review.logseq_open") as mock_open,
            patch("meta_bridge.journal_review._run_apply_via_http") as mock_apply,
            patch("meta_bridge.journal_review._paths.PAGES_DIR") as mock_pages,
            patch("meta_bridge.journal_review._paths.journal_path") as mock_jp,
        ):
            # Nenhum journal existe → CLI informa "nenhum journal encontrado", exit 0
            mock_jp.return_value = MagicMock(exists=lambda: False)
            mock_pages.rglob.return_value = []
            result = CliRunner().invoke(cli, ["journal-review", "--days", "0"])
        mock_open.assert_not_called()
        mock_apply.assert_not_called()


# ---------------------------------------------------------------------------
# init-project
# ---------------------------------------------------------------------------

class TestInitProjectGate:
    def _git_ok(self):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "/tmp/test-repo\n"
        return m

    def test_open_routes_to_http(self):
        with (
            patch("meta_bridge.init_project.subprocess.run", return_value=self._git_ok()),
            patch("meta_bridge.init_project.derive_repo_host", return_value="#github"),
            patch("meta_bridge.init_project.extract_description", return_value=""),
            patch("meta_bridge.init_project.logseq_open", return_value=True),
            patch("meta_bridge.init_project._init_via_http", return_value="criado") as mock_init,
        ):
            result = CliRunner().invoke(cli, ["init-project", "--cluster", "test"])
        assert result.exit_code == 0
        mock_init.assert_called_once()

    def test_http_error_exits_nonzero(self):
        with (
            patch("meta_bridge.init_project.subprocess.run", return_value=self._git_ok()),
            patch("meta_bridge.init_project.derive_repo_host", return_value="#github"),
            patch("meta_bridge.init_project.extract_description", return_value=""),
            patch("meta_bridge.init_project.logseq_open", return_value=True),
            patch("meta_bridge.init_project._init_via_http", side_effect=LogseqHTTPError("err")),
        ):
            result = CliRunner().invoke(cli, ["init-project", "--cluster", "test"])
        assert result.exit_code != 0

    def test_closed_does_not_call_http(self):
        with (
            patch("meta_bridge.init_project.subprocess.run", return_value=self._git_ok()),
            patch("meta_bridge.init_project.derive_repo_host", return_value="#github"),
            patch("meta_bridge.init_project.extract_description", return_value=""),
            patch("meta_bridge.init_project.logseq_open", return_value=False),
            patch("meta_bridge.init_project._init_via_http") as mock_init,
            patch("meta_bridge.init_project._paths") as mock_paths,
            patch("meta_bridge.init_project.bootstrap_from_template", return_value=["- cluster:: test"]),
            patch("meta_bridge.init_project.fill_props_in_template", return_value=["- cluster:: test"]),
        ):
            mock_p = MagicMock()
            mock_p.exists.return_value = False
            mock_p.parent.mkdir.return_value = None
            mock_p.write_text.return_value = None
            mock_paths.page_path.return_value = mock_p
            result = CliRunner().invoke(cli, ["init-project", "--cluster", "test"])
        mock_init.assert_not_called()
