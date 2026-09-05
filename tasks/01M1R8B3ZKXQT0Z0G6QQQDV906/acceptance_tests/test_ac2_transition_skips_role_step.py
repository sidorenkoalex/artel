"""AC-2 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): если предварительный `advance`
выполняет переход состояния — `runner.cmd_run` на этой итерации не
вызывается, и в журнал задачи пишется строка «шаг <роль> не нужен:
переход выполнен по готовым артефактам», где `<роль>` — роль состояния
до перехода.

Красен до реализации: нынешний `orchestrator/auto.py::_cmd_auto` зовёт
`runner.cmd_run` БЕЗ УСЛОВИЙ на каждой итерации, до всякого `advance`
(SPEC T038) — `self.events` содержал бы `("run", "developer")`, и в
журнале нет и не может быть строки «шаг ... не нужен ...» (её текста
сегодня в коде нет вовсе).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import AutoAdvanceOrderSandbox  # noqa: E402

from orchestrator import auto, config, store  # noqa: E402


class Ac2TransitionSkipsRoleStepTest(AutoAdvanceOrderSandbox):

    def test_ac2_transition_before_run_skips_the_role_step_and_is_journalled(self):
        """Предварительный `advance` из `in_dev` сразу переводит задачу в
        `review` (артефакт уже готов) — шаг `developer` в этой же
        итерации не запускается, а в журнале появляется строка «шаг
        developer не нужен: переход выполнен по готовым артефактам».

        Ловит мутацию: цикл, реагирующий на переход `advance` так же,
        как на отказ — запустил бы `cmd_run` для `developer` следом,
        и/или не оставил бы в журнале строку «шаг ... не нужен ...».
        """
        self.set_state("in_dev")
        role = config.STATE_ROLE["in_dev"]
        self.advance.arm_transition("review")
        # Вторая итерация (уже в `review`) не имеет отношения к предмету
        # AC-2 — guard-отказ останавливает цикл немедленно, не пускает
        # его крутиться дальше и не расходует лишних вызовов `cmd_run`.
        self.advance.arm_guard_refusal()
        journaled_before = len(store.task_steps(store.db(), self.TASK))

        self.capture(auto.cmd_auto, self.TASK)

        self.assertNotIn(("run", role), self.events,
                         f"шаг {role} запущен, хотя advance уже перевёл "
                         f"задачу дальше")
        self.assertEqual(self.state(), "review")
        rows = store.task_steps(store.db(), self.TASK)[journaled_before:]
        expected = f"шаг {role} не нужен: переход выполнен по готовым артефактам"
        self.assertTrue(
            any(expected in (r["action"] or "") or expected in (r["detail"] or "")
                for r in rows),
            f"строка «{expected}» не найдена в журнале: "
            f"{[(r['actor'], r['action'], r['detail']) for r in rows]}")


if __name__ == "__main__":
    unittest.main()
