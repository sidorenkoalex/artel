"""Генератор справочника ядра: `scripts/core_reference.build` по набору текстов.

Группа: долгоживущий
Красен до реализации: модуля scripts/core_reference.py ещё нет — `from scripts import core_reference` в каждом тесте падает ImportError.

`build(sources, setting, sha, *, min_uses, generator_sha256)` — чистая
функция набора исходных текстов (путь → текст), настройки проекта (поле
`core_reference` записи `targets.yaml`: `modules`, `constants_module`,
`constants`), sha источника, порога использования и `generator_sha256`;
свойства проверяются модульно, без песочницы пульта.

Разметку строк справочника SPEC не фиксирует: тесты ищут запись по её
содержимому — сигнатуру сравнивают без учёта пробелов (форма «как в коде»
и форма `ast.unparse` дают одно и то же), остальное — подстроками строки
записи («одна строка на запись»).
"""
import ast
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

SHA = "0123456789abcdef0123456789abcdef01234567"
GEN_SHA = "a1" * 32


def generator():
    from scripts import core_reference
    return core_reference


def build(sources, setting, *, sha=SHA, min_uses=3, gen=GEN_SHA) -> str:
    return generator().build(sources, setting, sha, min_uses=min_uses,
                             generator_sha256=gen)


def squeeze(text: str) -> str:
    return "".join(text.split())


def signature_lines(text: str, signature: str) -> list:
    """Строки справочника, несущие сигнатуру (сравнение без пробелов)."""
    wanted = squeeze(signature)
    return [line for line in text.split("\n") if wanted in squeeze(line)]


def lines_with(text: str, *needles: str) -> list:
    return [line for line in text.split("\n")
            if all(needle in line for needle in needles)]


def numbers(text: str) -> set:
    return set(re.findall(r"\b\d+\b", text))


def attr_users(names, count: int, prefix: str) -> dict:
    """`count` файлов, обращающихся к `core.<имя>` без вызова."""
    body = "from lib import core\n" + "".join(f"core.{n}\n" for n in names)
    return {f"{prefix}/user{i}.py": body for i in range(count)}


LONG_DOC = ("Первая строка докстринга функции full длинная и "
            + "".join(chr(0x430 + i % 32) for i in range(120)))

CORE_FUNCTIONS = f'''"""Ядро фикстуры: первая строка модуля.

Вторая строка докстринга модуля сюда не попадает.
"""
import functools


def full(a: int, /, b: str = 'x', *args: int, c: float = 1.5, d=None, **kw: str) -> dict[str, int]:
    """{LONG_DOC}

    Вторая строка докстринга функции.
    """
    return {{}}


async def fetch_async(url: str, *, retries: int = 2) -> bytes:
    """Асинхронная выборка."""
    return b''


@functools.lru_cache(maxsize=None)
def memo(key: str) -> str:
    """Запоминает ключ."""
    return key


def twice(a: int) -> int:
    """Первое определение."""
    return a


def twice(b: str, c: str = 'y') -> str:
    """Второе определение."""
    return b
'''


class NoExecutionAndDeterminismTest(unittest.TestCase):
    """AC-1: код проекта не исполняется, генератор — только stdlib, выход детерминирован."""

    def test_ac1_project_code_is_not_executed(self):
        """Модуль, чей верхний уровень пишет файл, заводит каталог и падает, разобран без следа.

        Верхний уровень модуля настройки и файлов-пользователей пишет файл,
        заводит каталог, делит на ноль и зовёт `SystemExit`; справочник
        обязан собраться (запись функции модуля на месте), а ни файла, ни
        каталога на диске появиться не должно.

        Ловит мутацию: генератор вместо `ast.parse` исполняет модуль
        (`importlib`/`exec(compile(...))`) — на диске появится файл следа,
        либо сборку уронит `SystemExit`/`ZeroDivisionError`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.txt"
            trace_dir = Path(tmp) / "trace-dir"
            core = (
                '"""Модуль со следом на верхнем уровне."""\n'
                "import os\n"
                f"open({str(trace)!r}, 'w').write('след')\n"
                f"os.makedirs({str(trace_dir)!r})\n\n\n"
                "def traced(v: int) -> int:\n"
                '    """Функция модуля со следом."""\n'
                "    return v\n\n\n"
                "raise SystemExit(7)\n")
            user = ("from lib import core\n"
                    f"open({str(trace)!r}, 'a').write('пользователь')\n"
                    "core.traced(1)\n"
                    "1 / 0\n")
            sources = {"lib/core.py": core}
            sources.update({f"use/u{i}.py": user for i in range(3)})
            text = build(sources, {"modules": ["lib/core.py"]})
            self.assertFalse(trace.exists(), "генератор исполнил код проекта")
            self.assertFalse(trace_dir.exists(), "генератор исполнил код проекта")
        self.assertIn("Модуль со следом на верхнем уровне.", text)
        self.assertTrue(signature_lines(text, "traced(v: int) -> int"), text)

    def test_ac1_generator_imports_only_standard_library(self):
        """Все импорты файла генератора (проверка `ast`) — из стандартной библиотеки.

        Ловит мутацию: генератор берёт порог из пульта (`from orchestrator
        import config`) или помощник карты (`from scripts import
        codebase_map`) — импорт вне `sys.stdlib_module_names` назван в
        тексте провала.
        """
        path = Path(generator().__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        foreign = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tops = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    foreign.append(f"строка {node.lineno}: относительный импорт")
                    continue
                tops = [(node.module or "").split(".")[0]]
            else:
                continue
            foreign += [f"строка {node.lineno}: {top}" for top in tops
                        if top not in sys.stdlib_module_names]
        self.assertEqual([], foreign, "импорты генератора вне стандартной библиотеки")

    def test_ac1_output_is_identical_across_hash_seeds_and_key_order(self):
        """Два подпроцесса с разными `PYTHONHASHSEED` и порядком ключей дают один текст.

        Один и тот же по содержимому набор исходников подаётся в двух
        порядках вставки ключей (прямом и перемешанном случайным зерном) в
        отдельных процессах с разным `PYTHONHASHSEED`; выход сравнивается
        байт в байт.

        Ловит мутацию: файлы обходятся в порядке словаря `sources` или
        множества (`set`) без сортировки — у примеров вызова и подсчёта
        использования меняется порядок, тексты расходятся.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        sources = dict(ORDER_SOURCES)
        sources["conf/settings.py"] = CONSTANTS_SETTINGS
        items = sorted(sources.items())
        shuffled = items[:]
        rng.shuffle(shuffled)
        setting = {"modules": ["lib/core.py", "conf/settings.py"],
                   "constants_module": "conf/settings.py",
                   "constants": sorted(CONSTANT_NAMES)}
        driver = (
            "import importlib.util, json, sys\n"
            "spec = importlib.util.spec_from_file_location('cr_probe', sys.argv[1])\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "data = json.loads(sys.stdin.read())\n"
            "sources = {}\n"
            "for path, text in data['sources']:\n"
            "    sources[path] = text\n"
            "out = mod.build(sources, data['setting'], data['sha'],\n"
            "                min_uses=3, generator_sha256=data['gen'])\n"
            "sys.stdout.buffer.write(out.encode('utf-8'))\n")
        outputs = []
        for hash_seed, order in (("1", items), ("4242", shuffled)):
            payload = json.dumps({"sources": order, "setting": setting,
                                  "sha": SHA, "gen": GEN_SHA})
            env = dict(os.environ, PYTHONHASHSEED=hash_seed,
                       PYTHONDONTWRITEBYTECODE="1")
            res = subprocess.run(
                [sys.executable, "-c", driver, generator().__file__],
                input=payload.encode("utf-8"), capture_output=True, env=env,
                timeout=120)
            self.assertEqual(0, res.returncode, res.stderr.decode(errors="replace"))
            outputs.append(res.stdout)
        self.assertTrue(outputs[0], "справочник пуст")
        self.assertEqual(outputs[0], outputs[1], f"зерно: {seed}")


class UsageThresholdTest(unittest.TestCase):
    """AC-3: использование — число других файлов, порог — параметр `min_uses`."""

    def test_ac3_usage_is_counted_in_distinct_other_files(self):
        """Имя в `m` файлах входит, в `m-1` — нет, сколько бы обращений ни было.

        Порог `m` выбирается случайно; обращения к `core.<имя>` и
        `from lib.core import <имя>` раскиданы по файлам случайно (по
        1–4 на файл). `below` встречается в `m-1` файлах, но десятью
        обращениями в одном; `selfish` — в `m-1` других файлах и пять раз
        в собственном модуле той же формой `core.selfish`; `_secret` — в
        `m+2` файлах, но приватное.
        Затем порог `m-1` из параметра пропускает `below` и `selfish`.

        Ловит мутацию: подсчёт идёт по числу обращений, а не файлов
        (`below` войдёт при пороге `m`), собственный файл модуля входит в
        подсчёт (`selfish` войдёт при пороге `m`), фильтр ведущего `_` снят
        (`_secret` в тексте) или порог взят константой, а не параметром
        (`below` не войдёт при пороге `m-1`).
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        m = rng.randint(2, 6)
        names = ("exact", "below", "selfish", "_secret")
        core = '"""Модуль порога."""\nimport sys\n\n\n' + "".join(
            f'def {name}(v: int) -> int:\n    """Док {name}."""\n    return v\n\n\n'
            for name in names)
        core += ("def runner_loop() -> None:\n"
                 "    core = sys.modules[__name__]\n"
                 + "".join(f"    core.selfish({i})\n" for i in range(5)))
        sources = {"lib/core.py": core}

        def users(name: str, count: int, heavy: int = 0) -> None:
            for i in range(count):
                refs = heavy if (heavy and i == 0) else rng.randint(1, 4)
                if rng.random() < 0.5:
                    body = "from lib import core\n" + f"core.{name}\n" * refs
                else:
                    body = (f"from lib.core import {name}\n"
                            + f"x = {name}\n" * refs)
                sources[f"use/{name.strip('_')}_{i}.py"] = body

        users("exact", m)
        users("below", m - 1, heavy=10)
        users("selfish", m - 1)
        users("_secret", m + 2)
        setting = {"modules": ["lib/core.py"]}

        text = build(sources, setting, min_uses=m)
        context = f"зерно: {seed}, порог {m}\n{text}"
        self.assertTrue(signature_lines(text, "exact(v: int) -> int"), context)
        self.assertNotIn("below(", text, context)
        self.assertNotIn("selfish(", text, context)
        self.assertNotIn("_secret", text, context)

        lowered = build(sources, setting, min_uses=m - 1)
        context = f"зерно: {seed}, порог {m - 1}\n{lowered}"
        self.assertTrue(signature_lines(lowered, "below(v: int) -> int"), context)
        self.assertTrue(signature_lines(lowered, "selfish(v: int) -> int"), context)
        self.assertNotIn("_secret", lowered, context)


class FunctionRecordTest(unittest.TestCase):
    """AC-4: запись функции — модуль, сигнатура как в коде, первая строка docstring."""

    def setUp(self):
        sources = {"lib/core.py": CORE_FUNCTIONS}
        sources.update(attr_users(("full", "fetch_async", "memo", "twice"),
                                  3, "use"))
        self.text = build(sources, {"modules": ["lib/core.py"]})

    def test_ac4_module_path_and_first_docstring_line(self):
        """Раздел модуля несёт путь и первую строку docstring, вторую — нет.

        Ловит мутацию: в справочник уходит весь docstring модуля (строка
        «Вторая строка докстринга модуля» в тексте) или путь модуля
        потерян.
        """
        self.assertIn("lib/core.py", self.text)
        self.assertIn("Ядро фикстуры: первая строка модуля.", self.text)
        self.assertNotIn("Вторая строка докстринга модуля", self.text)

    def test_ac4_signature_as_in_code_with_truncated_first_docstring_line(self):
        """Сигнатура с `/`, умолчаниями, `*args`, `**kw`, аннотациями и возвратом — целиком.

        Первая строка docstring длиннее 100 символов: в записи — её начало
        с «…», не более 100 символов; вторая строка docstring не выводится.

        Ловит мутацию: сигнатура собрана из одних имён параметров (пропали
        аннотации, умолчания или `-> dict[str, int]`), docstring не обрезан
        (в тексте 101-й символ первой строки) или обрезан без «…».
        """
        rows = signature_lines(
            self.text, "full(a: int, /, b: str = 'x', *args: int, "
                       "c: float = 1.5, d=None, **kw: str) -> dict[str, int]")
        self.assertTrue(rows, self.text)
        self.assertIn(LONG_DOC[:99], rows[0])
        self.assertIn("…", rows[0])
        self.assertNotIn(LONG_DOC[:101], self.text)
        self.assertNotIn("Вторая строка докстринга функции", self.text)

    def test_ac4_async_and_decorated_functions_keep_their_signatures(self):
        """`async def` и функция под декоратором выводятся со своей сигнатурой и docstring.

        Ловит мутацию: обход берёт только `ast.FunctionDef` (запись
        `fetch_async` пропадёт) или сигнатура декорированной функции
        берётся из вызова декоратора (`maxsize=None` вместо `key: str`).
        """
        rows = signature_lines(self.text,
                               "fetch_async(url: str, *, retries: int = 2) -> bytes")
        self.assertTrue(rows, self.text)
        self.assertIn("Асинхронная выборка.", rows[0])
        rows = signature_lines(self.text, "memo(key: str) -> str")
        self.assertTrue(rows, self.text)
        self.assertIn("Запоминает ключ.", rows[0])

    def test_ac4_last_of_two_top_level_definitions_wins(self):
        """При двух определениях `twice` верхнего уровня в записи — второе.

        Ловит мутацию: словарь определений заполняется «первое не
        перезаписывать» (`setdefault`) — в тексте окажутся `twice(a: int)`
        и «Первое определение.».
        """
        rows = signature_lines(self.text, "twice(b: str, c: str = 'y') -> str")
        self.assertTrue(rows, self.text)
        self.assertIn("Второе определение.", rows[0])
        self.assertFalse(signature_lines(self.text, "twice(a: int)"), self.text)
        self.assertNotIn("Первое определение.", self.text)


class ClassRecordTest(unittest.TestCase):
    """AC-5: запись класса — имя, базовые классы, имена публичных методов."""

    def test_ac5_class_record_lists_bases_and_public_method_names_only(self):
        """Класс `Widget` одной строкой: базы и публичные методы, без сигнатур и docstring.

        `Gadget` используется в двух файлах (ниже порога), `_Inner` —
        приватный: обоих в справочнике нет.

        Ловит мутацию: в запись класса попадают сигнатуры методов
        (`speed`/`grace` в тексте), их docstring, приватные методы
        (`_hidden_step`, `__init__`), пропадают базовые классы или классы
        выводятся без порога использования (`Gadget` в тексте).
        """
        core = '''"""Модуль классов."""
import mixins


class Widget(BaseThing, mixins.Mixin):
    """Виджет фикстуры."""

    def __init__(self, size: int = 1):
        self.size = size

    def run_fast(self, speed: int = 3) -> None:
        """Метод бежит быстро."""

    def stop_now(self, grace: float = 0.5) -> None:
        """Метод останавливает."""

    def _hidden_step(self):
        pass


class Gadget:
    pass


class _Inner:
    pass
'''
        sources = {"lib/core.py": core}
        sources.update(attr_users(("Widget", "_Inner"), 3, "use"))
        sources.update(attr_users(("Gadget",), 2, "few"))
        text = build(sources, {"modules": ["lib/core.py"]})
        rows = lines_with(text, "Widget", "BaseThing")
        self.assertTrue(rows, text)
        row = rows[0]
        for name in ("Mixin", "run_fast", "stop_now"):
            self.assertIn(name, row, text)
        for name in ("_hidden_step", "__init__"):
            self.assertNotIn(name, row, text)
        for fragment in ("speed", "grace", "Метод бежит быстро", "Метод останавливает",
                         "Gadget", "_Inner"):
            self.assertNotIn(fragment, text)


ORDER_CORE = '''"""Модуль примеров."""


def ord_path(n: int = 0) -> int:
    """Порядок путей."""
    return n


def ord_case(n: int = 0) -> int:
    """Порядок регистра."""
    return n


def ord_line(n: int = 0) -> int:
    """Порядок строк."""
    return n


def pri_attr(n: int = 0) -> int:
    """Приоритет обращения через модуль."""
    return n


def pri_imp(n: int = 0) -> int:
    """Приоритет файла с импортом."""
    return n


def pri_self(n: int = 0) -> int:
    """Пример из самого модуля."""
    return n


def no_example(n: int = 0) -> int:
    """Без примера."""
    return n


def len_lim(s: str = '') -> str:
    """Предел длины примера."""
    return s


def own_calls() -> None:
    pri_attr(4003)
    pri_imp(5003)
    pri_self(6001)
'''

CALL_80 = "core.len_lim('" + "e" * 64 + "')"
CALL_81 = "core.len_lim('" + "f" * 65 + "')"
ORDER_SOURCES = {
    "lib/core.py": ORDER_CORE,
    "m/a-b.py": "from lib import core\ncore.ord_path(1001)\n",
    "m/a/b.py": "from lib import core\ncore.ord_path(1002)\n",
    "Q/x.py": "from lib import core\ncore.ord_case(2001)\n",
    "a/x.py": "from lib import core\ncore.ord_case(2002)\n",
    "n/one.py": "from lib import core\ncore.ord_line(3002)\ncore.ord_line(3001)\n",
    "a/imp.py": "from lib.core import pri_attr\npri_attr(4001)\n",
    "z/att.py": "from lib import core\ncore.pri_attr(4002)\n",
    "z/imp.py": "from lib.core import pri_imp\npri_imp(5001)\n",
    "a/plain.py": "pri_imp(5002)\npri_self(6002)\nno_example(7001)\n",
    "a/0.py": "from lib import core\ncore.len_lim(\n    'multi')\n",
    "a/1.py": "from lib import core\n" + CALL_81 + "\n",
    "a/2.py": "from lib import core\n" + CALL_80 + "\n",
    "a/3.py": "from lib import core\ncore.len_lim('late')\n",
}
ORDER_SOURCES.update(attr_users(
    ("ord_path", "ord_case", "ord_line", "pri_attr", "pri_imp", "pri_self",
     "no_example", "len_lim"), 3, "zz"))


class ExampleCallTest(unittest.TestCase):
    """AC-6: пример вызова — первый подходящий по приоритету и порядку «путь, строка»."""

    def setUp(self):
        self.assertEqual(80, len(CALL_80))
        self.assertEqual(81, len(CALL_81))
        self.text = build(ORDER_SOURCES, {"modules": ["lib/core.py"]})

    def test_ac6_first_by_codepoint_path_then_line(self):
        """Из вызовов `core.<имя>(` берётся первый по пути (посимвольно), затем по строке.

        `m/a-b.py` раньше `m/a/b.py` посимвольно (`-` < `/`), но позже по
        частям пути; `Q/x.py` раньше `a/x.py` по коду символа, но позже без
        учёта регистра; в одном файле строка 2 раньше строки 3.

        Ловит мутацию: файлы сортируются как `Path` по частям (пример
        `ord_path(1002)`), без учёта регистра (`ord_case(2002)`) или
        примеры внутри файла берутся по последней строке (`ord_line(3001)`).
        """
        for chosen, rejected in (("core.ord_path(1001)", "ord_path(1002)"),
                                 ("core.ord_case(2001)", "ord_case(2002)"),
                                 ("core.ord_line(3002)", "ord_line(3001)")):
            with self.subTest(chosen=chosen):
                self.assertIn(chosen, self.text)
                self.assertNotIn(rejected, self.text)

    def test_ac6_priority_module_attribute_then_importing_file_then_module(self):
        """Ступени: `core.<имя>(` → `<имя>(` в файле с импортом → `<имя>(` в самом модуле.

        Вызов `<имя>(` в файле без импорта имени из модуля примером не
        считается ни на какой ступени; без подходящего вызова примера нет.

        Ловит мутацию: ступени перепутаны или слиты в один поиск по
        порядку путей (`pri_attr(4001)` из `a/imp.py` раньше `z/att.py`),
        вызов в файле без импорта принят за пример (`pri_imp(5002)`,
        `pri_self(6002)`, `no_example(7001)`), ступень «сам модуль»
        пропущена (`pri_self(6001)` нет).
        """
        self.assertIn("core.pri_attr(4002)", self.text)
        for rejected in ("pri_attr(4001)", "pri_attr(4003)"):
            self.assertNotIn(rejected, self.text)
        self.assertIn("pri_imp(5001)", self.text)
        for rejected in ("pri_imp(5002)", "pri_imp(5003)"):
            self.assertNotIn(rejected, self.text)
        self.assertIn("pri_self(6001)", self.text)
        self.assertNotIn("pri_self(6002)", self.text)
        self.assertTrue(signature_lines(self.text, "no_example(n: int = 0) -> int"))
        self.assertNotIn("no_example(7001)", self.text)
        self.assertEqual(1, self.text.count("no_example("), self.text)

    def test_ac6_example_is_single_line_and_at_most_80_characters(self):
        """Многострочный вызов и вызов в 81 символ пропускаются, берётся вызов ровно в 80.

        Ловит мутацию: длина не проверяется (в тексте вызов из 81 символа),
        граница строгая `< 80` (вызов ровно в 80 потерян, взят
        `core.len_lim('late')`) или многострочный вызов взят первой
        строкой (`'multi'`).
        """
        self.assertIn(CALL_80, self.text)
        self.assertNotIn(CALL_81, self.text)
        self.assertNotIn("'multi'", self.text)
        self.assertNotIn("core.len_lim('late')", self.text)


LONG_VALUE = "[" + ", ".join(f"'k{i:03d}'" for i in range(120)) + "]"
LONG_NOTE = "Длинное пояснение без знаков конца предложения " + "".join(
    chr(0x430 + i % 32) for i in range(160))
CONSTANTS_SETTINGS = f'''"""Настройки фикстуры."""

# Предел числа повторов. Подробности ниже.
# Вторая строка блока.
RETRIES = 314159

# Версия 1.5 формата: подробности дальше
VERSION_NOTE = 'v271828'

# Точка с запятой; дальше хвост
SEMI = 'q223606'

# Блок над строкой не главнее
INLINE_WINS = 161803  # строковый комментарий главнее

SPACED = {{
    'alpha':     1,
    'beta':  2,
}}

# Комментарий отделён пустой строкой

DETACHED = 'q577215'

NO_COMMENT = 'q141421'

LONG_VALUE = {LONG_VALUE}

# {LONG_NOTE}
LONG_NOTE = 'q173205'

NOT_LISTED = 'q999111'
'''
CONSTANTS_CORE = '''"""Ядро с константой-двойником."""

RETRIES = 777777
ELSEWHERE = 'q888888'
'''
CONSTANT_NAMES = ("RETRIES", "VERSION_NOTE", "SEMI", "INLINE_WINS", "SPACED",
                  "DETACHED", "NO_COMMENT", "LONG_VALUE", "LONG_NOTE",
                  "ELSEWHERE", "MISSING_ONE")
CONSTANTS_SOURCES = {"conf/settings.py": CONSTANTS_SETTINGS,
                     "lib/core.py": CONSTANTS_CORE}


class ConstantsTest(unittest.TestCase):
    """AC-7: константы — перечень настройки из модуля констант, значение и пояснение."""

    def setUp(self):
        setting = {"modules": ["lib/core.py", "conf/settings.py"],
                   "constants_module": "conf/settings.py",
                   "constants": list(CONSTANT_NAMES)}
        self.text = build(dict(CONSTANTS_SOURCES), setting)

    def row(self, name: str, fragment: str) -> str:
        rows = lines_with(self.text, name, fragment)
        self.assertTrue(rows, f"нет строки {name} с «{fragment}»\n{self.text}")
        return rows[0]

    def test_ac7_value_is_one_line_with_collapsed_spaces_truncated_after_400(self):
        """Значение — одной строкой со схлопнутыми пробелами; длиннее 400 — обрезка с «…».

        Ловит мутацию: многострочное значение выводится как есть (строка
        `'alpha':     1` с пробелами в тексте), длинное не обрезается (в
        тексте 401-й символ значения) или обрезается без «…».
        """
        self.row("RETRIES", "314159")
        spaced = self.row("SPACED", "'alpha': 1")
        self.assertIn("'beta': 2", spaced)
        self.assertNotIn("'alpha':     1", self.text)
        long_row = self.row("LONG_VALUE", LONG_VALUE[:399])
        self.assertIn("…", long_row)
        self.assertNotIn(LONG_VALUE[:401], self.text)

    def test_ac7_explanation_inline_then_first_sentence_of_block_above(self):
        """Пояснение: комментарий в строке главнее блока; иначе первое предложение блока.

        Предложение кончается на `.`, `:` или `;` с пробелом за ним (точка
        в «1.5» без пробела предложение не кончает), не длиннее 160
        символов; блок, отделённый пустой строкой, и отсутствие комментария
        дают «без пояснения».

        Ловит мутацию: блок над строкой берётся раньше комментария в строке
        («Блок над строкой» в тексте), предложение режется по любой точке
        («Версия 1» без «1.5 формата») или не режется вовсе («Подробности
        ниже», «дальше хвост»), длина пояснения не ограничена (161-й символ
        в тексте), блок через пустую строку принят за пояснение.
        """
        self.row("RETRIES", "Предел числа повторов")
        self.assertNotIn("Подробности ниже", self.text)
        self.assertNotIn("Вторая строка блока", self.text)
        self.row("VERSION_NOTE", "Версия 1.5 формата")
        self.assertNotIn("подробности дальше", self.text)
        self.row("SEMI", "Точка с запятой")
        self.assertNotIn("дальше хвост", self.text)
        self.row("INLINE_WINS", "строковый комментарий главнее")
        self.assertNotIn("Блок над строкой", self.text)
        self.row("LONG_NOTE", LONG_NOTE[:159])
        self.assertNotIn(LONG_NOTE[:161], self.text)
        self.row("DETACHED", "без пояснения")
        self.assertNotIn("Комментарий отделён пустой строкой", self.text)
        self.row("NO_COMMENT", "без пояснения")

    def test_ac7_only_listed_names_and_only_from_constants_module(self):
        """Константа вне перечня не выводится; имя перечня вне модуля констант — «нет в коммите».

        Ловит мутацию: выводятся все присваивания модуля (`NOT_LISTED`,
        `q999111` в тексте), константы ищутся во всех модулях настройки
        (значение `777777` двойника `RETRIES` или `q888888` из `lib/core.py`
        в тексте) или ненайденное имя молча пропускается (нет «нет в
        коммите»).
        """
        self.assertNotIn("NOT_LISTED", self.text)
        self.assertNotIn("q999111", self.text)
        self.assertNotIn("777777", self.text)
        self.assertNotIn("q888888", self.text)
        self.row("MISSING_ONE", "нет в коммите")
        self.row("ELSEWHERE", "нет в коммите")


class RobustnessAndHeaderTest(unittest.TestCase):
    """AC-8: сбои разбора не роняют сборку, шапка, очистка управляющих символов."""

    def test_ac8_missing_or_broken_setting_module_keeps_other_sections(self):
        """Отсутствующий и неразбираемый модули настройки дают строку раздела, остальное строится.

        Ловит мутацию: отсутствующий модуль бросает `KeyError`, синтаксическая
        ошибка модуля настройки роняет сборку `SyntaxError`, или раздел
        такого модуля молча пропадает (путь только в шапке).
        """
        sources = {"lib/broken.py": "def broken(:\n",
                   "lib/core.py": '"""Живой модуль."""\n\n\n'
                                  "def alive(v: int) -> int:\n"
                                  '    """Живая функция."""\n    return v\n'}
        sources.update(attr_users(("alive",), 3, "use"))
        text = build(sources, {"modules": ["lib/absent.py", "lib/broken.py",
                                           "lib/core.py"]})
        self.assertTrue(signature_lines(text, "alive(v: int) -> int"), text)
        for path in ("lib/absent.py", "lib/broken.py"):
            with self.subTest(path=path):
                self.assertGreaterEqual(len(lines_with(text, path)), 2,
                                        f"нет раздела {path} с причиной\n{text}")

    def test_ac8_unparsable_files_do_not_count_and_are_counted_in_header(self):
        """Файлы с `SyntaxError`/`ValueError` вне подсчёта и посчитаны числом в шапке.

        `k` (случайное, не встречающееся числом в базовом тексте) файлов,
        обращающихся к `core.edge`, не разбираются: синтаксическая ошибка
        или одиночный суррогат в тексте (`ast.parse` бросает
        `UnicodeEncodeError` — подкласс `ValueError`). Двух разобранных
        пользователей `edge` ниже порога 3, поэтому `edge` в справочник не
        входит, а число `k` появляется в тексте.

        Ловит мутацию: неразобранный файл входит в подсчёт использования
        (по тексту регуляркой — `edge` войдёт), исключение разбора не
        поймано (сборка падает) или неразобранные не считаются (числа `k`
        в тексте нет).
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        core = ('"""Модуль края."""\n\n\n'
                'def edge(v: int) -> int:\n    """Край."""\n    return v\n')
        base = {"lib/core.py": core}
        base.update(attr_users(("edge",), 2, "use"))
        setting = {"modules": ["lib/core.py"]}
        baseline = build(dict(base), setting)
        k = rng.choice([n for n in range(11, 30) if str(n) not in numbers(baseline)])
        broken = dict(base)
        for i in range(k):
            if rng.random() < 0.5:
                broken[f"bad/s{i}.py"] = "from lib import core\ncore.edge\ndef (:\n"
            else:
                broken[f"bad/v{i}.py"] = "from lib import core\ncore.edge\nx = '\udcff'\n"
        text = build(broken, setting)
        context = f"зерно: {seed}, k={k}\n{text}"
        self.assertNotIn("edge(", text, context)
        self.assertIn(str(k), numbers(text), context)

    def test_ac8_recursion_and_memory_errors_do_not_break_the_build(self):
        """Файл с `RecursionError` разбора и файл с `MemoryError` сборку не роняют.

        `RecursionError` даёт сам разбор глубоко вложенного выражения;
        `MemoryError` воспроизводится подменой `ast.parse` для текста с
        меткой — иначе его не получить детерминированно.

        Ловит мутацию: обработчик разбора ловит только `SyntaxError`/
        `ValueError` — `RecursionError` или `MemoryError` уронит сборку.
        """
        core = ('"""Модуль глубины."""\n\n\n'
                'def deep(v: int) -> int:\n    """Глубина."""\n    return v\n')
        sources = {"lib/core.py": core,
                   "bad/recursion.py": "x = " + "1+" * 200000 + "1\n",
                   "bad/memory.py": "# provoke-memory-error\nx = 1\n"}
        sources.update(attr_users(("deep",), 3, "use"))
        real_parse = ast.parse

        def parse(source, *args, **kwargs):
            if isinstance(source, str) and "provoke-memory-error" in source:
                raise MemoryError("подмена теста")
            return real_parse(source, *args, **kwargs)

        with mock.patch.object(ast, "parse", parse):
            text = build(sources, {"modules": ["lib/core.py"]})
        self.assertTrue(signature_lines(text, "deep(v: int) -> int"), text)

    def test_ac8_header_names_source_setting_threshold_and_body_hash(self):
        """Шапка: `built_at_sha`, `generator_sha256`, настройка, порог, sha256 тела, строка роли.

        sha, `generator_sha256`, порог и имена настройки случайны на каждый
        запуск; sha256 тела ищется среди 64-значных шестнадцатеричных
        токенов текста как хэш его хвоста, начатого с какой-то строки.

        Ловит мутацию: шапка теряет поле (`built_at_sha`, значение sha,
        `generator_sha256`, модуль или имя константы, порог), sha256 считан
        не от тела (ни один хвост текста не совпадёт) или пропала строка
        для роли о рабочем каталоге.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        sha = "".join(rng.choice("0123456789abcdef") for _ in range(40))
        gen = "".join(rng.choice("0123456789abcdef") for _ in range(64))
        min_uses = rng.randint(4, 9)
        module = f"pkg{rng.randint(100, 999)}/mod{rng.randint(100, 999)}.py"
        const_module = f"cfg{rng.randint(100, 999)}/values.py"
        const_name = f"LIMIT_{rng.randint(1000, 9999)}"
        sources = {module: '"""Модуль шапки."""\n\n\ndef head(v: int) -> int:\n'
                           '    """Шапка."""\n    return v\n',
                   const_module: f'"""Значения."""\n\n{const_name} = 5  # предел\n'}
        setting = {"modules": [module, const_module],
                   "constants_module": const_module, "constants": [const_name]}
        text = build(sources, setting, sha=sha, min_uses=min_uses, gen=gen)
        context = f"зерно: {seed}\n{text}"
        for fragment in ("built_at_sha", sha, "generator_sha256", gen, module,
                         const_module, const_name, "CORE_REFERENCE_MIN_USES"):
            self.assertIn(fragment, text, context)
        self.assertTrue(any(str(min_uses) in line for line in
                            lines_with(text, "CORE_REFERENCE_MIN_USES")), context)
        self.assertIn("рабоч", text.lower(), context)
        lines = text.split("\n")
        digests = set()
        for i in range(len(lines)):
            tail = "\n".join(lines[i:])
            for variant in (tail, tail.rstrip("\n"), tail.rstrip("\n") + "\n"):
                digests.add(hashlib.sha256(variant.encode("utf-8")).hexdigest())
        tokens = set(re.findall(r"\b[0-9a-f]{64}\b", text)) - {gen}
        self.assertTrue(tokens & digests, f"нет sha256 тела в шапке\n{context}")

    def test_ac8_control_characters_from_code_become_spaces(self):
        """Символы категории Cc из docstring, комментариев и примеров заменены пробелом.

        В тексте справочника не остаётся ни одного символа Cc, кроме `\\n`;
        NEL (`\\x85`) в docstring строку не делит — продолжение первой
        строки на месте.

        Ловит мутацию: очистка не применена к docstring или комментарию
        константы (ESC/BEL в тексте) либо первая строка docstring берётся
        `splitlines()` (обрыв на NEL — «Гамма» потеряна).
        """
        core = ('"""Модуль\x07сигнала."""\n\n\n'
                "def ctl(v: str = '') -> str:\n"
                '    """Альфа\x1bБета\x85Гамма\x7f."""\n'
                "    return v\n")
        settings = ('"""Значения."""\n\n'
                    "CTL = 'знач\x1bение'  # пояс\x07нение\n")
        user = "from lib import core\ncore.ctl('пр\x1bимер')\n"
        sources = {"lib/core.py": core, "conf/settings.py": settings}
        sources.update({f"use/u{i}.py": user for i in range(3)})
        text = build(sources, {"modules": ["lib/core.py", "conf/settings.py"],
                               "constants_module": "conf/settings.py",
                               "constants": ["CTL"]})
        controls = sorted({repr(ch) for ch in text
                           if ch != "\n" and unicodedata.category(ch) == "Cc"})
        self.assertEqual([], controls, text)
        self.assertIn("Модуль сигнала.", text)
        self.assertIn("Альфа Бета Гамма", text)
        self.assertIn("пояс нение", text)


if __name__ == "__main__":
    unittest.main()
