"""pytest cobrindo enrich.py sub-tool (skills/enrich-blocks/sub-tools).

Critério parsing-complexo per ADR-002 § Decisão 6 Adendo (2026-06-16) — sub-tool
faz parser de markdown indented + property region scan + append idempotente;
pytest formal cobre os cenários enumerados em ## Verificação manual do plano
onda-5-hook-enrich-blocks + invariantes operacionais.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SUB_TOOL = PLUGIN_ROOT / "skills" / "enrich-blocks" / "sub-tools" / "enrich.py"


@pytest.fixture
def enrich_mod():
    """Carrega enrich.py como módulo isolado (path standalone, sem package)."""
    spec = importlib.util.spec_from_file_location("enrich", SUB_TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["enrich"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pages_dir(tmp_path):
    """Cria 2 Project Pages canonical para matching (com repo-path:: per fix de scoping)."""
    d = tmp_path / "pages"
    d.mkdir()
    (d / "meta-bridge.md").write_text("repo-path:: /storage/dev/projects/meta-bridge\n")
    (d / "meta-system.md").write_text("repo-path:: /storage/dev/projects/meta-system\n")
    return d


def write_journal(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# Cenário (i) — sub-bullet sem provenance:: recebe append correto
def test_subbullet_without_provenance_gets_append(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #meta-bridge\n"
        "\tclosed:: 2026-06-20T18:00:00+00:00\n"
        "\t- DONE algo mencionando meta-system\n",
    )
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, skipped = enrich_mod.process_journal(journal, pages)
    assert enriched == 1
    assert skipped == 0
    # Asserção como linha inteira força canonical property line shape
    # (`\t\t<prop>:: <value>` per logseq-notes ADR-003 SD2) — regressão pra
    # `\tprovenance::` (1 tab) ou substring espalhada não passaria.
    lines = journal.read_text().splitlines()
    assert "\t\tprovenance:: #enriched" in lines
    assert "\t\tentities:: [[meta-system]]" in lines


# Cenário (ii) — sub-bullet com provenance:: já set skip (idempotência)
def test_subbullet_with_provenance_skipped(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #meta-bridge\n"
        "\tclosed:: 2026-06-20T18:00:00+00:00\n"
        "\t- DONE algo\n"
        "\t\tprovenance:: #enriched\n"
        "\t\tentities:: [[meta-system]]\n",
    )
    before = journal.read_text()
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, skipped = enrich_mod.process_journal(journal, pages)
    assert enriched == 0
    assert skipped == 1
    # Idempotente: journal inalterado (não re-write)
    assert journal.read_text() == before


# Cenário (iii) — bucket vazio skip silente
def test_empty_bucket_skips(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(journal, "- #empty-bucket\n")
    before = journal.read_text()
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, skipped = enrich_mod.process_journal(journal, pages)
    assert enriched == 0
    assert skipped == 0
    assert journal.read_text() == before


# Cenário (iv) — journal ausente recusa clean
def test_journal_missing_returns_zero(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "absent.md"  # não criado
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, skipped = enrich_mod.process_journal(journal, pages)
    assert enriched == 0
    assert skipped == 0
    assert not journal.exists()


# Cenário (v) — matching de entity contra pages/ existentes
def test_matching_against_existing_pages_only(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #meta-bridge\n"
        "\t- Sub-bullet mencionando entidade-nao-existente + meta-bridge\n",
    )
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, _ = enrich_mod.process_journal(journal, pages)
    assert enriched == 1
    out = journal.read_text()
    assert "[[meta-bridge]]" in out
    assert "[[entidade-nao-existente]]" not in out


# Cenário (vi) — regression: dedup não contamina cross-bucket
def test_no_cross_bucket_contamination(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #bucket-a\n"
        "\t- DONE algo mencionando meta-system\n"
        "\t\tprovenance:: #enriched\n"
        "\t\tentities:: [[meta-system]]\n"
        "- #bucket-b\n"
        "\t- DONE outro mencionando meta-bridge\n",
    )
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, skipped = enrich_mod.process_journal(journal, pages)
    # bucket-a: 1 skipped (já enriched); bucket-b: 1 enriched
    assert enriched == 1
    assert skipped == 1
    out = journal.read_text()
    lines = out.splitlines()
    bucket_b_idx = lines.index("- #bucket-b")
    # bucket-b deve ter sua própria provenance (não vazada de bucket-a)
    assert any("provenance::" in l for l in lines[bucket_b_idx:])
    assert any("[[meta-bridge]]" in l for l in lines[bucket_b_idx:])


# Cenário (v-bis) — mention via page-link `[[<page>]]` casa sem duplicar brackets
def test_pagelink_mention_does_not_duplicate_brackets(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #meta-bridge\n"
        "\t- DONE algo referenciando [[meta-system]] inline\n",
    )
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, _ = enrich_mod.process_journal(journal, pages)
    assert enriched == 1
    out = journal.read_text()
    assert "\t\tentities:: [[meta-system]]" in out.splitlines()
    # No double-bracket leakage (e.g. `[[[[meta-system]]]]`)
    assert "[[[[" not in out
    assert "]]]]" not in out


# Cenário (v-ter) — dedup de mention dentro do mesmo sub-bullet
def test_dedup_repeated_mention_same_subbullet(enrich_mod, tmp_path, pages_dir):
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #meta-bridge\n"
        "\t- DONE meta-system, depois mais meta-system, e meta-system de novo\n",
    )
    pages = enrich_mod.list_project_pages(pages_dir)
    enriched, _ = enrich_mod.process_journal(journal, pages)
    assert enriched == 1
    lines = journal.read_text().splitlines()
    entities_lines = [l for l in lines if l.startswith("\t\tentities::")]
    assert len(entities_lines) == 1
    assert entities_lines[0] == "\t\tentities:: [[meta-system]]"


# Cenário (vii) — re-invocação atomic: re-entrada cobre blocks pendentes
# (atomic write all-or-nothing; falha de I/O = re-invocação seguinte completa)
def test_partial_state_preserves_enriched_blocks(enrich_mod, tmp_path, pages_dir):
    """Simulação: invocação 1 enriquece bloco A; invocação 2 (após edit do
    operador adicionando bloco B) só processa B, mantendo A intacto."""
    journal = tmp_path / "journal.md"
    write_journal(
        journal,
        "- #meta-bridge\n"
        "\t- DONE primeiro mencionando meta-system\n",
    )
    pages = enrich_mod.list_project_pages(pages_dir)

    enriched1, _ = enrich_mod.process_journal(journal, pages)
    assert enriched1 == 1
    state_after_first = journal.read_text()
    assert "[[meta-system]]" in state_after_first

    # Operador adiciona novo sub-bullet manualmente (simulação)
    journal.write_text(
        state_after_first.rstrip("\n")
        + "\n\t- DONE segundo mencionando meta-bridge\n"
    )

    enriched2, skipped2 = enrich_mod.process_journal(journal, pages)
    assert enriched2 == 1  # novo bloco enriched
    assert skipped2 == 1   # bloco pré-existente skip silente

    final = journal.read_text()
    # Bloco A (primeiro) ainda tem suas properties intactas
    assert "[[meta-system]]" in final
    # Bloco B (segundo) tem properties novas
    assert "[[meta-bridge]]" in final


# --- Cenários de list_project_pages (scoping fix #25) ---

# Cenário (viii) — project page (repo-path:: presente) incluída; non-project excluída
def test_list_project_pages_filters_by_repo_path_prop(enrich_mod, tmp_path):
    d = tmp_path / "pages"
    d.mkdir()
    (d / "meta-bridge.md").write_text("repo-path:: /storage/dev/projects/meta-bridge\n")
    (d / "concept-page.md").write_text("# Just a concept, no repo-path\n")
    result = enrich_mod.list_project_pages(d)
    assert result == ["meta-bridge"]


# Cenário (ix) — -digested.md e template.md (sem repo-path::) excluídos
def test_list_project_pages_excludes_digested_and_template(enrich_mod, tmp_path):
    d = tmp_path / "pages"
    d.mkdir()
    (d / "meta-bridge.md").write_text("repo-path:: /storage/dev/projects/meta-bridge\n")
    (d / "meta-bridge-digested.md").write_text("provenance:: #digested\n")
    (d / "Project Template.md").write_text("type:: template\n")
    result = enrich_mod.list_project_pages(d)
    assert result == ["meta-bridge"]


# Cenário (x) — arquivo inacessível (OSError) excluído silenciosamente
def test_list_project_pages_skips_unreadable_file(enrich_mod, tmp_path):
    d = tmp_path / "pages"
    d.mkdir()
    (d / "meta-bridge.md").write_text("repo-path:: /storage/dev/projects/meta-bridge\n")
    (d / "unreadable.md").write_text("repo-path:: /some/path\n")
    original_read_text = Path.read_text

    def patched_read_text(self, *args, **kwargs):
        if self.name == "unreadable.md":
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", patched_read_text):
        result = enrich_mod.list_project_pages(d)
    assert result == ["meta-bridge"]


# Cenário (xi) — arquivo com bytes inválidos (UnicodeDecodeError) excluído silenciosamente
def test_list_project_pages_skips_binary_file(enrich_mod, tmp_path):
    d = tmp_path / "pages"
    d.mkdir()
    (d / "meta-bridge.md").write_text("repo-path:: /storage/dev/projects/meta-bridge\n")
    (d / "binary.md").write_bytes(b"\xff\xfe invalid utf-8 bytes")
    result = enrich_mod.list_project_pages(d)
    assert result == ["meta-bridge"]


# Cenário (xii) — pages_dir ausente retorna lista vazia sem exceção
def test_list_project_pages_missing_dir_returns_empty(enrich_mod, tmp_path):
    result = enrich_mod.list_project_pages(tmp_path / "nonexistent")
    assert result == []
