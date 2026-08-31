"""Юнит-тесты `orchestrator/answer.py` (SPEC T075): счётчик номера
ANSWER-n.md, генерация guard-валидного документа, отказы `answer` вне
состояния escalated и на нечитаемом файле ответа.

Happy path (создание, коммит, авторство, журнал) уже покрыт приёмочным
тестом AC-2 (`tasks/T075/acceptance_tests/test_ac2_answer_command.py`,
песочница `RealPultGitTest` с настоящим git) — здесь только то, что он
не проверяет: чистые функции модуля и отказы по предусловиям.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import answer, fsm, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Какой вариант выбрать?** — варианты: A) первый; B) второй — дефолт: A.
"""


class NextAnswerNumberTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_first_round_is_one(self):
        self.assertEqual(answer._next_answer_number(self.tdir), 1)

    def test_uses_max_plus_one_not_count(self):
        (self.tdir / "ANSWER-1.md").write_text("x", encoding="utf-8")
        (self.tdir / "ANSWER-3.md").write_text("x", encoding="utf-8")
        self.assertEqual(
            answer._next_answer_number(self.tdir), 4,
            "следующий номер — максимум существующих + 1, не счёт файлов")

    def test_non_numeric_suffix_is_ignored(self):
        (self.tdir / "ANSWER-1.md").write_text("x", encoding="utf-8")
        (self.tdir / "ANSWER-final.md").write_text("x", encoding="utf-8")
        self.assertEqual(answer._next_answer_number(self.tdir), 2)


class AnswerDocumentIsGuardValidTest(unittest.TestCase):

    def test_generated_document_passes_guard(self):
        text = answer._answer_document("T999", 3, "Ответ Оператора: A.\n")
        errors = guard.check_content("tasks/T999/ANSWER-3.md", text)
        self.assertEqual(errors, [])

    def test_generated_document_carries_the_raw_answer_text(self):
        text = answer._answer_document("T001", 1, "МАРКЕР-xyz\n")
        self.assertIn("МАРКЕР-xyz", text)


class AnswerCommandRefusalsTest(RealPultGitTest):

    def test_refuses_outside_escalated_state(self):
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_writing")
        answer_file = self._answer_file("Ответ.\n")

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, answer_file)

        self.assertIn("escalated", str(ctx.exception))
        self.assertFalse((self.task_dir() / "ANSWER-1.md").exists())

    def test_refuses_on_unreadable_answer_file(self):
        self._escalate()
        missing = str(Path(self.root) / "нет-такого-файла.txt")

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, missing)

        self.assertIn("не прочитан", str(ctx.exception))
        self.assertFalse((self.task_dir() / "ANSWER-1.md").exists())

    def _escalate(self) -> None:
        (self.task_dir() / "QUESTIONS.md").write_text(
            QUESTIONS_TEXT.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir("батч вопросов")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")

    def _answer_file(self, text: str) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        f.write(text)
        f.close()
        return f.name


if __name__ == "__main__":
    unittest.main()
