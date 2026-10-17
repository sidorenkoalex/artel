"""Пять утверждений целевого метода на месте и не ослаблены.

Группа: разовый
Зелёный с рождения: на main метод `SuiteRunProfileLimitTest::test_ac5_…` несёт все пять утверждений (:612, :617, :619, :620, :621-622) безусловно, а помощник `standalone` — регулярку `(?<![\\d.:])N(?![\\d.:])`; планка держит, что правка задачи их не удалит и не ослабит.

Утверждения ищутся разбором текста целевого файла
(`tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`) рабочей
копии кода; помощник `standalone`, на котором стоят :620 и :621-622,
сверяется с его определением на main исполнением на случайных строках.
"""
import ast
import importlib
import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutant  # noqa: E402

GUARDS = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
          ast.ExceptHandler)


def main_standalone(number: int, text: str) -> bool:
    """Определение помощника на main (`:119-120`)."""
    return re.search(rf"(?<![\d.:]){number}(?![\d.:])", text) is not None


class AssertionsKeptTest(unittest.TestCase):

    def setUp(self):
        path = _mutant.code_root() / _mutant.TARGET_REL
        self.source = path.read_text(encoding="utf-8")
        tree = ast.parse(self.source)
        cls = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                    and n.name == _mutant.TARGET_CLASS), None)
        self.assertIsNotNone(cls, f"класса {_mutant.TARGET_CLASS} нет")
        self.cls = cls
        self.method = next((n for n in cls.body
                            if isinstance(n, ast.FunctionDef)
                            and n.name == _mutant.TARGET_METHOD), None)
        self.assertIsNotNone(self.method, f"метода {_mutant.TARGET_METHOD} нет")
        self.parents = {}
        for node in ast.walk(self.method):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node

    def calls(self, name: str) -> list:
        """Безусловные вызовы `self.<name>(…)` метода: не под if/for/while/
        except."""
        found = []
        for node in ast.walk(self.method):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == name
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self" and node.args):
                continue
            up, guarded = self.parents.get(node), False
            while up is not None and up is not self.method:
                guarded = guarded or isinstance(up, GUARDS)
                up = self.parents.get(up)
            if not guarded:
                found.append(node)
        return found

    def assigned_text(self, name: str) -> str:
        return "\n".join(ast.unparse(n.value) for n in ast.walk(self.method)
                         if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == name
                                 for t in n.targets))

    def test_ac4_five_assertions_are_present_unconditionally(self):
        """Все пять утверждений метода стоят безусловно и не выключены.

        Сценарий: разбор метода целевого файла; в нём безусловно (не под
        if/for/while/except) стоят: `assertIn("запущен", …)` (:612);
        `assertTrue` над событиями «start» пробника (:617); `assertTrue` над
        строками «не уложился» (:619); `assertTrue` с `standalone` — N в
        строке (:620); `assertFalse` с `standalone` — значение config копии
        в строке (:621-622). Ни метод, ни класс не помечены пропуском, в
        методе нет `skipTest` и раннего `return`.

        Ловит мутацию: правка задачи удаляет утверждение :617 (старт
        пробника при подменённых часах «мешает») или прячет :621-622 под
        условие/`skipTest` — нужного вызова среди безусловных нет, метод
        красен.
        """
        def unparsed(name):
            return [ast.unparse(c.args[0]) for c in self.calls(name)]

        self.assertTrue(any(isinstance(c.args[0], ast.Constant)
                            and c.args[0].value == "запущен"
                            for c in self.calls("assertIn")),
                        "нет assertIn(\"запущен\", …) (:612)")
        trues = unparsed("assertTrue")
        self.assertTrue(any("events(" in t and "'start'" in t for t in trues),
                        f"нет assertTrue над событиями «start» (:617): {trues}")
        self.assertTrue(
            any("не уложился" in t
                or (t.isidentifier() and "не уложился" in self.assigned_text(t))
                for t in trues),
            f"нет assertTrue над строками «не уложился» (:619): {trues}")
        self.assertTrue(any("standalone(" in t for t in trues),
                        f"нет assertTrue со standalone — N в строке (:620): "
                        f"{trues}")
        falses = unparsed("assertFalse")
        self.assertTrue(any("standalone(" in t for t in falses),
                        f"нет assertFalse со standalone — значение config "
                        f"(:621-622): {falses}")
        for node in (self.method, self.cls):
            for deco in node.decorator_list:
                self.assertNotIn("skip", ast.unparse(deco),
                                 f"{node.name} помечен пропуском")
        self.assertFalse([n for n in ast.walk(self.method)
                          if isinstance(n, ast.Return)],
                         "в методе ранний return")
        self.assertNotIn("skipTest", ast.unparse(self.method),
                         "в методе skipTest")

    def test_ac4_standalone_helper_is_not_weakened(self):
        """Помощник `standalone` целевого файла судит как на main.

        Сценарий: на случайных числах и строках (зерно печатается) —
        число между буквами, в начале/конце, между цифрами, за точкой и
        двоеточием — `standalone` модуля даёт тот же ответ, что регулярка
        main `(?<![\\d.:])N(?![\\d.:])`.

        Ловит мутацию: «стабилизация» правкой утверждения вместо фикстуры —
        `standalone` требует небуквенных соседей (`\\b`), и `K60X` перестаёт
        считаться отдельно стоящим 60 — ответ расходится с main, метод
        красен.
        """
        root = str(_mutant.code_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        module = importlib.import_module(_mutant.TARGET_MODULE)
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        pads = ["", "K", "x", " ", "[", "]", "№", "1", "9", ".", ":", "-", "("]
        cases = [(60, "[01MK60X]"), (60, "160"), (60, "60.5"), (12, "в 12 с")]
        for _ in range(400):
            number = rng.choice([rng.randint(1, 99), 60])
            cases.append((number, rng.choice(pads) + rng.choice(pads)
                          + str(number) + rng.choice(pads) + rng.choice(pads)))
        for number, text in cases:
            self.assertEqual(module.standalone(number, text),
                             main_standalone(number, text),
                             f"standalone({number}, {text!r}) расходится с "
                             f"main; зерно: {seed}")


if __name__ == "__main__":
    unittest.main()
