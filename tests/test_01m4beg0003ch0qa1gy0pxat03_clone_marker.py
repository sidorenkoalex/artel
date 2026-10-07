"""Маркер полного набора проходит только в процесс ведения канарейки."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, config


class CanaryCloneMarkerTest(unittest.TestCase):
    def test_clone_launch_passes_marker_to_child(self):
        """Процесс клона получает включённый маркер от блока канарейки.

        Ловит мутацию: запуск клона не передаёт маркер или передаёт «0» —
        дочерний автогейт снова запустит полный набор.
        """
        seen = []

        class Finished:
            def wait(self, timeout=None):
                return 0

        def fake_popen(argv, **kwargs):
            self.assertEqual(list(argv[:3]),
                             [sys.executable, "-m", canary.CANARY_DRIVE_MODULE])
            seen.append(kwargs["env"].get(config.CANARY_SKIP_FULL_SUITE_ENV))
            return Finished()

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(config, "CANARY_SKIP_FULL_SUITE", True), \
                mock.patch.object(canary.subprocess, "Popen", fake_popen):
            result, _, _ = canary._drive_in_clone(Path(tmp), Path(tmp) / "task.md")

        self.assertEqual(result, 0)
        self.assertEqual(seen, ["1"])

    def test_marker_is_active_only_in_canary_drive_process(self):
        """Внешний env не отключает обычный гейт, но вход клона читает маркер.

        Ловит мутацию: общий импорт принимает маркер в обычном процессе
        либо вход `canary_drive` забывает его прочитать.
        """
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            hook = Path(tmp) / "sitecustomize.py"
            hook.write_text(
                "import atexit\n"
                "def report():\n"
                "    from orchestrator import config\n"
                "    print('CANARY_SKIP_AT_EXIT=' + "
                "str(config.CANARY_SKIP_FULL_SUITE), flush=True)\n"
                "atexit.register(report)\n",
                encoding="utf-8")
            env = os.environ.copy()
            env[config.CANARY_SKIP_FULL_SUITE_ENV] = "1"
            env["PYTHONPATH"] = os.pathsep.join(
                (tmp, str(root), env.get("PYTHONPATH", "")))

            ordinary = subprocess.run(
                [sys.executable, "-c", "from orchestrator import config"],
                cwd=root, env=env, capture_output=True, text=True, timeout=30)
            child = subprocess.run(
                [sys.executable, "-m", canary.CANARY_DRIVE_MODULE, "--help"],
                cwd=root, env=env, capture_output=True, text=True, timeout=30)

        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertIn("CANARY_SKIP_AT_EXIT=False", ordinary.stdout)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("CANARY_SKIP_AT_EXIT=True", child.stdout)


if __name__ == "__main__":
    unittest.main()
