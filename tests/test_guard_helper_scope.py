"""Юнит-тесты поиска помощников вне своего класса и своего модуля в
`scripts/guard.py` и покрытия находки мандатом на путь помощника в
`advance_gates/test_integrity.py` (SPEC 01M4G8N9KBTVNNT7YGZ59Q5WBF,
требования 1, 2, 4).

Долгоживущий файл задачи (`tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_*`)
держит сценарии гейта мержа в настоящем git; здесь — формы разбора и
границы, которых там нет: импорт модуля `from tests import sandbox`,
псевдоним импорта, базовый класс через два модуля, базовый класс своего
файла без модулей стороны, цикл наследования, функция чужого модуля
`tests/` (не песочницы), список ослабленных помощников и смешанная
находка под мандатом на путь помощника.
"""
import unittest

from orchestrator.advance_gates import test_integrity
from scripts import guard

SANDBOX = guard.SANDBOX_MODULE_PATH


def modules(files: dict) -> guard.TestModules:
    return guard.TestModules(files.get)


def assertions(source: str, files: dict, path="tests/test_x.py") -> dict:
    return guard.test_assertions(source, path, modules(files))


class SandboxFunctionFormsTest(unittest.TestCase):

    sandbox = ("def expect_ok(test, value):\n"
               "    test.assertEqual(value, 7)\n")

    def test_module_import_attribute_call_is_helper(self):
        """`from tests import sandbox` и `sandbox.<fn>(…)` — функция песочницы видна.

        Ловит мутацию: функции `tests/sandbox.py` ищутся только по голому
        имени из `from tests.sandbox import <fn>` — вызов через атрибут
        модуля утверждений не даёт, список метода пуст.
        """
        source = ("from tests import sandbox\n\n\n"
                  "class C:\n"
                  "    def test_m(self):\n"
                  "        sandbox.expect_ok(self, run())\n")
        found = assertions(source, {SANDBOX: self.sandbox})["C::test_m"]
        self.assertEqual(["test.assertEqual(value, 7)"],
                         [text for _key, text in found])

    def test_aliased_import_is_helper(self):
        """`from tests.sandbox import <fn> as <alias>` — вызов по псевдониму виден.

        Ловит мутацию: привязка импорта берёт `alias.name` вместо
        `alias.asname` — псевдоним не разрешается, список метода пуст.
        """
        source = ("from tests.sandbox import expect_ok as check\n\n\n"
                  "def test_m():\n"
                  "    check(None, run())\n")
        found = assertions(source, {SANDBOX: self.sandbox})["test_m"]
        self.assertEqual(1, len(found))

    def test_function_of_other_tests_module_is_not_helper(self):
        """Функция модуля `tests/`, отличного от песочницы, помощником не считается.

        Ловит мутацию: проверка пути модуля функции (`tests/sandbox.py`)
        снята — функция `tests/other.py` разворачивается в утверждения
        метода вне границ SPEC (требование 1 называет только песочницу).
        """
        source = ("from tests.other import expect_ok\n\n\n"
                  "def test_m():\n"
                  "    expect_ok(None, run())\n")
        found = assertions(source, {"tests/other.py": self.sandbox})["test_m"]
        self.assertEqual([], found)


class InheritanceChainTest(unittest.TestCase):

    def test_grand_base_in_third_module_is_found(self):
        """Помощник базового класса базового класса из третьего модуля виден.

        Ловит мутацию: обход базовых классов останавливается на первом
        уровне наследования — помощник прародителя не найден, список пуст.
        """
        files = {
            "tests/mid.py": ("from tests.top import Top\n\n\n"
                             "class Mid(Top):\n    pass\n"),
            "tests/top.py": ("class Top:\n"
                             "    def check(self, value):\n"
                             "        self.assertIn(value, (1, 2))\n"),
        }
        source = ("from tests.mid import Mid\n\n\n"
                  "class C(Mid):\n"
                  "    def test_m(self):\n"
                  "        self.check(run())\n")
        found = guard._assertion_records(source, "tests/test_x.py",
                                         modules(files))["C::test_m"]
        self.assertEqual([("Top.check", "tests/top.py")],
                         [origin for *_rest, origin in found])

    def test_same_file_base_class_without_modules(self):
        """Базовый класс своего файла виден и без модулей стороны.

        Ловит мутацию: обход базовых классов идёт только через модули
        стороны (`modules`) — вызов без них, как у прежних потребителей
        `test_assertions(source)`, теряет помощника базового класса.
        """
        source = ("class Base:\n"
                  "    def check(self, value):\n"
                  "        assert value\n\n\n"
                  "class C(Base):\n"
                  "    def test_m(self):\n"
                  "        self.check(run())\n")
        self.assertEqual(1, len(guard.test_assertions(source)["C::test_m"]))

    def test_inheritance_cycle_does_not_hang(self):
        """Цикл наследования между модулями обход не роняет и не зацикливает.

        Ловит мутацию: обход не помнит пройденные классы — рекурсия по
        циклу `A(B)`/`B(A)` падает `RecursionError`.
        """
        files = {
            "tests/a.py": "from tests.b import B\n\n\nclass A(B):\n    pass\n",
            "tests/b.py": "from tests.a import A\n\n\nclass B(A):\n    pass\n",
        }
        source = ("from tests.a import A\n\n\n"
                  "class C(A):\n"
                  "    def test_m(self):\n"
                  "        self.missing()\n")
        self.assertEqual([], assertions(source, files)["C::test_m"])


class WeakenedHelpersTest(unittest.TestCase):

    def test_lists_only_helpers_that_lost_an_assertion(self):
        """Список ослабленных помощников: потерявший утверждение и исчезнувший — да, нетронутый и усиленный — нет.

        Ловит мутацию: сравнивается число утверждений, а не мультимножество
        нормальных форм — замена утверждения другим списком не попадает;
        исчезнувший помощник не учитывается.
        """
        base = ("def same(t):\n    t.assertTrue(1)\n\n"
                "def swapped(t):\n    t.assertEqual(1, 2)\n\n"
                "def gone(t):\n    t.assertIsNone(t)\n\n"
                "class K:\n"
                "    def grown(self):\n        self.assertTrue(1)\n")
        head = ("def same(t):\n    t.assertTrue(1)\n\n"
                "def swapped(t):\n    t.assertTrue(2)\n\n"
                "class K:\n"
                "    def grown(self):\n"
                "        self.assertTrue(1)\n        self.assertTrue(2)\n")
        self.assertEqual({"swapped", "gone"},
                         guard.weakened_helpers(base, head))


class HelperMandateCoverageTest(unittest.TestCase):

    def test_helper_path_covers_only_pure_single_file_helper_change(self):
        """Путь помощника покрывает находку, только если все изменённые утверждения — из помощников этого файла.

        Ловит мутацию: путь помощника добавляется к элементам мандата при
        любом происхождении — смешанная находка (своё утверждение метода
        рядом с утверждением помощника) или помощники двух файлов
        снимаются мандатом на один файл помощника.
        """
        pure = (("Base.check", "tests/h.py"), ("Base.other", "tests/h.py"))
        mixed = (("Base.check", "tests/h.py"), None)
        two = (("Base.check", "tests/h.py"), ("fn", SANDBOX))
        self.assertEqual(("tests/h.py",), test_integrity._helper_paths(pure))
        self.assertEqual((), test_integrity._helper_paths(mixed))
        self.assertEqual((), test_integrity._helper_paths(two))
        finding = test_integrity.Finding(
            "tests/test_x.py", "C::test_m", "t", "",
            test_integrity._helper_paths(pure))
        self.assertIn("tests/h.py", finding.mandate_elements)

    def test_ratchet_decline_in_caller_covered_by_helper_path(self):
        """Убыль храповика у метода, потерявшего утверждения только в помощнике, покрывает мандат на путь помощника.

        Ловит мутацию: `_decline_source` не учитывает пути помощников —
        убыль в файле вызывающего остаётся непокрытой мандатом на файл
        помощника, и гейт отказывает храповиком после снятой находки.
        """
        decline = test_integrity._Decline(
            (1, 2), (1, 1), [("tests/test_x.py", "", ["C::test_m"])])
        mandate = {"tests/h.py": "ANSWER-1"}
        self.assertIsNone(test_integrity._decline_source(decline, mandate))
        self.assertEqual("ANSWER-1", test_integrity._decline_source(
            decline, mandate, {("tests/test_x.py", "C::test_m"):
                               ("tests/h.py",)}))


if __name__ == "__main__":
    unittest.main()
