"""Thin client para a Logseq Local HTTP Server (porta 12315).

Modalidade de escrita HTTP **aditiva** ao write engine file-direct (ADR-003):
opera com o Logseq **aberto** — a serialização da escrita é responsabilidade do
próprio Logseq, não do filesystem, então não há gate `pgrep` aqui (3ª categoria
de relação com o gate da ADR-001 SD7). Substrato consumido cross-process pelo
backend de annotations do toolkit e pelo reconciler.

Sem dep nova: cliente sobre `urllib` stdlib (filosofia minimalista).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

from . import _paths

CONFIG_PATH = _paths.LOGSEQ_HTTP_CONFIG_PATH
DEFAULT_ENDPOINT = _paths.DEFAULT_LOGSEQ_HTTP_ENDPOINT

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class LogseqHTTPError(Exception):
    """Erro traduzido da Logseq Local HTTP Server (config, conexão ou auth)."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Bloqueia redirects: urllib reenvia `Authorization` cross-host, e o bearer
    token concede read+write do grafo inteiro — jamais deve seguir para outro
    host. Nenhum redirect legítimo é esperado num POST loopback `/api`."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code, f"redirect bloqueado para {newurl}", headers, fp
        )


_OPENER = urllib.request.build_opener(_NoRedirect)


def _load_config() -> tuple[str, str]:
    """Retorna `(endpoint, token)` do config file dedicado.

    Schema flat `{"token": "...", "endpoint": "..."}`; endpoint cai no default
    quando omitido. Token nunca é logado.
    """
    if not CONFIG_PATH.exists():
        raise LogseqHTTPError(
            f"config ausente em {CONFIG_PATH} — criar com "
            '{"token": "<token do Local HTTP Server>"} e rodar `chmod 600`.'
        )
    # Enforcement leve: o token concede read+write do grafo inteiro via API de
    # plugin; permissão frouxa vaza o cognitive hub. Warning, não bloqueio.
    if CONFIG_PATH.stat().st_mode & 0o077:
        print(
            f"aviso: {CONFIG_PATH} legível por outros — rodar `chmod 600` "
            "(o token concede read+write do grafo inteiro).",
            file=sys.stderr,
        )
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise LogseqHTTPError(f"config ilegível em {CONFIG_PATH}: {exc}") from exc
    token = data.get("token")
    if not token:
        raise LogseqHTTPError(
            f"config em {CONFIG_PATH} sem campo `token` — adicionar o token do "
            "Local HTTP Server do Logseq."
        )
    endpoint = data.get("endpoint") or DEFAULT_ENDPOINT
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in _LOOPBACK_HOSTS:
        raise LogseqHTTPError(
            f"endpoint {endpoint!r} não-loopback recusado — o token concede "
            "read+write do grafo inteiro e só deve trafegar para o Logseq local."
        )
    return endpoint, token


def _post(method: str, args: list) -> object:
    """POST `{endpoint}/api` com bearer token; retorna o JSON da resposta.

    Traduz falha de conexão (Logseq fechado / server desabilitado) e auth
    (HTTP 401) em `LogseqHTTPError` acionável — nunca stacktrace cru.
    """
    endpoint, token = _load_config()
    payload = json.dumps({"method": method, "args": args}).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}/api",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with _OPENER.open(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise LogseqHTTPError(
                "token inválido/ausente (HTTP 401) — conferir o token do Local "
                f"HTTP Server em {CONFIG_PATH}."
            ) from exc
        raise LogseqHTTPError(
            f"Logseq HTTP API respondeu HTTP {exc.code} para `{method}`."
        ) from exc
    except urllib.error.URLError as exc:
        raise LogseqHTTPError(
            f"Logseq HTTP server não acessível em {endpoint} "
            "(Logseq aberto? Local HTTP Server habilitado?)."
        ) from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LogseqHTTPError(
            f"resposta não-JSON da Logseq HTTP API para `{method}`."
        ) from exc


def append_block_in_page(page: str, content: str) -> object:
    """Append de um bloco no fim da página `page` (cria a página se ausente)."""
    return _post("logseq.Editor.appendBlockInPage", [page, content])


def upsert_block_property(block_uuid: str, key: str, value: str) -> object:
    return _post("logseq.Editor.upsertBlockProperty", [block_uuid, key, value])


def datascript_query(query: str) -> object:
    return _post("logseq.DB.datascriptQuery", [query])
