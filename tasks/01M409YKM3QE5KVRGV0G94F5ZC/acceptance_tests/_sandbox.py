"""Тонкая надстройка сценариев планки над `tests/sandbox.py`.

`DocsStepSandbox` — шаг роли на НАСТОЯЩЕМ git: главная копия пульта —
git-репозиторий с `main` и bare `origin`, ссылка документов задачи
`refs/artifacts/<id>` пишется штатным узлом (`artifact_branch.commit_files`),
рабочая копия кода заводится `workspace.ensure`, шаг — штатный
`runner.cmd_run` с подменённым процессом агента (`runner.spawn_agent`).
Заглушкой (`fake_git`) выкладку документов из ссылки и автокоммит в ссылку
не проверить: оба — операции настоящего git.

`AcceptanceRunSandbox` — лёгкая песочница переходов
(`LightTransitionSandbox`): переход `in_dev -> verifying` публичным
`fsm.cmd_advance` доходит до прогона приёмочных тестов; сам прогон —
вызов pytest через `subprocess.run` — подменён шпионом, который видит
диск в момент прогона и отдаёт зелёный, красный исход либо исключение.
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

from orchestrator import (artifact_branch, catalog, config, gitcmd, keychain,
                          runner, store, workspace)
from tests.sandbox import (FakeProc, LightTransitionSandbox, TmpRootTest,
                           capture, capture_new_task_id, event,
                           network_guarded_real_run,
                           seed_developer_brief_fixtures)

#: Корень рабочей копии кода, в которую выложена планка
#: (`<корень>/tasks/<id>/acceptance_tests/<файл>`) — источник `templates/`,
#: `skills/`, `.gitignore` для песочницы.
CODE_ROOT = Path(__file__).resolve().parents[3]

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: песочница каталога документов

## Контекст

## Требования

## Критерии приёмки

AC-1. Первый критерий песочницы.

## Не входит
"""


def docs_dir(task_id: str, project: str = None) -> Path:
    """Каталог документов задачи `.artel/projects/<проект>/tasks/<id>/`
    (SPEC, требование 1); проект задачи артели — `config.DEFAULT_TARGET`."""
    return config.PROJECTS / (project or config.DEFAULT_TARGET) / "tasks" / task_id


def disk_tree(root: Path) -> dict:
    """{путь относительно `root`: байты} всех файлов под `root`; каталога
    нет — пустой словарь."""
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def ref_tree(task_id: str) -> dict:
    """{путь относительно `tasks/<id>/`: байты} дерева головы
    `refs/artifacts/<id>` — штатным чтением `artifact_branch.read_tree`."""
    prefix = f"tasks/{task_id}/"
    return {rel[len(prefix):]: text.encode("utf-8")
            for rel, text in artifact_branch.read_tree(task_id).items()
            if rel.startswith(prefix)}


def result_line() -> str:
    return event(type="result", subtype="success", is_error=False,
                 result="готово", total_cost_usd=0.1)


class DocsStepSandbox(TmpRootTest):
    """Задача артели в `tests_writing` на настоящем git; шаг роли —
    test_author (`run_step`)."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        # Настоящий git вместо плотницкой заглушки `SpyRun` базового
        # класса: ссылка документов и её чтение — предмет сценариев.
        self.patch(gitcmd.subprocess, "run", network_guarded_real_run)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

        self.sh("git", "init", "-q", "-b", config.MAIN_BRANCH)
        self.sh("git", "config", "user.email", "artel@example.invalid")
        self.sh("git", "config", "user.name", "artel tests")
        shutil.copytree(CODE_ROOT / "templates", self.root / "templates")
        shutil.copytree(CODE_ROOT / "skills", self.root / "skills")
        shutil.copy(CODE_ROOT / ".gitignore", self.root / ".gitignore")
        seed_developer_brief_fixtures(self.root)
        self.sh("git", "add", "-A")
        self.sh("git", "commit", "-q", "-m", "init")
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        self.sh("git", "init", "-q", "--bare", str(origin))
        self.sh("git", "remote", "add", "origin", str(origin))
        self.sh("git", "push", "-q", "origin",
                f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

        self.patch(keychain, "token", lambda slot: "tok-test")
        self.patch(runner.time, "sleep", lambda _: None)
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target, **step: [])
        preflight.start()
        self.addCleanup(preflight.stop)

        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new,
                                           "Каталог документов вне кода")
        self.commit_docs({"SPEC.md": SPEC_TEXT.format(task=self.TASK)},
                         "SPEC песочницы")
        store.update_task(store.db(), self.TASK, state="tests_writing")
        self.wt = workspace.path(self.TASK)

    # ------------------------------------------------------------ утилиты

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    def sh(self, *argv: str, cwd: Path = None) -> str:
        res = subprocess.run(list(argv), cwd=cwd or self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"{' '.join(argv)}: {res.stderr}")
        return res.stdout

    def word(self) -> str:
        return "".join(self.rnd.choice("abcdefghijklmnopqrstuvwxyz")
                       for _ in range(8))

    def commit_docs(self, files: dict, message: str) -> str:
        """Коммит `{путь от tasks/<id>/: текст}` в ссылку документов штатным
        узлом записи и перефиксация (так ссылку двигают команды пульта —
        сверка целостности на старте шага иначе увидела бы расхождение)."""
        sha = artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/{rel}": text
                        for rel, text in files.items()},
            f"{self.TASK}: {message}")
        self.assertTrue(sha, "фикстура не записала ссылку документов")
        store.record_fixation(store.db(), self.TASK)
        return sha

    def run_step(self, on_spawn) -> dict:
        """Шаг test_author: `on_spawn(cmd, kwargs)` исполняется в момент
        запуска агента (то есть уже после всей подготовки шага пультом) —
        это и есть «роль». Возврат: число запусков агента, отказ шага,
        печать."""
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append(list(cmd))
            on_spawn(list(cmd), kwargs)
            return FakeProc([result_line()])

        refusal, buf = None, io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(buf):
            try:
                runner.cmd_run(self.TASK)
            except SystemExit as exc:
                refusal = str(exc.code)
        return {"calls": calls, "refusal": refusal, "output": buf.getvalue()}

    def code_copy_doc_hits(self, names) -> list:
        """Пути рабочей копии кода задачи (без `.git`), которые несут
        `tasks/<id>` либо имя одного из файлов документов `names`."""
        hits = []
        if not self.wt.is_dir():
            return hits
        task_dir = self.wt / "tasks" / self.TASK
        if task_dir.exists():
            hits.append(str(task_dir))
        for path in self.wt.rglob("*"):
            if ".git" in path.relative_to(self.wt).parts:
                continue
            if path.is_file() and path.name in names:
                hits.append(str(path))
        return hits


class LockedDocsSandbox(DocsStepSandbox):
    """`DocsStepSandbox` после выхода из `tests_writing` штатным
    `fsm.cmd_advance`: в ссылке — SPEC, планка `acceptance_tests/
    test_ac1_plank.py` и готовый PLAN, в кодовой ветке — свой долгоживущий
    файл `self.own`; задача в `in_dev`, лок (`tests_locked_sha`) и перечень
    сумм записаны пультом. Шаг `run_step` здесь — шаг developer."""

    def setUp(self):
        super().setUp()
        from tests.test_long_lived_transitions import (long_lived_source,
                                                       plank_source)
        self.plank_rel = "acceptance_tests/test_ac1_plank.py"
        self.commit_docs({self.plank_rel: plank_source()}, "планка песочницы")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        wt, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        self.own = f"tests/test_{self.TASK.lower()}_{self.word()}.py"
        (wt / self.own).parent.mkdir(parents=True, exist_ok=True)
        (wt / self.own).write_text(long_lived_source(), encoding="utf-8")
        self.sh("git", "add", "--", self.own, cwd=wt)
        self.sh("git", "commit", "-q", "-m", "свой долгоживущий файл", cwd=wt)
        out = self.advance()
        row = store.get_task(store.db(), self.TASK)
        self.assertEqual(row["state"], "in_dev",
                         f"фикстура: выход из tests_writing не прошёл\n{out}")
        self.assertTrue(row["tests_locked_sha"], "фикстура: лок не записан")
        from tests.test_git_fixation import PLAN_READY
        self.commit_docs({"PLAN.md": PLAN_READY.format(task=self.TASK)},
                         "PLAN готов")

    def advance(self) -> str:
        from orchestrator import fsm
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                fsm.cmd_advance(self.TASK)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc}")
        return buf.getvalue()

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} {r['detail'] or ''}" for r in rows)


# ----------------------------------------------------------------------------


PLANK_TEST_TEMPLATE = '''"""Учебный тест планки песочницы {tag}."""
import unittest


class PlankTest(unittest.TestCase):

    def test_ac1_{tag}(self):
        self.assertTrue(True)
'''


class AcceptanceRunSandbox(LightTransitionSandbox):
    """Переход `in_dev -> verifying` до прогона приёмочных тестов: ветка
    не отстала от `main` (`gitcmd.commits_behind` -> 0), рабочая копия
    кода на ветке задачи (`workspace.on_task_branch` -> True). Планка —
    случайный набор файлов в источнике документов лёгкой песочницы."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        self.write_acceptance_plank()
        tests_dir = self.tdir / "acceptance_tests"
        self.plank = {"test_stub.py"}
        for _ in range(self.rnd.randint(1, 3)):
            tag = "".join(self.rnd.choice("abcdefghijklmnopqrstuvwxyz")
                          for _ in range(8))
            name = f"test_{tag}.py"
            (tests_dir / name).write_text(PLANK_TEST_TEMPLATE.format(tag=tag),
                                          encoding="utf-8")
            self.plank.add(name)
        self.code_root = workspace.path(self.TASK)
        self.code_root.mkdir(parents=True, exist_ok=True)
        for target, attr, value in (
                (gitcmd, "commits_behind", lambda *a, **k: 0),
                (workspace, "on_task_branch", lambda *a, **k: True)):
            self.patch(target, attr, value)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    def plank_dir(self) -> Path:
        return self.code_root / "tasks" / self.TASK / "acceptance_tests"

    def advance_with_run(self, outcome: str) -> dict:
        """`advance` из `in_dev`; каждый вызов pytest по каталогу
        `acceptance_tests` перехватывается: шпион запоминает `cwd` и файлы
        планки на диске в этот момент и отдаёт `outcome` — "green" (код 0),
        "red" (код 1) либо "crash" (исключение внутри прогона). Прочие
        вызовы `subprocess.run` идут дальше как были."""
        previous_run = subprocess.run
        runs = []

        def is_plank_run(cmd) -> bool:
            if not isinstance(cmd, (list, tuple)):
                return False
            argv = [str(part) for part in cmd]
            return "pytest" in argv and any(
                Path(part).name == "acceptance_tests" for part in argv)

        def spy(cmd, *args, **kwargs):
            if not is_plank_run(cmd):
                return previous_run(cmd, *args, **kwargs)
            cwd = Path(kwargs.get("cwd") or os.getcwd())
            plank = cwd / "tasks" / self.TASK / "acceptance_tests"
            runs.append({"cwd": cwd, "files": sorted(
                p.name for p in plank.glob("*") if p.is_file())
                if plank.is_dir() else None})
            if outcome == "crash":
                raise RuntimeError("песочница: сбой внутри прогона планки")
            code = 0 if outcome == "green" else 1
            out = ("1 passed\n" if code == 0
                   else "FAILED test_stub.py::StubTest::test_stub\n1 failed\n")
            return subprocess.CompletedProcess(list(cmd), code, out, "")

        crashed = None
        with mock.patch.object(subprocess, "run", spy):
            try:
                output = self.advance_from_in_dev()
            except Exception as exc:  # сбой прогона доходит наружу как есть
                crashed, output = exc, ""
        return {"runs": runs, "crashed": crashed, "output": output,
                "state": self.state()}
