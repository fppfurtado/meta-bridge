"""Thin client para a Logseq Local HTTP Server (porta 12315).

Modalidade de escrita HTTP **aditiva** ao write engine file-direct (ADR-003):
opera com o Logseq **aberto** — a serialização da escrita é responsabilidade do
próprio Logseq, não do filesystem, então não há gate `pgrep` aqui (3ª categoria
de relação com o gate da ADR-001 SD7). Substrato consumido cross-process pelo
backend de annotations do toolkit e pelo reconciler.

Sem dep nova: cliente sobre `urllib` stdlib (filosofia minimalista).
"""

from __future__ import annotations

import calendar
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import _paths, logseq

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


def get_page_blocks_tree(page: str) -> list:
    """Retorna a árvore de blocos da página `page` (journal ou page qualquer).

    Cada bloco é um dict com `uuid`, `content` e `children` (lista aninhada).
    Retorna lista vazia quando a página não existe no grafo — usado pelo
    `reconcile-apply` como detector de nome-de-página errado (fallback ISO→ordinal).
    """
    result = _post("logseq.Editor.getPageBlocksTree", [page])
    return result if isinstance(result, list) else []


def update_block(uuid: str, content: str) -> object:
    """Atualiza o conteúdo do bloco `uuid` para `content`.

    O Logseq serializa a escrita — sem gate `pgrep` necessário (ADR-003).
    """
    return _post("logseq.Editor.updateBlock", [uuid, content])


def insert_block(src_block_uuid: str, content: str, sibling: bool = False) -> object:
    """Insere um bloco relativo ao bloco `src_block_uuid`.

    `sibling=False` (default) → filho do bloco src.
    `sibling=True` → irmão após o bloco src.
    O Logseq serializa a escrita — sem gate `pgrep` necessário (ADR-003).
    """
    return _post("logseq.Editor.insertBlock", [src_block_uuid, content, {"sibling": sibling}])


def insert_block_group(parent_uuid: str, group_lines: list) -> None:
    """Insere um grupo de linhas-bullet normalizadas sob `parent_uuid`,
    preservando o aninhamento por nível de indent.

    Reconstrói via API a árvore que o file-direct escreveria como linhas
    indentadas: nível 1 aninha sob `parent_uuid`; nível N sob o último bloco
    do nível N-1 (o `uuid` retornado por `insertBlock`). Cada linha é uma string
    `\\t*- <content>` (output de `logseq.normalize_indent`). Sem este reuso, os
    sub-bullets `commit:`/`plan:` seriam perdidos no write-path HTTP.
    """
    parent_by_level: dict[int, str] = {0: parent_uuid}
    for line in group_lines:
        level, rest = logseq.indent_level(line)
        content = logseq.bullet_text(rest) if logseq.is_bullet(rest) else rest
        anchor = parent_by_level.get(level - 1, parent_uuid)
        result = insert_block(anchor, content, sibling=False)
        new_uuid = result.get("uuid") if isinstance(result, dict) else None
        if new_uuid:
            parent_by_level[level] = new_uuid


def _ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def logseq_page_name_candidates(journal_path: str | Path) -> list[tuple[str, str]]:
    """Retorna candidatos de nome de página Logseq para um journal path.

    Retorna `[(name, label)]` em ordem de tentativa:
    1. ISO `YYYY-MM-DD` — formato padrão mais comum no Logseq.
    2. Ordinal US `Mon DDth, YYYY` — formato alternativo (ex.: `Jun 27th, 2026`).

    O chamador tenta cada candidato via `get_page_blocks_tree`; usa o primeiro
    que retorna lista não-vazia. Lista vazia → página não encontrada no grafo.
    Retorna lista vazia para stems inválidos (não no formato `YYYY_MM_DD`).
    """
    stem = Path(journal_path).expanduser().stem  # ex.: "2026_06_27"
    try:
        year, month, day = (int(p) for p in stem.split("_"))
    except ValueError:
        return []
    iso = f"{year:04d}-{month:02d}-{day:02d}"
    month_abbr = calendar.month_abbr[month]  # ex.: "Jun"
    ordinal = f"{month_abbr} {day}{_ordinal_suffix(day)}, {year}"
    return [(iso, "ISO"), (ordinal, "ordinal-US")]
