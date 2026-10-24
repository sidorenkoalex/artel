"""Общий разбор планки волны 2б-3 сведения тестов: песочница отчётов исходов
в `tests/report_outcome_sandbox.py`, тесты в `tests/test_report_outcome_module.py`.

Только чистые функции и вызовы git по переданному репозиторию: модуль не
импортирует `_pult` — значения выкладки (корень рабочей копии, база диффа,
репозиторий и ревизия ссылки документов) передают сами тесты.

Соглашения разбора PLAN.md, которых держится вся планка:

- раздел — заголовок markdown (`#`…`######`) вне ограждения кода; строки
  шапки таблицы `mutation-run` (`# mutation-run №…`, `# источник патчей:`,
  `# ревизия прогона:`, `# тесты:`, `# патч …`) заголовками не считаются;
  раздел длится до следующего заголовка того же или более высокого уровня;
- таблица `mutation-run` — текст, напечатанный командой
  (`orchestrator/mutation_run.py::_header`, `_Run.row`): шапка из строк
  `# …`, строка колонок `номер<TAB>исход<TAB>узлы` и строки
  `<номер><TAB><исход><TAB><узлы через запятую>`; при делении набора
  `--patches` таблиц в разделе несколько, у мутации берётся её последняя
  строка в порядке текста;
- ссылка на мутацию в тексте PLAN — имя патча `mutation-<nnn>` (с `.diff`
  или без) либо `мутация <n>` / `мутация №<n>` (любая форма слова);
- ссылка на тест исходных файлов — `<Класс>::<метод>`, с префиксом
  `tests/<файл>.py::` или без него; ссылка на узел нового файла —
  `test_report_outcome_module.py::<функция>` (с префиксом `tests/` или без,
  с вариантом `[<вариант>]` или без — без варианта она покрывает все
  варианты функции);
- упавшее утверждение — ссылка `tests/<файл>.py:<строка>` (как в логе
  прогона патча `mutation-run`) в той же строке PLAN, что ссылка на
  мутацию и на убивший узел;
- сопоставление «тест — мутация» и перечни (удалённые дубли, узлы,
  убитые падением подготовки, находки) — строки PLAN вне таблиц, где
  ссылка на тест (узел) и ссылка на мутацию стоят в ОДНОЙ строке;
  удалённые дубли — строки раздела, в заголовке которого есть слово
  «дубл…»; находки — строки со словом «находк…» либо строки раздела, в
  заголовке которого оно есть; узлы, убитые падением подготовки, — строки
  со словом `setUp` или «подготовк…».
"""
import ast
import copy
import os
import re
import subprocess
from pathlib import Path

SOURCE_FILE = "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py"
SOURCE_FILES = (SOURCE_FILE,)
NEW_FILE = "tests/test_report_outcome_module.py"
SANDBOX_FILE = "tests/report_outcome_sandbox.py"
AFTER_FILES = (NEW_FILE, SANDBOX_FILE)
IMPORTER = "tests/test_component_report_gates.py"
INVARIANTS_TEST = "tests/test_invariants.py"
INVARIANTS_DOC = "docs/invariants.md"
INVARIANT_CLASS = "ReportedOutcomeNotGreenInvariantTest"
OLD_MODULE = "tests.test_01m590gjaf0edv4nbc4c99mfvh_report_outcome"
NEW_MODULE = "tests.report_outcome_sandbox"
# Имена переходного модуля — строка импорта требования 7 SPEC, по порядку.
TRANSITION_NAMES = ("ReportSandbox", "junit", "vitest_report", "vitest_test")
CLAIM = "Ловит мутацию"
CLAIM_COUNT = 26

# Строки исходного файла, переносимые дословно (требование 6 SPEC).
SANDBOX_LINES = (54, 606)
SANDBOX_STATEMENTS = 50

# Методы подготовки песочницы и `key_case`: падение в них — не
# доказательство (AC-3); `setUp` — ошибка setup.
PREP_METHODS = ("setUp", "profile", "records_of", "by_id", "table",
                "accepted_major", "cache_flag", "key_case")

# Помощники AC-11, имя которых в новом файле обязано остаться прежним:
# имя функции модуля → (класс, метод) источника.
HELPERS = {
    "assert_unknown": ("ReportSandbox", "assert_unknown"),
    "key_case": ("ResultKeyTest", "key_case"),
    "main_head": ("ArtelUnchangedTest", "main_head"),
}
# Помощники AC-11 с префиксом бывшего класса (совпадение имени с другой
# функцией модуля или с локальной переменной вызывающего теста):
# (класс, метод) источника; имя функции — `<префикс класса><метод>`.
PREFIXED = (("VitestReporterTest", "full_vitest"),
            ("InstallAndDepsTest", "full_vitest"),
            ("ArtelUnchangedTest", "channels"))
HELPER_METHODS = ("assert_unknown", "key_case", "main_head", "full_vitest",
                  "channels")
# Методы с утверждениями: фикстура их не зовёт (AC-10).
ASSERTING = ("profile", "records_of", "by_id", "table", "accepted_major",
             "cache_flag", "assert_unknown", "key_case")

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
LIMIT_OUTCOMES = ("оборвана по пределу", "не прогнана (предел)")
OUTCOMES = (KILLED, SURVIVED, COLLECTION, "итог неизвестен",
            *LIMIT_OUTCOMES, "патч не применяется", "патч трогает тесты")
MAX_PART = 15

PATCH_NAME = re.compile(r"^mutation-(\d{3,})\.diff$")

_HEAD = re.compile(r"^# mutation-run №(\d+) задачи (\S+)$")
_SOURCE = re.compile(r"^# источник патчей: (\S.*)$")
_REVISION = re.compile(r"^# ревизия прогона: (base|head|worktree) ([0-9a-f]{7,64})$")
_TESTS = re.compile(r"^# тесты: (\S.*)$")
_PATCH = re.compile(r"^# патч (\d+) (\S+) sha256 ([0-9a-f]{64})$")
_WORKERS = re.compile(r"^# рабочих процессов: (\d+)$")
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


def docs_entries(docs_repo, revision: str, task_id: str) -> list[str]:
    """Имена первого уровня `tasks/<id>/` ссылки документов (файлы и каталоги)."""
    rel = f"tasks/{task_id}/"
    out = git_out(docs_repo, "ls-tree", "-z", "--name-only", revision, "--", rel)
    return [p[len(rel):] for p in out.split("\0") if p.startswith(rel)]


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


def class_prefixed(name: str, method: str, cls: str) -> bool:
    """`name` — имя `method` с непустым префиксом бывшего класса `cls`:
    `name` кончается на `method`, перед ним непустой префикс, который без
    подчёркиваний и регистра входит в имя класса без регистра
    (`vitest_reporter_full_vitest`, `VitestReporterTest_full_vitest`)."""
    if not name.endswith(method) or name == method:
        return False
    prefix = name[:-len(method)].replace("_", "").casefold()
    return bool(prefix) and prefix in cls.casefold()


def patch_names(entries: list[str]) -> dict[int, str]:
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
    """Ссылки строки на тесты исходных файлов в виде `<Класс>::<метод>`."""
    return {f"{c}::{m}" for c, m in _TEST_KEY.findall(line)}


def after_refs(line: str) -> set[tuple[str, str]]:
    """Ссылки строки на узлы нового файла: {(функция, вариант или "")}."""
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
    """Узел нового файла попадает под отметку: та же функция и тот же
    вариант, либо отметка без варианта."""
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
                    (_TESTS, "тесты"))
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
            else:
                table.tests = [t.strip() for t in match.group(1).split(",")]
            i += 1
        if broken:
            continue
        # Строка числа рабочих процессов шапки (`mutation-run --workers`,
        # 01M5PWFGJQNV8YSAN5MF0CKHVW) стоит между `# тесты:` и `# патч …`.
        if i < len(lines) and _WORKERS.match(lines[i]):
            i += 1
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


# --------------------------------------------------- исходные тесты (ast)

class BaseTest:
    def __init__(self, path: str, cls: str, func: ast.FunctionDef):
        self.path, self.cls, self.func = path, cls, func
        self.key = f"{cls}::{func.name}"
        self.claim = CLAIM in (ast.get_docstring(func) or "")


def base_tests(path: str, text: str) -> list[BaseTest]:
    tree = ast.parse(text)
    found = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name.startswith("test"):
                    found.append(BaseTest(path, node.name, item))
    return found


# Число смысловых позиционных аргументов `self.assert*`: дальше — msg.
_ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


def _is_self_assert(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and not node.func.attr.startswith("assertRaises"))


def is_method_assert(node) -> bool:
    """Вызов `<что угодно>.assert*(...)` (кроме `assertRaises*`)."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and not node.func.attr.startswith("assertRaises"))


def constants(node) -> set:
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and not isinstance(sub.value, bool) \
                and isinstance(sub.value, (str, int, float)):
            found.add(sub.value)
    return found


def assert_calls(tree) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if _is_self_assert(n)]


def semantic_args(call: ast.Call) -> list:
    count = 1 if call.func.attr in _ONE_ARG else 2
    return list(call.args[:count])


def assertion_literals(tree) -> set:
    """Литералы (строки и числа) смысловых аргументов `self.assert*`."""
    found = set()
    for call in assert_calls(tree):
        for arg in semantic_args(call):
            found |= constants(arg)
    return found


def assertion_constant_names(tree) -> set:
    """Имена констант модуля (`ВЕРХНИЙ_РЕГИСТР`) в смысловых аргументах
    `self.assert*`."""
    found = set()
    for call in assert_calls(tree):
        for arg in semantic_args(call):
            found |= {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)
                      and re.fullmatch(r"[A-Z][A-Z0-9_]*", n.id)}
    return found


def assertion_kinds(tree) -> set[str]:
    return {call.func.attr for call in assert_calls(tree)}


def equality_literals(tree) -> tuple[set, set]:
    """(литералы аргументов равенства `assertEqual`/`assert*Equal` кроме
    `assertCountEqual`/`assertNotEqual`, литералы аргументов `assertIn`/
    `assertNotIn`)."""
    equal, member = set(), set()
    for call in assert_calls(tree):
        name = call.func.attr
        lits = set()
        for arg in semantic_args(call):
            lits |= constants(arg)
        if name.endswith("Equal") and name not in ("assertCountEqual",
                                                   "assertNotEqual",
                                                   "assertAlmostEqual",
                                                   "assertNotAlmostEqual"):
            equal |= lits
        elif name in ("assertIn", "assertNotIn"):
            member |= lits
    return equal, member


def text_raises_sites(tree) -> int:
    """Места исходного файла, где проверялся текст исключения:
    `with self.assertRaises(E) as x` с чтением `x.exception` в той же
    функции и вызовы `assertRaisesRegex`/`assertRaisesRegexp`."""
    count = 0
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        read = {n.value.id for n in ast.walk(func)
                if isinstance(n, ast.Attribute) and n.attr == "exception"
                and isinstance(n.value, ast.Name)}
        for node in ast.walk(func):
            if isinstance(node, ast.With):
                for item in node.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and \
                            isinstance(call.func, ast.Attribute) and \
                            call.func.attr == "assertRaises" and \
                            isinstance(item.optional_vars, ast.Name) and \
                            item.optional_vars.id in read:
                        count += 1
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("assertRaisesRegex",
                                           "assertRaisesRegexp"):
                count += 1
    return count


def class_method(tree, cls: str, method: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == method:
                    return item
    return None


def top_level(tree, lines: tuple[int, int]) -> list:
    """Утверждения верхнего уровня модуля, начинающиеся в строках `lines`."""
    first, last = lines
    return [n for n in tree.body if first <= n.lineno <= last]


def bound_names(node) -> list[str]:
    """Имена, которые связывает утверждение верхнего уровня модуля."""
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


def expected_helper_body(method, param: str, calls: dict | None = None) -> str:
    """`ast.dump` тела метода-источника, переведённого в функцию модуля:
    `self.` → стенд, вызовы помощников перечня — голым именем."""
    node = copy.deepcopy(method)
    node = _SelfToParam(param, calls or {}).visit(node)
    return ast.dump(ast.Module(body=strip_docstring(node.body), type_ignores=[]))


def body_dump(func) -> str:
    return ast.dump(ast.Module(body=strip_docstring(copy.deepcopy(func).body),
                               type_ignores=[]))


def rest_args_dump(args: ast.arguments, drop_first: bool) -> str:
    """`ast.dump` параметров без первого (стенда или `self`)."""
    node = copy.deepcopy(args)
    if drop_first:
        node.args = node.args[1:]
    return ast.dump(node)


# ------------------------------------------------------- новый файл (ast)

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


def is_pytest_raises(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "raises"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest")


def non_docstring_constants(tree) -> set:
    """Литералы файла без докстрингов модуля, классов и функций."""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    found = set()
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Constant) and id(sub) not in docstrings \
                and not isinstance(sub.value, bool) \
                and isinstance(sub.value, (str, int, float)):
            found.add(sub.value)
    return found


def compare_operands(tree) -> list[tuple[str, set]]:
    """[(вид сравнения, литералы операндов)] каждого `ast.Compare` и
    каждого вызова `<стенд>.assert*Equal`: вид — `eq` (==, !=, is,
    `assertEqual`), `in` (in, not in), `order` (<, <=, >, >=)."""
    found = []
    for node in ast.walk(tree):
        if is_method_assert(node) and node.func.attr in ("assertEqual",
                                                         "assertNotEqual"):
            lits = set()
            for arg in node.args[:2]:
                lits |= constants(arg)
            found.append(("eq", lits))
            continue
        if not isinstance(node, ast.Compare):
            continue
        kinds = set()
        for op in node.ops:
            if isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
                kinds.add("eq")
            elif isinstance(op, (ast.In, ast.NotIn)):
                kinds.add("in")
            else:
                kinds.add("order")
        lits = set()
        for operand in [node.left, *node.comparators]:
            lits |= constants(operand)
        for kind in kinds:
            found.append((kind, lits))
    return found


def parametrize_columns(tree) -> list[list]:
    """Столбцы литеральных значений `@pytest.mark.parametrize`: для каждого
    декоратора со списком/кортежем литералов — список значений каждого
    имени параметра."""
    columns = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in parametrize_decorators(node):
            if len(deco.args) < 2:
                continue
            values = deco.args[1]
            if not isinstance(values, (ast.List, ast.Tuple)):
                continue
            try:
                literal = ast.literal_eval(values)
            except (ValueError, TypeError, SyntaxError):
                continue
            names = deco.args[0]
            width = 1
            if isinstance(names, ast.Constant) and isinstance(names.value, str):
                width = len([n for n in names.value.split(",") if n.strip()])
            elif isinstance(names, (ast.List, ast.Tuple)):
                width = len(names.elts)
            if width == 1:
                columns.append(list(literal))
            else:
                for k in range(width):
                    columns.append([row[k] for row in literal
                                    if isinstance(row, (list, tuple))
                                    and len(row) > k])
    return columns


# ------------------------------------------- место упавшего утверждения

def _is_assertion_node(node) -> bool:
    if isinstance(node, ast.Assert):
        return True
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr.startswith("assert") or func.attr in ("fail", "raises")
    return isinstance(func, ast.Name) and func.id == "fail"


def assertion_site(text: str, line: int) -> tuple[bool, list[str]]:
    """(строка `line` лежит в утверждении, имена объемлющих функций —
    от внешней к внутренней)."""
    tree = ast.parse(text)
    inside = any(_is_assertion_node(n) and n.lineno <= line <= (n.end_lineno or n.lineno)
                 for n in ast.walk(tree))
    chain = sorted((n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.lineno <= line <= (n.end_lineno or n.lineno)),
                   key=lambda n: (n.lineno, -(n.end_lineno or n.lineno)))
    return inside, chain


def in_preparation(chain: list) -> bool:
    """Объемлющая функция — метод подготовки песочницы или фикстура."""
    return any(f.name in PREP_METHODS or is_fixture(f) for f in chain)
