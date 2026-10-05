"""Песочница сценариев профиля тестов на настоящем git клона проекта.

Поверх `tests.sandbox.LightTransitionSandbox` (задача, БД, документы на
диске) — клон проекта `config.PROJECTS/<имя>/repo` с bare `origin` рядом и
веткой задачи; рабочая копия задачи — настоящий `git worktree` клона в
`workspace.path`, выписанный на ветку задачи (подменённый `workspace.
ensure` заводит его без fetch и хуков пина). git-вызовы с репозиторием внутри `config.PROJECTS` идут в
настоящий git (обработчик `in_repo_handlers` песочницы); `gitcmd.show`/
`gitcmd.ls_tree_files` по коду — настоящие, по `tasks/<id>/` — с диска,
пока сценарий не перевёл документы в настоящую ссылку документов
(`use_real_docs_ref`). `subprocess.run`: pytest не исполняется (успех;
команда и `cwd` запоминаются), `gh`/`claude` — отказ, прочее — шпиону
песочницы. Паузы пульта поднимают исключение-метку `GateFinished`.
"""
import contextlib
import io
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from orchestrator import config, fsm, gitcmd, review, store, workspace
from tests.sandbox import (LightTransitionSandbox, disk_backed_ls_tree_files,
                           disk_backed_show, patch_pult_sleep)

REAL_RUN = subprocess.run
REAL_SHOW = gitcmd.show
REAL_LS_TREE = gitcmd.ls_tree_files

ARTEL = config.DEFAULT_TARGET

SPEC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: профиль тестов проекта (сценарий)

## Критерии приёмки

AC-1. Единственный критерий сценария.
"""


def plank_text(group: str | None = "разовый", note: str = "") -> str:
    group_line = "" if group is None else f"\nГруппа: {group}\n"
    return f'''"""Зелёный с рождения: фикстура сценария профиля тестов.{note}
{group_line}"""
import unittest


class PlankTest(unittest.TestCase):
    def test_ac1_only(self):
        """Фикстурный критерий.

        Ловит мутацию: фикстура, исполнением не проверяется.
        """
        self.assertTrue(True)
'''


def long_lived_text(note: str = "") -> str:
    return f'''"""Зелёный с рождения: фикстура долгоживущего файла.{note}

Группа: долгоживущий
"""
import unittest


class LongLivedTest(unittest.TestCase):
    def test_property(self):
        """Фикстурное свойство.

        Ловит мутацию: фикстура, исполнением не проверяется.
        """
        self.assertTrue(True)
'''


def fixture_test_class(methods=("test_one", "test_two"), assertion="self.assertEqual(1, 1)",
                    claim: bool = True) -> str:
    body = []
    for name in methods:
        doc = ('        """Метод фикстуры.\n\n        Ловит мутацию: фикстура.\n'
               '        """\n') if claim else '        """Метод фикстуры."""\n'
        body.append(f"    def {name}(self):\n{doc}        {assertion}\n")
    return "import unittest\n\n\nclass FixtureTest(unittest.TestCase):\n\n" + \
        "\n".join(body)


ARTEL_PROFILE = {
    "command": ["python3", "-m", "pytest"],
    "long_lived_dir": "tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": ["tests/**/*.py"],
    "mutation_claim_scope": ["tests/test_*.py"],
    "report": "junit-xml",
    "install": [],
}


def render_profile(profile: dict | None) -> str:
    if profile is None:
        return ""
    lines = ["    test_profile:"]
    for key, value in profile.items():
        shown = "[" + ", ".join(value) + "]" if isinstance(value, list) else value
        lines.append(f"      {key}: {shown}")
    return "\n".join(lines) + "\n"


ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
{profile}"""


class GateFinished(Exception):
    """Пауза пульта: команда прошла проверки и ждёт CI."""


def stop_at_pause(*_args) -> None:
    raise GateFinished()


class ProfileGitSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.real_docs = False
        self.profiles: dict = {}
        self.pytest_calls: list = []
        run_patcher = mock.patch.object(subprocess, "run", self.fake_run)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)
        # Рабочая копия на ветке задачи вместо заглушки лёгкой песочницы.
        ensure_patcher = mock.patch.object(workspace, "ensure", self.ensure_impl)
        ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)
        self.in_repo_handlers.append(self.real_git_handler)
        show_patcher = mock.patch.object(gitcmd, "show", self.route_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files", self.route_ls_tree)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(SPEC.format(task=self.TASK),
                                           encoding="utf-8")
        self.write_plank(plank_text())
        self.write_plan_ready()
        self.target = ARTEL

    # ------------------------------------------------------------ plumbing

    def projects_root(self) -> Path:
        return Path(os.path.realpath(config.PROJECTS))

    def is_project_path(self, repo) -> bool:
        try:
            Path(os.path.realpath(repo)).relative_to(self.projects_root())
        except ValueError:
            return False
        return True

    def real_git_handler(self, repo, *args):
        if not self.is_project_path(repo):
            return None
        if not self.real_docs and any("refs/artifacts" in str(a) for a in args):
            return None
        return REAL_RUN(["git", "-C", str(repo), *args], capture_output=True,
                        text=True, env=gitcmd.pult_env())

    def route_show(self, branch, rel, *, repo=None):
        if rel.startswith(f"{config.TASKS.name}/") and not self.real_docs:
            return disk_backed_show(branch, rel, repo=repo)
        return REAL_SHOW(branch, rel, repo=repo)

    def route_ls_tree(self, branch, rel_dir, *, repo=None):
        if rel_dir.startswith(f"{config.TASKS.name}/") and not self.real_docs:
            return disk_backed_ls_tree_files(branch, rel_dir, repo=repo)
        return REAL_LS_TREE(branch, rel_dir, repo=repo)

    def ensure_impl(self, task_id, branch, target=None):
        """Рабочая копия задачи в области проекта, выписанная на ветку
        задачи (`git worktree add` в клоне) — без fetch и хуков пина."""
        target = target or self.target
        path = workspace.path(task_id, target)
        if not path.exists():
            self.git(self.clone(target), "worktree", "add", "-q", str(path), branch)
        return path, None

    def fake_run(self, cmd, *args, **kwargs):
        words = [str(part) for part in cmd]
        if any("pytest" in word for word in words):
            self.pytest_calls.append((words, kwargs.get("cwd")))
            return subprocess.CompletedProcess(
                words, 0, "1 test collected\n1 passed\n", "")
        if words and Path(words[0]).name in ("gh", "claude"):
            return subprocess.CompletedProcess(words, 1, "", "нет в песочнице")
        return self.git_spy(cmd, *args, **kwargs)

    def git(self, repo: Path, *args: str, env: dict | None = None,
            check: bool = True) -> str:
        res = REAL_RUN(["git", "-C", str(repo), *args], capture_output=True,
                       text=True, env=env)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)}: {res.stderr}")
        return res.stdout.strip()

    # ------------------------------------------------------------ projects

    def clone(self, target: str) -> Path:
        return config.PROJECTS / target / "repo"

    def write_targets(self) -> None:
        text = "targets:\n" + "".join(
            ENTRY.format(name=name, base=config.MAIN_BRANCH,
                         url=config.PROJECTS / name / "origin.git",
                         profile=render_profile(profile))
            for name, profile in self.profiles.items())
        config.TARGETS.write_text(text, encoding="utf-8")

    def set_row(self, **fields) -> None:
        conn = store.db()
        for key, value in fields.items():
            conn.execute(f"UPDATE tasks SET {key}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    def make_project(self, target: str, profile: dict | None,
                     base_files: dict | None = None) -> Path:
        """Клон проекта с первым коммитом `base_files` на базовой ветке,
        bare `origin`, запись в `targets.yaml`, задача — этого проекта."""
        self.profiles.setdefault(ARTEL, ARTEL_PROFILE)
        self.profiles[target] = profile
        self.write_targets()
        clone = self.clone(target)
        if clone.exists():
            shutil.rmtree(clone)
        clone.mkdir(parents=True)
        self.git(clone, "init", "-q", "-b", config.MAIN_BRANCH)
        self.git(clone, "config", "user.email", "artel@example.invalid")
        self.git(clone, "config", "user.name", "artel tests")
        self.write_files(clone, dict({"README.md": "проект\n"}, **(base_files or {})))
        self.git(clone, "add", "-A")
        self.git(clone, "commit", "-q", "-m", "база")
        origin = config.PROJECTS / target / "origin.git"
        self.git(clone, "init", "-q", "--bare", str(origin))
        self.git(clone, "remote", "add", "origin", str(origin))
        self.git(clone, "push", "-q", "origin", config.MAIN_BRANCH)
        self.git(clone, "fetch", "-q", "origin")
        self.git(clone, "branch", "-q", self.branch, config.MAIN_BRANCH)
        self.target = target
        if target != ARTEL:
            self.set_row(target=target)
        return clone

    @staticmethod
    def write_files(root: Path, files: dict) -> None:
        for rel, content in files.items():
            path = root / rel
            if content is None:
                if path.exists():
                    path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def work_copy(self) -> Path:
        path, error = self.ensure_impl(self.TASK, self.branch, self.target)
        self.assertIsNone(error)
        return path

    def set_branch(self, changes: dict) -> Path:
        """Ветка задачи = база + `changes` одним коммитом (прежние коммиты
        ветки сброшены); рабочая копия задачи — на ней."""
        wt = self.work_copy()
        self.git(wt, "reset", "-q", "--hard", config.MAIN_BRANCH)
        self.write_files(wt, changes)
        self.git(wt, "add", "-A")
        self.git(wt, "commit", "-q", "--allow-empty", "-m", "правка задачи")
        return wt

    # ------------------------------------------------------------ documents

    def write_plank(self, text: str, name: str = "test_ac.py") -> None:
        plank_dir = self.tdir / "acceptance_tests"
        if plank_dir.is_dir():
            shutil.rmtree(plank_dir)
        plank_dir.mkdir(parents=True)
        (plank_dir / name).write_text(text, encoding="utf-8")

    def docs_commit(self, files: dict, parent: str | None = None) -> str:
        """Коммит дерева документов задачи `files` (пути от `tasks/<id>/`)
        в клоне проекта задачи, без ссылки; sha."""
        clone = self.clone(self.target)
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        prefix = f"{config.TASKS.name}/{self.TASK}"
        self.write_files(scratch, {f"{prefix}/{rel}": text
                                   for rel, text in files.items()})
        env = dict(os.environ, GIT_INDEX_FILE=str(scratch / ".index"),
                   GIT_WORK_TREE=str(scratch))
        self.git(clone, "--work-tree", str(scratch), "add", "-A", ".", env=env)
        tree = self.git(clone, "write-tree", env=env)
        args = ["commit-tree", tree, "-m", "документы"]
        if parent:
            args[2:2] = ["-p", parent]
        return self.git(clone, *args)

    def use_real_docs_ref(self, head: str) -> None:
        """Ссылка документов задачи — настоящая (`head`), в клоне и его
        `origin`; документы читаются из неё, фиксация пульта — на ней."""
        clone = self.clone(self.target)
        ref = f"refs/artifacts/{self.TASK}"
        self.git(clone, "update-ref", ref, head)
        self.git(clone, "push", "-q", "-f", "origin", f"{ref}:{ref}")
        self.real_docs = True
        store.record_fixation(store.db(), self.TASK)

    # ------------------------------------------------------------ commands

    def outcome(self, fn, *args) -> tuple:
        before = len(store.task_steps(store.db(), self.TASK))
        buf = io.StringIO()
        exit_text = ""
        finished = False
        with contextlib.redirect_stdout(buf), patch_pult_sleep(stop_at_pause):
            try:
                fn(*args)
            except SystemExit as exc:
                exit_text = str(exc.code or "")
            except GateFinished:
                finished = True
        rows = [dict(r) for r in store.task_steps(store.db(), self.TASK)[before:]]
        text = (buf.getvalue() + "\n" + exit_text + "\n"
                + "\n".join(f"{r['action']}: {r['detail'] or ''}" for r in rows))
        return text, rows, finished

    def advance_from(self, state: str) -> tuple:
        self.set_state(state)
        self.pytest_calls.clear()
        text, rows, _finished = self.outcome(fsm.cmd_advance, self.TASK)
        return text, rows

    def approve_merge(self) -> tuple:
        self.set_state("merge_gate")
        return self.outcome(fsm.cmd_approve, self.TASK)

    def package(self) -> tuple:
        before = len(store.task_steps(store.db(), self.TASK))
        with contextlib.redirect_stdout(io.StringIO()):
            pkg = review.review_package(store.db(), self.TASK, self.TASK_TITLE,
                                        self.branch)
        rows = [dict(r) for r in store.task_steps(store.db(), self.TASK)[before:]]
        return pkg, rows

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"
