"""Сторож Bash-команд роли (`docs/reference/role-home/claude/hooks/
bash_guard.py`): полный прогон набора тестов внутри шага отклоняется,
адресный прогон и прочие команды проходят.

Скрипт живёт в референсе курируемого слоя ролей (не в `scripts/`), потому
что исполняется хуком из `$CLAUDE_CONFIG_DIR` роли — загружаем его по
пути, как деплой и делает.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "docs" / "reference" / "role-home" / "claude" / "hooks" / "bash_guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("bash_guard", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.g = _load()

    def test_blocks_full_suite_forms(self):
        for cmd in [
            "python3 -m unittest",
            "python3 -m unittest -v",
            "python3 -m unittest -v 2>&1 | tail -30",
            "python3 -m unittest > /dev/null 2>&1",
            "python3 -m unittest -v >log.txt",
            "python3 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tasks/X/acceptance_tests -p 'test_*.py' -t .",
            "cd .artel/worktrees/X && python3 -m unittest",
            "python -m unittest",
            "python3.11 -m unittest -k lease",
            "pytest",
            "pytest -q",
            "python3 -m pytest tests/ -q",
            "python3 -m pytest tests",
            "pytest . -x",
            "PYTHONPATH=. python3 -m unittest",
            "git status; python3 -m unittest discover",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(self.g.verdict(cmd))

    def test_allows_targeted_runs_and_other_commands(self):
        for cmd in [
            "python3 -m unittest tests.test_liveness -v 2>&1 | tail -30",
            "python3 -m unittest tests.test_a tests.test_b",
            "python3 -m unittest tasks/X/acceptance_tests/test_ac1.py",
            "python3 -m unittest -k lease tests.test_store",
            "python3 -m pytest tests/test_multitarget.py -q",
            "pytest tests/test_x.py::Case::test_y -q",
            "python3 -c 'print(1)'",
            "python3 scripts/guard.py tasks/X/SPEC.md",
            "git status && git diff --stat",
            "",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.g.verdict(cmd))

    def test_reason_names_the_rule_and_the_alternative(self):
        reason = self.g.verdict("python3 -m unittest")
        self.assertIn("CI", reason)
        self.assertIn("tests.test_x", reason)


class HookProtocolTest(unittest.TestCase):
    """Протокол хука Claude Code: JSON на stdin, код 2 + stderr — отказ,
    код 0 — пропуск; мусор на stdin не блокирует."""

    def _run(self, stdin: str):
        return subprocess.run([sys.executable, str(HOOK)], input=stdin,
                              capture_output=True, text=True, timeout=30)

    def test_blocking_exit_code_and_reason(self):
        r = self._run(json.dumps({"tool_name": "Bash",
                                  "tool_input": {"command": "python3 -m unittest"}}))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Сторож роли", r.stderr)

    def test_pass_through(self):
        r = self._run(json.dumps({"tool_name": "Bash",
                                  "tool_input": {"command": "python3 -m unittest tests.test_x"}}))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")

    def test_other_tools_and_garbage_pass(self):
        self.assertEqual(self._run(json.dumps({"tool_name": "Read",
                                               "tool_input": {}})).returncode, 0)
        self.assertEqual(self._run("не json").returncode, 0)

    def test_reference_settings_wire_the_hook(self):
        settings = json.loads((HOOK.parents[1] / "settings.json").read_text(encoding="utf-8"))
        entries = settings["hooks"]["PreToolUse"]
        self.assertTrue(any(e.get("matcher") == "Bash" and any(
            "hooks/bash_guard.py" in h.get("command", "") for h in e["hooks"])
            for e in entries))


if __name__ == "__main__":
    unittest.main()
