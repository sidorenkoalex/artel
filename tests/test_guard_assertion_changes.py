"""Юнит-тесты различения смены ожидания и ослабления, строгости нового
ожидания и разбора раздела SPEC «Меняемое поведение» в `scripts/guard.py`
(SPEC 01M45FJD46BX45VHC36S4VS9QN, требования 1, 5, 6, 9) и разбора отчёта
двустороннего прогона (`advance_gates/two_sided.py`, требование 10).

Сценарии долгоживущих файлов задачи (`tests/test_01m45fjd46bx45vhc36s4vs9qn_*`)
держат прямые направления правил; здесь — обратные и отрицательные формы,
которых там нет: `assertNotAlmostEqual`, `assertNotIn`/`not in`,
`assertFalse` с порядком, вызовы `mock`, `match=` у `pytest.raises`,
сверка пар по типу, литерал с `;` внутри пары и шаблонная заглушка
раздела.
"""
import unittest

from orchestrator.advance_gates import two_sided
from scripts import guard

HEADER = "import unittest\nfrom unittest import mock\n\nimport app\nimport pytest\n"


def source(lines) -> str:
    body = "".join(f"        {line}\n" for line in lines)
    return f"{HEADER}\n\nclass C(unittest.TestCase):\n\n    def test_m(self):\n{body}"


def change(old: str, new: str) -> guard.AssertionChange:
    return guard.assertion_changes(source([old]), source([new]))["C::test_m"]


class StrictnessDirectionTest(unittest.TestCase):

    def assert_weak(self, old, new):
        found = change(old, new)
        self.assertEqual(guard.ASSERTION_CHANGE_EXPECTATION, found.kind, found)
        self.assertTrue(found.signs, found)

    def assert_tight(self, old, new):
        found = change(old, new)
        self.assertEqual(guard.ASSERTION_CHANGE_EXPECTATION, found.kind, found)
        self.assertEqual((), found.signs, found)

    def test_not_almost_equal_tolerance_is_inverted(self):
        """У `assertNotAlmostEqual` меньший `delta` и больший `places` — ослабление, обратное — нет.

        Ловит мутацию: направление допуска `assertNotAlmostEqual` не
        обращено (взято как у `assertAlmostEqual`) — уменьшенный `delta`
        проходит молча, а увеличенный становится находкой.
        """
        self.assert_weak("self.assertNotAlmostEqual(app.R, 0.5, delta=0.1)",
                         "self.assertNotAlmostEqual(app.R, 0.5, delta=0.01)")
        self.assert_tight("self.assertNotAlmostEqual(app.R, 0.5, delta=0.01)",
                          "self.assertNotAlmostEqual(app.R, 0.5, delta=0.1)")
        self.assert_weak("self.assertNotAlmostEqual(app.R, 0.5, places=3)",
                         "self.assertNotAlmostEqual(app.R, 0.5, places=5)")

    def test_not_in_superstring_is_weakening(self):
        """`assertNotIn`/`not in`: новая строка — надстрока прежней (ослабление), подстрока — ужесточение.

        Ловит мутацию: отрицание вхождения оценивается правилом прямого
        вхождения — надстрока проходит, а подстрока становится находкой.
        """
        self.assert_weak("self.assertNotIn('abc', app.T)",
                         "self.assertNotIn('abcdef', app.T)")
        self.assert_tight("self.assertNotIn('abcdef', app.T)",
                          "self.assertNotIn('abc', app.T)")
        self.assert_weak("assert 'abc' not in app.T",
                         "assert 'abcdef' not in app.T")

    def test_assert_false_flips_the_order_bound(self):
        """`assertFalse(x > c)` — это `x <= c`: граница сверху, рост `c` — ослабление.

        Ловит мутацию: отрицание `assertFalse` не обращает оператор
        порядка — рост верхней границы проходит как ужесточение.
        """
        self.assert_weak("self.assertFalse(app.C > 10)",
                         "self.assertFalse(app.C > 20)")
        self.assert_tight("self.assertFalse(app.C > 20)",
                          "self.assertFalse(app.C > 10)")
        self.assert_weak("assert not 10 < app.C", "assert not 20 < app.C")

    def test_constant_on_the_left_of_order_is_an_upper_bound(self):
        """`assertGreater(c, x)`: константа слева — верхняя граница `x`, её рост — ослабление.

        Ловит мутацию: сторона константы в сравнении порядка не
        учитывается — рост верхней границы принят за ужесточение.
        """
        self.assert_weak("self.assertGreater(10, app.C)",
                         "self.assertGreater(20, app.C)")
        self.assert_tight("self.assertLess(10, app.C)",
                          "self.assertLess(20, app.C)")

    def test_mock_call_arguments_and_raises_match(self):
        """Аргументы `assert_called_with` — равенство; `match=` у `pytest.raises` — регулярное выражение.

        Ловит мутацию: аргументы вызовов `mock` не названы позицией
        равенства — смена значения становится «правило не умеет оценить
        строгость»; `match=` не опознан — потеря якоря проходит молча.
        """
        self.assert_tight("app.f.assert_called_with(1, key='a')",
                          "app.f.assert_called_with(2, key='b')")
        self.assert_weak("with pytest.raises(ValueError, match='^bad$'):\n"
                         "            pass",
                         "with pytest.raises(ValueError, match='bad'):\n"
                         "            pass")

    def test_not_regex_change_is_unrated(self):
        """Любая смена регулярного выражения `assertNotRegex` — признак «правило не умеет оценить строгость».

        Ловит мутацию: `assertNotRegex` оценивается правилом
        `assertRegex` — добавленный якорь проходит как ужесточение.
        """
        found = change("self.assertNotRegex(app.T, 'abc')",
                       "self.assertNotRegex(app.T, '^abc')")
        self.assertTrue(any(guard.SIGN_UNRATED in s for s in found.signs),
                        found)

    def test_equality_inside_container_literal_is_rated(self):
        """Смена элемента списка в `assertEqual` — равенство, не находка строгости.

        Ловит мутацию: роль равенства ставится только константе прямо в
        аргументе — элемент списка уходит в «правило не умеет оценить».
        """
        self.assert_tight("self.assertEqual(app.L, [1, -2])",
                          "self.assertEqual(app.L, [1, -3])")


class PairKeysTest(unittest.TestCase):

    def test_declared_pairs_compare_by_type_and_value(self):
        """`1` и `1.0`, `True` и `1` — разные значения; нелитерал ни с чем не совпадает.

        Ловит мутацию: пары сравниваются по `==` без типа (`1 == 1.0 ==
        True`) — объявленная `1` совпадает с фактической `1.0`; нелитерал
        читается как строка — совпадает со строкой того же текста.
        """
        actual = guard.value_pair_keys([(1, 2.0)])
        self.assertEqual(actual, guard.literal_pair_keys([("1", "2.0")]))
        self.assertNotEqual(actual, guard.literal_pair_keys([("1", "2")]))
        self.assertNotEqual(guard.value_pair_keys([(True, 2)]),
                            guard.literal_pair_keys([("1", "2")]))
        self.assertIsNone(guard.literal_pair_keys([("x", "2")]))


SPEC = """---
task: T001
type: spec
author_role: analyst
status: ready
---

# SPEC

## Требования

1. Первое.
2. Второе.

## Меняемое поведение

{body}
"""


class SectionParsingTest(unittest.TestCase):

    def test_semicolon_inside_literal_is_part_of_the_pair(self):
        """Точка с запятой внутри литерала не делит пару.

        Ловит мутацию: пары делятся по `; ` текста строки — литерал
        `'a; b'` рвётся на две негодные «пары», строка становится
        нарушением.
        """
        body = "- `tests/test_x.py::C::test_m`: `'a; b'` → `'c'`; `1` → `2` (требование 2)"
        items, errors = guard.behavior_change_items(SPEC.format(body=body))
        self.assertEqual([], errors)
        self.assertEqual(((("'a; b'", "'c'"), ("1", "2"))), items[0].pairs)
        self.assertEqual(2, items[0].requirement)

    def test_template_placeholder_is_no_section(self):
        """Раздел с одной шаблонной заглушкой `<…>` — то же, что раздела нет.

        Ловит мутацию: заглушка шаблона SPEC разбирается как строки
        раздела — её образец строки становится нарушением формы на
        каждом SPEC, заведённом из шаблона.
        """
        body = ("<Необязательный раздел. Образец:\n"
                "- `tests/<путь>.py::<Класс>::<метод>`: `<было>` → `<стало>` "
                "(требование <N>)>")
        self.assertEqual(([], []), guard.behavior_change_items(SPEC.format(body=body)))

    def test_text_between_pairs_is_a_violation(self):
        """Текст вне обратных кавычек между парами — нарушение, называющее строку.

        Ловит мутацию: текст между парами молча отбрасывается — строка
        «`a` для всех случаев → `b`» проходит с искажённой парой.
        """
        body = "- `tests/test_x.py::C::test_m`: `1` для всех → `2` (требование 1)"
        _items, errors = guard.behavior_change_items(SPEC.format(body=body))
        self.assertEqual(1, len(errors), errors)
        self.assertIn("tests/test_x.py::C::test_m", errors[0])


class TwoSidedVerdictTest(unittest.TestCase):
    NODE = "tests/test_x.py::C::test_m"

    def record(self, when, outcome, **extra):
        return {"nodeid": self.NODE, "when": when, "outcome": outcome, **extra}

    def test_assertion_in_call_is_proof_and_set_up_is_not(self):
        """Провал call на `AssertionError` — доказательство; тот же класс внутри `setUp` — нет.

        Ловит мутацию: признак кадра `setUp` не проверяется — утверждение,
        упавшее в `setUp` unittest (фаза call у pytest), засчитано
        доказательством.
        """
        ok = [self.record("setup", "passed"),
              self.record("call", "failed", exception="AssertionError",
                          assertion=True, in_setup=False)]
        self.assertEqual("", two_sided._verdict(ok, self.NODE))
        in_setup = [self.record("call", "failed", exception="AssertionError",
                                assertion=True, in_setup=True)]
        self.assertIn("setUp", two_sided._verdict(in_setup, self.NODE))

    def test_skip_teardown_and_plugin_timeout_are_not_proof(self):
        """Пропуск, ошибка teardown и таймаут pytest-timeout — не доказательство.

        Ловит мутацию: смотрится только запись фазы call — пропуск
        (setup skipped) читается «узел зелёный»/«не найден», а таймаут
        pytest-timeout (`Failed`) засчитан как `pytest.fail` утверждения.
        """
        skipped = [self.record("setup", "skipped")]
        self.assertIn("пропуск", two_sided._verdict(skipped, self.NODE))
        timeout = [self.record("call", "failed", exception="Failed",
                               assertion=True, timeout=True, in_setup=False)]
        self.assertIn(two_sided.TIMEOUT, two_sided._verdict(timeout, self.NODE))
        teardown = [self.record("call", "passed"),
                    self.record("teardown", "failed", exception="OSError")]
        self.assertIn("teardown", two_sided._verdict(teardown, self.NODE))


if __name__ == "__main__":
    unittest.main()
