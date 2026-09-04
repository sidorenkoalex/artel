"""Общая песочница приёмочных тестов «штатной команды правки
зафиксированной планки приёмки» (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

Имя команды и модуль её реализации НЕ фиксированы SPEC (раздел «Не
входит»: «Имя команды и модуль размещения кода — решение исполнителя
(разработчика на этапе PLAN), не предмет приёмки») — тот же случай, что
прецедент tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D (`acceptance-dry-run`).
`discover_amend_command_name()` находит имя статическим AST-разбором
диспетчера `orchestrator/artel.py::main` (`table = {...}`) как разницу с
`BASELINE_COMMANDS` — снимком ключей диспетчера ДО этой задачи (25 команд,
HEAD на момент написания этих тестов; прецедент 01M1GJ3ZP1YGG5QRB6FQ44NN8D
уже смержен, поэтому `acceptance-dry-run` уже в снимке). Разбор
статический (`ast`, без импорта/исполнения файла) — часть команд таблицы
мутирующая, вслепую звать их нельзя; вызывается только ОДНА новая команда,
которая появится сверх снимка. Зашить конкретное имя литералом значило бы
самовольно принять решение, которое SPEC явно оставляет разработчику
(skills/escalation-rules.md: «не выбирать интерпретацию на свой вкус»).

Реальный git (`tests.sandbox.RealGitSandbox`, тот же приём, что
`tests/test_acceptance_tests_flow.py::LockTest`): предмет проверки —
настоящие коммиты на артефактной ветке пульта, реальное значение
`tests_locked_sha`, инвариант 27 лока (`git diff --quiet` между
зафиксированным и текущим sha) — заглушкой `gitcmd.git` этого не изобразить.

Красен до реализации: до кода задачи 01M1HNNHDMP2C1AJTH5QF1BTN2 в таблице
диспетчера `orchestrator/artel.py::main` нет ни одной команды сверх
`BASELINE_COMMANDS` — `discover_amend_command_name()` падает
`AssertionError` с понятным текстом ещё до того, как тест успевает
проверить хоть что-то по существу.

ANSWER-3 (переписывание `AmendSandbox`, вариант б): после A7 планка
`tasks/<id>/` живёт ТОЛЬКО в артефактной ветке пульта (`artifact_branch.
branch_name`), никогда в кодовой ветке задачи — `enter_in_dev()` поэтому
пишет SPEC.md/acceptance_tests ПРЯМО на артефактную ветку плотницки
(`artifact_branch.commit_files`, тот же приём, что `_new_external_
artifact_branch`/`checkpoint._commit_external_step_artifacts`), а не в
worktree кодовой ветки. Worktree (`workspace.ensure`) остаётся
исключительно поверхностью, которой РЕАЛЬНО оперирует производственная
команда правки планки: Оператор кладёт правку `acceptance_tests/` прямо
в него (`write_acceptance_tests`, тот же физический путь, что и раньше),
команда сама читает её оттуда и коммитит на артефактную ветку — сама
песочница коммит не делает вовсе.

`head()` и `git_wt()` адресуются к АРТЕФАКТНОЙ ветке пульта (`self.branch`),
не к HEAD worktree'а кодовой ветки: именно с ней сверяет лок гейт
`in_dev -> review` (`orchestrator/fsm_advance.py::in_dev`, `lock_ref =
branch`) и именно её сдвигает production `amend-tests` после коммита
(ANSWER-3, вопрос 2) — до этой правки `tests_locked_sha` сдвигался на
HEAD worktree'а кодовой ветки, асимметрия с гейтом (см. `PLAN.md`,
раздел «Эскалация», вопрос 2, ныне устранённая).
"""
import ast
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artel, artifact_branch, catalog, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture_new_task_id  # noqa: E402

ARTEL_PY = REPO_ROOT / "orchestrator" / "artel.py"

# Ключи `table` в orchestrator/artel.py::main на HEAD этой ветки на момент
# написания тестов (25 команд) плюс `pin-update`, влившаяся из main
# подтяжкой A7 (ANSWER-2) — заведомо НЕ включает команду правки планки,
# которую заведёт разработчик.
BASELINE_COMMANDS = frozenset({
    "init", "new", "status", "show", "advance", "workspace", "run", "auto",
    "approve", "reject", "answer", "kill", "release", "pause", "resume",
    "log", "budget", "target-init", "doctor", "alert-ack", "version",
    "canary", "prune", "report", "acceptance-dry-run", "pin-update",
})


def _dispatch_table_keys(source: str) -> set:
    """Строковые ключи словаря `table = {...}` внутри `def main()` —
    разбор AST дерева модуля, без исполнения ни строчки файла."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Assign)
                        and isinstance(sub.value, ast.Dict)
                        and any(isinstance(t, ast.Name) and t.id == "table"
                                for t in sub.targets)):
                    return {k.value for k in sub.value.keys
                            if isinstance(k, ast.Constant)
                            and isinstance(k.value, str)}
    return set()


def discover_amend_command_name() -> str:
    """Имя новой операторской команды правки планки — см. докстринг модуля
    про то, почему оно не зашито литералом."""
    source = ARTEL_PY.read_text(encoding="utf-8")
    added = _dispatch_table_keys(source) - BASELINE_COMMANDS
    assert added, (
        "новая команда правки зафиксированной планки приёмки не найдена "
        "в таблице диспетчера orchestrator/artel.py::main — код задачи "
        "01M1HNNHDMP2C1AJTH5QF1BTN2 ещё не реализован (SPEC AC-1)")
    assert len(added) == 1, (
        f"в таблице диспетчера появилось больше одной новой команды: "
        f"{sorted(added)} — тест не может однозначно выбрать, какая из "
        f"них правка планки")
    return next(iter(added))


SPEC_TPL = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура правки планки

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом или пометкой.

## Не входит
"""

# Исходное содержимое acceptance_tests/, которым фикстура заходит в
# in_dev (тот же приём, что AC_TEST_BOTH_COVERED в
# tests/test_acceptance_tests_flow.py): трассируемость AC-1 тестом,
# AC-2 manual-пометкой, маркер красноты — обязателен на выходе tests_writing.
AC_TEST_LOCKED = '''"""Красен до реализации: фикстура покрывает оба критерия
SPEC-фикстуры песочницы правки планки — тест и manual-пометка, до
появления реализации кода задачи."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''

# Правка Оператора: содержательно ДРУГОЙ текст (новый тестовый метод),
# по-прежнему зелёный и с маркером — сценарий УСПЕШНОЙ правки планки.
AC_TEST_AMENDED_V1 = '''"""Красен до реализации: фикстура покрывает оба критерия
SPEC-фикстуры песочницы правки планки — тест и manual-пометка (правка
Оператора: добавлена вторая проверка критерия AC-1)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac1_first_criterion_again(self):
        self.assertEqual(1 + 1, 2)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''

# Вторая, ЕЩЁ ОДНА независимая правка — для сценариев, которым нужны две
# последовательные успешные правки одной задачи (счётчик, отчётность).
AC_TEST_AMENDED_V2 = '''"""Красен до реализации: фикстура покрывает оба критерия
SPEC-фикстуры песочницы правки планки — тест и manual-пометка (вторая
правка Оператора: добавлена третья проверка критерия AC-1)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac1_first_criterion_again(self):
        self.assertEqual(1 + 1, 2)

    def test_ac1_first_criterion_yet_again(self):
        self.assertEqual(2 + 2, 4)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''

# Падение БЕЗ маркера красноты — прогон обязан отказать (AC-10).
AC_TEST_BROKEN_NO_MARKER = '''"""Фикстура без маркера красноты — падение здесь
намеренное, для проверки отказа команды правки планки по непрошедшему
прогону (AC-10)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(False, "намеренно красный тест без маркера")


# AC-2: manual — Оператор проверяет глазами на приёмке
'''

# Падение С маркером красноты — тем же разбором, что переход
# tests_writing, такое падение НЕ блокирует правку (AC-10, требование 6).
AC_TEST_BROKEN_WITH_MARKER = '''"""Красен до реализации: намеренно красный тест
— часть кода задачи-фикстуры ещё не реализована, прогон обязан пройти
правку планки несмотря на падение (AC-10)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(False, "намеренно красный тест с маркером")


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


class AmendSandbox(RealGitSandbox):
    """Задача, доведённая реальным FSM до `in_dev` — лок `tests_locked_sha`
    уже стоит (тот же рецепт, что `LockTest.enter_in_dev` в
    `tests/test_acceptance_tests_flow.py`, ANSWER-3 вопрос 1, вариант б)."""

    def setUp(self):
        super().setUp()
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new,
                                           "Фикстура правки планки")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        # post-A7 cmd_new больше не заводит worktree/кодовую ветку сама
        # (ANSWER-2) — production amend.py читает правку Оператора именно
        # отсюда (ANSWER-3, вопрос 2), заводим явно ДО первой записи.
        wt_path, error = workspace.ensure(self.TASK, self.row()["branch"])
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.tdir = wt_path / "tasks" / self.TASK

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def git_wt(self, *args: str) -> str:
        """Git-запрос к АРТЕФАКТНОЙ ветке пульта (см. докстринг модуля):
        имя сохранено ради `test_ac6_commit_message_includes_reason.py`
        (локед, интерфейс не менялся) — правка планки коммитится туда,
        не в worktree кодовой ветки, поэтому запрос идёт в `config.ROOT`
        с явным именем ветки последним аргументом (валидный синтаксис
        `git log`/`show`: ревизия — обычный позиционный аргумент)."""
        res = subprocess.run(["git", "-C", str(config.ROOT), *args, self.branch],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C {config.ROOT} {' '.join(args)} {self.branch}: "
                         f"{res.stderr}")
        return res.stdout

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def head(self) -> str:
        """sha головы артефактной ветки — независимо от текущего чекаута
        (та же ветка, с которой сверяет лок гейт `in_dev -> review`)."""
        return gitcmd.branch_head_sha(self.branch)

    def artifact_commit(self, files: dict, message: str) -> str:
        """Коммитит `files` ПЛОТНИЦКИ прямо на артефактную ветку задачи
        (ANSWER-3, вопрос 1) — тем же приёмом, что `catalog._new_external_
        artifact_branch`/`checkpoint._commit_external_step_artifacts`."""
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} на артефактную ветку не удался")
        return sha

    def write_acceptance_tests(self, content: str) -> None:
        """Правка Оператора — физически в worktree кодовой ветки
        (`self.tdir`), тот самый каталог, который production `amend-tests`
        читает и коммитит на артефактную ветку (ANSWER-3, вопрос 2)."""
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(content, encoding="utf-8")

    def enter_in_dev(self) -> str:
        """Доводит задачу до `in_dev` с зафиксированным локом; возвращает
        sha лока (== HEAD артефактной ветки на этот момент)."""
        self.artifact_commit({f"tasks/{self.TASK}/SPEC.md":
                              SPEC_TPL.format(task=self.TASK)}, "SPEC")
        self.capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        self.capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.state(), "tests_writing")

        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_LOCKED},
            "acceptance_tests от test_author")
        self.capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        self.assertEqual(self.state(), "in_dev")

        locked = self.row()["tests_locked_sha"]
        self.assertEqual(locked, self.head(), "лок берёт sha этого коммита")
        return locked

    def run_amend(self, reason: str | None = "исправлена опечатка теста "
                  "(инцидент 03.09)", task_id: str = None) -> str:
        """Полный вывод команды правки планки (обычный stdout ИЛИ текст
        `sys.exit(...)`, если команда отказывает исключением) — критерии
        не фиксируют, каким из двух путей идёт честный отказ, тест
        собирает оба канала (тот же приём, что `run_dry_run` в прецеденте
        01M1GJ3ZP1YGG5QRB6FQ44NN8D)."""
        task_id = self.TASK if task_id is None else task_id
        cmd = discover_amend_command_name()
        argv = ["artel.py", cmd, task_id]
        if reason is not None:
            argv += ["--reason", reason]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            try:
                with redirect_stdout(buf):
                    artel.main()
            except SystemExit as exc:
                code = exc.code
                return buf.getvalue() + ("" if code is None else str(code))
        return buf.getvalue()
