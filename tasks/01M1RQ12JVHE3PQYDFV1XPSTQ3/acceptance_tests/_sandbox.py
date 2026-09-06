"""Общая песочница приёмочной планки SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3.

Композиция уже проверенных песочниц `tests/test_agent_failure.py::
CmdRunFailureTest` (журнал/ретраи/эскалация исхода агентного шага) и
`tests/test_analyst_role.py` (TZ.md → роль analyst) — плюс работа с
диском РЕАЛЬНОГО рабочего каталога роли (`runner.role_cwd`, для self/
артели это git worktree задачи, SPEC T045), которого эта задача касается
напрямую и которого не было нужно трогать в тех песочницах.

Два разных адреса `tasks/<id>/` в этой песочнице (не путать):
- `config.TASKS/<id>/` — эмуляция АРТЕФАКТНОЙ ВЕТКИ пульта, читается
  `disk_backed_show`/`disk_backed_ls_tree_files` (см. их докстринги в
  `tests/sandbox.py`) — сюда пишут `sync_spec_from_worktree`/`write_tz`.
- `workspace.path(task_id)/tasks/<id>/` — РЕАЛЬНЫЙ рабочий каталог роли
  (`runner.role_cwd` для self/артели), куда в проде роль пишет свои
  артефакты инструментом Write. `FakeProc` в этих тестах не пишет на
  диск по-настоящему — `seed_role_artifact` кладёт файл сюда напрямую,
  имитируя «роль уже написала» ДО прогона шага.
"""
import shutil
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, gitcmd, runner, store, workspace  # noqa: E402
from tests.sandbox import (FakeProc, TmpRootTest, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git, seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

TASK_TITLE = "Бриф роли называет артефакты путём от рабочего каталога роли"


class RoleCwdSandbox(TmpRootTest):
    """Задача заведена (`cmd_new`), SPEC.md синхронизирован на диск-
    эмуляцию ветки (`config.TASKS`) — тем же приёмом, что и у
    `tests/test_agent_failure.py::CmdRunFailureTest`."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        seed_developer_brief_fixtures(self.root)

        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.capture(catalog.cmd_init)
        config.TASKS.mkdir(parents=True, exist_ok=True)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, TASK_TITLE)
        sync_spec_from_worktree(self.TASK)

        self.pauses = []
        sleep_patcher = mock.patch.object(runner.time, "sleep",
                                          self.pauses.append)
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

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_tz(self, raw: str = "Хотим починить путь артефакта в брифе.\n") -> None:
        """TZ.md задачи на диске-эмуляции ветки — делает роль analyst
        достижимой (`runner.step_role`, тот же приём, что `tests/
        test_analyst_role.py::_AnalystRoleTmpRootTest.write_tz`)."""
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "TZ.md").write_text(
            catalog._tz_document(self.TASK, TASK_TITLE, raw), encoding="utf-8")

    def role_workdir_task_dir(self) -> Path:
        """`tasks/<id>/` в РЕАЛЬНОМ рабочем каталоге роли — см. докстринг
        модуля (второй из двух адресов)."""
        return workspace.path(self.TASK) / "tasks" / self.TASK

    def seed_role_artifact(self, rel: str, text: str = "маркер\n") -> Path:
        """Кладёт файл в рабочий каталог роли ДО прогона шага — имитирует,
        что роль его уже написала (см. докстринг модуля)."""
        dest = self.role_workdir_task_dir() / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        return dest

    def run_agent(self, *attempts) -> str:
        """attempts: (rc, строки вывода) — по одной паре на попытку (тот
        же приём, что `tests/test_agent_failure.py::CmdRunFailureTest.
        run_agent`); лишние заготовки, не понадобившиеся при раннем
        успешном возврате `cmd_run`, просто не расходуются."""
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs) as popen:
            out = self.capture(runner.cmd_run, self.TASK)
        self.popen = popen
        return out

    def prompt_text(self) -> str:
        return Path(self.popen.call_args.kwargs["stdin"].name).read_text(
            encoding="utf-8")

    def journal_details(self, action: str | None = None) -> list[str]:
        if action is None:
            rows = store.db().execute(
                "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
                (self.TASK,))
        else:
            rows = store.db().execute(
                "SELECT detail FROM steps WHERE task_id=? AND action=? "
                "ORDER BY id", (self.TASK, action))
        return [r["detail"] for r in rows]

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()
