"""Юнит-тесты ast-разбора тестов в `scripts/guard.py` (SPEC
01M3FQ2V77QNK95Z599DM124QN, требование 1): квалифицированные имена
тестовых методов (`qualified_test_methods`) и маркеры пропуска/ожидаемого
провала (`test_skip_markers`) — единственный адрес правила «что считается
тестовым методом» в пульте, которым живут ОБА гейта неослабления тестов.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402

TWO_CLASSES = '''import unittest


def test_module_level():
    assert True


class AlphaTest(unittest.TestCase):

    def test_same_name(self):
        pass

    def helper(self):
        pass


class BetaTest(unittest.TestCase):

    def test_same_name(self):
        pass
'''


class QualifiedTestMethodsTest(unittest.TestCase):

    def test_class_methods_carry_their_class_in_the_name(self):
        """Ловит мутацию: ключ собирается голым именем метода (как в
        `_collect_test_functions`) — одноимённые методы двух классов
        схлопываются в один, и исчезновение `AlphaTest::test_same_name`
        при живом `BetaTest::test_same_name` гейт не замечает вовсе."""
        names = set(guard.qualified_test_methods(TWO_CLASSES))
        self.assertEqual(
            {"test_module_level", "AlphaTest::test_same_name",
             "BetaTest::test_same_name"}, names)

    def test_non_test_methods_are_not_collected(self):
        """Ловит мутацию: в сбор попадает любой метод класса, не только
        `test_*` — переименование помощника начинает выглядеть потерей
        теста."""
        self.assertNotIn("AlphaTest::helper",
                         guard.qualified_test_methods(TWO_CLASSES))

    def test_unparseable_source_gives_empty_mapping(self):
        """Ловит мутацию: `SyntaxError` не перехвачен — гейт падает
        трейсбеком на файле с недописанным кодом вместо того, чтобы
        считать сведения об этой стороне отсутствующими."""
        self.assertEqual({}, guard.qualified_test_methods("def test_(:\n"))
        self.assertEqual({}, guard.qualified_test_methods(None))

    def test_bare_name_collector_stays_compatible(self):
        """Ловит мутацию: `_collect_test_functions`, выраженный через
        квалифицированный сборщик, начинает отдавать имена с `::` —
        гейт заявки мутации (`test_functions_without_mutation_claim`)
        печатал бы в detail `Class::test_x` вместо имени функции, а
        сравнение с base по ключу перестало бы совпадать."""
        import ast
        bare = guard._collect_test_functions(ast.parse(TWO_CLASSES))
        self.assertEqual({"test_module_level", "test_same_name"}, set(bare))


class SkipMarkersTest(unittest.TestCase):

    def test_decorator_on_method_is_found_with_its_dotted_name(self):
        """Ловит мутацию: распознаётся только голое `@skip` без разбора
        точечного имени — `@unittest.skipUnless(...)`, самый частый в
        этом репозитории вид условного пропуска, проходит мимо."""
        source = ('import unittest\n\n\n'
                  'class T(unittest.TestCase):\n\n'
                  '    @unittest.skipUnless(False, "нет окружения")\n'
                  '    def test_one(self):\n        pass\n')
        self.assertEqual({"T::test_one": {"@unittest.skipUnless"}},
                         guard.test_skip_markers(source))

    def test_decorator_on_class_is_attributed_to_the_class(self):
        """Ловит мутацию: осматриваются только узлы функций — один
        `@pytest.mark.xfail` над классом гасит весь файл тестов и
        остаётся незамеченным."""
        source = ('import pytest\nimport unittest\n\n\n'
                  '@pytest.mark.xfail(reason="пока не чиним")\n'
                  'class T(unittest.TestCase):\n\n'
                  '    def test_one(self):\n        pass\n')
        self.assertEqual({"T": {"@pytest.mark.xfail"}},
                         guard.test_skip_markers(source))

    def test_class_without_test_methods_is_not_reported(self):
        """Ловит мутацию: маркер собирается с ЛЮБОГО декорированного
        класса — `@pytest.mark.xfail` над классом-фикстурой без тестов
        начинает отказывать переходу, хотя ни один тест не выключен."""
        source = ('import pytest\n\n\n'
                  '@pytest.mark.xfail\nclass Fixture:\n\n'
                  '    def helper(self):\n        pass\n')
        self.assertEqual({}, guard.test_skip_markers(source))

    def test_skip_calls_in_the_body_are_found(self):
        """Ловит мутацию: осматривается только `decorator_list` — вызов
        `self.skipTest(`/`pytest.skip(` в теле остаётся законным
        способом выключить тест мимо рубежа."""
        source = ('import pytest\nimport unittest\n\n\n'
                  'class T(unittest.TestCase):\n\n'
                  '    def test_one(self):\n'
                  '        self.skipTest("окружение")\n\n'
                  '    def test_two(self):\n'
                  '        pytest.skip("окружение")\n')
        self.assertEqual({"T::test_one": {"self.skipTest("},
                         "T::test_two": {"pytest.skip("}},
                        guard.test_skip_markers(source))

    def test_ordinary_test_has_no_markers(self):
        """Ловит мутацию: в маркеры попадает любой декоратор (например
        `@mock.patch.object`) — каждая правка теста с моками начинает
        отказывать переходу на ровном месте."""
        source = ('from unittest import mock\n\n\n'
                  'class T:\n\n'
                  '    @mock.patch.object(object, "__doc__")\n'
                  '    def test_one(self, _patched):\n        pass\n')
        self.assertEqual({}, guard.test_skip_markers(source))


def _changed(base: str, head: str) -> dict:
    """Изменённые утверждения base -> head (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6,
    требование 3) — тем же путём, каким их видит гейт."""
    return guard.changed_test_assertions(guard.test_assertions(base),
                                         guard.test_assertions(head))


def _method(body: str, header: str = "import unittest\n") -> str:
    return (f"{header}\n\nclass T(unittest.TestCase):\n\n"
            f"    def test_x(self):\n{body}")


class ChangedAssertionsTest(unittest.TestCase):
    """Сравнение утверждений метода, сохранившего имя (SPEC
    01M3Y753QNG6TS5C7MTJS1MEV6, требования 1-3, тесты 10а-в)."""

    def test_removed_kind_and_argument_changes_are_findings(self):
        """Удалённый `assertIn`, `assertEqual` -> `assertTrue` и
        `self.pult_home` -> `self.clone_home` — каждое находка с исходным
        текстом утверждения base.

        Ловит мутацию: сравнение утверждений выключено или сравнивает
        только число утверждений."""
        removed = _changed(
            _method('        body = render()\n'
                    '        self.assertIn("ПУТИ", body)\n'
                    '        self.assertTrue(body)\n'),
            _method('        body = render()\n'
                    '        self.assertTrue(body)\n'))
        self.assertEqual({"T::test_x": ['self.assertIn("ПУТИ", body)']},
                         removed)
        kind = _changed(_method("        self.assertEqual(flag(), 1)\n"),
                        _method("        self.assertTrue(flag())\n"))
        self.assertEqual({"T::test_x": ["self.assertEqual(flag(), 1)"]}, kind)
        argument = _changed(
            _method('        self.assertIn(str(self.pult_home / "r"), d())\n'),
            _method('        self.assertIn(str(self.clone_home / "r"), d())\n'))
        self.assertEqual(
            {"T::test_x": ['self.assertIn(str(self.pult_home / "r"), d())']},
            argument)

    def test_neutral_edits_are_not_findings(self):
        """Добавление, перестановка, локальные имена, `msg=` и
        позиционное сообщение, корень импорта `fsm.` -> `ci_rerun.` —
        находок нет.

        Ловит мутацию: локальные имена, сообщение или корень импорта
        входят в ключ сравнения."""
        header = "import unittest\n\nfrom orchestrator import ci_rerun, fsm\n"
        base = _method(
            '        value = render()\n'
            '        self.assertIn("x", value)\n'
            '        self.assertEqual(size(), 3, msg="старое")\n'
            '        self.assertTrue(ready(), "старое")\n'
            '        assert size() == 3, "старое"\n'
            '        self.assertTrue(fsm._x(1))\n', header)
        head = _method(
            '        self.assertTrue(ci_rerun._x(1))\n'
            '        assert size() == 3, "новое"\n'
            '        self.assertTrue(ready(), "новое")\n'
            '        self.assertEqual(size(), 3, msg="новое")\n'
            '        other = render()\n'
            '        self.assertIn("x", other)\n'
            '        self.assertFalse(broken())\n', header)
        self.assertEqual({}, _changed(base, head))

    def test_first_level_helpers_are_unfolded(self):
        """Перенос утверждения в `self._helper(…)` — не находка; удаление
        утверждения из помощника — находка на вызывающем методе.

        Ловит мутацию: вспомогательные функции не разворачиваются."""
        inline = ("import unittest\n\n\nclass T(unittest.TestCase):\n\n"
                  "    def _helper(self, value):\n"
                  "        use(value)\n\n"
                  "    def test_x(self):\n"
                  "        result = compute()\n"
                  "        self.assertEqual(result, 1)\n"
                  "        self._helper(result)\n")
        moved = ("import unittest\n\n\nclass T(unittest.TestCase):\n\n"
                 "    def _helper(self, value):\n"
                 "        self.assertEqual(value, 1)\n\n"
                 "    def test_x(self):\n"
                 "        result = compute()\n"
                 "        self._helper(result)\n")
        self.assertEqual({}, _changed(inline, moved))
        self.assertEqual({}, _changed(moved, inline))
        emptied = moved.replace("self.assertEqual(value, 1)", "use(value)")
        self.assertEqual({"T::test_x": ["self.assertEqual(value, 1)"]},
                         _changed(moved, emptied))

    def test_unparseable_side_gives_none(self):
        """Неразбираемый текст — `None`, не пустой словарь и не исключение
        (требование 4: сравнивать не с чем, и гейт обязан это назвать).

        Ловит мутацию: `SyntaxError` не перехвачен либо неразбираемый
        текст читается как «утверждений нет» — голова сверяется с пустым,
        и каждое утверждение base становится ложной находкой."""
        self.assertIsNone(guard.test_assertions("def test_(:\n"))
        self.assertIsNone(guard.test_assertions(None))


if __name__ == "__main__":
    unittest.main()
