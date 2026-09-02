"""AC-3 (SPEC T101) — сбой сбора fingerprint (бинарь не найден, таймаут)
не меняет исход агентного шага: шаг завершается так же, как если бы
сбор не выполнялся вовсе.

Зелёный с рождения: без кода задачи сбора fingerprint попросту нет, а
значит и вмешаться в исход шага ему нечем — эти проверки уже сейчас
верны, потому что нечему их нарушать. Смысл теста не в этом
вырожденном состоянии, а в том, что он обязан остаться зелёным и
ПОСЛЕ того, как разработчик добавит сбор (сохранение существующего
поведения шага при недоступном инструменте, тот же приём, что T033
`Ac8ExistingAdvanceTestsNotWeakenedTest`).

Сценарии — по одному на git и на claude, каждый в своём подпроцессе
(`_sandbox.run_driver`), тем же приёмом, что `test_ac2_agent_step_
missing_and_timeout.py`: разные сценарии в одном процессе Python
рисковали бы унаследовать кэш AC-6 друг от друга.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import run_driver  # noqa: E402


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

    def assert_outcome_unaffected(self) -> None:
        detail = self.finished()
        self.assertIn("rc=0", detail,
                      "шаг должен завершиться так же, как если бы сбор "
                      "fingerprint не выполнялся вовсе (AC-3)")
        for action in ("agent run FAILED", "agent run SKIPPED",
                      "agent run TIMEOUT"):
            self.assertNotIn(action, self.result["details"], (action, self.result))
        self.assertEqual(self.result["state"], "in_dev",
                         "сбой сбора не должен сдвигать состояние задачи")


class MissingGitDoesNotAffectOutcomeTest(_DriverScenarioTestCase):
    GIT_BEHAVIOR = "missing"
    CLAUDE_BEHAVIOR = "ok"

    def test_ac3_missing_git_does_not_change_agent_step_outcome(self):
        self.assert_outcome_unaffected()


class TimeoutClaudeDoesNotAffectOutcomeTest(_DriverScenarioTestCase):
    GIT_BEHAVIOR = "ok"
    CLAUDE_BEHAVIOR = "timeout"

    def test_ac3_timeout_claude_does_not_change_agent_step_outcome(self):
        self.assert_outcome_unaffected()


if __name__ == "__main__":
    unittest.main()
