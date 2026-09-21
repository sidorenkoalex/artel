"""Общая обвязка планки 01M31ZHSA6HMH40C2JTDPQJQNZ: песочница ШАГА —
`runner.cmd_run` на поддельном процессе агента.

Не тест: общий код нескольких файлов планки живёт только в модулях
`_*.py` рядом с тестами (skills/test-authoring.md).

Почему через `cmd_run`, а не прямым вызовом `spend.charge_step`: поля
`model=`/`provider=` строки стоимости приписывает точка завершения шага
(`orchestrator/runner.py::_numbered_with_model`), а не сам `spend.py` —
прямой вызов проверял бы строку, которой пульт в работе не пишет
(AC-13), и не увидел бы ни выбора ветки учёта, ни провайдера роли шага
(AC-8, AC-9). Песочница — готовая `tests.sandbox.DeveloperBriefTmpRootTest`
(временные пути `config`, шаблоны/скилы репозитория, фикстуры брифа), а
не собственная копия чего-либо из `tests/sandbox.py`.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (agent_log, catalog, config, gitcmd,  # noqa: E402
                          runner, spend, store)
from tests.sandbox import (DeveloperBriefTmpRootTest,  # noqa: E402
                           FakeProc, FakeStream, capture_new_task_id,
                           fake_git, sync_spec_from_worktree)

import _sample  # noqa: E402

#: Действия журнала стоимости шага — литералами SPEC (требования 4-6):
#: `spend.KNOWN_COST_JOURNAL_ACTION` планка берёт из кода, остальные
#: четыре в коде именованных констант не имеют.
KNOWN = spend.KNOWN_COST_JOURNAL_ACTION
PARTIAL = "agent cost PARTIAL"
UNKNOWN = "agent cost UNKNOWN"
ESTIMATED = "agent cost ESTIMATED"
LOST = "agent cost LOST"

#: Текст «источник=…» строки стоимости: факт CLI против расчёта по
#: тарифу (SPEC требование 4, AC-9/AC-10).
SOURCE_CLI = "источник=факт CLI"
SOURCE_TARIFF = "источник=расчёт по тарифу"


def timeout_then_killed_proc(lines) -> mock.Mock:
    """Процесс, чей `wait()` сперва бросает `TimeoutExpired`, — таймаут
    шага без единого ретрая (тот же приём, что у
    `tests/test_step_cost.py::timeout_then_killed_proc`; копия здесь
    потому, что планка не импортирует тесты пульта, а только их
    песочницу)."""
    proc = mock.Mock(stdout=FakeStream(lines))
    proc.wait.side_effect = [
        runner.subprocess.TimeoutExpired(cmd="claude",
                                         timeout=config.AGENT_TIMEOUT_SEC),
        -9,
    ]
    return proc


class StepRunSandbox(DeveloperBriefTmpRootTest):
    """Временный пульт с одной задачей в `in_dev`: `self.run_stream()`
    прогоняет шаг роли `developer` на заготовленных строках вывода."""

    ROLE = _sample.ROLE

    def setUp(self):
        super().setUp()
        # Патч git ДО `cmd_new` (SPEC T048): он сам заводит ветку и
        # worktree через `gitcmd`, без фейка ушёл бы в реальный
        # репозиторий пульта.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Вывод, стоимость и провалы у провайдера")
        sync_spec_from_worktree(self.TASK)
        self.set_task(state="in_dev", budget_usd=100.0)

        # Обязательный артефакт роли developer (SPEC
        # 01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 3): без него успешная
        # попытка честно ретраится, а планке нужен один прогон.
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

        for target, attr, value in (
                (runner.time, "sleep", lambda _: None),
                (runner.keychain, "token", lambda slot: "tok-test")):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        pf_patcher = mock.patch("orchestrator.doctor.preflight_checks",
                                lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        self.conn = store.db()

    # --- управление задачей ------------------------------------------

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    # --- прогон шага --------------------------------------------------

    def run_stream(self, lines, rc: int = 0) -> str:
        """Один прогон шага на заготовленных строках вывода агента."""
        proc = FakeProc(list(lines), rc)
        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            return self.capture(runner.cmd_run, self.TASK)

    def run_timeout(self, lines) -> str:
        """Прогон, оборвавшийся таймаутом шага: финального события потока
        нет, промежуточные usage-события уже пришли."""
        proc = timeout_then_killed_proc(list(lines))
        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            return self.capture(runner.cmd_run, self.TASK)

    # --- наблюдаемое --------------------------------------------------

    def details(self, action: str) -> list:
        return [row["detail"] for row in store.task_steps(self.conn, self.TASK)
                if row["action"] == action]

    def actions(self) -> list:
        return [row["action"] for row in store.task_steps(self.conn, self.TASK)]

    def journal_text(self) -> str:
        return "\n".join(f"{row['action']} | {row['detail']}"
                         for row in store.task_steps(self.conn, self.TASK))

    def alerts(self) -> list:
        return store.db().execute("SELECT * FROM alerts").fetchall()

    def log_text(self) -> str:
        path = agent_log.last_agent_log(self.TASK, self.ROLE)
        return Path(path).read_text(encoding="utf-8") if path != "—" else ""

    def friction(self) -> float:
        values = self.details(agent_log.FRICTION_JOURNAL_ACTION)
        return float(values[-1]) if values else None
