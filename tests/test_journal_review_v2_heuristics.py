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


def _emit_candidates(candidates):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        jr.emit_candidates(candidates)
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


# --- compute_candidates: geração determinística (núcleo mecânico) ----------

def _cand(agg, cooccur_min=2, namedrift_max=2, rename_gap=2):
    return jr.compute_candidates(agg, cooccur_min, namedrift_max, rename_gap)


def _orphan(bucket, date, line=2):
    return {"path": "j", "line": line, "date": date, "bucket": bucket,
            "marker": "TODO", "content": "x", "sub_bullets": []}


# co-occurrence (counting)

def test_cooccurrence_pair_count_meets_threshold():
    agg = _agg(buckets_all=["a", "b", "c"], buckets_per_journal=[
        ("2026-06-10", ["a", "b"]),
        ("2026-06-12", ["a", "b"]),
        ("2026-06-14", ["a", "c"]),
    ])
    c = _cand(agg, cooccur_min=2)
    assert ("a", "b", 2) in c["cooccurrence"]
    # a+c compartilham só 1 journal < 2 → não candidato
    assert not any({a, b} == {"a", "c"} for a, b, _ in c["cooccurrence"])


def test_cooccurrence_threshold_override():
    agg = _agg(buckets_all=["a", "b"], buckets_per_journal=[("2026-06-10", ["a", "b"])])
    assert _cand(agg, cooccur_min=2)["cooccurrence"] == []  # share 1 < 2
    assert ("a", "b", 1) in _cand(agg, cooccur_min=1)["cooccurrence"]


# naming-drift (Levenshtein)

def test_levenshtein_basic():
    assert jr._levenshtein("tjpa-tools", "tjpa-tool") == 1  # deleção
    assert jr._levenshtein("abc", "abc") == 0
    assert jr._levenshtein("", "abc") == 3                  # inserção
    assert jr._levenshtein("abc", "abx") == 1              # substituição pura
    assert jr._levenshtein("ab", "ba") == 2               # transposição = 2 (Levenshtein, não Damerau)
    assert jr._levenshtein("Abc", "abc") == 1             # case-sensitive (não normaliza)


def test_naming_drift_within_distance_and_coexisting():
    agg = _agg(buckets_all=["tjpa-tools", "tjpa-tool"],
               buckets_per_journal=[("2026-06-10", ["tjpa-tools", "tjpa-tool"])])
    assert ("tjpa-tool", "tjpa-tools", 1) in _cand(agg, namedrift_max=2)["naming_drift"]


def test_naming_drift_excludes_over_distance_semantic_rename():
    # weekly-review vs journal-review: Levenshtein grande (semântico, NÃO léxico) →
    # não é naming-drift (é caso de rename-implicit via judgment semântico na skill)
    agg = _agg(buckets_all=["weekly-review", "journal-review"],
               buckets_per_journal=[("2026-06-10", ["weekly-review", "journal-review"])])
    assert _cand(agg, namedrift_max=2)["naming_drift"] == []


def test_naming_drift_excludes_identical_and_respects_threshold():
    agg = _agg(buckets_all=["abc", "abx"], buckets_per_journal=[("2026-06-10", ["abc", "abx"])])
    assert ("abc", "abx", 1) in _cand(agg, namedrift_max=2)["naming_drift"]
    assert _cand(agg, namedrift_max=0)["naming_drift"] == []  # dist 1 > 0


# rename-implicit (gap + órfãs)

def test_rename_implicit_gap_and_orphans_required():
    agg = _agg(
        markers_open=[_orphan("weekly-review", "2026-06-08")],
        buckets_all=["weekly-review", "journal-review"],
        buckets_per_journal=[
            ("2026-06-08", ["weekly-review"]),   # idx0
            ("2026-06-10", []),                  # idx1
            ("2026-06-12", ["journal-review"]),  # idx2, gap=2 de idx0
        ],
    )
    ri = _cand(agg, rename_gap=2)["rename_implicit"]
    assert len(ri) == 1
    a, last, orphans, successors = ri[0]
    assert a == "weekly-review" and "journal-review" in successors
    assert orphans == ["j:2"] and last == "2026-06-08"


def test_rename_implicit_skips_bucket_without_orphans():
    # weekly-review some mas SEM markers abertos → não é candidato a rename
    agg = _agg(
        buckets_all=["weekly-review", "journal-review"],
        buckets_per_journal=[
            ("2026-06-08", ["weekly-review"]),
            ("2026-06-12", ["journal-review"]),
        ],
    )
    assert _cand(agg, rename_gap=2)["rename_implicit"] == []


def test_rename_implicit_respects_gap_threshold():
    agg = _agg(
        markers_open=[_orphan("weekly-review", "2026-06-08")],
        buckets_all=["weekly-review", "journal-review"],
        buckets_per_journal=[
            ("2026-06-08", ["weekly-review"]),   # idx0
            ("2026-06-10", ["journal-review"]),  # idx1, gap=1
        ],
    )
    assert _cand(agg, rename_gap=2)["rename_implicit"] == []  # gap 1 < 2
    ri = _cand(agg, rename_gap=1)["rename_implicit"]
    assert len(ri) == 1 and "journal-review" in ri[0][3]


def test_compute_candidates_emit_sections_present():
    agg = _agg(buckets_all=["a", "b"], buckets_per_journal=[("2026-06-10", ["a", "b"])])
    out = _emit_candidates(_cand(agg, cooccur_min=1))
    assert "### Co-occurrence candidates" in out
    assert "### Naming-drift candidates" in out
    assert "### Rename-implicit candidates" in out
    assert "- #a #b | shared-journals: 1" in out


def test_emit_candidates_drift_and_rename_line_shapes():
    """Shapes que a SKILL.md re-parseia downstream — drift `| distance:` e rename
    `| last: … | orphans: … | successors: #…` (drift num par, rename noutro)."""
    agg = _agg(
        markers_open=[_orphan("abx", "2026-06-08")],
        buckets_all=["abx", "aby", "tjpa-tools", "tjpa-tool"],
        buckets_per_journal=[
            ("2026-06-08", ["abx", "tjpa-tools", "tjpa-tool"]),  # idx0
            ("2026-06-12", ["aby"]),                             # idx1, gap 1 de abx
        ],
    )
    out = _emit_candidates(_cand(agg, cooccur_min=1, namedrift_max=2, rename_gap=1))
    assert "- #tjpa-tool #tjpa-tools | distance: 1" in out
    assert "- #abx | last: 2026-06-08 | orphans: j:2 | successors: #aby" in out


def test_emit_candidates_none_branch():
    empty = {"cooccurrence": [], "naming_drift": [], "rename_implicit": []}
    out = _emit_candidates(empty)
    assert out.count("_(none)_") == 3  # 3 seções vazias


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


# --- Discriminação 2f-vs-2g via compute_candidates (mecânica, Finding 4b) --

def test_drift_vs_rename_discrimination_mutually_exclusive():
    """Mesma proximidade léxica (abx/aby, Levenshtein 1): coexistir → naming-drift;
    gap temporal (com órfã) → rename-implicit (e NÃO naming-drift). compute_candidates
    discrimina mecanicamente — o mesmo par nunca dispara as duas."""
    # OVERLAP (drift): abx e aby coexistem no mesmo journal
    agg_drift = _agg(buckets_all=["abx", "aby"],
                     buckets_per_journal=[("2026-06-10", ["abx", "aby"])])
    cd = _cand(agg_drift)
    assert any({a, b} == {"abx", "aby"} for a, b, _ in cd["naming_drift"])
    assert cd["rename_implicit"] == []  # coexistem → não é rename

    # GAP (rename): abx some (com órfã), aby surge depois
    agg_gap = _agg(
        markers_open=[_orphan("abx", "2026-06-08")],
        buckets_all=["abx", "aby"],
        buckets_per_journal=[
            ("2026-06-08", ["abx"]),  # idx0
            ("2026-06-10", []),       # idx1
            ("2026-06-12", ["aby"]),  # idx2, gap 2
        ],
    )
    cg = _cand(agg_gap)
    assert cg["naming_drift"] == []  # não coexistem → não é drift
    assert any(a == "abx" and "aby" in succ for a, _, _, succ in cg["rename_implicit"])


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
