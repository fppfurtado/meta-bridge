"""Tests para skills/inbox-aggregate/sub-tools/inbox_aggregate.py.

Cobertura per ADR-002 § Decisão 6 Adendo (critério parsing-complexo → pytest)
e planos inbox-agregador-fase-1 + inbox-captura-universal-non-task:

- Cenário 1: parse_forge_issues — happy path e edge cases (empty title, no iid)
- Cenário 2: parse_pkm_tasks — adição de #pkm-native; preservação quando já presente
- Cenário 3: dedup exact-match — empty existing, partial overlap, case-insensitive
- Cenário 4: read_bucket_children — bucket presente/ausente; filhos em profundidade 2+
- Cenário 5: find_or_create_bucket + insert_tasks_after_bucket — criação e posicionamento
- Cenário 6 (edge case a): task idêntica Forge + PKM-native → dedup remove duplicata
- Cenário 7 (edge case b): #inbox em sub-bullet profundidade 2+ capturado;
                            top-level '- #inbox' bucket filtrado (não conta como filho)
- Cenário 8: main() E2E via tmp_path — write ao journal, idempotência, journal criado
- Cenário 9: parse_pkm_non_tasks — bloco sem marker, linhas vazias filtradas
- Cenário 10: dedup cross-type — task e non-task com mesmo conteúdo após strip de marker
- Cenário 11: main() E2E com non-tasks — mix task+non-task, Papel 1 filtrado no caller
"""
import importlib.util
import json
from pathlib import Path

import pytest

SUB_TOOL_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "inbox-aggregate"
    / "sub-tools"
    / "inbox_aggregate.py"
)
_spec = importlib.util.spec_from_file_location("inbox_aggregate", SUB_TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_forge_issues = _mod.parse_forge_issues
parse_pkm_tasks = _mod.parse_pkm_tasks
parse_pkm_non_tasks = _mod.parse_pkm_non_tasks
dedup = _mod.dedup
normalize = _mod.normalize
content_key = _mod.content_key
read_bucket_children = _mod.read_bucket_children
find_or_create_bucket = _mod.find_or_create_bucket
insert_tasks_after_bucket = _mod.insert_tasks_after_bucket
main = _mod.main


def _invoke_main(tmp_path, monkeypatch, journal_content, forge_issues, pkm_tasks, pkm_non_tasks=None):
    """Invoca main() in-process via monkeypatch de sys.argv; retorna (rc, result, journal)."""
    journal = tmp_path / "journal.md"
    if journal_content is not None:
        journal.write_text(journal_content, encoding="utf-8")
    argv = [
        "inbox_aggregate.py",
        "--journal",
        str(journal),
        "--forge-issues",
        json.dumps(forge_issues),
        "--pkm-tasks",
        json.dumps(pkm_tasks),
    ]
    if pkm_non_tasks is not None:
        argv += ["--pkm-non-tasks", json.dumps(pkm_non_tasks)]
    monkeypatch.setattr("sys.argv", argv)
    import io
    import sys as _sys

    captured = io.StringIO()
    monkeypatch.setattr(_sys, "stdout", captured)
    rc = main()
    result = json.loads(captured.getvalue()) if captured.getvalue().strip() else {}
    journal_text = journal.read_text(encoding="utf-8") if journal.exists() else ""
    return rc, result, journal_text


# ---------- Cenário 1: parse_forge_issues ----------


def test_cenario_1_happy_path():
    issues = [{"iid": 5, "title": "Fix auth bug"}]
    tasks = parse_forge_issues(issues, "#pje-2.1")
    assert tasks == [{"line": "\t- TODO Fix auth bug (#5)  #inbox #pje-2.1", "type": "forge"}]


def test_cenario_1_multiple_issues():
    issues = [
        {"iid": 5, "title": "Fix auth bug"},
        {"iid": 12, "title": "Update schema"},
    ]
    tasks = parse_forge_issues(issues, "#scripts-judiciais")
    assert len(tasks) == 2
    assert all(t["type"] == "forge" for t in tasks)
    assert "#scripts-judiciais" in tasks[0]["line"]
    assert "#12" in tasks[1]["line"]


def test_cenario_1_empty_title_skipped():
    issues = [{"iid": 5, "title": ""}, {"iid": 6, "title": "Valid task"}]
    tasks = parse_forge_issues(issues, "#pje-2.1")
    assert len(tasks) == 1
    assert "Valid task" in tasks[0]["line"]


def test_cenario_1_no_iid_no_suffix():
    issues = [{"title": "Task sem iid"}]
    tasks = parse_forge_issues(issues, "#pje-2.1")
    assert tasks == [{"line": "\t- TODO Task sem iid  #inbox #pje-2.1", "type": "forge"}]


# ---------- Cenário 2: parse_pkm_tasks ----------


def test_cenario_2_adds_pkm_native_tag():
    lines = ["\t- TODO revisar PR de ontem  #inbox"]
    tasks = parse_pkm_tasks(lines)
    assert tasks[0]["type"] == "pkm_task"
    assert "#pkm-native" in tasks[0]["line"]


def test_cenario_2_preserves_existing_pkm_native():
    lines = ["\t- TODO tarefa  #inbox #pkm-native"]
    tasks = parse_pkm_tasks(lines)
    assert tasks[0]["line"].count("#pkm-native") == 1


def test_cenario_2_skips_empty_lines():
    lines = ["", "\t- TODO tarefa  #inbox", ""]
    tasks = parse_pkm_tasks(lines)
    assert len(tasks) == 1


def test_cenario_2_strips_trailing_whitespace():
    lines = ["\t- TODO tarefa  #inbox   "]
    tasks = parse_pkm_tasks(lines)
    assert not tasks[0]["line"].endswith("   ")


# ---------- Cenário 3: dedup ----------


def test_cenario_3_empty_existing_passes_all():
    tasks = [
        {"line": "\t- TODO task A  #inbox #pje-2.1", "type": "forge"},
        {"line": "\t- TODO task B  #inbox #pje-2.1", "type": "forge"},
    ]
    assert dedup(tasks, set()) == tasks


def test_cenario_3_partial_overlap():
    existing = {content_key("\t- TODO task A  #inbox #pje-2.1")}
    tasks = [
        {"line": "\t- TODO task A  #inbox #pje-2.1", "type": "forge"},
        {"line": "\t- TODO task B  #inbox #pje-2.1", "type": "forge"},
    ]
    result = dedup(tasks, existing)
    assert len(result) == 1
    assert "task B" in result[0]["line"]


def test_cenario_3_all_duplicates_filtered():
    task = {"line": "\t- TODO task A  #inbox #pje-2.1", "type": "forge"}
    existing = {content_key(task["line"])}
    assert dedup([task], existing) == []


def test_cenario_3_case_insensitive():
    existing = {content_key("\t- TODO TASK A  #inbox #pje-2.1")}
    tasks = [{"line": "\t- TODO task a  #inbox #pje-2.1", "type": "forge"}]
    assert dedup(tasks, existing) == []


def test_cenario_3_no_intra_list_duplicates():
    task = {"line": "\t- TODO same  #inbox #pje-2.1", "type": "forge"}
    result = dedup([task, task], set())
    assert len(result) == 1


# ---------- Cenário 4: read_bucket_children ----------


def test_cenario_4_bucket_absent():
    lines = ["- #meta-system\n", "\t- Sessão\n"]
    children, idx = read_bucket_children(lines)
    assert children == []
    assert idx is None


def test_cenario_4_bucket_with_tasks():
    lines = [
        "- #inbox\n",
        "\t- TODO task A  #inbox #pje-2.1\n",
        "\t- TODO task B  #inbox #scripts-judiciais\n",
    ]
    children, idx = read_bucket_children(lines)
    assert idx == 0
    assert len(children) == 2
    assert "task A" in children[0]


def test_cenario_4_bucket_followed_by_other_bucket():
    lines = [
        "- #inbox\n",
        "\t- TODO task A  #inbox #pje-2.1\n",
        "- #meta-system\n",
    ]
    children, _ = read_bucket_children(lines)
    assert len(children) == 1
    assert "task A" in children[0]


def test_cenario_4_blank_lines_inside_bucket_skipped():
    lines = [
        "- #inbox\n",
        "\t- TODO task A  #inbox #pje-2.1\n",
        "\n",
        "\t- TODO task B  #inbox #scripts-judiciais\n",
    ]
    children, _ = read_bucket_children(lines)
    assert len(children) == 2


# ---------- Cenário 5: find_or_create_bucket + insert_tasks_after_bucket ----------


def test_cenario_5_creates_bucket_when_absent():
    lines = ["- #meta-system\n", "\t- nota\n"]
    new_lines, idx = find_or_create_bucket(lines)
    assert "- #inbox\n" in new_lines
    assert new_lines[idx] == "- #inbox\n"


def test_cenario_5_finds_existing_bucket():
    lines = ["- #inbox\n", "\t- TODO task  #inbox #pje-2.1\n"]
    new_lines, idx = find_or_create_bucket(lines)
    assert idx == 0
    assert new_lines == lines


def test_cenario_5_insert_tasks_no_existing_children():
    lines = ["- #inbox\n", "- #meta-system\n"]
    _, idx = find_or_create_bucket(lines)
    result = insert_tasks_after_bucket(lines, idx, ["\t- TODO new  #inbox #pje-2.1"])
    assert "\t- TODO new  #inbox #pje-2.1\n" in result
    inbox_pos = result.index("- #inbox\n")
    task_pos = result.index("\t- TODO new  #inbox #pje-2.1\n")
    assert task_pos == inbox_pos + 1


def test_cenario_5_insert_tasks_after_existing_children():
    lines = [
        "- #inbox\n",
        "\t- TODO existing  #inbox #pje-2.1\n",
        "- #meta-system\n",
    ]
    _, idx = find_or_create_bucket(lines)
    result = insert_tasks_after_bucket(lines, idx, ["\t- TODO new  #inbox #scripts-judiciais"])
    existing_pos = result.index("\t- TODO existing  #inbox #pje-2.1\n")
    new_pos = result.index("\t- TODO new  #inbox #scripts-judiciais\n")
    assert new_pos > existing_pos


# ---------- Cenário 6 (edge case a): task idêntica Forge + PKM-native ----------


def test_cenario_6_forge_and_pkm_native_different_source_tags_both_pass():
    """Forge (#pje-2.1) + PKM-native (#pkm-native) com mesma task content → 2 entradas.

    Dedup semântico cross-fonte é YAGNI per ADR-004 SD3 — operador consolida manualmente.
    Source tags diferem → content_key diferentes → exact-match não remove.
    """
    forge_task = {"line": "\t- TODO Fix auth bug (#5)  #inbox #pje-2.1", "type": "forge"}
    pkm_task = parse_pkm_tasks(["\t- TODO Fix auth bug (#5)  #inbox"])[0]
    assert pkm_task["line"] != forge_task["line"]  # source tags diferentes
    result = dedup([forge_task, pkm_task], set())
    assert len(result) == 2


def test_cenario_6_exact_same_string_intra_list_deduped():
    """String EXATAMENTE igual aparecendo duas vezes na lista → deduplicada para 1."""
    task = {"line": "\t- TODO Fix auth bug (#5)  #inbox #pje-2.1", "type": "forge"}
    result = dedup([task, task], set())
    assert len(result) == 1


# ---------- Cenário 7 (edge case b): profundidade 2+ vs top-level bucket ----------


def test_cenario_7_sub_bullet_depth_2_captured():
    """Task #inbox em sub-bullet profundidade 2 (2 tabs) é capturada como filha."""
    lines = [
        "- #inbox\n",
        "\t- TODO depth1  #inbox #pje-2.1\n",
        "\t\t- TODO depth2  #inbox #pkm-native\n",
    ]
    children, _ = read_bucket_children(lines)
    assert len(children) == 2
    assert any("depth2" in c for c in children)


def test_cenario_7_top_level_bucket_not_counted_as_child():
    """'- #inbox' top-level (Papel 1) não é contado como filho do próprio bucket."""
    lines = ["- #inbox\n"]
    children, bucket_idx = read_bucket_children(lines)
    assert bucket_idx == 0
    assert children == []


def test_cenario_7_top_level_bucket_excluded_from_dedup_pool():
    """Bucket line '- #inbox' não entra no pool de dedup via content_key."""
    lines = ["- #inbox\n", "\t- TODO task A  #inbox #pje-2.1\n"]
    children, _ = read_bucket_children(lines)
    existing_pool = {content_key(t) for t in children}
    assert content_key("- #inbox") not in existing_pool


# ---------- Cenário 8: main() E2E ----------


def test_cenario_8_main_writes_to_journal(tmp_path, monkeypatch):
    forge = {"#pje-2.1": [{"iid": 5, "title": "Fix auth bug"}]}
    pkm = ["\t- TODO revisar PR  #inbox"]
    rc, result, journal_text = _invoke_main(tmp_path, monkeypatch, None, forge, pkm)
    assert rc == 0
    assert result["count_new"] == 2
    assert "Fix auth bug" in journal_text
    assert "revisar PR" in journal_text
    assert "#pkm-native" in journal_text
    assert "- #inbox" in journal_text


def test_cenario_8_idempotencia(tmp_path, monkeypatch):
    """Segunda invocação não duplica tasks já presentes."""
    forge = {"#pje-2.1": [{"iid": 5, "title": "Fix auth bug"}]}
    rc1, r1, _ = _invoke_main(tmp_path, monkeypatch, None, forge, [])
    assert rc1 == 0
    assert r1["count_new"] == 1

    monkeypatch.undo()
    rc2, r2, journal_text = _invoke_main(
        tmp_path, monkeypatch, (tmp_path / "journal.md").read_text(), forge, []
    )
    assert rc2 == 0
    assert r2["count_new"] == 0
    assert journal_text.count("Fix auth bug") == 1


def test_cenario_8_empty_forge_and_pkm(tmp_path, monkeypatch):
    rc, result, journal_text = _invoke_main(tmp_path, monkeypatch, None, {}, [])
    assert rc == 0
    assert result["count_new"] == 0
    assert journal_text == ""


def test_cenario_8_existing_journal_with_other_buckets(tmp_path, monkeypatch):
    """Journal com outros buckets preservados; tasks adicionadas ao bucket #inbox."""
    existing = "- #meta-system\n\t- nota qualquer\n"
    forge = {"#scripts-judiciais": [{"iid": 10, "title": "Update parser"}]}
    rc, result, journal_text = _invoke_main(tmp_path, monkeypatch, existing, forge, [])
    assert rc == 0
    assert "- #meta-system" in journal_text
    assert "Update parser" in journal_text
    assert result["count_new"] == 1


def test_cenario_8_result_has_type_field(tmp_path, monkeypatch):
    """JSON de saída inclui type por item (forge/pkm_task/pkm_non_task)."""
    forge = {"#pje-2.1": [{"iid": 1, "title": "Issue F"}]}
    pkm = ["\t- TODO Task PKM  #inbox"]
    rc, result, _ = _invoke_main(tmp_path, monkeypatch, None, forge, pkm)
    assert rc == 0
    types = {t["type"] for t in result["tasks"]}
    assert "forge" in types
    assert "pkm_task" in types


def test_cenario_8_count_pkm_backward_compat(tmp_path, monkeypatch):
    """count_pkm permanece como total pkm_task + pkm_non_task para backward compat."""
    pkm = ["\t- TODO T  #inbox"]
    non_tasks = ["\t- nota de captura  #inbox"]
    rc, result, _ = _invoke_main(tmp_path, monkeypatch, None, {}, pkm, non_tasks)
    assert rc == 0
    assert result["count_pkm"] == result["count_pkm_task"] + result["count_pkm_non_task"]
    assert result["count_pkm_task"] == 1
    assert result["count_pkm_non_task"] == 1


# ---------- Cenário 9: parse_pkm_non_tasks ----------


def test_cenario_9_non_task_parsed():
    lines = ["\t- nota de captura rápida  #inbox"]
    result = parse_pkm_non_tasks(lines)
    assert len(result) == 1
    assert result[0]["type"] == "pkm_non_task"
    assert result[0]["line"] == "\t- nota de captura rápida  #inbox"


def test_cenario_9_empty_lines_filtered():
    lines = ["", "\t- nota  #inbox", ""]
    result = parse_pkm_non_tasks(lines)
    assert len(result) == 1


def test_cenario_9_trailing_whitespace_stripped():
    lines = ["\t- nota  #inbox   "]
    result = parse_pkm_non_tasks(lines)
    assert not result[0]["line"].endswith("   ")


def test_cenario_9_multiple_non_tasks():
    lines = ["\t- nota A  #inbox", "\t- nota B  #inbox #insight"]
    result = parse_pkm_non_tasks(lines)
    assert len(result) == 2
    assert all(r["type"] == "pkm_non_task" for r in result)


# ---------- Cenário 10: dedup cross-type task == non-task ----------


def test_cenario_10_task_and_non_task_same_content_deduped():
    """TODO prefix é stripped no content_key: task e non-task com mesmo conteúdo → 1 entrada."""
    task = {"line": "\t- TODO nota de captura  #inbox #pkm-native", "type": "pkm_task"}
    non_task = {"line": "\t- nota de captura  #inbox #pkm-native", "type": "pkm_non_task"}
    result = dedup([task, non_task], set())
    assert len(result) == 1
    assert result[0] is task  # primeiro vence


def test_cenario_10_non_task_already_in_bucket_blocks_task():
    """Non-task já no bucket bloqueia task incoming com mesmo conteúdo."""
    existing_line = "\t- nota de captura  #inbox #pkm-native"
    existing_pool = {content_key(existing_line)}
    task = {"line": "\t- TODO nota de captura  #inbox #pkm-native", "type": "pkm_task"}
    result = dedup([task], existing_pool)
    assert result == []


def test_cenario_10_task_already_in_bucket_blocks_non_task():
    """Task já no bucket bloqueia non-task incoming com mesmo conteúdo."""
    existing_line = "\t- TODO nota de captura  #inbox #pkm-native"
    existing_pool = {content_key(existing_line)}
    non_task = {"line": "\t- nota de captura  #inbox #pkm-native", "type": "pkm_non_task"}
    result = dedup([non_task], existing_pool)
    assert result == []


def test_cenario_10_different_source_tags_not_deduped():
    """Task com #pje-2.1 e non-task com #pkm-native → conteúdos distintos, ambas passam."""
    task = {"line": "\t- TODO Fix bug  #inbox #pje-2.1", "type": "forge"}
    non_task = {"line": "\t- Fix bug  #inbox #pkm-native", "type": "pkm_non_task"}
    result = dedup([task, non_task], set())
    assert len(result) == 2


# ---------- Cenário 11: main() E2E com non-tasks ----------


def test_cenario_11_non_task_written_to_journal(tmp_path, monkeypatch):
    """Non-task block com #inbox é escrito no bucket #inbox do journal."""
    non_tasks = ["\t- ideia sobre refactor do gate  #inbox #insight"]
    rc, result, journal_text = _invoke_main(tmp_path, monkeypatch, None, {}, [], non_tasks)
    assert rc == 0
    assert result["count_new"] == 1
    assert result["count_pkm_non_task"] == 1
    assert "ideia sobre refactor do gate" in journal_text
    assert "- #inbox" in journal_text


def test_cenario_11_mix_task_and_non_task(tmp_path, monkeypatch):
    """Mix de forge issue + pkm task + non-task → todos escritos, counts corretos."""
    forge = {"#pje-2.1": [{"iid": 3, "title": "Fix API"}]}
    pkm = ["\t- TODO tarefa pkm  #inbox"]
    non_tasks = ["\t- nota de captura  #inbox"]
    rc, result, journal_text = _invoke_main(tmp_path, monkeypatch, None, forge, pkm, non_tasks)
    assert rc == 0
    assert result["count_new"] == 3
    assert result["count_forge"] == 1
    assert result["count_pkm_task"] == 1
    assert result["count_pkm_non_task"] == 1
    assert "Fix API" in journal_text
    assert "tarefa pkm" in journal_text
    assert "nota de captura" in journal_text


def test_cenario_11_papel1_top_level_excluded_by_caller():
    """Papel 1 top-level '- #inbox' não entra em pkm_non_tasks — filtrado pelo grep do SKILL.md.

    O SKILL.md usa '^\t+' (1+ tabs) para o grep de non-tasks, excluindo '- #inbox'
    top-level (sem tabs). Este teste documenta que parse_pkm_non_tasks aceita a linha
    se passar mas o filtro é responsabilidade do caller (grep), não do sub-tool.
    A invariante real é que '- #inbox' sem tabs NÃO aparece no --pkm-non-tasks arg.
    """
    non_tasks = ["\t- nota indentada  #inbox"]  # indentada — passaria pelo grep
    top_level_bucket = "- #inbox"  # NÃO indentada — filtrada pelo grep ANTES de chegar aqui
    result = parse_pkm_non_tasks(non_tasks)
    assert len(result) == 1
    assert top_level_bucket not in result[0]["line"]


def test_cenario_11_idempotencia_non_task(tmp_path, monkeypatch):
    """Segunda invocação com mesma non-task não duplica."""
    non_tasks = ["\t- nota captura  #inbox #insight"]
    rc1, r1, _ = _invoke_main(tmp_path, monkeypatch, None, {}, [], non_tasks)
    assert rc1 == 0
    assert r1["count_new"] == 1

    monkeypatch.undo()
    rc2, r2, journal_text = _invoke_main(
        tmp_path, monkeypatch, (tmp_path / "journal.md").read_text(), {}, [], non_tasks
    )
    assert rc2 == 0
    assert r2["count_new"] == 0
    assert journal_text.count("nota captura") == 1
