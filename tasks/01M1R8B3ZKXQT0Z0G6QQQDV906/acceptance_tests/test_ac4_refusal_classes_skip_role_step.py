"""AC-4 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): если предварительный `advance`
отказал guard'ом (`cmd_advance` вернул `True`) либо журналируемым отказом
другого класса («переход отклонён: …» — лок приёмочных тестов, дерево не
на ветке, гейт ёмкости diff, свежесть ветки и т. п.) — шаг роли на этой
итерации не запускается; цикл реагирует так же, как сегодня реагирует на
такой же отказ `advance`, полученный ПОСЛЕ шага роли: два одинаковых
отказа подряд останавливают цикл стоп-краном (SPEC T038), отказ guard'ом
— немедленной остановкой.

Красен до реализации: нынешний `orchestrator/auto.py::_cmd_auto` зовёт
`runner.cmd_run` БЕЗУСЛОВНО на каждой итерации, ДО `advance` (SPEC T038)
— оба сценария ниже нашли бы `("run", "developer")` в `self.events`,
хотя AC-4 требует его отсутствия.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import AutoAdvanceOrderSandbox  # noqa: E402

from orchestrator import auto, config  # noqa: E402


class Ac4JournaledRefusalSkipsTheRoleStepTest(AutoAdvanceOrderSandbox):

    def test_ac4_journaled_refusal_never_runs_the_role_step(self):
        """Два подряд журналируемых отказа одним текстом (класс «лок
        приёмочных тестов», как в T038) — стоп-кран останавливает цикл
        (существующее поведение, требование 7 — пороги не меняются), а
        `developer` не запускается ни на одной из двух итераций.

        Ловит мутацию: реализация, которая по-прежнему зовёт `cmd_run`
        до проверки класса отказа `advance` — `("run", "developer")`
        оказался бы в `self.events` уже на первой итерации, до всякого
        стоп-крана.
        """
        text = "переход отклонён: лок приёмочных тестов"
        self.set_state("in_dev")
        role = config.STATE_ROLE["in_dev"]
        self.advance.arm_journaled_refusal(text, n=2)

        out = self.capture(auto.cmd_auto, self.TASK)

        self.assertNotIn(("run", role), self.events,
                         "шаг роли запущен при журналируемом отказе advance")
        self.assertEqual(self.advance.calls, 2,
                         "цикл не остановился на втором подряд отказе")
        self.assertIn("auto остановлен", out)
        self.assertIn(text, out)

    def test_ac4_guard_refusal_never_runs_the_role_step_and_stops_immediately(self):
        """Guard-отказ (`cmd_advance` вернул `True`) — цикл встаёт на
        первом же таком отказе, `developer` не запускается вовсе.

        Ловит мутацию: реализация, которая продолжает крутить цикл
        (или запускает роль) после guard-отказа, вместо немедленной
        остановки, как и до этой задачи (существующая ветка `if fsm.
        cmd_advance(...): auto_stop(...)`).
        """
        self.set_state("in_dev")
        role = config.STATE_ROLE["in_dev"]
        self.advance.arm_guard_refusal()

        out = self.capture(auto.cmd_auto, self.TASK)

        self.assertNotIn(("run", role), self.events,
                         "шаг роли запущен при guard-отказе advance")
        self.assertEqual(self.advance.calls, 1,
                         "guard-отказ не остановил цикл немедленно")
        self.assertIn(f"почини артефакт и повтори artel.py advance {self.TASK}",
                      out)


if __name__ == "__main__":
    unittest.main()
