"""AC-1 (tasks/T089/SPEC.md): `_ts_ago`, `FakeStream`, `SpyRun`,
`RealGitSandbox`, `_dead_pid` определены ровно один раз в кодовой базе —
в `tests/sandbox.py`.

Красен до реализации: до сведения хелперов `tests/sandbox.py` не несёт
всех пяти канонических определений (сейчас там их нет вовсе — хелперы
живут только копиями в `tests/test_release.py`, `tests/test_merge_lock.py`,
`tests/test_lease.py`, `tests/test_parallel_limit.py` (`_ts_ago`,
`_dead_pid`), `tests/test_doctor.py`, `tests/test_step_cost.py`,
`tests/test_agent_log.py`, `tests/test_agent_failure.py` (`FakeStream`),
`tests/test_invariants.py`, `tests/test_auto_cycle.py` (`SpyRun`),
`tests/test_gitcmd_branch_reads.py`, `tests/test_answer_branch_reads.py`
(`RealGitSandbox`)) — оба ассерта ниже падают до правки задачи.

AC-4 SPEC явно разрешает копиям остаться нетронутыми в
`tasks/*/acceptance_tests/` уже ЗАКРЫТЫХ задач («известный остаток») —
поэтому «ровно один раз» здесь проверяется с этим же исключением:
удар мимо `tests/sandbox.py` допустим только внутри
`tasks/<закрытая>/acceptance_tests/`. Открытые задачи и `tests/` — без
исключений (это же покрывают отдельно AC-2/AC-3, здесь — сводный взгляд
на «всю кодовую базу», как говорит сама формулировка AC-1).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _repo_scan import (HELPER_PATTERNS, acceptance_test_dirs, all_py_files,  # noqa: E402
                        open_task_ids, repo_root, scan_definitions,
                        task_id_of)


class SingleDefinitionPointTest(unittest.TestCase):

    def test_ac1_helpers_defined_only_in_sandbox_or_closed_task_remainder(self):
        root = repo_root()
        sandbox_path = (root / "tests" / "sandbox.py").resolve()
        open_ids = open_task_ids(root)

        closed_acceptance_dirs = {
            d.resolve() for d in acceptance_test_dirs(root)
            if task_id_of(d) not in open_ids
        }

        stray = []
        for path, name in scan_definitions(all_py_files(root)):
            path = path.resolve()
            if path == sandbox_path:
                continue
            if any(parent in closed_acceptance_dirs
                  for parent in (path, *path.parents)):
                continue
            stray.append((str(path.relative_to(root)), name))

        self.assertEqual(
            stray, [],
            "хелперы определены вне tests/sandbox.py и вне известного "
            f"остатка закрытых задач: {stray}")

    def test_ac1_sandbox_carries_every_named_helper(self):
        root = repo_root()
        sandbox_path = root / "tests" / "sandbox.py"
        self.assertTrue(sandbox_path.is_file(),
                        f"{sandbox_path} должен существовать")
        found = {name for _, name in scan_definitions([sandbox_path])}
        self.assertEqual(
            found, set(HELPER_PATTERNS),
            "tests/sandbox.py не несёт канонического определения всех "
            f"хелперов SPEC T089: не хватает {set(HELPER_PATTERNS) - found}")


if __name__ == "__main__":
    unittest.main()
