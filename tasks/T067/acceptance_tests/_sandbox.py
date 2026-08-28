"""Общая песочница приёмочных тестов T067 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Авторазрешение конфликта подтяжки `docs/codebase-map.md`
(`orchestrator/fsm.py::_pull_main_or_escalate`, SPEC «Материалы») — операции
над РЕАЛЬНЫМ git (конфликт слияния, `git merge --abort`, счёт коммитов,
merge-коммит) и РЕАЛЬНЫМ `scripts/codebase_map.py` (не мок): AC-1 требует,
чтобы повторный прогон генератора на слитом дереве не давал диффа —
подменять генератор заглушкой сделало бы эту часть проверки тавтологией.
Тот же приём временного git-репозитория и per-task worktree, что и
`tasks/T051/acceptance_tests/_sandbox.py`; мьютекс-окно `merge_gate`
(вызов внутри него, T053) — приёмом `tasks/T053/acceptance_tests/_sandbox.py`
(CI-заглушка, bare-remote upstream, двухшаговый `approve` по sha).

`scripts/codebase_map.py` копируется В САМ временный репозиторий (не
запускается по абсолютному пути из REPO_ROOT, как в
`tasks/T027/acceptance_tests/test_codebase_map.py`): реализация T067,
по требованию 2 SPEC, обязана запускать генератор ОТНОСИТЕЛЬНЫМ путём
внутри слитого дерева worktree задачи (`_regenerate_and_commit_map`,
`orchestrator/fsm.py`, уже так делает для main) — если файла нет в самой
песочнице, у `subprocess.run(["python3", "scripts/codebase_map.py"], cwd=...)`
реализации нечего запускать.

Реальный `docs/codebase-map.md` содержательно детерминирован только
файлом `scripts/codebase_map.py` (единственный `.py` в дереве песочницы —
директорий `orchestrator/`/`tests/` в ней нет вовсе, генератор трактует
отсутствующую директорию как пустую, требований к их наличию у него нет).
Предмерджевая дивергенция карты между main и веткой задачи создаётся
РУЧНОЙ правкой `docs/codebase-map.md` (не перегенерацией) — она всё равно
целиком перезаписывается настоящим генератором при авторазрешении, а
итоговое содержимое сверяется с независимым повторным прогоном того же
генератора (без строки `built_at_sha:`, тем же приёмом сверки содержимым,
каким уже пользуется сам `fsm.py` — `_map_content_without_sha`, SPEC T042).

Тесты не переоткрывают саму логику авторазрешения (её ещё нет — эту
задачу впервые пишет developer после test_author) — только наблюдаемое
поведение публичных точек входа `fsm.cmd_advance`/`fsm.cmd_approve`,
которые уже существуют и не должны менять сигнатуру.
"""
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, ci, config, fsm, store, workspace  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK = "T001"
GENERATOR_REL = "scripts/codebase_map.py"
MAP_REL = "docs/codebase-map.md"

PLAN_READY_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: авторазрешение конфликта карты

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

# Приёмочный тест, который всегда проходит — маркер того, что прогон
# приёмочных тестов задачи в подтянутом дереве состоялся и был зелёным
# (тот же приём, что `tasks/T051/acceptance_tests/_sandbox.py`).
PASSING_ACCEPTANCE_TEST = '''"""Маркер: заведомо зелёный приёмочный тест песочницы T067."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''

# Стенд-генератор, который ВСЕГДА падает ненулевым кодом возврата (AC-5).
# Перед падением пишет файл-маркер по АБСОЛЮТНОМУ пути вне git-дерева
# (`{marker_path}` подставляется в `setUp`, per-instance) — так тест
# может убедиться, что оркестратор ДЕЙСТВИТЕЛЬНО запустил именно этот
# генератор на слитом дереве (не просто эскалировал конфликт, не доходя
# до попытки регенерации вовсе), не полагаясь на конкретный текст
# диагностики в журнале/выводе, который SPEC не фиксирует дословно.
BROKEN_GENERATOR_TEMPLATE = '''"""Стенд: генератор карты, который всегда падает (AC-5, T067)."""
from pathlib import Path

Path({marker_path!r}).write_text("invoked\\n", encoding="utf-8")
raise SystemExit(7)
'''


def strip_built_at_sha(text: str) -> str:
    """Текст карты без строки `built_at_sha:` — та же сверка содержимым,
    каким приёмом уже пользуется сам `orchestrator/fsm.py`
    (`_map_content_without_sha`, SPEC T042): `built_at_sha` меняется при
    каждом прогоне генератора (текущий HEAD в момент запуска) и сам по
    себе не показатель содержательного расхождения — во время
    авторазрешения регенерация идёт ДО завершения merge-коммита, так что
    её `built_at_sha` неизбежно называет ветку-родителя, а не будущий
    merge-sha (та же механика, что и `git commit` внутри мержа вообще)."""
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("built_at_sha:"))


class MapConflictRealGitTest(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории с веткой main,
    настоящим `scripts/codebase_map.py` и bare-remote upstream (нужен
    сценарию подтяжки внутри окна `merge_gate`, T053-приём); ветка задачи
    заводится тестом там, где сценарию нужна.

    `broken_generator = True` (класс-атрибут подклассов, AC-5) —
    `scripts/codebase_map.py` с самого init заменён на заведомо падающий
    стенд: дивергенция карты между main и веткой задачи в этом случае —
    тоже ручная правка текста (регенерировать нечем по построению).
    """

    TASK = TASK
    broken_generator = False

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "shared.txt").write_text("base\n", encoding="utf-8")

        (self.root / "scripts").mkdir()
        (self.root / "docs").mkdir()
        if self.broken_generator:
            marker_dir = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, marker_dir, ignore_errors=True)
            self.regen_marker_path = marker_dir / "regen-attempted.marker"
            (self.root / GENERATOR_REL).write_text(
                BROKEN_GENERATOR_TEMPLATE.format(
                    marker_path=str(self.regen_marker_path)),
                encoding="utf-8")
            (self.root / MAP_REL).write_text(
                "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
                "---\n\n# Карта (заглушка песочницы)\n", encoding="utf-8")
        else:
            shutil.copy(REPO_ROOT / GENERATOR_REL, self.root / GENERATOR_REL)

        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        if not self.broken_generator:
            regen = self.regenerate(self.root)
            self.assertEqual(regen.returncode, 0,
                             f"генератор упал в setUp: {regen.stderr}")
            self.commit_all(self.root, "карта: init")

        # Upstream — bare-remote без сети (нужен сценарию merge_gate,
        # тот же приём, что `tasks/T053/acceptance_tests/_sandbox.py`).
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
            ("PROJECTS", self.root / ".artel" / "projects"),
            ("TARGETS", self.root / "targets.yaml"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-map-conflict"
        store.insert_task(store.db(), self.TASK, "Авторазрешение конфликта карты",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # Зелёный CI (нужен только сценарию merge_gate — предмет этих
        # тестов не он, тот же приём, что T053).
        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    @staticmethod
    def capture(fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def regenerate(self, cwd: Path) -> subprocess.CompletedProcess:
        """Настоящий прогон `scripts/codebase_map.py` СОБСТВЕННОЙ копии
        песочницы (не REPO_ROOT — AC-5 подменяет именно эту копию)."""
        return subprocess.run(
            [sys.executable, str(cwd / GENERATOR_REL)], cwd=cwd,
            capture_output=True, text=True, timeout=60)

    def task_row(self, task_id=None):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id or self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str, task_id=None) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     (state, task_id or self.TASK))
        conn.commit()

    def journal_rows(self, task_id=None) -> list:
        return store.task_steps(store.db(), task_id or self.TASK)

    def journal_details(self, task_id=None) -> list:
        return [r["detail"] for r in self.journal_rows(task_id)]

    def make_worktree(self, task_id=None, branch=None) -> Path:
        wt_path, error = workspace.ensure(task_id or self.TASK,
                                          branch or self.branch)
        self.assertIsNone(error, error)
        return wt_path

    def commit_all(self, path: Path, message: str) -> str:
        self.git("add", "-A", cwd=path)
        self.git("commit", "-q", "-m", message, cwd=path)
        return self.head(path)

    def head(self, path=None) -> str:
        return self.git("rev-parse", "HEAD", cwd=path).stdout.strip()

    def main_head(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()

    def branch_head(self, branch=None) -> str:
        return self.git("rev-parse",
                        f"refs/heads/{branch or self.branch}").stdout.strip()

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str,
                    cwd=None) -> bool:
        res = self.git("merge-base", "--is-ancestor", ancestor_sha,
                       descendant_sha, cwd=cwd, check=False)
        return res.returncode == 0

    def assert_no_merge_in_progress(self, wt: Path) -> None:
        """Ни незавершённого merge, ни грязного дерева не осталось —
        `git merge --abort` действительно отработал (AC-3, AC-4, AC-5)."""
        merge_head = self.git("rev-parse", "-q", "--verify", "MERGE_HEAD",
                              cwd=wt, check=False)
        self.assertNotEqual(
            merge_head.returncode, 0,
            "MERGE_HEAD всё ещё присутствует — git merge --abort не был "
            "выполнен")
        status = self.git("status", "--porcelain", cwd=wt).stdout
        self.assertEqual(
            status.strip(), "",
            f"рабочее дерево worktree должно быть чистым после отката "
            f"merge, а не:\n{status}")

    def write_plan_ready(self, wt_path: Path, task_id=None) -> None:
        tdir = wt_path / "tasks" / (task_id or self.TASK)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text(
            PLAN_READY_MD.format(task=task_id or self.TASK), encoding="utf-8")

    def write_acceptance_test(self, wt_path: Path, content: str,
                              task_id=None) -> None:
        acc_dir = wt_path / "tasks" / (task_id or self.TASK) / "acceptance_tests"
        acc_dir.mkdir(parents=True, exist_ok=True)
        (acc_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def diverge_map_only(self, wt: Path,
                         task_text="карта версии ветки задачи (тест)\n",
                         main_text="карта версии main (тест)\n") -> tuple:
        """Правка ТОЛЬКО `docs/codebase-map.md` по-разному на обеих
        сторонах — единственный конфликтующий при merge файл. Итоговое
        содержимое всё равно перезаписывается настоящей регенерацией при
        успешном авторазрешении — здесь важна только сама дивергенция,
        не текст."""
        (wt / MAP_REL).write_text(task_text, encoding="utf-8")
        c1 = self.commit_all(wt, f"{self.TASK}: правка карты (дивергенция теста)")
        (self.root / MAP_REL).write_text(main_text, encoding="utf-8")
        c2 = self.commit_all(self.root, "main: правка карты (дивергенция теста)")
        return c1, c2

    def diverge_shared_txt(self, wt: Path, task_text="task-version\n",
                           main_text="main-version\n") -> tuple:
        """Правка ТОЛЬКО `shared.txt` по-разному на обеих сторонах —
        конфликт, который карты не задевает вовсе (AC-4) либо задевает её
        ВМЕСТЕ с картой, если до этого уже была вызвана `diverge_map_only`
        (AC-3)."""
        (wt / "shared.txt").write_text(task_text, encoding="utf-8")
        c1 = self.commit_all(wt, f"{self.TASK}: правка shared.txt (дивергенция теста)")
        (self.root / "shared.txt").write_text(main_text, encoding="utf-8")
        c2 = self.commit_all(self.root, "main: правка shared.txt (дивергенция теста)")
        return c1, c2

    def advance_from_in_dev(self, wt: Path) -> str:
        self.write_plan_ready(wt)
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        self.commit_all(wt, f"{self.TASK}: PLAN готов + приёмочные тесты")
        self.set_state("in_dev")

    def approve(self) -> str:
        """Двухшаговое подтверждение sha (`orchestrator/fsm.py`
        `confirm_fixation`/`APPROVE_NEEDS_SHA`), тем же приёмом, что
        `tasks/T053/acceptance_tests/_sandbox.py::MergeQueueRealGitTest.approve`.
        Каждый вызов независим (заново раскрывает актуальный sha) —
        корректно работает и когда предыдущий approve сдвинул head ветки
        подтяжкой main, не только когда head не менялся."""
        first = self.capture(fsm.cmd_approve, self.TASK)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, self.TASK, match.group(1))
        return first + second
