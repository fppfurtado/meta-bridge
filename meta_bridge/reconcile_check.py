"""meta_bridge.reconcile_check — verify-state cross-store em load-time (read-only).

Faceta A do reconciler (#46, ADR-001 SD17). Surfa inconsistências cross-store na
abertura de sessão **antes de orientar**, reusando o primitivo verify-state-
before-materialize (toolkit ADR-069) em load-time. **Read-only:** emite findings
JSON; não muta o grafo (escrita é a faceta C, #48) — por isso sem gate `pgrep`.

3 checks v0:
- `journal_forge_closed`: task aberta (`TODO`/`DOING`/`WAITING`/`NOW`/`LATER`) em
  bucket Forge-synced (`#<repo>`, ou `#inbox` tagueada `#<repo>`) carregando
  `(#<iid>)` cuja issue está fechada — candidato a reconciliar.
- `notes_encerrada`: entry de NOTES.md com o marcador `Encerrada YYYY-MM-DD` no
  início de um bullet/linha — não re-orientar para ela.
- `cross_store_dedup` (faceta B, #47, ADR-001 SD18): item de pendência
  co-rastreado em ≥2 stores — entry de NOTES cujo título casa (exact + fuzzy
  `rapidfuzz`) uma task GTD aberta do journal. Materializa o componente dedup do
  contrato cross-store ADR-025. **v0 read-only local-first:** só os 2 stores
  locais (NOTES + Journal); as legs forge (`stale_cross_ref`/`NOTES↔Forge`) e o
  dedup canônico Journal↔Forge via listing ficam deferidos (forma do dado de iid
  em NOTES não-travada + listing fora da disciplina targeted). `canonical_ssot`
  por heurística barata derivada do próprio dado — task com `(#<iid>)` → Forge
  (forge-synced, confirmado); sem iid → Journal (SSOT default; NOTES é scratch
  non-SSOT per ADR-054). Nunca afirma Forge para item não-confirmado.

**Decomposição mecânico/judgment (ADR-002, padrão `inbox_aggregate`):** o
subcomando é puramente determinístico — recebe as issues fechadas via
`--closed-issues` (JSON); a **skill `/reconcile`** orquestra o fetch forge
(forge-auto-detect → `gh`/`glab`). Sem subprocess aqui — toda a heterogeneidade
de forge (gh vs glab) e a degradação graciosa vivem na skill. Match por `(#<iid>)`
(drift-proof); o iid vem do suffix que entries Forge-synced carregam (SD14).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import click
from rapidfuzz.distance import Levenshtein

from . import logseq
from .cli import cli

_IID_RE = re.compile(r"\(#(\d+)\)")
_HASHTAG_RE = re.compile(r"#([a-z0-9.-]+)")
# Marcador deliberado: início de bullet/linha (tolera `- `, `**` de bold), não
# menção incidental em prosa no meio da linha.
_ENCERRADA_RE = re.compile(r"^[\t ]*[-*]?\s*\*{0,2}Encerrada (\d{4}-\d{2}-\d{2})")
# Markers "abertos" (não-resolvidos) — task já DONE/CANCELLED não vira finding.
_OPEN_MARKERS = {"TODO", "DOING", "WAITING", "NOW", "LATER"}
_INBOX = "inbox"

# Dedup cross-store (faceta B): header de entry de NOTES + prefixo de data
# canonical (`## YYYY-MM-DD — <título>`, tolerando —/–/-) a remover do título.
_NOTES_HEADER_RE = re.compile(r"^## (.+)$")
_NOTES_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*[—–-]\s*")
# Similaridade normalizada (0..1) mínima pro fallback fuzzy — conservador pra
# evitar falso-positivo de duplicata. Calibração contra dado real é pendência.
_DEDUP_FUZZY_THRESHOLD = 0.85


def _iter_tasks(block: logseq.Block):
    """Yield recursivamente os blocos descendentes que têm marker GTD."""
    for child in block.children:
        if child.marker:
            yield child
        yield from _iter_tasks(child)


def check_journal_forge_closed(
    blocks: list[logseq.Block], closed_by_repo: dict[str, list[int]]
) -> list[dict]:
    """Findings de tasks abertas em bucket Forge-synced cuja issue está fechada.

    `closed_by_repo`: `{"<repo>": [<iid>, ...]}` — issues fechadas por repo,
    fornecidas pela skill. Em bucket `#<repo>` o repo é o próprio bucket; em
    `#inbox` o repo é a hashtag inline que casa uma chave conhecida (SD14).
    """
    closed_sets = {repo: set(iids) for repo, iids in closed_by_repo.items()}
    findings: list[dict] = []
    for block in blocks:
        bucket = block.bucket
        if bucket is None:
            continue
        for task in _iter_tasks(block):
            if task.marker not in _OPEN_MARKERS:
                continue
            iid_m = _IID_RE.search(task.text)
            if not iid_m:
                continue
            iid = int(iid_m.group(1))
            if bucket == _INBOX:
                repos = [h for h in _HASHTAG_RE.findall(task.content) if h in closed_sets]
            elif bucket in closed_sets:
                repos = [bucket]
            else:
                repos = []
            for repo in repos:
                if iid in closed_sets[repo]:
                    findings.append(
                        {
                            "check": "journal_forge_closed",
                            "repo": repo,
                            "iid": iid,
                            "task": task.text,
                        }
                    )
                    break
    return findings


def check_notes_encerrada(notes_text: str) -> list[dict]:
    """Findings (um por entry) de NOTES.md marcadas `Encerrada YYYY-MM-DD`."""
    findings: list[dict] = []
    seen_headers: set[str] = set()
    current_header = "(sem header)"
    for line in notes_text.splitlines():
        if line.startswith("## "):
            current_header = line[3:].strip()
        m = _ENCERRADA_RE.match(line)
        if m and current_header not in seen_headers:
            seen_headers.add(current_header)
            findings.append(
                {"check": "notes_encerrada", "entry": current_header, "date": m.group(1)}
            )
    return findings


def _norm_title(text: str) -> str:
    """Normaliza um título pro match cross-store: sem o suffix `(#<iid>)`,
    minúsculas, whitespace colapsado."""
    return " ".join(_IID_RE.sub("", text).lower().split())


def _notes_titles(notes_text: str) -> list[str]:
    """Títulos das entries de NOTES (headers `## [<data> —] <título>`), sem o
    prefixo de data canonical."""
    titles: list[str] = []
    for line in notes_text.splitlines():
        m = _NOTES_HEADER_RE.match(line)
        if m:
            titles.append(_NOTES_DATE_PREFIX_RE.sub("", m.group(1).strip()).strip())
    return titles


def check_cross_store_dedup(blocks: list[logseq.Block], notes_text: str) -> list[dict]:
    """Findings de item co-rastreado em ≥2 stores (NOTES + Journal) — faceta B.

    v0 read-only local-first (ADR-001 SD18, materializa o dedup de ADR-025): casa
    tasks GTD **abertas** do journal (sob bucket) contra headers de entries de
    NOTES por título (exact + fallback fuzzy `rapidfuzz`). `canonical_ssot` por
    heurística barata derivada do próprio dado — task com `(#<iid>)` → Forge
    (forge-synced, confirmado); sem iid → Journal (SSOT default; NOTES é sempre
    scratch non-SSOT per ADR-054). Nunca afirma Forge p/ item não-confirmado (F7).
    Puramente local — sem forge/listing/cluster-lookup. Um finding por task
    (primeiro match de NOTES basta — evita ruído).
    """
    norm_notes = [(t, _norm_title(t)) for t in _notes_titles(notes_text) if t.strip()]
    if not norm_notes:
        return []

    findings: list[dict] = []
    for block in blocks:
        if block.bucket is None:
            continue
        for task in _iter_tasks(block):
            if task.marker not in _OPEN_MARKERS:
                continue
            task_norm = _norm_title(task.content)
            if not task_norm:
                continue
            has_iid = bool(_IID_RE.search(task.text))
            for raw_note, note_norm in norm_notes:
                if note_norm == task_norm:
                    match = "exact"
                elif Levenshtein.normalized_similarity(task_norm, note_norm) >= _DEDUP_FUZZY_THRESHOLD:
                    match = "fuzzy"
                else:
                    continue
                findings.append(
                    {
                        "check": "cross_store_dedup",
                        "severity": "info",
                        "item": task.content,
                        "canonical_ssot": "Forge" if has_iid else "Journal",
                        "evidence": {
                            "journal_task": task.text,
                            "journal_bucket": block.bucket,
                            "notes_entry": raw_note,
                            "match": match,
                        },
                    }
                )
                break
    return findings


@cli.command("reconcile-check")
@click.option("--journal", required=True, type=click.Path(), help="Path do journal a checar.")
@click.option(
    "--notes",
    type=click.Path(),
    default=None,
    help="Path do NOTES.md (default: .claude/local/NOTES.md no cwd).",
)
@click.option(
    "--closed-issues",
    default="{}",
    help='JSON {"<repo>": [<iid>, ...]} de issues fechadas (skill fornece via forge-auto-detect).',
)
def reconcile_check(journal: str, notes: str | None, closed_issues: str) -> None:
    """[read-only] Surfa inconsistências cross-store na abertura (verify-state em load-time)."""
    try:
        closed_by_repo: dict[str, list[int]] = json.loads(closed_issues)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--closed-issues JSON inválido: {exc}")

    findings: list[dict] = []
    checks_run: list[str] = []
    checks_skipped: list[str] = []

    journal_path = Path(journal).expanduser()
    blocks: list[logseq.Block] | None = None
    if journal_path.exists():
        _, blocks = logseq.parse_document(journal_path.read_text(encoding="utf-8"))
        if closed_by_repo:
            findings.extend(check_journal_forge_closed(blocks, closed_by_repo))
            checks_run.append("journal_forge_closed")
        else:
            # failure-open: sem dados de issue fechada (forge indisponível / skill
            # não passou) → pula Check 1, Check 2 local ainda roda.
            checks_skipped.append("journal_forge_closed (sem --closed-issues)")
    else:
        checks_skipped.append("journal_forge_closed (journal ausente)")

    notes_path = (
        Path(notes).expanduser()
        if notes
        else Path.cwd() / ".claude" / "local" / "NOTES.md"
    )
    notes_text: str | None = None
    if notes_path.exists():
        notes_text = notes_path.read_text(encoding="utf-8")
        findings.extend(check_notes_encerrada(notes_text))
        checks_run.append("notes_encerrada")
    else:
        checks_skipped.append("notes_encerrada (NOTES.md ausente)")

    # Check 3 (faceta B): dedup cross-store local — exige journal E NOTES (ambos
    # locais; sem forge/listing). Roda sempre que os 2 stores existem.
    if blocks is not None and notes_text is not None:
        findings.extend(check_cross_store_dedup(blocks, notes_text))
        checks_run.append("cross_store_dedup")
    else:
        missing = "journal" if blocks is None else "NOTES"
        checks_skipped.append(f"cross_store_dedup ({missing} ausente)")

    click.echo(
        json.dumps(
            {"findings": findings, "checks_run": checks_run, "checks_skipped": checks_skipped},
            ensure_ascii=False,
        )
    )
