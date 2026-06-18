#!/usr/bin/env python3
"""Sub-tool determinístico de /wiki-compile (meta-bridge skill).

Responsabilidades minimal (per ADR-017 § decomposição faceta ii + plano Onda 2
do roadmap knowledge layer block-first F4 reduzido):

1. find-or-create section na entity page com ordem canonical preservada
2. literal append no fim da seção alvo
3. dedup por conteúdo (probe via match exato)

Substância heurística (decidir o que agregar) fica na skill `/wiki-compile`;
este sub-tool é write engine determinístico — recebe content pronto, faz
positioning + dedup, escreve.

Não faz: parsing semântico, inferência de seção, mutação de properties
page-level, rewrite de id::, fallback defensivo.

Invariantes upstream (per logseq-notes ADR-003 SD3 + meta-bridge ADR-001 SD2):
- ordem canonical: Notas curadas → Sources digeridas → Síntese
- literal append (NÃO block-ref resolvido em runtime — block-ref `((id))` chega
  inline no --content do caller)

Uso:
    compile.py --entity-page <path> --section "<header>" --content "<markdown>"

Exit codes:
- 0: agregado OR já presente (idempotência)
- 1: erro (path inexistente, args inválidos, falha de write)
"""

import argparse
import sys
from pathlib import Path

SECTION_ORDER = ["Notas curadas", "Sources digeridas", "Síntese"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="wiki-compile sub-tool determinístico")
    p.add_argument("--entity-page", required=True, help="Path absoluto da entity page")
    p.add_argument("--section", required=True, help="Header da seção alvo (ex: 'Notas curadas')")
    p.add_argument("--content", required=True, help="Markdown literal a inserir")
    return p.parse_args()


def validate(args: argparse.Namespace) -> Path:
    page = Path(args.entity_page).expanduser()
    if not page.exists():
        sys.stderr.write(f"entity-page não existe: {page}\n")
        sys.exit(1)
    if args.section not in SECTION_ORDER:
        sys.stderr.write(
            f"section inválida: '{args.section}' — valores aceitos: {SECTION_ORDER}\n"
        )
        sys.exit(1)
    if not args.content.strip():
        sys.stderr.write("content vazio — recusa\n")
        sys.exit(1)
    return page


def find_section_bounds(lines: list[str], section: str) -> tuple[int, int] | None:
    """Retorna (start_line, end_line) inclusive da seção, ou None se ausente.

    start_line aponta pra header `## <section>`; end_line aponta pra última
    linha de conteúdo da seção (antes do próximo `## ` ou EOF).
    """
    header = f"## {section}"
    start = None
    for idx, line in enumerate(lines):
        if line.rstrip() == header:
            start = idx
            break
    if start is None:
        return None
    # Encontrar fim: próximo `## ` ou EOF
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            return (start, idx - 1)
    return (start, len(lines) - 1)


def find_insert_position(lines: list[str], section: str) -> int:
    """Posição pra inserir nova seção preservando ordem canonical.

    Ordem de probe:
    1. Procura primeira seção canonical posterior existente — insere antes dela.
    2. Senão, procura última seção canonical anterior existente — insere após o fim dela.
    3. Senão, insere após page-level properties + linha em branco (fallback).
    """
    target_idx = SECTION_ORDER.index(section)
    # (1) próxima seção posterior existente
    for later_section in SECTION_ORDER[target_idx + 1 :]:
        bounds = find_section_bounds(lines, later_section)
        if bounds is not None:
            return bounds[0]
    # (2) última seção anterior existente
    for earlier_section in reversed(SECTION_ORDER[:target_idx]):
        bounds = find_section_bounds(lines, earlier_section)
        if bounds is not None:
            return bounds[1] + 1
    # (3) fallback: após page-level properties block
    for idx, line in enumerate(lines):
        if "::" in line:
            continue
        if line.strip() == "" and idx > 0:
            return idx + 1
    return len(lines)


def ensure_section(lines: list[str], section: str) -> tuple[list[str], tuple[int, int]]:
    """Garante seção existe; retorna (lines_modificadas, bounds_da_seção)."""
    bounds = find_section_bounds(lines, section)
    if bounds is not None:
        return lines, bounds
    insert_at = find_insert_position(lines, section)
    new_section_lines = [f"## {section}\n", "\n"]
    new_lines = lines[:insert_at] + new_section_lines + lines[insert_at:]
    new_bounds = (insert_at, insert_at + 1)
    return new_lines, new_bounds


def content_already_present(lines: list[str], bounds: tuple[int, int], content: str) -> bool:
    """Dedup por match exato — content é multi-line; comparar bloco-a-bloco."""
    section_body = "".join(lines[bounds[0] : bounds[1] + 1])
    return content.rstrip() in section_body


def append_to_section(
    lines: list[str], bounds: tuple[int, int], content: str
) -> list[str]:
    """Append literal no fim da seção (antes da próxima header ou EOF)."""
    insert_at = bounds[1] + 1
    content_lines = [l + "\n" for l in content.rstrip().split("\n")]
    # Garantir linha em branco antes do conteúdo se a seção termina sem uma
    prefix = []
    if bounds[1] >= bounds[0] and lines[bounds[1]].strip() != "":
        prefix = ["\n"]
    return lines[:insert_at] + prefix + content_lines + lines[insert_at:]


def main() -> int:
    args = parse_args()
    page = validate(args)
    raw = page.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)

    lines, bounds = ensure_section(lines, args.section)

    if content_already_present(lines, bounds, args.content):
        sys.stderr.write(f"dedup: conteúdo já presente em '## {args.section}' — no-op\n")
        # Persistir mesmo assim caso ensure_section tenha criado seção
        page.write_text("".join(lines), encoding="utf-8")
        return 0

    new_lines = append_to_section(lines, bounds, args.content)
    page.write_text("".join(new_lines), encoding="utf-8")
    sys.stderr.write(f"agregado em '## {args.section}'\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
