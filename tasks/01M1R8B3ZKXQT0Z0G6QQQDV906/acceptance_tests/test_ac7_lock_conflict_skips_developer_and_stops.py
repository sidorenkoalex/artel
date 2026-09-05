"""AC-7 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): отказ по локу
`acceptance_tests/` на предварительном `advance` в `in_dev` не запускает
шаг developer; повтор того же отказа на следующей итерации `auto`
останавливает цикл тем же стоп-краном, что и сегодня (SPEC T038).

Реальный git (не заглушка) — тем же приёмом и по тому же доводу, что и
`tests/test_acceptance_tests_flow.py::LockTest`, который `_sandbox.
LockConflictSandbox` наследует (не напрямую в этом файле — см. докстринг
`_sandbox.py`, почему): лок `acceptance_tests/` сверяется настоящим `git
diff` между зафиксированным sha и текущим HEAD, заглушкой это не
изобразить.

Красен до реализации: нынешний `orchestrator/auto.py::_cmd_auto` зовёт
`runner.cmd_run` (роль `developer`) БЕЗУСЛОВНО на каждой итерации, ДО
`fsm.cmd_advance` (SPEC T038) — лок уже сегодня отказывает переходу
`in_dev -> review` (T023, существующая механика), но ПОСЛЕ того, как
шаг `developer` этой итерации уже стартовал; `self.recorder.roles`
содержал бы `"developer"`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

from orchestrator import auto  # noqa: E402
from tests.test_acceptance_tests_flow import AC_TEST_MISSING_AC2  # noqa: E402

# `_sandbox.LockConflictSandbox` — не `from _sandbox import
# LockConflictSandbox`: тот bind сделал бы имя видимым в этом модуле, и
# `unittest discover` собрал бы `LockConflictSandbox` ЕЩЁ РАЗ как
# самостоятельный `TestCase` (он наследует настоящие `test_*`-методы
# `LockTest`, не только базу) — тот же класс дефекта, что докстринг
# `_sandbox.py` уже разбирает для прямого импорта `LockTest`.


class Ac7LockRefusalSkipsDeveloperAndStopsTheCycleTest(_sandbox.LockConflictSandbox):

    def test_ac7_lock_conflict_skips_developer_and_stops_on_the_repeat(self):
        """Ловит мутацию: реализация, оставившая старый порядок «run,
        затем advance» — `self.recorder.roles` содержал бы `"developer"`
        хотя бы раз, несмотря на то что лок отказывает переходу с самой
        первой итерации.
        """
        self.enter_in_dev()
        self.on_artifact_branch()
        (self.tdir / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_MISSING_AC2, encoding="utf-8")
        self.commit_task_dir("разработчик поправил тест — спор с тестом")

        out = self.capture(auto.cmd_auto, self.TASK)

        self.assertNotIn(
            "developer", self.recorder.roles,
            "auto запустил шаг developer при конфликте с локом "
            "acceptance_tests/")
        self.assertEqual(self.state(), "in_dev", "лок не удержал переход")
        self.assertIn("почини причину и повтори", out)


if __name__ == "__main__":
    unittest.main()
