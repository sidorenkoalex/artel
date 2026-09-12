"""Юнит-тесты `scripts/guard.py::test_functions_without_mutation_claim`
(SPEC 01M29A0F88P9GKSXFW90F99H2N, требования 1-2, AC-1..AC-4).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402


class NewFunctionTest(unittest.TestCase):

    def test_new_module_level_function_without_claim_is_reported(self):
        """Ловит мутацию: условие «имени нет в base_source» заменено на
        «файл целиком новый» — новая функция в уже существующем файле
        (base_source не None, но без этого имени) молча пропускалась бы."""
        head = "def test_x():\n    pass\n"
        base = "def test_y():\n    pass\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim(base, head), ["test_x"])

    def test_new_file_base_none_without_claim_is_reported(self):
        """Ловит мутацию: `base_source is None` не трактуется как «файл
        добавлен» — первый тест совсем нового файла остался бы без
        проверки заявки."""
        head = "def test_x():\n    pass\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim(None, head), ["test_x"])

    def test_new_function_with_claim_is_not_reported(self):
        """Ловит мутацию: заявка в докстринге игнорируется — функция с
        валидной заявкой всё равно попадала бы в отказ."""
        head = 'def test_x():\n    """Ловит мутацию: срез off-by-one."""\n    pass\n'
        self.assertEqual(
            guard.test_functions_without_mutation_claim(None, head), [])


class ChangedFunctionTest(unittest.TestCase):

    def test_changed_function_body_without_claim_is_reported(self):
        """Ловит мутацию: сравнение текста сегмента функции убрано —
        изменённая функция (тело отличается от base) трактовалась бы как
        неизменённая и пропускала бы обязательную заявку."""
        base = "def test_x():\n    pass\n"
        head = "def test_x():\n    assert 1 == 1\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim(base, head), ["test_x"])

    def test_changed_function_with_claim_is_not_reported(self):
        base = "def test_x():\n    pass\n"
        head = ('def test_x():\n    """Ловит мутацию: неверное сравнение."""\n'
               "    assert 1 == 1\n")
        self.assertEqual(
            guard.test_functions_without_mutation_claim(base, head), [])

    def test_unchanged_function_without_claim_is_not_reported(self):
        """Ловит мутацию: старый тест без заявки (никогда не требовалось —
        задача правит только новые/изменённые) начинает отказывать —
        байт-в-байт совпадающий сегмент обязан считаться неизменённым."""
        source = "def test_x():\n    assert True\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim(source, source), [])

    def test_unrelated_whitespace_outside_function_does_not_count_as_change(self):
        """Ловит мутацию: сравнение по всему файлу целиком, не по сегменту
        функции — правка комментария файла ВЫШЕ функции ложно требовала
        бы заявку для теста, который сам не менялся."""
        base = "def test_x():\n    assert True\n"
        head = "# новый комментарий модуля\n\n\ndef test_x():\n    assert True\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim(base, head), [])


class EmptyClaimTextTest(unittest.TestCase):

    def test_claim_without_text_after_colon_is_reported(self):
        """Ловит мутацию: проверка `MUTATION_CLAIM` ослаблена до голого
        `"Ловит мутацию:"` без требования непустого текста — строка-маркер
        без объяснения засчитывалась бы как заполненная заявка."""
        head = 'def test_x():\n    """Ловит мутацию:"""\n    pass\n'
        self.assertEqual(
            guard.test_functions_without_mutation_claim(None, head), ["test_x"])

    def test_no_docstring_at_all_is_reported(self):
        head = "def test_x():\n    pass\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim(None, head), ["test_x"])


class MethodInsideClassTest(unittest.TestCase):

    def test_method_of_class_is_collected(self):
        """Ловит мутацию: сбор ограничен уровнем модуля — тестовые методы
        внутри `unittest.TestCase`-класса (обычная форма тестов пульта)
        не собирались бы вовсе."""
        head = ("class FooTest:\n"
               "    def test_x(self):\n"
               "        pass\n")
        self.assertEqual(
            guard.test_functions_without_mutation_claim(None, head), ["test_x"])

    def test_helper_test_prefixed_function_nested_inside_function_is_not_collected(self):
        """Ловит мутацию: сбор углубляется в тела функций — вложенный
        помощник `test_*`, объявленный ВНУТРИ другой функции (не метод
        класса), не тестовый метод фреймворка и не обязан нести заявку."""
        head = ("def make_helper():\n"
               "    def test_inner():\n"
               "        pass\n"
               "    return test_inner\n")
        self.assertEqual(
            guard.test_functions_without_mutation_claim(None, head), [])


class UnparsableHeadTest(unittest.TestCase):

    def test_syntax_error_in_head_returns_single_element_list(self):
        """Ловит мутацию: `SyntaxError` не перехвачен — функция роняла бы
        исключение вместо отказа c именованной причиной (AC-4)."""
        result = guard.test_functions_without_mutation_claim(None, "def test_x(:\n")
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("<не парсится:"))

    def test_unparsable_base_treats_head_functions_as_new(self):
        """Ловит мутацию: base, не прошедший ast.parse, роняет всю
        функцию исключением вместо fail-safe отката к «сведений о base
        нет» — HEAD с валидным синтаксисом не должен падать из-за
        мусора в base."""
        head = "def test_x():\n    pass\n"
        self.assertEqual(
            guard.test_functions_without_mutation_claim("def broken(:\n", head),
            ["test_x"])


if __name__ == "__main__":
    unittest.main()
