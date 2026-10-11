"""AC-2 (tasks/T056/SPEC.md): запуск любой команды CLI из главной копии —
поведение идентично прежнему, байт-в-байт.

Эталон «прежнего» поведения — те же функции модулей `orchestrator`,
вызванные напрямую, в обход `artel.py::main`: по требованию 1 SPEC
проверка ROOT обязана жить строго на входе CLI, до диспетчеризации
команды, — то есть прямой вызов функции модуля в принципе не проходит
через неё и даёт результат «как если бы проверки не было». Из главной
копии (не worktree) CLI обязан дать тот же самый вывод байт-в-байт —
иначе проверка ROOT задела путь, которого требование 6 SPEC трогать не
разрешает.

Песочница — `_sandbox.WorktreeGuardSandbox`, но БЕЗ `git worktree add`:
`init_git_repo` даёт обычный git-репозиторий («главная копия»).
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from _sandbox import WorktreeGuardSandbox  # noqa: E402


class MainCopyUnaffectedTest(WorktreeGuardSandbox):

    def setUp(self):
        super().setUp()
        self.main_copy = self.sandbox / "main"
        self.seed_copy(self.main_copy)
        self.init_git_repo(self.main_copy)

    def direct_call_output(self) -> subprocess.CompletedProcess:
        """`init`+`status`, вызванные напрямую через модуль в отдельном
        процессе — минуя `artel.py::main` и, значит, минуя саму точку,
        где по требованию 1 SPEC обязана жить проверка ROOT."""
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
               "from orchestrator import catalog; "
               "catalog.cmd_init(); catalog.cmd_status()")
        return subprocess.run(
            ["python3", "-c", code, str(self.main_copy)],
            cwd=self.main_copy, timeout=30, capture_output=True, text=True,
            encoding="utf-8")

    def test_ac2_main_copy_cli_output_matches_direct_call_byte_for_byte(self):
        cli_init = self.run_cli(self.main_copy, "init")
        cli_status = self.run_cli(self.main_copy, "status")
        self.assertEqual(cli_init.returncode, 0, cli_init.stderr)
        self.assertEqual(cli_status.returncode, 0, cli_status.stderr)
        cli_combined = cli_init.stdout + cli_status.stdout

        # Состояние, заведённое CLI-прогоном выше, должно быть заведено
        # заново прямым вызовом — иначе совпадение вывода ничего не
        # доказывает о самой проверке ROOT (первый `init` уже отработал бы
        # за оба прогона).
        shutil.rmtree(self.main_copy / ".artel")

        direct = self.direct_call_output()

        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertEqual(
            direct.stdout, cli_combined,
            "вывод CLI из главной копии разошёлся байт-в-байт с прямым "
            "вызовом модуля — проверка ROOT задела путь без worktree")


if __name__ == "__main__":
    unittest.main()
