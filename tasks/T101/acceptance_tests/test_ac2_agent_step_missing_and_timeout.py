"""AC-2, AC-6 (SPEC T101) — недоступный инструмент/таймаут при сборе
fingerprint во время агентного шага: поле помечается "недоступно:
<причина>", таймаут внешнего вызова короткий, сбор всё равно кэшируется
на процесс (не повторяется дважды в рамках одного `runner.cmd_run`).

Красен до реализации: без сборщика fingerprint нет ни поля "недоступно:
<причина>", которое требует AC-2, ни самого факта передачи короткого
timeout= — сейчас `git_calls`/`claude_calls` в выводе драйвера просто
пусты (сбора нет вовсе, сравнивать не с чем).

Два сценария — `missing` (бинарь не найден) и `timeout` (внешний вызов
подвис) — по одному на git и на claude отдельно, каждый в своём
подпроцессе (`_sandbox.run_driver`): в рамках одного процесса Python
кэш AC-6 иначе унаследовал бы значение другого сценария того же
процесса (см. докстринг `_sandbox.py`, «Почему отдельный процесс на
сценарий»).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import run_driver  # noqa: E402

# Таймаут AC-2 — «порядка единиц секунд»; прецедент кодовой базы
# (`orchestrator/doctor.py::cli_version`, названный в SPEC «Материалы»)
# использует ровно 10 — верхняя граница здесь совпадает с ним, а не
# зажимает разработчика в однозначные секунды.
MAX_REASONABLE_TIMEOUT_SEC = 10


class _DriverScenarioTestCase(unittest.TestCase):
    GIT_BEHAVIOR = "ok"
    CLAUDE_BEHAVIOR = "ok"

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.result = run_driver("agent_step", cls._tmp.name,
                                cls.GIT_BEHAVIOR, cls.CLAUDE_BEHAVIOR)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def finished(self) -> str:
        details = self.result["details"].get("agent run finished", [])
        self.assertEqual(len(details), 1, self.result)
        return details[0]


class MissingGitScenarioTest(_DriverScenarioTestCase):
    GIT_BEHAVIOR = "missing"
    CLAUDE_BEHAVIOR = "ok"

    def test_ac2_missing_git_records_insufficient_marker_without_crashing(self):
        # Драйвер уже потребовал rc=0 от подпроцесса (`run_driver`) — сам
        # факт, что этот метод дошёл до assert'ов, значит, отсутствие git
        # не породило необработанное исключение (вторая половина AC-2).
        detail = self.finished()

        self.assertIn("недоступно:", detail,
                      f"поле git не помечено «недоступно: <причина>» при "
                      f"отсутствующем бинаре (AC-2): {detail!r}")

    def test_ac6_missing_git_is_still_looked_up_only_once(self):
        self.assertEqual(
            len(self.result["git_calls"]), 1,
            f"git --version вызван {len(self.result['git_calls'])} раз(а) "
            f"вместо 1 даже в сценарии отказа — сбор обязан кэшироваться "
            f"на процесс независимо от исхода (AC-6): {self.result}")


class TimeoutClaudeScenarioTest(_DriverScenarioTestCase):
    GIT_BEHAVIOR = "ok"
    CLAUDE_BEHAVIOR = "timeout"

    def test_ac2_timeout_claude_records_insufficient_marker_without_crashing(self):
        detail = self.finished()

        self.assertIn("недоступно:", detail,
                      f"поле claude не помечено «недоступно: <причина>» при "
                      f"таймауте внешнего вызова (AC-2): {detail!r}")

    def test_ac2_timeout_passed_to_the_external_call_is_short(self):
        self.assertEqual(len(self.result["claude_calls"]), 1, self.result)
        timeout = self.result["claude_calls"][0]

        self.assertIsNotNone(
            timeout, "внешний вызов сбора fingerprint обязан передавать "
            "timeout= (AC-2) — иначе сценарий timeout завис бы навечно")
        self.assertGreater(timeout, 0)
        self.assertLessEqual(
            timeout, MAX_REASONABLE_TIMEOUT_SEC,
            f"таймаут {timeout}с не «порядка единиц секунд» (AC-2)")


if __name__ == "__main__":
    unittest.main()
