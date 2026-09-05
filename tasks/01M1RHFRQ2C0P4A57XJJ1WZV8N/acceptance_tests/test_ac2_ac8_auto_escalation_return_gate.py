"""Приёмочные тесты 01M1RHFRQ2C0P4A57XJJ1WZV8N — AC-2, AC-8: возврат из
`escalated` в состояние роли (правило AC-1, обобщённое на второй источник
входа — не только `review -> in_dev` напрямую).

Красен до реализации: `orchestrator/auto.py::_cmd_auto` не различает
«только что вернулись из escalated по неотработанному основанию» — ни по
`escalated -> in_dev` (AC-2), ни по возврату в `spec_writing` (AC-8):
пред-advance вызывает `fsm.cmd_advance` безусловно (см. докстринг
соседнего `test_ac1_ac4_ac9_auto_developer_step_gate.py`, тот же вызов,
строки 291-306 `orchestrator/auto.py`), а `orchestrator/fsm_advance.py::
spec_writing` эскалирует немедленно на одном лишь ФАКТЕ существования
QUESTIONS.md (строки 43-101, прочитано перед написанием теста), не
проверяя, отвечен ли уже прежний батч. Оба теста ниже покраснеют на
текущем коде: AC-2 — задача проскочит `in_dev -> review` по готовому
PLAN.md, ни разу не позвав developer; AC-8 — `auto` из `spec_writing`
повторно эскалирует по прежнему QUESTIONS.md, ни разу не позвав analyst
(тот же класс дефекта, что и второй инцидент 05.09, ANSWER-2 п.1).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                      agent_step)
from orchestrator import config, fsm, store  # noqa: E402

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


class EscalatedReturnToInDevStillNeedsADeveloperStepTest(AutoCycleTest):
    """AC-2: `escalated -> in_dev` (лимит ревью исчерпан — `escalated_from`
    не задан этой веткой `orchestrator/fsm_advance.py::review`, `_cmd_approve`
    дефолтит его в `in_dev`) с тем же неотработанным основанием
    (REVIEW.md ещё `changes_requested`) — правило AC-1 обязано сработать
    и здесь, не только на прямом `review -> in_dev`.
    """

    def test_ac2_pre_advance_yields_to_developer_after_escalated_return_to_in_dev(self):
        """Ловит мутацию: правило AC-1 реализовано ТОЛЬКО по имени
        предыдущего состояния (проверка «предыдущий переход был именно
        review -> in_dev»), не по факту «есть ли завершённый шаг
        developer с последней записи state -> in_dev» — возврат через
        `escalated` обошёл бы гейт стороной, цикл снова прочитал бы
        готовый PLAN.md и продвинул задачу в review, ни разу не позвав
        developer.
        """
        self.write_plan("ready")
        self.write_review("changes_requested", 1)
        self.set_state("escalated", review_iters=config.LIMIT_REVIEW_ITERS)

        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(
            self.state(), "in_dev",
            "approve не вернул задачу в in_dev — сценарий не воспроизведён")

        conn = store.db()
        self.agent.script = [
            agent_step(conn, self.TASK, lambda: self.set_state("escalated"))]

        self.auto()

        self.assertEqual(
            agent_run_finished_actors(conn, self.TASK), ["developer"],
            "developer не отработал шаг ровно один раз после возврата из "
            "escalated — предварительный advance продвинул задачу сам "
            "(или шаг достался другой роли)")


class EscalatedReturnByAnswerRunsTheRoleNotTheOldEscalationTest(AutoCycleTest):
    """AC-8: `spec_writing`, эскалированный батчем QUESTIONS.md (раунд 1),
    отвечен ANSWER-1.md и возвращён `approve` — QUESTIONS.md раунда 1
    остаётся на диске (леftover, ничем не переписан): `auto` обязан дать
    analyst шаг, не повторить переход в `escalated` по тому же файлу,
    который уже был основанием ПРОШЛОЙ, уже отвеченной эскалации.
    """

    def setUp(self):
        super().setUp()
        # `runner.step_role` подключает роль `analyst` для `spec_writing`
        # только при заведённом TZ.md (SPEC T025) — `AutoCycleTest.setUp`
        # заводит задачу без `--tz` (см. докстринг модуля `_sandbox.py`),
        # так что файл дописывается здесь напрямую на диск.
        (self.tdir / "TZ.md").write_text(
            "# ТЗ\n\nФикстура приёмочного теста 01M1RHFRQ2C0P4A57XJJ1WZV8N.\n",
            encoding="utf-8")

    def test_ac8_auto_runs_analyst_after_answered_escalation_not_the_stale_questions(self):
        """Ловит мутацию: пред-advance в auto не учитывает МОМЕНТ
        возврата (запись `state -> spec_writing`, оставленную `approve`)
        — читает QUESTIONS.md раунда 1 (существующий, ещё не
        переписанный analyst) и снова эскалирует задачу тем же путём,
        что и на первом заходе, ни разу не вызвав `cmd_run`:
        `agent.calls` останется пустым.
        """
        (self.tdir / "QUESTIONS.md").write_text(
            QUESTIONS_MD.format(task=self.TASK, n=1), encoding="utf-8")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "escalated", "раунд 1 не эскалировал")

        (self.tdir / "ANSWER-1.md").write_text(
            ANSWER_MD.format(task=self.TASK, n=1), encoding="utf-8")
        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(
            self.state(), "spec_writing",
            "approve не вернул задачу в spec_writing — сценарий не "
            "воспроизведён")

        conn = store.db()
        self.agent.script = [
            agent_step(conn, self.TASK, lambda: self.set_state("escalated"))]

        self.auto()

        self.assertEqual(
            agent_run_finished_actors(conn, self.TASK), ["analyst"],
            "analyst не отработал шаг ровно один раз — pre-advance снова "
            "эскалировал по прежнему QUESTIONS.md (или шаг достался "
            "другой роли)")


if __name__ == "__main__":
    import unittest
    unittest.main()
