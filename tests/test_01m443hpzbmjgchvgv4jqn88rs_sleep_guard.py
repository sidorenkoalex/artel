"""Сторож: тесты `tests/` не подменяют `time.sleep` на весь процесс.

Группа: долгоживущий

Красен до реализации: в `tests/` ещё 32 глобальные подмены `time.sleep` (`mock.patch("time.sleep")`, `mock.patch.object(<модуль>.time, "sleep", …)`, кортежи и вспомогательные методы) — `test_ac1_tests_tree_has_no_global_sleep_patch` их перечисляет; остальные методы зелёные с рождения: они проверяют сам поиск на подставленных исходниках и на неизменном `tests/test_merge_gate_clock_isolation.py`.

Подмена `time.sleep` модуля `time` целиком ловит и паузы стандартной
библиотеки — `subprocess.Popen._wait` опрашивает живой дочерний процесс
паузами `time.sleep`: счётчик пауз теста и подменённые часы сдвигаются
случайно, на медленном раннере тест краснеет. Пауза подменяется там, где
её зовёт проверяемый код: ссылка модуля на `time` заменяется
объектом-заместителем, у которого подменён только `sleep`.

Поиск идёт по синтаксическому дереву исходника, а не по тексту: подменой
считается только код — аргументы вызова (в том числе вспомогательного
метода теста, `setattr`) и элементы кортежа/списка, — а строки
документации и комментарии подменой не считаются. Признаки:
- строковый аргумент или элемент вида `"time.sleep"` (и `"<путь>.time.sleep"`);
- пара соседних аргументов/элементов «ссылка на `time`, строка `"sleep"`»,
  где ссылка на `time` — имя `time` (или его псевдоним `import time as …`)
  либо атрибут `<что-угодно>.time`;
- именованные `target=`/`attribute="sleep"` той же подмены.

`tests/test_invariants.py` — защищённый путь: правка в нём приходит
приложением к PLAN, поэтому сторож дерева его не читает; то же свойство
для него держит тестовый метод внутри самого `tests/test_invariants.py`.
"""
import ast
import random
import re
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
EXCLUDED = {"test_invariants.py"}

_TARGET_STRING = re.compile(r"^(?:[A-Za-z_][\w.]*\.)?time\.sleep$")
_ATTR = "sl" + "eep"
_READ_ONLY_CALLS = {"getattr", "hasattr"}


def _time_aliases(tree: ast.AST) -> set[str]:
    names = {"time"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "time" and alias.asname:
                    names.add(alias.asname)
    return names


def _is_time_ref(node: ast.AST, aliases: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in aliases
    return isinstance(node, ast.Attribute) and node.attr == "time"


def _is_str(node: ast.AST, value: str | None = None) -> bool:
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    return value is None or node.value == value


def _sequence_findings(items: list, aliases: set[str]) -> list[tuple[int, str]]:
    found = []
    for i, item in enumerate(items):
        if _is_str(item) and _TARGET_STRING.match(item.value):
            found.append((item.lineno, f"строка цели {item.value!r}"))
        if (i + 1 < len(items) and _is_time_ref(item, aliases)
                and _is_str(items[i + 1], _ATTR)):
            found.append((items[i + 1].lineno,
                          f"атрибут {_ATTR!r} у {ast.unparse(item)}"))
    return found


def global_sleep_patches(source: str, path: str) -> list[str]:
    """Глобальные подмены `time.sleep` в исходнике: строки `путь:строка: признак`."""
    tree = ast.parse(source, filename=path)
    aliases = _time_aliases(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name)
                    and node.func.id in _READ_ONLY_CALLS):
                continue
            found += _sequence_findings(list(node.args), aliases)
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            for value in kw.values():
                if _is_str(value) and _TARGET_STRING.match(value.value):
                    found.append((value.lineno,
                                  f"строка цели {value.value!r}"))
            if ("target" in kw and "attribute" in kw
                    and _is_time_ref(kw["target"], aliases)
                    and _is_str(kw["attribute"], _ATTR)):
                found.append((kw["attribute"].lineno,
                              f"атрибут {_ATTR!r} у "
                              f"{ast.unparse(kw['target'])}"))
        elif isinstance(node, (ast.Tuple, ast.List)):
            found += _sequence_findings(list(node.elts), aliases)
    return [f"{path}:{line}: глобальная подмена time.{_ATTR} — {why}"
            for line, why in sorted(set(found))]


def scan_tests_tree(root: Path = TESTS_DIR,
                    excluded: set[str] = EXCLUDED) -> tuple[list[str], list[str]]:
    """(находки, просмотренные файлы) по всем `*.py` под `root`, кроме `excluded`."""
    findings, scanned = [], []
    for file in sorted(root.rglob("*.py")):
        if "__pycache__" in file.parts:
            continue
        rel = file.relative_to(root.parent).as_posix()
        if file.parent == root and file.name in excluded:
            continue
        scanned.append(rel)
        findings += global_sleep_patches(file.read_text(encoding="utf-8"), rel)
    return findings, scanned


def _ident(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                            for _ in range(rng.randint(3, 8)))


def _padding(rng: random.Random) -> list[str]:
    """Посторонние строки перед подменой: пустые, комментарии, присваивания."""
    out = []
    for _ in range(rng.randint(0, 12)):
        kind = rng.randrange(3)
        if kind == 0:
            out.append("")
        elif kind == 1:
            out.append(f"# {_ident(rng, 'note_')}")
        else:
            out.append(f"{_ident(rng, 'v_')} = {rng.randint(0, 999)}")
    return out


def _module(rng: random.Random, body: list[str], test_lines: list[str]):
    """Исходник модуля теста; возвращает (текст, номер первой строки тела теста)."""
    lines = ["import time", "import unittest", "from unittest import mock",
             f"from orchestrator import {body[0]}"]
    lines += _padding(rng)
    lines += ["", "", f"class {_ident(rng, 'Case')}(unittest.TestCase):", ""]
    lines += [f"    {ln}" if ln else "" for ln in body[1:]]
    lines += [f"    def test_{_ident(rng, '')}(self):"]
    lines += [f"        {ln}" for ln in _padding(rng) if ln]
    first = len(lines) + 1
    lines += [f"        {ln}" for ln in test_lines]
    return "\n".join(lines) + "\n", first


def _bad_sources(rng: random.Random) -> list[tuple[str, str, int]]:
    """(имя формы, исходник, строка подмены) — по исходнику на форму."""
    mod = _ident(rng, "mod_")
    fake = _ident(rng, "fake_")
    var = _ident(rng, "s_")
    helper = _ident(rng, "patch_")
    other = _ident(rng, "attr_")
    helper_def = [f"def {helper}(self, *patches):",
                  "    for target, attr, value in patches:",
                  "        p = mock.patch.object(target, attr, value)",
                  "        p.start()",
                  "        self.addCleanup(p.stop)", ""]
    cases = [
        ("mock.patch(\"time.sleep\")", [mod],
         [f"with mock.patch(\"time.sleep\") as {var}:",
          f"    {mod}.run()", f"{var}.assert_not_called()"]),
        ("mock.patch.object(time, \"sleep\", f)", [mod],
         [f"{fake} = []",
          f"with mock.patch.object(time, \"sleep\", {fake}.append):",
          f"    {mod}.run()", f"self.assertEqual({fake}, [])"]),
        ("mock.patch.object(mod.time, \"sleep\", f)", [mod],
         [f"{fake} = []",
          f"with mock.patch.object({mod}.time, \"sleep\", {fake}.append):",
          f"    {mod}.run()", f"self.assertEqual({fake}, [])"]),
        ("кортеж (mod.time, \"sleep\", f) вспомогательному методу",
         [mod] + helper_def,
         [f"{fake} = []",
          f"self.{helper}(({mod}.time, \"sleep\", {fake}.append), "
          f"({mod}, \"{other}\", None))",
          f"{mod}.run()", f"self.assertEqual({fake}, [])"]),
        ("кортеж (\"time.sleep\", f) в цикле mock.patch", [mod],
         [f"{fake} = []",
          f"for target, value in ((\"time.sleep\", {fake}.append),):",
          "    p = mock.patch(target, value)",
          "    p.start()", "    self.addCleanup(p.stop)",
          f"{mod}.run()", f"self.assertEqual({fake}, [])"]),
    ]
    out = []
    for name, body, test_lines in cases:
        source, first = _module(rng, body, test_lines)
        offset = next(i for i, ln in enumerate(test_lines)
                      if "\"time.sleep\"" in ln or ".time, \"sleep\"" in ln
                      or "(time, \"sleep\"" in ln)
        out.append((name, source, first + offset))
    return out


def _proxy_sources(rng: random.Random) -> list[str]:
    """Исходники, где подменён только `sleep` объекта-заместителя ссылки модуля на `time`."""
    mod = _ident(rng, "mod_")
    fake = _ident(rng, "fake_")
    proxy = _ident(rng, "clock_")
    variants = [
        [f"{fake} = []",
         f"{proxy} = mock.Mock(wraps=time)",
         f"{proxy}.sleep = {fake}.append",
         f"with mock.patch.object({mod}, \"time\", {proxy}):",
         f"    {mod}.run()", f"self.assertEqual({fake}, [])"],
        [f"{fake} = []",
         f"{proxy} = mock.Mock(wraps=time)",
         f"with mock.patch.object({mod}, \"time\", {proxy}), "
         f"mock.patch.object({proxy}, \"sleep\", {fake}.append):",
         f"    {mod}.run()", f"self.assertEqual({fake}, [])"],
        [f"{fake} = []",
         f"{proxy} = types.SimpleNamespace(sleep={fake}.append, "
         f"monotonic=time.monotonic, time=time.time)",
         f"with mock.patch.object({mod}, \"time\", {proxy}):",
         f"    {mod}.run()", f"self.assertEqual({fake}, [])"],
    ]
    return [_module(rng, [mod], v)[0] for v in variants]


def _doc_and_comment_source(rng: random.Random) -> str:
    """Исходник, где все три формы упомянуты только в строке документации и в комментариях."""
    mod = _ident(rng, "mod_")
    doc = [
        "\"\"\"Сценарий.",
        "",
        "Ловит мутацию: возвращена глобальная подмена",
        f"`mock.patch(\"time.sleep\")`, `mock.patch.object(time, \"sleep\", f)`",
        f"или `mock.patch.object({mod}.time, \"sleep\", f)`.",
        "\"\"\"",
        f"# было: mock.patch.object({mod}.time, \"sleep\", lambda _: None)",
        "# было: mock.patch(\"time.sleep\")",
        f"{mod}.run()",
    ]
    return _module(rng, [mod], doc)[0]


class SleepGuardTreeTest(unittest.TestCase):

    def test_ac1_tests_tree_has_no_global_sleep_patch(self):
        """Ни один файл `tests/` (кроме `tests/test_invariants.py`) не подменяет `time.sleep` на весь процесс.

        Сценарий: сторож разбирает каждый `*.py` под `tests/`; находок нет,
        а среди просмотренных — файлы, где подмены были до задачи (значит,
        поиск действительно их читал, а не прошёл мимо).

        Ловит мутацию: в `tests/test_main_ci_line.py` возвращена
        `mock.patch("time.sleep") as sleep`, либо в `tests/test_auto_cycle.py`
        — `self.patch_object(auto.time, "sleep", fake_sleep)`, либо в
        долгоживущем файле — кортеж `(runner.time, "sleep", …)`: список
        находок станет непустым с файлом и строкой.
        """
        findings, scanned = scan_tests_tree()
        for rel in ("tests/test_main_ci_line.py", "tests/test_merge_queue.py",
                    "tests/test_auto_cycle.py"):
            self.assertIn(rel, scanned)
        self.assertNotIn("tests/test_invariants.py", scanned)
        self.assertEqual(findings, [], "\n".join(findings))


class SleepGuardSearchTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def test_ac2_each_form_is_reported_with_file_and_line(self):
        """Сторож краснеет на каждой из форм подмены и называет файл и строку.

        Сценарий: на нескольких случайных исходниках (случайные имена
        модулей, переменных, вспомогательного метода, случайное число
        посторонних строк перед подменой) по одному на форму —
        `mock.patch("time.sleep")`, `mock.patch.object(time, "sleep", f)`,
        `mock.patch.object(mod.time, "sleep", f)`, кортеж «цель, атрибут,
        значение» вспомогательному методу и кортеж `("time.sleep", f)` в
        цикле `mock.patch` — сторож возвращает находку, начинающуюся с
        `<файл>:<строка подмены>:`.

        Ловит мутацию: поиск смотрит только на прямой вызов `mock.patch*`
        (без кортежей и вспомогательных методов) — форма кортежа
        пропадает из находок; либо номер строки берётся от начала
        вызова/инструкции, а не от места подмены — сообщение назовёт
        чужую строку.
        """
        for _ in range(5):
            path = f"tests/test_{_ident(self.rng, '')}.py"
            for name, source, line in _bad_sources(self.rng):
                with self.subTest(form=name, seed=self.seed):
                    findings = global_sleep_patches(source, path)
                    self.assertTrue(
                        any(f.startswith(f"{path}:{line}:") for f in findings),
                        f"зерно {self.seed}: форма {name} не найдена на "
                        f"строке {line}: {findings}\n{source}")

    def test_ac2_proxy_sleep_is_not_reported(self):
        """Подмена `sleep` объекта-заместителя, подставленного вместо ссылки модуля на `time`, сторожем не отвергается.

        Сценарий: на нескольких случайных исходниках модуль получает
        заместитель `time` (`mock.Mock(wraps=time)` с подменённым `sleep`,
        `mock.patch.object(<заместитель>, "sleep", f)`,
        `types.SimpleNamespace(sleep=f, …)`) — находок нет.

        Ловит мутацию: поиск считает подменой любую пару «объект,
        "sleep"» или любое `mock.patch.object(<модуль>, "time", …)` —
        законный приём исправленных тестов станет находкой.
        """
        for _ in range(5):
            path = f"tests/test_{_ident(self.rng, '')}.py"
            for source in _proxy_sources(self.rng):
                with self.subTest(seed=self.seed):
                    self.assertEqual(global_sleep_patches(source, path), [],
                                     f"зерно {self.seed}\n{source}")

    def test_ac3_docstring_and_comment_mentions_are_not_patches(self):
        """Форма подмены в строке документации и в комментарии подменой не считается.

        Сценарий: на нескольких случайных исходниках все три формы
        упомянуты только в строке документации теста и в комментариях,
        код теста паузу не подменяет — находок нет; настоящий
        `tests/test_merge_gate_clock_isolation.py`, где форма упомянута
        в строке документации, сторож тоже не отвергает.

        Ловит мутацию: поиск ведётся регулярным выражением по тексту
        файла (как `grep` сверки) — строка документации и комментарий
        дадут находки, а `tests/test_merge_gate_clock_isolation.py`
        будет отвергнут по строке документации.
        """
        for _ in range(5):
            source = _doc_and_comment_source(self.rng)
            self.assertIn("mock.patch(", source)
            with self.subTest(seed=self.seed):
                self.assertEqual(
                    global_sleep_patches(source, "tests/test_doc.py"), [],
                    f"зерно {self.seed}\n{source}")
        clock = TESTS_DIR / "test_merge_gate_clock_isolation.py"
        text = clock.read_text(encoding="utf-8")
        self.assertIn("mock.patch.object(time, \"sleep\"", text)
        self.assertEqual(global_sleep_patches(
            text, "tests/test_merge_gate_clock_isolation.py"), [])


if __name__ == "__main__":
    unittest.main()
