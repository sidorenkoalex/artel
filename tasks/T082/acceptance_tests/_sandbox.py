"""Общая песочница приёмочных тестов T082 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

`RunnerSandbox` — дословный перенос обвязки `tests/test_agent_failure.py::
CmdRunFailureTest` (та же природа задачи: провал попытки шага агента,
ретраи, журнал) — код репозитория этой веткой трогать нельзя (роль
test_author), поэтому обвязка не импортируется оттуда напрямую (тестовый
файл `tests/` не является частью публичного API песочниц, в отличие от
`tests/sandbox.py`), а копируется сюда с минимальными правками под нужды
T082: сбор пауз бэкоффа, чтение открытых алертов, поиск по всему журналу
задачи (не только по одному action).

Классификатор ошибки (SPEC T082, требование 1) на момент написания этих
тестов ЕЩЁ НЕ РЕАЛИЗОВАН — `orchestrator/runner.py` разбирает попытку
только на «упала / не упала» (см. `tasks/T082/SPEC.md`, «Контекст»).
Тесты поэтому не зовут никакую функцию классификации напрямую (её ещё
нет и её будущее имя не часть контракта, который фиксирует SPEC) — они
проверяют НАБЛЮДАЕМЫЙ эффект классификации через единственную публичную
точку входа роли (`runner.cmd_run`), тем же приёмом, что уже применяет
`tests/test_agent_failure.py`: подменяется `runner.spawn_agent` списком
фейковых процессов, `runner.time.sleep` не спит, а запоминает паузы.
"""
import shutil
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, config, fsm, gitcmd, runner, store  # noqa: E402
from tests.sandbox import FakeProc, TmpRootTest, fake_git  # noqa: E402
from tests.sandbox import seed_developer_brief_fixtures, sync_spec_from_worktree  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK = "T001"


class RunnerSandbox(TmpRootTest):
    """Задача T001 на шаге `in_dev` (роль developer) с фейковым агентом.

    Дословно повторяет `tests/test_agent_failure.py::CmdRunFailureTest`
    (см. её докстринг для обоснования каждого патча) — эта копия нужна,
    потому что `tests/` не предмет импорта для приёмочных тестов задачи
    (SPEC test_author работает от `tasks/<id>/acceptance_tests/`).
    """

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")
    TASK = TASK

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        seed_developer_brief_fixtures(self.root)

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "T082 песочница")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()

        self.pauses = []
        patcher = mock.patch.object(runner.time, "sleep", self.pauses.append)
        patcher.start()
        self.addCleanup(patcher.stop)

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

    def run_agent(self, *attempts) -> str:
        """attempts: (rc, строки вывода) — по одной паре на попытку.

        Строки вывода — обычный текст (не события `stream-json`): не-JSON
        строка попадает в лог/журнал как есть (`agent_log.render_agent_line`),
        тем же приёмом, что уже использует `tests/test_agent_failure.py`.
        """
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs) as popen:
            out = self.capture(runner.cmd_run, self.TASK)
        self.popen = popen
        return out

    def journal_rows(self) -> list:
        return store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def journal_blob(self) -> str:
        """Весь журнал задачи (action + detail) одной строкой в нижнем
        регистре — для точечного поиска подстроки без предположений о
        том, в каком именно action её разместит реализация."""
        return "\n".join(f"{r['action']} | {r['detail']}"
                         for r in self.journal_rows()).lower()

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def open_alerts(self, kind: str | None = None) -> list:
        return alerts.open_alerts(store.db(), kind)

    def approve(self) -> str:
        """`approve` без sha — тем же приёмом, что и `tests/test_agent_failure.py
        ::CmdRunFailureTest.test_approve_returns_failed_dev_step_to_in_dev`:
        в лёгкой песочнице (`fake_git`) двухшаговая sha-сверка проходит
        одним вызовом."""
        return self.capture(fsm.cmd_approve, self.TASK)

    def last_log_text(self) -> str:
        logs = sorted(config.LOGS.glob(f"{self.TASK}-developer-*.log"))
        return logs[-1].read_text(encoding="utf-8") if logs else ""
