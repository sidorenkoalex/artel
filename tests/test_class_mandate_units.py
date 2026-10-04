"""Юнит-тесты покрытия находки элементом-классом и разбора мандата тестов
в `answer` (SPEC 01M42NB9GKXNP74HAYEJ7C7CA8, требования 1 и 3) — углы, не
покрытые долгоживущим файлом
`tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`: пара
переименования, вложенный класс, несколько строк мандата в одном файле.
"""
import unittest

from orchestrator import answer
from orchestrator.advance_gates import test_integrity

MARKER = test_integrity.TEST_WEAKENING_MANDATE_MARKER


class ClassElementOfRenamedFileTest(unittest.TestCase):

    def test_class_element_by_either_path_of_rename_pair(self):
        """Элемент-класс засчитывается по обоим путям пары переименования.

        Находка о методе `A::test_m` файла, переименованного
        `tests/old.py` -> `tests/new.py`: `tests/new.py::A` и
        `tests/old.py::A` — среди покрывающих элементов, класс `AB` и
        префикс метода `A::test` — нет.

        Ловит мутацию: префиксы имени строятся только для пути базы
        (`path`) — элемент `tests/new.py::A` по пути из ветки не покроет
        находку; префикс берётся по строке, а не по частям `::` —
        `tests/old.py::A::test` окажется покрывающим.
        """
        finding = test_integrity.Finding("tests/old.py", "A::test_m",
                                         "метод A::test_m исчез",
                                         "tests/new.py")
        covering = finding.mandate_elements
        for element in ("tests/old.py::A", "tests/new.py::A",
                        "tests/new.py::A::test_m", "tests/new.py"):
            self.assertIn(element, covering)
        for element in ("tests/old.py::AB", "tests/old.py::A::test",
                        "tests/new.py::A::test_m2"):
            self.assertNotIn(element, covering)

    def test_outer_class_element_covers_nested_class_method(self):
        """Элемент внешнего класса покрывает метод вложенного класса.

        Находка о `Outer::Inner::test_x` покрыта и `путь::Outer`, и
        `путь::Outer::Inner`, и полным именем.

        Ловит мутацию: из имени берётся только первая часть или только
        полное имя — `путь::Outer::Inner` не окажется покрывающим.
        """
        finding = test_integrity.Finding("tests/x.py", "Outer::Inner::test_x",
                                         "метод исчез")
        for element in ("tests/x.py::Outer", "tests/x.py::Outer::Inner",
                        "tests/x.py::Outer::Inner::test_x"):
            self.assertIn(element, finding.mandate_elements)


class TestMandateElementsOfAnswerFileTest(unittest.TestCase):

    def test_elements_of_every_marker_line_without_repeats(self):
        """Журнал приёма называет элементы всех строк мандата тестов файла.

        Две строки маркера, элемент повторён во второй; маркер,
        процитированный в середине строки, элементов не даёт.

        Ловит мутацию: разбор берёт только первую строку маркера (как у
        мандата зон) — элемента второй строки в списке не будет; разбор
        ищет маркер где угодно в строке — в список попадёт цитата.
        """
        raw = (f"{MARKER} tests/a.py::A, tests/b.py\n"
               f"см. «{MARKER} tests/quoted.py»\n"
               f"  {MARKER} tests/b.py, tests/c.py::C::test_m\n")
        self.assertEqual(["tests/a.py::A", "tests/b.py",
                          "tests/c.py::C::test_m"],
                         answer._test_mandate_marker_elements(raw))
        self.assertEqual([], answer._test_mandate_marker_elements(
            "Расширение зон разрешено: orchestrator/x.py\n"))


if __name__ == "__main__":
    unittest.main()
