"""AC-4 (tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md): «После `answer` из
AC-3 `approve` в состоянии `escalated` возвращает задачу в работу (ANSWER
засчитан: число файлов ANSWER выросло относительно `answer_baseline`), а
не отказывает «не хватает ANSWER-n.md»».

Красен до реализации: возврат из эскалации (`orchestrator/fsm.py`,
ветка `state == "escalated"`) сравнивает `fsm._answer_file_count` (уже
ветко-корректная, читает АРТЕФАКТНУЮ ветку пульта через
`artifact_source.resolve`) с зафиксированным `answer_baseline`. Пока
`answer.py::_cmd_answer` пишет `ANSWER-n.md` только в worktree кодовой
ветки (AC-3), это чтение его не видит — счёт не растёт, и `approve`
отказывает «не хватает ANSWER-{baseline+1}.md» даже после честного
`answer`. Инциденты 03.09 (01M1HNNHDMP2C1AJTH5QF1BTN2,
01M1KCSTBYF1CRJBSY4P6VYQEA) воспроизводят именно это — Оператору
пришлось вручную «мостить» ANSWER в артефактную ветку в обход `answer`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import answer, fixation, fsm, store  # noqa: E402
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


class ApproveReturnsAfterAnswerTest(RealPultGitTest):

    def setUp(self):
        super().setUp()
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

    def fixed_sha(self) -> str:
        """Sha, который `confirm_fixation` потребует от `approve` для
        состояния `escalated` (`APPROVE_NEEDS_SHA`) — читается тем же
        `fixation.read`, каким сверяется сам `approve`, чтобы тест не
        зависел от того, КАК устроена фиксация self/артели, только от
        публичного контракта "approve <id> <sha зафиксированного>"."""
        target = store.task_target(store.db(), self.TASK)
        sha, _clean = fixation.read(self.TASK, target)
        return sha

    def test_ac4_approve_returns_to_work_after_answer_not_refuses_missing_answer(self):
        """После `answer` (пишет `ANSWER-1.md`, AC-3) `approve` на
        эскалированной задаче обязан вернуть её в работу — состояние
        меняется с `escalated` на то, откуда была эскалация
        (`escalated_from`, здесь `spec_writing`) — а не печатать «не
        хватает ANSWER-1.md».

        Ловит мутацию: `_cmd_answer`, продолжающий писать только в
        worktree кодовой ветки (не устранённый AC-3) — `fsm._answer_
        file_count` тогда не увидит роста числа ANSWER-файлов
        относительно `answer_baseline`, и `approve` останется в
        `escalated`, вместо перехода в `spec_writing`.
        """
        answer.cmd_answer(self.TASK, self.answer_file("Ответ Оператора.\n"))

        out = self.capture(fsm.cmd_approve, self.TASK, self.fixed_sha())

        self.assertNotIn("не хватает", out)
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "spec_writing")

    def test_ac4_without_answer_approve_still_refuses_as_before(self):
        """Регресс-контроль симметрии: БЕЗ `answer` `approve` на
        эскалированной задаче по-прежнему отказывает («не хватает
        ANSWER-1.md») и остаётся в `escalated` — сам факт исправления
        AC-3/AC-4 не имеет права ослабить этот гейт (никогда не
        принимать эскалацию без ответа).

        Ловит мутацию: любая реализация, которая перестаёт СЧИТАТЬ файлы
        ANSWER (например, всегда трактует эскалацию как отвеченную) —
        тогда `approve` без `answer` тоже вернул бы задачу в работу.
        """
        out = self.capture(fsm.cmd_approve, self.TASK, self.fixed_sha())

        self.assertIn("не хватает", out)
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "escalated")


if __name__ == "__main__":
    unittest.main()
