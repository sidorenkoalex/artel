"""Юнит-тесты `orchestrator/answer.py` (SPEC T075, SPEC
01M1KT0792125J9ZNJNZJ86E9Q требование 2): счётчик номера ANSWER-n.md,
генерация guard-валидного документа, отказы `answer` вне состояния
escalated и на нечитаемом файле ответа.

Happy path (создание, коммит в артефактную ветку, журнал) — приёмочные
тесты AC-3/AC-4 задачи 01M1KT0792125J9ZNJNZJ86E9Q (`tasks/
01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/`, песочница
`RealPultGitTest` с настоящим git) — здесь только то, что они не
проверяют: чистые функции модуля и отказы по предусловиям.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import answer, fsm, gitcmd, store  # noqa: E402
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

    def test_first_round_is_one(self):
        self.assertEqual(answer._next_answer_number([]), 1)

    def test_uses_max_plus_one_not_count(self):
        self.assertEqual(
            answer._next_answer_number(
                ["tasks/T001/ANSWER-1.md", "tasks/T001/ANSWER-3.md"]),
            4, "следующий номер — максимум существующих + 1, не счёт файлов")

    def test_non_numeric_suffix_is_ignored(self):
        self.assertEqual(
            answer._next_answer_number(
                ["tasks/T001/ANSWER-1.md", "tasks/T001/ANSWER-final.md"]),
            2)


class AnswerDocumentIsGuardValidTest(unittest.TestCase):

    def test_generated_document_passes_guard(self):
        text = answer._answer_document("T999", 3, "Ответ Оператора: A.\n")
        errors = guard.check_content("tasks/T999/ANSWER-3.md", text)
        self.assertEqual(errors, [])

    def test_generated_document_carries_the_raw_answer_text(self):
        text = answer._answer_document("T001", 1, "МАРКЕР-xyz\n")
        self.assertIn("МАРКЕР-xyz", text)


class _ArtifactBranchAnswerTest(RealPultGitTest):
    """`answer` (после SPEC 01M1KT0792125J9ZNJNZJ86E9Q, требование 2)
    пишет `ANSWER-n.md` плотницки в АРТЕФАКТНУЮ ветку пульта, кодовую
    ветку/worktree задачи не трогает вовсе — `_escalate()` сеет
    QUESTIONS.md туда же, тем же приёмом, что читает `fsm_advance.
    spec_writing` через `artifact_source.resolve`."""

    def _escalate(self) -> None:
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/QUESTIONS.md",
            QUESTIONS_TEXT.format(task=self.TASK),
            f"{self.TASK}: батч вопросов")
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

    def artifact_branch_files(self) -> list:
        from orchestrator import artifact_branch
        branch = artifact_branch.branch_name(self.TASK)
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []


class AnswerCommandRefusalsTest(_ArtifactBranchAnswerTest):

    def test_refuses_outside_escalated_state(self):
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_writing")
        answer_file = self._answer_file("Ответ.\n")

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, answer_file)

        self.assertIn("escalated", str(ctx.exception))
        self.assertNotIn(f"tasks/{self.TASK}/ANSWER-1.md",
                         self.artifact_branch_files())

    def test_refuses_on_unreadable_answer_file(self):
        self._escalate()
        missing = str(Path(self.root) / "нет-такого-файла.txt")

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, missing)

        self.assertIn("не прочитан", str(ctx.exception))
        self.assertNotIn(f"tasks/{self.TASK}/ANSWER-1.md",
                         self.artifact_branch_files())


class AnswerCommandDoesNotDisturbOtherArtifactsTest(_ArtifactBranchAnswerTest):
    """Тот же класс дефекта, что REVIEW T075 итерация 1, замечание major
    (тогда — `add -A` worktree, теперь — плотницкая запись): `answer`
    обязан коммитить РОВНО `ANSWER-n.md`, ничего больше из уже лежащего
    в артефактной ветке `tasks/<id>/` (например QUESTIONS.md эскалации)
    не трогая и не теряя."""

    def test_pre_existing_artifact_branch_files_survive_the_answer_commit(self):
        self._escalate()

        answer.cmd_answer(self.TASK, self._answer_file("Ответ.\n"))

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md", files)
        self.assertIn(f"tasks/{self.TASK}/QUESTIONS.md", files,
                      "answer не имеет права затронуть чужие артефакты "
                      "той же ветки")


if __name__ == "__main__":
    unittest.main()
