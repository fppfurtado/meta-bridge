import subprocess
import sys

import click

from . import __version__

# Imports de subcomandos vão no FIM deste arquivo — quebrar essa ordem causa
# import cycle, pois cada módulo importa `cli` e `fail_if_logseq_open` daqui.


def _logseq_open() -> bool:
    result = subprocess.run(
        ["pgrep", "-xi", "logseq"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


logseq_open = _logseq_open


def fail_if_logseq_open() -> None:
    if _logseq_open():
        click.echo(
            "Logseq desktop está aberto — fechar antes de invocar mb (gate falha-fechado).",
            err=True,
        )
        sys.exit(1)


@click.group()
@click.version_option(__version__, prog_name="mb")
def cli() -> None:
    """meta-bridge — CLI standalone para skills de bridge CC ↔ Logseq."""


from . import journal_note as _journal_note  # noqa: E402,F401 — registra @cli.command
from . import journal_close as _journal_close  # noqa: E402,F401 — registra @cli.command
from . import journal_review as _journal_review  # noqa: E402,F401 — registra @cli.command
from . import init_project as _init_project  # noqa: E402,F401 — registra @cli.command
from . import logseq_http_cli as _logseq_http_cli  # noqa: E402,F401 — registra @cli.command
from . import reconcile_check as _reconcile_check  # noqa: E402,F401 — registra @cli.command
from . import reconcile_apply as _reconcile_apply  # noqa: E402,F401 — registra @cli.command
