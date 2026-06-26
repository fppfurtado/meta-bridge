"""Superfície CLI dos primitivos do write-path HTTP (ADR-003).

Expõe `logseq_http` para consumo cross-process (backend de annotations do
toolkit, reconciler) que não importam `meta_bridge`. Estes comandos
**não** chamam `fail_if_logseq_open` — operam com o Logseq aberto (3ª
categoria do gate ADR-001 SD7), ao contrário dos subcomandos file-direct.
"""

from __future__ import annotations

import json
import sys

import click

from . import logseq_http
from .cli import cli


def _run(fn, *args) -> None:
    """Executa um primitivo HTTP, traduz `LogseqHTTPError` em exit 1 limpo e
    imprime o resultado como JSON quando há retorno."""
    try:
        result = fn(*args)
    except logseq_http.LogseqHTTPError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    if result is not None:
        click.echo(json.dumps(result, ensure_ascii=False))


@cli.command("logseq-append")
@click.argument("page")
@click.argument("content")
def logseq_append(page: str, content: str) -> None:
    """Append de um bloco na página PAGE via Logseq HTTP API (Logseq aberto)."""
    _run(logseq_http.append_block_in_page, page, content)


@cli.command("logseq-set-prop")
@click.argument("block_uuid")
@click.argument("key")
@click.argument("value")
def logseq_set_prop(block_uuid: str, key: str, value: str) -> None:
    """Upsert da property KEY=VALUE no bloco BLOCK_UUID (Logseq aberto)."""
    _run(logseq_http.upsert_block_property, block_uuid, key, value)


@cli.command("logseq-query")
@click.argument("datascript")
def logseq_query(datascript: str) -> None:
    """[experimental] Datascript query contra o grafo aberto; imprime JSON.

    Superfície ainda não-congelada — a forma da query pode mudar."""
    _run(logseq_http.datascript_query, datascript)
