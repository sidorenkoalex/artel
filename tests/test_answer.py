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


class ZonesMandateMarkerPathsTest(unittest.TestCase):
    """`answer._zones_mandate_marker_paths` (SPEC
    01M287TPG0HAVXS8CHBCY679WN, требование 1) — чистый разбор строки
    маркера в тексте файла ответа, в изоляции от команды/git."""

    def test_no_marker_gives_empty_list(self):
        self.assertEqual(
            answer._zones_mandate_marker_paths("Обычный ответ.\n"), [])

    def test_marker_line_paths_are_parsed(self):
        self.assertEqual(
            answer._zones_mandate_marker_paths(
                "Расширение зон разрешено: docs/a.md, docs/b.md\n"),
            ["docs/a.md", "docs/b.md"])

    def test_marker_not_at_line_start_is_ignored(self):
        """Ловит мутацию: поиск подстроки где угодно в тексте вместо
        строки, начинающейся с маркера (`line.startswith`) — маркер,
        случайно процитированный в свободном тексте, не должен
        восприниматься как настоящий мандат Оператора."""
        self.assertEqual(
            answer._zones_mandate_marker_paths(
                "Я читал про «Расширение зон разрешено: docs/a.md» в "
                "скиле, но сам его не даю.\n"), [])

    def test_leading_whitespace_before_marker_is_stripped(self):
        self.assertEqual(
            answer._zones_mandate_marker_paths(
                "  Расширение зон разрешено: docs/a.md\n"), ["docs/a.md"])


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


class AnswerMandateMarkerOutsideInDevOrReviewStillRefusesTest(_ArtifactBranchAnswerTest):
    """SPEC 01M287TPG0HAVXS8CHBCY679WN, требование 1: маркер расширяет
    приём ТОЛЬКО для `in_dev`/`review`, не для ЛЮБОГО состояния вне
    `escalated` — дополняет приёмочные тесты AC-1/AC-2 этой задачи
    (кроют только `in_dev`/`review`/отсутствие маркера, не третье
    состояние с маркером)."""

    def test_marker_in_spec_writing_state_still_refuses(self):
        """Ловит мутацию: гейт состояния ослаблен до «`escalated` ИЛИ
        (маркер в тексте)», без проверки конкретных `in_dev`/`review` —
        задача в `spec_writing` с тем же маркером прошла бы точно так
        же, как в `in_dev`."""
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_writing")
        answer_file = self._answer_file(
            "Расширение зон разрешено: docs/a.md\n")

        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_answer(self.TASK, answer_file)

        self.assertIn("escalated", str(ctx.exception))
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


PLAN_WITH_EXTENSION_TEMPLATE = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: тест zones-extend

## Подход

## Шаги

## Покрытие требований

## Влияние на систему

## Расширение зон

Пути: {paths}

Обоснование: тест.
"""


class ZonesExtendCommandTest(_ArtifactBranchAnswerTest):
    """`answer.cmd_zones_extend` (SPEC 01M287TPG0HAVXS8CHBCY679WN,
    требование 2) — дополняет приёмочные тесты AC-4/AC-5/AC-6 этой же
    задачи (`tasks/01M287TPG0HAVXS8CHBCY679WN/acceptance_tests/
    test_ac4_ac5_ac6_zones_extend.py`) на двух углах, которых они не
    кроют: пустой список путей и слияние с УЖЕ имеющимся
    `zones_extension` при повторном вызове (не перезапись)."""

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def artifact_commit(self, files: dict, message: str) -> None:
        from orchestrator import artifact_branch
        sha = artifact_branch.commit_files(
            self.TASK, files, f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} не удался")

    def test_empty_paths_argument_refuses(self):
        """Ловит мутацию: пустой/пробельный аргумент путей коммитит
        ANSWER с пустым маркером вместо именованного отказа."""
        with self.assertRaises(SystemExit) as ctx:
            answer.cmd_zones_extend(self.TASK, "  ,  ")
        self.assertIn("пустой список путей", str(ctx.exception))

    def test_second_call_merges_with_existing_zones_extension(self):
        """Повторный вызов с расширенным списком путей и обновлённым
        PLAN.md — `zones_extension` становится ОБЪЕДИНЕНИЕМ старого и
        нового множества, не перезаписывается последним вызовом.

        Ловит мутацию: `store.update_task(..., zones_extension=paths_str)`
        вместо merge с `t["zones_extension"]` — второй вызов стёр бы
        путь, легализованный первым."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_WITH_EXTENSION_TEMPLATE.format(
                task=self.TASK, paths="docs/a.md")},
            "PLAN v1")
        answer.cmd_zones_extend(self.TASK, "docs/a.md")
        self.assertEqual(self.row()["zones_extension"], "docs/a.md")

        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_WITH_EXTENSION_TEMPLATE.format(
                task=self.TASK, paths="docs/a.md, docs/b.md")},
            "PLAN v2")
        answer.cmd_zones_extend(self.TASK, "docs/a.md, docs/b.md")

        self.assertEqual(self.row()["zones_extension"], "docs/a.md,docs/b.md")


if __name__ == "__main__":
    unittest.main()
