"""Тонкая надстройка лёгкой песочницы переходов над эталонной
`tests/sandbox.py::LightTransitionSandbox` (skills/test-authoring.md) для
планки задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — не `test_*.py`,
подхватывается только импортом из `test_ac*.py`.

Своего `disk_backed_*`/`advance_from_in_dev` здесь нет: диск как
источник артефактов, поддельный `gitcmd.git`, worktree временным
подкаталогом — всё из импортированной эталонной песочницы. Надстройка —
ровно три вещи, которых у эталона нет и которые нужны именно этому
сценарию:

- поддельный прогон pytest (`PytestRunStub`): `acceptance.run_full_suite`
  зовёт `subprocess.run` НАПРЯМУЮ, и заглушка обязана отвечать только
  на pytest-команды, а остальные (git) пробрасывать в уже поставленный
  `TmpRootTest.git_spy` — иначе второй патч того же `subprocess.run`
  отобрал бы git у всей песочницы;
- worktree задачи, стоящий на её ветке (`workspace.on_task_branch`/
  `workspace.path`) с каталогом `tests/` внутри — без него прогон
  полного набора не запускается вовсе;
- `gates.yaml` с политикой `acceptance: auto` в корне песочницы —
  настоящим файлом, тем же путём, которым его читает `gates.policy`,
  а не патчем самой политики.
"""
import io
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artel, config, fsm, fsm_autogate,  # noqa: E402
                          store, workspace)
from tests.sandbox import LightTransitionSandbox  # noqa: E402

GATES_AUTO_ACCEPTANCE = "gates:\n  acceptance: auto\n  merge_gate: manual\n"


def capture_exit(fn, *args) -> tuple[str, str]:
    """(stdout, текст `SystemExit`) — `tests.sandbox.capture` исключения
    не ловит, а именованный отказ команды в этом пульте — именно
    `sys.exit("…")`. Отказа не было — вторым элементом пустая строка."""
    buf = io.StringIO()
    exit_text = ""
    with redirect_stdout(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            exit_text = str(exc.code) if exc.code is not None else ""
    return buf.getvalue(), exit_text


class PytestRunStub:
    """Подмена `subprocess.run` для модуля `orchestrator.acceptance`:
    pytest-команда отвечает заданным исходом, всё остальное уходит в
    `fallback` (спай git эталонной песочницы)."""

    def __init__(self, fallback):
        self.fallback = fallback
        self.stdout = ""
        self.stderr = ""
        self.returncode = 0
        self.timeout_sec = None
        self.calls: list = []

    @staticmethod
    def _is_pytest(cmd) -> bool:
        return any("pytest" in str(part) for part in cmd)

    def __call__(self, cmd, *args, **kwargs):
        if not self._is_pytest(cmd):
            return self.fallback(cmd, *args, **kwargs)
        self.calls.append(list(cmd))
        if self.timeout_sec is not None:
            raise subprocess.TimeoutExpired(list(cmd), self.timeout_sec,
                                            output=self.stdout,
                                            stderr=self.stderr)
        return subprocess.CompletedProcess(list(cmd), self.returncode,
                                           self.stdout, self.stderr)


class FullSuiteSandbox(LightTransitionSandbox):
    """Задача `self.TASK` с планкой приёмки на диске, заведённым worktree
    на своей ветке и поддельным прогоном полного набора."""

    TASK_TITLE = "Автогейт приёмки называет упавшие тесты"

    def setUp(self):
        super().setUp()
        self.write_acceptance_plank()
        (config.ROOT / "gates.yaml").write_text(GATES_AUTO_ACCEPTANCE,
                                                encoding="utf-8")

        self.tests_dir = self.wt_path / "tests"
        self.tests_dir.mkdir(parents=True, exist_ok=True)

        self.pytest_run = PytestRunStub(self.git_spy)
        run_patcher = mock.patch.object(acceptance.subprocess, "run",
                                        self.pytest_run)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

        self.on_task_branch = True
        branch_patcher = mock.patch.object(
            workspace, "on_task_branch",
            side_effect=lambda *a, **kw: self.on_task_branch)
        branch_patcher.start()
        self.addCleanup(branch_patcher.stop)
        path_patcher = mock.patch.object(workspace, "path",
                                         side_effect=lambda *a: self.wt_path)
        path_patcher.start()
        self.addCleanup(path_patcher.stop)

        config.LOGS.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------- исход прогона набора

    def set_red_run(self, output: str) -> None:
        self.pytest_run.returncode = 1
        self.pytest_run.stdout = output
        self.pytest_run.timeout_sec = None

    def set_green_run(self, output: str = "306 passed in 70.11s\n") -> None:
        self.pytest_run.returncode = 0
        self.pytest_run.stdout = output
        self.pytest_run.timeout_sec = None

    def set_timeout_run(self, output: str = "") -> None:
        """Прогон, не уложившийся в `config.FULL_SUITE_TIMEOUT_SEC` —
        предпосылка берётся от config, не литералом."""
        self.pytest_run.stdout = output
        self.pytest_run.timeout_sec = config.FULL_SUITE_TIMEOUT_SEC

    def drop_tests_dir(self) -> None:
        shutil.rmtree(self.tests_dir)

    # ------------------------------------------------------- логи и журнал

    def log_files(self) -> list:
        return sorted(p for p in config.LOGS.glob("*.log") if p.is_file())

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_blobs(self) -> list[str]:
        return [f"{r['action']} {r['detail'] or ''}" for r in self.journal_rows()]

    def journal_blob(self) -> str:
        return "\n".join(self.journal_blobs())

    # ------------------------------------------------------------- автогейт

    def autogate(self) -> str:
        """`fsm_autogate._maybe_autogate_acceptance` из состояния
        `acceptance` — единственная точка входа задачи в автогейт."""
        self.set_state("acceptance")
        conn = store.db()
        return self.capture(fsm_autogate._maybe_autogate_acceptance, conn,
                            self.TASK, self.task_row(), self.tdir, 1)

    def autogate_refusal_detail(self) -> str:
        """detail записи «автогейт acceptance не пройден» последнего
        прогона; пустая строка — такой записи не было."""
        rows = [r for r in self.journal_rows()
                if "автогейт" in r["action"] and "не пройден" in r["action"]]
        return (rows[-1]["detail"] or "") if rows else ""

    def checklist_detail(self) -> str:
        """detail единой записи «приёмка: что проверит approve»."""
        conn = store.db()
        return fsm_autogate._acceptance_checklist_detail(
            conn, self.TASK, self.task_row(), 1)


class ApproveAcceptanceSandbox(FullSuiteSandbox):
    """`FullSuiteSandbox` + `approve` из состояния `acceptance` командной
    строкой пульта (`artel.main`).

    Сверка фиксации и подтяжка main замоканы: предмет этих тестов — то,
    что `approve` делает с полным набором tests/, а не фиксация артефактов
    (`confirm_fixation`) и не свежесть ветки (`_pull_main_or_escalate`,
    своя песочница в `tests/test_branch_freshness_gate.py`). Побочные
    эффекты входа в `merge_gate` (снимок объёма, undraft Draft MR,
    подсказка sha) замоканы тем же доводом — они не условия перехода.
    """

    def setUp(self):
        super().setUp()
        for target, attr, kwargs in (
                (fsm, "confirm_fixation", {"return_value": True}),
                (fsm, "_pull_main_or_escalate", {"return_value": "fresh"}),
                (fsm, "_snapshot_split_assessment", {}),
                (fsm.github_adapter, "undraft_mr", {}),
                (fsm.fixation, "approve_sha_hint", {"return_value": ""}),
        ):
            patcher = mock.patch.object(target, attr, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.set_state("acceptance")

    def approve_cli(self, *args: str) -> tuple[str, str]:
        """`artel.py approve <id> [args…]` через настоящий диспетчер
        (`artel.main`) — разбор аргументов команды `approve` входит в
        предмет проверки (SPEC требование 8), поэтому не в обход его."""
        argv = ["artel.py", "approve", self.TASK, *args]
        with mock.patch.object(sys, "argv", argv):
            return capture_exit(artel.main)


if __name__ == "__main__":
    unittest.main()
