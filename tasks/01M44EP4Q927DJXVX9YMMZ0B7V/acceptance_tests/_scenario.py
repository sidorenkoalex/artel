"""Общий сценарий планки задачи 01M44EP4Q927DJXVX9YMMZ0B7V: настоящий git,
задача артели в `tests_writing`, ссылка документов с SPEC.md, рабочая
копия кода на ветке задачи (`workspace.ensure`) и загрузка выложенного
помощника пульта `_pult.py` как модуля.

Тонкая надстройка над `tests.sandbox.RealGitSandbox` — собственных копий
патчей песочницы здесь нет."""
import importlib.util
import itertools
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from orchestrator import (acceptance, artifact_branch, config, gitcmd,  # noqa: E402
                          store, workspace)
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK = "01FIXTUREPLANKHELPERTASK00"
BRANCH = f"task/{TASK.lower()}-pomoshchnik"
HELPER_NAME = "_pult.py"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: песочница помощника планки

## Критерии приёмки

AC-1. Единственный критерий песочницы.
""".format(task=TASK)

# Планка песочницы: один тест на AC-1, чтение артефакта — не с диска.
PLANK_TEST = '''"""Зелёный с рождения: фикстура планки песочницы, не планка задачи.
Группа: разовый"""
import unittest


class PlankTest(unittest.TestCase):

    def test_ac1_sandbox_criterion(self):
        """Тест песочницы.

        Зелёный с рождения: фикстура."""
        self.assertTrue(True)
'''

# Свой файл планки с зарезервированным именем — не помощник пульта.
PLANK_OWN_PULT = "# файл планки, не помощник пульта\nPLANK_OWN_PULT = 1\n"

_loaded = itertools.count()


def git(cwd: Path, *args: str) -> str:
    """Настоящий git в `cwd`; отказ — провал теста с ответом git."""
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                         text=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} в {cwd}: {res.stderr}")
    return res.stdout


def load_helper(path: Path):
    """Выложенный `_pult.py` как модуль под уникальным именем, без
    `__pycache__` рядом с планкой (иначе он попал бы в неотслеживаемые
    файлы рабочей копии)."""
    name = f"pult_helper_under_test_{next(_loaded)}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


def constant_values(module) -> list:
    """Значения открытых констант модуля (имена в верхнем регистре)."""
    return [value for key, value in vars(module).items()
            if key.isupper() and not key.startswith("_")]


def as_path_values(values) -> set:
    """Константы-пути (str/Path) в разрешённом виде."""
    paths = set()
    for value in values:
        if isinstance(value, (str, Path)) and str(value).startswith("/"):
            paths.add(Path(value).resolve())
    return paths


class PlankHelperSandbox(RealGitSandbox):
    """Задача `TASK` в `tests_writing`: origin синхронен с main, рабочая копия
    кода на `BRANCH`, ссылка документов несёт SPEC.md и зафиксирована."""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Помощник планки", "tests_writing",
                          BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(TASK, BRANCH)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        self.wt = wt
        self.ref = artifact_branch.branch_name(TASK)
        self.commit_to_ref({"SPEC.md": SPEC_TEXT}, "SPEC")
        self.plank_dir = self.wt / "tasks" / TASK / "acceptance_tests"
        self.helper_path = self.plank_dir / HELPER_NAME

    # ------------------------------------------------------------ ссылка
    def commit_to_ref(self, files: dict, message: str = "документы") -> str:
        """Коммит в ссылку документов задачи (пути — от `tasks/<id>/`) с
        перефиксацией, как у автокоммита шага."""
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/{rel}": text for rel, text in files.items()},
            message)
        self.assertTrue(sha, "коммит в ссылку документов не состоялся")
        store.record_fixation(self.conn, TASK)
        return sha

    def ref_tree(self) -> dict:
        return artifact_branch.read_tree(TASK)

    def docs_dir(self) -> Path:
        return artifact_branch.docs_dir(TASK, config.DEFAULT_TARGET)

    # ------------------------------------------------------- рабочая копия
    def wt_git(self, *args: str) -> str:
        return git(self.wt, *args)

    def commit_code(self, rel: str, text: str, message: str = "код задачи") -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.wt_git("add", rel)
        self.wt_git("commit", "-q", "-m", message)

    def write_untracked(self, rel: str, text: str = "черновик\n") -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def task_repo(self) -> Path:
        return workspace.task_repo(TASK)

    def expected_base(self) -> str:
        """База диффа ветки задачи тем же вызовом, что у гейта зон."""
        base = gitcmd.diff_base(BRANCH, repo=self.task_repo())
        self.assertTrue(base, "gitcmd.diff_base не ответил в песочнице")
        return base

    def expected_base_source(self) -> str:
        return gitcmd.diff_base_source(BRANCH, repo=self.task_repo())

    # ------------------------------------------------------------ выкладка
    def materialize(self):
        """Выкладка из ссылки документов и загрузка помощника пульта."""
        acceptance.materialize_from_branch(TASK, self.ref, self.wt)
        self.assertTrue(self.helper_path.is_file(),
                        f"выкладка не положила {HELPER_NAME} в {self.plank_dir}")
        return load_helper(self.helper_path)

    def code_branch_paths(self) -> list[str]:
        return [p for p in git(self.root, "ls-tree", "-r", "--name-only",
                               BRANCH).splitlines() if p]
