"""Модуль пульта `orchestrator/test_lint.py` и параметр `lint_base` узла `guard.long_lived_errors_from_files`.

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/test_lint.py` нет — импорт падает (AC-1); у `guard.long_lived_errors_from_files` нет параметра `lint_base` и узел не зовёт линт — нарушений в выводе нет (AC-8).

Модульные тесты без песочницы: разбор — чистая функция текста, узел guard —
функция пар (метка, текст). Закреплённый набор образцов — дословно
`_RULE_CORPUS` приложения 1 SPEC задачи (тот же набор держит защищённый
`tests/test_invariants.py::DeterministicTestsLintTest::test_rule_corpus_is_frozen`).
Имена классов и методов, порядок методов и положение нарушения — от
`random`; зерно печатается и входит в текст провала.
"""
import ast
import importlib
import inspect
import keyword
import random
import sys
import unittest
from pathlib import Path

from scripts import guard

LETTERS = "abcdefghijklmnopqrstuvwxyz"
PROBE = "tests/test_probe.py"
SLEEP_HIT = "time.sleep с ненулевой паузой"

# Дословно `_RULE_CORPUS` приложения 1 SPEC (снят прогоном прежнего разбора).
RULE_CORPUS = {
    'sleep_attr': (
        'import time\n\nclass T:\n    def test_a(self):\n        time.sleep(1)\n',
        {'tests/test_probe.py::T::test_a': ['строка 5: time.sleep с ненулевой паузой']}),
    'sleep_from': (
        'from time import sleep\n\ndef helper():\n    sleep(0.5)\n',
        {'tests/test_probe.py::helper': ['строка 4: time.sleep с ненулевой паузой']}),
    'sleep_zero_clean': (
        'import time\n\nclass T:\n    def test_a(self):\n        time.sleep(0)\n',
        {}),
    'while_monotonic': (
        'import time\n\nclass T:\n    def test_a(self):\n        deadline = time.monotonic() + 5\n        while time.monotonic() < deadline:\n            pass\n',
        {'tests/test_probe.py::T::test_a': ['строка 6: цикл до срока по time.monotonic()/time.time()']}),
    'for_if_time': (
        'import time\n\nclass T:\n    def test_a(self):\n        for _ in range(10):\n            if time.time() > 3:\n                break\n',
        {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()']}),
    'from_monotonic': (
        'from time import monotonic\n\nclass T:\n    def test_a(self):\n        while monotonic() < 9:\n            pass\n',
        {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()']}),
    'targets_file': (
        'from pathlib import Path\n\nclass T:\n    def test_a(self):\n        Path(__file__).parent.parent / "targets.yaml"\n',
        {'tests/test_probe.py::T::test_a': ["строка 5: путь к живому файлу репозитория Path(__file__).parent.parent / 'targets.yaml'"]}),
    'roles_joinpath': (
        'from pathlib import Path\n\nclass T:\n    def test_a(self):\n        Path(__file__).resolve().parent.joinpath("roles.yaml")\n',
        {'tests/test_probe.py::T::test_a': ["строка 5: путь к живому файлу репозитория Path(__file__).resolve().parent.joinpath('roles.yaml')"]}),
    'model_sets_osjoin': (
        'import os\n\nclass T:\n    def test_a(self):\n        os.path.join(os.path.dirname(__file__), "model_sets.yaml")\n',
        {'tests/test_probe.py::T::test_a': ["строка 5: путь к живому файлу репозитория os.path.join(os.path.dirname(__file__), 'model_sets.yaml')"]}),
    'docs_dir': (
        'from pathlib import Path\nROOT = Path(__file__).parent.parent\n\nclass T:\n    def test_a(self):\n        ROOT / "docs" / "backlog.md"\n',
        {'tests/test_probe.py::T::test_a': ["строка 6: путь к живому файлу репозитория ROOT / 'docs' / 'backlog.md'", "строка 6: путь к живому файлу репозитория ROOT / 'docs'"]}),
    'module_live_name': (
        'from pathlib import Path\nTARGETS = Path(__file__).parent.parent / "targets.yaml"\n\nclass T:\n    def test_a(self):\n        TARGETS.read_text()\n',
        {'tests/test_probe.py::T::test_a': ['строка 6: имя модуля TARGETS — путь к живому файлу репозитория']}),
    'model_sets_rel': (
        'from pathlib import Path\nfrom orchestrator import config\n\nclass T:\n    def test_a(self):\n        Path(__file__).parent.parent / config.MODEL_SETS_REL\n',
        {'tests/test_probe.py::T::test_a': ['строка 6: путь к живому файлу репозитория Path(__file__).parent.parent / config.MODEL_SETS_REL']}),
    'sandbox_root_clean': (
        'from orchestrator import config\n\nclass T:\n    def test_a(self):\n        config.ROOT / "targets.yaml"\n',
        {}),
    'ns_clocks': (
        'import time\n\nclass T:\n    def test_a(self):\n        while time.monotonic_ns() < 9:\n            pass\n\n    def test_b(self):\n        while time.time_ns() < 9:\n            pass\n',
        {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()'], 'tests/test_probe.py::T::test_b': ['строка 9: цикл до срока по time.monotonic()/time.time()']}),
    'async_for': (
        'import time\n\nclass T:\n    async def test_a(self):\n        async for _ in g():\n            if time.time() > 3:\n                break\n',
        {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()']}),
    'sleep_false_kw': (
        'import time\n\nclass T:\n    def test_a(self):\n        time.sleep(False)\n\n    def test_b(self):\n        time.sleep(secs=0)\n',
        {'tests/test_probe.py::T::test_a': ['строка 5: time.sleep с ненулевой паузой']}),
}


def word(rng: random.Random, size: int = 7) -> str:
    while True:
        value = "".join(rng.choice(LETTERS) for _ in range(size))
        if not keyword.iskeyword(value):
            return value


def class_source(cls: str, methods: dict) -> str:
    """Модуль долгоживущей группы с классом `cls`; `methods` — имя ->
    тело (строки с отступом 8). У каждого метода заявка мутации."""
    lines = ['"""Фикстура узла guard.', "", "Группа: " + guard.GROUP_LONG_LIVED,
             '"""', "import time", "import unittest", "", "",
             f"class {cls}(unittest.TestCase):"]
    for name, body in methods.items():
        lines += ["", f"    def {name}(self):",
                  '        """Фикстурный метод.', "",
                  "        Ловит " + "мутацию: фикстура узла guard.",
                  '        """', body]
    return "\n".join(lines) + "\n"


def sleep_errors(errors: list) -> list:
    return [e for e in errors if SLEEP_HIT in e]


class TestLintModuleTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.lint = importlib.import_module("orchestrator.test_lint")

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def test_ac1_stdlib_only_names_present(self):
        """Модуль импортирует только стандартную библиотеку и несёт константы правил и обе функции.

        Сценарий: исходник `orchestrator.test_lint` разбирается `ast`;
        верхнее имя каждого `import`/`from … import` — модуль стандартной
        библиотеки (`sys.stdlib_module_names`), не `orchestrator`/`scripts`,
        относительных импортов нет. Константы `CLOCK_CALLS`, `LIVE_FILES`,
        `LIVE_FILE_CONFIG_ATTRS` — непустые, `findings` и
        `top_level_functions` — вызываемые.

        Ловит мутацию: модуль импортирует `orchestrator.config` (ради
        `MODEL_SETS_REL`) или `scripts.guard` — цикл импорта guard ↔
        orchestrator; константа осталась в классе теста и в модуле её нет.
        """
        tree = ast.parse(inspect.getsource(self.lint))
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tops = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    bad.append(f"строка {node.lineno}: относительный импорт")
                    continue
                tops = [(node.module or "").split(".")[0]]
            else:
                continue
            bad += [f"строка {node.lineno}: {top}" for top in tops
                    if top not in sys.stdlib_module_names]
        self.assertEqual([], bad, "импорт вне стандартной библиотеки")
        for name in ("CLOCK_CALLS", "LIVE_FILES", "LIVE_FILE_CONFIG_ATTRS"):
            with self.subTest(константа=name):
                self.assertTrue(getattr(self.lint, name, None),
                                f"константы {name} нет или она пуста")
        for name in ("findings", "top_level_functions"):
            with self.subTest(функция=name):
                self.assertTrue(callable(getattr(self.lint, name, None)),
                                f"функции {name} нет")

    def test_ac1_rule_corpus_gives_frozen_findings(self):
        """Каждый образец закреплённого набора даёт ровно закреплённый словарь находок; `findings("def (", …)` — `SyntaxError`.

        Сценарий: шестнадцать образцов `_RULE_CORPUS` приложения SPEC
        (порядок от зерна) разбираются `findings(source,
        "tests/test_probe.py")`; результат равен закреплённому словарю
        побайтно — ключи «файл::метод» и тексты «строка N: …», чистые
        образцы — пустой словарь. Исходник «def (» поднимает `SyntaxError`.

        Ловит мутацию: из правила выпало имя живого файла, `async for`,
        условие `if` в теле цикла, часы `*_ns`, `joinpath`/`os.path.join`
        или `from time import …`; `sleep(0)`/`sleep(secs=0)` стали
        нарушением, а `sleep(False)` — нет; `findings` глотает
        `SyntaxError` и возвращает пустой словарь.
        """
        names = list(RULE_CORPUS)
        self.rng.shuffle(names)
        for name in names:
            source, expected = RULE_CORPUS[name]
            with self.subTest(образец=name):
                self.assertEqual(expected, self.lint.findings(source, PROBE),
                                 self.note(name))
        with self.assertRaises(SyntaxError):
            self.lint.findings("def (", PROBE)

    def test_ac1_top_level_functions_names_methods_and_functions(self):
        """`top_level_functions` даёт «Класс::метод» методов классов и имена функций модуля верхнего уровня с их узлами.

        Сценарий: модуль из функций и классов со случайными именами (от
        зерна), у одного класса — вложенная функция в методе и вложенный
        класс; `top_level_functions(ast.parse(...))` — пары (имя, узел) в
        порядке исходника: функции модуля по имени, методы как
        «Класс::метод», узел — то самое определение (имя узла совпадает);
        вложенные функции и методы вложенного класса не перечислены.

        Ловит мутацию: методы перечислены без имени класса, асинхронные
        функции пропущены или в перечень попали вложенные определения —
        адреса находок расходятся с ключами перечня `_EXCEPTIONS`.
        """
        expected, lines = [], []
        for _ in range(self.rng.randrange(2, 5)):
            if self.rng.random() < 0.5:
                name = word(self.rng)
                kind = self.rng.choice(("def", "async def"))
                lines += [f"{kind} {name}():", "    def inner():", "        pass", ""]
                expected.append(name)
            else:
                cls = word(self.rng).capitalize()
                lines.append(f"class {cls}:")
                lines += ["    class Nested:", "        def hidden(self):",
                          "            pass"]
                for _ in range(self.rng.randrange(1, 4)):
                    method = word(self.rng)
                    kind = self.rng.choice(("def", "async def"))
                    lines += [f"    {kind} {method}(self):", "        pass"]
                    expected.append(f"{cls}::{method}")
                lines.append("")
        source = "\n".join(lines) + "\n"
        got = list(self.lint.top_level_functions(ast.parse(source)))
        self.assertEqual(expected, [name for name, _node in got],
                         self.note(source))
        for name, node in got:
            self.assertEqual(name.rsplit("::", 1)[-1], node.name, self.note(name))


class LintBaseParameterTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def errors(self, label: str, source: str, **kwargs) -> list:
        return sleep_errors(guard.long_lived_errors_from_files(
            [(label, source)], "01" + "A" * 24, **kwargs))

    def test_ac8_lint_base_parameter_default_none(self):
        """У `long_lived_errors_from_files` есть именованный параметр `lint_base` со значением по умолчанию `None`.

        Сценарий: сигнатура узла читается `inspect.signature`; параметр
        `lint_base` есть, он только именованный или
        позиционно-именованный, умолчание — `None`.

        Ловит мутацию: параметр назван иначе (`base`, `locked`) или его
        умолчание — пустой словарь, при котором вызывающие без базы гасят
        нарушения по пустой базе иначе, чем при `None`.
        """
        params = inspect.signature(guard.long_lived_errors_from_files).parameters
        self.assertIn("lint_base", params)
        self.assertIs(params["lint_base"].default, None)
        self.assertIn(params["lint_base"].kind,
                      (inspect.Parameter.KEYWORD_ONLY,
                       inspect.Parameter.POSITIONAL_OR_KEYWORD))

    def test_ac8_base_silences_only_unchanged_methods(self):
        """При `None` нарушения у всех методов; с базой — метод с тем же «Класс::метод» и одинаковым `ast.dump` молчит, изменённый нарушающий — отказ.

        Сценарий: долгоживущий файл (метка `tests/test_<имя>.py`, имена от
        зерна) с классом и тремя методами, каждый зовёт `time.sleep(1)`:
        `kept` неизменён против базы, `changed` в базе есть, но правкой
        изменён (другое тело, всё ещё со сном), `added` в базе нет. Порядок
        методов от зерна. Без `lint_base` (и с `lint_base=None`) ошибки сна
        называют все три метода; с базой `{метка: текст базы}` — ровно
        `changed` и `added`, `kept` — нет. Метод, сдвинутый вниз строкой
        выше (тот же узел, другие строки), тоже молчит.

        Ловит мутацию: гашение по одному имени «Класс::метод» без сравнения
        `ast.dump` — `changed` молчит; сравнение по тексту файла или номеру
        строки — `kept` после сдвига строк даёт ошибку; база берётся по
        чужой метке — молчания нет вовсе.
        """
        cls = word(self.rng).capitalize() + "Test"
        kept, changed, added = (word(self.rng) for _ in range(3))
        label = f"tests/test_{word(self.rng)}.py"
        base_methods = {kept: "        time.sleep(1)",
                        changed: "        time.sleep(1)"}
        head_methods = {kept: "        time.sleep(1)",
                        changed: "        value = 2\n        time.sleep(value)",
                        added: "        time.sleep(1)"}
        order = list(head_methods)
        self.rng.shuffle(order)
        base = class_source(cls, base_methods)
        head = class_source(cls, {name: head_methods[name] for name in order})
        head = head.replace("import unittest\n",
                            "import unittest\n" + "# сдвиг\n" * self.rng.randrange(1, 4))

        def named(errors):
            return {name for name in (kept, changed, added)
                    if any(f"{label}::{cls}::{name}: строка " in e for e in errors)}

        for kwargs in ({}, {"lint_base": None}):
            with self.subTest(вызов=str(kwargs)):
                self.assertEqual({kept, changed, added},
                                 named(self.errors(label, head, **kwargs)),
                                 self.note("без базы"))
        self.assertEqual({changed, added},
                         named(self.errors(label, head, lint_base={label: base})),
                         self.note(f"с базой:\n{head}"))

    def test_ac8_exceptions_list_not_read(self):
        """Метод, названный в перечне `_EXCEPTIONS` линта `tests/test_invariants.py`, гейтом не прощается.

        Сценарий: из `tests/test_invariants.py` (разбором `ast`, без
        импорта) берётся случайная (от зерна) запись перечня
        `DeterministicTestsLintTest._EXCEPTIONS` «файл::метод»; узлу
        передаётся файл с той же меткой, где под тем же именем —
        `time.sleep(1)`. Ошибка сна называет этот «файл::метод».

        Ловит мутацию: гейт фильтрует находки перечнем `_EXCEPTIONS`
        (импортом класса теста или копией перечня) — метод из перечня
        проходит без ошибки.
        """
        keys = self.exception_keys()
        self.assertTrue(keys, "перечень _EXCEPTIONS не найден")
        key = self.rng.choice(sorted(keys))
        label, _, qualname = key.partition("::")
        cls, _, method = qualname.rpartition("::")
        if cls:
            source = class_source(cls, {method: "        time.sleep(1)"})
        else:
            source = ('"""Фикстура узла guard.\n\nГруппа: '
                      + guard.GROUP_LONG_LIVED
                      + '\n"""\nimport time\n\n\ndef ' + method
                      + "():\n    time.sleep(1)\n")
        errors = self.errors(label, source)
        self.assertTrue(any(f"{key}: строка " in e for e in errors),
                        self.note(f"{key} прощён: {errors}"))

    @staticmethod
    def exception_keys() -> set:
        tree = ast.parse((Path(__file__).resolve().parent
                          / "test_invariants.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "DeterministicTestsLintTest":
                for item in node.body:
                    if (isinstance(item, ast.Assign) and any(
                            isinstance(target, ast.Name) and target.id == "_EXCEPTIONS"
                            for target in item.targets)
                            and isinstance(item.value, ast.Dict)):
                        return {ast.literal_eval(k) for k in item.value.keys}
        return set()


if __name__ == "__main__":
    unittest.main()
