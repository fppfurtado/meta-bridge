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


@cli.command("init-project")
def init_project() -> None:
    """Cria/atualiza Project Page no graph Logseq (stub)."""
    click.echo("mb init-project: stub — implementação no Bloco 5.")


from . import journal_note as _journal_note  # noqa: E402,F401 — registra @cli.command
from . import journal_close as _journal_close  # noqa: E402,F401 — registra @cli.command
from . import journal_review as _journal_review  # noqa: E402,F401 — registra @cli.command
