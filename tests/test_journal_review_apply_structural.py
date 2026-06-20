"""Tests para meta_bridge/journal_review.py — apply estrutural (A2 + B2).

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest):
- A2 archived bucket: find-or-create page agregadora, append em section, multi-refs,
  idempotência por bucket name presente, fail-soft em refs inválidos.
- B2 emerging bucket: find-or-create no journal de hoje (reusa journal_note),
  sub-bullet origem opcional, idempotência por construção.
- Payload misto: transitions + structural na mesma invocação.
- Regression legacy v0.3.0: payload `## Transitions`-only ainda aplica.
"""
import datetime
import io
import sys
from pathlib import Path

import pytest

from meta_bridge import _paths
from meta_bridge.journal_review import (
    apply_archived_bucket,
    apply_emerging_bucket,
    parse_structural,
    run_apply_mode,
)


@pytest.fixture
def logseq_root(monkeypatch, tmp_path):
    """Redireciona LOGSEQ_ROOT/JOURNALS_DIR/PAGES_DIR para tmp_path."""
    root = tmp_path / "logseq"
    journals = root / "journals"
    pages = root / "pages"
    journals.mkdir(parents=True)
    pages.mkdir(parents=True)
    monkeypatch.setattr(_paths, "LOGSEQ_ROOT", root)
    monkeypatch.setattr(_paths, "JOURNALS_DIR", journals)
    monkeypatch.setattr(_paths, "PAGES_DIR", pages)
    return root


# ---------- parse_structural ----------

def test_parse_structural_archived_basic():
    raw = (
        "## Structural\n"
        "### Archived buckets\n"
        "- tjpa | judiciario | /tmp/j.md:5;/tmp/j2.md:10\n"
    )
    archived, emerging = parse_structural(raw)
    assert archived == [
        {
            "bucket": "tjpa",
            "categoria": "judiciario",
            "refs": ["/tmp/j.md:5", "/tmp/j2.md:10"],
        }
    ]
    assert emerging == []


def test_parse_structural_emerging_with_origem():
    raw = (
        "## Structural\n"
        "### Emerging buckets\n"
        "- ondas-knowledge-layer | narratives 2026-06-15\n"
    )
    archived, emerging = parse_structural(raw)
    assert archived == []
    assert emerging == [
        {"canonical": "ondas-knowledge-layer", "origem": "narratives 2026-06-15"}
    ]


def test_parse_structural_emerging_no_origem():
    raw = (
        "## Structural\n"
        "### Emerging buckets\n"
        "- ondas-knowledge-layer\n"
    )
    _, emerging = parse_structural(raw)
    assert emerging == [{"canonical": "ondas-knowledge-layer", "origem": None}]


def test_parse_structural_absent():
    raw = "## Transitions\n- /tmp/j.md:5 | TODO foo | DONE foo\n"
    archived, emerging = parse_structural(raw)
    assert archived == []
    assert emerging == []


# ---------- apply_archived_bucket (A2) ----------

def test_archived_page_create_with_refs(logseq_root, tmp_path):
    """A2 cenário 1: page ausente → cria + append entry com block-refs."""
    # Cria refs reais (Path.exists() check passa)
    j1 = logseq_root / "journals" / "2026_06_15.md"
    j1.write_text("- #tjpa\n")
    ok, msg = apply_archived_bucket("tjpa", "judiciario", [f"{j1}:1"])
    assert ok is True
    page = _paths.page_path("judiciario")
    assert page.exists()
    content = page.read_text()
    assert "- ## Buckets arquivados" in content
    assert "\t- #tjpa" in content
    assert f"\t\t- {j1}:1" in content


def test_archived_page_existing_dedup(logseq_root, tmp_path):
    """A2 cenário 2: re-aplicar = no-op (bucket já presente em qualquer linha)."""
    j1 = logseq_root / "journals" / "2026_06_15.md"
    j1.write_text("- #tjpa\n")
    apply_archived_bucket("tjpa", "judiciario", [f"{j1}:1"])
    ok, msg = apply_archived_bucket("tjpa", "judiciario", [f"{j1}:1"])
    assert ok is False
    assert "já mencionado" in msg


def test_archived_multi_refs(logseq_root, tmp_path):
    """A2 cenário 3: multi-refs cross-journals."""
    j1 = logseq_root / "journals" / "2026_06_15.md"
    j2 = logseq_root / "journals" / "2026_06_17.md"
    j1.write_text("- #x\n")
    j2.write_text("- #x\n")
    ok, _ = apply_archived_bucket(
        "x", "categoria", [f"{j1}:1", f"{j2}:1"]
    )
    assert ok is True
    page = _paths.page_path("categoria")
    content = page.read_text()
    assert f"\t\t- {j1}:1" in content
    assert f"\t\t- {j2}:1" in content


def test_archived_fail_soft_invalid_ref(logseq_root, tmp_path):
    """A2: ref com path inexistente → skipped (warning); entry gravada com refs válidos."""
    j_valid = logseq_root / "journals" / "2026_06_15.md"
    j_valid.write_text("- #x\n")
    j_invalid = tmp_path / "ghost.md"  # never created
    ok, msg = apply_archived_bucket(
        "x", "categoria", [f"{j_valid}:1", f"{j_invalid}:1"]
    )
    assert ok is True
    page = _paths.page_path("categoria")
    content = page.read_text()
    assert f"\t\t- {j_valid}:1" in content
    assert f"\t\t- {j_invalid}:1" not in content
    assert "1 skipped" in msg


def test_archived_zero_valid_refs(logseq_root, tmp_path):
    """A2: zero refs válidos → entry gravada só com nome do bucket."""
    j_invalid = tmp_path / "ghost.md"
    ok, _ = apply_archived_bucket("x", "categoria", [f"{j_invalid}:1"])
    assert ok is True
    page = _paths.page_path("categoria")
    content = page.read_text()
    assert "\t- #x" in content
    # Sem child de ref
    assert "\t\t- " not in content


# ---------- apply_emerging_bucket (B2) ----------

def test_emerging_creates_bucket_today(logseq_root, monkeypatch):
    """B2 cenário 1: bucket criado no journal de hoje."""
    # Fixa hoje pra reprodutibilidade
    fixed = datetime.date(2026, 6, 20)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr("meta_bridge.journal_review.datetime", datetime)
    monkeypatch.setattr(datetime, "date", FakeDate)

    ok, msg = apply_emerging_bucket("ondas-knowledge-layer", None)
    assert ok is True
    journal = _paths.journal_path("2026_06_20")
    assert journal.exists()
    content = journal.read_text()
    assert "- #ondas-knowledge-layer" in content


def test_emerging_idempotent_existing(logseq_root, monkeypatch):
    """B2 cenário 2: bucket já existe → find-or-create no-op (sem duplicação)."""
    fixed = datetime.date(2026, 6, 20)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr("meta_bridge.journal_review.datetime", datetime)
    monkeypatch.setattr(datetime, "date", FakeDate)

    journal = _paths.journal_path("2026_06_20")
    journal.write_text("- #ondas-knowledge-layer\n\t- existing child\n")

    apply_emerging_bucket("ondas-knowledge-layer", None)
    content = journal.read_text()
    # Sem duplicação do bucket
    assert content.count("- #ondas-knowledge-layer") == 1


def test_emerging_origem_subbullet(logseq_root, monkeypatch):
    """B2: origem opcional vira sub-bullet `\\t- (origem: ...)`."""
    fixed = datetime.date(2026, 6, 20)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr("meta_bridge.journal_review.datetime", datetime)
    monkeypatch.setattr(datetime, "date", FakeDate)

    ok, _ = apply_emerging_bucket("x", "narratives 2026-06-15")
    assert ok is True
    journal = _paths.journal_path("2026_06_20")
    content = journal.read_text()
    assert "- #x" in content
    assert "\t- (origem: narratives 2026-06-15)" in content


def test_emerging_origem_dedup(logseq_root, monkeypatch):
    """B2: re-aplicar mesma origem → sub-bullet não duplica."""
    fixed = datetime.date(2026, 6, 20)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr("meta_bridge.journal_review.datetime", datetime)
    monkeypatch.setattr(datetime, "date", FakeDate)

    apply_emerging_bucket("x", "narratives 2026-06-15")
    apply_emerging_bucket("x", "narratives 2026-06-15")
    journal = _paths.journal_path("2026_06_20")
    content = journal.read_text()
    assert content.count("(origem: narratives 2026-06-15)") == 1


# ---------- E2E run_apply_mode (stdin → apply) ----------

def test_run_apply_mode_transitions_only_regression(logseq_root, monkeypatch, capsys):
    """Regression legacy v0.3.0: payload só `## Transitions` ainda aplica
    (parser pré-v0.4.0 preservado). F8 design-reviewer."""
    j = logseq_root / "journals" / "2026_06_15.md"
    j.write_text("- #tjpa\n\t- TODO foo\n")
    payload = f"- {j}:2 | \\t- TODO foo | \\t- DONE foo\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    run_apply_mode()
    out = capsys.readouterr().out
    assert "transitions: 1 aplicadas, 0 skipped" in out
    assert "\t- DONE foo" in j.read_text()


def test_run_apply_mode_payload_misto(logseq_root, monkeypatch, capsys):
    """Payload misto: transitions + structural na mesma invocação.
    Ordem fixa: transitions primeiro, structural depois."""
    fixed = datetime.date(2026, 6, 20)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr("meta_bridge.journal_review.datetime", datetime)
    monkeypatch.setattr(datetime, "date", FakeDate)

    j = logseq_root / "journals" / "2026_06_15.md"
    j.write_text("- #tjpa\n\t- TODO foo\n")
    payload = (
        f"- {j}:2 | \\t- TODO foo | \\t- DONE foo\n"
        "## Structural\n"
        "### Archived buckets\n"
        f"- old-bucket | judiciario | {j}:1\n"
        "### Emerging buckets\n"
        "- new-concept\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    run_apply_mode()
    out = capsys.readouterr().out
    assert "transitions: 1 aplicadas" in out
    assert "structural: 1 archived + 1 emerging" in out
    # Verificar todos aplicados
    assert "\t- DONE foo" in j.read_text()
    assert "- #old-bucket" in _paths.page_path("judiciario").read_text()
    assert "- #new-concept" in _paths.journal_path("2026_06_20").read_text()


def test_run_apply_mode_empty_payload(monkeypatch, capsys):
    """Empty payload → exit 1 com mensagem de formato."""
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    with pytest.raises(SystemExit) as exc:
        run_apply_mode()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "nenhuma transição" in err


# ---------- qa-reviewer gap coverage ----------

def test_parse_structural_section_boundary():
    """Gap 1: parser sai de ## Structural ao encontrar outra ## section.
    Entries após boundary são ignoradas."""
    raw = (
        "## Structural\n"
        "### Archived buckets\n"
        "- a | cat | /tmp/x:1\n"
        "## Outra Seção\n"
        "- d | e | f\n"
    )
    archived, _ = parse_structural(raw)
    assert len(archived) == 1
    assert archived[0]["bucket"] == "a"


def test_parse_structural_malformed_entry_silent_skip():
    """Gap 2: linhas malformadas dentro de subsection são silenciosamente
    puladas (fail-soft intencional). Parser não levanta."""
    raw = (
        "## Structural\n"
        "### Archived buckets\n"
        "- bucket-sem-pipes\n"
        "- valido | cat | /tmp/x:1\n"
    )
    archived, _ = parse_structural(raw)
    assert len(archived) == 1
    assert archived[0]["bucket"] == "valido"


def test_archived_dedup_mention_outside_section(logseq_root, tmp_path):
    """Gap 3: dedup escopo amplo — bucket mencionado em linha narrativa
    fora da section arquivados ainda dispara skip."""
    page = _paths.page_path("cat")
    page.write_text("- nota qualquer mencionando #tjpa em texto livre\n")
    j = logseq_root / "journals" / "2026_06_15.md"
    j.write_text("- #tjpa\n")
    ok, msg = apply_archived_bucket("tjpa", "cat", [f"{j}:1"])
    assert ok is False
    assert "já mencionado" in msg


def test_archived_multiple_buckets_same_page(logseq_root, tmp_path):
    """Gap 4: múltiplos buckets distintos na mesma categoria reusam section
    única e preservam ordem de inserção."""
    j = logseq_root / "journals" / "2026_06_15.md"
    j.write_text("- #a\n- #b\n")
    apply_archived_bucket("a", "cat", [f"{j}:1"])
    apply_archived_bucket("b", "cat", [f"{j}:2"])
    page = _paths.page_path("cat")
    content = page.read_text()
    # Section única
    assert content.count("- ## Buckets arquivados") == 1
    # Ambos children presentes
    assert "\t- #a" in content
    assert "\t- #b" in content
    # Ordem: a antes de b
    assert content.index("\t- #a") < content.index("\t- #b")


def test_emerging_origem_dedup_does_not_leak_across_buckets(logseq_root, monkeypatch):
    """Gap 5 (regression do bug fixed): dedup origem de bucket #x não pode
    falsamente match contra child de bucket subsequente #outro.
    Pré-fix: child (origem: X) de #outro vazava como falso-positivo de #x."""
    fixed = datetime.date(2026, 6, 20)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr("meta_bridge.journal_review.datetime", datetime)
    monkeypatch.setattr(datetime, "date", FakeDate)

    journal = _paths.journal_path("2026_06_20")
    # #x ANTES de #outro com origem matching
    journal.write_text("- #x\n- #outro\n\t- (origem: shared-mention)\n")
    apply_emerging_bucket("x", "shared-mention")
    content = journal.read_text()
    lines = content.splitlines()
    x_idx = next(i for i, l in enumerate(lines) if l == "- #x")
    # Child esperado sob #x: \t- (origem: shared-mention)
    children_of_x = []
    for j in range(x_idx + 1, len(lines)):
        if not lines[j].startswith("\t"):
            break
        children_of_x.append(lines[j])
    assert "\t- (origem: shared-mention)" in children_of_x


def test_run_apply_mode_transition_skipped_emits_stderr(logseq_root, monkeypatch, capsys):
    """Gap 6: transition cujo `before` não casa o conteúdo real → reportada
    como skipped em stdout E stderr."""
    j = logseq_root / "journals" / "2026_06_15.md"
    j.write_text("- #x\n\t- TODO real-content\n")
    # before não casa a linha
    payload = f"- {j}:2 | \\t- TODO content-errado | \\t- DONE content-errado\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    run_apply_mode()
    captured = capsys.readouterr()
    assert "0 aplicadas, 1 skipped" in captured.out
    assert "skipped" in captured.err
    assert str(j) in captured.err


def test_run_apply_mode_archived_idempotent_skipped(logseq_root, monkeypatch, capsys):
    """Gap 7: re-aplicar archived → conta como skipped no E2E + stderr."""
    j = logseq_root / "journals" / "2026_06_15.md"
    j.write_text("- #x\n")
    payload = (
        "## Structural\n"
        "### Archived buckets\n"
        f"- x | cat | {j}:1\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    run_apply_mode()
    capsys.readouterr()  # discard 1st run
    # 2nd run com mesmo payload
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    run_apply_mode()
    captured = capsys.readouterr()
    assert "structural: 0 archived + 0 emerging (1 skipped)" in captured.out
    assert "skipped archived #x" in captured.err
