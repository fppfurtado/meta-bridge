"""Tests para meta_bridge/logseq_http.py — substrato write-path HTTP (ADR-003).

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest):
- config-loading: presente, ausente, sem token, endpoint não-loopback, permissão frouxa
- parse de resposta HTTP: objeto JSON, body vazio → None, non-JSON → erro
- tradução de erro: HTTP 401, HTTPError genérico, URLError (conexão)
- segurança: redirect bloqueado; token nunca aparece em mensagem de erro
- primitivos: nome de método + ordem de args corretos por chamada

HTTP real é **mockado** (sem Logseq vivo na suite) — separação mock-vs-real explícita.
"""
import io
import json
import urllib.error
import urllib.request

import pytest

from meta_bridge import logseq_http


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Aponta CONFIG_PATH para um config válido em tmp_path (chmod 600)."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"token": "s3cr3t-token"}))
    cfg.chmod(0o600)
    monkeypatch.setattr(logseq_http, "CONFIG_PATH", cfg)
    return cfg


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _mock_open(monkeypatch, body=b"", exc=None):
    def fake_open(request, timeout=None):
        if exc is not None:
            raise exc
        return _FakeResponse(body)

    monkeypatch.setattr(logseq_http._OPENER, "open", fake_open)


def _http_error(code):
    return urllib.error.HTTPError(
        "http://127.0.0.1:12315/api", code, "msg", {}, io.BytesIO(b"")
    )


# --- config loading ---


def test_load_config_default_endpoint(config):
    endpoint, token = logseq_http._load_config()
    assert endpoint == logseq_http.DEFAULT_ENDPOINT
    assert token == "s3cr3t-token"


def test_load_config_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(logseq_http, "CONFIG_PATH", tmp_path / "nope.json")
    with pytest.raises(logseq_http.LogseqHTTPError, match="config ausente"):
        logseq_http._load_config()


def test_load_config_missing_token(config):
    config.write_text(json.dumps({"endpoint": "http://127.0.0.1:12315"}))
    with pytest.raises(logseq_http.LogseqHTTPError, match="sem campo .token"):
        logseq_http._load_config()


def test_load_config_rejects_non_loopback(config):
    config.write_text(json.dumps({"token": "x", "endpoint": "http://evil.example"}))
    with pytest.raises(logseq_http.LogseqHTTPError, match="não-loopback"):
        logseq_http._load_config()


def test_load_config_rejects_non_http_scheme(config):
    config.write_text(json.dumps({"token": "x", "endpoint": "https://127.0.0.1:12315"}))
    with pytest.raises(logseq_http.LogseqHTTPError, match="não-loopback"):
        logseq_http._load_config()


def test_load_config_malformed_json(config):
    config.write_text("{not json")
    with pytest.raises(logseq_http.LogseqHTTPError, match="ilegível"):
        logseq_http._load_config()


def test_load_config_warns_on_loose_perms(config, capsys):
    config.chmod(0o644)
    logseq_http._load_config()
    err = capsys.readouterr().err
    assert "chmod 600" in err
    assert "s3cr3t-token" not in err  # token nunca logado


# --- response parsing ---


def test_post_sends_bearer_and_payload(config, monkeypatch):
    captured = {}

    def fake_open(request, timeout=None):
        captured["request"] = request
        return _FakeResponse(b"")

    monkeypatch.setattr(logseq_http._OPENER, "open", fake_open)
    logseq_http.append_block_in_page("page", "content")
    req = captured["request"]
    assert req.full_url == logseq_http.DEFAULT_ENDPOINT + "/api"
    assert req.get_header("Authorization") == "Bearer s3cr3t-token"
    assert req.method == "POST"
    assert json.loads(req.data) == {
        "method": "logseq.Editor.appendBlockInPage",
        "args": ["page", "content"],
    }


def test_post_parses_json_object(config, monkeypatch):
    _mock_open(monkeypatch, body=json.dumps({"uuid": "abc"}).encode("utf-8"))
    assert logseq_http.append_block_in_page("page", "content") == {"uuid": "abc"}


def test_post_empty_body_returns_none(config, monkeypatch):
    _mock_open(monkeypatch, body=b"")
    assert logseq_http.upsert_block_property("u", "k", "v") is None


def test_post_non_json_raises(config, monkeypatch):
    _mock_open(monkeypatch, body=b"<html>not json</html>")
    with pytest.raises(logseq_http.LogseqHTTPError, match="não-JSON"):
        logseq_http.datascript_query("[:find ?b]")


# --- tradução de erro ---


def test_post_401_clear_message(config, monkeypatch):
    _mock_open(monkeypatch, exc=_http_error(401))
    with pytest.raises(logseq_http.LogseqHTTPError, match="401"):
        logseq_http.append_block_in_page("p", "c")


def test_post_generic_http_error(config, monkeypatch):
    _mock_open(monkeypatch, exc=_http_error(500))
    with pytest.raises(logseq_http.LogseqHTTPError, match="HTTP 500"):
        logseq_http.append_block_in_page("p", "c")


def test_post_connection_refused(config, monkeypatch):
    _mock_open(monkeypatch, exc=urllib.error.URLError("connection refused"))
    with pytest.raises(logseq_http.LogseqHTTPError, match="não acessível"):
        logseq_http.append_block_in_page("p", "c")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exc": _http_error(401)},
        {"exc": _http_error(500)},
        {"exc": urllib.error.URLError("refused")},
        {"body": b"<html>not json</html>"},
    ],
)
def test_no_error_path_leaks_token(config, monkeypatch, kwargs):
    _mock_open(monkeypatch, **kwargs)
    with pytest.raises(logseq_http.LogseqHTTPError) as excinfo:
        logseq_http.append_block_in_page("p", "c")
    assert "s3cr3t-token" not in str(excinfo.value)


# --- segurança: redirect bloqueado ---


def test_redirect_blocked():
    handler = logseq_http._NoRedirect()
    req = urllib.request.Request("http://127.0.0.1:12315/api")
    with pytest.raises(urllib.error.HTTPError, match="redirect bloqueado"):
        handler.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "http://evil/")


def test_opener_has_noredirect_handler():
    assert any(
        isinstance(h, logseq_http._NoRedirect) for h in logseq_http._OPENER.handlers
    )


# --- primitivos: método + ordem de args ---


def test_primitives_call_correct_methods(config, monkeypatch):
    calls = []
    monkeypatch.setattr(
        logseq_http, "_post", lambda method, args: calls.append((method, args))
    )
    logseq_http.append_block_in_page("P", "C")
    logseq_http.upsert_block_property("U", "K", "V")
    logseq_http.datascript_query("Q")
    assert calls == [
        ("logseq.Editor.appendBlockInPage", ["P", "C"]),
        ("logseq.Editor.upsertBlockProperty", ["U", "K", "V"]),
        ("logseq.DB.datascriptQuery", ["Q"]),
    ]


# ---------------------------------------------------------------------------
# insert_block_group — reconstrução de aninhamento (paridade com file-direct)
# ---------------------------------------------------------------------------

def test_insert_block_group_reconstructs_nesting(monkeypatch):
    """Sub-bullets nível 2 aninham sob o bloco-child nível 1, não sob o parent."""
    calls = []
    uuids = iter(["uuid-child", "uuid-sub1", "uuid-sub2"])

    def fake_insert(anchor, content, sibling=False):
        calls.append((anchor, content))
        return {"uuid": next(uuids)}

    monkeypatch.setattr(logseq_http, "insert_block", fake_insert)
    group = ["\t- TODO fix bug", "\t\t- commit: abc1234", "\t\t- plan: do-x"]
    logseq_http.insert_block_group("bucket-uuid", group)
    assert calls == [
        ("bucket-uuid", "TODO fix bug"),
        ("uuid-child", "commit: abc1234"),
        ("uuid-child", "plan: do-x"),
    ]


def test_insert_block_group_uuid_missing_falls_back_to_parent(monkeypatch):
    """insertBlock sem uuid no retorno → sub-bullet ancora no parent (degrada,
    não perde o dado — failure-soft de nesting)."""
    calls = []
    monkeypatch.setattr(
        logseq_http,
        "insert_block",
        lambda anchor, content, sibling=False: calls.append((anchor, content)),
    )
    group = ["\t- TODO x", "\t\t- commit: deadbee"]
    logseq_http.insert_block_group("bucket-uuid", group)
    assert calls == [("bucket-uuid", "TODO x"), ("bucket-uuid", "commit: deadbee")]


# ---------------------------------------------------------------------------
# resolve_journal_page_name / resolve_journal_tree — robusto ao date-format
# ---------------------------------------------------------------------------

def test_resolve_journal_page_name_via_journal_day(monkeypatch):
    """Resolve o nome canônico (qualquer formato) via :block/journal-day."""
    captured = {}

    def fake_query(q):
        captured["q"] = q
        return [["2026/06/28"]]  # formato yyyy/MM/dd do grafo real

    monkeypatch.setattr(logseq_http, "datascript_query", fake_query)
    assert logseq_http.resolve_journal_page_name("~/Notes/logseq/journals/2026_06_28.md") == "2026/06/28"
    assert "20260628" in captured["q"]  # journal-day correto


def test_resolve_journal_page_name_invalid_stem_skips_query(monkeypatch):
    """Stem fora de YYYY_MM_DD → None sem tocar a API."""
    monkeypatch.setattr(
        logseq_http, "datascript_query",
        lambda q: (_ for _ in ()).throw(AssertionError("não deveria consultar")),
    )
    assert logseq_http.resolve_journal_page_name("pages/some-page.md") is None


def test_resolve_journal_page_name_not_found(monkeypatch):
    monkeypatch.setattr(logseq_http, "datascript_query", lambda q: [])
    assert logseq_http.resolve_journal_page_name("2026_06_28.md") is None


def test_resolve_journal_tree_uses_canonical_name(monkeypatch):
    """Journal existente → (nome canônico, árvore) via journal-day."""
    monkeypatch.setattr(logseq_http, "resolve_journal_page_name", lambda p: "2026/06/28")
    monkeypatch.setattr(
        logseq_http, "get_page_blocks_tree",
        lambda name: [{"uuid": "x", "content": "#dev"}] if name == "2026/06/28" else [],
    )
    name, tree = logseq_http.resolve_journal_tree("2026_06_28.md")
    assert name == "2026/06/28"
    assert tree and tree[0]["content"] == "#dev"


def test_resolve_journal_tree_falls_back_to_candidates(monkeypatch):
    """Journal não resolvido por journal-day (inexistente) → candidatos de formato
    para o create-path; sem árvore → (primeiro candidato, [])."""
    monkeypatch.setattr(logseq_http, "resolve_journal_page_name", lambda p: None)
    monkeypatch.setattr(logseq_http, "get_page_blocks_tree", lambda name: [])
    name, tree = logseq_http.resolve_journal_tree("2026_06_28.md")
    assert name == "2026-06-28"  # candidates[0][0] (ISO) como alvo de create
    assert tree == []


def test_resolve_journal_tree_invalid_stem_returns_none(monkeypatch):
    """Path de page (não-journal) → (None, []) → caller cai no path de page."""
    monkeypatch.setattr(logseq_http, "resolve_journal_page_name", lambda p: None)
    name, tree = logseq_http.resolve_journal_tree("pages/sources/foo.md")
    assert name is None
    assert tree == []


# ---------------------------------------------------------------------------
# find_or_create_bucket_block — find-or-create robusto ao create de journal novo
# ---------------------------------------------------------------------------

def test_find_or_create_bucket_existing(monkeypatch):
    """Bucket já presente → retorna sem nenhum append."""
    bucket = {"uuid": "b", "content": "#dev", "children": []}
    monkeypatch.setattr(logseq_http, "resolve_journal_tree", lambda p: ("J", [bucket]))
    monkeypatch.setattr(
        logseq_http, "append_block_in_page",
        lambda *a: (_ for _ in ()).throw(AssertionError("não deveria criar")),
    )
    name, b = logseq_http.find_or_create_bucket_block("2026_06_28.md", "dev")
    assert name == "J" and b is bucket


def test_find_or_create_bucket_absent_page_exists(monkeypatch):
    """Bucket ausente em journal existente → 1 append, encontra no re-resolve."""
    bucket = {"uuid": "b", "content": "#dev", "children": []}
    seq = iter([("J", []), ("J", [bucket])])
    appends = []
    monkeypatch.setattr(logseq_http, "resolve_journal_tree", lambda p: next(seq))
    monkeypatch.setattr(logseq_http, "append_block_in_page", lambda page, c: appends.append((page, c)))
    name, b = logseq_http.find_or_create_bucket_block("2026_06_28.md", "dev")
    assert name == "J" and b is bucket
    assert appends == [("J", "#dev")]  # exatamente 1 append


def test_find_or_create_bucket_new_journal_retries(monkeypatch):
    """Journal inexistente: 1º append materializa página vazia (bloco não landa);
    re-resolve via journal-day + retry no nome canônico → encontra."""
    bucket = {"uuid": "b", "content": "#dev", "children": []}
    # ambos os resolves retornam árvore vazia (página criada mas bucket não landou)
    seq = iter([("2026-06-28", []), ("2026/06/28", [])])
    appends = []
    monkeypatch.setattr(logseq_http, "resolve_journal_tree", lambda p: next(seq))
    monkeypatch.setattr(logseq_http, "append_block_in_page", lambda page, c: appends.append((page, c)))
    monkeypatch.setattr(logseq_http, "get_page_blocks_tree", lambda name: [bucket])
    name, b = logseq_http.find_or_create_bucket_block("2026_06_28.md", "dev")
    assert name == "2026/06/28" and b is bucket
    # 2 appends: 1º (ISO, materializa página) + retry (canônico, landa o bucket)
    assert appends == [("2026-06-28", "#dev"), ("2026/06/28", "#dev")]


def test_find_or_create_bucket_invalid_stem(monkeypatch):
    monkeypatch.setattr(logseq_http, "resolve_journal_tree", lambda p: (None, []))
    name, b = logseq_http.find_or_create_bucket_block("pages/foo.md", "dev")
    assert name is None and b is None
