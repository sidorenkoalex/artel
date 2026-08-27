"""Общая песочница приёмочных тестов T045 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

Worktree-механика требует НАСТОЯЩЕГО git (`git worktree add/remove`), в
отличие от лёгких песочниц остального оркестратора (`gitcmd.git`
заглушкой, tests/sandbox.py). Поэтому `config.ROOT` здесь — временный
git-репозиторий с копией `skills/` (шаги роли читают их с `config.ROOT`,
см. orchestrator/runner.py `_cmd_run`), а не сам пульт: настоящие
worktree не должны создаваться в дереве, где гоняются тесты.
`roles.yaml` НЕ копируется — `config.ROLES` вычисляется при импорте
модуля от исходного `config.ROOT` и патчем `config.ROOT` не задевается,
так что читается настоящий файл пульта (то же для чтения через
`config.ROLES` в orchestrator/roles.py).
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

from orchestrator import catalog, ci, config, fsm, runner, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK = "T001"
TZ_RAW = "Тестовая задача worktree-нормы: проверить обособление рабочих поверхностей.\n"


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.lines)

    def close(self):
        pass


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines=("готово\n",), returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class WorktreeRepoTest(unittest.TestCase):
    """Задача T001 (роль analyst, TZ.md есть — самый лёгкий агентный путь,
    см. tests/test_analyst_role.py RunAnalystTest) в свежем временном
    git-репозитории с настоящей веткой main."""

    TASK = TASK

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var, а сравнения
        # путей ниже (worktree_path и т.п.) — строковые/Path-объекты.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        # Бриф роли (analyst/developer) читает docs/codebase-map.md с
        # config.ROOT (orchestrator/brief.py fresh_map_text) — сверка
        # свежести на несвязанном sha временного репозитория переживается
        # некритичной пометкой "стухла", но сам файл обязан быть на диске.
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / "docs" / "codebase-map.md",
                   self.root / "docs" / "codebase-map.md")
        self.git("add", "-A")
        self.git("commit", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Возможный будущий путь стандартного места worktree
        # (`config.WORKTREES`, SPEC «в стандартном месте... .artel/worktrees/<id>»)
        # патчится защитно: `create=True`, т.к. атрибута может ещё не
        # существовать до реализации T045 — без этого код, вычисливший бы
        # его от НЕПОДМЕНЁННОГО config.ROOT при импорте, создавал бы
        # настоящие worktree в РЕАЛЬНОМ репозитории пульта.
        wt_patcher = mock.patch.object(
            config, "WORKTREES", self.root / ".artel" / "worktrees",
            create=True)
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Worktree-норма")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]
        self.write_tz()

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def task_row(self, task_id=None):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id or self.TASK,)).fetchone()

    def state(self, task_id=None) -> str:
        return self.task_row(task_id)["state"]

    def set_state_raw(self, state: str, task_id=None) -> None:
        """Ставит состояние в обход переходов FSM — по образцу
        tests/test_invariants.py `set_state`."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     (state, task_id or self.TASK))
        conn.commit()

    def write_tz(self, raw: str = TZ_RAW, task_id=None, tdir=None) -> Path:
        tdir = tdir or self.tdir
        task_id = task_id or self.TASK
        tz_path = tdir / "TZ.md"
        tz_path.write_text(
            catalog._tz_document(task_id, "Worktree-норма", raw),
            encoding="utf-8")
        return tz_path

    def worktree_path(self, task_id=None) -> Path:
        return self.root / ".artel" / "worktrees" / (task_id or self.TASK)

    def make_worktree(self, task_id=None, branch=None) -> Path:
        """Создаёт per-task worktree НАПРЯМУЮ настоящим git — независимо
        от того, реализована ли уже команда `workspace` (T045): тестам
        уборки/гейта нужен факт существования worktree по стандартному
        пути, а не конкретный способ, которым его завела `workspace`."""
        task_id = task_id or self.TASK
        branch = branch or self.task_row(task_id)["branch"]
        path = self.worktree_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.git("rev-parse", "--verify", "--quiet",
                          f"refs/heads/{branch}", check=False).returncode == 0
        if exists:
            self.git("worktree", "add", str(path), branch)
        else:
            self.git("worktree", "add", "-b", branch, str(path))
        return path

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain").stdout

    def run_agent(self, task_id=None, lines=("готово\n",), returncode=0):
        """Прогон шага с подменённым процессом агента (по образцу
        tests/test_analyst_role.py RunAnalystTest); возвращает мок Popen
        и захваченный stdout."""
        task_id = task_id or self.TASK
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(lines, returncode)
            out = self.capture(runner.cmd_run, task_id)
        return popen, out


class MergeGateReadyTest(WorktreeRepoTest):
    """Задача T001 на гейте merge_gate: worktree с закоммиченным SPEC.md
    на ветке, зелёный CI (подменён), настоящий локальный bare-remote
    (push реален, без сети). Общее для AC-6/AC-7 (tasks/T045) и сценария
    «orchestrator-команда не в главной копии» AC-8.
    """

    def setUp(self):
        super().setUp()
        # tasks/T001/ несмерженной задачи не должен висеть незакоммиченным
        # в РАБОЧЕЙ КОПИИ ПУЛЬТА (main) — иначе fixation._fix_dogfood
        # увидит грязную копию и approve откажет по причине, не связанной
        # с T045 (`tasks/<id>` живёт на ВЕТКЕ задачи, не на main).
        shutil.rmtree(self.tdir, ignore_errors=True)

        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-u", "origin", config.MAIN_BRANCH)
        self.origin = bare

        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

        self.worktree = self.make_worktree()
        (self.worktree / "tasks").mkdir(parents=True, exist_ok=True)
        (self.worktree / "tasks" / self.TASK).mkdir(exist_ok=True)
        (self.worktree / "tasks" / self.TASK / "SPEC.md").write_text(
            "содержимое задачи, зафиксированное на ветке\n", encoding="utf-8")
        self.git("add", "-A", cwd=self.worktree)
        self.git("commit", "-m", f"{self.TASK}: SPEC", cwd=self.worktree)

        self.set_state_raw("merge_gate")

    def approve(self, task_id=None) -> str:
        """Двухшаговое подтверждение sha (orchestrator/fsm.py
        `confirm_fixation`/`APPROVE_NEEDS_SHA`): первый вызов без sha
        печатает зафиксированный sha и не мутирует состояние, второй —
        подтверждает его. Если отказ (в т.ч. AC-8) наступает раньше
        подсказки sha, второй вызов не нужен — возвращается первый вывод."""
        task_id = task_id or self.TASK
        first = self.capture(fsm.cmd_approve, task_id)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, task_id, match.group(1))
        return first + second

    def origin_main_sha(self) -> str:
        return self.git("rev-parse", "refs/heads/main",
                        cwd=self.origin).stdout.strip()

    def root_main_sha(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()
