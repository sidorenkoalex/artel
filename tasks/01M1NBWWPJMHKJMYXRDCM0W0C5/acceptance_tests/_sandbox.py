"""Общая песочница приёмочных тестов задачи 01M1NBWWPJMHKJMYXRDCM0W0C5
(AC-1..AC-8): условия автогейта acceptance (`orchestrator/fsm_autogate.py`
`_autogate_conditions`/`_maybe_autogate_acceptance`) обязаны читать
планку `acceptance_tests/` и её AC-пометки через источник артефактов
задачи — артефактную ветку `artifact/<id>` (`artifact_source.resolve` +
`gitcmd.ls_tree_files`/`gitcmd.show`, SPEC требование 1) — а не через
путь на диске рабочей копии (`acc_tdir`), который после переноса
артефактов в артефактную ветку (A7) остаётся пустым (SPEC «Контекст»).

Задача заводится строкой БД напрямую (`store.insert_task`), тем же
приёмом, что `tasks/T066/acceptance_tests/_sandbox.py::AutogateSandbox`:
полный `catalog.cmd_new` не нужен — планка коммитится плотницки прямо
в артефактную ветку (`artifact_branch.commit_files`), диск (`acc_tdir`)
остаётся под полным контролем каждого теста (пустой каталог, либо
намеренно конфликтующее содержимое — AC-1).

Условия ADR-0007 п.3 б/в/г/д (полный прогон приёмочных тестов задачи —
к моменту вызова уже гарантированно зелёный, полный набор `tests/`,
бюджет, вердикт ревью approved) в `conditions()`/`autogate()` ниже
заглушены на «выполнено»: предмет тестов этой задачи — только условие
«а» (источник чтения планки и её AC-пометок), политику самого ADR-0007
эта задача не меняет (SPEC «Не входит»). Отдельная сборка `test_ac7...`
патчит эти же точки индивидуально, чтобы проверить, что порядок/причины
отказа б-д не сдвинулись.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artifact_branch, budget, catalog,  # noqa: E402
                          config, fsm_autogate, gates, store, workspace)

REPO_ROOT = Path(__file__).resolve().parents[3]

TASK = "T001"

# Планка песочницы: зелёная, без manual/skip-критериев (условие «а»
# выполнено).
CLEAN_PLANKA = '''"""Маркер: заведомо чистая планка песочницы (без manual/skip)."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''

# `_HASH`-косвенность НАМЕРЕННАЯ (тот же приём, что `tasks/T066/
# acceptance_tests/_sandbox.py`, см. его докстринг): буквальный текст
# решётка+пробел+"AC"+дефис+"2"+двоеточие+manual (и то же для skip) в
# ЭТОМ файле сам попал бы под сканирование guard'ом как пометка ТЕКУЩЕЙ
# задачи (01M1NBWWPJMHKJMYXRDCM0W0C5) — `_sandbox.py` лежит рядом с её
# собственными `test_ac*.py` в этом же `acceptance_tests/`, а ветко-
# корректное чтение (`orchestrator/fsm.py::_tests_writing_ac_state`,
# и после этой же задачи — `_autogate_conditions`) разбирает ВСЕ `*.py`
# каталога текстом, без импорта (`scripts/guard.py::AC_MARKER`), не
# только `test_*.py` — не отличит фикстуру-строку от настоящей пометки
# этой задачи. Проверено напрямую: `guard.scan_ac_content([text
# ЭТОГО файла])` без косвенности находит ложный manual-маркер AC-2.
_HASH = "#"

# Планка песочницы с одним manual-критерием (номер AC внутри фикстуры —
# произвольный, это планка СИМУЛИРУЕМОЙ задачи T001, не текущей).
MANUAL_PLANKA = (
    '"""Маркер: планка песочницы с одним manual-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    + _HASH + " AC-2: manual — маркер песочницы: критерий с пометкой "
    "manual обязан блокировать условие (а) автопрохода.\n"
)

# То же для skip.
SKIP_PLANKA = (
    '"""Маркер: планка песочницы с одним skip-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    + _HASH + " AC-2: skip — маркер песочницы: критерий с пометкой "
    "skip обязан блокировать условие (а) автопрохода.\n"
)


class AutogateBranchSandbox(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории; строка БД без
    `catalog.cmd_new` — планка коммитится прямо в артефактную ветку,
    диск (`acc_tdir`) под контролем каждого теста."""

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
        self.branch = f"task/{self.TASK.lower()}-avtogeyt-test"
        store.insert_task(store.db(), self.TASK,
                          "Автогейт читает планку из артефактной ветки",
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
        задачи — плотницки, минуя диск (`artifact_branch.commit_files`,
        тот же приём, что и живая фиксация артефактов, A7). Возвращает
        sha получившегося коммита артефактной ветки."""
        rel = f"tasks/{self.TASK}/acceptance_tests/{filename}"
        sha = artifact_branch.commit_files(
            self.TASK, {rel: content}, "тест: планка песочницы")
        self.assertTrue(sha, "commit_files не вернул sha")
        return sha

    def stale_disk_dir(self) -> Path:
        """Путь `acc_tdir`, каким его после A7 видит вызывающий код —
        каталог задачи на диске главной копии, пустой/несуществующий
        (SPEC «Контекст»: `tasks/<id>/` на диске рабочей копии пусто
        после автокоммита шага)."""
        return self.root / "tasks" / self.TASK

    def conditions(self, acc_tdir=None, iteration: int = 1):
        """Вызывает `_autogate_conditions` напрямую с условиями б/в/г/д,
        заглушенными на «выполнено» — предмет теста только условие «а»
        (источник чтения планки)."""
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
        """Вызывает `_maybe_autogate_acceptance` end-to-end (политика
        `acceptance`=`auto`, условия б/в/г/д заглушены на «выполнено»,
        как в `conditions()`) — возвращает захваченный вывод команды."""
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
