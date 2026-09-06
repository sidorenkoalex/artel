"""AC-5 (SPEC.md, требование 2): журнальная запись `AMEND_ACTION`
(«правка планки») после успешной фиксации `amend-tests` по-прежнему
называет зелёный итог прогона и число тестов — теперь по сводке pytest,
не по строке unittest.

Сквозной сценарий реальным git (`RealGitSandbox`), тем же приёмом, что
`tests/test_amend.py::AmendThenReviewGateTest` — эта задача не меняет
сам механизм amend-tests (какая ветка, какой лок), только то, ЧЕМ
разбирается хвост прогона перед записью в журнал (`amend._run_summary`),
поэтому воспроизводится полный путь до журнала, не только вызов
`_run_summary` в изоляции (это уже AC-4).

Красен до реализации: до тех пор, пока requirement 1
(`acceptance.run()`) не переключён на pytest, обязательный прогон внутри
`_cmd_amend_tests` производит unittest-хвост («Ran 2 tests… OK»), и
запись журнала несёт именно его — `assertIn` на pytest-словo «passed» в
детали события откажет.

Фикстура правки (`AC_TEST_TWO_PASSING`) — в `_util.py`, не литералом
здесь: она несёт настоящую пометку критерия АС-2 внутри строки-фикстуры,
и guard иначе прочёл бы её как реальную разметку ЭТОЙ задачи (тот же
довод, что в докстринге `_util.py`/`test_ac6_marker_scanning_regression.py`).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import amend, artifact_branch, catalog, fsm, store, workspace  # noqa: E402
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import (  # noqa: E402
    AC_TEST_BOTH_COVERED, PLAN_MD, SPEC_V2)
from _util import AC_TEST_TWO_PASSING  # noqa: E402


class AmendJournalPytestSummaryTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "amend journal — сводка pytest")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt_path = wt_path
        self.tdir = wt_path / "tasks" / self.TASK
        (self.wt_path / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git_wt("add", "feature.txt")
        self.git_wt("commit", "-q", "-m", f"{self.TASK}: код фичи")

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def git_wt(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.wt_path), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C {self.wt_path} {' '.join(args)}: {res.stderr}")
        return res.stdout

    def artifact_commit(self, files: dict, message: str) -> None:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} на артефактную ветку не удался")

    def enter_in_dev(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK, extra="")},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)
        from orchestrator import config, gitcmd
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_BOTH_COVERED},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)

    def test_ac5_journal_entry_names_pytest_style_green_summary(self):
        """После успешного `amend-tests` над планкой, реально проходящей
        под НАСТОЯЩИМ прогоном `acceptance.run()`, запись журнала
        `AMEND_ACTION` несёт извлечённую сводку в pytest-формате («N
        passed»), не в формате unittest («OK»/«Ran N»).

        Ловит мутацию: `_cmd_amend_tests` не обновлён вместе с `_run_summary`
        (`amend.py`, требование 2) — деталь события несёт либо весь
        необрезанный хвост pytest (регулярка не нашла сводку), либо
        сохранившийся unittest-формат «Ran N tests… OK», ни то ни другое
        не содержит подстроку «passed».
        """
        self.enter_in_dev()
        (self.tdir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (self.tdir / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_TWO_PASSING, encoding="utf-8")
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)}, "PLAN")

        out = capture(amend.cmd_amend_tests, self.TASK,
                      "две проверки AC-1 вместо одной (тест сводки журнала)")
        row = self.row()
        self.assertTrue(row["tests_locked_sha"], f"amend-tests отказал: {out}")

        steps = store.task_steps(self.conn, self.TASK)
        amend_steps = [s for s in steps if amend.AMEND_ACTION in s["action"]]
        self.assertTrue(amend_steps, f"нет записи журнала {amend.AMEND_ACTION!r}")
        detail = amend_steps[-1]["detail"]

        self.assertIn("приёмочные тесты:", detail)
        self.assertRegex(
            detail, r"\d+\s+passed",
            f"деталь события не несёт pytest-сводку 'N passed': {detail}")
        self.assertNotIn(
            "Ran ", detail,
            f"деталь события всё ещё несёт unittest-формат 'Ran N tests': "
            f"{detail}")


if __name__ == "__main__":
    unittest.main()
