"""Наблюдение неослабления: двусторонний прогон КАЖДОГО изменённого метода на переходе `in_dev -> verifying` — место упавшего утверждения в `Outcome`, запись «двусторонний прогон (наблюдение)», признак «в изменённых строках», неизменность вердикта гейта, флаг и предел времени, сводка наблюдения в отчёте (AC-1..AC-10, AC-13, AC-14).

Группа: долгоживущий

Красен до реализации: флага наблюдения в `orchestrator/config.py` и его выключения в `tests/sandbox.py` нет — помощник `observation_on` падает «флаг наблюдения не найден» во всех сценариях на включённом флаге; `two_sided.Outcome` не несёт места утверждения; записи «двусторонний прогон (наблюдение)» гейт не пишет; в отчёте нет сводки наблюдения.

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и клон
артели — один настоящий git-репозиторий `self.root`, голый origin. База —
коммит на main с `app.py` и файлом тестов фикстуры; задача заводится
`catalog.cmd_new`; SPEC (с разделом «Меняемое поведение» или без него),
PLAN и зелёная планка — в ссылке документов задачи; approve —
`fsm.cmd_approve`; голова — коммит рабочей копии задачи; переход —
`fsm.cmd_advance` из `in_dev` (все рубежи настоящие); гейт мержа —
`test_integrity.merge_gate_escalates`; ревью-пакет —
`review.review_package`; отчёт — `report.cmd_report`. Двусторонний прогон
и наблюдение идут настоящим pytest. Запуски процессов видны через обёртку
над `subprocess.Popen` (`SpawnSpy`), которая подменяет только нужный
запуск (таймаут, сбой `git worktree add`, исключение).

Как тест находит имена, которых SPEC не называет:
- флаг наблюдения — атрибут `config`, который `tests/sandbox.py`
  выставляет в `False` (присваиванием `config.<ИМЯ> = False`,
  `setattr(config, "<ИМЯ>", False)` либо `mock.patch.object(config,
  "<ИМЯ>", False)`), а исходник `orchestrator/config.py` присваивает
  `True` (требование 7); включение — `mock.patch.object(config, <ИМЯ>,
  True)`;
- предел времени наблюдения — константы `orchestrator/config.py` со
  значением 600 по исходнику (требование 6): AC-10 подменяет их все;
- запись наблюдения — по действию журнала «двусторонний прогон
  (наблюдение)»; её часть о методе — от адреса `путь::Класс::метод` до
  адреса другого метода; часть о стороне — от названия стороны
  (`two_sided.NEW_ON_BASE`/`two_sided.OLD_ON_BRANCH`) до названия другой;
- исход стороны: «утвержд…» — упала на утверждении, «зелён…» — зелёная;
  место — путь файла и номер строки рядом (`путь:строка`, `путь, строка N`);
- признак «в изменённых строках»: «неприменимо»; либо после слова
  «изменённ…» в пределах 25 знаков «да»/«нет» (true/false, истина/ложь);
  либо «входит»/«не входит»;
- длительность — число с единицей (`с`, `сек`, `s`, `мс`, `ms`).
Имя файла тестов, имя класса, литералы и номера требований — из `random`;
зерно печатается и входит в текст каждого провала.

Валидация стабом: временный стаб во временной ветке (флаг `True` и предел
600 в `config`, выключение флага в `tests/sandbox.py`, место утверждения —
последний кадр вне библиотек — в плагине и новых полях `Outcome`, таймаут
стороны параметром `two_sided.run`, наблюдение по методу в
`_test_integrity_gate` после `_journal_pass`, сводка в отчёте) — все тесты
файла зелёные; мутации стаба «признак стороны „старая версия на ветке“ по
изменённым строкам head» и «класс „смена ожидания“ раньше „покрыто
мандатом“» краснят AC-4 и AC-13. Стаб удалён, ветка удалена.
"""
import ast
import contextlib
import dataclasses
import html
import io
import os
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (artifact_source, catalog, config, fsm, projects,
                          report, review, store, workspace)
from orchestrator.advance_gates import test_integrity, two_sided
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox

DOCS_REF_PREFIX = "refs/artifacts/"

OBS_ACTION = "двусторонний прогон (наблюдение)"
PASSED_ACTION = test_integrity.TWO_SIDED_PASSED_ACTION
REFUSAL_ACTION = test_integrity.TEST_INTEGRITY_REFUSAL_ACTION
ALLOWED_ACTION = test_integrity.TEST_INTEGRITY_ALLOWED_ACTION
MARKER = test_integrity.TEST_WEAKENING_MANDATE_MARKER
OUTSIDE = test_integrity.REASON_OUTSIDE
TWO_SIDED_MISSING = test_integrity.REASON_TWO_SIDED_MISSING
NEW_ON_BASE = two_sided.NEW_ON_BASE
OLD_ON_BRANCH = two_sided.OLD_ON_BRANCH
SIDES = (NEW_ON_BASE, OLD_ON_BRANCH)
REQUIREMENTS = 9
OBSERVATION_LIMIT_SOURCE_VALUE = 600

SANDBOX_SOURCE = Path(__file__).resolve().parent / "sandbox.py"
CONFIG_SOURCE = Path(config.__file__).resolve()
REAL_POPEN = subprocess.Popen

DURATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:мс|ms|сек\w*|с|s)(?!\w)")
FLAG_TOKEN = re.compile(
    r"изм[её]н[её]нн\w*[^;\n|]{0,25}?(?<!\w)(да|нет|true|false|истина|ложь)(?!\w)",
    re.I)

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, app.py
budget_usd: 30
---

# SPEC: фикстура наблюдения

## Контекст

Фикстура песочницы.

## Требования

{requirements}

## Критерии приёмки

AC-1. Фикстурный критерий.
{section}
## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: фикстура

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

Нет.
"""

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_fixture_plank(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''


# ---------------------------------------------------------------------------
# Имена флага и предела — из исходников (см. докстринг модуля).

def _value(node: ast.AST):
    """Значение константного выражения исходника (числа, строки, `True`,
    арифметика над числами); иное — `ValueError`."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_value(node.operand)
    if isinstance(node, ast.BinOp):
        left, right = _value(node.left), _value(node.right)
        ops = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
               ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}
        for kind, fn in ops.items():
            if isinstance(node.op, kind):
                return fn(left, right)
    raise ValueError(ast.dump(node))


def config_source_constants() -> dict:
    """{имя: значение} присваиваний верхнего уровня исходника
    `orchestrator/config.py` с константным значением."""
    tree = ast.parse(CONFIG_SOURCE.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for target in targets:
            if isinstance(target, ast.Name):
                try:
                    found[target.id] = _value(value)
                except ValueError:
                    continue
    return found


def _is_config(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "config"


def _is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def sandbox_disabled_names() -> set:
    """Атрибуты `config`, которые `tests/sandbox.py` выставляет в `False`."""
    tree = ast.parse(SANDBOX_SOURCE.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_false(node.value):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and _is_config(target.value):
                    names.add(target.attr)
        if isinstance(node, ast.Call) and len(node.args) >= 3 \
                and _is_config(node.args[0]) and _is_false(node.args[2]) \
                and isinstance(node.args[1], ast.Constant) \
                and isinstance(node.args[1].value, str):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else \
                getattr(func, "id", "")
            if name in ("setattr", "object"):
                names.add(node.args[1].value)
    return names


def observation_flags() -> list:
    """Флаг наблюдения: выключен в `tests/sandbox.py`, `True` в исходнике
    `orchestrator/config.py`."""
    constants = config_source_constants()
    return sorted(n for n in sandbox_disabled_names()
                  if constants.get(n) is True)


def limit_names() -> list:
    """Константы `orchestrator/config.py` со значением 600 по исходнику."""
    return sorted(n for n, v in config_source_constants().items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)
                  and v == OBSERVATION_LIMIT_SOURCE_VALUE)


# ---------------------------------------------------------------------------
# Фикстуры исходников.

def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def method_text(name: str, lines: list) -> str:
    """Метод фикстуры с заявкой мутации (её требует соседний гейт)."""
    body = "".join(f"        {line}\n" for line in lines)
    return (f"\n    def {name}(self):\n"
            f'        """Фикстура {name}.\n\n'
            f"        Ловит мутацию: фикстура песочницы.\n"
            f'        """\n{body}')


def fixture_source(cls: str, methods: dict, header: str = "") -> str:
    """Файл тестов фикстуры: класс `cls`, {имя метода: [строки тела]}."""
    text = f"import unittest\n\nimport app\n{header}\n\nclass {cls}(unittest.TestCase):\n"
    for name, lines in methods.items():
        text += method_text(name, lines)
    return text


def line_of(source: str, needle: str) -> int:
    """Номер (с 1) первой строки `source`, содержащей `needle`."""
    for number, line in enumerate(source.splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(f"строки {needle!r} в фикстуре нет")


def pairs_text(pairs: list) -> str:
    return "; ".join(f"`{old}` → `{new}`" for old, new in pairs)


def segment(text: str, name: str, names) -> str:
    """Кусок `text` от первого вхождения `name` до первого вхождения
    любого другого имени из `names` после него (или до конца)."""
    start = text.find(name)
    if start < 0:
        return ""
    end = len(text)
    for other in names:
        if other == name or other in name:
            continue
        pos = text.find(other, start + len(name))
        if 0 <= pos < end:
            end = pos
    return text[start:end]


def side_part(text: str, side: str) -> str:
    return segment(text, side, SIDES)


def flag_of(text: str):
    """Признак «в изменённых строках» в куске записи: `"n/a"`, `"yes"`,
    `"no"`; `None` — не распознан."""
    if "неприменимо" in text:
        return "n/a"
    match = FLAG_TOKEN.search(text)
    if match:
        return "yes" if match.group(1).lower() in ("да", "true", "истина") \
            else "no"
    if re.search(r"не\s+входит|вне\s+изм[её]н[её]нн", text):
        return "no"
    if re.search(r"входит", text):
        return "yes"
    return None


def has_location(text: str, path: str, line: int) -> bool:
    return re.search(rf"{re.escape(path)}[^\d\n]{{0,20}}?(?<!\d){line}(?!\d)",
                     text) is not None


# ---------------------------------------------------------------------------
# Запуски процессов.

def is_pytest_node(argv: list) -> bool:
    """Запуск pytest по узлу `<файл>.py::…`."""
    return any("pytest" in a for a in argv) and any(".py::" in a for a in argv)


def is_worktree_add(argv: list) -> bool:
    return bool(argv) and argv[0].rsplit("/", 1)[-1] == "git" \
        and "worktree" in argv and "add" in argv


class TimeoutProc:
    """Процесс, у которого истекает любое ожидание с таймаутом."""

    def __init__(self, args):
        self.args = args
        self.returncode = None
        self.pid = 0
        self.stdin = self.stdout = self.stderr = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def communicate(self, input=None, timeout=None):
        raise subprocess.TimeoutExpired(self.args, timeout or 0)

    def wait(self, timeout=None):
        if timeout is not None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.returncode = -9
        return -9

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    terminate = kill


class RecordingPopen(REAL_POPEN):
    """Настоящий процесс, запоминающий таймаут ожидания в `sink`."""

    sink: list = None
    in_communicate = False

    def communicate(self, input=None, timeout=None):
        self.sink.append(timeout)
        self.in_communicate = True
        try:
            return super().communicate(input, timeout)
        finally:
            self.in_communicate = False

    def wait(self, timeout=None):
        if timeout is not None and not self.in_communicate:
            self.sink.append(timeout)
        return super().wait(timeout)


def recording_rule(sink: list):
    """Подмена запуска pytest по узлу настоящим процессом, пишущим
    таймаут ожидания в `sink`."""
    def make(args, *rest, **kwargs):
        proc = RecordingPopen(args, *rest, **kwargs)
        proc.sink = sink
        return proc
    return lambda argv: make if is_pytest_node(argv) else None


def timeout_rule(argv: list):
    return (lambda args, *a, **k: TimeoutProc(args)) if is_pytest_node(argv) \
        else None


class SpawnSpy:
    """Обёртка над настоящим `subprocess.Popen`: запоминает (argv, cwd)
    каждого запуска; `rule(argv)` может вернуть замену того же вида."""

    def __init__(self, real, rule=None):
        self.real = real
        self.rule = rule
        self.calls: list = []

    def __call__(self, args, *rest, **kwargs):
        argv = [str(a) for a in args] if isinstance(args, (list, tuple)) \
            else [str(args)]
        self.calls.append((argv, str(kwargs.get("cwd") or "")))
        substitute = self.rule(argv) if self.rule else None
        if substitute is not None:
            return substitute(args, *rest, **kwargs)
        return self.real(args, *rest, **kwargs)

    def pytest_nodes(self) -> list:
        return [argv for argv, _cwd in self.calls if is_pytest_node(argv)]

    def worktree_adds(self) -> list:
        return [argv for argv, _cwd in self.calls if is_worktree_add(argv)]


# ---------------------------------------------------------------------------
# Место утверждения в `Outcome` (AC-1).

def leaves(value) -> list:
    """Листья структуры: строки и числа (пути — строкой)."""
    if isinstance(value, bool):
        return [value]
    if isinstance(value, (str, int, float)):
        return [value]
    if isinstance(value, Path):
        return [str(value)]
    if isinstance(value, dict):
        return [leaf for k, v in value.items() for leaf in leaves(k) + leaves(v)]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [leaf for item in value for leaf in leaves(item)]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [leaf for f in dataclasses.fields(value)
                for leaf in leaves(getattr(value, f.name))]
    if hasattr(value, "__dict__"):
        return leaves(vars(value))
    return []


def nodes(value) -> list:
    """Все контейнеры структуры, включая её саму."""
    found = []
    if isinstance(value, (str, bytes, int, float, bool, Path)) or value is None:
        return found
    found.append(value)
    if isinstance(value, dict):
        children = list(value.keys()) + list(value.values())
    elif isinstance(value, (list, tuple, set, frozenset)):
        children = list(value)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        children = [getattr(value, f.name) for f in dataclasses.fields(value)]
    elif hasattr(value, "__dict__"):
        children = list(vars(value).values())
    else:
        children = []
    for child in children:
        found += nodes(child)
    return found


def outcome_extra(outcome) -> list:
    """Поля `Outcome` сверх прежних (`refusals`, `results`, `head_sha`,
    `base_sha`)."""
    known = (outcome.refusals, outcome.results, outcome.head_sha,
             outcome.base_sha)
    if isinstance(outcome, tuple):
        values = list(outcome)
    elif dataclasses.is_dataclass(outcome):
        values = [getattr(outcome, f.name) for f in dataclasses.fields(outcome)]
    else:
        values = list(vars(outcome).values())
    return [v for v in values if not any(v is k for k in known)]


def _path_leaf(leaf, path: str) -> bool:
    return isinstance(leaf, str) and (
        leaf == path or re.search(rf"(?<![\w/.-]){re.escape(path)}", leaf))


def _line_leaf(leaf, line: int) -> bool:
    if isinstance(leaf, bool):
        return False
    if isinstance(leaf, int):
        return leaf == line
    return isinstance(leaf, str) and re.search(rf"(?<!\d){line}(?!\d)", leaf)


def _text_leaf(leaf, text: str) -> bool:
    return isinstance(leaf, str) and text.strip() in leaf


def location_found(extra: list, path: str, line: int, text: str,
                   foreign: list) -> bool:
    """В дополнительных полях есть контейнер с путём `path`, строкой
    `line` и текстом `text`, не несущий текстов `foreign` (места других
    методов)."""
    for node in nodes(extra):
        found = leaves(node)
        if any(_text_leaf(leaf, f) for leaf in found for f in foreign):
            continue
        if any(_path_leaf(leaf, path) for leaf in found) \
                and any(_line_leaf(leaf, line) for leaf in found) \
                and any(_text_leaf(leaf, text) for leaf in found):
            return True
    return False


# Сдвиг литерала голого `assert` от значения стороны — вне диапазона сдвига
# `new` от `old` (1…3999): иначе на части зёрен `new == bare_old`, и старая
# версия голого `assert` зеленеет на ветке (SPEC 01M5G6PDQA7AYDYDPA7DD5JD4S,
# зерно 189949286).
NEW_SHIFT_LIMIT = 4000
BARE_SHIFT = NEW_SHIFT_LIMIT


def location_literals(seed: int) -> dict:
    """Литералы фикстуры `test_ac1_outcome_carries_relative_assertion_location`
    от зерна: имена класса, файлов, модуля помощника и ветки, значения
    `app.VALUE` сторон, литералы утверждений и тексты файлов. При любом зерне
    `bare_old != new`, `bare_new != old`, `old != new`, а `sent_other` и
    `sent_same` не равны ни `old`, ни `new`."""
    rng = random.Random(seed)
    cls = f"Fx{word(rng).capitalize()}Test"
    path = f"tests/test_fx_{word(rng)}.py"
    helper_mod = f"fxcheck_{word(rng)}"
    old = rng.randrange(1000, 5000)
    new = old + rng.randrange(1, NEW_SHIFT_LIMIT)
    bare_old, bare_new = old + BARE_SHIFT, new + BARE_SHIFT
    sent_other = new + 10000 + rng.randrange(1000)
    sent_same = sent_other + 20000
    header = (f"from tests.{helper_mod} import check_other\n\n\n"
              f"def check_same(value):\n"
              f"    assert value == {sent_same}, 'помощник того же файла'\n")

    def source(value: int, bare: int, green: bool) -> str:
        return fixture_source(cls, {
            "test_self": [f"self.assertEqual(app.VALUE + 0, {value})"],
            "test_bare": [f"assert app.VALUE * 1 == {bare}"],
            "test_other": ["check_other(app.VALUE)",
                           f"self.assertEqual(app.VALUE, {value})"],
            "test_same": ["check_same(app.VALUE)",
                          f"self.assertEqual(app.VALUE, {value})"],
            "test_green": (["self.assertTrue(app.VALUE)"] if green else
                           [f"self.assertEqual(app.VALUE - 0, {value})"]),
        }, header)

    return {
        "cls": cls, "path": path, "helper_mod": helper_mod,
        "helper_path": f"tests/{helper_mod}.py",
        "old": old, "new": new, "bare_old": bare_old, "bare_new": bare_new,
        "sent_other": sent_other, "sent_same": sent_same,
        "helper_source": (f"def check_other(value):\n"
                          f"    assert value == {sent_other}, 'помощник другого файла'\n"),
        "base_source": source(old, bare_old, green=False),
        "head_source": source(new, bare_new, green=True),
        "base_app": f"VALUE = {old}\n", "head_app": f"VALUE = {new}\n",
        "branch": f"task/fx-{word(rng)}",
    }


class LocationLiteralsTest(unittest.TestCase):

    def test_literals_never_collide(self):
        """`location_literals` на зёрнах 0…19999 и 189949286, 12, 9694, 11783 даёт попарно различные значения сторон и литералов утверждений.

        Сценарий: для каждого зерна `bare_old != new`, `bare_new != old`,
        `old != new`, `sent_other` и `sent_same` не равны ни `old`, ни
        `new`.

        Ловит мутацию: сдвиг голого `assert` возвращён к 7 при сдвиге `new`
        из 1…3999 — на зерне 189949286 `new == bare_old`; `sent_same`
        выбран из диапазона, пересекающего `new`.
        """
        bad = []
        for seed in [*range(20000), 189949286, 12, 9694, 11783]:
            v = location_literals(seed)
            if not (v["bare_old"] != v["new"] and v["bare_new"] != v["old"]
                    and v["old"] != v["new"]
                    and v["sent_other"] not in (v["old"], v["new"])
                    and v["sent_same"] not in (v["old"], v["new"])):
                bad.append((seed, v["old"], v["new"]))
        self.assertEqual(bad[:5], [], f"совпадения на {len(bad)} зёрнах")


class OutcomeLocationTest(GitignoreCommittedRealGitSandbox):
    """`two_sided.run` на настоящем репозитории песочницы: база на main,
    голова на ветке."""

    def test_ac1_outcome_carries_relative_assertion_location(self):
        """`Outcome` несёт путь (относительно корня дерева стороны), номер и текст строки упавшего утверждения; вердикт прежний.

        Сценарий: файл тестов фикстуры с пятью методами — `self.assertEqual`
        (стиль тестов пульта), голый `assert`, утверждение в помощнике
        другого файла `tests/`, утверждение в помощнике того же файла вне
        метода и метод, чья новая версия зелёная на базе. `app.VALUE` на
        базе и на ветке разное, литералы случайные. Для каждой упавшей
        стороны в дополнительных полях `Outcome` есть контейнер с путём
        файла (для помощника другого файла — его путь), номером строки
        утверждения в этом файле (не `unittest/case.py`) и текстом строки;
        ни один лист не несёт абсолютного пути временного дерева. Отказ —
        ровно прежняя строка «новая версия на базе: зелёная — тест не
        различает поведение» про зелёный метод, `results` — «пройден» у
        остальных.

        Ловит мутацию: плагин берёт последний кадр трассировки — номер
        строки из `unittest/case.py`, а не из файла теста; кадр помощника
        другого файла отброшен как «не файл узла» и место не записано; путь
        пишется абсолютным путём временного дерева; место положено в текст
        `results`/`refusals` — вердикт изменился.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        lit = location_literals(seed)
        for rel in (lit["path"], lit["helper_path"]):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / "app.py").write_text(lit["base_app"], encoding="utf-8")
        (self.root / lit["path"]).write_text(lit["base_source"], encoding="utf-8")
        (self.root / lit["helper_path"]).write_text(lit["helper_source"],
                                                    encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        base_sha = self.git("rev-parse", "HEAD").strip()
        self.checkout(lit["branch"], create=True)
        (self.root / "app.py").write_text(lit["head_app"], encoding="utf-8")
        (self.root / lit["path"]).write_text(lit["head_source"], encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        self.checkout(config.MAIN_BRANCH)
        self.check_relative_location(seed, base_sha, lit["branch"])

    def test_ac1_relative_location_on_colliding_seed(self):
        """Сценарий `test_ac1_outcome_carries_relative_assertion_location` на зерне 189949286 зелёный.

        Сценарий: подготовка репозитория — как в методе со случайным
        зерном, литералы — `location_literals(189949286)`; на этом зерне
        сдвиг `new` от `old` равен 7, прежний сдвиг голого `assert`.

        Ловит мутацию: сдвиг голого `assert` возвращён к 7 — на этом зерне
        `new == bare_old`, старая версия `test_bare` зелёная на ветке, и
        `results` несёт для неё не «пройден».
        """
        seed = 189949286
        lit = location_literals(seed)
        for rel in (lit["path"], lit["helper_path"]):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / "app.py").write_text(lit["base_app"], encoding="utf-8")
        (self.root / lit["path"]).write_text(lit["base_source"], encoding="utf-8")
        (self.root / lit["helper_path"]).write_text(lit["helper_source"],
                                                    encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        base_sha = self.git("rev-parse", "HEAD").strip()
        self.checkout(lit["branch"], create=True)
        (self.root / "app.py").write_text(lit["head_app"], encoding="utf-8")
        (self.root / lit["path"]).write_text(lit["head_source"], encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        self.checkout(config.MAIN_BRANCH)
        self.check_relative_location(seed, base_sha, lit["branch"])

    def check_relative_location(self, seed: int, base_sha: str, branch: str) -> None:
        """`two_sided.run` и утверждения `test_ac1_outcome_carries_relative_assertion_location`
        над репозиторием, подготовленным методом из `location_literals(seed)`."""
        lit = location_literals(seed)
        note = lambda text: f"{text} (зерно: {seed})"  # noqa: E731
        cls, path, helper_path = lit["cls"], lit["path"], lit["helper_path"]
        old, new = lit["old"], lit["new"]
        bare_old, bare_new = lit["bare_old"], lit["bare_new"]
        sent_other, sent_same = lit["sent_other"], lit["sent_same"]
        helper_source = lit["helper_source"]
        base_source, head_source = lit["base_source"], lit["head_source"]

        names =("test_self", "test_bare", "test_other", "test_same", "test_green")
        methods = [two_sided.Method(path, path, f"{cls}::{m}", base_source,
                                    head_source) for m in names]
        outcome = two_sided.run(self.root, branch, base_sha, methods)
        extra = outcome_extra(outcome)
        context = note(f"outcome: {outcome!r}")

        green_address = f"{path}::{cls}::test_green"
        expected_green = (f"{NEW_ON_BASE}: зелёная — тест не различает "
                          f"поведение")
        self.assertEqual(outcome.refusals, [
            f"{path}: {cls}::test_green: двусторонний прогон: {expected_green}"],
            context)
        self.assertEqual(outcome.results, {
            **{f"{path}::{cls}::{m}": two_sided.PASSED for m in names[:-1]},
            green_address: expected_green}, context)

        helper_line = "    assert value == " + str(sent_other)
        same_line = "    assert value == " + str(sent_same)
        expectations = {
            ("test_self", NEW_ON_BASE): (path, f"self.assertEqual(app.VALUE + 0, {new})", head_source),
            ("test_self", OLD_ON_BRANCH): (path, f"self.assertEqual(app.VALUE + 0, {old})", base_source),
            ("test_bare", NEW_ON_BASE): (path, f"assert app.VALUE * 1 == {bare_new}", head_source),
            ("test_bare", OLD_ON_BRANCH): (path, f"assert app.VALUE * 1 == {bare_old}", base_source),
            ("test_other", NEW_ON_BASE): (helper_path, helper_line, helper_source),
            ("test_other", OLD_ON_BRANCH): (helper_path, helper_line, helper_source),
            ("test_same", NEW_ON_BASE): (path, same_line, head_source),
            ("test_same", OLD_ON_BRANCH): (path, same_line, base_source),
            ("test_green", OLD_ON_BRANCH): (path, f"self.assertEqual(app.VALUE - 0, {old})", base_source),
        }
        for (method, side), (rel, text, text_source) in expectations.items():
            foreign = sorted({t for (m, _s), (_r, t, _x) in expectations.items()
                              if m != method and t.strip() != text.strip()})
            line = line_of(text_source, text)
            with self.subTest(method=method, side=side):
                self.assertTrue(
                    location_found(extra, rel, line, text, foreign),
                    note(f"{method} / {side}: нет места {rel}:{line} "
                         f"«{text.strip()}» в {extra!r}"))
        absolute = [leaf for leaf in leaves(extra) if isinstance(leaf, str)
                    and re.search(rf"[^\s:'\"]/(?:{re.escape(path)}|"
                                  rf"{re.escape(helper_path)})", leaf)]
        self.assertEqual(absolute, [], note(f"абсолютный путь места: {absolute}"))


# ---------------------------------------------------------------------------
# Песочница перехода.

class ObservationSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели от `spec_gate` до `in_dev`: база на main, SPEC в ссылке
    документов, голова в рабочей копии задачи и в origin."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.cls = f"Fx{word(self.rng).capitalize()}Test"
        self.path = f"tests/test_fx_{word(self.rng)}.py"
        self.origin = self.add_synced_origin()
        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(
            SPEC_TEXT.format(task="TASK_ID", requirements="1. Фикстура.",
                             section=""), encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.task_id = ""
        self.branch = ""
        self.wt = None
        self.methods: list = []

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def run_cmd(self, fn, *args, **kwargs) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    @contextlib.contextmanager
    def observation_on(self):
        """Флаг наблюдения включён (имя — из исходников, докстринг модуля)."""
        flags = observation_flags()
        self.assertTrue(flags, self.note(
            "флаг наблюдения не найден: нет атрибута config, выключенного в "
            "tests/sandbox.py и включённого в исходнике orchestrator/config.py"))
        with contextlib.ExitStack() as stack:
            for flag in flags:
                stack.enter_context(mock.patch.object(config, flag, True))
            yield

    @contextlib.contextmanager
    def spawn_spy(self, rule=None):
        spy = SpawnSpy(subprocess.Popen, rule)
        with mock.patch.object(subprocess, "Popen", spy):
            yield spy

    def name(self, method: str) -> str:
        return f"{self.cls}::{method}"

    def full(self, method: str) -> str:
        return f"{self.path}::{self.cls}::{method}"

    def line(self, method: str, pairs: list, req: int) -> str:
        return f"- `{self.full(method)}`: {pairs_text(pairs)} (требование {req})"

    def spec_text(self, section) -> str:
        requirements = "\n".join(f"{n}. Требование фикстуры номер {n}."
                                 for n in range(1, REQUIREMENTS + 1))
        body = "" if section is None else (
            "\n## Меняемое поведение\n\nСмены ожидания фикстуры.\n\n"
            + "\n".join(section) + "\n")
        return SPEC_TEXT.format(task=self.task_id, requirements=requirements,
                                section=body)

    def docs_head(self) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + self.task_id).strip()

    def commit_docs(self, files: dict, message: str) -> None:
        old = self.docs_head()
        self.assertTrue(old, self.note("ссылки документов нет"))
        scratch = self.root / ".artel" / f"docs-copy-{self.rng.randrange(1 << 30)}"
        self.git("worktree", "add", "-q", "--detach", str(scratch), old)
        try:
            for rel, text in files.items():
                target = scratch / "tasks" / self.task_id / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            self.git("-C", str(scratch), "add", "-A")
            self.git("-C", str(scratch), "commit", "-q", "-m", message)
            new = self.git("-C", str(scratch), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(scratch))
        self.git("update-ref", DOCS_REF_PREFIX + self.task_id, new, old)
        store.record_fixation(store.db(), self.task_id)

    # --- сценарий ------------------------------------------------------

    def start(self, base: dict, section) -> None:
        """База на main, задача, документы, approve, `in_dev`."""
        for rel, text in base.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        before = {row["id"] for row in store.all_tasks(store.db())}
        self.run_cmd(catalog.cmd_new, f"Наблюдение {self.seed}",
                     target=config.DEFAULT_TARGET)
        created = [row["id"] for row in store.all_tasks(store.db())
                   if row["id"] not in before]
        self.assertEqual(len(created), 1, self.note("задача не заведена"))
        self.task_id = created[0]
        self.branch = self.row()["branch"]
        if not self.git("branch", "--list", self.branch).strip():
            self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.commit_docs({"SPEC.md": self.spec_text(section),
                          "PLAN.md": PLAN_TEXT.format(task=self.task_id),
                          "acceptance_tests/test_plank.py": PLANK_TEXT},
                         "документы задачи")
        store.update_task(store.db(), self.task_id, state="spec_gate")
        store.record_fixation(store.db(), self.task_id)
        out = self.run_cmd(fsm.cmd_approve, self.task_id)
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.docs_head(), state="in_dev",
                          draft_mr_created=1)
        store.record_fixation(store.db(), self.task_id)

    def head(self, files: dict, message: str = "голова") -> None:
        for rel, text in files.items():
            target = self.wt / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("-C", str(self.wt), "add", "-A")
        self.git("-C", str(self.wt), "commit", "-q", "--allow-empty", "-m",
                 message)
        self.git("push", "-q", "-f", "origin", f"{self.branch}:{self.branch}")

    def move_head(self) -> None:
        """Новый коммит головы без правки `tests/` — новый sha."""
        app = self.wt / "app.py"
        app.write_text(app.read_text(encoding="utf-8")
                       + f"# сдвиг {self.rng.randrange(1 << 30)}\n",
                       encoding="utf-8")
        self.head({}, "сдвиг головы")

    def scenario(self, base: dict, head: dict, section, elements: str = "") -> None:
        """База, approve, `in_dev`, голова, мандат (если `elements`)."""
        self.methods = sorted({m for files in (base, head)
                               for m in re.findall(r"def (test_\w+)\(",
                                                   files.get(self.path, ""))})
        self.start(base, section)
        self.head(head)
        if elements:
            self.mandate(elements)

    def head_sha(self) -> str:
        return self.git("rev-parse", f"refs/heads/{self.branch}").strip()

    def mandate(self, elements: str) -> None:
        self.commit_docs({"ANSWER-1.md": f"# Ответ Оператора\n\n{MARKER} "
                                         f"{elements}\nОснование: решение "
                                         f"Оператора ({self.seed}).\n"},
                         f"{self.task_id}: ANSWER-1 — ответ Оператора")

    def advance(self) -> str:
        return self.run_cmd(fsm.cmd_advance, self.task_id)

    def reset_in_dev(self) -> None:
        store.update_task(store.db(), self.task_id, state="in_dev")

    def row(self):
        return store.get_task(store.db(), self.task_id)

    def state(self) -> str:
        return self.row()["state"]

    def steps(self) -> list:
        return [(s["id"], s["action"], s["detail"] or "", s["actor"])
                for s in store.task_steps(store.db(), self.task_id)]

    def details(self, action: str) -> list:
        return [detail for _id, act, detail, _a in self.steps() if act == action]

    def journal_text(self) -> str:
        return "\n".join(f"{act} | {detail}" for _id, act, detail, _a in self.steps())

    def refusal(self) -> str:
        found = self.details(REFUSAL_ACTION)
        return found[-1] if found else ""

    def observations(self) -> list:
        return self.details(OBS_ACTION)

    def observation_of(self, method: str) -> str:
        """Записи наблюдения о методе `method`: запись целиком, если других
        методов она не называет, иначе её часть от адреса метода."""
        full = self.full(method)
        others = [self.full(m) for m in self.methods if m != method]
        parts = []
        for rec in self.observations():
            if full not in rec:
                continue
            if any(o in rec for o in others):
                rec = segment(rec, full, others + [full])
            parts.append(rec)
        return "\n".join(parts)

    def artifact(self) -> str:
        docs, _foreign = artifact_source.resolve(store.db(), self.task_id)
        return docs

    def merge_gate(self) -> bool:
        return test_integrity.merge_gate_escalates(
            store.db(), self.task_id, self.state(), self.branch, self.artifact())

    def review_text(self) -> str:
        return review.review_package(store.db(), self.task_id,
                                     self.row()["title"], self.branch)["text"]

    def context(self, out: str = "", spy: SpawnSpy = None) -> str:
        calls = f"\nзапуски:\n{spy.calls}" if spy is not None else ""
        return self.note(f"вывод:\n{out}\nжурнал:\n{self.journal_text()}{calls}")

    # --- фикстуры ------------------------------------------------------

    def two_values(self) -> tuple:
        old = self.rng.randrange(1000, 5000)
        return old, old + self.rng.randrange(1, 4000)

    def value_change(self, base_value, head_value, old, new,
                     method: str = "test_value") -> tuple:
        base = {"app.py": f"VALUE = {base_value!r}\n",
                self.path: fixture_source(self.cls, {
                    method: [f"self.assertEqual(app.VALUE, {old!r})"]})}
        head = {"app.py": f"VALUE = {head_value!r}\n",
                self.path: fixture_source(self.cls, {
                    method: [f"self.assertEqual(app.VALUE, {new!r})"]})}
        return base, head

    def undeclared_files(self) -> tuple:
        """Смена литерала `test_value` вне раздела; обе стороны падают на
        утверждении."""
        old, new = self.two_values()
        return self.value_change(old, new, old, new)

    def declared_scenario(self, head_value=None) -> tuple:
        """Объявленная смена литерала `test_value` (требование 2); `app.VALUE`
        на ветке — `head_value(old, new)` (по умолчанию `new`)."""
        old, new = self.two_values()
        base, head = self.value_change(
            old, new if head_value is None else head_value(old, new), old, new)
        self.scenario(base, head, [self.line("test_value", [(repr(old), repr(new))], 2)])
        return old, new


# ---------------------------------------------------------------------------
# AC-1 (признак «неприменимо»), AC-2, AC-3, AC-4: запись наблюдения.

class ObservationRecordTest(ObservationSandbox):

    def test_ac1_helper_assertion_flag_is_not_applicable(self):
        """Упавшее утверждение в помощнике другого файла и в помощнике того же файла вне метода — признак «неприменимо» у обеих сторон.

        Сценарий: два необъявленных метода сменили литерал своего
        `assertEqual`, но первым в каждом стоит вызов помощника, который
        падает на обоих деревьях: `check_other` из `tests/<модуль>.py` и
        `check_same` — функция того же файла вне тела метода. Переход
        отклонён находками; запись наблюдения о каждом методе по каждой
        стороне несёт «неприменимо», о первом — путь файла помощника.

        Ловит мутацию: признак считается по номеру строки без сверки
        файла — строка помощника другого файла сверяется с изменёнными
        строками метода и даёт «да»/«нет»; строка помощника того же файла
        вне тела метода сверяется с изменёнными строками — «нет» вместо
        «неприменимо»; место помощника другого файла не пишется.
        """
        mod = f"fxcheck_{word(self.rng)}"
        helper_path = f"tests/{mod}.py"
        old, new = self.two_values()
        sent_other, sent_same = new + 10000, new + 30000
        header = (f"from tests.{mod} import check_other\n\n\n"
                  f"def check_same(value):\n"
                  f"    assert value == {sent_same}, 'помощник того же файла'\n")

        def files(value: int) -> dict:
            return {"app.py": f"VALUE = {value}\n",
                    self.path: fixture_source(self.cls, {
                        "test_other": ["check_other(app.VALUE)",
                                       f"self.assertEqual(app.VALUE, {value})"],
                        "test_same": ["check_same(app.VALUE)",
                                      f"self.assertEqual(app.VALUE, {value})"]},
                        header)}

        base = {**files(old), helper_path: (
            f"def check_other(value):\n"
            f"    assert value == {sent_other}, 'помощник другого файла'\n")}
        self.scenario(base, files(new), None)
        with self.observation_on():
            out = self.advance()
        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        other = self.observation_of("test_other")
        same = self.observation_of("test_same")
        self.assertTrue(other and same, context)
        self.assertIn(helper_path, other, context)
        for method, text in (("test_other", other), ("test_same", same)):
            for side in SIDES:
                with self.subTest(method=method, side=side):
                    self.assertEqual(flag_of(side_part(text, side)), "n/a",
                                     self.note(f"{method} / {side}: {text}"))

    def test_ac2_undeclared_method_gets_full_observation_record(self):
        """Изменённый необъявленный метод получает запись наблюдения со всеми полями требования 2.

        Сценарий: раздела «Меняемое поведение» нет; `test_lit` сменил
        литерал `assertEqual` (`app.VALUE` сменился так же — обе стороны
        падают на утверждении), `test_weak` заменил `assertEqual` на
        `assertTrue` (новая версия на базе зелёная). Переход отклонён
        находками. Запись о `test_lit` несёт sha головы, адрес
        `путь::Класс::метод`, текстовый вердикт «смена вне раздела…», вид
        «смена ожидания», обе стороны с исходом «утверждение», место
        `путь:строка` упавшего утверждения каждой стороны (строка из
        версии файла этой стороны), распознанный признак и длительность.
        Запись о `test_weak` несёт вид «ослабление или иная смена», признак
        «другой вид утверждения», вердикт «ослабление» и сторону «новая
        версия на базе» с исходом «зелёный».

        Ловит мутацию: наблюдение гоняет только объявленные методы — записей
        нет; в запись не попадает sha головы, вердикт, `kind`/`signs`,
        место или длительность; исход стороны пишется одним на метод, а не
        по сторонам; для стороны «старая версия на ветке» номер строки
        берётся из версии головы.
        """
        old, new = self.two_values()

        def files(value: int, lit: int, weak: str) -> dict:
            return {"app.py": f"VALUE = {value}\n",
                    self.path: fixture_source(self.cls, {
                        "test_lit": [f"self.assertEqual(app.VALUE, {lit})"],
                        "test_weak": [weak]})}

        base = files(old, old, f"self.assertEqual(app.VALUE * 1, {old})")
        head = files(new, new, "self.assertTrue(app.VALUE)")
        self.scenario(base, head, None)
        sha = self.head_sha()
        with self.observation_on():
            out = self.advance()
        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        lit = self.observation_of("test_lit")
        weak = self.observation_of("test_weak")
        self.assertTrue(lit, context)
        self.assertTrue(weak, context)
        self.assertIn(sha[:7], lit, context)
        self.assertIn(self.full("test_lit"), lit, context)
        self.assertIn(OUTSIDE, lit, context)
        self.assertIn(guard.ASSERTION_CHANGE_EXPECTATION, lit, context)
        self.assertRegex(lit, DURATION, context)
        lines = {NEW_ON_BASE: line_of(head[self.path], f"assertEqual(app.VALUE, {new})"),
                 OLD_ON_BRANCH: line_of(base[self.path], f"assertEqual(app.VALUE, {old})")}
        for side in SIDES:
            part = side_part(lit, side)
            with self.subTest(method="test_lit", side=side):
                self.assertRegex(part, r"утвержд", self.note(f"{side}: {lit}"))
                self.assertTrue(has_location(part, self.path, lines[side]),
                                self.note(f"{side}: нет места "
                                          f"{self.path}:{lines[side]}: {lit}"))
                self.assertIsNotNone(flag_of(part), self.note(f"{side}: {lit}"))
        self.assertIn(guard.ASSERTION_CHANGE_OTHER, weak, context)
        self.assertIn(guard.SIGN_OTHER_KIND, weak, context)
        self.assertIn(test_integrity.REASON_WEAKENING, weak, context)
        self.assertRegex(side_part(weak, NEW_ON_BASE), r"зел[её]н", context)
        self.assertNotRegex(side_part(weak, OLD_ON_BRANCH), r"зел[её]н", context)

    def test_ac3_method_with_same_sources_is_not_run(self):
        """Метод вызывающего файла вне диффа (тексты файла base и head совпадают) двусторонним прогоном наблюдения не прогоняется.

        Сценарий: помощник базового класса в `tests/<модуль>.py` потерял
        утверждение; файл `tests/test_<x>.py` с наследником, зовущим
        помощника, в ветке не меняется — его метод попадает в изменённые с
        одинаковыми текстами файла. Рядом в файле фикстуры сменён литерал
        `test_value` — его наблюдение идёт. Ни один запуск pytest по узлу
        не называет путь вызывающего файла; запись наблюдения о
        `test_value` есть.

        Ловит мутацию: отбор `base_source != head_source` снят — pytest по
        узлу вызывающего файла запускается.
        """
        mod = f"helpers_{word(self.rng)}"
        base_cls = f"Base{word(self.rng).capitalize()}Test"
        caller_path = f"tests/test_caller_{word(self.rng)}.py"
        caller_cls = f"Caller{word(self.rng).capitalize()}Test"
        k = self.rng.randrange(10, 99)
        caller = (f"import unittest\n\nfrom tests.{mod} import {base_cls}\n\n\n"
                  f"class {caller_cls}({base_cls}):\n\n"
                  f"    def test_call(self):\n"
                  f'        """Фикстура.\n\n        Ловит мутацию: фикстура.\n        """\n'
                  f"        self.check({k})\n")

        def helper(body: str) -> str:
            return (f"import unittest\n\n\nclass {base_cls}(unittest.TestCase):\n\n"
                    f"    def check(self, value):\n{body}")

        base, head = self.undeclared_files()
        base.update({f"tests/{mod}.py": helper(
            f"        self.assertEqual(value, {k})\n        self.assertTrue(value)\n"),
            caller_path: caller})
        head[f"tests/{mod}.py"] = helper("        self.assertTrue(value)\n")
        self.scenario(base, head, None)
        with self.observation_on(), self.spawn_spy() as spy:
            out = self.advance()
        context = self.context(out, spy)
        self.assertTrue(self.observation_of("test_value"), context)
        runs = [argv for argv in spy.pytest_nodes()
                if any(caller_path in a for a in argv)]
        self.assertEqual(runs, [], context)

    def test_ac4_changed_lines_flag_per_side_with_shifted_lines(self):
        """Признак «в изменённых строках» по каждой стороне на фикстуре со сдвигом номеров строк: истинен у изменённого утверждения, ложен у неизменённого.

        Сценарий: в голове в начало файла добавлены строки-константы — все
        номера строк ниже сдвинуты. `test_hit` падает на обеих сторонах на
        своём `assertEqual`, чей литерал сменён; `test_miss` падает на обеих
        сторонах на неизменённом `assertEqual(app.OTHER, k)` (рядом сменён
        литерал другого утверждения). Признак `test_hit` — «да» у обеих
        сторон, `test_miss` — «нет» у обеих; место стороны — строка своей
        версии файла.

        Ловит мутацию: изменённые строки считаются позиционным сравнением
        файлов (со сдвигом всё ниже вставки «изменено») — `test_miss` даёт
        «да»; строка стороны «старая версия на ветке» сверяется с
        изменёнными строками head-версии (номера разошлись на сдвиг) —
        `test_hit` даёт «нет»; признак один на метод, не по сторонам.
        """
        old, new = self.two_values()
        k = self.rng.randrange(10, 99)
        pad = "".join(f"PAD_{i} = {i}\n" for i in range(self.rng.randrange(3, 9)))

        def files(value: int, header: str) -> dict:
            return {"app.py": f"VALUE = {value}\nOTHER = {k + 1}\n",
                    self.path: fixture_source(self.cls, {
                        "test_hit": ["value = app.VALUE",
                                     f"self.assertEqual(value, {value})"],
                        "test_miss": [f"self.assertEqual(app.OTHER, {k})",
                                      f"self.assertEqual(app.VALUE + 0, {value})"]},
                        header)}

        base, head = files(old, ""), files(new, pad)
        self.scenario(base, head, None)
        with self.observation_on():
            out = self.advance()
        context = self.context(out)
        expected = {
            ("test_hit", NEW_ON_BASE): ("yes", head, f"assertEqual(value, {new})"),
            ("test_hit", OLD_ON_BRANCH): ("yes", base, f"assertEqual(value, {old})"),
            ("test_miss", NEW_ON_BASE): ("no", head, f"assertEqual(app.OTHER, {k})"),
            ("test_miss", OLD_ON_BRANCH): ("no", base, f"assertEqual(app.OTHER, {k})"),
        }
        for (method, side), (flag, files_, needle) in expected.items():
            text = self.observation_of(method)
            part = side_part(text, side)
            line = line_of(files_[self.path], needle)
            with self.subTest(method=method, side=side):
                self.assertTrue(text, context)
                self.assertTrue(has_location(part, self.path, line),
                                self.note(f"{method} / {side}: нет места "
                                          f"{self.path}:{line}: {text}"))
                self.assertEqual(flag_of(part), flag,
                                 self.note(f"{method} / {side}: {text}"))


# ---------------------------------------------------------------------------
# AC-5, AC-6: сбой наблюдения и повтор на том же sha.

class ObservationFailureTest(ObservationSandbox):

    def mandate_covered(self) -> None:
        """Смена литерала вне раздела, покрытая мандатом на метод: переход
        проходит, объявленного прогона нет — все запуски pytest по узлу
        принадлежат наблюдению."""
        base, head = self.undeclared_files()
        self.scenario(base, head, None, elements=self.full("test_value"))

    def test_ac5_observation_failure_journals_reason_and_keeps_transition(self):
        """Таймаут pytest, исключение запуска и сбой `git worktree add` при наблюдении — запись с причиной, переход проходит как без наблюдения.

        Сценарий: смена вне раздела покрыта мандатом (без наблюдения
        переход проходит в `verifying`). Три прогона рубежа на трёх
        головах: (1) запуск pytest по узлу зависает — любое ожидание с
        таймаутом истекает; (2) запуск pytest по узлу бросает исключение
        со случайной меткой; (3) `git worktree add` завершается кодом 128
        со случайной меткой в stderr. Каждый раз — `verifying`, записи
        отказа нет, новая запись наблюдения о методе называет причину
        (таймаут; метка или класс исключения; метка или git).

        Ловит мутацию: исключение/таймаут наблюдения не перехвачены —
        `advance` падает или переход отклонён; сбой наблюдения превращён в
        отказ гейта (fail-closed); сбой молча проглочен без записи.
        """
        self.mandate_covered()
        token = f"метка-{word(self.rng)}"

        def boom(args, *a, **k):
            raise RuntimeError(token)

        failing = [sys.executable, "-c",
                   f"import sys; sys.stderr.write({token!r}); sys.exit(128)"]
        modes = (
            ("таймаут", timeout_rule, re.compile(r"таймаут|timeout", re.I)),
            ("исключение", lambda argv: boom if is_pytest_node(argv) else None,
             re.compile(rf"{re.escape(token)}|RuntimeError")),
            ("git", lambda argv: (lambda args, *a, **k: REAL_POPEN(failing, *a, **k))
             if is_worktree_add(argv) else None,
             re.compile(rf"{re.escape(token)}|git|worktree", re.I)),
        )
        for index, (label, rule, reason) in enumerate(modes):
            if index:
                self.reset_in_dev()
                self.move_head()
            before = len(self.observations())
            with self.observation_on(), self.spawn_spy(rule) as spy:
                try:
                    out = self.advance()
                except Exception as exc:  # noqa: BLE001 — предмет: наблюдение не роняет переход
                    out = f"исключение: {exc!r}"
            context = self.context(f"[{label}] {out}", spy)
            with self.subTest(mode=label):
                self.assertEqual(self.state(), "verifying", context)
                self.assertEqual(self.refusal(), "", context)
                fresh = "\n".join(self.observations()[before:])
                self.assertIn(self.full("test_value"), fresh, context)
                self.assertRegex(fresh, reason, context)

    def test_ac6_repeat_advance_on_same_sha_does_not_observe_again(self):
        """Повторный `advance` на том же sha головы наблюдение не повторяет.

        Сценарий: смена вне раздела без мандата — переход отклонён, задача
        остаётся в `in_dev`. Первый `advance` на включённом флаге запускает
        pytest по узлу и пишет записи наблюдения; второй на том же sha —
        ни запуска pytest по узлу, ни `git worktree add`, число записей
        наблюдения прежнее.

        Ловит мутацию: основание «запись уже есть для этого sha» не
        проверяется — второй `advance` снова гоняет pytest и дописывает
        записи; проверка сверяет запись без sha головы и пропускает
        наблюдение и на новом sha (тогда первый прогон не пишет записей —
        тест краснеет на предпосылке).
        """
        base, head = self.undeclared_files()
        self.scenario(base, head, None)
        with self.observation_on(), self.spawn_spy() as spy:
            out = self.advance()
        context = self.context(out, spy)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertTrue(spy.pytest_nodes(), context)
        first = len(self.observations())
        self.assertGreater(first, 0, context)
        with self.observation_on(), self.spawn_spy() as spy:
            out = self.advance()
        context = self.context(out, spy)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertEqual(spy.pytest_nodes(), [], context)
        self.assertEqual(spy.worktree_adds(), [], context)
        self.assertEqual(len(self.observations()), first, context)


# ---------------------------------------------------------------------------
# AC-7, AC-8: вердикт гейта неизменен.

class VerdictUnchangedTest(ObservationSandbox):

    def off_then_on(self, read):
        """`read()` после `advance` без наблюдения и после `advance` на
        включённом флаге той же задачи (между ними — возврат в `in_dev`)."""
        out_off = self.advance()
        off = read()
        state_off = self.state()
        self.reset_in_dev()
        with self.observation_on():
            out_on = self.advance()
        on = read()
        return (off, state_off, out_off), (on, self.state(), out_on)

    def test_ac7_uncovered_finding_same_refusal_and_observation_recorded(self):
        """Сценарий `test_ac24_uncovered_finding_runs_nothing` на включённом флаге: тот же отказ, тот же текст, `in_dev`, запись наблюдения есть.

        Сценарий: объявленная смена `test_value` рядом со сменой литерала в
        необъявленном `test_other`. `advance` без наблюдения и затем на
        включённом флаге: оба раза `in_dev`, текст отказа совпадает,
        записи «двусторонний прогон пройден» нет, после второго есть
        запись наблюдения о `test_other`.

        Ловит мутацию: наблюдение дописывает свои строки в текст отказа
        или меняет ветвление (отказ пропал, задача ушла в `verifying`);
        наблюдение стоит после ветвления — при отказе записи нет.
        """
        old, new = self.two_values()
        base, head = self.value_change(old, new, old, new)
        base[self.path] += method_text("test_other", [f"self.assertEqual(abs({old}), {old})"])
        head[self.path] += method_text("test_other", [f"self.assertEqual(abs({new}), {new})"])
        self.scenario(base, head, [self.line("test_value", [(repr(old), repr(new))], 2)])
        (off, state_off, out_off), (on, state_on, out_on) = \
            self.off_then_on(self.refusal)
        context = self.context(f"{out_off}\n---\n{out_on}")
        self.assertEqual(state_off, "in_dev", context)
        self.assertIn(self.name("test_other"), off, context)
        self.assertEqual(state_on, "in_dev", context)
        self.assertEqual(on, off, context)
        self.assertEqual(self.details(PASSED_ACTION), [], context)
        self.assertTrue(self.observation_of("test_other"), context)

    def test_ac7_no_declaration_transition_passes(self):
        """Сценарий `test_ac24_no_declaration_runs_nothing` на включённом флаге: переход проходит.

        Сценарий: SPEC без раздела, в голове добавлено утверждение и сменён
        `app.py`. На включённом флаге `advance` доводит задачу до
        `verifying`, записи отказа нет.

        Ловит мутацию: наблюдение без записи объявления падает или
        возвращает отказ — задача остаётся в `in_dev`.
        """
        v = self.rng.randrange(10, 99)
        base = {"app.py": f"VALUE = {v}\n", self.path: fixture_source(self.cls, {
            "test_value": [f"self.assertEqual(app.VALUE, {v})"]})}
        head = {"app.py": f"VALUE = {v}\nEXTRA = 1\n",
                self.path: fixture_source(self.cls, {
                    "test_value": [f"self.assertEqual(app.VALUE, {v})",
                                   "self.assertEqual(app.EXTRA, 1)"]})}
        self.scenario(base, head, None)
        with self.observation_on():
            out = self.advance()
        context = self.context(out)
        self.assertEqual(self.state(), "verifying", context)
        self.assertEqual(self.refusal(), "", context)

    def test_ac7_declared_change_same_verdict_and_passed_record(self):
        """Объявленная смена на включённом флаге: тот же вердикт и та же запись «двусторонний прогон пройден», что без наблюдения.

        Сценарий: объявленная смена литерала, обе стороны падают на
        утверждении. `advance` без наблюдения — `verifying` и запись
        «пройден»; возврат в `in_dev`, `advance` на включённом флаге —
        `verifying`, новая запись «пройден» совпадает с первой, всего
        таких записей две (по одной на переход).

        Ловит мутацию: наблюдение пишет свою запись «двусторонний прогон
        пройден» (их три) или меняет её текст; результат наблюдения
        подменяет результат объявленного прогона.
        """
        self.declared_scenario()
        (off, state_off, out_off), (on, state_on, out_on) = \
            self.off_then_on(lambda: list(self.details(PASSED_ACTION)))
        context = self.context(f"{out_off}\n---\n{out_on}")
        self.assertEqual(state_off, "verifying", context)
        self.assertEqual(len(off), 1, context)
        self.assertEqual(state_on, "verifying", context)
        self.assertEqual(len(on), 2, context)
        self.assertEqual(on[1], off[0], context)
        self.assertTrue(self.observation_of("test_value"), context)

    def test_ac7_mandate_covered_finding_same_verdict(self):
        """Находка, покрытая мандатом, на включённом флаге: прежний вердикт — переход проходит, та же запись разрешения.

        Ловит мутацию: наблюдение отклоняет переход по своему итогу
        (например, по стороне, упавшей не на изменённой строке) — задача
        в `in_dev`; запись разрешения мандатом меняется.
        """
        base, head = self.undeclared_files()
        self.scenario(base, head, None, elements=self.full("test_value"))
        (off, state_off, out_off), (on, state_on, out_on) = \
            self.off_then_on(lambda: list(self.details(ALLOWED_ACTION)))
        context = self.context(f"{out_off}\n---\n{out_on}")
        self.assertEqual(state_off, "verifying", context)
        self.assertEqual(state_on, "verifying", context)
        self.assertEqual(len(on), 2, context)
        self.assertEqual(on[1], off[0], context)
        self.assertEqual(self.refusal(), "", context)

    def test_ac7_declared_run_refusal_same_with_observation(self):
        """Отказ объявленного двустороннего прогона (зелёная сторона; сбой `git worktree add`) на включённом флаге — тот же отказ, что без наблюдения.

        Сценарий: объявленная смена, но `app.VALUE` на ветке прежний —
        старая версия зелёная на ветке. `advance` без наблюдения и на
        включённом флаге: оба раза `in_dev`, тексты отказа равны. Затем на
        новой голове то же под подменой `git worktree add` (код 128,
        случайная метка в stderr): тексты отказа равны.

        Ловит мутацию: отказ объявленного прогона подменён итогом
        наблюдения или дополнен им; перехват исключений наблюдения
        охватывает объявленный прогон и превращает его сбой в проход.
        """
        self.declared_scenario(head_value=lambda old, new: old)
        (off, _s, out_off), (on, state_on, out_on) = self.off_then_on(self.refusal)
        context = self.context(f"{out_off}\n---\n{out_on}")
        self.assertIn(OLD_ON_BRANCH, off, context)
        self.assertEqual(state_on, "in_dev", context)
        self.assertEqual(on, off, context)

        self.move_head()
        token = f"отказ-дерева-{word(self.rng)}"
        failing = [sys.executable, "-c",
                   f"import sys; sys.stderr.write({token!r}); sys.exit(128)"]
        rule = (lambda argv: (lambda args, *a, **k: REAL_POPEN(failing, *a, **k))
                if is_worktree_add(argv) else None)
        with self.spawn_spy(rule):
            (off, _s, out_off), (on, state_on, out_on) = \
                self.off_then_on(self.refusal)
        context = self.context(f"{out_off}\n---\n{out_on}")
        self.assertIn(token, off, context)
        self.assertEqual(state_on, "in_dev", context)
        self.assertEqual(on, off, context)

    def test_ac7_gate_two_sided_exception_not_caught_by_observation(self):
        """Исключение объявленного `two_sided.run` гейта на включённом флаге ведёт себя так же, как без наблюдения; наблюдение своё записывает.

        Сценарий: объявленная смена; `two_sided.run` подменён функцией,
        бросающей `RuntimeError` со случайной меткой. Исход `advance`
        (класс и текст исключения, состояние задачи, текст отказа) без
        наблюдения и на включённом флаге совпадает; после второго есть
        запись наблюдения о методе.

        Ловит мутацию: перехват исключений наблюдения охватывает и вызов
        `two_sided.run` гейта — исключение проглочено, исход отличается;
        исключение наблюдения не перехвачено — записи наблюдения нет.
        """
        self.declared_scenario()
        token = f"сбой-прогона-{word(self.rng)}"

        def raiser(*args, **kwargs):
            raise RuntimeError(token)

        def outcome() -> tuple:
            try:
                out = self.advance()
                error = None
            except Exception as exc:  # noqa: BLE001 — предмет: исход исключения
                out, error = "", (type(exc).__name__, str(exc))
            return error, self.state(), self.refusal(), out

        with mock.patch.object(two_sided, "run", raiser):
            error_off, state_off, refusal_off, out_off = outcome()
            self.reset_in_dev()
            with self.observation_on():
                error_on, state_on, refusal_on, out_on = outcome()
        context = self.context(f"{out_off}\n---\n{out_on}")
        self.assertEqual((error_on, state_on, refusal_on),
                         (error_off, state_off, refusal_off), context)
        self.assertTrue(self.observation_of("test_value"), context)

    def test_ac8_observation_never_proves_method(self):
        """Наблюдение не пишет «двусторонний прогон пройден» и не меняет доказанность: строки ревью-пакета прежние, гейт мержа эскалирует метод без записи прогона.

        Сценарий: объявленная смена `test_value` (обе стороны упали бы на
        утверждении) рядом со сменой необъявленного `test_other` (обе его
        стороны падают на утверждении). Строки `review_lines` до перехода;
        `advance` на включённом флаге отклонён — записи «пройден» нет,
        записи наблюдения о методах есть, строки `review_lines` после
        перехода совпадают с прежними. Затем мандат на `test_other`: гейт
        мержа эскалирует, называя `test_value` с причиной «двусторонний
        прогон для текущей головы не записан».

        Ловит мутацию: зелёные по доказательству стороны наблюдения
        записываются как «двусторонний прогон пройден» — запись есть,
        ревью-пакет говорит «пройден», гейт мержа пропускает `test_value`.
        """
        old, new = self.two_values()
        base, head = self.value_change(old, new, old, new)
        base[self.path] += method_text("test_other", [f"self.assertEqual(app.VALUE + 1, {old + 1})"])
        head[self.path] += method_text("test_other", [f"self.assertEqual(app.VALUE + 1, {new + 1})"])
        self.scenario(base, head, [self.line("test_value", [(repr(old), repr(new))], 2)])

        def lines() -> list:
            found, _unobserved, _git = test_integrity.review_lines(
                store.db(), self.task_id, self.branch, self.artifact())
            return found

        before = lines()
        with self.observation_on():
            out = self.advance()
            after = lines()
        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertTrue(self.observation_of("test_value"), context)
        self.assertTrue(self.observation_of("test_other"), context)
        self.assertEqual(self.details(PASSED_ACTION), [], context)
        self.assertEqual(after, before, context)
        self.mandate(self.full("test_other"))
        last = self.steps()[-1][0]
        with self.observation_on():
            escalated = self.merge_gate()
        context = self.context(out)
        self.assertTrue(escalated, context)
        fresh = "\n".join(d for i, _a, d, _actor in self.steps() if i > last)
        self.assertIn(self.name("test_value"), fresh, context)
        self.assertIn(TWO_SIDED_MISSING, fresh, context)


# ---------------------------------------------------------------------------
# AC-9, AC-10: флаг, канарейка, предел времени.

class SwitchAndLimitTest(ObservationSandbox):

    def test_ac9_flag_enabled_in_config_source_and_disabled_in_sandbox(self):
        """Флаг наблюдения по исходнику `orchestrator/config.py` включён, в окружении тестов выключен.

        Ловит мутацию: боевое значение флага в исходнике `config` —
        `False` (наблюдение выключено в бою) — флаг не находится; песочница
        флаг не выключает — значение атрибута после импорта
        `tests/sandbox.py` не `False`.
        """
        flags = observation_flags()
        self.assertTrue(flags, self.note("флаг наблюдения не найден"))
        constants = config_source_constants()
        for flag in flags:
            self.assertIs(constants[flag], True, self.note(flag))
            self.assertIs(getattr(config, flag), False, self.note(flag))

    def test_ac9_disabled_flag_runs_nothing(self):
        """При выключенном флаге наблюдение не выполняется: ни запусков pytest по узлу, ни записей.

        Сценарий: смена вне раздела (отказ, объявленного прогона нет), флаг
        в положении окружения тестов — выключен.

        Ловит мутацию: флаг не проверяется — наблюдение гоняет pytest и
        пишет записи при выключенном флаге.
        """
        self.assertTrue(observation_flags(), self.note("флаг наблюдения не найден"))
        base, head = self.undeclared_files()
        self.scenario(base, head, None)
        with self.spawn_spy() as spy:
            out = self.advance()
        context = self.context(out, spy)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertEqual(spy.pytest_nodes(), [], context)
        self.assertEqual(self.observations(), [], context)

    def test_ac9_canary_task_is_not_observed(self):
        """Для задачи канарейки наблюдение на включённом флаге не выполняется.

        Ловит мутацию: наблюдение стоит до выхода гейта по `is_canary` —
        для канареечной задачи запускается pytest по узлу и пишутся записи.
        """
        base, head = self.undeclared_files()
        self.scenario(base, head, None)
        store.update_task(store.db(), self.task_id, is_canary=1)
        with self.observation_on(), self.spawn_spy() as spy:
            out = self.advance()
        context = self.context(out, spy)
        self.assertEqual(spy.pytest_nodes(), [], context)
        self.assertEqual(self.observations(), [], context)

    def test_ac10_side_timeout_is_min_of_two_sided_timeout_and_remaining_limit(self):
        """Таймаут стороны наблюдения — меньшее из `TWO_SIDED_PYTEST_TIMEOUT_SEC` и остатка предела.

        Сценарий: смена вне раздела (все запуски pytest по узлу —
        наблюдения). (1) `TWO_SIDED_PYTEST_TIMEOUT_SEC` = T (случайное, меньше
        предела по умолчанию): таймаут каждого ожидания запуска pytest по
        узлу не больше T, наибольший — T. (2) На новой голове предел
        (константы `config` со значением 600 по исходнику) = L, T = L + 100:
        каждый таймаут положителен и не больше L.

        Ловит мутацию: сторона наблюдения ждёт ровно
        `TWO_SIDED_PYTEST_TIMEOUT_SEC` без учёта остатка предела — во
        втором прогоне таймаут больше L; ждёт остаток предела без
        ограничения `TWO_SIDED_PYTEST_TIMEOUT_SEC` — в первом прогоне
        таймаут больше T.
        """
        limits = limit_names()
        base, head = self.undeclared_files()
        self.scenario(base, head, None)
        t = self.rng.randrange(45, 90)
        sink: list = []
        with self.observation_on(), \
                mock.patch.object(config, "TWO_SIDED_PYTEST_TIMEOUT_SEC", t), \
                self.spawn_spy(recording_rule(sink)) as spy:
            out = self.advance()
        context = self.note(f"T={t} таймауты={sink}\n{self.context(out, spy)}")
        waits = [s for s in sink if s is not None]
        self.assertTrue(waits, context)
        self.assertTrue(all(s <= t + 1e-6 for s in waits), context)
        self.assertGreaterEqual(max(waits), t - 1, context)

        self.move_head()
        limit = self.rng.randrange(20, 40)
        sink.clear()
        with contextlib.ExitStack() as stack:
            stack.enter_context(self.observation_on())
            for name in limits:
                stack.enter_context(mock.patch.object(config, name, limit))
            stack.enter_context(mock.patch.object(
                config, "TWO_SIDED_PYTEST_TIMEOUT_SEC", limit + 100))
            spy = stack.enter_context(self.spawn_spy(recording_rule(sink)))
            out = self.advance()
        context = self.note(f"L={limit} пределы={limits} таймауты={sink}\n"
                            f"{self.context(out, spy)}")
        waits = [s for s in sink if s is not None]
        self.assertTrue(waits, context)
        self.assertTrue(all(0 < s <= limit + 1e-6 for s in waits), context)

    def test_ac10_exhausted_limit_marks_methods_and_keeps_gate_timeout(self):
        """Исчерпанный предел: каждый метод записан «не прогнан: предел», объявленный прогон гейта ждёт `TWO_SIDED_PYTEST_TIMEOUT_SEC`.

        Сценарий: две объявленные смены (`test_value`, `test_more`), обе
        стороны падают на утверждении; предел (константы `config` со
        значением 600 по исходнику) — микросекунда, `TWO_SIDED_PYTEST_TIMEOUT_SEC`
        = T. Переход проходит; запуски pytest по узлу — только два
        запуска объявленного прогона, каждый с таймаутом T; записи
        наблюдения о каждом методе несут «не прогнан» и «предел».

        Ловит мутацию: исчерпание отмечено только у первого метода, а
        следующие прогоняются — запусков pytest больше двух; предел
        наблюдения применён и к объявленному прогону — его таймаут не T.
        """
        limits = limit_names()
        old, new = self.two_values()
        more_old, more_new = old + 1, new + 1
        base = {"app.py": f"VALUE = {old}\n", self.path: fixture_source(self.cls, {
            "test_value": [f"self.assertEqual(app.VALUE, {old})"],
            "test_more": [f"self.assertEqual(app.VALUE + 1, {more_old})"]})}
        head = {"app.py": f"VALUE = {new}\n", self.path: fixture_source(self.cls, {
            "test_value": [f"self.assertEqual(app.VALUE, {new})"],
            "test_more": [f"self.assertEqual(app.VALUE + 1, {more_new})"]})}
        self.scenario(base, head, [
            self.line("test_value", [(repr(old), repr(new))], 2),
            self.line("test_more", [(repr(more_old), repr(more_new))], 3)])
        t = self.rng.randrange(120, 240)
        sink: list = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(self.observation_on())
            for name in limits:
                stack.enter_context(mock.patch.object(config, name, 1e-6))
            stack.enter_context(mock.patch.object(
                config, "TWO_SIDED_PYTEST_TIMEOUT_SEC", t))
            spy = stack.enter_context(self.spawn_spy(recording_rule(sink)))
            out = self.advance()
        context = self.note(f"T={t} пределы={limits} таймауты={sink}\n"
                            f"{self.context(out, spy)}")
        self.assertEqual(self.state(), "verifying", context)
        self.assertEqual(len(spy.pytest_nodes()), 2, context)
        self.assertEqual([s for s in sink if s is not None], [t, t], context)
        for method in ("test_value", "test_more"):
            text = self.observation_of(method)
            with self.subTest(method=method):
                self.assertIn("не прогнан", text, context)
                self.assertIn("предел", text, context)


# ---------------------------------------------------------------------------
# AC-14: гейт мержа, ревью-пакет и общий вход наблюдение не выполняют.

class NoObservationElsewhereTest(ObservationSandbox):

    def test_ac14_merge_gate_review_and_uncovered_do_not_observe(self):
        """Гейт мержа, ревью-пакет и общий вход `uncovered` на включённом флаге наблюдение не выполняют.

        Сценарий: смена вне раздела в голове, `advance` не вызывался —
        записи наблюдения на этом sha нет. Под обёрткой запусков:
        `review.review_package`, `test_integrity.uncovered` и
        `merge_gate_escalates` (эскалирует). Ни запуска pytest по узлу, ни
        `git worktree add`, ни записи «двусторонний прогон (наблюдение)».

        Ловит мутацию: наблюдение вызвано из общего `_journal_pass`
        (его зовут гейт мержа и `uncovered`) или из `_evaluate` (его зовёт
        и ревью-пакет) — появляются запуски pytest и записи наблюдения.
        """
        base, head = self.undeclared_files()
        self.scenario(base, head, None)
        with self.observation_on(), self.spawn_spy() as spy:
            text = self.review_text()
            found, _git = test_integrity.uncovered(
                store.db(), self.task_id, self.branch, self.artifact())
            escalated = self.merge_gate()
        context = self.context(text, spy)
        self.assertTrue(found, context)
        self.assertTrue(escalated, context)
        self.assertEqual(spy.pytest_nodes(), [], context)
        self.assertEqual(spy.worktree_adds(), [], context)
        self.assertEqual(self.observations(), [], context)


# ---------------------------------------------------------------------------
# AC-13: сводка наблюдения в отчёте.

ROW_RE = re.compile(r"<tr\b.*?</tr>|<li\b.*?</li>|"
                    r"<div[^>]*class=\"[^\"]*metric-row[^\"]*\"[^>]*>.*?</div>",
                    re.S)


def report_rows(page: str) -> list:
    """Строки таблиц/списков отчёта — текстом без тегов."""
    rows = []
    for chunk in ROW_RE.findall(page):
        text = html.unescape(re.sub(r"<[^>]+>", " ", chunk))
        rows.append(" ".join(text.split()))
    return rows


def row_count(row: str):
    numbers = re.findall(r"(?<![\d.,])\d+(?![\d.,])", row)
    return int(numbers[-1]) if numbers else None


class ObservationSummaryTest(ObservationSandbox):

    def test_ac13_report_summary_groups_verdicts_by_class(self):
        """Сводка наблюдения в отчёте группирует текстовый вердикт по классам; «покрыто мандатом» старше прочих маркеров; нераспознанный — «прочее».

        Сценарий: в одном файле шесть изменённых методов, у каждого обе
        стороны падают на своём изменённом утверждении: две объявленные
        смены ожидания с разными номерами требований, объявленная смена,
        покрытая мандатом («смена ожидания по SPEC (требование N); покрыто
        мандатом ANSWER-1»), смена вне раздела, ослабление `assertEqual` →
        `assertTrue` и смена, не совпавшая с объявленной парой. `advance` на
        включённом флаге отклонён, записи наблюдения — по каждому методу.
        В журнал добавлена копия записи о смене вне раздела, где текст
        «смена вне раздела…» заменён случайным. `report.cmd_report`: строки
        с «смена ожидания по SPEC» (без «покрыто мандатом») есть и у
        каждой число 2; с «покрыто мандатом» — есть, число 1; «находка вне
        раздела», «ослабление», «несовпадение с объявленным», «прочее» —
        есть, число 1.

        Ловит мутацию: вердикт группируется полным текстом — две смены
        ожидания с разными номерами требований дают две строки по 1;
        классы проверяются в порядке «смена ожидания» раньше «покрыто
        мандатом» — покрытая смена уходит в класс смены ожидания (число 3,
        строки «покрыто мандатом» нет); нераспознанный текст отброшен или
        отнесён к классу по слову «находка» — строки «прочее» нет.
        """
        values = {}
        base_methods, head_methods = {}, {}
        for index, method in enumerate(("test_exp1", "test_exp2", "test_cov",
                                        "test_out", "test_weak", "test_mis")):
            old = self.rng.randrange(1000, 5000) + 10000 * index
            new = old + self.rng.randrange(1, 4000)
            values[method] = (old, new)
            attr = f"V{index}"
            base_methods[method] = [f"self.assertEqual(app.{attr}, {old})"]
            head_methods[method] = (["self.assertTrue(app.V4)"]
                                    if method == "test_weak" else
                                    [f"self.assertEqual(app.{attr}, {new})"])
        app_base = "".join(f"V{i} = {values[m][0]}\n" for i, m in enumerate(values))
        app_head = "".join(f"V{i} = {values[m][1]}\n" for i, m in enumerate(values))
        base = {"app.py": app_base, self.path: fixture_source(self.cls, base_methods)}
        head = {"app.py": app_head, self.path: fixture_source(self.cls, head_methods)}
        req = self.rng.sample(range(1, REQUIREMENTS + 1), 4)
        mis_old, mis_new = values["test_mis"]
        section = [
            self.line("test_exp1", [tuple(map(repr, values["test_exp1"]))], req[0]),
            self.line("test_exp2", [tuple(map(repr, values["test_exp2"]))], req[1]),
            self.line("test_cov", [tuple(map(repr, values["test_cov"]))], req[2]),
            self.line("test_mis", [(repr(mis_old), repr(mis_new + 1))], req[3]),
        ]
        self.scenario(base, head, section, elements=self.full("test_cov"))
        with self.observation_on():
            out = self.advance()
        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        fulls = [self.full(m) for m in values]
        own = [(detail, actor) for _id, act, detail, actor in self.steps()
               if act == OBS_ACTION and self.full("test_out") in detail
               and not any(f in detail for f in fulls if f != self.full("test_out"))]
        self.assertTrue(own, self.note(f"нет отдельной записи о test_out:\n{context}"))
        detail, actor = own[-1]
        self.assertIn(OUTSIDE, detail, context)
        # Копия — под другим именем метода: читатель, берущий одну запись на
        # адрес и sha, не сольёт её с исходной.
        ghost = detail.replace(OUTSIDE, f"загадка-{word(self.rng)}").replace(
            self.full("test_out"), self.full("test_ghost"))
        store.journal(store.db(), self.task_id, actor, OBS_ACTION, ghost)

        self.run_cmd(report.cmd_report)
        page = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
        rows = report_rows(page)
        context = self.note("строки отчёта:\n" + "\n".join(rows))

        def counts(predicate) -> list:
            return [row_count(r) for r in rows if predicate(r)]

        expectation = counts(lambda r: "смена ожидания по SPEC" in r
                             and "покрыто мандатом" not in r)
        self.assertTrue(expectation, context)
        self.assertEqual(set(expectation), {2}, context)
        for label in ("покрыто мандатом", "находка вне раздела", "ослабление",
                      "несовпадение с объявленным", "прочее"):
            found = counts(lambda r, label=label: label in r)
            with self.subTest(label=label):
                self.assertTrue(found, context)
                self.assertEqual(set(found), {1}, context)


if __name__ == "__main__":
    unittest.main()
