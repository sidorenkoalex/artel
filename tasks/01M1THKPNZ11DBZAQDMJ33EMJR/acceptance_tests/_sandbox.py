"""Общая песочница приёмочных тестов задачи 01M1THKPNZ11DBZAQDMJ33EMJR
(стоп-кран волны, часть 1 — счётчик класса отказа по волне и алерт).

Функции подсчёта/заведения алерта СЕГОДНЯ НЕ СУЩЕСТВУЕТ (SPEC, «Контекст»):
классификация отказа попытки (`failure_classification.py`) видна только по
одной задаче за раз, агрегатора нет вовсе. Тесты поэтому не зовут никакую
функцию подсчёта напрямую (её будущее имя не часть контракта, который
фиксирует SPEC — требование 3 называет только ДВЕ ТОЧКИ ВЫЗОВА в
`orchestrator/runner.py`, где механика будет подключена: журналирование
классифицированного отказа, `failure_classification.
_record_failure_classification`, и журналирование таймаута шага, запись
`"agent run TIMEOUT"`) — они проверяют НАБЛЮДАЕМЫЙ эффект через единственную
существующую публичную точку входа роли, `runner.cmd_run`, тем же приёмом,
что уже применяют `tasks/T082/acceptance_tests/_sandbox.py` и
`tests/test_agent_failure.py`.

id задачи — ULID (SPEC T094), не предсказуемая строка `"T001"`
(историческая песочница T082 хранит устаревший приём и сегодня падает —
проверено прогоном при подготовке этого файла): реальный id забирается
`capture_new_task_id`, тем же приёмом, что и текущий `tests/
test_agent_failure.py`.

`WaveBreakerSandbox.fail_class` гоняет `config.AGENT_ATTEMPTS` провальных
попыток подряд с одним и тем же текстом — задача уходит в `escalated`,
классификатор журналирует «agent failure classified» на каждой попытке
(разные события, ОДНА задача — то, что как раз нужно тестам AC-5).
`WaveBreakerSandbox.fail_timeout` — одна попытка, обрывающаяся таймаутом
(не ретраится, тем же приёмом, что `tests/test_agent_failure.py::
CmdRunFailureTest.test_timeout_is_not_retried`).

Заведение задачи внешнего target (AC-9) — тем же `catalog.cmd_new(...,
target=...)`, что и для self: `target` не проверяется против реестра
(`orchestrator/catalog.py::cmd_new` — `target = target or config.
DEFAULT_TARGET`, без сверки с `targets.yaml`), а дальнейший путь `run`
для НЕ-self target деградирует тихо там, где ему нечем ответить без
настоящего git (`artifact_branch.materialize_task_dir` — голова ветки не
резолвится под `fake_git`, AC-2 самой функции — тихая деградация), не
падает исключением — та же git-обвязка (`fake_git`/`disk_backed_show`/
`disk_backed_ls_tree_files`), что уже проверена рабочей для self target
существующими тестами `tests/test_agent_failure.py`, отрабатывает и здесь.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import (FakeProc, FakeStream, TmpRootTest,  # noqa: E402
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git,
                           seed_developer_brief_fixtures, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parents[3]

# Требование 3: буквальный маркер сообщения алерта стоп-крана волны —
# «стоп-кран волны: класс <класс> у N задач за M минут». Тесты ищут именно
# эту подстроку, не домысливая имя источника/kind, которое SPEC не называет.
WAVE_BREAKER_MARKER = "стоп-кран волны"


class WaveBreakerSandbox(TmpRootTest):
    """Песочница с фейковым агентом и настоящим `runner.cmd_run` — БД,
    задачи и логи во временном каталоге (тот же набор патчей, что и
    `tests/test_agent_failure.py::_AgentFailureTmpRootTest`)."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        import shutil
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        seed_developer_brief_fixtures(self.root)

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)
        self.capture(catalog.cmd_init)

        self.pauses = []
        sleep_patcher = mock.patch.object(runner.time, "sleep", self.pauses.append)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    # ------------------------------------------------------------ утилиты

    def new_task(self, title: str, *, target: str | None = None) -> str:
        """Заводит задачу на шаге `in_dev` (роль developer) — состояние,
        где падает попытка агента (тот же шаг, что уже несут все
        существующие тесты классификатора/таймаута, `tests/
        test_agent_failure.py`)."""
        _, task_id = capture_new_task_id(
            lambda: catalog.cmd_new(title, target=target))
        sync_spec_from_worktree(task_id)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (task_id,))
        conn.commit()
        return task_id

    def fail_class(self, task_id: str, text: str) -> str:
        """`config.AGENT_ATTEMPTS` провальных попыток подряд с тем же
        текстом — задача уходит в `escalated`, классификатор журналирует
        «agent failure classified» на каждой попытке (одна и та же
        задача, несколько событий — материал для AC-5)."""
        procs = [FakeProc([f"{text}\n"], 1) for _ in range(config.AGENT_ATTEMPTS)]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs):
            out = self.capture(runner.cmd_run, task_id)
        return out

    def fail_timeout(self, task_id: str) -> str:
        """Одна попытка, обрывающаяся таймаутом шага — не ретраится (тот
        же приём, что `tests/test_agent_failure.py::CmdRunFailureTest.
        test_timeout_is_not_retried`)."""
        proc = mock.Mock(stdout=FakeStream([]))
        proc.wait.side_effect = [
            runner.subprocess.TimeoutExpired(cmd="claude",
                                            timeout=config.AGENT_TIMEOUT_SEC),
            -9,
        ]
        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            out = self.capture(runner.cmd_run, task_id)
        return out

    def open_incident_alerts(self) -> list:
        return alerts.open_alerts(store.db(), "incident")

    def wave_breaker_alerts(self) -> list:
        """Алерты стоп-крана волны среди открытых `incident` — отличаются
        от прочих `incident` (например, `spend.unknown_cost` обрыва
        потока) буквальным маркером сообщения требования 3."""
        return [row for row in self.open_incident_alerts()
                if WAVE_BREAKER_MARKER in row["message"]]

    def task_row(self, task_id: str):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
