"""AC-3 (tasks/T086/SPEC.md): зелёный CI (`ci.VERIFYING_GREEN`) в цикле
`auto` переводит задачу в `acceptance`, и `auto` продолжает цикл дальше
тем же вызовом (не останавливается на `verifying`).

`acceptance` сам не несёт агентной роли (`config.STATE_ROLE`) — «цикл
продолжается дальше» наблюдается как «оценил verifying, перешёл в
acceptance, ОСТАНОВИЛСЯ УЖЕ ТАМ» (одно и то же поведение, что и вход в
acceptance с любого другого агентского состояния сегодня, requirement 6
SPEC), а не как «застрял на verifying» — единственная развилка, которую
эта задача трогает.

Файл красит два разных теста по-разному (проверено исполнением):

- `test_ac3_green_ci_moves_to_acceptance_not_stuck_in_verifying` —
  красен до реализации: `verifying` не входит в `STATE_ROLE` сегодня —
  `auto._cmd_auto` не заходит в тело цикла вовсе (`role is None` уже на
  входе) и печатает подсказку остановки НА `verifying`, а не переводит
  задачу в `acceptance`; `self.state()` остаётся `"verifying"`, ассерт
  красный.
- `test_ac3_first_poll_green_needs_no_pause_before_continuing` — зелёный
  с рождения: сегодняшний код не знает про `time.sleep` вовсе ни в одной
  ветке `verifying`, так что «пауза не звалась» тривиально верно уже
  сейчас — тест существует не как регрессия сегодняшнего поведения, а
  как планка на реализацию требования 1: добавляя паузу МЕЖДУ повторными
  опросами (AC-1), она не имеет права звать её и на ПЕРВОМ, сразу
  зелёном, опросе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto  # noqa: E402
from _sandbox import GREEN_RUNS, VerifyingTest  # noqa: E402


class VerifyingGreenCiAdvancesAndContinuesTest(VerifyingTest):

    def test_ac3_green_ci_moves_to_acceptance_not_stuck_in_verifying(self):
        self.enter_verifying(GREEN_RUNS)

        auto.cmd_auto(self.TASK)

        self.assertEqual(
            self.state(), "acceptance",
            "зелёный CI обязан перевести verifying -> acceptance внутри "
            "цикла auto, так же как ручной advance (SPEC T079)")

    def test_ac3_first_poll_green_needs_no_pause_before_continuing(self):
        """Зелёный ответ ПЕРВЫМ же опросом обязан продолжить цикл тем же
        вызовом, а не пройти через паузу ожидания (та нужна только между
        повторными опросами незелёного/незавершённо-красного CI, AC-1) —
        `time.sleep` не имеет права быть вызван вовсе."""
        self.enter_verifying(GREEN_RUNS)

        with mock.patch("time.sleep") as sleep_spy:
            auto.cmd_auto(self.TASK)

        sleep_spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
