"""AC-2 (tasks/T089/SPEC.md): файлы `tests/*.py`, ранее содержавшие
собственные копии хелперов, импортируют их из `tests/sandbox.py`; grep
по сигнатурам (`def _ts_ago`, `class FakeStream`, `class SpyRun`, `class
RealGitSandbox`, `def _dead_pid` и одноклассников) в каталоге `tests/`
находит только определения в `tests/sandbox.py`.

Красен до реализации: сейчас (до правки T089) в `tests/` живут собственные
определения — `_ts_ago` в `test_release.py`/`test_merge_lock.py`/
`test_lease.py`/`test_parallel_limit.py`, `_dead_pid` в
`test_merge_lock.py`/`test_parallel_limit.py`, `FakeStream` в
`test_doctor.py`/`test_step_cost.py`/`test_agent_log.py`/
`test_agent_failure.py`, `SpyRun` в `test_invariants.py`/
`test_auto_cycle.py`, `RealGitSandbox` в `test_gitcmd_branch_reads.py`/
`test_answer_branch_reads.py` — этот тест берёт ровно способ проверки,
названный самим критерием (grep по каталогу `tests/`), и падает на этих
копиях уже сейчас.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _repo_scan import repo_root, scan_definitions, tests_dir_py_files  # noqa: E402


class TestsDirImportsFromSandboxTest(unittest.TestCase):

    def test_ac2_grep_in_tests_dir_finds_only_sandbox_definitions(self):
        root = repo_root()
        sandbox_path = (root / "tests" / "sandbox.py").resolve()

        stray = [
            (str(path.relative_to(root)), name)
            for path, name in scan_definitions(tests_dir_py_files(root))
            if path.resolve() != sandbox_path
        ]

        self.assertEqual(
            stray, [],
            "grep по сигнатурам хелперов в tests/ находит определения вне "
            f"tests/sandbox.py: {stray}")


if __name__ == "__main__":
    unittest.main()
