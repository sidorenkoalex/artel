"""Сторож и запись автора коммитов (SPEC 01M6RB74H9BDTJAA5D2S4QPK1E): свойства вне долгоживущих файлов задачи.

Строка `project-commit-author-<проект>` есть только у хостинга с
конвейерами (GitLab), и `doctor --fix` для прочих хостингов `token_user` не
зовёт; `projects.set_commit_author` отказывает причиной, не завершая
процесс, на тех же рубежах, что `target-set`.
"""
from unittest import mock

import pytest

from orchestrator import config, doctor, projects, runner, targets
from orchestrator.doctor import project_checks
from tests.sandbox import artel_target_entry

NAME = "pgithub"


def test_guard_row_only_for_pipeline_hosting(monkeypatch):
    """Хостинг без конвейеров (GitHub) с `token_slot`: строки сторожа нет, `doctor --fix` владельца токена не спрашивает.

    Ловит мутацию: `commit_author_applies` не смотрит
    `forge.ci_by_pipeline` (строка и запрос `token_user` появляются у
    проекта GitHub).
    """
    entry = {"forge": "github", "token_slot": f"{NAME}-token"}
    calls = []
    monkeypatch.setattr(runner, "in_role_environment", lambda env=None: False)
    monkeypatch.setattr(doctor.forge, "ci_by_pipeline", lambda name: False)
    monkeypatch.setattr(doctor.forge, "token_user",
                        lambda name: calls.append(name))
    monkeypatch.setattr(doctor.targets, "load", lambda: {NAME: entry})
    assert project_checks.commit_author_checks(NAME, entry) == []
    project_checks.fix_commit_authors()
    assert calls == []


def test_set_commit_author_refuses_layer_with_comment(initialized_tmp_root):
    """Комментарий в локальном слое: `set_commit_author` возвращает причину `target-set`, файл побайтно прежний, процесс не завершается.

    Ловит мутацию: функция записи зовёт `_target_set_load` (его
    `sys.exit` роняет `doctor --fix`) или пересобирает файл с комментарием
    (комментарий стирается).
    """
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    lines = ["# заметка Оператора", "targets:", f"  {NAME}:", "    description:",
             f"      base: {config.MAIN_BRANCH}", "      test_profile:",
             "        command: [python3, -m, pytest]",
             "        long_lived_dir: tests",
             "        long_lived_name: test_<id>_<name>.py", "    policy:",
             "      no_paths: []", "      project_skills: []",
             "      merge_gate: target-human",
             "      weakening_scope: [tests/**/*.py]",
             "      mutation_claim_scope: [tests/test_*.py]",
             "    machine:", "      forge: gitlab",
             f"      url: https://localhost/team/{NAME}",
             f"      token_slot: {NAME}-token"]
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = path.read_bytes()
    with mock.patch("sys.exit", side_effect=AssertionError("sys.exit")):
        refusal, done = projects.set_commit_author(
            NAME, {"name": "bot", "email": "bot@localhost"})
    assert "комментарий" in refusal and done == ""
    assert path.read_bytes() == before


@pytest.mark.parametrize("name", [config.DEFAULT_TARGET, "absent"])
def test_set_commit_author_refuses_artel_and_missing_entry(initialized_tmp_root, name):
    """Запись артели или запись, которой нет в локальном слое: причина отказа, без завершения процесса.

    Ловит мутацию: рубежи `_target_set_load` потеряны при выносе в
    `_local_layer_for` (запись артели идёт в локальный слой) или
    возвращаются через `sys.exit`.
    """
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    with mock.patch("sys.exit", side_effect=AssertionError("sys.exit")):
        refusal, done = projects.set_commit_author(
            name, {"name": "bot", "email": "bot@localhost"})
    assert refusal and done == ""
