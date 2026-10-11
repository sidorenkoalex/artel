"""AC-1 (tasks/T086/SPEC.md): из `verifying` при `ci.VERIFYING_NONE` или
`ci.VERIFYING_RUNNING` цикл `auto` не останавливается и не завершает
вызов — повторяет advance-опрос статуса CI с паузой на конфиг-константу
величиной порядка 60-120 секунд между попытками.

Красен до реализации: сегодня `verifying` не входит в `config.STATE_ROLE`,
поэтому `runner.step_role` возвращает `None` уже на входе, и
`auto._cmd_auto` ни разу не заходит в тело цикла — вызов заканчивается
немедленно, ни одного опроса `ci.verifying_status` сверх нулевого не
происходит и `time.sleep` не зовётся вовсе. Тест ожидает обратное:
несколько опросов с паузой в заданном диапазоне ДО того, как исчерпается
губернатор — до реализации `LoopGoverned` не бросается никогда (вызов
`auto.cmd_auto` просто возвращается), и `assertRaises` падает первым.

## Губернатор

CI-фикстура намеренно никогда не становится зелёной (`RUNNING_RUNS` без
запусков по `gh run list`) — без внешнего ограничителя цикл, если он
реализован по требованию 1, крутился бы часами реального времени теста.
`install_sleep_pause_governor(3)` останавливает его после третьей паузы
контролируемым исключением (см. докстринг `_sandbox.py`) — тест
проверяет, что до этой точки дошло минимум три паузы, каждая — в
диапазоне 60-120 секунд, буквально названном требованием 1.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto  # noqa: E402
from _sandbox import LoopGoverned, RUNNING_RUNS, VerifyingTest  # noqa: E402


class VerifyingAutoPollsWithPauseTest(VerifyingTest):

    def test_ac1_running_ci_keeps_polling_with_pause_in_range(self):
        self.enter_verifying(RUNNING_RUNS, "[]")
        pauses = self.install_sleep_pause_governor(3)

        with self.assertRaises(
                LoopGoverned,
                msg="auto обязан продолжать опрос (и звать паузу) при "
                    "незелёном/незавершённо-красном CI, а не остановить "
                    "вызов на первом же незелёном ответе"):
            auto.cmd_auto(self.TASK)

        self.assertGreaterEqual(
            len(pauses), 3,
            "цикл обязан повторять advance-опрос статуса CI, а не "
            "останавливаться после одной-двух попыток")
        for seconds in pauses:
            self.assertGreaterEqual(
                seconds, 60,
                f"пауза {seconds}с короче нижней границы требования 1 "
                f"(60-120 секунд)")
            self.assertLessEqual(
                seconds, 120,
                f"пауза {seconds}с длиннее верхней границы требования 1 "
                f"(60-120 секунд)")

        self.assertEqual(
            self.state(), "verifying",
            "незелёный/незавершённо-красный CI сам по себе не имеет "
            "права сдвинуть задачу из verifying")


if __name__ == "__main__":
    unittest.main()
