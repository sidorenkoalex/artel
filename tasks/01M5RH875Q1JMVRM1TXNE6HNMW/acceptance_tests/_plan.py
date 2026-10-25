"""Общий разбор планки задачи 01M5RH875Q1JMVRM1TXNE6HNMW (волна 2а-2б
сведения тестов): 17 тестов
`tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` — функциями в
новом `tests/test_outcome_components_module.py`, песочницы гейта исходов по
компонентам — в новом `tests/components_outcome_sandbox.py`, два пути
докстринга `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`.

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
  `<номер><TAB><исход><TAB><узлы через запятую>`; при делении набора
  `--patches` таблиц в разделе несколько, у мутации берётся её последняя
  строка в порядке текста;
- ссылка на мутацию в тексте PLAN — имя патча `mutation-<nnn>` (с `.diff`
  или без) либо `мутация <n>` / `мутация №<n>` (любая форма слова);
  строка PLAN ссылается на мутации, названные в ней самой, и на мутации,
  названные в заголовке ближайшего объемлющего раздела (так описание
  мутации можно вести списком под заголовком `### mutation-003 …`);
- ссылка на исходный тест — `<Класс>::<метод>`, с префиксом
  `tests/<файл>.py::` или без него; ссылка на функцию приёмника —
  `test_outcome_components_module.py::<функция>` (с префиксом `tests/` или
  без);
- соответствие имён «до → после» — строка PLAN вне таблиц, где стоят
  ссылка на исходный тест и ссылка на функцию приёмника;
- упавшее утверждение — ссылка `tests/<файл>.py:<строка>` (как в логе
  прогона патча `mutation-run`) в строке PLAN, ссылающейся на мутацию;
  исходный файл и песочницы-предки «до» читаются из базы ветки,
  приёмник и песочницы «после» — из HEAD;
- сопоставление «тест — мутация» и перечни (удалённые дубли, находки) —
  строки PLAN вне таблиц, где стоит ссылка на тест и которые ссылаются на
  мутацию; удалённые дубли — строки раздела, в заголовке которого есть
  слово «дубл…»; находки — строки со словом «находк…» либо строки
  раздела, в заголовке которого оно есть;
- обоснование независимости исхода от случайности — строка, ссылающаяся
  на мутацию, со словом «случайн…» или «зерн…».
"""
import ast
import copy
import os
import re
import subprocess
from pathlib import Path

SOURCE = "tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py"
SOURCE_FILES = (SOURCE,)
MODULE = "tests/test_outcome_components_module.py"
SANDBOX = "tests/components_outcome_sandbox.py"
MERGE_SANDBOX = "tests/merge_outcome_sandbox.py"
OUTCOME_SANDBOX = "tests/outcome_gate_sandbox.py"
PRIOR = "tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py"
PRIOR_COUNT = 44
PRIOR_PATHS = (
    ("tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.MergeOutcomeSandbox",
     "tests.merge_outcome_sandbox.MergeOutcomeSandbox"),
    ("tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox",
     "tests.outcome_gate_sandbox.OutcomeGateSandbox"),
)
MAP_FILE = "docs/codebase-map.md"
FIXTURES_FILE = "tests/fixtures.py"
CLAIM = "Ловит мутацию"
CLAIMS = 17

# Операторы старого файла, переносимые в песочницу (AC-7): от
# `import contextlib` до `COUNTS` включительно и именованные определения.
SANDBOX_FIRST, SANDBOX_LAST = "contextlib", "COUNTS"
SANDBOX_NAMES = ("ContextRunnerProc", "ComponentsOutcomeSandbox",
                 "FAIL_TO_PASS_ACTION", "FOREIGN", "ForeignPlankSandbox")
SANDBOX_CLASSES = ("ContextRunnerProc", "ComponentsOutcomeSandbox",
                   "ForeignPlankSandbox")

# Помощники тестовых классов → функции модуля (AC-12).
HELPERS = ("mandate_answer", "review_section", "broken_consumer")
HELPER_SIGNATURES = {
    "mandate_answer": "def mandate_answer(box, t, marker: str, element: str, "
                      "matrix_element: str, covered: str) -> None:\n    pass\n",
    "review_section": "def review_section(box, t) -> str:\n    pass\n",
    "broken_consumer": "def broken_consumer(box):\n    pass\n",
}
HELPER_CLASS = {"mandate_answer": "Ac13Ac14GateMandateTest",
                "review_section": "Ac18ReviewLinesTest",
                "broken_consumer": "Ac13Ac14GateMandateTest"}
# Помощник исхода: его утверждение — доказательство (требование 4 SPEC).
OUTCOME_HELPERS = ("mandate_answer",)

# Стенды (AC-11): фикстура → класс песочницы и бывшие тестовые классы.
BOX, FOREIGN_BOX = "box", "foreign_box"
FIXTURE_CLASS = {BOX: "ComponentsOutcomeSandbox",
                 FOREIGN_BOX: "ForeignPlankSandbox"}
FOREIGN_CLASSES = ("Ac19ForeignPlankTest", "Ac25TrainingProjectTest",
                   "Ac27OutOfBoundsForeignTest")

# Методы подготовки песочниц с утверждениями: падение в них — не
# доказательство (AC-4); фикстуры — тоже подготовка.
PREP_METHODS = ("setUp", "writing_task", "component_task", "in_dev_task",
                "artel_in_dev_task", "operator_mandate", "direct_task",
                "verifying_task", "rewrite_passed", "git")
ASSERTING = PREP_METHODS[1:] + ("refusal", "no_gate_refusal")

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
UNKNOWN = "итог неизвестен"
LIMIT_OUTCOMES = ("оборвана по пределу", "не прогнана (предел)")
NOT_APPLIED = "патч не применяется"
TOUCHES = "патч трогает тесты"
# Исходы «ни убита, ни выжила» (AC-4).
VOID_OUTCOMES = (UNKNOWN, NOT_APPLIED, TOUCHES, *LIMIT_OUTCOMES)
OUTCOMES = (KILLED, SURVIVED, COLLECTION, *VOID_OUTCOMES)

MAX_PART = 15

PATCH_NAME = re.compile(r"^mutation-(\d{3,})\.diff$")
# Справочная копия таблицы `--copy-table` (`mutation_run._copy_path`).
COPY_NAME = re.compile(r"^mutation-run-(\d+)\.tsv$")

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
_AFTER_REF = re.compile(r"(test_outcome_components_module)\.py::(test\w*)")
_FILE_LINE = re.compile(r"(tests/[\w./-]+\.py):(\d+)(?!\d)")
_RANDOM_WORD = re.compile(r"случайн|зерн", re.IGNORECASE)

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


def docs_typed_entries(docs_repo, revision: str,
                       task_id: str) -> list[tuple[str, str]]:
    """[(тип git-объекта, имя)] первого уровня `tasks/<id>/` ссылки
    документов: `blob` — файл, `tree` — подкаталог."""
    rel = f"tasks/{task_id}/"
    out = git_out(docs_repo, "ls-tree", "-z", revision, "--", rel)
    found = []
    for item in out.split("\0"):
        if not item:
            continue
        meta, _tab, path = item.partition("\t")
        if path.startswith(rel):
            found.append((meta.split()[1], path[len(rel):]))
    return found


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


def _is_table_any(line: str) -> bool:
    return _is_table_line(line) or line == _COLUMNS or bool(_ROW.match(line))


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
    return [line for line in text.split("\n") if not _is_table_any(line)]


def refs(line: str) -> set[int]:
    """Номера мутаций, на которые ссылается сама строка."""
    found = set()
    for pattern in _REF:
        found.update(int(m) for m in pattern.findall(line))
    return found


def ref_lines(text: str) -> list[tuple[str, set[int]]]:
    """[(строка, номера мутаций)] строк текста вне таблиц `mutation-run`:
    номера — из самой строки и из заголовка ближайшего объемлющего раздела."""
    lines = text.split("\n")
    heads = {i: (level, title) for i, level, title in _headings(lines)}
    stack: list[tuple[int, set]] = []
    found = []
    for i, line in enumerate(lines):
        if i in heads:
            level, title = heads[i]
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, refs(title)))
            found.append((line, refs(line)))
            continue
        if _is_table_any(line):
            continue
        context = stack[-1][1] if stack else set()
        found.append((line, refs(line) | context))
    return found


def test_keys(line: str) -> set[str]:
    """Ссылки строки на тесты исходного файла в виде `<Класс>::<метод>`."""
    return {f"{c}::{m}" for c, m in _TEST_KEY.findall(line)}


def after_refs(line: str) -> set[tuple[str, str]]:
    """Ссылки строки на функции приёмника: {(файл, функция)}."""
    return {(f"tests/{stem}.py", func) for stem, func in _AFTER_REF.findall(line)}


def transfer_map(plan: str) -> dict[str, set[tuple[str, str]]]:
    """{`<Класс>::<метод>` исходного теста: {(приёмник, функция)}} по
    строкам PLAN вне таблиц, где стоят обе ссылки."""
    mapped: dict[str, set] = {}
    for line in prose_lines(plan):
        funcs = after_refs(line)
        if not funcs:
            continue
        for key in test_keys(line):
            mapped.setdefault(key, set()).update(funcs)
    return mapped


def file_lines(line: str) -> list[tuple[str, int]]:
    """Ссылки строки вида `tests/<файл>.py:<строка>`."""
    return [(path, int(n)) for path, n in _FILE_LINE.findall(line)]


def random_justified(line: str) -> bool:
    return bool(_RANDOM_WORD.search(line))


def node_key(node: str) -> str:
    """`tests/<файл>.py::<Класс>::<метод>` → `<Класс>::<метод>`."""
    keys = test_keys(node)
    return next(iter(keys)) if len(keys) == 1 else node


def after_node_parts(node: str) -> tuple[str, str]:
    """`tests/<приёмник>.py::<функция>[<вариант>]` → (приёмник, функция)."""
    path, _sep, tail = node.partition("::")
    func = tail.rsplit("::", 1)[-1].partition("[")[0]
    return path, func


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
        # Строки таблицы как в тексте: от `# mutation-run №…` до последней
        # строки мутации; `start` — индекс первой строки в тексте.
        self.lines: list[str] = []
        self.start = 0


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
        table.start = i
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
        workers = _WORKERS.match(lines[i]) if i < len(lines) else None
        if workers:
            table.workers = workers.group(1)
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
        table.lines = lines[table.start:i]
        found.append(table)
    return found, errors


def contains_block(text: str, block: list[str]) -> bool:
    """Строки `block` стоят в `text` подряд и дословно."""
    lines = text.split("\n")
    width = len(block)
    return width > 0 and any(lines[k:k + width] == block
                             for k in range(len(lines) - width + 1))


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


def all_outcomes(found: list[Table]) -> list[tuple[int, str, str]]:
    """[(номер, sha256 патча из шапки, исход)] всех строк всех таблиц."""
    result = []
    for table in found:
        for number, outcome, _nodes in table.rows:
            sha = table.patches.get(number, ("", ""))[1]
            result.append((number, sha, outcome))
    return result


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


def message_arg(call: ast.Call):
    """Аргумент сообщения `self.assert*` (позиционный после смысловых или
    `msg=`); нет — None."""
    count = 1 if call.func.attr in _ONE_ARG else 2
    if len(call.args) > count:
        return call.args[count]
    return next((kw.value for kw in call.keywords if kw.arg == "msg"), None)


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
    """(литералы аргументов `assertEqual`, литералы аргументов
    `assertIn`/`assertNotIn`)."""
    equal, member = set(), set()
    for call in assert_calls(tree):
        name = call.func.attr
        lits = set()
        for arg in semantic_args(call):
            lits |= constants(arg)
        if name == "assertEqual":
            equal |= lits
        elif name in ("assertIn", "assertNotIn"):
            member |= lits
    return equal, member


def class_node(tree, cls: str):
    return next((n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == cls), None)


def class_method(tree, cls: str, method: str):
    node = class_node(tree, cls)
    if node is None:
        return None
    return next((item for item in node.body
                 if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and item.name == method), None)


def class_method_names(tree, cls: str) -> set[str]:
    node = class_node(tree, cls)
    if node is None:
        return set()
    return {item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}


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


def sandbox_statements(tree) -> list:
    """Операторы верхнего уровня старого файла, переносимые в песочницу
    (AC-7), в порядке файла: от `import contextlib` до связывания `COUNTS`
    включительно и определения `SANDBOX_NAMES`."""
    body = tree.body
    first = next((i for i, n in enumerate(body) if isinstance(n, ast.Import)
                  and [a.name for a in n.names] == [SANDBOX_FIRST]), None)
    last = next((i for i, n in enumerate(body)
                 if SANDBOX_LAST in bound_names(n)), None)
    if first is None or last is None:
        return []
    picked = list(range(first, last + 1))
    picked += [i for i, n in enumerate(body) if i > last
               and set(bound_names(n)) & set(SANDBOX_NAMES)]
    return [body[i] for i in sorted(set(picked))]


# ------------------------------------------------------ преобразования (ast)

def strip_docstring(body: list) -> list:
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        return body[1:]
    return body


class SelfToParam(ast.NodeTransformer):
    """`self.<помощник>(…)` → `<функция>(<стенд>, …)`; прочие `self` →
    имя стенда."""

    def __init__(self, param: str, calls=()):
        self.param, self.calls = param, set(calls)

    def visit_Call(self, node):
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == self.param and func.attr in self.calls:
            node.func = ast.Name(id=func.attr, ctx=ast.Load())
            node.args = [ast.Name(id=self.param, ctx=ast.Load()), *node.args]
        return node

    def visit_Name(self, node):
        if node.id == "self":
            node.id = self.param
        return node


_COMPARE = {"assertEqual": ast.Eq, "assertIn": ast.In, "assertNotIn": ast.NotIn}


class AssertToStatement(ast.NodeTransformer):
    """Оператор `<стенд>.assertX(…)` → `assert …` по соответствию
    требования 17 SPEC: `assertEqual(a, b)` ↔ `a == b`, `assertTrue(x)` ↔
    `x`, `assertIn(a, b)` ↔ `a in b`, `assertNotIn(a, b)` ↔ `a not in b`;
    сообщение — вторым операндом."""

    def __init__(self, param: str):
        self.param = param

    def visit_Expr(self, node):
        call = node.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == self.param):
            return node
        attr = call.func.attr
        msg = message_arg(call) if attr in (*_COMPARE, "assertTrue") else None
        if attr == "assertTrue":
            test = call.args[0]
        elif attr in _COMPARE:
            test = ast.Compare(left=call.args[0], ops=[_COMPARE[attr]()],
                               comparators=[call.args[1]])
        else:
            return node
        return ast.Assert(test=test, msg=msg)


class _FlattenAdd(ast.NodeTransformer):
    """Цепочка `a + b + c` при любой расстановке скобок → один вызов
    `__add__(a, b, c)`."""

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if not isinstance(node.op, ast.Add):
            return node
        parts = []
        for side in (node.left, node.right):
            if isinstance(side, ast.Call) and isinstance(side.func, ast.Name) \
                    and side.func.id == "__add__":
                parts += side.args
            else:
                parts.append(side)
        return ast.Call(func=ast.Name(id="__add__", ctx=ast.Load()),
                        args=parts, keywords=[])


def _rename_locals(module: ast.Module) -> ast.Module:
    """Локальные имена (цели присваиваний, `for`, `with`, `except`) по
    порядку первого появления → `_v0`, `_v1`, …: переименование локальной
    переменной (требование 17) не меняет каноничного дампа."""
    stored = sorted((n for n in ast.walk(module)
                     if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)),
                    key=lambda n: (n.lineno, n.col_offset))
    stored += sorted((n for n in ast.walk(module)
                      if isinstance(n, ast.ExceptHandler) and n.name),
                     key=lambda n: (n.lineno, n.col_offset))
    order = {}
    for node in stored:
        name = node.id if isinstance(node, ast.Name) else node.name
        order.setdefault(name, f"_v{len(order)}")
    for node in ast.walk(module):
        if isinstance(node, ast.Name) and node.id in order:
            node.id = order[node.id]
        elif isinstance(node, ast.ExceptHandler) and node.name in order:
            node.name = order[node.name]
    return module


def canonical(body: list, rename: bool = False) -> str:
    module = ast.Module(body=copy.deepcopy(body), type_ignores=[])
    if rename:
        module = _rename_locals(module)
    return ast.dump(_FlattenAdd().visit(module))


def expected_test_body(method, param: str) -> str:
    """Каноничный дамп тела тестового метода, переведённого в функцию:
    `self.<помощник>(…)` → `<помощник>(<стенд>, …)`, `self` → стенд,
    `assertX` → `assert` с сообщением вторым операндом; локальные имена
    обезличены."""
    node = SelfToParam(param, HELPERS).visit(copy.deepcopy(method))
    node = AssertToStatement(param).visit(node)
    ast.fix_missing_locations(node)
    return canonical(strip_docstring(node.body), rename=True)


def actual_test_body(func) -> str:
    return canonical(strip_docstring(copy.deepcopy(func).body), rename=True)


def expected_helper_body(method, param: str) -> str:
    node = SelfToParam(param).visit(copy.deepcopy(method))
    return canonical(strip_docstring(node.body))


def actual_helper_body(func) -> str:
    return canonical(strip_docstring(copy.deepcopy(func).body))


def signature_dump(func) -> str:
    return ast.dump(func.args) + "|" + (ast.dump(func.returns) if func.returns else "")


def reference_signature(name: str) -> str:
    return signature_dump(ast.parse(HELPER_SIGNATURES[name]).body[0])


def attribute_assignments(func, param: str) -> list[str]:
    """Цели присваиваний атрибутам стенда (`<стенд>.x = …`,
    `<стенд>.x[…] = …`) в порядке текста — `ast.unparse` цели."""
    found = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                root = target
                while isinstance(root, (ast.Attribute, ast.Subscript)):
                    root = root.value
                if isinstance(root, ast.Name) and root.id == param \
                        and target is not root:
                    found.append((node.lineno, node.col_offset, ast.unparse(target)))
    return [t for _l, _c, t in sorted(found)]


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


def non_docstring_constants(tree) -> set:
    """Литералы без докстрингов модуля, классов и функций."""
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
    """[(вид сравнения, литералы операндов)] каждого `ast.Compare`: вид —
    `eq` (==, !=, is), `in` (in, not in), `order` (<, <=, >, >=)."""
    found = []
    for node in ast.walk(tree):
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


# ------------------------------------------- место упавшего утверждения

def is_assertion_node(node) -> bool:
    if isinstance(node, ast.Assert):
        return True
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr.startswith("assert") or func.attr in ("fail", "raises")
    return isinstance(func, ast.Name) and func.id == "fail"


def assertion_site(text: str, line: int) -> tuple[bool, list]:
    """(строка `line` лежит в утверждении, объемлющие функции — от внешней
    к внутренней)."""
    tree = ast.parse(text)
    inside = any(is_assertion_node(n) and n.lineno <= line <= (n.end_lineno or n.lineno)
                 for n in ast.walk(tree))
    chain = sorted((n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.lineno <= line <= (n.end_lineno or n.lineno)),
                   key=lambda n: (n.lineno, -(n.end_lineno or n.lineno)))
    return inside, chain


def in_preparation(chain: list) -> bool:
    """Объемлющая функция — метод подготовки песочницы или фикстура."""
    return any(f.name in PREP_METHODS or is_fixture(f) for f in chain)
