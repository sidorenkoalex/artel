"""Юнит-тест гейта возврата из эскалации (SPEC T075, AC-3/AC-4): второй
раунд эскалации той же задачи обязан потребовать НОВЫЙ ANSWER-n.md, не
удовлетворяться файлом прошлого раунда, оставшимся в каталоге задачи.

Приёмочные тесты T075 (`tasks/T075/acceptance_tests/`) проверяют ровно
один раунд эскалации на задачу — многораундовый сценарий (`answer_baseline`
обязан расти вместе с числом файлов, не просто быть «непустым») ими не
покрыт; здесь — белый ящик по `orchestrator/fsm.py::_answer_file_count`
и колонке `answer_baseline`, песочница по образцу
`tests/test_advance_guard.py::AdvanceGuardTest`.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, fsm, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import capture, capture_new_task_id, fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

QUESTIONS_MD = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: раунд {n}

## Вопросы

1. **Вопрос раунда {n}?** — варианты: A) да; B) нет — дефолт: A.
"""

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


class SecondEscalationRoundNeedsANewAnswerTest(unittest.TestCase):

    capture = staticmethod(capture)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Гейт ответа — второй раунд")
        self.tdir = config.TASKS / self.TASK

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def write(self, name: str, template: str, n: int) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(
            template.format(task=self.TASK, n=n), encoding="utf-8")

    def test_leftover_answer_from_round_one_does_not_satisfy_round_two(self):
        # Раунд 1: эскалация -> ответ -> возврат.
        self.write("QUESTIONS.md", QUESTIONS_MD, 1)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "escalated", "раунд 1 не эскалировал")

        self.write("ANSWER-1.md", ANSWER_MD, 1)
        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "spec_writing",
                         "раунд 1 не вернулся после ответа")

        # Раунд 2: новый батч вопросов эскалирует снова; ANSWER-1.md всё
        # ещё лежит в каталоге — гейт не имеет права принять его за ответ
        # на ВТОРОЙ раунд.
        self.write("QUESTIONS.md", QUESTIONS_MD, 2)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "escalated", "раунд 2 не эскалировал")

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "approve обязан отказать: ANSWER-2.md ещё нет, ANSWER-1.md — "
            "ответ на прошлый раунд, не на этот")
        self.assertIn("ANSWER-2.md", out)

        # Ответ на ВТОРОЙ раунд снимает отказ.
        self.write("ANSWER-2.md", ANSWER_MD, 2)
        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "spec_writing",
                         "раунд 2 не вернулся после своего ответа")


if __name__ == "__main__":
    unittest.main()
