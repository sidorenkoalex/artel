"""Общая песочница приёмочных тестов «сухого прогона приёмки»
(tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md).

Реальный git (`tests.sandbox.RealGitSandbox`, тот же приём, что
`tests/test_answer_branch_reads.py::_AnswerRealGitSandbox` и
`tasks/T075/acceptance_tests/test_ac2_answer_command.py`): предмет
проверки этой задачи — ветко-корректное чтение (инвариант 28), заглушка
`gitcmd.git` не отличает ветку от диска и не годится.

Имя команды НЕ фиксировано. SPEC (требование 1) явно отдаёт имя команды
и модуль её реализации на усмотрение разработчика — критерии приёмки
описывают НАБЛЮДАЕМОЕ ПОВЕДЕНИЕ команды, а не её идентификатор в CLI.
Зашить конкретное имя в тест значило бы самовольно принять решение,
которое SPEC явно оставляет разработчику (skills/escalation-rules.md:
«не выбирать интерпретацию на свой вкус»). Вместо этого
`discover_dry_run_command_name()` находит имя статическим разбором AST
таблицы диспетчера `orchestrator/artel.py::main` (`table = {...}`) как
разницу с `BASELINE_COMMANDS` — снимком команд ДО этой задачи. Разбор
статический (`ast`, без импорта/исполнения) — часть команд таблицы
мутирующая, вслепую звать их нельзя, поэтому вызывается только та ОДНА
команда, что появится сверх снимка. Приём таблицы `table = {"cmd":
lambda: ...}` внутри `main()` — установленная конвенция регистрации,
общая для всех ~24 сегодняшних команд (сам файл, строки 298-328); нет
основания ждать, что новая команда будет зарегистрирована иначе.

Красен до реализации: до кода задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D в
таблице диспетчера нет ни одной команды сверх `BASELINE_COMMANDS` —
`discover_dry_run_command_name()` падает `AssertionError` с понятным
текстом ещё до того, как тест успевает проверить хоть что-то по
существу.
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

from orchestrator import artel, config, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

ARTEL_PY = REPO_ROOT / "orchestrator" / "artel.py"

# Ключи `table` в orchestrator/artel.py::main на HEAD этой задачи, ДО
# реализации SPEC 01M1GJ3ZP1YGG5QRB6FQ44NN8D (снимок строк 298-328
# файла на момент написания этих тестов) — заведомо НЕ включает команду
# сухого прогона приёмки, которую заведёт разработчик.
BASELINE_COMMANDS = frozenset({
    "init", "new", "status", "show", "advance", "workspace", "run", "auto",
    "approve", "reject", "answer", "kill", "release", "pause", "resume",
    "log", "budget", "target-init", "doctor", "alert-ack", "version",
    "canary", "prune", "report",
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


def discover_dry_run_command_name() -> str:
    """Имя новой read-only CLI-команды сухого прогона приёмки — см.
    докстринг модуля про то, почему оно не зашито литералом."""
    source = ARTEL_PY.read_text(encoding="utf-8")
    added = _dispatch_table_keys(source) - BASELINE_COMMANDS
    assert added, (
        "новая команда сухого прогона приёмки не найдена в таблице "
        "диспетчера orchestrator/artel.py::main — код "
        "tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D ещё не реализован (SPEC "
        "требование 1)")
    assert len(added) == 1, (
        f"в таблице диспетчера появилось больше одной новой команды: "
        f"{sorted(added)} — тест не может однозначно выбрать, какая из "
        f"них сухой прогон приёмки")
    return next(iter(added))


FIXTURE_TASK = "T900"
FIXTURE_BRANCH = "task/t900-suhoy-progon-fixture"

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура сухого прогона

## Критерии приёмки

{ac_section}
"""


class DryRunSandbox(RealGitSandbox):
    """Ветка `FIXTURE_BRANCH` задачи `FIXTURE_TASK` — SPEC.md и
    acceptance_tests/ живут только там; рабочая копия (`self.root`)
    остаётся на `main` весь тест, ровно тот чужой чекаут, о котором
    AC-7 (то же расхождение, что `_AnswerRealGitSandbox`)."""

    TASK = FIXTURE_TASK
    BRANCH = FIXTURE_BRANCH

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def seed_task(self, state: str = "in_dev", branch: str = None,
                  task_id: str = None) -> None:
        task_id = self.TASK if task_id is None else task_id
        branch = self.BRANCH if branch is None else branch
        store.insert_task(self.conn, task_id, "Фикстура сухого прогона",
                          state, branch, config.DEFAULT_TARGET, 25.0)

    def _branch_exists_locally(self, branch: str) -> bool:
        res = subprocess.run(["git", "branch", "--list", branch],
                             cwd=self.root, capture_output=True, text=True)
        return bool(res.stdout.strip())

    def commit_fixture(self, ac_section: str, test_files: dict,
                       branch: str = None, task_id: str = None) -> None:
        """Коммитит SPEC.md + acceptance_tests/*.py на `branch` (заводит
        её, если нет) и возвращает рабочую копию на main. `task_id`
        отдельно от `self.TASK` — нужно тестам, сравнивающим ДВЕ
        независимые фикстуры-задачи в одном сценарии (differential-тест
        трассируемости, AC-3)."""
        task_id = self.TASK if task_id is None else task_id
        branch = self.BRANCH if branch is None else branch
        self.checkout(branch, create=not self._branch_exists_locally(branch))
        d = self.root / "tasks" / task_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(
            SPEC_TEMPLATE.format(task=task_id, ac_section=ac_section),
            encoding="utf-8")
        if test_files:
            tests_dir = d / "acceptance_tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            for name, content in test_files.items():
                (tests_dir / name).write_text(content, encoding="utf-8")
        # `add "tasks/<id>"`, не `-A`: `-A` подхватил бы и untracked
        # `.artel/state.db` рабочей копии в коммит фикстурной ветки — на
        # возврате `checkout(config.MAIN_BRANCH)` git тогда удаляет файл
        # с диска (он не отслежен на main), унося таблицы БД теста.
        self.git("add", f"tasks/{task_id}")
        self.git("commit", "-q", "-m", "фикстура сухого прогона")
        self.checkout(config.MAIN_BRANCH)

    def run_dry_run(self, task_id: str = None) -> str:
        """Полный вывод команды (обычный stdout ИЛИ текст `sys.exit(...)`,
        если команда отказывает исключением) — критерии не фиксируют,
        каким из двух путей идёт честный отказ (AC-8), тест собирает
        оба канала."""
        task_id = self.TASK if task_id is None else task_id
        cmd = discover_dry_run_command_name()
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", cmd, task_id]):
            try:
                with redirect_stdout(buf):
                    artel.main()
            except SystemExit as exc:
                code = exc.code
                return buf.getvalue() + ("" if code is None else str(code))
        return buf.getvalue()
