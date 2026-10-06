"""Юнит-тесты умолчания песочницы для паузы повтора агента — `TmpRootTest`,
`patch_retry_pause`, `patch_pult_sleep` поверх умолчания и точечные подмены
классов на голом `unittest.TestCase` (SPEC 01M48WR0HKZW8KJCBWDZTFC4ZY).

Сам шаг роли с неуспешной попыткой и заявка «прежней длительности» при
своей подмене теста — в долгоживущем
`tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`; здесь — явный
отказ флагом класса, совместимость с `patch_pult_sleep` и подмены в
`tests/test_agent_prompt.py`/`tests/test_review_freshness.py`.

Песочницы проверяются ручным `setUp()`/`doCleanups()` экземпляра, а не
наследованием: подкласс `TestCase` на уровне модуля pytest собрал бы как
отдельный тест.
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import runner  # noqa: E402
from tests import test_agent_prompt, test_review_freshness  # noqa: E402
from tests.sandbox import TimeWithSleep, TmpRootTest, patch_pult_sleep  # noqa: E402


def _sandbox(cls):
    """Экземпляр песочницы `cls` после `setUp`; снятие — `doCleanups()`."""
    probe = cls(methodName="setUp")
    probe.setUp()
    return probe


class TmpRootTestRetryPauseTest(unittest.TestCase):

    def test_default_records_pause_instead_of_sleeping(self):
        """Умолчание `TmpRootTest`: пауза `runner` уходит в
        `self.retry_pauses` с прежней длительностью; после снятия песочницы
        `runner.time` — снова модуль `time`.

        Ловит мутацию: `TmpRootTest.setUp` не накладывает
        `patch_retry_pause` — `runner.time` остаётся модулем `time`, и
        первая же проверка покраснеет (а пауза ушла бы в настоящий сон).
        """
        probe = _sandbox(TmpRootTest)
        try:
            self.assertIsInstance(runner.time, TimeWithSleep)
            runner.time.sleep(7)
            runner.time.sleep(14)
            self.assertEqual(probe.retry_pauses, [7, 14])
        finally:
            probe.doCleanups()
        self.assertIs(runner.time, time)

    def test_opt_out_keeps_the_real_sleep(self):
        """`REAL_RETRY_PAUSE = True` — явный отказ: `runner.time` в песочнице
        остаётся настоящим модулем `time`, пауз в `retry_pauses` нет.

        Ловит мутацию: `setUp` не читает флаг `REAL_RETRY_PAUSE` (подмена
        накладывается всегда) — `runner.time` окажется заместителем.
        """
        class RealPause(TmpRootTest):
            REAL_RETRY_PAUSE = True

        probe = _sandbox(RealPause)
        try:
            self.assertIs(runner.time, time)
            self.assertEqual(probe.retry_pauses, [])
        finally:
            probe.doCleanups()

    def test_pult_sleep_patch_overrides_the_default(self):
        """`patch_pult_sleep(f)` внутри песочницы забирает и паузу `runner`:
        она уходит в `f`, а не в `retry_pauses`; `close()` возвращает
        умолчание песочницы.

        Ловит мутацию: `patch_pult_sleep` снова подменяет только модули,
        чья ссылка `time` — модуль `time`, — `runner` с заместителем
        песочницы пропущен, пауза уходит в `retry_pauses`, список `f` пуст.
        """
        probe = _sandbox(TmpRootTest)
        try:
            default = runner.time
            seen = []
            stack = patch_pult_sleep(seen.append)
            try:
                runner.time.sleep(3)
            finally:
                stack.close()
            self.assertEqual(seen, [3])
            self.assertEqual(probe.retry_pauses, [])
            self.assertIs(runner.time, default)
        finally:
            probe.doCleanups()


class PlainTestCaseRetryPauseTest(unittest.TestCase):

    def test_plain_sandboxes_patch_the_retry_pause(self):
        """`PromptChannelTest` и `ReviewFreshnessScenarioTest` — классы на
        голом `TestCase` — после своего `setUp` держат паузу `runner` без
        сна: она уходит в их `retry_pauses`.

        Ловит мутацию: точечная подмена паузы убрана из `setUp` одного из
        файлов — `runner.time` в его песочнице остаётся модулем `time`.
        """
        for cls in (test_agent_prompt.PromptChannelTest,
                    test_review_freshness.ReviewFreshnessScenarioTest):
            with self.subTest(cls=cls.__name__):
                probe = _sandbox(cls)
                try:
                    self.assertIsInstance(runner.time, TimeWithSleep)
                    runner.time.sleep(5)
                    self.assertEqual(probe.retry_pauses, [5])
                finally:
                    probe.doCleanups()
                self.assertIs(runner.time, time)


if __name__ == "__main__":
    unittest.main()
