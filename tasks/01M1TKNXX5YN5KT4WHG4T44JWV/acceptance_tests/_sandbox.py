"""Общая песочница приёмочных тестов задачи 01M1TKNXX5YN5KT4WHG4T44JWV
(«гейты `in_dev`/`review` как предикаты с единым исходом»).

Не сканируется guard'ом на AC-маркеры/тест-методы (только test_*.py,
SPEC T081) — файлы test_ac*.py этого каталога делят с ним фикстуры.

`GateChainSandbox` — тот же каркас настройки, что `tasks/
01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/_sandbox.py::GateSandbox`
(задача гейта ёмкости): задача в `in_dev` с готовым PLAN.md, переход
`in_dev -> review` через `fsm.cmd_advance`, с тем же `fake_git`. Эта
песочница ЗАВЕДОМО работает на переходе через РЕАЛЬНЫЙ диспетчер
(`in_dev`/`review` — публичные точки входа, чьи сигнатуры и имена
модульных функций-гейтов SPEC 01M1TKNXX5YN5KT4WHG4T44JWV требует
сохранить, AC-6) — тесты этого каталога намеренно НЕ зовут внутренние
предикаты по имени (кроме трёх уже существующих `_capacity_gate_refuses`/
`_zones_gate_refuses`/`_review_rework_gate_refuses`, чьи вызовы и
сигнатуры дословно фиксирует `tests/test_capacity_gate.py`/
`tests/test_zones_gate.py`/`tests/test_fsm_review_rework_gate.py`), чтобы
не изобретать имя ещё не написанного каркаса/типа исхода.

Нижняя половина файла (`find_immutable_outcome_type_names`/
`find_predicate_function_names`/`function_side_effect_calls`/
`function_body_line_count`/`function_if_nesting_depth`) — статический
AST-разбор `fsm_advance.py` для AC-1/AC-2/AC-6: критерии описывают
АРХИТЕКТУРУ кода (наличие типа-исхода, форма сигнатуры предиката, длина
и вложенность тела точки входа), не имя символа (SPEC сознательно не
называет тип в самих критериях приёмки — только пример «например
GateRefusal(...)» в разделе «Требования») — код ищет структуру, не
жёстко зашитое имя. Живёт в этом же файле, а не в отдельном `_gate_ast.
py`: guard засчитывает как «не постороннее» под `acceptance_tests/`
только `test_*.py`/`_sandbox.py`/`markers.py`/`__init__.py` (`scripts/
guard.py::ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL`) — второй файл с
подчёркиванием провалил бы сканирование посторонних файлов.
"""
import ast
import inspect
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import catalog, config, fsm, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import TmpRootTest, capture, capture_new_task_id, fake_git  # noqa: E402

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: гейт-каркас

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_CHANGES_REQUESTED = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 1
---

# REVIEW

## Замечания
major — доработать.
"""


def _log_reply(subject: str, when: str) -> str:
    return f"{when}\x1f{subject}\n"


class GateChainSandbox(TmpRootTest):
    """Задача в `in_dev` с готовым PLAN.md — переход `in_dev -> review`
    через `fsm.cmd_advance`, ветка не отстала от main (`commits_behind`
    заглушен нулём — подтяжка не звонится, только цепочка гейтов
    `fsm_advance.py`)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")

        self.wt_path = self.root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        with mock.patch.object(gitcmd, "git", fake_git):
            self.capture(catalog.cmd_init)
            _, self.TASK = capture_new_task_id(catalog.cmd_new, "Тест каркаса гейтов")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]
        self.write_plan_ready()
        self._set_state("in_dev")
        # Счётчики вызовов git-диффа каждого гейта — прямое доказательство
        # «гейт вообще не звался», не только «не отказал» (AC-3).
        self.diff_names_calls: list = []
        self.review_show_calls: list = []
        self.rework_log_calls: list = []

    def task_row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_rows(self) -> list:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def journal_details(self) -> list[str]:
        return [row[2] for row in self.journal_rows()]

    def refusal_rows(self) -> list:
        """Только строки журнала отказа перехода (`actor=fsm`, `action`
        начинается с «переход отклонён») — остальные строки (`created`,
        `lease взят`, `sha зафиксирован`, ...) сопровождают КАЖДЫЙ прогон
        независимо от исхода гейтов и не относятся к предмету AC-3/AC-4/
        AC-8."""
        return [row for row in self.journal_rows()
               if row[0] == "fsm" and row[1].startswith("переход отклонён")]

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def write_review_changes_requested(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_CHANGES_REQUESTED.format(task=self.TASK), encoding="utf-8")

    def set_zones(self, zones: str) -> None:
        store.update_task(store.db(), self.TASK, zones=zones)

    def _set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    # Лог-ответы гейта рубежа «замечания ревью не отработаны» — те же
    # значения, что `tests/test_fsm_review_rework_gate.py::
    # ReviewReworkGateFallbackTest.test_falls_back_to_last_review_md_commit_
    # and_still_refuses`: ни один коммит REVIEW.md не несёт префикс
    # автокоммита шага reviewer -> fallback на дату последнего коммита
    # REVIEW.md (2026-08-01), которая позже последнего коммита developer
    # (2026-07-31) -> гейт отказывает.
    _REWORK_LAST_REVIEW_MD_COMMIT = "2026-08-01T10:00:00+00:00\n"
    _REWORK_NO_REVIEWER_AUTOCOMMIT = _log_reply(
        "T001: правка REVIEW.md вручную", "2026-08-03T10:00:00+00:00")
    _REWORK_DEVELOPER_BEFORE_FALLBACK = _log_reply(
        "код фикса", "2026-07-31T10:00:00+00:00")

    def _git_stub(self, *, code_diff: str = "", artifacts_diff: str = "",
                 zone_files: list | None = None, rework_stale: bool = False):
        """Единый `gitcmd.git`-стаб на всю длительность прогона: различает
        диффы гейтов ПО ХВОСТУ АРГУМЕНТОВ (тот же приём, что и
        `tests/test_capacity_gate.py::CapacityGateTwoNumbersMessageTest`/
        `tests/test_zones_gate.py`), считает обращения к `--name-only`
        (гейт зон) и к любому `log` (гейт рубежа) — остальное отдаёт
        `fake_git` (PLAN.md/REVIEW.md с диска, идентичность роли).

        REVIEW.md отсутствует на диске (сценарии без `write_review_
        changes_requested()`) — `_review_rework_gate_refuses` возвращает
        `False` сразу на `gitcmd.show`, ни разу не позвав `log`: параметр
        `rework_stale` тогда не имеет значения."""
        tasks_prefix = f"tasks/{self.TASK}/"

        def stub(*args):
            if args and args[0] == "diff":
                if "--name-only" in args:
                    self.diff_names_calls.append(list(args))
                    files = zone_files or []
                    return subprocess.CompletedProcess(
                        list(args), 0, "\n".join(files), "")
                if f":!{tasks_prefix}" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, code_diff, "")
                if tasks_prefix in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, artifacts_diff, "")
            if args and args[0] == "log":
                self.rework_log_calls.append(list(args))
                if not rework_stale:
                    return subprocess.CompletedProcess(list(args), 0, "", "")
                if "-1" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, self._REWORK_LAST_REVIEW_MD_COMMIT, "")
                if "--" in args:
                    return subprocess.CompletedProcess(
                        list(args), 0, self._REWORK_NO_REVIEWER_AUTOCOMMIT, "")
                return subprocess.CompletedProcess(
                    list(args), 0, self._REWORK_DEVELOPER_BEFORE_FALLBACK, "")
            return fake_git(*args)
        return stub

    def advance(self, **gate_kwargs) -> str:
        """Прогон `fsm.cmd_advance` под общим стабом — возвращает stdout
        (`tests.sandbox.capture`)."""
        with mock.patch.object(gitcmd, "git", self._git_stub(**gate_kwargs)), \
                mock.patch.object(gitcmd, "commits_behind", return_value=0):
            return capture(fsm.cmd_advance, self.TASK)


# --------------------------------------------------------- AC-1/AC-2/AC-6
# Статический AST-разбор `orchestrator/fsm_advance.py` — см. докстринг
# модуля выше.

from orchestrator import fsm_advance as _fsm_advance  # noqa: E402

_FSM_ADVANCE_SOURCE = inspect.getsource(_fsm_advance)
_FSM_ADVANCE_TREE = ast.parse(
    _FSM_ADVANCE_SOURCE, filename=inspect.getsourcefile(_fsm_advance))


def _decorator_is_frozen_dataclass(dec: ast.expr) -> bool:
    """`@dataclass(frozen=True)`/`@dataclasses.dataclass(frozen=True)` —
    голый `@dataclass` без аргументов не в счёт: он мутируем по умолчанию,
    а AC-1 требует именно неизменяемость."""
    if not isinstance(dec, ast.Call):
        return False
    name = dec.func.id if isinstance(dec.func, ast.Name) else (
        dec.func.attr if isinstance(dec.func, ast.Attribute) else None)
    if name != "dataclass":
        return False
    return any(kw.arg == "frozen" and isinstance(kw.value, ast.Constant)
              and kw.value.value is True for kw in dec.keywords)


def _base_is_named_tuple(base: ast.expr) -> bool:
    name = base.id if isinstance(base, ast.Name) else (
        base.attr if isinstance(base, ast.Attribute) else None)
    return name == "NamedTuple"


def find_immutable_outcome_type_names() -> list[str]:
    """Имена классов модуля, объявленных как frozen-dataclass либо
    `NamedTuple` — обе формы неизменяемого типа-значения, которыми уже
    пользуется этот кодекс (`orchestrator/auto.py::Stop/Refused/Advanced/
    RoleRan`, тот же приём `@dataclass(frozen=True)`)."""
    names = []
    for node in ast.walk(_FSM_ADVANCE_TREE):
        if not isinstance(node, ast.ClassDef):
            continue
        if any(_decorator_is_frozen_dataclass(d) for d in node.decorator_list):
            names.append(node.name)
        elif any(_base_is_named_tuple(b) for b in node.bases):
            names.append(node.name)
    return names


def _annotation_is_optional_of(annotation: ast.expr, type_name: str) -> bool:
    """`<type_name> | None` (PEP 604) в любом порядке операндов — буквальная
    форма сигнатуры из AC-2: «(conn, task_id, t, ...) -> <тип исхода> |
    None»."""
    if not isinstance(annotation, ast.BinOp) or not isinstance(annotation.op, ast.BitOr):
        return False
    sides = (annotation.left, annotation.right)
    has_type = any(isinstance(s, ast.Name) and s.id == type_name for s in sides)
    has_none = any(isinstance(s, ast.Constant) and s.value is None for s in sides)
    return has_type and has_none


def find_predicate_function_names(type_name: str) -> list[str]:
    """Имена функций модуля верхнего уровня, чья аннотация возврата —
    ровно `<type_name> | None`."""
    names = []
    for node in _FSM_ADVANCE_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.returns is not None \
                and _annotation_is_optional_of(node.returns, type_name):
            names.append(node.name)
    return names


class _CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.store_journal_calls = 0
        self.print_calls = 0

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "journal" \
                and isinstance(func.value, ast.Name) and func.value.id == "store":
            self.store_journal_calls += 1
        if isinstance(func, ast.Name) and func.id == "print":
            self.print_calls += 1
        self.generic_visit(node)


def function_side_effect_calls(func_name: str) -> tuple[int, int]:
    """(число вызовов `store.journal(...)`, число вызовов `print(...)`)
    внутри ТЕЛА функции `func_name`, объявленной в `fsm_advance.py`
    (не считая вложенных def — гейт-предикат не имеет права журналировать
    или печатать НИ ЧЕРЕЗ КОГО в своём собственном теле)."""
    for node in _FSM_ADVANCE_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            collector = _CallCollector()
            for stmt in node.body:
                collector.visit(stmt)
            return collector.store_journal_calls, collector.print_calls
    raise LookupError(f"функция {func_name} не найдена в fsm_advance.py")


def function_body_line_count(func_name: str) -> int:
    """Число строк исходника функции `func_name`, кроме самой строки
    `def ...:` — прямое измерение «тела» из AC-6 («≤ 40 строк тела
    каждой»)."""
    func = getattr(_fsm_advance, func_name)
    source_lines = inspect.getsource(func).splitlines()
    return len(source_lines) - 1


def _max_if_nesting_depth(stmts: list, depth: int = 0) -> int:
    """Наибольшая глубина настоящего `if` ВНУТРИ ТЕЛА другого `if`.

    `elif`/`else` разбираются `ast` как вложенный `If` в `orelse` того же
    узла — синтаксически неотличимо от «`if` внутри `else`», поэтому
    `orelse` обходится на ТОЙ ЖЕ глубине (цепочка `if/elif/elif` не
    наращивает вложенность условий), а глубже уходит только `body`
    (настоящее «условие внутри условия»). Другие составные операторы
    (`for`/`while`/`with`/`try`) обходятся на той же глубине — AC-6 говорит
    именно про вложенность УСЛОВИЙ, не циклов."""
    best = depth
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            best = max(best, _max_if_nesting_depth(stmt.body, depth + 1))
            best = max(best, _max_if_nesting_depth(stmt.orelse, depth))
        else:
            for field in ("body", "orelse", "finalbody"):
                sub = getattr(stmt, field, None)
                if sub:
                    best = max(best, _max_if_nesting_depth(sub, depth))
    return best


def function_if_nesting_depth(func_name: str) -> int:
    """Глубина вложенности `if` в теле функции `func_name` — 0, если тело
    вовсе не содержит настоящего `if` внутри `if`."""
    for node in _FSM_ADVANCE_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return _max_if_nesting_depth(node.body, 0)
    raise LookupError(f"функция {func_name} не найдена в fsm_advance.py")
