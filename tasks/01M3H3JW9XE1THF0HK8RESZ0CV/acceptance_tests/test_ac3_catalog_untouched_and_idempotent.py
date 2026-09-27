"""Приёмочный тест AC-3 задачи 01M3H3JW9XE1THF0HK8RESZ0CV.

AC-3: `orchestrator/catalog.py` не изменён; его предварительная склейка
на уже склеенной строке не изменяет результат.

Красен до реализации: предварительная склейка каталога пока ДАЁТ результат, которого общий разбор строки зон сам не даёт — `_tz_zone_items` возвращает целые пути, а `guard.zone_items` той же строки обрывки, так что «склейка ничего не добавляет» ещё не выполняется.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import catalog  # noqa: E402
from scripts import guard  # noqa: E402

PROTECTED_PATH = "orchestrator/catalog.py"

# Тело строки «Зоны:» ТЗ с разрывом пути внутри и то же ТЗ целиком.
ZONES_BODY = "scripts/guard.py, orchestrator/\n    budget.py, tests/."
TZ_TEXT = f"# ТЗ: фикстура планки\n\nЗоны: {ZONES_BODY}\n\nРамка: $15.\n"

# Перенос после слова прозы — не разрыв пути: склейка его не трогает.
PROSE_BODY = "scripts/guard.py, задачи 01M3FQ2V77\n    docs/stack.md, tests/"


class CatalogUntouchedTest(unittest.TestCase):

    def test_ac3_catalog_py_not_touched_by_task_diff(self):
        """Дифф ветки задачи от общего предка с main не трогает
        `orchestrator/catalog.py`.

        Файл назван в ТЗ «только чтение» (зона другой задачи в полёте):
        проверяются и коммиты ветки, и незакоммиченные правки рабочего
        дерева.

        Ловит мутацию: разработчик «заодно» убирает ставшую избыточной
        предварительную склейку из `catalog._tz_zone_items` — правка
        попадает в дифф ветки по запрещённому пути.
        """
        if _util.current_branch() == _util.config.MAIN_BRANCH:
            self.skipTest("рабочее дерево на main — диффить не с чем")

        self.assertNotIn(PROTECTED_PATH, _util.changed_paths())

    def test_ac3_prejoin_changes_nothing_on_joined_line(self):
        """Предварительная склейка каталога на уже склеенной строке
        ничего не меняет.

        Строка, к которой склейка уже применена, второй раз проходит её
        без изменений; перенос после слова прозы она не снимает и в
        первый раз — иначе путь в начале следующей строки слипся бы с
        прозой и перестал быть путём.

        Ловит мутацию: правило склейки перенесли в общий разбор и
        расширили до любого переноса строки (лишились условия «после /,
        _ или -») — перенос после слова прозы начинает склеиваться.
        """
        once = catalog._TZ_WRAPPED_PATH_BREAK.sub("", ZONES_BODY)

        self.assertEqual(catalog._TZ_WRAPPED_PATH_BREAK.sub("", once), once)
        self.assertEqual(catalog._TZ_WRAPPED_PATH_BREAK.sub("", PROSE_BODY),
                         PROSE_BODY)

    def test_ac3_prejoin_adds_nothing_to_shared_parse(self):
        """Разбор строки зон ТЗ каталогом и общий разбор той же строки
        дают один и тот же результат.

        `catalog._tz_zone_items` склеивает разрыв ДО вызова
        `guard.zone_items`; после задачи тот же разрыв снимает сам общий
        разбор, поэтому элементы ТЗ с переносом внутри пути обязаны
        совпасть с элементами той же строки зон, разобранной напрямую.

        Ловит мутацию: склейку добавили не в `zone_items`, а в отдельную
        функцию, которую зовут только потребители-вызовы (например
        `budget`) — прямой разбор строки зон по-прежнему даёт обрывки и
        расходится с результатом каталога.
        """
        self.assertEqual(catalog._tz_zone_items(TZ_TEXT),
                         sorted(guard.zone_items(ZONES_BODY)))


if __name__ == "__main__":
    unittest.main()
