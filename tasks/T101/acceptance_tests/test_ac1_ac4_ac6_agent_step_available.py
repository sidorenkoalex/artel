"""AC-1, AC-4, AC-6 (SPEC T101) — сбор fingerprint при доступных git/claude,
попадание в оба журнальных события агентного шага, кэш на один процесс.

Красен до реализации: сборщика fingerprint ещё нет — детали событий
"agent run started"/"agent run finished" не несут ни версии Python, ни
версии git, ни версии claude CLI, а `git_calls`/`claude_calls` в выводе
драйвера пусты (см. `_driver_agent_step.py`) вместо списка из одного
таймаута каждый.

Сценарий "ok, ok" гоняется ОДИН раз в отдельном подпроцессе
(`_sandbox.run_driver`, обоснование — её докстринг): `runner.cmd_run`
внутри драйвера журналирует и "agent run started", и "agent run
finished" одним вызовом — единственный процесс оркестратора, в рамках
которого проверяется кэш AC-6.
"""
import platform
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from _sandbox import run_driver  # noqa: E402


class AgentStepFingerprintAvailableTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls._tmp = tempfile.TemporaryDirectory()
        cls.result = run_driver("agent_step", cls._tmp.name, "ok", "ok")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def started(self) -> str:
        details = self.result["details"].get("agent run started", [])
        self.assertEqual(len(details), 1, self.result)
        return details[0]

    def finished(self) -> str:
        details = self.result["details"].get("agent run finished", [])
        self.assertEqual(len(details), 1, self.result)
        return details[0]

    def test_ac1_fingerprint_with_available_tools_includes_python_git_claude(self):
        detail = self.finished()

        self.assertIn(sys.executable, detail,
                      "путь интерпретатора Python (AC-1) не найден в detail")
        self.assertIn(platform.python_version(), detail,
                      "версия интерпретатора Python (AC-1) не найдена в detail")
        self.assertIn("2.43.0", detail,
                      "версия git (AC-1), отданная фейковым `git --version` "
                      "драйвера, не найдена в detail")
        self.assertIn(config.CLI_VERSION_PIN, detail,
                      "версия claude CLI (AC-1), отданная фейковым "
                      "`claude --version` драйвера, не найдена в detail")

    def test_ac4_fingerprint_present_in_started_and_finished_events(self):
        started_detail = self.started()
        finished_detail = self.finished()

        for detail, label in ((started_detail, "agent run started"),
                              (finished_detail, "agent run finished")):
            self.assertIn(sys.executable, detail, label)
            self.assertIn("2.43.0", detail, label)
            self.assertIn(config.CLI_VERSION_PIN, detail, label)

    def test_ac6_repeated_reads_do_not_repeat_subprocess_calls(self):
        # Оба журнальных события ("started" и "finished") читают fingerprint
        # в рамках ОДНОГО вызова `runner.cmd_run` этого драйвера — если бы
        # каждое читало заново, git/claude `--version` вызывались бы дважды.
        self.assertEqual(
            len(self.result["git_calls"]), 1,
            f"git --version вызван {len(self.result['git_calls'])} раз(а) "
            f"вместо 1 — сбор не кэшируется на процесс (AC-6): "
            f"{self.result}")
        self.assertEqual(
            len(self.result["claude_calls"]), 1,
            f"claude --version вызван {len(self.result['claude_calls'])} "
            f"раз(а) вместо 1 — сбор не кэшируется на процесс (AC-6): "
            f"{self.result}")


if __name__ == "__main__":
    unittest.main()
