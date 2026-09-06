"""Общая песочница приёмочных тестов задачи 01M1SHJTT0V516BWHYXWS50F3G
(AC-3..AC-6): пометка критерия `ci` в условии «а» автогейта acceptance
(`orchestrator/fsm_autogate.py`) и в сводке ручного гейта
(`orchestrator/acceptance.py::summary`) — доказательство исполнения
критерия берётся из статуса CI ГОЛОВЫ КОДОВОЙ ветки задачи
(`orchestrator/ci.py`), не повторным прогоном `tests/` пультом (SPEC
требования 2, 4).

Тот же приём реального временного git-репозитория и заглушки условий
б/в/г/д, что `tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/
_sandbox.py::AutogateBranchSandbox` (условие «а» той задачи — источник
чтения планки; предмет ЭТОЙ задачи — новая пометка `ci` внутри того же
условия «а», плюс её отражение в сводке ручного гейта). Дополнительно
заводится РЕАЛЬНАЯ ветка КОДА задачи (`self.branch`, не только
артефактная — она несёт только планку) с настоящим коммитом, чей sha
проверяет CI: единственная внешняя граница `orchestrator/ci.py` —
`ci.gh` (сам вызов `gh`) — подменяется здесь, так что тест не завязан
на то, какую именно функцию `ci.py` (`branch_status`/`verifying_status`/
другую) выберет реализация — любая из них в итоге спрашивает `gh` через
эту точку, а голову ветки — через настоящий `git rev-parse` (репозиторий
настоящий, не мок).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artifact_branch, budget, catalog,  # noqa: E402
                          ci, config, fsm_autogate, gates, store, workspace)

REPO_ROOT = Path(__file__).resolve().parents[3]

TASK = "T001"

# Индирекция символа решётки (тот же приём и с той же причиной, что
# `tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/_sandbox.py::_HASH`):
# буквальный текст "# AC-<n>: ci — …" в ЭТОМ файле сам попал бы под
# ветко-корректное сканирование ВСЕХ *.py каталога планки
# (`guard.scan_ac_content`, `fsm_autogate._autogate_conditions`) как
# пометка ТЕКУЩЕЙ задачи (01M1SHJTT0V516BWHYXWS50F3G) — фикстуры здесь
# планка СИМУЛИРУЕМОЙ задачи T001, не текущей.
_HASH = "#"


def ci_marker(n: int, reason: str = "существующие tests/ уже зелёные "
              "по CI ветки") -> str:
    return f"{_HASH} AC-{n}: ci — {reason}\n"


CLEAN_TEST_METHOD = (
    '"""Маркер: планка песочницы с одним ci-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
)


def ci_only_planka(n: int = 2) -> str:
    """Планка с единственной пометкой критерия `AC-<n>: ci` — без
    manual/skip, без непокрытых критериев (условие «а» помимо ci чисто)."""
    return CLEAN_TEST_METHOD + ci_marker(n)


class AutogateCiMarkerSandbox(unittest.TestCase):
    TASK = TASK

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
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

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

        # Реальная ветка КОДА задачи (не артефактная!) — критерий `ci`
        # смотрит на её головной коммит (SPEC AC-4), артефактная ветка
        # несёт только планку.
        self.branch = f"task/{self.TASK.lower()}-avtogeyt-ci-test"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / "code.txt").write_text("v1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код задачи")
        self.code_sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)

        store.insert_task(store.db(), self.TASK,
                          "Автогейт: пометка ci по статусу CI кодовой ветки",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.artifact_branch = artifact_branch.branch_name(self.TASK)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None, check: bool = True):
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    @staticmethod
    def capture(fn, *args):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def journal_rows(self) -> list:
        """(actor, action, detail) журнала задачи по порядку записи."""
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (self.TASK,))]

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def seed_planka(self, content: str, filename: str = "test_marker.py") -> str:
        """Коммитит `content` в `acceptance_tests/` артефактной ветки
        задачи — плотницки, минуя диск (`artifact_branch.commit_files`),
        тот же приём, что и живая фиксация артефактов (A7)."""
        rel = f"tasks/{self.TASK}/acceptance_tests/{filename}"
        sha = artifact_branch.commit_files(
            self.TASK, {rel: content}, "тест: планка песочницы")
        self.assertTrue(sha, "commit_files не вернул sha")
        return sha

    def stale_disk_dir(self) -> Path:
        """Путь `acc_tdir`, каким его после A7 видит вызывающий код —
        каталог задачи на диске главной копии, пустой/несуществующий."""
        return self.root / "tasks" / self.TASK

    def gh_check_runs(self, conclusion: str = "success",
                      status: str = "completed", name: str = "python"):
        """Подмена `ci.gh`: единственный ответ на любой запрос —
        `check-runs` головного коммита кодовой ветки, одна проверка с
        заданными `status`/`conclusion`. Достаточно и для
        `ci.branch_status`, и для `ci.verifying_status` — обе читают
        именно этот эндпойнт первым источником."""
        payload = json.dumps({"total_count": 1, "check_runs": [
            {"name": name, "status": status, "conclusion": conclusion}]})

        def fake_gh(*args, timeout=None):
            if len(args) > 1 and "check-runs" in args[1]:
                return subprocess.CompletedProcess(args, 0, payload, "")
            return subprocess.CompletedProcess(args, 0, "[]", "")
        return mock.patch.object(ci, "gh", side_effect=fake_gh)

    def gh_no_data(self):
        """Подмена `ci.gh`: `gh` отвечает ошибкой на любой запрос — CI-
        статуса нет вовсе (SPEC AC-5, ветка «данных нет»)."""
        def fake_gh(*args, timeout=None):
            return subprocess.CompletedProcess(args, 1, "", "gh: not found")
        return mock.patch.object(ci, "gh", side_effect=fake_gh)

    def conditions(self, acc_tdir=None, iteration: int = 1):
        """Вызывает `_autogate_conditions` напрямую с условиями б/в/г/д,
        заглушенными на «выполнено» (тот же приём, что T092
        `AutogateBranchSandbox.conditions`) — предмет тестов этой
        задачи — новая ветвь условия «а» про пометку `ci`."""
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        acc_tdir = acc_tdir if acc_tdir is not None else self.stale_disk_dir()
        with mock.patch.object(workspace, "on_task_branch", return_value=True), \
             mock.patch.object(workspace, "path", return_value=self.root), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, "")), \
             mock.patch.object(budget, "budget_block", return_value=None):
            return fsm_autogate._autogate_conditions(conn, self.TASK, t,
                                                      acc_tdir, iteration)

    def autogate(self, acc_tdir=None, iteration: int = 1) -> str:
        """Вызывает `_maybe_autogate_acceptance` целиком (политика
        `acceptance`=`auto`, условия б/в/г/д заглушены, как в
        `conditions()`)."""
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        acc_tdir = acc_tdir if acc_tdir is not None else self.stale_disk_dir()
        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
             mock.patch.object(workspace, "on_task_branch", return_value=True), \
             mock.patch.object(workspace, "path", return_value=self.root), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, "")), \
             mock.patch.object(budget, "budget_block", return_value=None):
            return self.capture(fsm_autogate._maybe_autogate_acceptance,
                                conn, self.TASK, t, acc_tdir, iteration)
