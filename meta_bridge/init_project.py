"""mb init-project — cria ou atualiza Project Page no graph Logseq.

Per F1 design-reviewer absorption: cluster prompt fica na SKILL.md
(`/init-logseq-project`); CLI exige `--cluster <name>` quando lookups falham.

Ordem de resolução de cluster:
1. `--cluster <name>` se passado (precedente sobre lookups).
2. Lookup em `~/.mrconfig` (sections `[<path>]` + `tags = <cluster> [<sub>]`).
3. Lookup em `~/Projects/meta-system/REPOS.md` (tabela markdown + heading `## <cluster>`).
4. Sem nenhum → exit non-zero orientando.

Invariantes preservados de ADR-001 Sub-decisão 4 (per F4 absorption):
- Bootstrap via `~/Notes/logseq/pages/Project Template.md` (skip wrapper + dedent 1 tab fixo).
- Macro substitution `<% current page %>` → `[[<basename>]]`.
- Update idempotente: 4 props mecânicas (cluster, subcluster, repo-path, repo-host)
  sobrescritas; demais (status, description, blocos humanos) preservados.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import click

from . import _paths, logseq, logseq_http
from .cli import cli, logseq_open
from .logseq_http import LogseqHTTPError


MRCONFIG_PATH = Path.home() / ".mrconfig"
REPOS_MD_PATH = Path.home() / "Projects" / "meta-system" / "REPOS.md"
PROJECT_TEMPLATE = _paths.PAGES_DIR / "Project Template.md"

MRCONFIG_SECTION_RE = re.compile(r"^\[(.+)\]$")
MRCONFIG_TAGS_RE = re.compile(r"^tags\s*=\s*(.+)$")
PROPS_MECANICAS = ("cluster", "subcluster", "repo-path", "repo-host")
TEMPLATE_WRAPPER = ("type::", "- template::", "template-including-parent::")
MACRO_CURRENT_PAGE = "<% current page %>"


def derive_repo_host(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "#local"
    url = result.stdout.strip()
    m = re.search(r"(?:github\.com|gitlab\.com|[\w.-]+\.\w+)", url)
    if not m:
        return "#local"
    host = m.group(0)
    if "github.com" in host:
        return "#github"
    if "gitlab.com" in host:
        return "#gitlab"
    return f"#{host}"


def lookup_mrconfig(target_path: Path) -> tuple[str, str] | None:
    """Retorna (cluster, subcluster) se match; None caso contrário."""
    if not MRCONFIG_PATH.exists():
        return None
    target_resolved = target_path.resolve()
    header_matches = False
    for line in MRCONFIG_PATH.read_text().splitlines():
        sm = MRCONFIG_SECTION_RE.match(line)
        if sm:
            header_raw = sm.group(1)
            try:
                header_expanded = Path(os.path.expandvars(header_raw)).expanduser()
                header_resolved = header_expanded.resolve()
                header_matches = header_resolved == target_resolved
            except OSError:
                header_matches = False
            continue
        if header_matches:
            tm = MRCONFIG_TAGS_RE.match(line)
            if tm:
                tokens = tm.group(1).split()
                cluster = tokens[0] if tokens else ""
                subcluster = tokens[1] if len(tokens) > 1 else ""
                return (cluster, subcluster)
    return None


def lookup_repos_md(basename: str) -> str | None:
    """Retorna cluster se basename aparece em tabela; None caso contrário."""
    if not REPOS_MD_PATH.exists():
        return None
    lines = REPOS_MD_PATH.read_text().splitlines()
    current_cluster: str | None = None
    pattern = f"| `{basename}`"
    for line in lines:
        if line.startswith("## "):
            current_cluster = line[3:].strip()
            continue
        if line.startswith(pattern):
            return current_cluster
    return None


def extract_description(repo_path: Path) -> str:
    """Lê primeira seção após '# <title>' em CLAUDE.md (ou README.md fallback)
    e retorna primeiro parágrafo (max 200 chars)."""
    for filename in ("CLAUDE.md", "README.md"):
        f = repo_path / filename
        if not f.exists():
            continue
        lines = f.read_text().splitlines()
        body: list[str] = []
        seen_title = False
        for line in lines:
            if not seen_title:
                if line.startswith("# "):
                    seen_title = True
                continue
            if line.startswith("## "):
                break
            body.append(line)
        # First paragraph = first non-empty block separated by blank line
        paragraph: list[str] = []
        for line in body:
            if line.strip() == "":
                if paragraph:
                    break
                continue
            paragraph.append(line.strip())
        result = " ".join(paragraph)
        if result:
            return result[:200]
    return ""


def bootstrap_from_template(basename: str) -> list[str]:
    """Lê Project Template, skip wrapper, dedent 1 tab, substitui macro."""
    if not PROJECT_TEMPLATE.exists():
        raise click.ClickException(
            f"Template '{PROJECT_TEMPLATE}' ausente — setup do graph (Onda 3) requerido."
        )
    raw = PROJECT_TEMPLATE.read_text().splitlines()
    body: list[str] = []
    for line in raw:
        # lstrip necessário porque Logseq indenta props-filhas de `- template::`
        # com 2 espaços (`  template-including-parent:: false`).
        stripped_left = line.lstrip()
        if any(stripped_left.startswith(w) for w in TEMPLATE_WRAPPER):
            continue
        body.append(logseq.dedent_one_level(line))
    while body and body[0].strip() == "":
        body.pop(0)
    return [line.replace(MACRO_CURRENT_PAGE, f"[[{basename}]]") for line in body]


def fill_props_in_template(
    body: list[str],
    cluster: str,
    subcluster: str,
    repo_path: Path,
    repo_host: str,
    description: str,
) -> list[str]:
    """Substitui props vazias no template + opcionalmente adiciona description."""
    prop_values = {
        "cluster": cluster,
        "subcluster": subcluster,
        "status": "#active",
        "repo-path": str(repo_path),
        "repo-host": repo_host,
    }
    out: list[str] = []
    for line in body:
        level, rest = logseq.indent_level(line)
        kv = logseq.parse_property(rest)
        # prop mecânica com valor vazio no template → preencher, preservando indent.
        if kv is not None and kv[0] in prop_values and kv[1].strip() == "":
            leading = line[: len(line) - len(rest)]
            out.append(f"{leading}{kv[0]}:: {prop_values[kv[0]]}")
        else:
            out.append(line)
    if description:
        # Adiciona bullet `- description:: <text>` antes do primeiro
        # `- ## <heading>` (per SKILL.md: "primeira linha sob root").
        for i, line in enumerate(out):
            if line.startswith("- ## "):
                out.insert(i, f"- description:: {description}")
                break
    return out


def update_existing_page(
    page_path: Path,
    cluster: str,
    subcluster: str,
    repo_path: Path,
    repo_host: str,
) -> dict[str, int]:
    """Sobrescreve 4 props mecânicas in-place; preserva tudo o mais.
    Retorna counts {sobrescritas, adicionadas, preservadas_humanas}.

    Props faltantes são inseridas após a **primeira** prop encontrada
    (mecânica ou humana), preservando ordem canonical entre as faltantes
    (per SKILL.md Sub-decisão 4 § "Presente — atualização cirúrgica")."""
    lines = page_path.read_text().splitlines()
    new_values = {
        "cluster": cluster,
        "subcluster": subcluster,
        "repo-path": str(repo_path),
        "repo-host": repo_host,
    }
    counts = {"sobrescritas": 0, "adicionadas": 0, "preservadas_humanas": 0}
    seen_props: set[str] = set()
    out: list[str] = []
    first_prop_idx: int | None = None
    for line in lines:
        level, rest = logseq.indent_level(line)
        kv = logseq.parse_property(rest)
        leading = line[: len(line) - len(rest)]
        if kv is not None and kv[0] in PROPS_MECANICAS:
            # prop mecânica → sobrescreve valor, preserva indent.
            out.append(f"{leading}{kv[0]}:: {new_values[kv[0]]}")
            seen_props.add(kv[0])
            if first_prop_idx is None:
                first_prop_idx = len(out) - 1
            counts["sobrescritas"] += 1
        else:
            if kv is not None:  # prop humana → preserva linha verbatim
                counts["preservadas_humanas"] += 1
                if first_prop_idx is None:
                    first_prop_idx = len(out)
            out.append(line)

    missing = [p for p in PROPS_MECANICAS if p not in seen_props]
    if missing and first_prop_idx is not None:
        indent_ref = re.match(r"^(\s*)", out[first_prop_idx]).group(1)
        insert_at = first_prop_idx + 1
        for prop in missing:
            out.insert(insert_at, f"{indent_ref}{prop}:: {new_values[prop]}")
            insert_at += 1
            counts["adicionadas"] += 1

    page_path.write_text("\n".join(out) + "\n")
    return counts


def _init_via_http(
    base: str,
    resolved_cluster: str,
    resolved_subcluster: str,
    repo: Path,
    repo_host: str,
) -> str:
    """Cria/atualiza Project Page via Logseq HTTP API. Retorna 'criado'/'atualizado'.

    HTTP path YAGNI: sem template replication (layout flat). `append_block_in_page`
    cria a página se ausente; `upsert_block_property` no primeiro bloco seta/atualiza
    as 4 props mecânicas (cluster, subcluster, repo-path, repo-host). LogseqHTTPError
    propaga para o caller traduzir em exit 1.
    """
    tree = logseq_http.get_page_blocks_tree(base)
    mode = "criado" if not tree else "atualizado"
    if not tree:
        logseq_http.append_block_in_page(base, "")
        tree = logseq_http.get_page_blocks_tree(base) or []
    if not tree:
        raise LogseqHTTPError(f"falha ao criar/encontrar página {base!r} no grafo.")
    block_uuid = tree[0]["uuid"]
    props = {
        "cluster": resolved_cluster,
        "subcluster": resolved_subcluster,
        "repo-path": str(repo),
        "repo-host": repo_host,
    }
    for key, value in props.items():
        logseq_http.upsert_block_property(block_uuid, key, value)
    return mode


@cli.command("init-project")
@click.option("--repo-path", type=click.Path(file_okay=False, path_type=Path), default=None, help="Path do repo (default cwd).")
@click.option("--basename", type=str, default=None, help="Override do basename (default=basename do repo-path).")
@click.option("--cluster", type=str, default=None, help="Cluster do repo. Obrigatório se lookups mrconfig/REPOS.md falharem.")
@click.option("--subcluster", type=str, default="", help="Subcluster opcional (default vazio).")
def init_project_cmd(
    repo_path: Path | None,
    basename: str | None,
    cluster: str | None,
    subcluster: str,
) -> None:
    """Cria/atualiza Project Page no graph Logseq (idempotente)."""
    repo = (repo_path or Path.cwd()).resolve()
    # Verifica git repo
    rev = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if rev.returncode != 0:
        click.echo(f"--repo-path {repo} não é git repo.", err=True)
        sys.exit(1)
    repo = Path(rev.stdout.strip())
    base = basename or repo.name

    # Cluster: --cluster precede; depois mrconfig; depois REPOS.md
    resolved_cluster = cluster
    resolved_subcluster = subcluster
    cluster_source = "flag"
    if not resolved_cluster:
        mr_match = lookup_mrconfig(repo)
        if mr_match:
            resolved_cluster, mr_sub = mr_match
            if not resolved_subcluster:
                resolved_subcluster = mr_sub
            cluster_source = "mrconfig"
    if not resolved_cluster:
        repos_match = lookup_repos_md(base)
        if repos_match:
            resolved_cluster = repos_match
            cluster_source = "REPOS.md"
    if not resolved_cluster:
        click.echo(
            f"cluster ausente: passe --cluster <name> ou cadastre {base} em "
            f"{MRCONFIG_PATH} ou {REPOS_MD_PATH}.",
            err=True,
        )
        sys.exit(1)

    repo_host = derive_repo_host(repo)
    description = extract_description(repo)

    if logseq_open():
        try:
            mode = _init_via_http(
                base, resolved_cluster, resolved_subcluster, repo, repo_host
            )
        except LogseqHTTPError as exc:
            click.echo(
                f"Logseq HTTP error — fechar o Logseq ou verificar o Local HTTP Server.\n{exc}",
                err=True,
            )
            sys.exit(1)
        click.echo(f"page: {base} (via HTTP)")
        click.echo(f"mode: {mode}")
        click.echo(f"cluster: {resolved_cluster} (source: {cluster_source})")
        if resolved_subcluster:
            click.echo(f"subcluster: {resolved_subcluster}")
        click.echo(f"repo-host: {repo_host}")
        return

    page_path = _paths.page_path(base)
    page_path.parent.mkdir(parents=True, exist_ok=True)

    if not page_path.exists():
        body = bootstrap_from_template(base)
        body = fill_props_in_template(
            body,
            resolved_cluster,
            resolved_subcluster,
            repo,
            repo_host,
            description,
        )
        page_path.write_text("\n".join(body) + "\n")
        mode = "criado"
        counts = {"linhas": len(body)}
    else:
        mode = "atualizado"
        counts = update_existing_page(
            page_path,
            resolved_cluster,
            resolved_subcluster,
            repo,
            repo_host,
        )

    click.echo(f"page: {page_path}")
    click.echo(f"mode: {mode}")
    click.echo(f"cluster: {resolved_cluster} (source: {cluster_source})")
    if resolved_subcluster:
        click.echo(f"subcluster: {resolved_subcluster}")
    click.echo(f"repo-host: {repo_host}")
    if mode == "criado":
        click.echo(f"linhas: {counts['linhas']}")
    else:
        click.echo(
            f"props: {counts['sobrescritas']} sobrescritas, "
            f"{counts['adicionadas']} adicionadas, "
            f"{counts['preservadas_humanas']} props humanas preservadas"
        )
