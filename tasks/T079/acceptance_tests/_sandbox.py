"""Общая песочница приёмочных тестов T079 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py, тем же
приёмом, что `tasks/T052/acceptance_tests/_sandbox.py`).

`VerifyingTest(FsmTest)` — задача T001 в состоянии `verifying`
(`tests.test_invariants.FsmTest`: БД и артефакты во временном каталоге,
git и `gh` не исполняются по-настоящему — `SpyRun` перехватывает ЛЮБОЙ
`subprocess.run` процесса, включая ещё не написанный вызов адаптера,
тем же приёмом, что и `FsmTest.set_ci` уже использует для `ci.gh`/
`ci.head_sha`). Небезопасно было бы гонять эти тесты на лёгкой песочнице
без глобального перехвата subprocess (`tests.sandbox.TmpRootTest` +
`fake_git`, что патчит только `gitcmd.git`) — код verifying ещё не
существует, и вызов `gh` из него, попади он в реальный subprocess.run,
ушёл бы на настоящий GitHub настоящим токеном разработчика.

`set_ci_dual` различает ДВА источника ответа `gh` по содержимому argv:
check-runs коммита (`orchestrator/ci.py::check_runs_page`, уже
существующий вызов `gh api .../check-runs?...`) и `gh run list` по ветке
— требование 5 SPEC называет источник ДОСЛОВНО («gh run list по
ветке» — TZ.md п.4, SPEC.md AC-6/AC-7), поэтому распознавание вызова
по литералам `run`/`list` — не домысел интерфейса, а прямая цитата
критерия (в отличие от Draft-MR-флоу AC-1..AC-3, где SPEC сознательно
не называет механизм — см. `test_manual_criteria.py`).
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import ci, store  # noqa: E402
from tests.test_invariants import FAKE_SHA, FsmTest  # noqa: E402


def _check_runs(runs: list) -> str:
    return json.dumps({"total_count": len(runs), "check_runs": runs})


# Четыре исхода requirement 5 (SPEC AC-5..AC-8), собранные в фикстуры имени
# исхода — переиспользуются во всех test_ac*.py этого каталога.
GREEN_RUNS = _check_runs([
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "python", "status": "completed", "conclusion": "success"},
])
NO_RUNS = _check_runs([])
RUNNING_RUNS = _check_runs([
    {"name": "python", "status": "in_progress", "conclusion": None},
])
RED_RUNS = _check_runs([
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "python", "status": "completed", "conclusion": "failure"},
])

NO_RUN_LIST = "[]"
SOME_RUN_LIST = json.dumps(
    [{"headBranch": "task/t001-verifying", "status": "in_progress"}])


class VerifyingTest(FsmTest):
    """`FsmTest` + `ci.gh` управляемый по двум источникам (check-runs
    коммита / `gh run list` ветки) вместо единственного канонического
    `GREEN_CI`, который ставит `FsmTest.set_ci` по умолчанию."""

    def enter_verifying(self, check_runs_json: str = GREEN_RUNS,
                        run_list_json: str = NO_RUN_LIST) -> None:
        self.set_state("verifying")
        self.set_ci_dual(check_runs_json, run_list_json)

    def set_ci_dual(self, check_runs_json: str,
                    run_list_json: str = NO_RUN_LIST) -> None:
        def gh(*args: str) -> subprocess.CompletedProcess:
            joined = " ".join(args)
            if "check-runs" in joined:
                return subprocess.CompletedProcess(list(args), 0,
                                                    check_runs_json, "")
            if "run" in args or "actions/runs" in joined:
                return subprocess.CompletedProcess(list(args), 0,
                                                    run_list_json, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        for target, value in (("gh", gh),
                              ("head_sha", lambda branch: (FAKE_SHA, ""))):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ журнал

    def last_step_id(self) -> int:
        rows = store.task_steps(store.db(), self.TASK)
        return rows[-1]["id"] if rows else 0

    def journal_details_since(self, since_id: int) -> list[str]:
        """Строки журнала (`action` + `detail`, не только `detail`) —
        `store.journal` кладёт содержательный текст то в один столбец,
        то в другой (например `_maybe_autogate_acceptance` несёт саму
        причину отказа автогейта в `action`, не в `detail`)."""
        rows = store.task_steps(store.db(), self.TASK)
        return [f"{r['action']} {r['detail']}"
               for r in rows if r["id"] > since_id]

    # ------------------------------------------------------------- git

    def git_subcommands_since(self, since_index: int) -> list[str]:
        """Подкоманды `git` (первый argv, без учёта `-C`/`-c`) среди
        вызовов `git_spy`, сделанных ПОСЛЕ `since_index` (индекс в
        `self.git_spy.calls` на момент старта проверяемого действия)."""
        return [c[1] for c in self.git_spy.calls[since_index:]
               if len(c) > 1 and c[0] == "git"]
