"""Tests para skills/wiki-compile/sub-tools/compile.py — sub-tool determinístico.

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest):
- Cenário 1 (shapes a-d): find_insert_position cobrindo os 3 ramos de SECTION_ORDER.
- Cenário 1 (shape e): ensure_section idempotente quando seção já presente.
- Cenário 2-5: main() E2E in-process com monkeypatch de sys.argv cobrindo dedup,
  idempotência, edge case section sem trailing newline, edge case page sem
  properties block.
"""
import importlib.util
from pathlib import Path

import pytest

SUB_TOOL_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "wiki-compile"
    / "sub-tools"
    / "compile.py"
)
_spec = importlib.util.spec_from_file_location("wiki_compile_sub_tool", SUB_TOOL_PATH)
compile_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compile_mod)


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _invoke_compile(page_path: Path, section: str, content: str, monkeypatch) -> str:
    """Invoca compile.main() in-process via monkeypatch de sys.argv; retorna conteúdo final."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "compile.py",
            "--entity-page",
            str(page_path),
            "--section",
            section,
            "--content",
            content,
        ],
    )
    rc = compile_mod.main()
    assert rc == 0
    return page_path.read_text(encoding="utf-8")


# ---------- Cenário 1: section order canonical preservada ----------

def test_cenario_1_find_insert_position_shape_a_no_other_sections_with_properties():
    """(a) target sem anteriores nem posteriores → fallback após properties block (ramo 3)."""
    page = _lines("- type:: #project\n  status:: #active\n\n")
    pos = compile_mod.find_insert_position(page, "Sources digeridas")
    assert pos == 3


def test_cenario_1_find_insert_position_shape_b_only_later_sections():
    """(b) target só com posteriores → insere antes da primeira posterior (ramo 1)."""
    page = _lines(
        "- type:: #project\n\n"
        "## Síntese\n\n"
        "- conteúdo\n"
    )
    pos = compile_mod.find_insert_position(page, "Notas curadas")
    assert pos == 2


def test_cenario_1_find_insert_position_shape_c_only_earlier_sections_regression():
    """(c) target só com anteriores → insere após última anterior (ramo 2 — regression do bug histórico).

    Bug histórico: find_insert_position percorria só seções posteriores; quando ausentes,
    caía no fallback ignorando anteriores existentes. Descoberto em /run-plan
    onda-2-knowledge-layer-piloto (meta-system, 2026-06-18) — 6ª chamada inseriu
    Sources digeridas ANTES de Notas curadas violando ordem canonical.
    """
    page = _lines(
        "- type:: #project\n\n"
        "## Notas curadas\n\n"
        "- nota um\n"
    )
    pos = compile_mod.find_insert_position(page, "Sources digeridas")
    assert pos == 5


def test_cenario_1_find_insert_position_shape_d_both_sides_precedence():
    """(d) target com anteriores E posteriores → posterior tem precedência (ramo 1 wins sobre ramo 2)."""
    page = _lines(
        "- type:: #project\n\n"
        "## Notas curadas\n\n"
        "- nota\n\n"
        "## Síntese\n\n"
        "- sintese\n"
    )
    pos = compile_mod.find_insert_position(page, "Sources digeridas")
    assert pos == 6


def test_cenario_1_ensure_section_shape_e_idempotent():
    """(e) target já presente → ensure_section retorna bounds existentes sem modificar lines."""
    page_text = (
        "- type:: #project\n\n"
        "## Notas curadas\n\n"
        "- nota existente\n"
    )
    page = _lines(page_text)
    new_lines, bounds = compile_mod.ensure_section(page, "Notas curadas")
    assert new_lines == page, "ensure_section modificou lines em shape (e) — esperado no-op"
    assert bounds == (2, 4), f"bounds inesperado em shape (e): {bounds}"


def test_cenario_1_main_e2e_preserves_canonical_order(tmp_path, monkeypatch):
    """E2E: criar seção anterior em página com seção posterior existente preserva ordem canonical no arquivo final.

    Defende invariante de domínio (SECTION_ORDER) no layer E2E — shapes (a)-(d) testam
    find_insert_position pura; aqui a interação positioning + append_to_section + write
    é exercitada via main(). Captura regressões onde a função posicional retorna OK mas
    o output composto viola a ordem.
    """
    page = tmp_path / "entity.md"
    page.write_text(
        "- type:: #project\n\n"
        "## Síntese\n\n"
        "- síntese existente\n",
        encoding="utf-8",
    )
    out = _invoke_compile(page, "Notas curadas", "- nota nova", monkeypatch)
    idx_notas = out.index("## Notas curadas")
    idx_sintese = out.index("## Síntese")
    assert idx_notas < idx_sintese, "ordem canonical violada — Notas curadas após Síntese no output"
    assert "- nota nova" in out
    assert "- síntese existente" in out


# ---------- Cenário 2: dedup multi-line ----------

def test_cenario_2_dedup_multi_line_content(tmp_path, monkeypatch):
    """Re-invocação com bloco multi-linha já presente → no-op byte-equivalent."""
    page = tmp_path / "entity.md"
    initial = (
        "- type:: #project\n\n"
        "## Notas curadas\n\n"
        "- linha 1\n"
        "- linha 2 com continuação\n"
        "  - sub-bullet\n"
    )
    page.write_text(initial, encoding="utf-8")
    content = "- linha 1\n- linha 2 com continuação\n  - sub-bullet"
    out = _invoke_compile(page, "Notas curadas", content, monkeypatch)
    assert out == initial, "dedup deveria ser no-op byte-equivalent"


# ---------- Cenário 3: idempotência de re-runs ----------

def test_cenario_3_idempotence_re_runs(tmp_path, monkeypatch):
    """N invocações com mesmo input produzem output byte-equivalente."""
    page = tmp_path / "entity.md"
    page.write_text("- type:: #project\n\n", encoding="utf-8")
    content = "- bloco original\n  - detalhe"

    out1 = _invoke_compile(page, "Notas curadas", content, monkeypatch)
    out2 = _invoke_compile(page, "Notas curadas", content, monkeypatch)
    out3 = _invoke_compile(page, "Notas curadas", content, monkeypatch)
    assert out1 == out2 == out3, "re-runs não-idempotentes — output divergiu"
    # Gap 2 reviewer: fixa contrato de prefix da 1ª invocação (não só estabilidade pós-1ª).
    assert "## Notas curadas\n\n- bloco original\n  - detalhe\n" in out1, "shape de append inesperado em out1"


# ---------- Cenário 4: edge case section sem trailing newline ----------

def test_cenario_4_edge_section_without_trailing_newline(tmp_path, monkeypatch):
    """Página com seção alvo sem newline final → append preserva conteúdo existente."""
    page = tmp_path / "entity.md"
    page.write_text(
        "- type:: #project\n\n"
        "## Notas curadas\n\n"
        "- nota antiga",  # SEM \n final
        encoding="utf-8",
    )
    out = _invoke_compile(page, "Notas curadas", "- nota nova", monkeypatch)
    assert "- nota antiga" in out, "nota antiga foi corrompida"
    assert "- nota nova" in out, "nota nova não foi appendada"


# ---------- Cenário 5: edge case page sem properties block ----------

def test_cenario_5_edge_page_without_properties_block(tmp_path, monkeypatch):
    """Página sem properties block (criada manualmente fora do schema) → cria seção sem corromper."""
    page = tmp_path / "entity.md"
    page.write_text("conteúdo livre sem properties\n\n", encoding="utf-8")
    out = _invoke_compile(page, "Notas curadas", "- primeira nota", monkeypatch)
    assert "## Notas curadas" in out, "seção não foi criada"
    assert "- primeira nota" in out, "conteúdo não foi appendado"
    assert "conteúdo livre sem properties" in out, "conteúdo pré-existente foi corrompido"


# ---------- validate() error paths (fail-fast em input inválido) ----------

def test_validate_rejects_invalid_section(tmp_path, monkeypatch):
    """validate() recusa section fora de SECTION_ORDER com exit code 1."""
    page = tmp_path / "entity.md"
    page.write_text("- type:: #project\n\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "compile.py",
            "--entity-page", str(page),
            "--section", "Fora do schema",
            "--content", "- nota",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        compile_mod.main()
    assert exc_info.value.code == 1


def test_validate_rejects_missing_page(tmp_path, monkeypatch):
    """validate() recusa --entity-page apontando pra arquivo inexistente com exit code 1."""
    page = tmp_path / "nonexistent.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "compile.py",
            "--entity-page", str(page),
            "--section", "Notas curadas",
            "--content", "- nota",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        compile_mod.main()
    assert exc_info.value.code == 1


def test_validate_rejects_empty_content(tmp_path, monkeypatch):
    """validate() recusa content whitespace-only com exit code 1."""
    page = tmp_path / "entity.md"
    page.write_text("- type:: #project\n\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "compile.py",
            "--entity-page", str(page),
            "--section", "Notas curadas",
            "--content", "   ",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        compile_mod.main()
    assert exc_info.value.code == 1
