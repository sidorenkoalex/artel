"""Общая песочница приёмочных тестов 01M2B6K02YVJBWE1JDWP85EJH0 (канарейка
на целевом sha).

Расширяет `tests.sandbox.RealGitSandbox` (настоящий git-репозиторий
пульта, ветка main, один коммит) — не переизобретает её (conventions-
core/test-authoring: «лёгкая песочница переходов — не копия, импорт»)
— двумя вещами, специфичными именно для этой задачи:

1. Настоящий bare `origin` (тот же приём, что `tasks/
   01M1NGFK3N6MRMYGCC09H975V3/acceptance_tests/_sandbox.py::
   CanaryPinSandbox`), плюс `advance_origin_only` — способ увести
   `origin/<MAIN_BRANCH>` ВПЕРЁД локального `main`, НЕ трогая сам
   локальный `main` (через отдельный вспомогательный клон origin,
   пушащий туда прямо, минуя `self.root`). Это ровно сценарий из
   SPEC/Контекст: «правка ушла в `origin/main`, но не в пин (`HEAD`
   главной копии)» — предпосылка AC-1/AC-8 (пометка «код origin/main»).

2. `run_cmd_canary` — прогон `canary.cmd_canary(k=1, sha=...)` с
   пулом ровно из одного шаблона, `_drive_task` заменена синтетическим
   шагом `_kill_at_merge_gate` (штатный, «зелёный» путь канарейки —
   тот же приём, что `tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
   test_canary_report_kill_reason.py::RunOneTaskKillReasonReportTest`),
   опционально снимающая HEAD эфемерного клона В МОМЕНТ вождения задачи
   (когда `config.ROOT` уже указывает на клон, `_ephemeral_clone`) —
   единственный способ узнать, на каком именно sha остался checkout,
   не домысливая внутреннее имя параметра/функции реализации.
"""
import io
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402


class TargetShaCanarySandbox(RealGitSandbox):
    """`self.root` — пульт (main + ДВА коммита, `self.root_sha`/
    `self.head_sha()` — см. ниже) + настоящий bare `self.origin`,
    синхронный с main на момент `setUp`."""

    def setUp(self):
        super().setUp()
        self.root_sha = self.head_sha()
        # Второй локальный коммит поверх `RealGitSandbox.setUp`'овского
        # «init» — без него единственный коммит песочницы одновременно
        # был бы и HEAD, и единственным доступным «предком, отличным от
        # HEAD» для сценариев AC-2/AC-8 (явный `--sha` обязан отличаться
        # от текущего HEAD, чтобы проверка вообще что-то различала).
        (self.root / "second.txt").write_text("second\n", encoding="utf-8")
        self.git("add", "second.txt")
        self.git("commit", "-q", "-m", "second")

        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.origin)], check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

        tmp_tpl = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_tpl.cleanup)
        self.pool_home = Path(tmp_tpl.name)
        (self.pool_home / config.CANARY_POOL_DIRNAME).mkdir()
        home_patcher = mock.patch.object(Path, "home",
                                         return_value=self.pool_home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)
        self._write_pool_template("t1.md")

    # --- git -------------------------------------------------------------

    def head_sha(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def origin_head_sha(self) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "rev-parse",
             "refs/heads/" + config.MAIN_BRANCH],
            capture_output=True, text=True)
        return res.stdout.strip() if res.returncode == 0 else ""

    def advance_origin_only(self, name: str = "upstream-work") -> str:
        """Пушит новый коммит прямо в `self.origin`, МИНУЯ `self.root` —
        локальный `main` (`gitcmd.head_sha()`) остаётся на месте, а
        `origin/<MAIN_BRANCH>` уходит вперёд (см. докстринг класса, п.1).
        Возвращает новый sha `origin/<MAIN_BRANCH>`."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        clone_dir = Path(tmp.name) / "upstream-clone"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(clone_dir)],
                       check=True, capture_output=True, text=True)
        (clone_dir / f"{name}.txt").write_text("upstream\n", encoding="utf-8")
        subprocess.run(["git", "add", f"{name}.txt"], cwd=clone_dir, check=True,
                       capture_output=True, text=True)
        subprocess.run(["git", "commit", "-q", "-m", name], cwd=clone_dir,
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "push", "-q", "origin", config.MAIN_BRANCH],
                       cwd=clone_dir, check=True, capture_output=True, text=True)
        return self.origin_head_sha()

    # --- пул шаблонов ------------------------------------------------------

    def _write_pool_template(self, name: str) -> Path:
        path = self.pool_home / config.CANARY_POOL_DIRNAME / name
        path.write_text("# ТЗ\n\nсодержимое канареечного шаблона.\n",
                        encoding="utf-8")
        return path

    # --- прогон cmd_canary с синтетическим (зелёным) вождением -----------

    @staticmethod
    def _mark_killed(task_id: str) -> None:
        store.update_task(store.db(), task_id, state="killed")

    def run_cmd_canary(self, *, sha=None, capture_clone_head=False):
        """Зовёт `canary.cmd_canary(k=1[, sha=sha])` с одним шаблоном пула;
        `_drive_task` заменена синтетическим штатным путём
        (`_kill_at_merge_gate` — задача считается «штатно», verdict
        `green`); `catalog.cmd_new`/`workspace.ensure`/`_ephemeral_clone` —
        настоящие (реальный git). Возвращает `(stdout_текст,
        captured_dict)`; `captured_dict['clone_head']` — sha, на котором
        реально стоял checkout эфемерного клона В МОМЕНТ вождения
        задачи, если `capture_clone_head=True`."""
        captured = {}

        def fake_drive(conn, task_id):
            if capture_clone_head:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=config.ROOT,
                    capture_output=True, text=True)
                captured["clone_head"] = res.stdout.strip()
            canary._kill_at_merge_gate(conn, task_id)

        with mock.patch.object(
                canary.cleanup, "cmd_kill",
                side_effect=lambda tid: self._mark_killed(tid)), \
             mock.patch.object(canary, "_drive_task", side_effect=fake_drive):
            buf = io.StringIO()
            with redirect_stdout(buf):
                if sha is None:
                    canary.cmd_canary(k=1)
                else:
                    canary.cmd_canary(k=1, sha=sha)
            return buf.getvalue(), captured

    def latest_canary_run(self):
        conn = store.db()
        return conn.execute(
            "SELECT * FROM canary_runs ORDER BY id DESC LIMIT 1").fetchone()


if __name__ == "__main__":
    import unittest
    unittest.main()
