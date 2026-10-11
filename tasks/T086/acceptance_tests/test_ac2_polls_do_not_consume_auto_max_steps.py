"""AC-2 (tasks/T086/SPEC.md): паузы опроса `verifying` внутри цикла `auto`
не увеличивают счётчик шагов, ограничиваемый `AUTO_MAX_STEPS` — после
любого числа таких опросов у `auto` в том же вызове остаётся доступным
столько же шагов агентных состояний, сколько было бы без опроса.

## Как тест отличает «не расходует» от «расходует», не видя счётчик

SPEC не называет внутреннее имя переменной-счётчика цикла — тест не
имеет права заглянуть в него напрямую. Наблюдаемое следствие требования
2 то же самое: если бы опрос `verifying` расходовал `AUTO_MAX_STEPS`
(конфиг существующего кода, `orchestrator/config.py`, уже используемый
циклом до этой задачи), цикл сам остановился бы на `config.AUTO_MAX_STEPS`-м
опросе с сообщением «лимит N шагов за вызов исчерпан» — не дойдя до
опроса номер `AUTO_MAX_STEPS + 5`, которым дирижирует губернатор теста.
Тест поэтому не проверяет цифру напрямую, а доводит цикл ЗАВЕДОМО дальше
потолка шагов и проверяет, что он не сдался раньше срока по причине
шагового лимита — единственное наблюдение, совместимое с требованием 2,
но несовместимое с «опрос тоже тратит шаг».

Красен до реализации: по той же причине, что и AC-1 (`verifying` не
входит в `STATE_ROLE`, цикл не заходит в тело вовсе) — `time.sleep` не
зовётся ни разу, `LoopGoverned` не бросается, `assertRaises` падает.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, config  # noqa: E402
from _sandbox import LoopGoverned, RUNNING_RUNS, VerifyingTest  # noqa: E402


class VerifyingPollsDoNotConsumeStepsTest(VerifyingTest):

    def test_ac2_more_polls_than_auto_max_steps_do_not_hit_the_step_limit(self):
        self.enter_verifying(RUNNING_RUNS, "[]")
        since = self.last_step_id()
        overrun = config.AUTO_MAX_STEPS + 5
        pauses = self.install_sleep_pause_governor(overrun)

        with self.assertRaises(LoopGoverned):
            auto.cmd_auto(self.TASK)

        self.assertGreaterEqual(
            len(pauses), overrun,
            f"цикл остановился раньше {overrun}-й паузы опроса — если "
            f"это остановка по исчерпанному AUTO_MAX_STEPS "
            f"({config.AUTO_MAX_STEPS}), опрос verifying расходует "
            f"шаговый лимит цикла, что запрещено требованием 2")

        journal = "\n".join(self.journal_details_since(since))
        self.assertNotIn(
            "шагов за вызов исчерпан", journal,
            "журнал несёт остановку по шаговому лимиту — опрос verifying "
            "не имеет права расходовать AUTO_MAX_STEPS (требование 2)")


if __name__ == "__main__":
    unittest.main()
