"""Общая песочница приёмочных тестов 01M1KVG3KSCY47HWXWF5HM0E76 (автокоммит
артефактов шага учитывает `.gitignore`).

`GitignoreExternalTargetSandbox` — тот же приём, что `tests/
test_checkpoint_external_step_artifacts.py::CommitExternalStepArtifactsTest`
(`RealGitSandbox`: `config.ROOT` — настоящий git-репозиторий пульта;
рабочий каталог внешнего target — обычный каталог на диске без git,
`checkpoint._commit_external_step_artifacts` читает файлы с диска и
коммитит их плотницки в артефактную ветку ПУЛЬТА) — добавляет только
корневой `.gitignore` пульта: SPEC, требование 1, критерий фильтрации —
`.gitignore` ЦЕЛЕВОГО репозитория (пульта, `config.ROOT`), не список
расширений, зашитый в код. `dropme/` в фикстуре — намеренно ДИРЕКТОРНОЕ
правило (не суффикс/расширение): список расширений в коде его никогда
не поймает, только настоящий разбор `.gitignore` (`git check-ignore`
или эквивалент по тем же правилам).

`LockFlowSandbox` — сокращённая копия `tests/test_acceptance_tests_flow.py
::LockTest` (тот же реальный git и та же цепочка `spec_writing ->
spec_gate -> tests_writing -> in_dev`, нужная, чтобы `t["tests_locked_sha"]`
оказался выставлен по-настоящему — иначе AC-4 нечего сверять). Приёмочный
файл не наследует `LockTest` напрямую: унаследовав `unittest.TestCase`,
он потянул бы за собой чужие тестовые методы того класса под именами
AC-разметки этой задачи. Здесь только заготовка состояния, тестовые
методы — в `test_ac4_...py`.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artel, artifact_branch, catalog, config, doctor, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import (RealGitSandbox, capture, capture_new_task_id,  # noqa: E402
                           claude_only_popen, resilient_tmp_cleanup)

TARGET = "extproj"

# Реальный корневой .gitignore пульта (SPEC, требование 1) — те же
# правила, что перечислены как минимум SPEC ("__pycache__/, *.pyc,
# *.log"), плюс `dropme/` — директорное правило, которого расширением
# не описать (см. докстринг модуля), и `.artel/` — как в настоящем
# `.gitignore` пульта (рантайм-каталог `store.db()`/`config.DB`,
# без него AC-5 (`git status --porcelain` над `config.ROOT`) увидел бы
# `.artel/` как чужую грязь рабочего дерева, а не как игнорируемый путь).
GITIGNORE_TEXT = "__pycache__/\n*.pyc\n*.log\ndropme/\n.artel/\n"

SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
{extra}---

# SPEC: приёмочные тесты до кода

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом или пометкой.

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: приёмочные тесты до кода

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

AC_TEST_BOTH_COVERED = '''"""Красен до реализации: фикстура покрывает оба критерия SPEC_V2
песочницы — тест и manual-пометка, до появления реализации кода задачи."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


class GitignoreExternalTargetSandbox(RealGitSandbox):
    """`self.task_dir` — каталог `tasks/<id>/` внешнего target на диске;
    `config.ROOT` (`self.root`) несёт настоящий `.gitignore` пульта."""

    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore пульта")

        self.TASK = "01EXTTASKIGNOREFLT01"
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача внешнего target",
                          "in_dev", f"task/{self.TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, content) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def artifact_branch_files(self) -> list:
        branch = artifact_branch.branch_name(self.TASK)
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def artifact_branch_text(self, rel: str):
        branch = artifact_branch.branch_name(self.TASK)
        text, _ = gitcmd.show(branch, rel)
        return text


class _FakeLiveSmokeProc:
    """Замена `subprocess.Popen` для `doctor.live_smoke` (копия
    `tests/test_doctor.py::FakeLiveSmokeProc` — тот же приём, только
    `.communicate`, без реального запуска `claude`): `doctor --fix`
    (AC-5) обязан быть безопасен для CI/локального прогона — без этой
    подмены `live_smoke` внутри `all_checks` реально спросил бы
    `claude`, если бинарь есть в PATH окружения, где гоняются тесты."""

    def __init__(self, output: str = "нет события со стоимостью\n",
                returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


class DoctorFixSandbox(RealGitSandbox):
    """`config.ROOT` — пульт с реальным `.gitignore`; одна живая задача
    (`state="in_dev"`) с артефактной веткой, засеянной НАПРЯМУЮ
    (`artifact_branch.commit_files`, в обход автокоммита шага — AC-5
    проверяется независимо от AC-1/AC-2/AC-3): нормальный файл и
    игнорируемый `__pycache__/*.pyc`, тот же класс инцидента, что в SPEC
    «Контекст» (артефактная ветка hotfix-задачи 01M1KT0792125J9ZNJNZJ86E9Q
    несёт ровно такие же семь `.pyc` сегодня, в реальном репозитории)."""

    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore пульта")

        self.TASK = "01LIVETASKDOCTORFIX1"
        conn = store.db()
        store.insert_task(conn, self.TASK, "Живая задача с мусором в ветке",
                          "in_dev", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        self.branch = artifact_branch.branch_name(self.TASK)
        sha = artifact_branch.commit_files(
            self.TASK,
            {
                f"tasks/{self.TASK}/PLAN.md": "план разработчика\n",
                f"tasks/{self.TASK}/acceptance_tests/__pycache__/"
                "test_ac1.cpython-311.pyc": b"\x00\x01\xff",
            },
            f"{self.TASK}: артефакты шага developer (автокоммит оркестратора)")
        self.assertTrue(sha, "seed-коммит артефактной ветки обязан пройти")

        self.main_head_before = self.git("rev-parse", config.MAIN_BRANCH).strip()

    def artifact_branch_files(self) -> list:
        return gitcmd.ls_tree_files(self.branch, f"tasks/{self.TASK}") or []

    def journal_entries(self) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def run_doctor_fix(self) -> str:
        """`artel.py doctor --fix` — CLI целиком (AC-5 называет команду
        буквально, не внутреннюю функцию); `SystemExit` (обычные doctor-
        проверки почти наверняка проваливаются в голой песочнице — нет
        токенов) проглатывается: AC-5 не про итоговый код возврата
        doctor, а про сам факт уборки игнорируемых файлов + журнал +
        нетронутый main.

        `doctor.cli_version` заменена целиком, а не только `Popen`
        (случай, когда CLI `claude` реально стоит в PATH окружения,
        где гоняются тесты, — этот процесс): `check_cli_version()` идёт
        через `subprocess.run(["claude", ...])`, а `subprocess.run`
        внутри себя открывает `Popen(...)` как контекстный менеджер —
        подмена `Popen` на `_FakeLiveSmokeProc` (нужная для `live_smoke`)
        ловит и этот вызов тоже и падает `TypeError`, потому что у
        подмены нет `__enter__`/`__exit__`. Проверка версии CLI не
        относится к AC-5 (уборка игнорируемых файлов), поэтому она
        просто закорочена на пин, без похода в subprocess вовсе."""
        fake_proc = _FakeLiveSmokeProc()
        with mock.patch.object(sys, "argv", ["artel.py", "doctor", "--fix"]), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=claude_only_popen(fake_proc)), \
                mock.patch.object(doctor, "cli_version",
                                  return_value=config.CLI_VERSION_PIN):
            try:
                return capture(artel.main)
            except SystemExit:
                return ""


class LockFlowSandbox(unittest.TestCase):
    """Копия каркаса `tests/test_acceptance_tests_flow.py::LockTest.setUp`
    (без её тестовых методов) — реальный git пульта с `templates/`,
    `skills/`, `.gitignore`, полный проход `catalog.cmd_new` ->
    `spec_writing -> spec_gate -> tests_writing -> in_dev`, чтобы
    `tests_locked_sha` был выставлен настоящим кодом лока, не подделкой."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(_REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(_REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(_REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = mock.patch.multiple(
            config, ROOT=self.root, DB=self.root / ".artel" / "state.db",
            TASKS=self.root / "tasks", LOGS=self.root / ".artel" / "logs",
            PROJECTS=self.root / ".artel" / "projects",
            ROLE_HOME=self.root / ".artel" / "home",
            ROLE_CONFIG_DIR=self.root / ".artel" / "home" / ".claude",
            WORKTREES=self.root / ".artel" / "worktrees")
        self.patches.start()
        self.addCleanup(self.patches.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new,
                                           "Лок приёмочных тестов (AC-4)")
        self.code_branch = self.row()["branch"]
        self.git("checkout", "-q", "-b", self.code_branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код фичи")
        self.git("checkout", "-q", config.MAIN_BRANCH)

        self.branch = artifact_branch.branch_name(self.TASK)
        self.tdir = self.root / "tasks" / self.TASK

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    capture = staticmethod(capture)

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def on_artifact_branch(self) -> None:
        self.git("checkout", "-q", self.branch)

    def commit_task_dir(self, message: str = "артефакт") -> None:
        # `-f`: AC-4 сеет игнорируемый `.pyc` НАПРЯМУЮ (симуляция инцидента
        # 03.09) тем же методом, каким остальные сценарии кладут обычные
        # файлы — голый `git add -A` тихо пропускает игнорируемые пути, и
        # `git commit` без единого добавленного файла падает кодом 1.
        self.git("add", "-A", "-f", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", message)
        self.git("checkout", "-q", config.MAIN_BRANCH)

    def head(self) -> str:
        return self.git("rev-parse", self.branch).strip()

    def enter_tests_writing(self) -> str:
        self.on_artifact_branch()
        (self.tdir / "SPEC.md").write_text(
            SPEC_V2.format(task=self.TASK, extra=""), encoding="utf-8")
        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        self.capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.state(), "tests_writing")
        return sha

    def write_acceptance_tests(self, content: str) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(content, encoding="utf-8")

    def enter_in_dev(self) -> str:
        self.enter_tests_writing()
        self.on_artifact_branch()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)
        self.commit_task_dir("acceptance_tests от test_author")

        self.capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev

        self.assertEqual(self.state(), "in_dev")
        locked = self.row()["tests_locked_sha"]
        self.assertEqual(locked, self.head(), "лок берёт sha этого коммита")
        self.on_artifact_branch()
        (self.tdir / "PLAN.md").write_text(
            PLAN_MD.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir("PLAN")
        return locked
