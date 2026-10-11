"""Общая песочница приёмочных тестов T086 (не `test_*.py` — не подхватывается
`unittest discover` напрямую, только импортом из `test_ac*.py`, тем же
приёмом, что `tasks/T079/acceptance_tests/_sandbox.py`, чей предмет —
непосредственный предшественник этой задачи: состояние `verifying`,
маршрут `review -> verifying -> acceptance`, различение исходов CI через
`ci.verifying_status`).

`VerifyingTest(FsmTest)` — задача T001 в состоянии `verifying`
(`tests.test_invariants.FsmTest`: БД и артефакты во временном каталоге,
git и `gh` не исполняются по-настоящему — `SpyRun`, унаследованный от
`FsmTest`, перехватывает ЛЮБОЙ `subprocess.run` git-процесса; `ci.gh`/
`ci.head_sha` подменяются напрямую `set_ci_dual`, тем же приёмом, что и
T079). Небезопасно было бы гонять эти тесты без глобального перехвата —
код цикла `auto` в `verifying` (требование 1 SPEC этой задачи) ещё не
существует, и случайный настоящий вызов `gh`/`git`, попади он в реальный
`subprocess.run`, ушёл бы на настоящий GitHub настоящим токеном
разработчика.

## Опрос без ожидания реальных секунд — «губернатор» цикла

Требование 1 SPEC заводит паузу МЕЖДУ повторными опросами внутри одного
вызова `auto` — при незелёном и незавершённо-красном CI опрос не
заканчивается сам, значит без внешнего ограничителя тест либо звал бы
`time.sleep` по-настоящему (десятки минут одного прогона), либо завис
бы навсегда (CI фикстуры теста намеренно никогда не становится зелёным).

`install_sleep_pause_governor` патчит ГЛОБАЛЬНЫЙ `time.sleep` (не
`auto.time`/`fsm.time` — SPEC не называет, в каком модуле будет жить
пауза, а `import time; time.sleep(x)` — сквозной приём уже существующего
кода, `orchestrator/runner.py::cmd_run`, и патч самого модуля `time`
ловит вызов независимо от того, куда именно ляжет `import time` новой
реализации; риск не сработать есть только при `from time import sleep`,
чего нигде в кодовой базе сегодня нет). Каждый вызов patched-`sleep`
запоминает переданную длительность и, начиная с `stop_after`-го вызова,
бросает `LoopGoverned` — не сбой теста, а управляемая точка остановки
бесконечного (по конструкции фикстуры) цикла; тест ожидает именно это
исключение через `assertRaises`.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import ci, runner, store  # noqa: E402
from tests.test_invariants import FAKE_SHA, FsmTest  # noqa: E402


def _check_runs(runs: list) -> str:
    return json.dumps({"total_count": len(runs), "check_runs": runs})


# Четыре исхода `ci.verifying_status` (SPEC T079, не меняются этой задачей
# — требование 2 SPEC T086 «трактовка исходов опроса CI не меняется»).
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


class LoopGoverned(Exception):
    """Сигнал остановки теста, не сбой: см. докстринг модуля."""


def _no_agent_role_here(task_id, session_id=None):
    raise AssertionError(
        f"cmd_run вызван для {task_id} — ни verifying, ни прочие "
        f"состояния этого свипа не несут агентной роли (STATE_ROLE), "
        f"агент не имеет права стартовать")


class VerifyingTest(FsmTest):
    """`FsmTest` + управление CI-фикстурой `verifying` и «губернатор» пауз.

    `runner.cmd_run` патчится на бросок `AssertionError` при любом вызове
    (не остаётся настоящей, в отличие от `FsmTest`): все состояния этого
    набора тестов — `verifying` и прочие без агентной роли (AC-9) — не
    имеют права звать агента вовсе. Оставь `FsmTest` эту точку настоящей —
    баг реализации, вызывающий агента из `verifying`, породил бы
    настоящий `subprocess.Popen` внешнего CLI без сети/токена и повесил
    бы прогон, а не упал бы читаемым сообщением.
    """

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(runner, "cmd_run", _no_agent_role_here)
        patcher.start()
        self.addCleanup(patcher.stop)

    def enter_verifying(self, check_runs_json: str = GREEN_RUNS,
                        run_list_json: str = NO_RUN_LIST) -> None:
        self.set_state("verifying")
        self.set_ci_dual(check_runs_json, run_list_json)

    def set_ci_dual(self, check_runs_json: str,
                    run_list_json: str = NO_RUN_LIST) -> None:
        """Ответ `gh` по двум источникам (check-runs коммита / `gh run
        list` ветки, requirement 5 SPEC T079) + запись сырых argv в
        `self.gh_calls` (AC-10: опрос не имеет права дёрнуть ничего,
        кроме чтения — `rerun`/`workflow`/`dispatch` в argv не появится)."""
        self.gh_calls: list[tuple] = []

        def gh(*args: str) -> subprocess.CompletedProcess:
            self.gh_calls.append(args)
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

    def install_sleep_pause_governor(self, stop_after: int) -> list:
        """Патчит глобальный `time.sleep`: копит длительности, после
        `stop_after`-го вызова бросает `LoopGoverned` (см. докстринг
        модуля). Возвращает список фактически переданных длительностей —
        растёт и после того, как тест поймал исключение, вплоть до
        последнего (стоп-)вызова включительно."""
        pauses: list = []

        def fake_sleep(seconds):
            pauses.append(seconds)
            if len(pauses) >= stop_after:
                raise LoopGoverned(
                    f"губернатор теста остановил цикл после {stop_after} "
                    f"пауз опроса — цикл сам не думал останавливаться")

        patcher = mock.patch("time.sleep", fake_sleep)
        patcher.start()
        self.addCleanup(patcher.stop)
        return pauses

    def install_verifying_status_spy(self) -> list:
        """Считает вызовы `ci.verifying_status`, не меняя её поведение
        (реальная функция по-прежнему читает CI-фикстуру из `set_ci_dual`).
        AC-8: ручной `advance` обязан опросить статус РОВНО один раз."""
        calls: list = []
        original = ci.verifying_status

        def spy(branch):
            calls.append(branch)
            return original(branch)

        patcher = mock.patch.object(ci, "verifying_status", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def age_verifying_entry(self, ago: timedelta) -> None:
        """Отодвигает `tasks.updated_at` в прошлое — симулирует момент
        входа в `verifying` `ago` назад (требование 3 SPEC: потолок
        считается от `updated_at` перехода `-> verifying`, не от числа
        `advance`). Формат — тот же, что пишет `store.set_state`
        (`orchestrator/store.py`, с точностью до микросекунд)."""
        stamp = (datetime.now(timezone.utc) - ago).strftime(
            "%Y-%m-%d %H:%M:%S.%fZ")
        conn = store.db()
        conn.execute("UPDATE tasks SET updated_at=? WHERE id=?",
                     (stamp, self.TASK))
        conn.commit()

    # ------------------------------------------------------------ журнал

    def last_step_id(self) -> int:
        rows = store.task_steps(store.db(), self.TASK)
        return rows[-1]["id"] if rows else 0

    def journal_details_since(self, since_id: int) -> list[str]:
        """Строки журнала (`action` + `detail`, не только `detail`) —
        `store.journal` кладёт содержательный текст то в один столбец,
        то в другой."""
        rows = store.task_steps(store.db(), self.TASK)
        return [f"{r['action']} {r['detail']}"
               for r in rows if r["id"] > since_id]

    # ------------------------------------------------------------- git

    def git_subcommands_since(self, since_index: int) -> list[str]:
        """Подкоманды `git` (первый argv, без учёта `-C`/`-c`) среди
        вызовов `git_spy`, сделанных ПОСЛЕ `since_index`."""
        return [c[1] for c in self.git_spy.calls[since_index:]
               if len(c) > 1 and c[0] == "git"]
