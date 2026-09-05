"""AC-6 (tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md): пометка ревью-пакета
«diff не собран» на итерации > 1 поднимает Оператору алерт `kind=warning`
(вместо тихой строки журнала — требование 3 SPEC); алерт авто-
подтверждается, когда diff следующего сбора пакета той же задачи собран
успешно.

Красен до реализации: сегодня `runner.cmd_run` только журналирует «ревью-
пакет собран» с пометкой `diff не собран: <причина>» (`orchestrator/
review.py::package_note`) — НИКАКОГО алерта не заводит; `alerts.KINDS`
даже не содержит `"warning"`, так что вызов `alerts.raise_alert(...,
"warning", ...)` где бы то ни было сегодня закончился бы `ValueError`.
Сквозной прогон через `runner.cmd_run` (не вызов гипотетической функции
по имени) — этот класс поведения целиком новый, у него ещё нет
устоявшегося места в коде, которое можно было бы дёрнуть напрямую.
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import alerts, catalog, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import FakeProc, SpyRun, capture, capture_new_task_id  # noqa: E402

FORM_MD = """---
task: T000
type: review
author_role: reviewer
status: draft
---

# REVIEW: <заголовок>

## Замечания
"""


class ToggleDiffGit:
    """`gitcmd.git`: `show` отдаёт заготовленные файлы, `diff` — успех или
    отказ в зависимости от `self.broken` (переключается тестом МЕЖДУ
    двумя прогонами `cmd_run`)."""

    def __init__(self, files: dict):
        self.files = dict(files)
        self.broken = True

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        if args and args[0] == "show":
            _, rel = args[1].split(":", 1)
            if rel not in self.files:
                return subprocess.CompletedProcess(
                    list(args), 128, "",
                    f"fatal: path '{rel}' does not exist in '{args[1]}'")
            return subprocess.CompletedProcess(list(args), 0, self.files[rel], "")
        if args and args[0] == "ls-tree":
            return subprocess.CompletedProcess(list(args), 0, "", "")
        if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
                and args[-1].startswith("refs/heads/")):
            return subprocess.CompletedProcess(list(args), 1, "", "")
        if args and args[0] == "rev-parse":
            return subprocess.CompletedProcess(list(args), 0, "", "")
        if args and args[0] == "diff":
            if self.broken:
                return subprocess.CompletedProcess(list(args), 1, "", "fatal: bad revision")
            stdout = "orchestrator/artel.py | 2 +-" if "--stat" in args else "diff --git a b"
            return subprocess.CompletedProcess(list(args), 0, stdout, "")
        if args[:2] == ("config", "--get"):
            return subprocess.CompletedProcess(list(args), 0, "test\n", "")
        return subprocess.CompletedProcess(list(args), 0, "", "")


class DiffNotCollectedAlertTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in ("skills", "templates"):
            shutil.copytree(_REPO_ROOT / name, root / name)
        for attr, value in (("ROOT", root),
                            ("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        skill_files = {f"skills/{p.name}": p.read_text(encoding="utf-8")
                       for p in (root / "skills").glob("*.md")}
        self.git = ToggleDiffGit(files={"templates/REVIEW.md": FORM_MD, **skill_files})
        git_patcher = mock.patch.object(gitcmd, "git", self.git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        wt_patcher = mock.patch.object(
            runner.workspace, "ensure", lambda task_id, branch: (root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "AC-6 diff не собран")
        self.conn = store.db()
        # Итерация 2 у следующего запуска роли `review` (`role_prompt.
        # mission_brief_package`: `iteration = t["reviewed_iter"] + 1`) —
        # без реального цикла FSM approve/reject, напрямую (SQL, не
        # `store.set_state`): AC-6 проверяет пометку/алерт при iteration >
        # 1, не сам механизм подсчёта итераций (уже покрыт T079,
        # `tests/test_review_freshness.py`) — и НЕ трогает `fixed_sha`
        # (остаётся NULL), так что `fixation.check_integrity` в начале
        # `cmd_run` пропускает шаг без сверки («фиксации ещё нет»).
        self.conn.execute(
            "UPDATE tasks SET state='review', reviewed_iter=1 WHERE id=?",
            (self.TASK,))
        self.conn.commit()

    capture = staticmethod(capture)

    def run_review_step(self) -> None:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            self.capture(runner.cmd_run, self.TASK)

    def open_warning_alerts(self) -> list:
        return [r for r in alerts.open_alerts(store.db(), "warning")
               if r["target"] == self.TASK]

    def test_ac6_uncollected_diff_at_iteration_gt_1_raises_a_warning_alert(self):
        """Первый прогон шага `review` итерации 2 с заведомо сломанным
        `git diff` — пакет несёт пометку «diff не собран» (существующее
        поведение, T011), и ЭТА пометка обязана поднять Оператору алерт
        `kind=warning`, привязанный к задаче.

        Ловит мутацию: алерт не заводится вовсе (сохранено старое
        поведение — тихая строка журнала) или заводится не тем `kind`
        (например, остаётся `incident`) — `open_warning_alerts()`
        останется пустым.
        """
        self.git.broken = True

        self.run_review_step()

        details = [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, "ревью-пакет собран")).fetchall()]
        self.assertEqual(len(details), 1)
        self.assertIn("diff не собран", details[0], "предпосылка теста не выполнена")

        opened = self.open_warning_alerts()
        self.assertEqual(len(opened), 1)
        self.assertIn(self.TASK, opened[0]["message"])

    def test_ac6_alert_auto_confirms_once_the_next_collection_succeeds(self):
        """После первого (сломанного) прогона — второй прогон того же шага
        с ПОЧИНЕННЫМ `git diff`: пакет больше не несёт пометку «diff не
        собран», и ранее открытый алерт `kind=warning` обязан
        подтвердиться сам, без участия Оператора.

        Ловит мутацию: авто-подтверждение не реализовано (алерт остаётся
        открытым вечно) — `open_warning_alerts()` после второго прогона
        всё ещё вернёт запись.
        """
        self.git.broken = True
        self.run_review_step()
        self.assertEqual(len(self.open_warning_alerts()), 1, "предпосылка не выполнена")

        self.git.broken = False
        self.run_review_step()

        details = [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, "ревью-пакет собран")).fetchall()]
        self.assertEqual(len(details), 2)
        self.assertNotIn("diff не собран", details[1], "предпосылка не выполнена")

        self.assertEqual(self.open_warning_alerts(), [],
                         "алерт не подтвердился сам после успешного сбора diff")


if __name__ == "__main__":
    unittest.main()
