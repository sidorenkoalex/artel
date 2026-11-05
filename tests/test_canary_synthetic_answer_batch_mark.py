"""Синтетический ответ канарейки на эскалацию ставит признак «батч вопросов
отвечен» тем же узлом и при том же условии, что `approve` (SPEC
01M6PFGA0GR4ZMGT3H7PKS7SN5).

Сторож после мержа: планка задачи — разовая и после мержа не гоняется, а
без признака `spec_writing` эскалирует тот же `QUESTIONS.md` снова —
прогон канарейки 03.11 стал red четырьмя эскалациями подряд.

`tests.sandbox.LightTransitionSandbox`: документы задачи — на диске
`config.TASKS/<id>/`, песочница читает их как ветку документов. Канал
ANSWER подменён (`canary.answer.cmd_answer`) и сам кладёт `ANSWER-<n>.md`,
как в `tests/test_canary_synthetic_answer.py`: настоящий канал требует
lease, артефактной ветки и origin.
"""
import hashlib
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, fsm, store
from tests.sandbox import LightTransitionSandbox

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: батч сторожа канарейки

## Вопросы

1. **Вопрос сторожа?**
   - A) да
   - B) нет
   - дефолт: A.
"""


class SyntheticAnswerBatchMarkTest(LightTransitionSandbox):

    def _escalate(self, escalated_from: str, baseline) -> str:
        """Канареечная задача в `escalated` с полями эскалации и
        `QUESTIONS.md` в документах; возвращает текст батча."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        text = QUESTIONS_TEXT.format(task=self.TASK)
        (self.tdir / "QUESTIONS.md").write_text(text, encoding="utf-8")
        conn = store.db()
        store.update_task(conn, self.TASK, is_canary=1)
        self.set_state("escalated")
        store.update_task(conn, self.TASK, escalated_from=escalated_from,
                          answer_baseline=baseline)
        return text

    def _synthetic_pass(self) -> int:
        """Индекс первой новой записи журнала после синтетического ответа."""
        def channel(_task_id, file_path, *args, **kwargs):
            (self.tdir / "ANSWER-1.md").write_text(
                Path(file_path).read_text(encoding="utf-8"), encoding="utf-8")

        start = len(store.task_steps(store.db(), self.TASK))
        with mock.patch.object(canary.answer, "cmd_answer",
                               side_effect=channel):
            canary._pass_escalated_with_synthetic_answer(store.db(), self.TASK)
        return start

    def _new_steps(self, start: int) -> list:
        return list(store.task_steps(store.db(), self.TASK))[start:]

    def test_first_escalation_of_batch_marks_it_before_state_change(self):
        """Эскалация из `spec_writing` с `answer_baseline = 0` (первая
        эскалация батча): ровно одна новая строка
        `fsm.QUESTIONS_ANSWERED_ACTION` с хэшем `QUESTIONS.md` и номером
        синтетического ANSWER, раньше записи `state -> spec_writing`.

        Ловит мутацию: вызов `fsm._mark_questions_answered` удалён из
        `_pass_escalated_with_synthetic_answer` либо `answer_baseline`
        проверяется по истинности, а не `is not None` — строки признака
        нет; признак ставится после `store.set_state` — строка позже записи
        о смене состояния.
        """
        text = self._escalate("spec_writing", 0)

        rows = self._new_steps(self._synthetic_pass())

        actions = [r["action"] for r in rows]
        marks = [i for i, a in enumerate(actions)
                 if a == fsm.QUESTIONS_ANSWERED_ACTION]
        self.assertEqual(1, len(marks), actions)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(f"sha256={sha}; ANSWER-1", rows[marks[0]]["detail"])
        self.assertIn("state -> spec_writing", actions)
        self.assertLess(marks[0], actions.index("state -> spec_writing"))
        self.assertEqual("spec_writing", self.state())

    def test_no_mark_when_half_of_approve_condition_fails(self):
        """Не выполнена одна половина условия approve — признака нет,
        задача возвращена в прежнее состояние: (а) `in_dev` при
        `answer_baseline = 0`; (б) `spec_writing` при `answer_baseline =
        None`.

        Ловит мутацию: вызов признака безусловный — строка в обоих
        случаях; проверяется только `answer_baseline` — строка в (а);
        проверяется только `escalated_from` — строка в (б).
        """
        for escalated_from, baseline in (("in_dev", 0),
                                         ("spec_writing", None)):
            with self.subTest(escalated_from=escalated_from,
                              baseline=baseline):
                self._escalate(escalated_from, baseline)

                rows = self._new_steps(self._synthetic_pass())

                self.assertNotIn(fsm.QUESTIONS_ANSWERED_ACTION,
                                 [r["action"] for r in rows])
                self.assertEqual(escalated_from, self.state())


if __name__ == "__main__":
    unittest.main()
