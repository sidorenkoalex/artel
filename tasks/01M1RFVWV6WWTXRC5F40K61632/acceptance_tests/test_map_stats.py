"""Приёмочные тесты 01M1RFVWV6WWTXRC5F40K61632 — AC-1..AC-4: чистая
функция `scripts.codebase_map.map_stats`.

Источник — только tasks/01M1RFVWV6WWTXRC5F40K61632/SPEC.md, раздел
«Критерии приёмки». Фикстуры карты (`_fixtures.build_map`) строятся
РЕАЛЬНЫМ рендерером `codebase_map.render` на синтетических `ModuleInfo`
— см. `_fixtures.py`, включая обоснование выбранной схемы полей
`bytes_by_dir`/`top_sections`.

Красен до реализации: `scripts/codebase_map.py` ещё не содержит
`map_stats` — `from scripts import codebase_map` проходит (модуль
существует), но `codebase_map.map_stats` падает `AttributeError` в
каждом тесте этого файла, пока функция не написана (требование 1
SPEC).
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import codebase_map  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures  # noqa: E402

# Шесть секций, по две на каждый из трёх каталогов перечня, с заведомо
# РАЗНЫМИ размерами (число функций растёт по ряду 1,2,3,4,5,6) — без
# совпадений между собой, чтобы ранжирование `top_sections` было
# однозначным без допущений о порядке при равенстве.
SIX_SECTIONS_SPEC = [
    ("orchestrator/aaa.py", "Оркестрирует А.", 1, []),
    ("orchestrator/bbb.py", "Оркестрирует Б, подлиннее описание модуля.", 4, []),
    ("scripts/ccc.py", "Скрипт Ц.", 2, []),
    ("scripts/ddd.py", "Скрипт Д, тоже подлиннее описание модуля тут.", 5, []),
    ("tests/eee.py", "Тестирует Е.", 3, []),
    ("tests/fff.py", "Тестирует Ж, ещё длиннее описание секции здесь.", 6, []),
]


def _six_sections_map() -> str:
    return _fixtures.build_map(SIX_SECTIONS_SPEC)


class MapStatsPurityTest(unittest.TestCase):
    """AC-1: чистая функция — без диска и git."""

    def test_ac1_does_not_touch_disk_or_subprocess(self):
        """Прогоняет `map_stats` на фикстуре с патчем `Path.read_text`/
        `Path.write_text`/`subprocess.run`, каждый из которых роняет тест
        при вызове — функция обязана дойти до конца, ни разу их не
        потревожив, и принимать только переданный текст.

        Ловит мутацию: реализация внутри `map_stats` подглядывает в
        `docs/codebase-map.md` на диске или зовёт `git`/`subprocess`
        вместо работы с аргументом `map_text` — тест краснеет на
        `AssertionError` из побочного вызова.
        """
        fixture = _six_sections_map()

        def boom(*a, **kw):
            raise AssertionError(
                "map_stats не должна читать/писать диск или звать "
                "subprocess — она чистая функция текст-в-словарь")

        with mock.patch.object(Path, "read_text", side_effect=boom), \
                mock.patch.object(Path, "write_text", side_effect=boom), \
                mock.patch("subprocess.run", side_effect=boom):
            result = codebase_map.map_stats(fixture)

        self.assertIsInstance(result, dict)


class MapStatsFieldsTest(unittest.TestCase):
    """AC-2: bytes_total, sections_total, bytes_by_dir, top_sections."""

    def setUp(self):
        self.fixture = _six_sections_map()
        self.expected = _fixtures.expected_stats(self.fixture)
        self.result = codebase_map.map_stats(self.fixture)

    def test_ac2_bytes_total_is_utf8_length_of_the_whole_text(self):
        """`bytes_total` — размер ВСЕГО текста карты в байтах UTF-8 (не
        символах — фикстура несёт кириллицу, где это расходится).

        Ловит мутацию: реализация считает `len(map_text)` (символы)
        вместо `len(map_text.encode('utf-8'))` — кириллица в
        «Назначении» модулей даёт разные числа, тест поймает расхождение.
        """
        self.assertEqual(self.result["bytes_total"], self.expected["bytes_total"])

    def test_ac2_sections_total_counts_top_level_module_sections(self):
        """`sections_total` — число секций `## <путь>` верхнего уровня;
        фикстура несёт ровно 6.

        Ловит мутацию: подсчёт вложенных заголовков/строк вместо секций
        — на этой фикстуре дал бы число, отличное от 6.
        """
        self.assertEqual(self.result["sections_total"], 6)

    def test_ac2_bytes_by_dir_sums_section_bytes_per_top_level_directory(self):
        """`bytes_by_dir` — байты по каждому из трёх каталогов перечня;
        фикстура даёт заведомо разные суммы для `orchestrator/`,
        `scripts/`, `tests/` (секции внутри разного размера).

        Ловит мутацию: сумма по каталогу считает байты СЕКЦИИ, а не
        байты в разбивке по каталогу (например, добавляет байты шапки
        карты в один из каталогов, или путает `scripts`/`tests`) — три
        числа разойдутся с независимо посчитанным эталоном.
        """
        self.assertEqual(self.result["bytes_by_dir"],
                         self.expected["bytes_by_dir"])
        # Явно живой ассерт, не тавтология с expected: у каждого каталога
        # непустая пара секций разного размера — суммы обязаны быть
        # строго больше нуля и различаться между каталогами.
        by_dir = self.result["bytes_by_dir"]
        self.assertEqual(set(by_dir), {"orchestrator", "scripts", "tests"})
        self.assertTrue(all(v > 0 for v in by_dir.values()))

    def test_ac2_top_sections_are_five_largest_sorted_descending_with_name_and_bytes(self):
        """`top_sections` — пять самых крупных секций (из шести
        фикстуры), имя и размер в байтах, по убыванию размера.

        Ловит мутацию: берутся пять САМЫХ МЕЛКИХ секций, или сортировка
        по возрастанию, или отбор трёх вместо пяти — расхождение с
        независимо посчитанным эталоном (та же логика «секция = `## ` до
        следующего `## `», `_fixtures.expected_stats`).
        """
        top = self.result["top_sections"]
        self.assertEqual(len(top), 5)
        self.assertEqual(top, self.expected["top_sections"])
        sizes = [entry["bytes"] for entry in top]
        self.assertEqual(sizes, sorted(sizes, reverse=True),
                         "не по убыванию размера")
        # Самая мелкая из шести секций фикстуры не входит в топ-5.
        all_sizes = {h: len(_fixtures.section_block(self.fixture, h).encode("utf-8"))
                    for h in _fixtures.section_headers(self.fixture)}
        smallest_name = min(all_sizes, key=all_sizes.get)
        names = [entry["name"] for entry in top]
        self.assertNotIn(smallest_name, names)


class MapStatsProjectionKeyAbsentTest(unittest.TestCase):
    """AC-3: `bytes_projection` отсутствует, пока в модуле нет
    `project_for_brief` (состояние на момент написания SPEC)."""

    def test_ac3_bytes_projection_key_is_absent_not_zero_or_null(self):
        """На сегодняшней версии `scripts/codebase_map.py` (без
        `project_for_brief`, проверено `grep` при написании SPEC —
        «Материалы») ключ `bytes_projection` в результате `map_stats`
        отсутствует целиком: не `0`, не `None`.

        Ловит мутацию: реализация всегда кладёт `bytes_projection`
        (например, `0` «на всякий случай» или `None`-заглушку) —
        `assertNotIn` поймает наличие ключа в обоих случаях, `in`-проверка
        по значению его бы пропустила.
        """
        self.assertFalse(
            hasattr(codebase_map, "project_for_brief"),
            "codebase_map уже содержит project_for_brief — предпосылка "
            "AC-3 (SPEC, «Материалы») больше не верна, критерий в этой "
            "формулировке не проверяем буквально, нужно решение Оператора")

        result = codebase_map.map_stats(_six_sections_map())

        self.assertNotIn("bytes_projection", result)


class MapStatsJsonSerializableTest(unittest.TestCase):
    """AC-4: результат — компактный однострочный JSON, пригодный для
    поля `detail` записи журнала."""

    def test_ac4_result_serializes_to_compact_single_line_json_and_round_trips(self):
        """Компактная сериализация (`separators=(",", ":")`, без
        `ensure_ascii`) не содержит переносов строк и восстанавливается
        обратно в тот же словарь.

        Ловит мутацию: `top_sections`/`bytes_by_dir` несут несериализуемые
        значения (например, `Path` вместо строки в `name`, `set` вместо
        `dict`) — `json.dumps` упадёт `TypeError` вместо тихого прохода;
        встроенный перенос строки в значении (аномалия) поймает проверка
        `"\\n" not in compact`.
        """
        result = codebase_map.map_stats(_six_sections_map())

        compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))

        self.assertNotIn("\n", compact)
        self.assertNotIn("  ", compact, "незначащие пробелы компактный JSON не несёт")
        self.assertEqual(json.loads(compact), result)


if __name__ == "__main__":
    unittest.main()
