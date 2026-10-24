"""Общий разбор планки волны 2б-4 сведения тестов: 13 тестов
`tests/test_component_report_gates.py` (crg) — функциями в
`tests/test_report_outcome_module.py`, crg удаляется.

Только чистые функции и вызовы git по переданному репозиторию: модуль не
импортирует `_pult` — значения выкладки (корень рабочей копии, база диффа,
репозиторий и ревизия ссылки документов) передают сами тесты.

Соглашения разбора PLAN.md, которых держится вся планка:

- раздел — заголовок markdown (`#`…`######`) вне ограждения кода; строки
  шапки таблицы `mutation-run` (`# mutation-run №…`, `# источник патчей:`,
  `# ревизия прогона:`, `# тесты:`, `# рабочих процессов:`, `# патч …`)
  заголовками не считаются; раздел длится до следующего заголовка того же
  или более высокого уровня;
- таблица `mutation-run` — текст, напечатанный командой
  (`orchestrator/mutation_run.py::_header`, `_Run.row`): шапка из строк
  `# …`, строка колонок `номер<TAB>исход<TAB>узлы` и строки
  `<номер><TAB><исход><TAB><узлы через запятую>`;
- ссылка на мутацию в тексте PLAN — имя патча `mutation-<nnn>` (с `.diff`
  или без) либо `мутация <n>` / `мутация №<n>` (любая форма слова);
- ссылка на тест crg — `<Класс>::<метод>`, с префиксом
  `tests/test_component_report_gates.py::` или без него; ссылка на узел
  модуля — `test_report_outcome_module.py::<функция>` (с префиксом `tests/`
  или без, с вариантом `[<вариант>]` или без — без варианта она покрывает
  все варианты функции);
- упавшее утверждение — ссылка `tests/<файл>.py:<строка>` (как в логе
  прогона патча `mutation-run`) в той же строке PLAN, что ссылка на
  мутацию и на убивший узел;
- перенос «тест crg → функция модуля»: функция модуля с тем же именем, что
  метод crg, либо строка PLAN вне таблиц, где стоит ровно одна ссылка на
  тест crg и ссылка на новую функцию модуля (не на один из 26 тестов базы);
- перечни (удалённые дубли, узлы, убитые падением подготовки, находки) —
  строки PLAN вне таблиц, где ссылка на тест (узел) и ссылка на мутацию
  стоят в ОДНОЙ строке; удалённые дубли — строки раздела, в заголовке
  которого есть слово «дубл…»; находки — строки со словом «находк…» либо
  строки раздела, в заголовке которого оно есть; узлы, убитые падением
  подготовки, — строки со словом `setUp` или «подготовк…».

«То же утверждение» (решение гейта SPEC, ANSWER-1 п. 3) — одна нормальная
форма: `self.assert*(…)` переводится в выражение `assert` (`assertEqual(a, b)`
→ `a == b`, `assertFalse(x)` → `not x`, …), сообщение отброшено, `self` и
стенд функции модуля — одна метка, вызов `<стенд>.<помощник>(…)` и
`<помощник>(<стенд>, …)` — одна форма (ANSWER-1 п. 2), префикс `crg_`/`CRG_`
снят; у `==`/`!=` порядок операндов не различается.
"""
import ast
import copy
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

SOURCE_FILE = "tests/test_component_report_gates.py"
NEW_FILE = "tests/test_report_outcome_module.py"
SANDBOX_FILE = "tests/report_outcome_sandbox.py"
SANDBOX_MODULE = "tests.report_outcome_sandbox"
MAP_FILE = "docs/codebase-map.md"
CLAIM = "Ловит мутацию"
CLAIM_COUNT = 13
EXISTING_TESTS = 26
WORKERS = "4"

# Определения верхнего уровня crg, переносимые дословно (требование 8).
DEFINITIONS = ("profile", "check", "UNKNOWN", "GREEN", "Reached")

# Методы тестовых классов crg без утверждений (требование 10): имя → класс.
HELPERS = {
    "suite": "AcceptanceSuiteChecksLocalTest",
    "approve": "AcceptanceSuiteChecksLocalTest",
    "two_components": "MergeGateComponentsTest",
    "selected": "MergeGateComponentsTest",
    "check_script": "ChecksLocalFromRecordTest",
    "checked_case": "ChecksLocalFromRecordTest",
    "journal": "ChecksLocalFromRecordTest",
    "merge": "ChecksLocalFromRecordTest",
}

# Стенды (требование 9): класс crg → обязательный параметр функции модуля;
# `None` — функция без параметров-фикстур.
STANDS = {
    "AcceptanceSuiteChecksLocalTest": "checks_stand",
    "ReportArgvTest": "box",
    "InstallLockTest": "tmp_dir",
    "SuiteRunParseReportedTest": None,
    "MergeGateComponentsTest": "box",
    "SuiteRunKeyTest": "box",
    "ChecksLocalFromRecordTest": "box",
    "EmptyInstallTest": "box",
}
STAND_NAMES = ("self", "box", "checks_stand", "tmp_dir", "stand")

# Наборы `subTest` (требование 11): литеральные без общего состояния —
# `parametrize`; нелитеральный и с общим состоянием — прежним циклом.
PARAMETRIZED = ("AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths",
                "AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green")
LOOPED = ("ReportArgvTest::test_pytest_args_only_for_pytest_command",
          "SuiteRunKeyTest::test_merge_gate_and_suite_run_keys_match_with_tools",
          "ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite")

# Утверждения подготовки песочницы (требование 4) и `setUp`: падение в них —
# не доказательство.
PREP_METHODS = ("setUp", "profile", "table", "accepted_major", "cache_flag")

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
UNKNOWN_OUTCOME = "итог неизвестен"
CUT = "оборвана по пределу"
NOT_RUN = "не прогнана (предел)"
NOT_APPLIED = "патч не применяется"
TOUCHES = "патч трогает тесты"
# Исходы, при которых мутация не засчитана ни убитой, ни выжившей (AC-4).
UNDECIDED = (UNKNOWN_OUTCOME, NOT_APPLIED, TOUCHES, NOT_RUN, CUT)
OUTCOMES = (KILLED, SURVIVED, COLLECTION, *UNDECIDED)

PATCH_NAME = re.compile(r"^mutation-(\d{3,})\.diff$")
# Справочная копия таблицы `mutation-run --copy-table` (ANSWER-1 п. 1).
TABLE_COPY = re.compile(r"^mutation-run-\d+\.tsv$")

_HEAD = re.compile(r"^# mutation-run №(\d+) задачи (\S+)$")
_SOURCE = re.compile(r"^# источник патчей: (\S.*)$")
_REVISION = re.compile(r"^# ревизия прогона: (base|head|worktree) ([0-9a-f]{7,64})$")
_TESTS = re.compile(r"^# тесты: (\S.*)$")
_WORKERS = re.compile(r"^# рабочих процессов: (\S+)$")
_PATCH = re.compile(r"^# патч (\d+) (\S+) sha256 ([0-9a-f]{64})$")
_COLUMNS = "номер\tисход\tузлы"
_ROW = re.compile(r"^(\d+)\t([^\t]+)(?:\t([^\t]*))?$")
_TABLE_LINE = (_HEAD, _SOURCE, _REVISION, _TESTS, _WORKERS, _PATCH)
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

_REF = (re.compile(r"mutation-0*(\d+)(?!\d)"),
        re.compile(r"[Мм]утаци[а-яё]*\s+№?\s*0*(\d+)(?!\d)"))
_TEST_KEY = re.compile(
    r"(?<![\w.])(?:tests/[\w./-]+\.py::)?([A-Za-z_]\w*)::(test\w*)")
_AFTER_REF = re.compile(
    r"test_report_outcome_module\.py::(test\w*)(\[[^\]\s]*\])?")
_FILE_LINE = re.compile(r"(tests/[\w./-]+\.py):(\d+)(?!\d)")

_REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
             "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
             "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")


# ------------------------------------------------------------------- git

def git(repo, *args: str) -> subprocess.CompletedProcess:
    """`git -C <repo> <args>` без переменных, уводящих git в чужой репозиторий."""
    env = {k: v for k, v in os.environ.items() if k not in _REPO_ENV}
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo).parent)
    return subprocess.run(["git", "-C", str(repo), *args], env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def git_out(repo, *args: str) -> str:
    res = git(repo, *args)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} в {repo} вернул "
                           f"{res.returncode}: {res.stderr.strip()}")
    return res.stdout


def show(repo, revision: str, path: str) -> str | None:
    """Текст `path` ревизии `revision`; файла там нет — None."""
    res = git(repo, "show", f"{revision}:{path}")
    return res.stdout if res.returncode == 0 else None


def docs_entry_types(docs_repo, revision: str, task_id: str) -> dict[str, str]:
    """{имя первого уровня `tasks/<id>/`: тип объекта git (`blob`/`tree`)}."""
    rel = f"tasks/{task_id}/"
    out = git_out(docs_repo, "ls-tree", "-z", revision, "--", rel)
    found = {}
    for item in out.split("\0"):
        meta, _tab, path = item.partition("\t")
        if path.startswith(rel) and meta:
            found[path[len(rel):]] = meta.split()[1]
    return found


def patch_names(entries) -> dict[int, str]:
    """{номер: имя} патчей мутаций первого уровня каталога задачи."""
    found = {}
    for name in entries:
        match = PATCH_NAME.match(name)
        if match:
            found[int(match.group(1))] = name
    return found


# ---------------------------------------------------------------- патчи

def _strip_side(path: str) -> str | None:
    path = path.strip().strip('"')
    if path == "/dev/null":
        return None
    return path[2:] if path[:2] in ("a/", "b/") else path


def patch_paths(text: str) -> set[str]:
    """Пути патча: заголовки `diff --git`, `---`/`+++`, переименования."""
    paths = set()
    for line in text.splitlines():
        if line.startswith("diff --git "):
            left, sep, right = line[len("diff --git "):].partition(" b/")
            for part in ([left, "b/" + right] if sep else
                         line[len("diff --git "):].split()):
                stripped = _strip_side(part)
                if stripped:
                    paths.add(stripped)
        elif line.startswith(("--- ", "+++ ")):
            stripped = _strip_side(line[4:].split("\t", 1)[0])
            if stripped:
                paths.add(stripped)
        else:
            for head in ("rename from ", "rename to ", "copy from ",
                         "copy to "):
                if line.startswith(head):
                    paths.add(line[len(head):].strip())
    return {os.path.normpath(p).replace(os.sep, "/") for p in paths}


def changed_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines()
               if line[:1] in "+-" and not line.startswith(("+++ ", "--- ")))


# ------------------------------------------------------------- разделы PLAN

def _is_table_line(line: str) -> bool:
    return any(p.match(line) for p in _TABLE_LINE)


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """[(индекс строки, уровень, текст)] заголовков вне ограждений кода."""
    found, fenced = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or _is_table_line(line):
            continue
        match = _HEADING.match(line)
        if match:
            found.append((i, len(match.group(1)), match.group(2)))
    return found


def sections(plan: str, word: str) -> list[str]:
    """Тексты разделов, в заголовке которых есть `word` (без учёта
    регистра); раздел — до заголовка того же или более высокого уровня."""
    lines = plan.split("\n")
    heads = _headings(lines)
    result = []
    for n, (start, level, title) in enumerate(heads):
        if word.casefold() not in title.casefold():
            continue
        end = len(lines)
        for nxt, nlevel, _t in heads[n + 1:]:
            if nlevel <= level:
                end = nxt
                break
        result.append("\n".join(lines[start + 1:end]))
    return result


def prose_lines(text: str) -> list[str]:
    """Строки текста без строк таблиц `mutation-run` (шапка, колонки, строки)."""
    return [line for line in text.split("\n")
            if not _is_table_line(line) and line != _COLUMNS
            and not _ROW.match(line)]


def refs(line: str) -> set[int]:
    """Номера мутаций, на которые ссылается строка."""
    found = set()
    for pattern in _REF:
        found.update(int(m) for m in pattern.findall(line))
    return found


def test_keys(line: str) -> set[str]:
    """Ссылки строки на тесты crg в виде `<Класс>::<метод>`."""
    return {f"{c}::{m}" for c, m in _TEST_KEY.findall(line)}


def after_refs(line: str) -> set[tuple[str, str]]:
    """Ссылки строки на узлы модуля: {(функция, вариант или "")}."""
    return {(func, variant) for func, variant in _AFTER_REF.findall(line)}


def file_lines(line: str) -> list[tuple[str, int]]:
    """Ссылки строки вида `tests/<файл>.py:<строка>`."""
    return [(path, int(n)) for path, n in _FILE_LINE.findall(line)]


def node_key(node: str) -> str:
    """`tests/<файл>.py::<Класс>::<метод>` → `<Класс>::<метод>`."""
    keys = test_keys(node)
    return next(iter(keys)) if len(keys) == 1 else node


def after_node_parts(node: str) -> tuple[str, str]:
    """`tests/test_report_outcome_module.py::<функция>[<вариант>]` →
    (функция, `[<вариант>]` или "")."""
    tail = node.rsplit("::", 1)[-1]
    func, bracket, rest = tail.partition("[")
    return func, (bracket + rest) if bracket else ""


def after_marked(node: str, marks: set[tuple[str, str]]) -> bool:
    """Узел модуля попадает под отметку: та же функция и тот же вариант,
    либо отметка без варианта."""
    func, variant = after_node_parts(node)
    return (func, "") in marks or (func, variant) in marks


# ------------------------------------------------------------ таблицы

class Table:
    def __init__(self):
        self.run_no = None
        self.task = ""
        self.source = ""
        self.ref = ""
        self.sha = ""
        self.tests: list[str] = []
        self.workers = ""
        self.patches: dict[int, tuple[str, str]] = {}
        self.rows: list[tuple[int, str, list[str]]] = []


def tables(text: str) -> tuple[list[Table], list[str]]:
    """(таблицы `mutation-run` текста, ошибки формата шапки)."""
    lines = text.split("\n")
    found, errors = [], []
    i = 0
    while i < len(lines):
        head = _HEAD.match(lines[i])
        if not head:
            i += 1
            continue
        table = Table()
        table.run_no, table.task = int(head.group(1)), head.group(2)
        i += 1
        expected = ((_SOURCE, "источник патчей"), (_REVISION, "ревизия прогона"),
                    (_TESTS, "тесты"), (_WORKERS, "рабочих процессов"))
        broken = False
        for pattern, what in expected:
            match = pattern.match(lines[i]) if i < len(lines) else None
            if not match:
                errors.append(f"таблица №{table.run_no}: нет строки шапки "
                              f"«# {what}: …» на своём месте (строка "
                              f"{lines[i] if i < len(lines) else '<конец>'!r})")
                broken = True
                break
            if pattern is _SOURCE:
                table.source = match.group(1)
            elif pattern is _REVISION:
                table.ref, table.sha = match.group(1), match.group(2)
            elif pattern is _TESTS:
                table.tests = [t.strip() for t in match.group(1).split(",")]
            else:
                table.workers = match.group(1)
            i += 1
        if broken:
            continue
        while i < len(lines) and _PATCH.match(lines[i]):
            match = _PATCH.match(lines[i])
            table.patches[int(match.group(1))] = (match.group(2), match.group(3))
            i += 1
        if i >= len(lines) or lines[i] != _COLUMNS:
            errors.append(f"таблица №{table.run_no}: после строк патчей нет "
                          f"строки колонок {_COLUMNS!r}")
            continue
        i += 1
        while i < len(lines) and _ROW.match(lines[i]):
            match = _ROW.match(lines[i])
            nodes = [n for n in (match.group(3) or "").split(",") if n]
            table.rows.append((int(match.group(1)), match.group(2), nodes))
            i += 1
        found.append(table)
    return found, errors


def last_rows(found: list[Table]) -> dict[int, tuple[str, list[str]]]:
    rows = {}
    for table in found:
        for number, outcome, nodes in table.rows:
            rows[number] = (outcome, nodes)
    return rows


def last_patch_sha(found: list[Table]) -> dict[int, str]:
    shas = {}
    for table in found:
        for number, (_name, sha) in table.patches.items():
            shas[number] = sha
    return shas


def killed(rows: dict) -> dict[int, list[str]]:
    """{номер: убившие узлы} мутаций с исходом «убита» и непустыми узлами."""
    return {n: nodes for n, (outcome, nodes) in rows.items()
            if outcome == KILLED and nodes}


# --------------------------------------------------------- исходные тесты

class BaseTest:
    def __init__(self, cls: str, func: ast.FunctionDef):
        self.cls, self.func = cls, func
        self.key = f"{cls}::{func.name}"
        self.claim = CLAIM in (ast.get_docstring(func) or "")


def base_tests(text: str) -> list[BaseTest]:
    """Тестовые методы классов crg."""
    found = []
    for node in ast.parse(text).body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name.startswith("test"):
                    found.append(BaseTest(node.name, item))
    return found


def class_method(tree, cls: str, method: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == method:
                    return item
    return None


def bound_names(node) -> list[str]:
    """Имена, которые связывает оператор верхнего уровня модуля."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(a.asname or a.name).split(".")[0] for a in node.names]
    targets = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    names = []
    for target in targets:
        names += [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
    return names


def top_names(tree) -> set[str]:
    return {name for node in tree.body for name in bound_names(node)}


def local_names(func) -> set[str]:
    """Имена в контексте записи и параметры функции (на любой глубине)."""
    names = {n.id for n in ast.walk(func)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    for node in ast.walk(func):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            names |= {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
    return names


def constants(node) -> set:
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and not isinstance(sub.value, bool) \
                and isinstance(sub.value, (str, int, float)):
            found.add(sub.value)
    return found


def is_method_assert(node) -> bool:
    """Вызов `<что угодно>.assert*(...)` (кроме `assertRaises*`)."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and not node.func.attr.startswith("assertRaises"))


def self_asserts(func) -> list[ast.Call]:
    """`self.assert*(…)` (кроме `assertRaises*`) в теле метода crg."""
    return [n for n in ast.walk(func) if is_method_assert(n)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"]


_ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


def semantic_args(call: ast.Call) -> list:
    count = 1 if call.func.attr in _ONE_ARG else 2
    return list(call.args[:count])


def assertion_literals(func) -> set:
    """Литералы смысловых аргументов `self.assert*` метода crg."""
    found = set()
    for call in self_asserts(func):
        for arg in semantic_args(call):
            found |= constants(arg)
    return found


def assertion_kinds(func) -> set[str]:
    return {call.func.attr for call in self_asserts(func)}


# ------------------------------------------------------- модуль (ast)

def is_fixture(func) -> bool:
    for deco in func.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
    return False


def module_tests(tree) -> list[ast.FunctionDef]:
    return [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test")]


def module_functions(tree) -> dict:
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def parametrize_decorators(func) -> list[ast.Call]:
    return [d for d in func.decorator_list
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
            and d.func.attr == "parametrize"]


def parametrize_names(func) -> set[str]:
    names = set()
    for deco in parametrize_decorators(func):
        if not deco.args:
            continue
        first = deco.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names |= {n.strip() for n in first.value.split(",") if n.strip()}
        elif isinstance(first, (ast.List, ast.Tuple)):
            names |= {e.value for e in first.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return names


def fixture_params(func) -> list[str]:
    """Параметры функции модуля, кроме имён `parametrize`."""
    names = parametrize_names(func)
    return [a.arg for a in func.args.args + func.args.kwonlyargs
            if a.arg not in names]


def is_pytest_raises(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "raises"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest")


def is_pytest_fail(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fail"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest")


def class_prefixed(name: str, method: str, cls: str) -> bool:
    """`name` — имя `method` с непустым префиксом бывшего класса `cls`:
    `name` кончается на `method`, перед ним непустой префикс, который без
    подчёркиваний и регистра входит в имя класса без регистра."""
    if not name.endswith(method) or name == method:
        return False
    prefix = name[:-len(method)].replace("_", "").casefold()
    return bool(prefix) and prefix in cls.casefold()


def helper_function_names(funcs: dict) -> dict[str, str]:
    """{метод-помощник crg: имя функции модуля} — голое имя либо имя с
    префиксом бывшего класса (первое найденное в порядке имён)."""
    found = {}
    for method, cls in HELPERS.items():
        if method in funcs:
            found[method] = method
            continue
        for name in sorted(funcs):
            if class_prefixed(name, method, cls):
                found[method] = name
                break
    return found


# ------------------------------------------------------ преобразования (ast)

class _SelfToParam(ast.NodeTransformer):
    """`self.<помощник>(…)` → `<функция>(<стенд>, …)`; прочие `self` →
    имя стенда."""

    def __init__(self, param: str, calls: dict):
        self.param, self.calls = param, calls

    def visit_Call(self, node):
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == self.param and func.attr in self.calls:
            node.func = ast.Name(id=self.calls[func.attr], ctx=ast.Load())
            node.args = [ast.Name(id=self.param, ctx=ast.Load()), *node.args]
        return node

    def visit_Name(self, node):
        if node.id == "self":
            node.id = self.param
        return node


def strip_docstring(body: list) -> list:
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        return body[1:]
    return body


def expected_helper_body(method, param: str, calls: dict) -> str:
    """`ast.dump` тела метода crg, переведённого в функцию модуля:
    `self.` → стенд, `self.<помощник>(…)` → `<функция>(<стенд>, …)`."""
    node = copy.deepcopy(method)
    node = _SelfToParam(param, calls).visit(node)
    return ast.dump(ast.Module(body=strip_docstring(node.body), type_ignores=[]))


def body_dump(func) -> str:
    return ast.dump(ast.Module(body=strip_docstring(copy.deepcopy(func).body),
                               type_ignores=[]))


def rest_args_dump(args: ast.arguments) -> str:
    """`ast.dump` параметров без первого (стенда или `self`)."""
    node = copy.deepcopy(args)
    node.args = node.args[1:]
    return ast.dump(node)


# ------------------------------------------- нормальная форма утверждения

_STAND = "<стенд>"
_COMPARE = {"assertEqual": ast.Eq, "assertNotEqual": ast.NotEq,
            "assertIn": ast.In, "assertNotIn": ast.NotIn,
            "assertIs": ast.Is, "assertIsNot": ast.IsNot,
            "assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE,
            "assertLess": ast.Lt, "assertLessEqual": ast.LtE}


class _Canon(ast.NodeTransformer):
    def __init__(self, stands: set, helpers: dict):
        self.stands, self.helpers = stands, helpers

    def visit_Name(self, node):
        if node.id in self.stands:
            return ast.Name(id=_STAND, ctx=ast.Load())
        for prefix in ("crg_", "CRG_"):
            if node.id.startswith(prefix) and node.id[len(prefix):] in DEFINITIONS:
                return ast.Name(id=node.id[len(prefix):], ctx=ast.Load())
        return ast.Name(id=node.id, ctx=ast.Load())

    def visit_Call(self, node):
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Name) and func.id in self.helpers and node.args \
                and isinstance(node.args[0], ast.Name) and node.args[0].id == _STAND:
            node.func = ast.Attribute(value=ast.Name(id=_STAND, ctx=ast.Load()),
                                      attr=self.helpers[func.id], ctx=ast.Load())
            node.args = node.args[1:]
        return node


def _expression(node):
    """Выражение `assert` для утверждения `node`; `None` — не утверждение."""
    if isinstance(node, ast.Assert):
        return node.test
    if is_pytest_raises(node) or (isinstance(node, ast.Call)
                                  and isinstance(node.func, ast.Attribute)
                                  and node.func.attr == "assertRaises"):
        exc = node.args[0] if node.args else ast.Constant(None)
        return ast.Call(func=ast.Name(id="<raises>", ctx=ast.Load()),
                        args=[exc], keywords=[])
    if not is_method_assert(node):
        return None
    name, args = node.func.attr, list(node.args)
    if name == "assertTrue" and args:
        return args[0]
    if name == "assertFalse" and args:
        return ast.UnaryOp(op=ast.Not(), operand=args[0])
    if name in ("assertIsNone", "assertIsNotNone") and args:
        op = ast.Is() if name == "assertIsNone" else ast.IsNot()
        return ast.Compare(left=args[0], ops=[op],
                           comparators=[ast.Constant(None)])
    if name in _COMPARE and len(args) >= 2:
        return ast.Compare(left=args[0], ops=[_COMPARE[name]()],
                           comparators=[args[1]])
    return ast.Call(func=ast.Name(id=f"<{name}>", ctx=ast.Load()),
                    args=args[:2], keywords=[])


def canon(node, stands, helpers: dict | None = None) -> str | None:
    """Нормальная форма утверждения `node` (см. докстринг модуля)."""
    expr = _expression(node)
    if expr is None:
        return None
    # helpers: {имя функции модуля: имя метода crg}
    expr = _Canon(set(stands), helpers or {}).visit(copy.deepcopy(expr))
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and \
            isinstance(expr.ops[0], (ast.Eq, ast.NotEq)):
        left, right = ast.dump(expr.left), ast.dump(expr.comparators[0])
        if right < left:
            expr = ast.Compare(left=expr.comparators[0], ops=expr.ops,
                               comparators=[expr.left])
    return ast.dump(expr)


def assertion_nodes(func) -> list:
    """Утверждения тела: `assert`, `<что-то>.assert*`, `assertRaises`,
    `pytest.raises`."""
    return [n for n in ast.walk(func)
            if isinstance(n, ast.Assert) or is_method_assert(n)
            or is_pytest_raises(n)
            or (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "assertRaises")]


def canon_counter(func, stands, helpers=None) -> Counter:
    return Counter(c for c in (canon(n, stands, helpers)
                               for n in assertion_nodes(func)) if c)


def raises_of_fail(tree, fail_node):
    """`pytest.raises(…)` блока `with`, внутри которого стоит `pytest.fail`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(n is fail_node for s in node.body
                                              for n in ast.walk(s)):
            for item in node.items:
                if is_pytest_raises(item.context_expr):
                    return item.context_expr
    return None


def site(text: str, line: int):
    """(узел утверждения, объемлющие функции — от внешней к внутренней) для
    строки `line`; узел `None` — строка не в утверждении. `pytest.fail`
    внутри блока `pytest.raises` — утверждение этого `pytest.raises`."""
    tree = ast.parse(text)
    spans = [n for n in ast.walk(tree)
             if (isinstance(n, ast.Assert) or is_method_assert(n)
                 or is_pytest_raises(n) or is_pytest_fail(n)
                 or (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == "assertRaises"))
             and n.lineno <= line <= (n.end_lineno or n.lineno)]
    chain = sorted((n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.lineno <= line <= (n.end_lineno or n.lineno)),
                   key=lambda n: (n.lineno, -(n.end_lineno or n.lineno)))
    if not spans:
        return None, chain
    node = min(spans, key=lambda n: (n.end_lineno or n.lineno) - n.lineno)
    if is_pytest_fail(node):
        node = raises_of_fail(tree, node)
    return node, chain


def in_preparation(chain: list) -> bool:
    """Объемлющая функция — метод подготовки песочницы или фикстура."""
    return any(f.name in PREP_METHODS or is_fixture(f) for f in chain)


# ------------------------------------------------------------ перенос

def transferred(plan: str | None, base_keys: dict, head_tree,
                base_module_tree) -> dict[str, set[str]]:
    """{ключ теста crg: имена функций модуля, в которые он перенесён} по
    правилу докстринга модуля (одноимённая функция либо строка PLAN)."""
    funcs = module_functions(head_tree)
    old = {f.name for f in module_tests(base_module_tree)}
    new = {name for name in funcs if name.startswith("test") and name not in old}
    found = {key: set() for key in base_keys}
    for key in base_keys:
        method = key.split("::", 1)[1]
        if method in new:
            found[key].add(method)
    for line in prose_lines(plan or ""):
        keys = test_keys(line) & set(base_keys)
        if len(keys) != 1:
            continue
        key = next(iter(keys))
        found[key] |= {func for func, _v in after_refs(line) if func in new}
    return found
