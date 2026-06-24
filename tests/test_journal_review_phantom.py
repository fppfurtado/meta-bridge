"""pytest — heurística 8 phantom-tag (SD15).

CLI faz detecção determinística (regex `#tag` colada a delimitador de enclosure
`)`/`]`/`}` → phantom page no Logseq) + apply in-place mínimo (insere espaço,
uniforme prosa/query). Judgment semântico (qual candidato corrigir) vive na
SKILL.md. Suite cobre o substrato mecânico:

1. `detect_phantom_tags` — quais formas casam / não casam (incl. `#[[...]]`
   fora de escopo, namespaced tag, top-level limpo).
2. `parse_phantom` — parse do payload `## Phantom fixes` + não-colisão com
   o shape de TRANSITION (3 campos).
3. `apply_phantom` — espaço inserido uniforme prosa/query, idempotência,
   fail-soft, agrupamento por path.
"""

import io
import contextlib

from meta_bridge import journal_review as jr


# --- detect_phantom_tags ---------------------------------------------------

def test_detect_delimiters(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- a (#foo)\n- b [#bar]\n- c {#baz}\n")
    hits = jr.detect_phantom_tags(p)
    assert [(h["line"], h["raw"], h["tag"]) for h in hits] == [
        (1, "#foo)", "foo"),
        (2, "#bar]", "bar"),
        (3, "#baz}", "baz"),
    ]


def test_detect_namespaced_tag(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- ns (#a/b)\n")
    hits = jr.detect_phantom_tags(p)
    assert hits == [{"path": str(p), "line": 1, "raw": "#a/b)", "tag": "a/b"}]


def test_detect_ignores_clean_and_spaced(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- #domain top-level\n- ja #ok )\n- meio #mid texto\n")
    assert jr.detect_phantom_tags(p) == []


def test_detect_ignores_double_bracket_tag(tmp_path):
    # #[[...]] fora de escopo (o `[` não está no charset) — falso-negativo aceito.
    p = tmp_path / "j.md"
    p.write_text("- ref (#[[page]]) brkt\n")
    assert jr.detect_phantom_tags(p) == []


def test_detect_multiple_per_line(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- (#foo) e (#bar)\n")
    hits = jr.detect_phantom_tags(p)
    assert [h["raw"] for h in hits] == ["#foo)", "#bar)"]


def test_detect_missing_file(tmp_path):
    assert jr.detect_phantom_tags(tmp_path / "nope.md") == []


# --- emit_phantom_candidates ----------------------------------------------

def _emit(phantom):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        jr.emit_phantom_candidates(phantom)
    return buf.getvalue()


def test_emit_format():
    out = _emit([{"path": "/g/journals/2026_06_21.md", "line": 5, "raw": "#foo)", "tag": "foo"}])
    assert "### Phantom-tag candidates" in out
    assert "- /g/journals/2026_06_21.md:5 | #foo) | #foo" in out


def test_emit_empty():
    assert "_(none)_" in _emit([])


# --- parse_phantom ---------------------------------------------------------

def test_parse_phantom_basic():
    payload = "## Phantom fixes\n- /g/j.md:5 | #foo)\n- /g/p.md:12 | #bar]\n"
    assert jr.parse_phantom(payload) == [
        {"path": "/g/j.md", "line": 5, "raw": "#foo)"},
        {"path": "/g/p.md", "line": 12, "raw": "#bar]"},
    ]


def test_parse_phantom_exits_on_other_section():
    payload = "## Phantom fixes\n- /g/j.md:5 | #foo)\n## Hygiene\n- not a fix\n"
    assert jr.parse_phantom(payload) == [
        {"path": "/g/j.md", "line": 5, "raw": "#foo)"}
    ]


def test_parse_phantom_absent_section():
    assert jr.parse_phantom("## Hygiene\n- x\n") == []


def test_phantom_line_does_not_match_transition_re():
    # Não-colisão direção A: linha phantom (1 pipe) não casa TRANSITION_RE
    # (2 pipes) → não é reaplicada como transição no loop de run_apply_mode.
    from meta_bridge.journal_close import TRANSITION_RE
    assert TRANSITION_RE.match("- /g/j.md:5 | #foo)") is None


def test_transition_line_not_parsed_as_phantom_outside_section():
    # Não-colisão direção B: linha de transição (que CASA PHANTOM_FIX_RE) fora
    # de `## Phantom fixes` é barrada pelo section-gating, não pelo regex.
    payload = "- /g/j.md:1 | TODO a | DONE a\n## Hygiene\n- x\n"
    assert jr.parse_phantom(payload) == []


def test_parse_phantom_ignores_preceding_transitions():
    payload = (
        "- /g/j.md:1 | TODO a | DONE a\n"
        "## Phantom fixes\n"
        "- /g/j.md:5 | #foo)\n"
    )
    assert jr.parse_phantom(payload) == [
        {"path": "/g/j.md", "line": 5, "raw": "#foo)"}
    ]


# --- apply_phantom ---------------------------------------------------------

def test_apply_inserts_space_prose_and_query(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- prosa (#foo) fim\n- {{query (and #bar) }}\n")
    entries = [
        {"path": str(p), "line": 1, "raw": "#foo)"},
        {"path": str(p), "line": 2, "raw": "#bar)"},
    ]
    applied, skipped, _ = jr.apply_phantom(entries)
    assert (applied, skipped) == (2, 0)
    assert p.read_text() == "- prosa (#foo ) fim\n- {{query (and #bar ) }}\n"


def test_apply_multiple_same_line(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- (#foo) e (#bar)\n")
    entries = [
        {"path": str(p), "line": 1, "raw": "#foo)"},
        {"path": str(p), "line": 1, "raw": "#bar)"},
    ]
    applied, skipped, _ = jr.apply_phantom(entries)
    assert (applied, skipped) == (2, 0)
    assert p.read_text() == "- (#foo ) e (#bar )\n"


def test_apply_idempotent(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- prosa (#foo) fim\n")
    entries = [{"path": str(p), "line": 1, "raw": "#foo)"}]
    jr.apply_phantom(entries)
    # re-detectar e re-aplicar: nada a corrigir (espaço quebrou o match).
    assert jr.detect_phantom_tags(p) == []
    applied, skipped, _ = jr.apply_phantom(entries)
    assert (applied, skipped) == (0, 1)


def test_apply_failsoft_missing_file_and_drift(tmp_path):
    p = tmp_path / "j.md"
    p.write_text("- linha sem o raw esperado\n")
    entries = [
        {"path": str(tmp_path / "nope.md"), "line": 1, "raw": "#x)"},
        {"path": str(p), "line": 1, "raw": "#foo)"},
    ]
    applied, skipped, _ = jr.apply_phantom(entries)
    assert (applied, skipped) == (0, 2)


def test_apply_empty():
    assert jr.apply_phantom([]) == (0, 0, [])
