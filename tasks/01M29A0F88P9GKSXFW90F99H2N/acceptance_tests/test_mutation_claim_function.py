"""Приёмочные тесты AC-1..AC-4 (задача 01M29A0F88P9GKSXFW90F99H2N):
`scripts/guard.py::MUTATION_CLAIM`/`test_functions_without_mutation_claim` —
чистая функция сбора `test_*`-функций/методов HEAD-версии файла без заявки
«Ловит мутацию: …» в докстринге, дифференцирующая новые/изменённые
функции от неизменённых.

Красен до реализации: ни `guard.MUTATION_CLAIM`, ни
`guard.test_functions_without_mutation_claim` ещё не существуют (SPEC
01M29A0F88P9GKSXFW90F99H2N, требование 1) — импорт модуля проходит (сам
модуль существует), но обращение к этим двум именам падает
`AttributeError` в каждом тесте ниже.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from scripts import guard  # noqa: E402


class MutationClaimConstantTest(unittest.TestCase):

    def test_ac1_mutation_claim_constant_is_a_compiled_pattern(self):
        """`guard.MUTATION_CLAIM` существует и устроена как `guard.
        REDNESS_MARKER` — скомпилированный regex, применимый через
        `.search(docstring)`.

        Ловит мутацию: константу назвали иначе или сделали обычной
        строкой вместо `re.compile(...)` — `hasattr`/`.search` упадёт
        или не будет соответствовать контракту «по образцу
        REDNESS_MARKER» требования 1.
        """
        self.assertTrue(hasattr(guard, "MUTATION_CLAIM"))
        self.assertTrue(hasattr(guard.MUTATION_CLAIM, "search"))


class CollectsModuleAndClassLevelTestFunctionsTest(unittest.TestCase):

    def test_ac1_collects_new_module_and_class_level_test_functions(self):
        """Файл добавлен целиком (`base_source=None`): функция обязана
        по AST HEAD-версии найти И функцию `test_*` на уровне модуля, И
        метод `test_*` внутри класса — обе без заявки в докстринге.

        Ловит мутацию: обход AST ограничен только `ast.iter_child_nodes`
        верхнего уровня модуля (без захода в тело `ast.ClassDef`) —
        `test_method` из класса `Foo` тихо потеряется, и функция
        сообщит только о `test_top`, хотя оба лишены заявки.
        """
        head_source = (
            "def test_top():\n"
            "    return 1\n"
            "\n"
            "\n"
            "class Foo:\n"
            "    def test_method(self):\n"
            "        return 2\n"
        )
        result = guard.test_functions_without_mutation_claim(None, head_source)
        self.assertIn("test_top", result)
        self.assertIn("test_method", result)

    def test_ac1_non_test_functions_are_never_collected(self):
        """Функция без префикса `test_` (например, вспомогательный
        `helper`) не попадает в результат, даже будучи новой и без
        заявки — критерий говорит только про функции и методы `test_*`.

        Ловит мутацию: фильтр по имени `test_*` убран/ослаблен —
        `helper` без докстринга ошибочно попадёт в список наравне с
        `test_top`.
        """
        head_source = (
            "def helper():\n"
            "    return 1\n"
            "\n"
            "\n"
            "def test_top():\n"
            "    return 2\n"
        )
        result = guard.test_functions_without_mutation_claim(None, head_source)
        self.assertNotIn("helper", result)
        self.assertIn("test_top", result)


class NewModifiedUnchangedDistinctionTest(unittest.TestCase):

    def test_ac2_unchanged_function_without_claim_is_never_flagged(self):
        """Функция с идентичным текстом сегмента в base и HEAD, но БЕЗ
        заявки в докстринге, не попадает в результат ни при каких
        условиях — старые тесты не трогаем (AC-2, буквально).

        Сегмент функции не меняется, а вот файл вокруг неё — да
        (добавленный `import os` перед функцией в HEAD): сравнение
        обязано идти по тексту самого сегмента функции, не всего файла.

        Ловит мутацию: сравнение «изменилась/нет» подменено сравнением
        текста ВСЕГО файла base/HEAD целиком — не относящаяся к функции
        правка (добавленный импорт) ложно посчитает `test_helper`
        изменённым и потребует заявку у теста, который никто не трогал.
        """
        base_source = (
            "def test_helper():\n"
            "    return 1\n"
        )
        head_source = (
            "import os\n"
            "\n"
            "\n"
            "def test_helper():\n"
            "    return 1\n"
        )
        result = guard.test_functions_without_mutation_claim(base_source,
                                                              head_source)
        self.assertNotIn("test_helper", result)

    def test_ac2_new_function_absent_from_base_is_flagged(self):
        """Функция, имени которой нет в непустом `base_source` (файл
        уже существовал, но эту функцию туда только что добавили), без
        заявки — попадает в результат; соседняя неизменённая функция
        того же файла — нет.

        Ловит мутацию: проверка «имени нет в base» заменена на «текст
        функции есть в base как подстрока» — короткое тело новой
        функции может случайно совпасть текстом с фрагментом другой
        строки base и ложно посчитаться «уже было», пропустив реально
        новый тест без заявки.
        """
        base_source = (
            "def test_old():\n"
            "    return 1\n"
        )
        head_source = (
            "def test_old():\n"
            "    return 1\n"
            "\n"
            "\n"
            "def test_new():\n"
            "    return 2\n"
        )
        result = guard.test_functions_without_mutation_claim(base_source,
                                                              head_source)
        self.assertIn("test_new", result)
        self.assertNotIn("test_old", result)

    def test_ac2_base_source_none_treats_every_function_as_new(self):
        """`base_source is None` (файл добавлен целиком) — все функции
        `test_*` HEAD трактуются как новые, не как «сравнивать не с
        чем, пропустить».

        Ловит мутацию: `base_source is None` обработан как «файла
        раньше не было — функции считаются неизменёнными» (перепутанная
        ветка условия) — новый файл тестов без единой заявки прошёл бы
        гейт молча.
        """
        head_source = (
            "def test_new():\n"
            "    return 1\n"
        )
        result = guard.test_functions_without_mutation_claim(None, head_source)
        self.assertIn("test_new", result)

    def test_ac2_modified_function_text_differs_from_base_is_flagged(self):
        """Функция с тем же именем есть в base, но текст её сегмента в
        HEAD отличается (тело изменили) — без заявки попадает в
        результат как изменённая.

        Ловит мутацию: сравнение текста сегмента заменено на сравнение
        только сигнатуры (имени и списка аргументов) — тело функции
        поменяли (единственное настоящее изменение теста), а «шапка»
        осталась той же, и функция ложно считается неизменённой.
        """
        base_source = (
            "def test_calc():\n"
            "    return 1\n"
        )
        head_source = (
            "def test_calc():\n"
            "    return 2\n"
        )
        result = guard.test_functions_without_mutation_claim(base_source,
                                                              head_source)
        self.assertIn("test_calc", result)


class ClaimPresenceTest(unittest.TestCase):

    def test_ac3_missing_docstring_flags_new_function(self):
        """Новая функция вовсе без докстринга — попадает в результат
        (отсутствие строки «Ловит мутацию:» в принципе).

        Ловит мутацию: `has_mutation_claim` не отличает `docstring is
        None` от «докстринг есть, но без нужной строки» и по ошибке
        считает отсутствующий докстринг как «заявка не нужна» —
        функция без единой строки документации прошла бы гейт молча.
        """
        head_source = (
            "def test_new():\n"
            "    return 1\n"
        )
        result = guard.test_functions_without_mutation_claim(None, head_source)
        self.assertIn("test_new", result)

    def test_ac3_claim_with_empty_text_after_colon_flags_function(self):
        """Докстринг несёт строку «Ловит мутацию:», но текст после
        двоеточия пуст (только пробелы) — критерий требует непустой
        текст, функция обязана попасть в результат.

        Ловит мутацию: проверка ослаблена до «строка "Ловит мутацию:"
        где-то в докстринге присутствует» без проверки непустоты
        текста после двоеточия — пустая заявка-заглушка ложно считалась
        бы настоящей и гейт пропустил бы тест без содержательного
        объяснения мутации.
        """
        head_source = (
            'def test_new():\n'
            '    """Ловит мутацию:   """\n'
            "    return 1\n"
        )
        result = guard.test_functions_without_mutation_claim(None, head_source)
        self.assertIn("test_new", result)

    def test_ac3_claim_with_nonempty_text_excludes_function(self):
        """Докстринг несёт строку «Ловит мутацию: <непустой текст>» —
        функция НЕ попадает в результат.

        Ловит мутацию: условие инвертировано (`if has_claim: append`
        вместо `if not has_claim: append`) — функция с настоящей,
        полноценной заявкой ложно попадала бы в список отказа.
        """
        head_source = (
            'def test_new():\n'
            '    """Ловит мутацию: сравнение заменили на <=, тест '
            'покраснеет."""\n'
            "    return 1\n"
        )
        result = guard.test_functions_without_mutation_claim(None, head_source)
        self.assertNotIn("test_new", result)


class HeadSyntaxErrorTest(unittest.TestCase):

    def test_ac4_head_syntax_error_returns_single_parse_error_element_not_raises(self):
        """HEAD-версия файла не парсится (`SyntaxError`) — функция
        возвращает список из ОДНОГО элемента с текстом ошибки, а не
        поднимает исключение наружу.

        Ловит мутацию: `try/except SyntaxError` вокруг `ast.parse`
        убран — вызов гейта на файле с синтаксической ошибкой в HEAD
        (обычное дело: HEAD ветки задачи ещё не готов) уронил бы весь
        переход `advance` трейсбеком вместо именованного отказа.
        """
        broken_head = "def test_x(:\n    pass\n"
        try:
            ast.parse(broken_head)
            self.fail("фикстура должна была вызвать SyntaxError")
        except SyntaxError as exc:
            expected_text = str(exc)

        result = guard.test_functions_without_mutation_claim(None, broken_head)

        self.assertEqual(len(result), 1)
        self.assertIn("не парсится", result[0])
        self.assertIn(expected_text, result[0])


if __name__ == "__main__":
    unittest.main()
