"""pytest — substrato mecânico das heurísticas v2 de bucket (SD10 Adendo 2026-06-24).

Per ADR-002 § Decisão 3, o judgment semântico (counting de pares de co-occurrence,
Levenshtein de naming-drift, plausibilidade de rename) vive na SKILL.md — não no CLI.
O que o CLI faz e este suite cobre é o **substrato mecânico**:

1. `emit_scan_output` emite os DADOS que o trio consome — `### Co-occurrence membership`
   (membership per-journal, só journals com ≥2 buckets) + first/last-seen no inventory —
   sem quebrar as 4 seções existentes (backward-compat das heurísticas 1-4).
2. `parse_hygiene` + `apply_hygiene` — parse + write aditivo forward-only em
   `pages/bucket-hygiene.md`, idempotente, sem tocar journals históricos.
3. O dado de first/last distingue gap temporal (sinal de rename-implicit) de
   sobreposição (sinal de naming-drift) — substrato da discriminação 2f-vs-2g.
"""

import io
import contextlib
import datetime

from meta_bridge import journal_review as jr


def _emit(agg, window=None):
    window = window or [datetime.date(2026, 6, 10), datetime.date(2026, 6, 12)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        jr.emit_scan_output(window, len(window), agg)
    return buf.getvalue()


def _agg(**kw):
    base = {
        "markers_open": [],
        "dones": [],
        "narratives": [],
        "buckets_all": [],
        "buckets_per_journal": [],
    }
    base.update(kw)
    return base


# --- Scan: Co-occurrence membership ---------------------------------------

def test_cooccurrence_membership_emits_only_multi_bucket_journals():
    agg = _agg(
        buckets_all=["a", "b", "c"],
        buckets_per_journal=[
            ("2026-06-10", ["a", "b"]),  # ≥2 → emitido
            ("2026-06-12", ["c"]),       # 1 bucket → omitido (sem co-occurrence)
        ],
    )
    out = _emit(agg)
    assert "### Co-occurrence membership" in out
    assert "- 2026-06-10 | #a #b" in out
    # journal single-bucket NÃO aparece na seção de co-occurrence
    assert "- 2026-06-12 | #c" not in out


def test_cooccurrence_membership_none_when_no_multi_bucket_journal():
    agg = _agg(
        buckets_all=["a"],
        buckets_per_journal=[("2026-06-10", ["a"])],
    )
    out = _emit(agg)
    # seção presente mas vazia
    assert "### Co-occurrence membership" in out
    section = out.split("### Co-occurrence membership", 1)[1]
    assert "_(none)_" in section


# --- Scan: first/last-seen -------------------------------------------------

def test_first_last_seen_spans_for_multi_journal_bucket():
    agg = _agg(
        buckets_all=["a"],
        buckets_per_journal=[
            ("2026-06-10", ["a"]),
            ("2026-06-12", ["a"]),
        ],
    )
    out = _emit(agg)
    assert "first: 2026-06-10 last: 2026-06-12" in out


def test_first_last_seen_equal_for_single_journal_bucket():
    agg = _agg(
        buckets_all=["a"],
        buckets_per_journal=[("2026-06-10", ["a"])],
    )
    out = _emit(agg)
    assert "first: 2026-06-10 last: 2026-06-10" in out


def test_journals_count_is_content_based_distinct_from_header_first_last():
    """journals: count é content-based (markers/dones/narratives); first/last é
    header-based. Um bucket header-only sem conteúdo: journals: 0 mas first/last set."""
    agg = _agg(
        markers_open=[
            {"path": "j", "line": 2, "date": "2026-06-10", "bucket": "a",
             "marker": "TODO", "content": "x", "sub_bullets": []},
        ],
        buckets_all=["a", "b"],
        buckets_per_journal=[
            ("2026-06-10", ["a", "b"]),
            ("2026-06-12", ["a", "b"]),
        ],
    )
    out = _emit(agg)
    # 'a' tem conteúdo só no 1º journal → journals: 1; header nos 2 → first≠last
    assert "- #a | journals: 1 | open_tasks: 1 | done_tasks: 0 | first: 2026-06-10 last: 2026-06-12" in out
    # 'b' header-only sem conteúdo → journals: 0 mas first/last set
    assert "- #b | journals: 0 | open_tasks: 0 | done_tasks: 0 | first: 2026-06-10 last: 2026-06-12" in out


# --- Scan: backward-compat das 4 seções existentes (Finding 4a) ------------

def test_backward_compat_four_existing_sections_intact():
    agg = _agg(
        markers_open=[
            {"path": "j", "line": 2, "date": "2026-06-10", "bucket": "a",
             "marker": "TODO", "content": "x", "sub_bullets": []},
        ],
        dones=[
            {"path": "j", "line": 5, "date": "2026-06-12", "bucket": "a",
             "marker": "DONE", "content": "y", "sub_bullets": []},
        ],
        narratives=[
            {"path": "j", "line": 8, "date": "2026-06-12", "bucket": "a",
             "content": "alguma narrativa"},
        ],
        buckets_all=["a"],
        buckets_per_journal=[("2026-06-10", ["a"]), ("2026-06-12", ["a"])],
    )
    out = _emit(agg)
    # As 4 seções existentes seguem presentes com o shape que heurísticas 1-4 consomem
    for header in ("### Active markers", "### DONE tasks", "### Narratives", "### Bucket inventory"):
        assert header in out, header
    assert "- j:2 | 2026-06-10 | #a | TODO x" in out
    assert "- j:5 | 2026-06-12 | #a | DONE y" in out
    assert "- j:8 | 2026-06-12 | #a | alguma narrativa" in out
    # inventory preserva os 3 campos canonical (count content-based) — aditivo só no fim
    assert "- #a | journals: 2 | open_tasks: 1 | done_tasks: 1 | first:" in out


# --- Apply: parse_hygiene --------------------------------------------------

_HYGIENE_PAYLOAD = """## Hygiene

### Co-occurrence
- [[a]] ∪ [[b]] coocorrem em 3 journals — considerar fusão

### Rename-implicit
- [[weekly-review]] → [[journal-review]] (órfãs: [[2026-06-08]]) — verificar rename

### Naming-drift
- [[tjpa-tools]] ~ [[tjpa-tool]] (Levenshtein 1) — canonical sugerido: tjpa-tools
"""


def test_parse_hygiene_three_types():
    entries = jr.parse_hygiene(_HYGIENE_PAYLOAD)
    assert [t for t, _ in entries] == ["Co-occurrence", "Rename-implicit", "Naming-drift"]
    assert entries[0][1].startswith("[[a]] ∪ [[b]]")


def test_parse_hygiene_empty_when_no_section():
    assert jr.parse_hygiene("## Transitions\n- a:1 | x | y\n") == []


def test_parse_hygiene_exits_on_next_section():
    payload = _HYGIENE_PAYLOAD + "\n## Structural\n### Archived buckets\n- z | cat | j:1\n"
    entries = jr.parse_hygiene(payload)
    # Só as 3 do bloco Hygiene; o bullet de Structural não vaza
    assert len(entries) == 3
    assert all("z | cat" not in s for _, s in entries)


def test_hygiene_suggestions_dont_collide_with_transition_re():
    """Contrato forward load-bearing: sugestões com page-refs [[...]] NUNCA casam
    TRANSITION_RE (senão viravam write destrutivo em journal)."""
    for line in _HYGIENE_PAYLOAD.splitlines():
        if line.startswith("- "):
            assert jr.TRANSITION_RE.match(line) is None, line


# --- Apply: apply_hygiene (idempotência + forward-only) --------------------

def _patch_page(monkeypatch, tmp_path):
    monkeypatch.setattr(jr._paths, "page_path", lambda name: tmp_path / f"{name}.md")


def test_apply_hygiene_creates_page_with_per_type_sections(tmp_path, monkeypatch):
    _patch_page(monkeypatch, tmp_path)
    entries = jr.parse_hygiene(_HYGIENE_PAYLOAD)
    applied, skipped, _ = jr.apply_hygiene(entries)
    assert (applied, skipped) == (3, 0)
    page = (tmp_path / "bucket-hygiene.md").read_text()
    for heading in ("- ## Co-occurrence", "- ## Rename-implicit", "- ## Naming-drift"):
        assert heading in page, heading
    assert "\t- [[a]] ∪ [[b]] coocorrem em 3 journals — considerar fusão" in page


def test_apply_hygiene_idempotent(tmp_path, monkeypatch):
    _patch_page(monkeypatch, tmp_path)
    entries = jr.parse_hygiene(_HYGIENE_PAYLOAD)
    jr.apply_hygiene(entries)
    page_after_first = (tmp_path / "bucket-hygiene.md").read_text()
    applied2, skipped2, _ = jr.apply_hygiene(entries)
    assert (applied2, skipped2) == (0, 3)
    assert (tmp_path / "bucket-hygiene.md").read_text() == page_after_first


def test_apply_hygiene_forward_only_journals_untouched(tmp_path, monkeypatch):
    _patch_page(monkeypatch, tmp_path)
    # Um "journal histórico" no mesmo dir — apply NÃO deve tocá-lo.
    journal = tmp_path / "2026_06_08.md"
    journal.write_text("- #weekly-review\n\t- TODO órfã\n")
    journal_before = journal.read_text()
    jr.apply_hygiene(jr.parse_hygiene(_HYGIENE_PAYLOAD))
    assert journal.read_text() == journal_before  # órfã permanece TODO; journal intacto


def test_apply_hygiene_empty_entries_noop(tmp_path, monkeypatch):
    _patch_page(monkeypatch, tmp_path)
    assert jr.apply_hygiene([]) == (0, 0, [])
    assert not (tmp_path / "bucket-hygiene.md").exists()


# --- Discriminação 2f-vs-2g: substrato de dado (Finding 4b) ----------------

def test_first_last_data_distinguishes_gap_from_overlap():
    """O mesmo par de nomes similares: com gap temporal (A sumiu antes de A' surgir)
    o dado first/last mostra A.last < A'.first (sinal de rename-implicit); com
    sobreposição mostra ranges que se cruzam (sinal de naming-drift). O CLI emite o
    dado; a discriminação é skill-side, mas o dado tem de torná-la possível."""
    window = [datetime.date(2026, 6, d) for d in (10, 12, 14, 16)]
    # Caso GAP (rename): weekly-review só nos 2 primeiros; journal-review só nos 2 últimos
    agg_gap = _agg(
        buckets_all=["weekly-review", "journal-review"],
        buckets_per_journal=[
            ("2026-06-10", ["weekly-review"]),
            ("2026-06-12", ["weekly-review"]),
            ("2026-06-14", ["journal-review"]),
            ("2026-06-16", ["journal-review"]),
        ],
    )
    out_gap = _emit(agg_gap, window)
    assert "- #weekly-review | journals: 0 | open_tasks: 0 | done_tasks: 0 | first: 2026-06-10 last: 2026-06-12" in out_gap
    assert "- #journal-review | journals: 0 | open_tasks: 0 | done_tasks: 0 | first: 2026-06-14 last: 2026-06-16" in out_gap
    # gap visível: weekly last (06-12) < journal first (06-14)

    # Caso OVERLAP (drift): tjpa-tools e tjpa-tool coexistem nos mesmos journals
    agg_overlap = _agg(
        buckets_all=["tjpa-tools", "tjpa-tool"],
        buckets_per_journal=[
            ("2026-06-10", ["tjpa-tools", "tjpa-tool"]),
            ("2026-06-12", ["tjpa-tools", "tjpa-tool"]),
        ],
    )
    out_overlap = _emit(agg_overlap, window)
    assert "- #tjpa-tools | journals: 0 | open_tasks: 0 | done_tasks: 0 | first: 2026-06-10 last: 2026-06-12" in out_overlap
    assert "- #tjpa-tool | journals: 0 | open_tasks: 0 | done_tasks: 0 | first: 2026-06-10 last: 2026-06-12" in out_overlap
    # overlap visível: ranges idênticos (coexistem) → drift, não rename


# --- Gaps absorvidos do qa-reviewer ----------------------------------------

def test_first_last_spans_non_contiguous_reappearance():
    """last reflete a ÚLTIMA aparição mesmo com gap intermediário (A→gap→A).
    Caso que quebraria sob uma lógica 'first/last da primeira janela contígua'."""
    window = [datetime.date(2026, 6, d) for d in (10, 12, 14)]
    agg = _agg(
        buckets_all=["a", "b"],
        buckets_per_journal=[
            ("2026-06-10", ["a"]),
            ("2026-06-12", ["b"]),  # gap p/ 'a'
            ("2026-06-14", ["a"]),
        ],
    )
    out = _emit(agg, window)
    assert "- #a | journals: 0 | open_tasks: 0 | done_tasks: 0 | first: 2026-06-10 last: 2026-06-14" in out


def test_apply_hygiene_dedup_is_global_cross_type(tmp_path, monkeypatch):
    """Dedup é global (qualquer seção), não por-tipo — invariante declarada na
    docstring. Mesmo texto sob tipo diferente skipa e não cria a 2ª seção."""
    _patch_page(monkeypatch, tmp_path)
    jr.apply_hygiene([("Co-occurrence", "dup")])
    applied, skipped, _ = jr.apply_hygiene([("Naming-drift", "dup")])
    assert (applied, skipped) == (0, 1)
    page = (tmp_path / "bucket-hygiene.md").read_text()
    assert "- ## Naming-drift" not in page  # 2ª seção nunca criada


def test_parse_hygiene_ignores_bullet_before_subheader():
    """Bullet dentro de ## Hygiene antes de qualquer ### <tipo> é descartado
    (guard current_type) — não vira entry sem tipo."""
    payload = "## Hygiene\n- preâmbulo solto\n### Co-occurrence\n- real\n"
    assert jr.parse_hygiene(payload) == [("Co-occurrence", "real")]


def test_apply_hygiene_multiple_same_type_accumulate(tmp_path, monkeypatch):
    """Duas sugestões do mesmo tipo acumulam sob uma única seção, em ordem —
    o caminho 'append a seção já-povoada' (uso real: N co-occurrences por review)."""
    _patch_page(monkeypatch, tmp_path)
    applied, skipped, _ = jr.apply_hygiene(
        [("Co-occurrence", "primeira"), ("Co-occurrence", "segunda")]
    )
    assert (applied, skipped) == (2, 0)
    page = (tmp_path / "bucket-hygiene.md").read_text()
    assert page.count("- ## Co-occurrence") == 1  # única seção
    assert "\t- primeira" in page and "\t- segunda" in page
    assert page.index("primeira") < page.index("segunda")  # ordem preservada
