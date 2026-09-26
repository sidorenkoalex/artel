"""Общие помощники планки 01M3F7BYE82S9AQCBSP1RTQQTR (паритет
безопасности роли на Codex).

Три предмета, нужные больше чем одному файлу планки:

1. **Таблица паритета в `docs/stack.md`** — разбор markdown-таблиц
   документа и перечень восьми запретов требования 1 (их читают тесты
   AC-1..AC-3 и мутации AC-4).
2. **Тесты в `tests/`** — отбор тестовых методов по СЦЕНАРИЮ (метод,
   его `setUp` и исходники помощников, на которые он ссылается) и их
   прогон поодиночке (AC-4, AC-8, AC-12, AC-13 проверяют критерии вида
   «тест в tests/ показывает …»: критерий требует не только, чтобы такой
   тест существовал и проходил, но и чтобы он РАЗЛИЧАЛ — падал на
   подменённой реализации).
3. **Артефакты и main** — текст PLAN.md читается ТОЛЬКО из артефактной
   ветки (`gitcmd.show`), исходник провайдера `claude` — из коммита
   `f89bab7c`, названного AC-10.

Имя файла с ведущим подчёркиванием — единственная форма общего кода
планки, которую checkpoint не отбрасывает (skills/test-authoring.md).
Лёгкую песочницу переходов FSM этот файл не переопределяет и не копирует:
планке нужны песочницы `tests/sandbox.py`/`tests/test_doctor.py`, они
импортируются тестами напрямую.
"""
import ast
import importlib
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, config, gitcmd  # noqa: E402

TASK_ID = "01M3F7BYE82S9AQCBSP1RTQQTR"

#: Коммит main, с которым AC-10 сверяет argv команды шага роли на Claude.
MAIN_SHA = "f89bab7c"

#: Пути читаются от `config.ROOT` — того же корня, которым пульт адресует
#: свои файлы; на диске планки это рабочая копия задачи.
STACK_MD = config.ROOT / "docs" / "stack.md"
TESTS_DIR = config.ROOT / "tests"
DOCTOR_DIR = config.ROOT / "orchestrator" / "doctor"

# --- таблица паритета docs/stack.md ------------------------------------

#: Восемь запретов перечня требования 1, перечисленные AC-1 дословно.
#: Значение — альтернативы опознания строки таблицы: альтернатива
#: срабатывает, когда в строке есть ВСЕ её подстроки (строка таблицы
#: приводится к нижнему регистру). Набор альтернатив держится широким
#: намеренно: критерий называет предмет запрета, а не формулировку
#: ячейки, и планка не вправе диктовать разработчику слова.
PROHIBITIONS = (
    ("файлы вне рабочего каталога",
     (("вне рабочего каталога",), ("файлы вне",), ("вне рабочей копии",))),
    ("сеть", (("сеть",), ("сети",), ("сетев",), ("network",))),
    ("Связка ключей и секреты",
     (("связка ключей",), ("связки ключей",), ("связке ключей",),
      ("keychain",), ("секрет",))),
    ("инструменты и MCP", (("mcp",),)),
    ("хуки", (("хук",),)),
    ("чтение user-слоя Оператора",
     (("user", "сло"), ("пользовательск", "сло"), ("user-layer",))),
    ("пул канарейки", (("пул",),)),
    ("посторонние файлы и защищённые пути",
     (("посторонние файлы",), ("посторонних файл",), ("защищённ",),
      ("защищен",))),
)

#: Чем запрет закрыт у роли на Codex — четвёрка средств, названная AC-2
#: (песочница, конфигурация дома роли, флаги команды шага, гейт пульта),
#: каждое несколькими написаниями.
CLOSURE_MEANS = ("песочниц", "sandbox", "дом", "config.toml", "конфиг",
                 "agents.md", "команд", "флаг", "argv", "гейт", "пульт")

#: Пометка «не закрыт» (AC-2/AC-3) — тремя родами: «запрет не закрыт»,
#: «не закрыто песочницей», «изоляция не закрыта».
NOT_CLOSED = ("не закрыт", "не закрыто", "не закрыта")

#: Компенсация строки «не закрыт» (AC-3): гейт пульта после шага либо
#: явная пометка принятого риска.
COMPENSATION = ("гейт", "риск")


def stack_md_text() -> str:
    """Текст `docs/stack.md` рабочей копии."""
    return STACK_MD.read_text(encoding="utf-8")


def markdown_tables(text: str) -> list:
    """Таблицы markdown документа: список блоков, каждый — список строк
    (сами строки, как в тексте, вместе с заголовком и разделителем).

    Блок — подряд идущие строки, начинающиеся с `|`: единственная форма
    таблицы в `docs/*.md` этого репозитория.
    """
    tables, current = [], []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


_SEPARATOR_ROW = re.compile(r"^\|[\s:|-]+\|?\s*$")


def data_rows(table: list) -> list:
    """Строки-данные таблицы: без строки заголовка и без разделителя
    `|---|---|`."""
    rows = [line for line in table if not _SEPARATOR_ROW.match(line.strip())]
    return rows[1:] if len(rows) > 1 else []


def row_matches(row: str, alternatives) -> bool:
    """Строка таблицы опознаётся одной из альтернатив (все подстроки
    альтернативы присутствуют, регистр не важен)."""
    lowered = row.lower()
    return any(all(part in lowered for part in alt) for alt in alternatives)


def coverage(rows: list) -> dict:
    """{название запрета: [строки таблицы, опознавшие его]} по всем
    восьми запретам требования 1."""
    return {name: [row for row in rows if row_matches(row, alternatives)]
            for name, alternatives in PROHIBITIONS}


def parity_table(text: str) -> list:
    """Строки-данные таблицы паритета: та таблица документа, которая
    покрывает БОЛЬШЕ всего запретов перечня (пустой список — таблиц в
    документе нет вовсе).

    Таблица ищется покрытием, а не заголовком раздела: AC-1 говорит про
    строку на каждый запрет, а не про имя раздела, и привязка к
    заголовку сделала бы планку заложницей формулировки заголовка.
    """
    best, best_score = [], -1
    for table in markdown_tables(text):
        rows = data_rows(table)
        score = sum(1 for hits in coverage(rows).values() if hits)
        if score > best_score:
            best, best_score = rows, score
    return best


def missing_prohibitions(rows: list) -> list:
    """Названия запретов перечня требования 1, которые не опознала ни
    одна из строк `rows`."""
    return [name for name, hits in coverage(rows).items() if not hits]


def row_is_open(row: str) -> bool:
    """Строка несёт пометку «не закрыт»."""
    lowered = row.lower()
    return any(mark in lowered for mark in NOT_CLOSED)


def _string_constants(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node


_CHECK_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
#: Строковые литералы `orchestrator/doctor/`, похожие на имя проверки по
#: форме, но именами проверок не являющиеся.
_NOT_A_CHECK = frozenset({"utf-8", "ls-remote", "rev-parse", "merge-base",
                          "pre-commit", "pre-push"})


def doctor_sources() -> list:
    """Исходники `orchestrator/doctor/*.py` рабочей копии."""
    return [path.read_text(encoding="utf-8")
            for path in sorted(DOCTOR_DIR.glob("*.py"))]


def main_doctor_sources() -> list:
    """Те же исходники из коммита `MAIN_SHA`."""
    paths = gitcmd.ls_tree_files(MAIN_SHA, "orchestrator/doctor")
    if paths is None:
        raise AssertionError(f"дерево {MAIN_SHA} не прочитано")
    return [main_source(rel) for rel in sorted(paths) if rel.endswith(".py")]


def doctor_check_names(sources=None) -> set:
    """Имена строк `doctor`, какими их знает сам код
    `orchestrator/doctor/`: первый аргумент вызовов `Check(...)` (включая
    имена, вынесенные в константу модуля) плюс строковые литералы формы
    `имя-через-дефис` — часть проверок собирает имя параметром
    (`check_role_home_reference`, `check_map_growth`), и по вызову их
    имени не видно.

    Набор собирается из кода, а не перечисляется здесь литералами: строка
    таблицы паритета обязана называть ЖИВУЮ проверку, а не ту, что была
    на момент написания планки. `sources` — тексты модулей (по умолчанию
    рабочая копия): тем же разбором читается и дерево main.
    """
    names, constants, trees = set(), {}, {}
    for index, source in enumerate(doctor_sources() if sources is None
                                   else sources):
        tree = ast.parse(source)
        trees[index] = tree
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) \
                    else getattr(func, "id", "")
                if name == "Check" and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        names.add(first.value)
                    elif isinstance(first, ast.Name) and first.id in constants:
                        names.add(constants[first.id])
        for node in _string_constants(tree):
            if _CHECK_NAME.match(node.value):
                names.add(node.value)
    return names - _NOT_A_CHECK


def doctor_check_functions(sources=None) -> set:
    """Имена функций-проверок `def check_*` пакета `orchestrator/doctor/`
    (по умолчанию — рабочей копии): по ним сверяется, что ни одна
    проверка не УДАЛЕНА."""
    found = set()
    for source in (doctor_sources() if sources is None else sources):
        for node in ast.parse(source).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith("check_"):
                found.add(node.name)
    return found


def function_source(source: str, name: str) -> str:
    """Исходный текст функции `name` модуля; пустая строка — такой
    функции в модуле нет."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(source, node) or ""
    return ""


def test_method_names(source: str) -> set:
    """Имена тестовых методов модуля (`класс.метод`)."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and item.name.startswith("test"):
                names.add(f"{node.name}.{item.name}")
    return names


def checks_named_in(row: str, known: set) -> list:
    """Имена проверок `doctor` из `known`, названные строкой таблицы
    (сравнение по границам слова: `cli-version` не считается названным
    внутри `codex-cli-version`)."""
    lowered = row.lower()
    return sorted(name for name in known
                  if re.search(rf"(?<![a-z0-9-]){re.escape(name)}(?![a-z0-9-])",
                               lowered))


# --- тесты в tests/ -----------------------------------------------------

_NAME_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SETUP_METHODS = ("setUp", "setUpClass")


def _definitions(tree: ast.AST, source: str) -> dict:
    """{имя уровня модуля: его исходный текст} — функции, классы и
    присваивания."""
    defs = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            defs[node.name] = ast.get_source_segment(source, node) or ""
        elif isinstance(node, ast.Assign):
            segment = ast.get_source_segment(source, node) or ""
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = segment
    return defs


def _scenario_text(source: str, tree: ast.AST, class_node: ast.ClassDef,
                   method: ast.AST) -> str:
    """Текст СЦЕНАРИЯ тестового метода: сам метод, `setUp` его класса и —
    по замыканию — исходники всех имён, на которые сценарий ссылается
    (помощники класса `self.<имя>`, функции и константы уровня модуля).

    Метода целиком мало, файла целиком много: тест, у которого чтение
    документа вынесено в `_parity_rows()`, а фикстуры — в `setUp`,
    говорит о своём предмете именно там, а сосед по файлу, не зовущий
    ничего из этого, в отбор не попадает.
    """
    module_defs = _definitions(tree, source)
    class_defs = {item.name: ast.get_source_segment(source, item) or ""
                  for item in class_node.body
                  if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    text = ast.get_source_segment(source, method) or ""
    for name in _SETUP_METHODS:
        if name in class_defs:
            text += "\n" + class_defs[name]
    # Базовый класс, объявленный В ЭТОМ ЖЕ файле (частая форма песочницы
    # набора): его имя в теле метода не встречается, поэтому добавляется
    # по заголовку класса, а не замыканием ниже.
    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id in module_defs:
            text += "\n" + module_defs[base.id]
    taken, changed = set(), True
    while changed:
        changed = False
        for name in _NAME_TOKEN.findall(text):
            if name in taken:
                continue
            body = class_defs.get(name, module_defs.get(name))
            if body is None:
                continue
            taken.add(name)
            text += "\n" + body
            changed = True
    return text


def test_methods_mentioning(*needles, file_needles=()) -> list:
    """[(имя модуля, класс, метод)] тестовых методов `tests/test_*.py`,
    чей СЦЕНАРИЙ (`_scenario_text`) упоминает все `needles`, а файл —
    все `file_needles`.
    """
    found = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if not all(needle in source
                   for needle in tuple(needles) + tuple(file_needles)):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not item.name.startswith("test"):
                    continue
                scenario = _scenario_text(source, tree, node, item)
                if all(needle in scenario for needle in needles):
                    found.append((f"tests.{path.stem}", node.name, item.name))
    return found


def method_source(module_name: str, class_name: str, method_name: str) -> str:
    """Текст сценария одного тестового метода `tests/` (тот же
    `_scenario_text`, что и у отбора) — по нему планка сверяет, о чём
    тест говорит, а не по файлу целиком, где сосед мог упомянуть что
    угодно."""
    path = TESTS_DIR / f"{module_name.split('.')[-1]}.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == method_name:
                    return _scenario_text(source, tree, node, item)
    return ""


def run_test_methods(ids: list) -> dict:
    """{(модуль, класс, метод): None если прошёл, иначе текст провала} —
    каждый метод прогоняется ОТДЕЛЬНЫМ прогоном: планке нужен исход
    каждого кандидата поимённо, а не агрегат набора."""
    outcomes = {}
    for module_name, class_name, method_name in ids:
        module = importlib.import_module(module_name)
        case = getattr(module, class_name)(method_name)
        result = unittest.TestResult()
        case.run(result)
        problems = result.failures + result.errors
        outcomes[(module_name, class_name, method_name)] = (
            None if not problems else problems[0][1][-800:])
    return outcomes


def passing(outcomes: dict) -> list:
    return [key for key, problem in outcomes.items() if problem is None]


def failing(outcomes: dict) -> list:
    return [key for key, problem in outcomes.items() if problem is not None]


def describe(ids) -> str:
    return ", ".join(f"{m}.{c}.{f}" for m, c, f in ids) or "(пусто)"


# --- артефакты задачи и исходник main -----------------------------------

def plan_text():
    """Текст PLAN.md — из АРТЕФАКТНОЙ ВЕТКИ задачи (`gitcmd.show`), без
    отката на диск: в среде прогона гейта на диске рабочей копии лежит
    один `acceptance_tests/` (skills/test-authoring.md). `None` — ветки
    или файла в ней ещё нет."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text


def main_source(rel: str) -> str:
    """Содержимое файла `rel` из коммита `MAIN_SHA` (`git show`)."""
    text, reason = gitcmd.show(MAIN_SHA, rel)
    if text is None:
        raise AssertionError(f"{MAIN_SHA}:{rel} не прочитан: {reason}")
    return text


#: Место argv, которое собирается вызовом (`runner.declared_tool_path`) —
#: значение зависит от резолва манифеста и сравнивается отдельно.
RESOLVED_CALL = object()


def claude_command_argv(source: str) -> list:
    """Argv шага роли на Claude, вычитанный из ИСХОДНИКА провайдера
    (`ClaudeProvider.command()` без модели): список значений, где элемент,
    собираемый вызовом, заменён маркером `RESOLVED_CALL`.

    Читается argv, а не текст метода: AC-10 говорит о совпадении argv, и
    сверка исходников красила бы планку на переписанном докстринге или
    перенесённом флаге, не меняющем ни одного элемента команды. Значения
    констант модуля (`ALLOWED_TOOLS`) берутся из ТОГО ЖЕ исходника, а
    атрибуты `config.*` (крутилка Оператора) — из сегодняшнего `config`.
    """
    tree = ast.parse(source)
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    function = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ClaudeProvider":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "command":
                    function = item
    if function is None:
        raise AssertionError("в исходнике нет ClaudeProvider.command")
    listing = None
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List) \
                and any(isinstance(t, ast.Name) and t.id == "cmd"
                        for t in node.targets):
            listing = node.value
            break
    if listing is None:
        raise AssertionError("в ClaudeProvider.command нет присваивания "
                             "cmd = [...] — argv не прочитан")
    return [_resolve_element(element, constants) for element in listing.elts]


def _resolve_element(node, constants):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in constants:
            raise AssertionError(f"константа {node.id} не найдена в исходнике")
        return constants[node.id]
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == "config":
        return getattr(config, node.attr)
    if isinstance(node, ast.Call):
        return RESOLVED_CALL
    raise AssertionError(f"элемент argv не разобран: {ast.dump(node)[:120]}")
