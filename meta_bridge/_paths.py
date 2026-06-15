from pathlib import Path

LOGSEQ_ROOT = Path.home() / "Notes" / "logseq"
JOURNALS_DIR = LOGSEQ_ROOT / "journals"
PAGES_DIR = LOGSEQ_ROOT / "pages"


def journal_path(date_str: str) -> Path:
    return JOURNALS_DIR / f"{date_str}.md"


def page_path(basename: str) -> Path:
    return PAGES_DIR / f"{basename}.md"
