"""Юнит-тесты ветко-корректного чтения ANSWER/QUESTIONS (SPEC T075):
`orchestrator/fsm.py::_answer_file_count` и `orchestrator/brief.py`
(`_answer_component`/`_questions_component`/`_latest_answer_rel`) на
чужой ветке (`gitcmd.on_foreign_branch` истинно) — обычный продовый
путь после T048 (докстрины обеих функций), но ни один тест первой
итерации диффа его не задевал: все использовали заглушку
`gitcmd.git = fake_git` (`tests/test_answer_gate.py`,
`tests/test_brief.py::AnswerComponentTest`,
`tasks/T075/acceptance_tests/_sandbox.py`), при которой
`on_foreign_branch` всегда ложно (REVIEW T075 итерация 1, замечание
major).

Реальный git, тем же приёмом, что `tests.sandbox.RealGitSandbox` (T089) —
сам предмет проверки (расхождение диска и ветки) заглушкой не изобразить.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import brief, config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

ANSWER_MD = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

## Ответы

Раунд {n}: OK.
"""

QUESTIONS_MD = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Вопрос?** — варианты: A) да; B) нет — дефолт: A.
"""


class _AnswerRealGitSandbox(RealGitSandbox):
    """Надстройка над общей `sandbox.RealGitSandbox`, нужная только этому
    файлу: ветка задачи заведена отдельно и main её не чекаутит —
    `on_foreign_branch(self.branch)` истинно с самого начала теста, ничего
    дополнительно готовить не надо."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.branch = "task/t001-vetko-korrektnoe-chtenie"
        self.checkout(self.branch, create=True)
        self.checkout(config.MAIN_BRANCH)

    def commit_on_branch(self, name: str, template: str, n: int = 1) -> None:
        """Пишет и коммитит артефакт ПРЯМО на ветку задачи — main (и
        `self.root` на диске) остаётся без него, тем же приёмом, что
        `write_on_task_branch` в `tests/test_fsm_branch_correct_status_
        reads.py`."""
        self.checkout(self.branch)
        d = self.root / "tasks" / self.TASK
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(template.format(task=self.TASK, n=n),
                              encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", name)
        self.checkout(config.MAIN_BRANCH)


class AnswerFileCountOnForeignBranchTest(_AnswerRealGitSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.create_schema(self.conn)
        store.insert_task(self.conn, self.TASK, "Задача", "spec_writing",
                          self.branch, config.DEFAULT_TARGET, 25.0)

    def test_counts_answer_files_from_the_branch_not_the_disk(self):
        self.commit_on_branch("ANSWER-1.md", ANSWER_MD, 1)
        self.commit_on_branch("ANSWER-2.md", ANSWER_MD, 2)
        self.assertTrue(gitcmd.on_foreign_branch(self.branch))
        self.assertFalse((self.root / "tasks" / self.TASK).exists(),
                         "файлы существуют только на ветке, не на диске")

        count = fsm._answer_file_count(self.conn, self.TASK,
                                       self.root / "tasks" / self.TASK)

        self.assertEqual(count, 2)

    def test_missing_directory_on_the_branch_is_zero_not_none(self):
        count = fsm._answer_file_count(self.conn, self.TASK,
                                       self.root / "tasks" / self.TASK)

        self.assertEqual(count, 0)

    def test_unresponsive_git_is_none(self):
        with mock.patch.object(gitcmd, "ls_tree_files", lambda *a, **k: None):
            count = fsm._answer_file_count(self.conn, self.TASK,
                                           self.root / "tasks" / self.TASK)

        self.assertIsNone(
            count, "git не ответил — не значит «ноль», вызывающий код "
            "решает, как трактовать (docstring _answer_file_count)")


class BriefAnswerComponentsOnForeignBranchTest(_AnswerRealGitSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.create_schema(self.conn)
        store.insert_task(self.conn, self.TASK, "Задача", "spec_writing",
                          self.branch, config.DEFAULT_TARGET, 25.0)

    def test_latest_answer_rel_reads_the_branch_and_compares_numerically(self):
        self.commit_on_branch("ANSWER-1.md", ANSWER_MD, 1)
        self.commit_on_branch("ANSWER-10.md", ANSWER_MD, 10)
        self.commit_on_branch("ANSWER-2.md", ANSWER_MD, 2)

        rel = brief._latest_answer_rel(self.TASK, self.branch, True)

        self.assertEqual(rel, "ANSWER-10.md",
                         "числовое сравнение номеров, не строковое")

    def test_answer_component_reads_text_from_the_branch(self):
        self.commit_on_branch("ANSWER-1.md", ANSWER_MD, 1)

        part = brief._answer_component(self.conn, self.TASK, "developer",
                                       self.branch, True, brief.new_run_id())

        self.assertIn("Раунд 1: OK.", part)

    def test_questions_component_reads_text_from_the_branch(self):
        self.commit_on_branch("QUESTIONS.md", QUESTIONS_MD)

        part = brief._questions_component(self.conn, self.TASK, "analyst",
                                          self.branch, True, brief.new_run_id())

        self.assertIn("QUESTIONS: батч", part)

    def test_no_answer_files_on_the_branch_is_empty_string(self):
        part = brief._answer_component(self.conn, self.TASK, "developer",
                                       self.branch, True, brief.new_run_id())

        self.assertEqual(part, "")


if __name__ == "__main__":
    unittest.main()
