"""Приёмочный тест 01M1RHFRQ2C0P4A57XJJ1WZV8N — AC-5: сценарий «замечания
ревью -> auto» запускает шаг developer, а не выполняет advance по
готовому PLAN.md.

В отличие от `test_ac1_ac4_ac9_auto_developer_step_gate.py::
PreAdvanceYieldsToDeveloperAfterReviewReworkTest` (там запись `state ->
in_dev` пишется тестом напрямую, изолированно от механики самого
перехода), этот тест воспроизводит переход `review -> in_dev` РЕАЛЬНЫМ
`fsm.cmd_advance` внутри цикла `auto` (задача стартует из `review`,
PLAN.md уже `ready` с прежнего прогона developer) — тем самым проверяется
не только условие пред-advance само по себе, но и то, что оно применяется
именно к журнальной записи, которую оставляет НАСТОЯЩИЙ переход
`orchestrator/fsm_advance.py::review`, а не только к искусственно
подготовленной записи теста.

Красен до реализации: тем же местом, что и `test_ac1_...py`
(`orchestrator/auto.py::_cmd_auto`, строки 291-306) — предварительный
`advance` продолжения цикла (уже из `in_dev`, куда его привёл честный
переход `review -> in_dev`) не отличает «developer ещё не отработал
замечания» от «артефакт готов» и продвинет задачу в `review` мимо
developer (на текущем коде — с несколькими холостыми оборотами `in_dev
-> review -> in_dev`, пока REVIEW.md той же итерации не окажется «уже
учтён» и цикл не позовёт РЕВЬЮВЕРА вместо developer, см. докстринг
`test_ac1_...py` для того же прогона на изолированной фикстуре).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                      agent_step)
from orchestrator import store  # noqa: E402


class ReviewRemarksScenarioRunsDeveloperBeforeAnyPreAdvanceSkipTest(AutoCycleTest):

    def test_ac5_review_remarks_scenario_runs_developer_not_ready_plan_advance(self):
        """Ловит мутацию: пред-advance пропускает шаг developer ТОЛЬКО
        когда запись `state -> in_dev` была подготовлена заранее (до
        старта `auto`), но не отслеживает НОВУЮ такую запись, оставленную
        переходом `review -> in_dev` УЖЕ ВНУТРИ текущего вызова `auto` —
        тест ниже требует и то, и другое: `developer` обязан получить шаг
        сразу после честного перехода `review -> in_dev`, случившегося тем
        же вызовом `auto`.
        """
        self.write_plan("ready")
        self.write_review("changes_requested", 1)
        self.set_state("review", review_iters=0, reviewed_iter=0)
        conn = store.db()
        self.agent.script = [
            agent_step(conn, self.TASK, lambda: self.set_state("escalated"))]

        out = self.auto()

        self.assertEqual(
            agent_run_finished_actors(conn, self.TASK), ["developer"],
            "developer не отработал шаг ровно один раз — сценарий "
            "«замечания ревью -> auto» продвинул задачу по готовому "
            "PLAN.md, минуя developer (или отдал шаг другой роли)")
        self.assertEqual(self.state(), "escalated")
        self.assertIn(
            "шаг reviewer не нужен: переход выполнен по готовым "
            "артефактам (review -> in_dev)", out,
            "переход review -> in_dev не случился — сценарий не воспроизведён")
        self.assertNotIn(
            "шаг developer не нужен: переход выполнен по готовым "
            "артефактам (in_dev -> review)", out,
            "цикл пропустил шаг developer и продвинул задачу сам")


if __name__ == "__main__":
    import unittest
    unittest.main()
