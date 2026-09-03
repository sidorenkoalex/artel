"""AC-3 (tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md): «`answer <id> <файл>`
у задачи с артефактной веткой создаёт `tasks/<id>/ANSWER-n.md` в
артефактной ветке (коммит без чекаута, кодовая ветка и рабочее дерево не
меняются); `n` — следующий номер по содержимому артефактной ветки».

Красен до реализации: `orchestrator/answer.py::_cmd_answer` (SPEC,
«Материалы», строки ~70-100) безусловно пишет `ANSWER-n.md` в worktree
КОДОВОЙ ветки задачи через `workspace.ensure(task_id, t["branch"])` — та
же функция, что и до A7, docstring `tests/test_answer.py::
_WorktreeAnswerTest` называет это прямо («A7 не генерализует этот файл»).
`workspace.ensure` при этом ЗАВОДИТ кодовую ветку/worktree как побочный
эффект (если их ещё не было) — эту ветку тесты ниже проверяют
буквально ПОСЛЕ вызова: она обязана остаться незаведённой.
"""
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import answer, artifact_branch, fsm, gitcmd, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

QUESTIONS_MD = """---
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


class _Ac3Sandbox(RealPultGitTest):
    """`RealPultGitTest.setUp` заводит `self.TASK` (target — self/артель)
    в `spec_writing` с реальной артефактной веткой пульта. Эскалация —
    тем же приёмом, что `tests/test_answer.py::_WorktreeAnswerTest.
    _escalate`: QUESTIONS.md сеется В АРТЕФАКТНУЮ ВЕТКУ (не на диск/в
    worktree кодовой ветки) — именно так `fsm_advance.spec_writing`
    реально видит батч вопросов после A7."""

    def escalate(self) -> None:
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/QUESTIONS.md",
            QUESTIONS_MD.format(task=self.TASK),
            f"{self.TASK}: батч вопросов")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "escalated",
            "предпосылка сценария: эскалация должна была состояться")

    def answer_file(self, text: str) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        f.write(text)
        f.close()
        return f.name

    def artifact_branch_files(self) -> list:
        branch = artifact_branch.branch_name(self.TASK)
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []


class AnswerCommitsToArtifactBranchTest(_Ac3Sandbox):

    def test_ac3_answer_lands_in_the_artifact_branch_not_the_code_branch(self):
        """`answer` на эскалированной задаче с артефактной веткой обязан
        положить `ANSWER-1.md` в АРТЕФАКТНУЮ ветку пульта — ту самую,
        откуда его читает возврат из эскалации (`fsm._answer_file_count`,
        уже ветко-корректная).

        Ловит мутацию: `_cmd_answer`, оставленный как есть (пишет только
        в worktree кодовой ветки задачи) — тогда `tasks/<id>/ANSWER-1.md`
        не появится в списке файлов артефактной ветки.
        """
        self.escalate()

        answer.cmd_answer(self.TASK, self.answer_file("Ответ Оператора.\n"))

        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md",
                      self.artifact_branch_files())

    def test_ac3_code_branch_is_not_created_by_answer(self):
        """До вызова `answer` кодовая ветка задачи (`t["branch"]`) в git
        не существует (задача не дошла до `in_dev`, ни один шаг ещё не
        заводил её worktree). После `answer` она обязана остаться
        незаведённой — «кодовая ветка и рабочее дерево не меняются»
        (буквальный текст AC-3): запись идёт плотницки, без чекаута.

        Ловит мутацию: `_cmd_answer`, вызывающий `workspace.ensure(task_id,
        t["branch"])` как сегодня — эта функция заводит и worktree, и
        саму кодовую ветку как побочный эффект, если их ещё не было.
        """
        self.escalate()
        t = store.get_task(store.db(), self.TASK)
        self.assertFalse(
            gitcmd.branch_exists(t["branch"]),
            "предпосылка сценария: кодовой ветки ещё нет")

        answer.cmd_answer(self.TASK, self.answer_file("Ответ Оператора.\n"))

        self.assertFalse(
            gitcmd.branch_exists(t["branch"]),
            "answer не имеет права заводить кодовую ветку задачи")

    def test_ac3_second_round_numbers_from_the_artifact_branch_content(self):
        """`n` — следующий номер по содержимому АРТЕФАКТНОЙ ветки, не
        диска/worktree: ANSWER-1.md уже лежит там (симулирует первый
        раунд, отвеченный ДО фикса — например, операторским «мостом» в
        артефактную ветку, как в инцидентах 03.09) — второй `answer`
        обязан посчитать номер `2` именно по ней.

        Ловит мутацию: подсчёт `n` по `tasks/<id>/` кодовой ветки/worktree
        (пустой в этом сценарии) — тогда второй `answer` снова назвал бы
        файл `ANSWER-1.md`, затерев номер первого раунда в счёте.
        """
        self.escalate()
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/ANSWER-1.md",
            ANSWER_MD.format(task=self.TASK, n=1),
            f"{self.TASK}: ANSWER-1 (симуляция домержевого раунда)")

        answer.cmd_answer(self.TASK, self.answer_file("Второй раунд.\n"))

        self.assertIn(f"tasks/{self.TASK}/ANSWER-2.md",
                      self.artifact_branch_files())


if __name__ == "__main__":
    unittest.main()
