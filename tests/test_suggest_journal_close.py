"""Tests para hooks/suggest_journal_close.py — guard isinstance(event, dict).

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest).
Fix: issue #17 — JSON scalar input (string/null/array) atravessava try/except e
quebrava em event.get(). Guard adicionado em main() após JSONDecodeError block.
"""
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "hooks" / "suggest_journal_close.py"
_spec = importlib.util.spec_from_file_location("suggest_journal_close", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _set_stdin(monkeypatch, data: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(data))


def test_main_json_null_exits_silent(monkeypatch, capsys):
    """stdin com JSON null → exit 0 sem stdout."""
    _set_stdin(monkeypatch, "null")
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_json_string_exits_silent(monkeypatch, capsys):
    """stdin com JSON string → exit 0 sem stdout."""
    _set_stdin(monkeypatch, '"hello"')
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_json_array_exits_silent(monkeypatch, capsys):
    """stdin com JSON array → exit 0 sem stdout."""
    _set_stdin(monkeypatch, '[1, 2, 3]')
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_empty_stdin_exits_silent(monkeypatch, capsys):
    """stdin vazio (JSONDecodeError) → exit 0 sem stdout."""
    _set_stdin(monkeypatch, "")
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""
