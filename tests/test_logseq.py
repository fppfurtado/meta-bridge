"""pytest — parser block-model de Logseq (meta_bridge/logseq.py, #37).

Trava os invariantes do parser ANTES de migrar os consumidores (Blocos 4-5):

- Cenário 1: indent_level — TAB vs 4-espaços vs mistos (a divergência que #37 mira).
- Cenário 2: normalize_indent + dedent_one_level.
- Cenário 3: primitivas — is_bullet/bullet_text/bucket_tag/parse_marker/parse_property.
- Cenário 4: parse_document — árvore de blocos + block-level properties.
- Cenário 5: parse_document — page-level properties (forma de page, F5 do reviewer).
- Cenário 6: markers GTD em sub-bullets aninhados (profundidade ≥2).
- Cenário 7: serialize round-trip idempotente sobre amostra enriquecida.
- Cenário 8: navegação line-based — find_bucket_line + bucket_region_end.
"""

from meta_bridge import logseq as L


# --- Cenário 1: indent_level (TAB vs 4-espaços vs mistos) -------------------

def test_indent_level_tab():
    assert L.indent_level("- top") == (0, "- top")
    assert L.indent_level("\t- one") == (1, "- one")
    assert L.indent_level("\t\t- two") == (2, "- two")


def test_indent_level_four_spaces_equals_tab():
    assert L.indent_level("    - one") == (1, "- one")
    assert L.indent_level("        - two") == (2, "- two")


def test_indent_level_mixed_tab_and_spaces():
    assert L.indent_level("\t    - mixed") == (2, "- mixed")
    # espaços avulsos <4 são ruído ignorado
    assert L.indent_level("  - noise") == (0, "- noise")


# --- Cenário 2: normalize_indent + dedent_one_level ------------------------

def test_normalize_indent_to_tab():
    assert L.normalize_indent("    - x") == "\t- x"
    assert L.normalize_indent("        - x") == "\t\t- x"
    assert L.normalize_indent("\t    - x") == "\t\t- x"
    assert L.normalize_indent("\t- x") == "\t- x"  # já canonical


def test_dedent_one_level():
    assert L.dedent_one_level("\t- x") == "- x"
    assert L.dedent_one_level("    - x") == "- x"
    assert L.dedent_one_level("- x") == "- x"  # nada a dedentar


def test_dedent_one_level_mixed_prefers_tab():
    # misto TAB+espaços: remove só o TAB (precedência), preserva os espaços.
    assert L.dedent_one_level("\t    - x") == "    - x"


# --- Cenário 3: primitivas -------------------------------------------------

def test_is_bullet_and_bullet_text():
    assert L.is_bullet("- foo") is True
    assert L.is_bullet("foo") is False
    assert L.is_bullet("key:: v") is False
    assert L.bullet_text("- foo bar") == "foo bar"


def test_bucket_tag():
    assert L.bucket_tag("#meta-bridge") == "meta-bridge"
    assert L.bucket_tag("#meta-bridge suffix") == "meta-bridge"
    assert L.bucket_tag("#tjpa.tools") == "tjpa.tools"  # `.` tolerado
    assert L.bucket_tag("not a bucket") is None
    assert L.bucket_tag("#tag #other") == "tag"  # só a 1ª (single-tag bucket)


def test_parse_marker():
    assert L.parse_marker("DONE finished it") == ("DONE", "finished it")
    assert L.parse_marker("TODO ") == ("TODO", "")        # marker + espaço, body vazio
    assert L.parse_marker("CANCELLED dropped") == ("CANCELLED", "dropped")
    assert L.parse_marker("TODO") is None                 # sem espaço → não é marker
    assert L.parse_marker("DONEISH x") is None            # marker deve ser palavra exata
    assert L.parse_marker("plain text") is None


def test_parse_property():
    assert L.parse_property("provenance:: #enriched") == ("provenance", "#enriched")
    assert L.parse_property("entities:: [[a]] [[b]]") == ("entities", "[[a]] [[b]]")
    assert L.parse_property("empty::") == ("empty", "")
    assert L.parse_property("key::value") == ("key", "value")  # espaço pós-:: opcional
    assert L.parse_property("- bullet") is None
    assert L.parse_property("just text") is None
    assert L.parse_property(":: noKey") is None


# --- Cenário 4: parse_document — árvore + block properties ------------------

def test_parse_document_tree_and_block_properties():
    text = (
        "- #meta-bridge\n"
        "\tclosed:: 2026-06-24T13:15:46-03:00\n"
        "\t- parent narrative\n"
        "\t\tprovenance:: #enriched\n"
        "\t\tentities:: [[x]]\n"
        "\t\t- DONE child task\n"
    )
    page_props, blocks = L.parse_document(text)
    assert page_props == {}
    assert len(blocks) == 1
    bucket = blocks[0]
    assert bucket.bucket == "meta-bridge"
    assert bucket.properties == {"closed": "2026-06-24T13:15:46-03:00"}
    assert len(bucket.children) == 1

    parent = bucket.children[0]
    assert parent.text == "parent narrative"
    assert parent.marker is None
    assert parent.properties == {"provenance": "#enriched", "entities": "[[x]]"}
    assert len(parent.children) == 1

    child = parent.children[0]
    assert child.marker == "DONE"
    assert child.content == "child task"


def test_block_content_empty_body_marker():
    # bullet `- DONE ` (marker sem corpo): content vazio, não IndexError nem "DONE".
    _, blocks = L.parse_document("- #b\n\t- DONE \n")
    child = blocks[0].children[0]
    assert child.marker == "DONE"
    assert child.content == ""


def test_property_attaches_to_nearest_shallower_owner():
    # property em nível N ancora no bullet imediatamente mais raso (< N).
    text = (
        "- a\n"
        "\t- b\n"
        "\t\tdeep:: v\n"   # level 2 → property de b (level 1)
        "\tmid:: w\n"      # level 1 → property de a (level 0)
    )
    _, blocks = L.parse_document(text)
    a = blocks[0]
    b = a.children[0]
    assert b.properties == {"deep": "v"}
    assert a.properties == {"mid": "w"}


def test_orphan_property_discarded_without_owner():
    # property top-level após o 1º bullet: sem owner mais raso → descartada, sem erro.
    page_props, blocks = L.parse_document("- root\norphan:: x\n")
    assert page_props == {}            # não é page-level (veio após bullet)
    assert blocks[0].properties == {}  # não ancorou em lugar nenhum


def test_parse_document_drops_blank_lines():
    # blanks são ignorados na árvore (responsabilidade do write path, não do tree).
    text = "- #b\n\n\t- child\n\n"
    _, blocks = L.parse_document(text)
    assert len(blocks) == 1
    assert blocks[0].children[0].text == "child"
    # caveat do contrato: serialize não recupera os blanks (round-trip ≠ com blanks).
    assert L.serialize(*L.parse_document(text)) == "- #b\n\t- child\n"


def test_parse_document_four_space_input_same_tree():
    tab = "- #b\n\t- one\n\t\t- two\n"
    spaces = "- #b\n    - one\n        - two\n"
    _, blocks_tab = L.parse_document(tab)
    _, blocks_sp = L.parse_document(spaces)
    # mesma estrutura lógica independente do estilo de indent
    assert blocks_tab[0].children[0].children[0].text == "two"
    assert blocks_sp[0].children[0].children[0].text == "two"


# --- Cenário 5: page-level properties (F5 do reviewer) ---------------------

def test_parse_document_page_level_properties():
    page = (
        "title:: Meu Projeto\n"
        "tags:: a, b\n"
        "- ## Heading\n"
        "\t- child bullet\n"
    )
    page_props, blocks = L.parse_document(page)
    assert page_props == {"title": "Meu Projeto", "tags": "a, b"}
    assert blocks[0].text == "## Heading"
    # property DEPOIS do 1º bullet não é page-level
    after = "- first\nlate:: prop\n"
    pp2, _ = L.parse_document(after)
    assert pp2 == {}


# --- Cenário 6: markers GTD aninhados --------------------------------------

def test_nested_gtd_markers_and_depth():
    text = (
        "- #b\n"
        "\t- TODO Próximos passos\n"
        "\t\t- DONE done sub\n"
        "\t\t- WAITING waiting sub\n"
    )
    _, blocks = L.parse_document(text)
    top = blocks[0].children[0]
    assert top.marker == "TODO"
    assert {c.marker for c in top.children} == {"DONE", "WAITING"}


# --- Cenário 7: serialize round-trip ---------------------------------------

def test_serialize_round_trip_enriched_sample():
    text = (
        "- #meta-bridge\n"
        "\tclosed:: 2026-06-24T13:15:46-03:00\n"
        "\t- Os dois momentos\n"
        "\t\tprovenance:: #enriched\n"
        "\t\tentities:: [[connector-pje-mandamus-tjpa]]\n"
        "\t\t- DONE Contrato #inbox\n"
        "\t\t\t- PR [#32](url)\n"
    )
    page_props, blocks = L.parse_document(text)
    assert L.serialize(page_props, blocks) == text


def test_serialize_round_trip_with_page_props():
    text = "title:: P\ntags:: x\n- root\n\t- child\n"
    assert L.serialize(*L.parse_document(text)) == text


def test_serialize_empty():
    assert L.serialize({}, []) == ""


# --- Cenário 8: navegação line-based ---------------------------------------

def test_find_bucket_line_and_region_end():
    lines = [
        "- #alpha",
        "\tclosed:: x",
        "\t- DONE a",
        "- #beta",
        "\t- DONE b",
    ]
    assert L.find_bucket_line(lines, "alpha") == 0
    assert L.find_bucket_line(lines, "beta") == 3
    assert L.find_bucket_line(lines, "missing") is None
    # região do alpha vai até o próximo bullet top-level (beta em 3)
    assert L.bucket_region_end(lines, 0) == 3
    assert L.bucket_region_end(lines, 3) == 5  # beta vai até EOF


def test_find_bucket_line_suffix_form():
    lines = ["- #repo Cluster Hub", "\t- DONE x"]
    assert L.find_bucket_line(lines, "repo") == 0


def test_find_bucket_line_no_prefix_collision():
    # `#meta` NÃO casa bucket `#meta-bridge` (o ($| ) previne colisão de prefixo).
    lines = ["- #meta-bridge", "\t- DONE x"]
    assert L.find_bucket_line(lines, "meta") is None
    assert L.find_bucket_line(lines, "meta-bridge") == 0
