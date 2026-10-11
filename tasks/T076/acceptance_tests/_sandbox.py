"""Общая песочница приёмочных тестов T076 (tasks/T076/SPEC.md).

Наследует `RealPultGitTest` (tests/test_git_fixation.py) — сценарий этой
задачи (расхождение `fixed_sha` при отклонённом переходе) проверяем
только на настоящем git: заглушкой `gitcmd.git` sha-фиксацию и реальные
коммиты роли внутри шага не изобразить (тот же довод, что у
`tests/test_step_autocommit.py`, `tests/test_timeout_checkpoint.py`).
Не переиспользуется напрямую импортом чужого `_sandbox.py` (T048/T051/
T064 — приватные модули своих задач), тот же приём, что и у них.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fixation, fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

# SPEC schema_version 2 с AC-разметкой — обязательное условие, чтобы
# spec_gate направил approve в tests_writing, а не сразу в in_dev
# (orchestrator/fsm.py::_cmd_approve, `guard.requires_ac_markup`).
SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: T076 приёмка — фиктивная задача песочницы

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом.

## Не входит
"""

# Полное покрытие AC-1/AC-2 реальным тестом, но БЕЗ маркера красноты в
# докстринге модуля — ровно сценарий T069/T073 (SPEC T064, «маркеры
# красноты»): guard отклоняет tests_writing -> in_dev по этой причине,
# хотя трассируемость AC сама по себе полная.
AC_TEST_NO_REDNESS_MARKER = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
"""


class T076Sandbox(RealPultGitTest):
    """`RealPultGitTest` + вход в `tests_writing` и коммит от имени
    test_author, обрамлённый журнальным окном «agent run started»/
    «agent run finished» — тем же полем, по которому SPEC (требование 1)
    разрешает сверять принадлежность коммита шагу задачи.
    """

    def enter_tests_writing(self) -> str:
        (self.task_dir() / "SPEC.md").write_text(
            SPEC_V2.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir("SPEC.md ready")
        self.capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = self.head()
        self.capture(fsm.cmd_approve, self.TASK, sha)  # spec_gate -> tests_writing
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "tests_writing",
            "подготовка теста не удалась — задача не дошла до tests_writing")
        return sha

    def commit_as_test_author(self, message: str) -> None:
        """Легитимный коммит роли ВНУТРИ шага — обрамлён теми же
        журнальными записями, что и настоящий `runner.cmd_run`
        (orchestrator/runner.py: «agent run started»/«agent run
        finished», см. SPEC T076, требование 1)."""
        conn = store.db()
        store.journal(conn, self.TASK, "test_author", "agent run started",
                      "шаг 1/1, лог: —, промпт: —")
        self.commit_task_dir(message)
        store.journal(conn, self.TASK, "test_author", "agent run finished",
                      "rc=0, шаг 1/1")

    def journal_details(self) -> list:
        return [r["detail"] for r in store.task_steps(store.db(), self.TASK)]

    def journal_entries(self) -> list:
        return [f"{r['action']}: {r['detail']}"
               for r in store.task_steps(store.db(), self.TASK)]
