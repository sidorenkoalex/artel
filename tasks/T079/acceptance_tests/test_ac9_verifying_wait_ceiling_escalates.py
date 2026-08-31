"""AC-9 (tasks/T079/SPEC.md): по истечении потолка ожидания (именованная
константа) без зелёного CI в любом из случаев AC-6..AC-8 `advance`
переводит задачу `verifying -> escalated` с диагностикой последнего
известного статуса CI в журнале.

Красен до реализации: состояния `verifying` в коде нет вовсе (см.
докстринг `test_ac5_verifying_green_ci_to_acceptance.py`) — задача
никогда не покидает `verifying` ни в `acceptance`, ни в `escalated`,
сколько раз `advance` ни повторяй.

## Допущение теста

SPEC требует «именованную константу» (требование 6), но НЕ называет её
идентификатор (в отличие, например, от tasks/T060/SPEC.md, требование 1,
буквально называющего `config.MAX_PARALLEL_TASKS`, — здесь такой
буквальной привязки нет). Тест поэтому не читает конкретное имя
`config.*` (скил test-authoring прямо просит не хардкодить ЗНАЧЕНИЕ
константы — здесь неизвестно даже её ИМЯ) — вместо этого гоняет
`advance` повторно с постоянно красным CI до упора в разумный потолок
попыток (`MAX_ADVANCE_ATTEMPTS` теста, не системы) и проверяет, что
эскалация УСПЕВАЕТ произойти внутри него. 200 — на порядок больше
любого разумного значения потолка ожидания CI (для сравнения:
`LIMIT_REVIEW_ITERS = 3`, `MAX_PARALLEL_TASKS = 10`); если потолок
задачи окажется больше — тест ложно покраснеет и это будет поводом
поднять `MAX_ADVANCE_ATTEMPTS`, а не признаком, что требование 6 не
выполнено.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm, store  # noqa: E402
from _sandbox import NO_RUN_LIST, RED_RUNS, VerifyingTest  # noqa: E402

MAX_ADVANCE_ATTEMPTS = 200


class VerifyingWaitCeilingEscalatesTest(VerifyingTest):

    def test_ac9_persistent_red_ci_eventually_escalates_with_diagnostics(self):
        self.enter_verifying(RED_RUNS, NO_RUN_LIST)

        escalated = False
        for _ in range(MAX_ADVANCE_ATTEMPTS):
            self.capture(fsm.cmd_advance, self.TASK)
            state = self.state()
            self.assertIn(
                state, ("verifying", "escalated"),
                "advance из verifying на красном CI не имеет права "
                "перевести задачу никуда, кроме verifying (ожидание) "
                "или escalated (потолок исчерпан)")
            if state == "escalated":
                escalated = True
                break

        self.assertTrue(
            escalated,
            f"потолок ожидания не сработал за {MAX_ADVANCE_ATTEMPTS} "
            f"повторных advance с неизменно красным CI — единственный "
            f"автоматический выход из verifying, кроме зелёного CI, "
            f"обязан существовать (требование 6)")

        journal = "\n".join(r["detail"] for r in
                            store.task_steps(store.db(), self.TASK))
        self.assertIn(
            "python", journal,
            "эскалация обязана нести диагностику ПОСЛЕДНЕГО известного "
            "статуса CI (имя незелёной проверки 'python' из фикстуры), "
            "не безадресное сообщение")


if __name__ == "__main__":
    unittest.main()
