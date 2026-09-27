"""Приёмочный тест AC-1 задачи 01M3H3JW9XE1THF0HK8RESZ0CV.

AC-1: `guard.zone_items` для строки зон склеивает путь, разорванный
переносом после «/», «_» или «-» с отступом следующей строки, и
возвращает тот же набор элементов, что для идентичной строки без
переноса.

Разрыв без отступа следующей строки тестом НЕ фиксируется: правило
`_TZ_WRAPPED_PATH_BREAK`, на которое AC-1 ссылается через требование 1
SPEC, допускает пустой отступ, и ассерт «без отступа не склеивает»
противоречил бы самому правилу.

Красен до реализации: zone_items переносы внутри пути не снимает — строка с разрывом после «/» даёт обрывок-каталог и элемент с переносом внутри вместо целого пути.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

# Путь строки зон, разорванный вёрсткой ТЗ в каждой из трёх точек правила:
# (голова до переноса, хвост следующей строки).
WRAPPED_PATHS = {
    "/": ("orchestrator/", "budget.py"),
    "_": ("orchestrator/zone_", "lock.py"),
    "-": ("docs/reference/role-", "home.md"),
}


def zone_line(head: str, tail: str, indent: str = "    ") -> str:
    """Строка зон, где путь `head + tail` разорван переносом между
    `head` и `tail`, а следующая строка идёт с отступом `indent`."""
    return f"scripts/guard.py, {head}\n{indent}{tail}, tests/"


class ZoneItemsWrappedPathTest(unittest.TestCase):

    def test_ac1_wrapped_path_gives_same_items_as_flat_line(self):
        """Строка зон с разрывом пути после «/», «_», «-» разбирается в
        тот же набор элементов, что та же строка без разрыва.

        Для каждой из трёх точек разрыва сравниваются наборы элементов
        строки с переносом и строки, написанной в одну строку; заодно
        проверяется, что целый путь в наборе есть, а обрывок-каталог до
        переноса самостоятельным элементом не стал (ложная зона,
        накрывающая почти любую задачу).

        Ловит мутацию: склейку сделали только для переноса после «/»
        (условие сузили до одного символа) — пара с разрывом после «_»
        или «-» перестаёт совпадать с плоской строкой.
        """
        for brk, (head, tail) in WRAPPED_PATHS.items():
            with self.subTest(разрыв=brk):
                wrapped = zone_line(head, tail)
                flat = f"scripts/guard.py, {head}{tail}, tests/"

                items = guard.zone_items(wrapped)

                self.assertEqual(items, guard.zone_items(flat))
                self.assertIn(head + tail, items)
                self.assertNotIn(head, items)

    def test_ac1_wrapped_path_joins_with_tab_indent(self):
        """Отступ следующей строки табуляцией — тот же разрыв внутри пути.

        ТЗ верстают и табуляцией: правило переноса считает отступом и
        пробелы, и табуляцию, поэтому строка зон с табом даёт тот же
        набор элементов, что и строка без переноса.

        Ловит мутацию: отступ после переноса снимают выражением с одними
        пробелами (`\\n +`) — путь, продолженный со строки с табуляцией,
        остаётся разорванным.
        """
        head, tail = WRAPPED_PATHS["/"]
        wrapped = zone_line(head, tail, indent="\t")

        self.assertEqual(guard.zone_items(wrapped),
                         guard.zone_items(f"scripts/guard.py, {head}{tail}, "
                                          f"tests/"))


if __name__ == "__main__":
    unittest.main()
