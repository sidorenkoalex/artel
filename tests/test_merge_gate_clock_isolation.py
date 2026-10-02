"""Регрессионный тест изоляции часов тестов гейта мержа (SPEC
01M3YJ7VQ7CSBBPC8X84Z0YG3R, требование 6).

02.10 `tests/test_merge_gate_ci_wait.py` дважды покраснил CI чужих веток:
часы теста подменяли `time.sleep` модуля `time` целиком и записывали паузы
`subprocess.Popen._wait` (0.001, 0.002, … 0.05), пока дочерний git ещё
жил на медленном раннере. Здесь под теми же часами, что ставит
`MergeGateCiWaitUnitTest.setUp`, запускается настоящий дочерний процесс,
живущий дольше первой паузы `Popen._wait` — его ожидание в часы теста
попадать не должно.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fsm_merge_gate  # noqa: E402
from tests import test_merge_gate_ci_wait as ci_wait  # noqa: E402


class MergeGateClockIsolationTest(ci_wait.MergeGateCiWaitUnitTest):

    def test_child_process_wait_does_not_touch_the_test_clock(self):
        """Ожидание живого дочернего процесса (`subprocess.run` с
        `timeout`, процесс спит 0.3 с) не добавляет записей в
        `clock.sleep_calls` и не сдвигает `monotonic()` часов пульта.

        Ловит мутацию: в `MergeGateCiWaitUnitTest.setUp` возвращена
        глобальная подмена `mock.patch.object(time, "sleep", clock.sleep)` —
        `Popen._wait` опрашивает процесс паузами `time.sleep` модуля `time`
        по настоящим `monotonic`-часам `subprocess`, а процесс живёт
        0.3 с, поэтому хотя бы одна пауза на любой скорости машины
        попадёт в `sleep_calls` и сдвинет показание часов.
        """
        self.assertEqual(self.clock.sleep_calls, [])
        before = fsm_merge_gate.time.monotonic()

        subprocess.run([sys.executable, "-c", "import time; time.sleep(0.3)"],
                       check=True, timeout=10)

        self.assertEqual(self.clock.sleep_calls, [])
        self.assertEqual(fsm_merge_gate.time.monotonic(), before)


if __name__ == "__main__":
    unittest.main()
