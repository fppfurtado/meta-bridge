from pathlib import Path

LOGSEQ_ROOT = Path.home() / "Notes" / "logseq"
JOURNALS_DIR = LOGSEQ_ROOT / "journals"
PAGES_DIR = LOGSEQ_ROOT / "pages"

# Write-path HTTP (ADR-003): config dedicado do token + endpoint da Logseq
# Local HTTP Server. Path canonical hardcoded como os demais runtime paths.
CONFIG_DIR = Path.home() / ".config" / "meta-bridge"
LOGSEQ_HTTP_CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_LOGSEQ_HTTP_ENDPOINT = "http://127.0.0.1:12315"


def journal_path(date_str: str) -> Path:
    return JOURNALS_DIR / f"{date_str}.md"


def page_path(basename: str) -> Path:
    return PAGES_DIR / f"{basename}.md"
