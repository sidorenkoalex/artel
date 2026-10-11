"""Общая песочница приёмочных тестов T087 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Позаимствована у `tasks/T053/acceptance_tests/_sandbox.py`
(`MergeQueueRealGitTest`) — тот же приём: НАСТОЯЩИЙ git (init + bare
origin-remote без сети) нужен, чтобы честно наблюдать сверку свежести
внутри `merge_gate` (T051-механика) и сам push нового head ветки задачи
в origin (SPEC T087, требование 1) — заглушкой `gitcmd.git` этого не
проверить (T053 «Материалы» приводит тот же довод).

Единственная точка, которую эта задача добавляет поверх T053: цикл
ожидания CI внутри `merge_gate` не должен реально ждать 60-120 секунд
между попытками и час до потолка (требования 3-4) — `setUp` глушит
`time.sleep` на весь класс (записывает длительность вызова, не спит),
а `install_fake_monotonic_clock` (используется только тестами потолка
ожидания — AC-4, AC-8) подменяет `time.monotonic` управляемым счётчиком.

Предположение о реализации (не факт SPEC): будущий код `fsm.py`
считает прошедшее время через `time.monotonic()`/паузу через
`time.sleep()` — тот же приём, что уже применяет `orchestrator/pause.py`
(`TERMINATE_GRACE_SEC`/`time.monotonic()`+`time.sleep()`) для похожей
задачи «пауза + потолок по времени». Это решение разработчика (SPEC не
называет конкретный API), но раз оно уже единственный прецедент в
кодовой базе для класса «пауза + потолок по времени», тесты потолка
ожидания (AC-4, AC-8) полагаются на него явно — см. докстринги этих
файлов.

`ci.branch_status` — единственная точка чтения статуса CI, которую зовёт
`fsm.py` (SPEC T087, требование 12, T082 «Материалы») — подменяется
напрямую последовательностью/функцией ответов, не сетевым `gh`.
"""
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, ci, config, fsm, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK = "T001"

SPEC_STUB = "# SPEC: заглушка песочницы T087\n"

PASSING_ACCEPTANCE_TEST = '''"""Маркер: заведомо зелёный приёмочный тест песочницы T087."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''

RUNNING = (False, "CI коммита abc12345 ещё идёт: python")
UNKNOWN = (False, "статус CI неизвестен: у коммита abc12345 нет ни одной проверки CI")
RED = (False, "CI коммита abc12345 не зелёный: python=failure")
GREEN = (True, "CI коммита abc12345 зелёный (1 проверок)")


def capture(fn, *args) -> str:
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FakeClock:
    """Счётчик для `time.monotonic`/`time.sleep`: `sleep(s)` продвигает
    значение `monotonic()` на `s` вместо настоящего ожидания — физически
    верная симуляция (сама природа sleep — продвижение часов), не
    угаданная константа. `sleep_calls` — длительности запрошенных пауз в
    порядке вызовов (AC-3: пауза 60-120 сек)."""

    def __init__(self, start: float = 0.0):
        self.value = start
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.value += seconds


class MergeGateCiWaitTest(unittest.TestCase):
    """Задача T001 в состоянии `acceptance` в свежем временном
    git-репозитории с настоящим bare-origin и настоящим worktree ветки
    задачи, готовая пройти `acceptance -> merge_gate -> done`.
    """

    TASK = TASK

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "shared.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.origin = bare

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-ci-wait"
        store.insert_task(store.db(), self.TASK, "approve ждёт CI после подтяжки",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # CI зелёный по умолчанию — тесты, которым нужен другой сценарий,
        # переопределяют `ci.branch_status` своей последовательностью
        # (`patch_branch_status`).
        self.patch_branch_status(lambda branch: GREEN)

        # Ни одна итерация цикла ожидания не имеет права ЗАСТАВИТЬ тест
        # реально ждать 60-120 сек / час (требования 3-4) — глушится на
        # весь класс; конкретное значение паузы читают тесты через
        # `self.clock.sleep_calls`, не жёстко прошитой константой.
        self.clock = FakeClock()
        sleep_patcher = mock.patch.object(time, "sleep", self.clock.sleep)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    # ------------------------------------------------------------ утилиты

    def install_fake_monotonic_clock(self) -> None:
        """Только для тестов потолка ожидания (AC-4, AC-8): подменяет
        `time.monotonic` тем же счётчиком, что уже двигает `time.sleep`
        (см. докстринг модуля) — элапсед внутри реализации считается
        честно от РЕАЛЬНО запрошенных пауз, без угадывания констант."""
        patcher = mock.patch.object(time, "monotonic", self.clock.monotonic)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_branch_status(self, fn) -> None:
        patcher = mock.patch.object(ci, "branch_status", fn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_trigger_rerun(self, fn=lambda branch: "ре-ран (тест)") -> None:
        patcher = mock.patch.object(ci, "trigger_rerun", fn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def make_worktree(self) -> Path:
        path = self.root / ".artel" / "worktrees" / self.TASK
        path.parent.mkdir(parents=True, exist_ok=True)
        self.git("worktree", "add", "-q", "-b", self.branch, str(path))
        tdir = path / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(SPEC_STUB, encoding="utf-8")
        return path

    def write_acceptance_test(self, wt_path: Path, content: str) -> None:
        acc_dir = wt_path / "tasks" / self.TASK / "acceptance_tests"
        acc_dir.mkdir(parents=True, exist_ok=True)
        (acc_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def commit_all(self, path: Path, message: str) -> str:
        self.git("add", "-A", cwd=path)
        self.git("commit", "-q", "-m", message, cwd=path)
        return self.head(path)

    def head(self, path=None) -> str:
        return self.git("rev-parse", "HEAD", cwd=path).stdout.strip()

    def main_head(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()

    def branch_head(self) -> str:
        return self.git("rev-parse", f"refs/heads/{self.branch}").stdout.strip()

    def origin_branch_sha(self) -> str:
        res = self.git("rev-parse", "--verify", "--quiet",
                       f"refs/heads/{self.branch}", cwd=self.origin, check=False)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_main_sha(self) -> str:
        return self.git("rev-parse", f"refs/heads/{config.MAIN_BRANCH}",
                        cwd=self.origin).stdout.strip()

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str,
                    cwd=None) -> bool:
        res = self.git("merge-base", "--is-ancestor", ancestor_sha,
                       descendant_sha, cwd=cwd, check=False)
        return res.returncode == 0

    def add_main_commit(self, name: str = "main-progress.txt",
                        content: str = "прогресс main\n") -> str:
        (self.root / name).write_text(content, encoding="utf-8")
        return self.commit_all(self.root, "прогресс main")

    def merge_lock_free(self) -> bool:
        return store.merge_lock_row(store.db()) is None

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows).lower()

    def approve(self) -> str:
        """Двухшаговое подтверждение sha (`confirm_fixation`/
        `APPROVE_NEEDS_SHA`), тем же приёмом, что T053/T052
        `_sandbox.py::approve`."""
        import re
        first = self.capture(fsm.cmd_approve, self.TASK)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, self.TASK, match.group(1))
        return first + second

    def enter_merge_gate(self) -> Path:
        """Заводит worktree, коммитит приёмочные тесты и переводит задачу
        `acceptance -> merge_gate` (ветка не отстала на этом шаге)."""
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        self.commit_all(wt, f"{self.TASK}: приёмочные тесты")
        self.approve()
        assert self.state() == "merge_gate", (
            f"предпосылка песочницы: вход на гейт обязан пройти, "
            f"состояние {self.state()!r}")
        return wt
