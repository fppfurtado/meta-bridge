"""mb journal-review — scan mecânico + write engine.

Per F2 design-reviewer absorption: heurísticas semânticas (task-closure,
task-zombie, bucket-underused, bucket-emerging) vivem na SKILL.md
`/journal-review`. CLI faz só:

1. **Scan mode** (default): resolve janela `--days N` ou `--from/--to`, scaneia
   journals, emite saída markdown estruturada com 4 seções (markers ativos,
   DONE tasks, narrativas, inventário de buckets). Skill consome pra análise.

2. **Apply mode** (`--apply`): lê transições in-place de stdin (mesmo formato
   de `mb journal-close` Transitions) e aplica. Skill compõe transições após
   análise semântica + cherry-pick do operador.

CLI permanece stateless. Toda decisão semântica é re-derivada pela skill em
cada invocação (per F2 contract).
"""

from __future__ import annotations

import datetime
import re
import sys
from collections import defaultdict
from pathlib import Path

import click
from rapidfuzz.distance import Levenshtein

from . import _paths, logseq, logseq_http
from .cli import cli, logseq_open
from .journal_close import (
    TRANSITION_RE,
    _decode_escapes,
    _close_transitions_via_http,
    apply_transition,
)
from .journal_note import bootstrap_journal, find_or_create_bucket
from .logseq_http import LogseqHTTPError, resolve_journal_tree


# Subset de markers GTD que o scan CLASSIFICA. CANCELLED (e demais do superset
# de logseq.GTD_MARKERS) é terminal mas não emitido na saída — cai como narrativa
# ou é ignorado (skill MD não consome), preservando o comportamento anterior.
SCAN_MARKERS = ("TODO", "DOING", "WAITING", "DONE")

# Structural apply payload parsing (per ADR-001 SD10 Adendo v0.4.0).
STRUCTURAL_HEADER_RE = re.compile(r"^## Structural\s*$")
ARCHIVED_SUBHEADER_RE = re.compile(r"^### Archived buckets\s*$")
EMERGING_SUBHEADER_RE = re.compile(r"^### Emerging buckets\s*$")
ARCHIVED_ENTRY_RE = re.compile(r"^- ([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+)$")
EMERGING_ENTRY_RE = re.compile(r"^- ([^|]+?)(?:\s*\|\s*(.+))?$")
ARCHIVED_PAGE_SECTION = "- ## Buckets arquivados"

# Hygiene apply payload parsing (per ADR-001 SD10 Adendo 2026-06-24 — trio v2).
HYGIENE_HEADER_RE = re.compile(r"^## Hygiene\s*$")
HYGIENE_SUB_RE = re.compile(r"^### (Co-occurrence|Rename-implicit|Naming-drift)\s*$")
HYGIENE_PAGE = "bucket-hygiene"

# Phantom-tag (heurística 8, SD15): #tag colada a delimitador de enclosure
# materializa phantom page no Logseq. Detecção determinística high-precision;
# #[[...]] fora de escopo (o `[` não está no charset → falso-negativo aceito).
# Tag exige ≥1 letra — exclui refs GitHub puramente-numéricas em prosa
# (`(#11)`, `(PR #83)`), que são notação GitHub, não intenção de tag Logseq.
PHANTOM_TAG_RE = re.compile(r"#([\w/-]*[a-zA-Z][\w/-]*)([)\]}])")
PHANTOM_HEADER_RE = re.compile(r"^## Phantom fixes\s*$")
# Phantom-fix tem 1 pipe → não casa TRANSITION_RE (2 pipes) no loop de
# run_apply_mode, logo nunca é reaplicada como transição. A direção reversa
# (linha de transição casaria PHANTOM_FIX_RE) é barrada pelo section-gating de
# parse_phantom — só lê linhas dentro de `## Phantom fixes`.
PHANTOM_FIX_RE = re.compile(r"^- (.+?):(\d+)\s*\|\s*(.+?)\s*$")


def resolve_window(
    days: int | None, from_: str | None, to: str | None
) -> list[datetime.date]:
    """Retorna lista de date objects pra janela. Validação mutual-exclusion
    via raise click.UsageError pra mensagem clara."""
    if days is not None and (from_ or to):
        raise click.UsageError("--days e --from/--to são mutuamente exclusivos")
    if (from_ and not to) or (to and not from_):
        raise click.UsageError("--from e --to exigem ambos")
    if from_ and to:
        try:
            d1 = datetime.date.fromisoformat(from_)
            d2 = datetime.date.fromisoformat(to)
        except ValueError:
            raise click.UsageError("--from/--to exigem YYYY-MM-DD")
        if d1 > d2:
            raise click.UsageError("--from > --to")
        span = (d2 - d1).days
        return [d1 + datetime.timedelta(days=i) for i in range(span + 1)]

    days_back = days if days is not None else 30
    if days_back < 0:
        raise click.UsageError("--days exige N >= 0")
    today = datetime.date.today()
    return [today - datetime.timedelta(days=i) for i in range(days_back + 1)][::-1]


def date_to_filename(d: datetime.date) -> str:
    return d.strftime("%Y_%m_%d")


def scan_journal(path: Path, date_iso: str) -> dict[str, list]:
    """Scan single journal — retorna dict com 4 listas:
    markers_open, dones, narratives, buckets (top-level encountered)."""
    out: dict[str, list] = {
        "markers_open": [],
        "dones": [],
        "narratives": [],
        "buckets": [],
    }
    if not path.exists():
        return out
    lines = path.read_text().splitlines()
    current_bucket: str | None = None

    def collect_sub_bullets(start_idx: int) -> list[str]:
        subs = []
        for j in range(start_idx + 1, len(lines)):
            if logseq.indent_level(lines[j])[0] >= 2:
                subs.append(lines[j])
            else:
                break
        return subs

    for i, line in enumerate(lines):
        level, rest = logseq.indent_level(line)
        if not logseq.is_bullet(rest):
            continue  # properties, blanks, non-bullets → ignorados

        if level == 0:
            tag = logseq.bucket_tag(logseq.bullet_text(rest))
            if tag:
                current_bucket = tag
                if tag not in out["buckets"]:
                    out["buckets"].append(tag)
            continue  # bullet top-level (bucket ou não) nunca é marker/narrativa

        if current_bucket is None or level != 1:
            continue  # markers/narrativas são só nível 1; nível ≥2 = sub_bullets

        text = logseq.bullet_text(rest)
        mk = logseq.parse_marker(text)
        if mk and mk[0] in SCAN_MARKERS:
            marker, content = mk
            if not content:
                continue  # marker sem corpo (`- TODO `) → ignorado (paridade c/ antigo)
            entry = {
                "path": str(path),
                "line": i + 1,
                "date": date_iso,
                "bucket": current_bucket,
                "marker": marker,
                "content": content,
                "sub_bullets": collect_sub_bullets(i),
            }
            if marker == "DONE":
                out["dones"].append(entry)
            else:  # TODO/DOING/WAITING
                out["markers_open"].append(entry)
            continue

        # narrativa: bullet nível 1 que não é marker do scan (inclui CANCELLED etc.)
        if text:
            out["narratives"].append(
                {
                    "path": str(path),
                    "line": i + 1,
                    "date": date_iso,
                    "bucket": current_bucket,
                    "content": text,
                }
            )
    return out


def emit_scan_output(
    window: list[datetime.date],
    journals_found: int,
    aggregate: dict[str, list],
) -> None:
    """Imprime markdown estruturado consumido pela SKILL.md.

    Entradas dentro de cada seção (Active markers / DONE tasks / Narratives)
    saem em **ordem cronológica ascendente** — heurística 1 da SKILL.md
    confia nessa ordem para identificar evidência posterior ao marker."""
    d1, dN = window[0], window[-1]
    click.echo(
        f"## journal-review scan (window {d1.isoformat()} to {dN.isoformat()}, "
        f"{journals_found} journals)\n"
    )

    click.echo("### Active markers\n")
    if aggregate["markers_open"]:
        for m in aggregate["markers_open"]:
            click.echo(
                f"- {m['path']}:{m['line']} | {m['date']} | #{m['bucket']} | "
                f"{m['marker']} {m['content']}"
            )
            for sb in m["sub_bullets"]:
                click.echo(f"  sub: {sb}")
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### DONE tasks\n")
    if aggregate["dones"]:
        for d in aggregate["dones"]:
            click.echo(
                f"- {d['path']}:{d['line']} | {d['date']} | #{d['bucket']} | "
                f"DONE {d['content']}"
            )
            for sb in d["sub_bullets"]:
                click.echo(f"  sub: {sb}")
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### Narratives\n")
    if aggregate["narratives"]:
        for n in aggregate["narratives"]:
            click.echo(
                f"- {n['path']}:{n['line']} | {n['date']} | #{n['bucket']} | "
                f"{n['content']}"
            )
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### Bucket inventory\n")
    bucket_data: dict[str, dict[str, int]] = defaultdict(
        lambda: {"journals": 0, "open_tasks": 0, "done_tasks": 0}
    )
    bucket_seen_per_journal: dict[str, set[str]] = defaultdict(set)
    for m in aggregate["markers_open"]:
        bucket_data[m["bucket"]]["open_tasks"] += 1
        bucket_seen_per_journal[m["bucket"]].add(m["date"])
    for d in aggregate["dones"]:
        bucket_data[d["bucket"]]["done_tasks"] += 1
        bucket_seen_per_journal[d["bucket"]].add(d["date"])
    for n in aggregate["narratives"]:
        bucket_seen_per_journal[n["bucket"]].add(n["date"])
    for bucket_name in aggregate["buckets_all"]:
        bucket_data[bucket_name]["journals"] = len(
            bucket_seen_per_journal[bucket_name]
        )
    # first/last-seen por bucket (header-based, cronológico) — consumido por
    # bucket-rename-implicit (SD10 Adendo 2026-06-24). buckets_per_journal vem
    # em ordem cronológica ascendente (window ordenada).
    bucket_first_last: dict[str, tuple[str, str]] = {}
    for date_iso, buckets in aggregate["buckets_per_journal"]:
        for b in buckets:
            if b not in bucket_first_last:
                bucket_first_last[b] = (date_iso, date_iso)
            else:
                bucket_first_last[b] = (bucket_first_last[b][0], date_iso)
    if bucket_data:
        for bucket_name in sorted(bucket_data):
            d = bucket_data[bucket_name]
            fl = bucket_first_last.get(bucket_name)
            fl_str = f" | first: {fl[0]} last: {fl[1]}" if fl else ""
            click.echo(
                f"- #{bucket_name} | journals: {d['journals']} | "
                f"open_tasks: {d['open_tasks']} | done_tasks: {d['done_tasks']}{fl_str}"
            )
    else:
        click.echo("_(none)_")


def compute_candidates(
    aggregate: dict[str, list],
    cooccur_min: int,
    namedrift_max: int,
    rename_gap: int,
) -> dict[str, list]:
    """Geração DETERMINÍSTICA de candidatos das heurísticas v2 (SD10 Adendo
    2026-06-24). Mecânica pura — o judgment semântico (fusão-faz-sentido,
    rename-plausível, escolha de canonical) fica na SKILL.md que consome estes
    candidatos. Espelha o padrão de 2c (CLI conta, skill julga).

    Retorna dict com 3 listas:
    - cooccurrence: [(A, B, shared)] — pares com ≥ cooccur_min journals compartilhados.
    - naming_drift: [(A, B, distance)] — Levenshtein ≤ namedrift_max E ranges
      coexistem (sobrepõem). Discriminado de rename por co-presença temporal.
    - rename_implicit: [(A, last_date, [orphan_refs], [successors])] — bucket A
      com tasks órfãs (markers abertos) + sucessores (gap ≥ rename_gap journals após
      A sumir). A escolha do sucessor plausível fica pra skill por similaridade
      SEMÂNTICA (não léxica — ex.: weekly-review→journal-review tem Levenshtein grande).
    """
    bpj = aggregate["buckets_per_journal"]  # [(date, [buckets])] cronológico
    first_pos: dict[str, int] = {}
    last_pos: dict[str, int] = {}
    last_date: dict[str, str] = {}
    for idx, (date_iso, buckets) in enumerate(bpj):
        for b in buckets:
            first_pos.setdefault(b, idx)
            last_pos[b] = idx
            last_date[b] = date_iso
    names = sorted(first_pos)

    cooccurrence: list[tuple[str, str, int]] = []
    naming_drift: list[tuple[str, str, int]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            shared = sum(1 for _, bk in bpj if a in bk and b in bk)
            if shared >= cooccur_min:
                cooccurrence.append((a, b, shared))
            # rapidfuzz com weights=(1,1,1) default ≡ custo unitário do DP caseiro
            # anterior (ins/del/sub = 1); naming-drift é léxico-determinístico.
            dist = Levenshtein.distance(a, b)
            coexist = first_pos[a] <= last_pos[b] and first_pos[b] <= last_pos[a]
            if 0 < dist <= namedrift_max and coexist:
                naming_drift.append((a, b, dist))

    orphans_by_bucket: dict[str, list[str]] = defaultdict(list)
    for m in aggregate["markers_open"]:
        orphans_by_bucket[m["bucket"]].append(f"{m['path']}:{m['line']}")
    rename_implicit: list[tuple[str, str, list[str], list[str]]] = []
    for a in names:
        orphans = orphans_by_bucket.get(a)
        if not orphans:
            continue
        successors = [
            b for b in names if b != a and first_pos[b] - last_pos[a] >= rename_gap
        ]
        if successors:
            rename_implicit.append((a, last_date[a], orphans, successors))

    return {
        "cooccurrence": cooccurrence,
        "naming_drift": naming_drift,
        "rename_implicit": rename_implicit,
    }


def emit_candidates(candidates: dict[str, list]) -> None:
    """Imprime as 3 seções de candidatos v2 (mecânicas) consumidas pela SKILL.md."""
    click.echo()
    click.echo("### Co-occurrence candidates\n")
    if candidates["cooccurrence"]:
        for a, b, shared in candidates["cooccurrence"]:
            click.echo(f"- #{a} #{b} | shared-journals: {shared}")
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### Naming-drift candidates\n")
    if candidates["naming_drift"]:
        for a, b, dist in candidates["naming_drift"]:
            click.echo(f"- #{a} #{b} | distance: {dist}")
    else:
        click.echo("_(none)_")
    click.echo()

    click.echo("### Rename-implicit candidates\n")
    if candidates["rename_implicit"]:
        for a, last, orphans, successors in candidates["rename_implicit"]:
            succ = " ".join(f"#{s}" for s in successors)
            click.echo(
                f"- #{a} | last: {last} | orphans: {';'.join(orphans)} | successors: {succ}"
            )
    else:
        click.echo("_(none)_")


def detect_phantom_tags(path: Path) -> list[dict]:
    """Detecta `#tag` colada (sem whitespace) a delimitador de enclosure
    `)`/`]`/`}` — materializa phantom page no Logseq (heurística 8, SD15).

    Determinístico high-precision. `#[[...]]` fica fora de escopo (o `[` não
    está no charset do regex → falso-negativo aceito, deferido a backlog).
    Retorna lista de dicts (path, line, raw, tag). Arquivo ausente → vazio.
    """
    out: list[dict] = []
    if not path.exists():
        return out
    for i, line in enumerate(path.read_text().splitlines()):
        for m in PHANTOM_TAG_RE.finditer(line):
            out.append(
                {
                    "path": str(path),
                    "line": i + 1,
                    "raw": m.group(0),
                    "tag": m.group(1),
                }
            )
    return out


def emit_phantom_candidates(phantom: list[dict]) -> None:
    """Imprime a seção `### Phantom-tag candidates` consumida pela SKILL.md."""
    click.echo()
    click.echo("### Phantom-tag candidates\n")
    if phantom:
        for p in phantom:
            click.echo(f"- {p['path']}:{p['line']} | {p['raw']} | #{p['tag']}")
    else:
        click.echo("_(none)_")


def parse_phantom(raw: str) -> list[dict]:
    """Parse seção `## Phantom fixes` do payload stdin.

    Format:
        ## Phantom fixes
        - <path>:<line> | <raw-match>

    `<raw-match>` é o texto literal colado (ex.: `#foo)`). Section ausente →
    lista vazia. 2 campos (1 pipe) — não colide com TRANSITION_RE.
    """
    entries: list[dict] = []
    in_section = False
    for line in raw.splitlines():
        if PHANTOM_HEADER_RE.match(line):
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            in_section = False
            continue
        if not in_section:
            continue
        m = PHANTOM_FIX_RE.match(line)
        if m:
            entries.append(
                {
                    "path": m.group(1).strip(),
                    "line": int(m.group(2)),
                    "raw": m.group(3).strip(),
                }
            )
    return entries


def apply_phantom(entries: list[dict]) -> tuple[int, int, list[str]]:
    """Insere espaço antes do delimitador: `#tag)` → `#tag )` (in-place).

    Transformação uniforme em prosa e `{{query}}` (per SD15 — fix mínimo mata a
    phantom page sem reclassificar tag→page-ref). Idempotente: o espaço quebra o
    re-match do regex, então `raw` já-corrigido não é encontrado na linha → skip.
    Fail-soft: arquivo inexistente ou `raw` ausente na linha (drift) → skip.
    """
    if not entries:
        return 0, 0, []
    applied = 0
    skipped = 0
    msgs: list[str] = []
    by_path: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_path[e["path"]].append(e)
    for path_str, ents in by_path.items():
        path = Path(path_str)
        if not path.exists():
            skipped += len(ents)
            continue
        lines = path.read_text().splitlines()
        changed = False
        for e in ents:
            idx = e["line"] - 1
            raw = e["raw"]
            fixed = raw[:-1] + " " + raw[-1]
            if 0 <= idx < len(lines) and raw in lines[idx]:
                lines[idx] = lines[idx].replace(raw, fixed, 1)
                applied += 1
                changed = True
                msgs.append(f"{path.name}:{e['line']} {raw} → {fixed}")
            else:
                skipped += 1
        if changed:
            path.write_text("\n".join(lines) + "\n")
    return applied, skipped, msgs


def parse_structural(raw: str) -> tuple[list[dict], list[dict]]:
    """Parse seção `## Structural` do payload stdin.

    Format:
        ## Structural
        ### Archived buckets
        - bucket-name | categoria-page | path:line;path:line
        ### Emerging buckets
        - canonical-name | origem-fonte (opcional)

    Retorna (archived_entries, emerging_entries). Cada entry é dict.
    Section ausente → ambos vazios.
    """
    archived: list[dict] = []
    emerging: list[dict] = []
    in_structural = False
    current_sub: str | None = None
    for line in raw.splitlines():
        if STRUCTURAL_HEADER_RE.match(line):
            in_structural = True
            current_sub = None
            continue
        if line.startswith("## ") and in_structural:
            # Saiu da seção Structural pra outra ## section
            in_structural = False
            current_sub = None
            continue
        if not in_structural:
            continue
        if ARCHIVED_SUBHEADER_RE.match(line):
            current_sub = "archived"
            continue
        if EMERGING_SUBHEADER_RE.match(line):
            current_sub = "emerging"
            continue
        if current_sub == "archived":
            m = ARCHIVED_ENTRY_RE.match(line)
            if m:
                bucket = m.group(1).strip()
                categoria = m.group(2).strip()
                refs_raw = m.group(3).strip()
                refs = [r.strip() for r in refs_raw.split(";") if r.strip()]
                archived.append(
                    {"bucket": bucket, "categoria": categoria, "refs": refs}
                )
        elif current_sub == "emerging":
            m = EMERGING_ENTRY_RE.match(line)
            if m:
                canonical = m.group(1).strip()
                origem = (m.group(2) or "").strip() or None
                emerging.append({"canonical": canonical, "origem": origem})
    return archived, emerging


def apply_archived_bucket(
    bucket: str, categoria: str, refs: list[str]
) -> tuple[bool, str]:
    """Append archived bucket entry em pages/<categoria>.md.

    Idempotente: bucket name já presente em qualquer linha da page → no-op
    (escopo amplo intencional — evita duplicar mesmo que a menção anterior
    seja narrativa fora da seção arquivados).
    Fail-soft: refs com path inexistente são skipped (warning no motivo);
    entry é gravada com refs válidos restantes. Zero refs válidos → entry
    ainda é gravada (apenas o nome do bucket).
    """
    page = _paths.page_path(categoria)
    bucket_marker = f"#{bucket}"
    if page.exists():
        existing = page.read_text()
        bucket_word_re = re.compile(
            rf"(?:^|[\s])#{re.escape(bucket)}(?:$|[\s])", re.MULTILINE
        )
        if bucket_word_re.search(existing):
            return False, f"bucket {bucket_marker} já mencionado em pages/{categoria}.md"
        lines = existing.splitlines()
    else:
        lines = []

    valid_refs: list[str] = []
    skipped_refs: list[str] = []
    for ref in refs:
        m = re.match(r"^(.+?):(\d+)$", ref)
        if m and Path(m.group(1)).exists():
            valid_refs.append(ref)
        else:
            skipped_refs.append(ref)

    # Find-or-create section `- ## Buckets arquivados`
    section_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == ARCHIVED_PAGE_SECTION.strip():
            section_idx = idx
            break
    if section_idx is None:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(ARCHIVED_PAGE_SECTION)
        section_idx = len(lines) - 1

    # Avança enquanto for child indent ou blank entre children; para antes
    # da próxima top-level (linha não-tab non-blank — outra `- ##` seção, etc.).
    insert_at = section_idx + 1
    while insert_at < len(lines) and (
        lines[insert_at].startswith("\t") or lines[insert_at] == ""
    ):
        if lines[insert_at] == "" and insert_at + 1 < len(lines) and not lines[insert_at + 1].startswith("\t"):
            break
        insert_at += 1

    new_block = [f"\t- {bucket_marker}"]
    for ref in valid_refs:
        new_block.append(f"\t\t- {ref}")
    lines[insert_at:insert_at] = new_block
    page.write_text("\n".join(lines) + "\n")

    msg = f"appended {bucket_marker} → pages/{categoria}.md ({len(valid_refs)} refs"
    if skipped_refs:
        msg += f", {len(skipped_refs)} skipped: {','.join(skipped_refs)}"
    msg += ")"
    return True, msg


def apply_emerging_bucket(canonical: str, origem: str | None) -> tuple[bool, str]:
    """Find-or-create bucket #<canonical> no journal de hoje (forward-only).

    Reusa `find_or_create_bucket` de journal_note. Bootstrap journal se ausente.
    Idempotente: bucket existente → find-or-create é no-op + sub-bullet origem
    é gravado uma única vez (dedup por igualdade textual).
    """
    today_iso = datetime.date.today().isoformat()
    today_filename = today_iso.replace("-", "_")
    journal = _paths.journal_path(today_filename)

    if not journal.exists():
        bootstrap_journal(journal)

    bucket_idx = find_or_create_bucket(journal, canonical)

    if origem:
        lines = journal.read_text().splitlines()
        origem_line = f"\t- (origem: {origem})"
        # Para no próximo top-level (linha não-tab) — sub-bullets de buckets
        # subsequentes não devem contaminar dedup deste bucket.
        already = False
        for j in range(bucket_idx + 1, len(lines)):
            if not lines[j].startswith("\t"):
                break
            if lines[j].strip() == origem_line.strip():
                already = True
                break
        if not already:
            lines.insert(bucket_idx + 1, origem_line)
            journal.write_text("\n".join(lines) + "\n")

    suffix = f" (origem: {origem})" if origem else ""
    return True, f"#{canonical} em {journal.name}{suffix}"


def parse_hygiene(raw: str) -> list[tuple[str, str]]:
    """Parse seção `## Hygiene` do payload stdin → lista de (tipo, sugestão).

    Format:
        ## Hygiene
        ### Co-occurrence
        - <texto da sugestão>
        ### Rename-implicit
        - <texto da sugestão>
        ### Naming-drift
        - <texto da sugestão>

    `tipo` é um dos headings de HYGIENE_SUB_RE. Section ausente → lista vazia.
    """
    entries: list[tuple[str, str]] = []
    in_hygiene = False
    current_type: str | None = None
    for line in raw.splitlines():
        if HYGIENE_HEADER_RE.match(line):
            in_hygiene = True
            current_type = None
            continue
        if line.startswith("## ") and in_hygiene:
            # Saiu da seção Hygiene pra outra ## section
            in_hygiene = False
            current_type = None
            continue
        if not in_hygiene:
            continue
        sm = HYGIENE_SUB_RE.match(line)
        if sm:
            current_type = sm.group(1)
            continue
        if current_type and line.startswith("- "):
            suggestion = line[2:].strip()
            if suggestion:
                entries.append((current_type, suggestion))
    return entries


def apply_hygiene(entries: list[tuple[str, str]]) -> tuple[int, int, list[str]]:
    """Append sugestões de higiene em pages/bucket-hygiene.md (forward-only).

    Page structure (Logseq outline):
        - ## Co-occurrence
        \t- <sugestão>
        - ## Rename-implicit
        \t- <sugestão>
        - ## Naming-drift
        \t- <sugestão>

    Find-or-create por seção de tipo. Idempotente: sugestão (match textual
    exato de linha) já presente em **qualquer** seção da page → skip (escopo
    global intencional, paralelo a apply_archived_bucket — sugestões carregam
    o nome do bucket, colisão de texto cross-tipo é pathológica). **Forward-only**
    — nunca toca journals históricos (read-mostly per SD10 Adendo; órfãs do
    rename-implicit entram como evidência na sugestão, não como transição).
    """
    if not entries:
        return 0, 0, []
    page = _paths.page_path(HYGIENE_PAGE)
    lines = page.read_text().splitlines() if page.exists() else []
    applied = 0
    skipped = 0
    msgs: list[str] = []
    for type_heading, suggestion in entries:
        sug_stripped = f"- {suggestion}"
        if any(line.strip() == sug_stripped for line in lines):
            skipped += 1
            continue
        section_marker = f"- ## {type_heading}"
        section_idx = next(
            (i for i, line in enumerate(lines) if line.strip() == section_marker),
            None,
        )
        if section_idx is None:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(section_marker)
            section_idx = len(lines) - 1
        insert_at = section_idx + 1
        while insert_at < len(lines) and lines[insert_at].startswith("\t"):
            insert_at += 1
        lines.insert(insert_at, f"\t- {suggestion}")
        applied += 1
        msgs.append(f"{type_heading}: {suggestion[:60]}")
    if applied:
        page.write_text("\n".join(lines) + "\n")
    return applied, skipped, msgs


def _parse_apply_payload(raw: str) -> tuple[list, list, list, list, list]:
    """Parse do payload stdin de `--apply` → (transitions, archived, emerging,
    hygiene, phantom). Compartilhado entre o file-direct `run_apply_mode` e o
    path HTTP — fonte única, evita divergência de parsing/erro entre os dois.

    TRANSITION_RE casa toda linha independente de seção; entries archived/emerging
    têm 3+/2 campos sem `:linha`, não colidem. Contrato forward (Bloco 4): a skill
    compõe `## Hygiene` SEM o shape `<path>:<linha> | <a> | <b>` (usa page-refs).
    """
    transitions: list[tuple[str, int, str, str]] = []
    for line in raw.splitlines():
        m = TRANSITION_RE.match(line)
        if m:
            transitions.append(
                (
                    m.group(1).strip(),
                    int(m.group(2)),
                    _decode_escapes(m.group(3)),
                    _decode_escapes(m.group(4)),
                )
            )
    archived, emerging = parse_structural(raw)
    hygiene = parse_hygiene(raw)
    phantom = parse_phantom(raw)
    return transitions, archived, emerging, hygiene, phantom


def _echo_apply_empty_error() -> None:
    """Mensagem de erro de payload vazio/inválido — compartilhada file-direct/HTTP."""
    click.echo(
        "--apply: nenhuma transição nem entry structural/hygiene/phantom parseável (stdin vazio ou formato inválido). Formatos:",
        err=True,
    )
    click.echo("  - <path>:<line> | <before> | <after>", err=True)
    click.echo("  ## Structural / ### Archived buckets / - bucket | categoria | refs", err=True)
    click.echo("  ## Structural / ### Emerging buckets / - canonical | origem", err=True)
    click.echo("  ## Hygiene / ### Co-occurrence|Rename-implicit|Naming-drift / - sugestão", err=True)
    click.echo("  ## Phantom fixes / - <path>:<line> | <raw-match>", err=True)


def _iter_block_contents(tree: list):
    """Itera recursivamente o `content` de todos os blocos da árvore Logseq.

    Base dos guards de idempotência HTTP de archived/hygiene — paridade barata
    com o match textual contra a page inteira do file-direct.
    """
    for block in tree:
        if not isinstance(block, dict):
            continue
        yield block.get("content", "")
        yield from _iter_block_contents(block.get("children") or [])


def _find_block_containing(tree: list, substr: str) -> tuple[str, str] | None:
    """Retorna (uuid, content) do primeiro bloco cujo content contenha `substr`.

    Recursivo (testa children). Usado pelo phantom HTTP path para localizar o
    bloco a corrigir sem depender do número de linha (indisponível na API).
    """
    for block in tree:
        if not isinstance(block, dict):
            continue
        content = block.get("content", "")
        if substr in content:
            return block.get("uuid"), content
        found = _find_block_containing(block.get("children") or [], substr)
        if found:
            return found
    return None


def _run_apply_via_http(
    transitions: list[tuple[str, int, str, str]],
    archived: list[dict],
    emerging: list[dict],
    hygiene: list[tuple[str, str]],
    phantom: list[dict],
) -> None:
    """Apply mode via Logseq HTTP API. LogseqHTTPError propaga para o caller."""
    # 1. Transitions — idêntico ao journal_close HTTP path
    applied_tr, skipped_tr = _close_transitions_via_http(transitions)
    if transitions:
        click.echo(f"transitions: {applied_tr} aplicadas, {len(skipped_tr)} skipped")
        for path_str, lineno, motivo in skipped_tr:
            click.echo(f"  skipped {path_str}:{lineno} — {motivo}", err=True)

    # 2. Archived buckets — find-or-create por categoria + refs como sub-bullets
    #    (paridade com apply_archived_bucket: refs path:line válidos viram filhos).
    #    Idempotente: #bucket já mencionado na page → skip. A estrutura de seção
    #    `## Buckets arquivados` é YAGNI no HTTP path (append flat).
    if archived:
        applied_arch = 0
        skipped_arch = 0
        cat_contents: dict[str, list[str]] = {}
        for entry in archived:
            categoria = entry["categoria"]
            bucket = entry["bucket"]
            if categoria not in cat_contents:
                cat_contents[categoria] = list(
                    _iter_block_contents(logseq_http.get_page_blocks_tree(categoria))
                )
            bucket_re = re.compile(rf"(?:^|\s)#{re.escape(bucket)}(?:$|\s)")
            if any(bucket_re.search(c) for c in cat_contents[categoria]):
                skipped_arch += 1
                continue
            result = logseq_http.append_block_in_page(categoria, f"#{bucket}")
            bucket_uuid = result.get("uuid") if isinstance(result, dict) else None
            if bucket_uuid:
                # refs path:line válidos (arquivo existe) viram filhos — mesma
                # validação fail-soft do file-direct (refs inválidos são dropados).
                for ref in entry.get("refs") or []:
                    m = re.match(r"^(.+?):(\d+)$", ref)
                    if m and Path(m.group(1)).exists():
                        logseq_http.insert_block(bucket_uuid, ref, sibling=False)
            cat_contents[categoria].append(f"#{bucket}")
            applied_arch += 1
            click.echo(f"  archived: #{bucket} → {categoria}")
        click.echo(f"structural: {applied_arch} archived, {skipped_arch} dedup-skipped (HTTP)")

    # 3. Emerging buckets — find-or-create no journal de hoje + sub-bullet origem
    #    (paridade com apply_emerging_bucket). find_or_create_bucket_block robusto
    #    ao journal inexistente; origem idempotente (não re-insere se já presente).
    if emerging:
        today_filename = datetime.date.today().strftime("%Y_%m_%d")
        journal_path = str(_paths.journal_path(today_filename))
        applied_emerg = 0
        for entry in emerging:
            canonical = entry["canonical"]
            origem = entry.get("origem")
            page_name, bucket = logseq_http.find_or_create_bucket_block(journal_path, canonical)
            if page_name is None:
                raise LogseqHTTPError(
                    f"não foi possível derivar nome de página para {journal_path!r}."
                )
            if bucket is None:
                raise LogseqHTTPError(f"falha ao criar/encontrar bucket #{canonical} em {page_name!r}.")
            if origem:
                origem_content = f"(origem: {origem})"
                children = [
                    c.get("content", "") for c in (bucket.get("children") or []) if isinstance(c, dict)
                ]
                if origem_content not in children:
                    logseq_http.insert_block(bucket["uuid"], origem_content, sibling=False)
            applied_emerg += 1
            click.echo(f"  emerging: #{canonical} em {page_name}")
        click.echo(f"structural: {applied_emerg} emerging (HTTP)")

    # 4. Hygiene — append flat por entry. Idempotente: sugestão (match exato) já
    #    presente → skip (paridade com apply_hygiene). Section structure por tipo
    #    é YAGNI no HTTP path.
    if hygiene:
        applied_hyg = 0
        skipped_hyg = 0
        existing_hyg = set(
            _iter_block_contents(logseq_http.get_page_blocks_tree(HYGIENE_PAGE))
        )
        for _, suggestion in hygiene:
            if suggestion in existing_hyg:
                skipped_hyg += 1
                continue
            logseq_http.append_block_in_page(HYGIENE_PAGE, suggestion)
            existing_hyg.add(suggestion)
            applied_hyg += 1
        click.echo(f"hygiene: {applied_hyg} sugestões aplicadas, {skipped_hyg} dedup-skipped (HTTP)")

    # 5. Phantom fixes — substring match em content do bloco + update
    if phantom:
        applied_ph = 0
        skipped_ph = 0
        by_path: dict[str, list[dict]] = defaultdict(list)
        for e in phantom:
            by_path[e["path"]].append(e)
        for path_str, ents in by_path.items():
            p = Path(path_str).expanduser()
            # Journal (stem YYYY_MM_DD) → resolve por journal-day; page → None,
            # cai no path relativo a PAGES_DIR.
            ph_page, ph_tree = resolve_journal_tree(str(p))
            if ph_page is None:
                try:
                    ph_page = str(p.relative_to(_paths.PAGES_DIR))[:-3]
                except ValueError:
                    skipped_ph += len(ents)
                    continue
                ph_tree = logseq_http.get_page_blocks_tree(ph_page) or []
            if not ph_tree:
                skipped_ph += len(ents)
                continue
            for e in ents:
                raw = e["raw"]
                fixed = raw[:-1] + " " + raw[-1]
                result = _find_block_containing(ph_tree, raw)
                if result is None:
                    skipped_ph += 1
                    continue
                uuid, block_content = result
                logseq_http.update_block(uuid, block_content.replace(raw, fixed, 1))
                applied_ph += 1
        click.echo(f"phantom: {applied_ph} fixes aplicados ({skipped_ph} skipped)")


def run_apply_mode() -> None:
    """Read payload from stdin (transitions + optional structural/hygiene), apply.

    Payload supports:
    - `- <path>:<line> | <before> | <after>` (legacy task-level transitions)
    - `## Structural` section with `### Archived buckets` + `### Emerging buckets`
      (apply estrutural per ADR-001 SD10 Adendo v0.4.0)
    - `## Hygiene` section with `### Co-occurrence`/`### Rename-implicit`/
      `### Naming-drift` (apply aditivo forward-only per SD10 Adendo 2026-06-24)
    """
    raw = sys.stdin.read()
    transitions, archived, emerging, hygiene, phantom = _parse_apply_payload(raw)

    if not transitions and not archived and not emerging and not hygiene and not phantom:
        _echo_apply_empty_error()
        sys.exit(1)

    # Transitions primeiro (preserva semântica v0.3.0), structural depois
    applied_tr = 0
    skipped_tr: list[tuple[str, int, str]] = []
    for path_str, lineno, before, after in transitions:
        ok, motivo = apply_transition(Path(path_str), lineno, before, after)
        if ok:
            applied_tr += 1
        else:
            skipped_tr.append((path_str, lineno, motivo))

    applied_arch = 0
    skipped_arch: list[tuple[str, str]] = []
    for entry in archived:
        ok, motivo = apply_archived_bucket(
            entry["bucket"], entry["categoria"], entry["refs"]
        )
        if ok:
            applied_arch += 1
            click.echo(f"  archived: {motivo}")
        else:
            skipped_arch.append((entry["bucket"], motivo))

    applied_emerg = 0
    skipped_emerg: list[tuple[str, str]] = []
    for entry in emerging:
        ok, motivo = apply_emerging_bucket(entry["canonical"], entry["origem"])
        if ok:
            applied_emerg += 1
            click.echo(f"  emerging: {motivo}")
        else:
            skipped_emerg.append((entry["canonical"], motivo))

    applied_hyg, skipped_hyg, hyg_msgs = apply_hygiene(hygiene)
    for msg in hyg_msgs:
        click.echo(f"  hygiene: {msg}")

    applied_ph, skipped_ph, ph_msgs = apply_phantom(phantom)
    for msg in ph_msgs:
        click.echo(f"  phantom: {msg}")

    if transitions:
        click.echo(
            f"transitions: {applied_tr} aplicadas, {len(skipped_tr)} skipped"
        )
        for path_str, lineno, motivo in skipped_tr:
            click.echo(f"  skipped {path_str}:{lineno} — {motivo}", err=True)
    if archived or emerging:
        click.echo(
            f"structural: {applied_arch} archived + {applied_emerg} emerging"
            f" ({len(skipped_arch) + len(skipped_emerg)} skipped)"
        )
        for bucket, motivo in skipped_arch:
            click.echo(f"  skipped archived #{bucket} — {motivo}", err=True)
        for canonical, motivo in skipped_emerg:
            click.echo(f"  skipped emerging #{canonical} — {motivo}", err=True)
    if hygiene:
        click.echo(
            f"hygiene: {applied_hyg} sugestões aplicadas ({skipped_hyg} skipped)"
        )
    if phantom:
        click.echo(
            f"phantom: {applied_ph} fixes aplicados ({skipped_ph} skipped)"
        )


@cli.command("journal-review")
@click.option("--days", type=int, default=None, help="Janela retroativa (default 30 se nem --from/--to).")
@click.option("--from", "from_", type=str, default=None, help="Início da janela YYYY-MM-DD.")
@click.option("--to", "to", type=str, default=None, help="Fim da janela YYYY-MM-DD.")
@click.option("--apply", "apply_mode", is_flag=True, default=False, help="Apply mode: lê transições de stdin.")
@click.option("--cooccur-min-journals", type=int, default=2, help="Threshold N de bucket-co-occurrence (default 2).")
@click.option("--namedrift-max-distance", type=int, default=2, help="Threshold D (Levenshtein) de bucket-naming-drift (default 2).")
@click.option("--rename-gap-journals", type=int, default=2, help="Threshold G (gap) de bucket-rename-implicit (default 2).")
def journal_review_cmd(
    days: int | None,
    from_: str | None,
    to: str | None,
    apply_mode: bool,
    cooccur_min_journals: int,
    namedrift_max_distance: int,
    rename_gap_journals: int,
) -> None:
    """Scan mecânico de markers/DONE/narrativas/buckets + candidatos v2 em janela; apply via stdin."""
    if apply_mode:
        if logseq_open():
            try:
                raw = sys.stdin.read()
                transitions, archived, emerging, hygiene, phantom = _parse_apply_payload(raw)
                if not transitions and not archived and not emerging and not hygiene and not phantom:
                    _echo_apply_empty_error()
                    sys.exit(1)
                _run_apply_via_http(transitions, archived, emerging, hygiene, phantom)
            except LogseqHTTPError as exc:
                click.echo(
                    f"Logseq HTTP error — fechar o Logseq ou verificar o Local HTTP Server.\n{exc}",
                    err=True,
                )
                sys.exit(1)
            return
        run_apply_mode()
        return

    window = resolve_window(days, from_, to)

    aggregate: dict[str, list] = {
        "markers_open": [],
        "dones": [],
        "narratives": [],
        "buckets_all": [],
        "buckets_per_journal": [],
    }
    phantom: list[dict] = []
    journals_found = 0
    for d in window:
        fname = date_to_filename(d)
        path = _paths.journal_path(fname)
        if not path.exists():
            continue
        journals_found += 1
        phantom.extend(detect_phantom_tags(path))
        scanned = scan_journal(path, d.isoformat())
        aggregate["markers_open"].extend(scanned["markers_open"])
        aggregate["dones"].extend(scanned["dones"])
        aggregate["narratives"].extend(scanned["narratives"])
        for b in scanned["buckets"]:
            if b not in aggregate["buckets_all"]:
                aggregate["buckets_all"].append(b)
        aggregate["buckets_per_journal"].append((d.isoformat(), scanned["buckets"]))

    if journals_found == 0:
        click.echo(
            f"nenhum journal encontrado na janela "
            f"{window[0].isoformat()} a {window[-1].isoformat()}.",
            err=True,
        )
        sys.exit(0)

    # Pages: scan full-dir (sem janela temporal — per SD15). Recursivo cobre
    # subdirs canonical (sources/, namespaces). Custo full-dir aceito sem cap.
    for page in sorted(_paths.PAGES_DIR.rglob("*.md")):
        phantom.extend(detect_phantom_tags(page))

    emit_scan_output(window, journals_found, aggregate)
    candidates = compute_candidates(
        aggregate,
        cooccur_min_journals,
        namedrift_max_distance,
        rename_gap_journals,
    )
    emit_candidates(candidates)
    emit_phantom_candidates(phantom)
