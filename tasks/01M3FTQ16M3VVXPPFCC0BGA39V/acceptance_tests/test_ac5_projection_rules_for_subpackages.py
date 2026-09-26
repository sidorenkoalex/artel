"""AC-5 — 01M3FTQ16M3VVXPPFCC0BGA39V: проекция для брифа применяет к
секции модуля подпакета то же правило, что к модулю верхнего уровня того
же пакета.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. В проекции `codebase_map.project_for_brief` секция модуля
подпакета внутри пакета orchestrator сохраняет «Назначение», «Публичные
функции» и «Импортирует» и теряет «Импортируется» — тем же правилом, что
секция модуля верхнего уровня того же пакета; секции `tests/*`
по-прежнему сохраняют только «Назначение».

Красен до реализации: секции модуля подпакета в карте сегодня нет вовсе
(генератор его не обходит) — `_util.section_text` вернёт `None`, и
`test_ac5_subpackage_section_keeps_the_same_fields_as_top_level` падает
на отсутствии секции. `test_ac5_tests_sections_keep_only_purpose`
зелёный уже сейчас: он фиксирует СОХРАНЕНИЕ существующего правила
проекции для `tests/*`, которое эта задача не меняет.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import codebase_map  # noqa: E402

PURPOSE = "Назначение"
FUNCTIONS = "Публичные функции"
IMPORTS = "Импортирует"
IMPORTED_BY = "Импортируется"


class ProjectionForBriefTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _util.write_tree(self.tdir)
        self.map_text, _, _ = _util.built_map(self.tdir)
        self.projected = codebase_map.project_for_brief(self.map_text)

    def _labels(self, map_text: str, rel: str) -> list:
        section = _util.section_text(map_text, rel)
        self.assertIsNotNone(
            section,
            f"в карте нет секции `## {rel}` (AC-5); секции: "
            f"{_util.section_headers(map_text)}")
        return _util.field_labels(section)

    def test_ac5_subpackage_section_keeps_the_same_fields_as_top_level(self):
        """Полная карта фикстуры несёт у секции модуля подпакета все
        четыре поля; проекция оставляет у неё «Назначение», «Публичные
        функции», «Импортирует» и снимает «Импортируется» — ровно тот же
        набор полей, что у секции модуля верхнего уровня того же пакета.

        Ловит мутацию: правило проекции выбирается по полному пути
        секции, а не по первому его сегменту (`_section_kind` возвращает
        `None` для `orchestrator/doctor/preflight.py`) — секция вернётся
        из проекции как есть, вместе с «Импортируется», и сравнение
        наборов полей покраснеет.
        """
        self.assertEqual(
            [PURPOSE, FUNCTIONS, IMPORTS, IMPORTED_BY],
            self._labels(self.map_text, _util.SUB_MODULE),
            "до проекции секция модуля подпакета обязана нести все четыре "
            "поля — иначе тест ниже проверял бы отсутствие поля, которого "
            "не было (AC-5)")

        sub_labels = self._labels(self.projected, _util.SUB_MODULE)
        top_labels = self._labels(self.projected, _util.TOP_MODULE)
        self.assertEqual([PURPOSE, FUNCTIONS, IMPORTS], sub_labels,
                         f"проекция секции {_util.SUB_MODULE} (AC-5)")
        self.assertEqual(top_labels, sub_labels,
                         f"секция модуля подпакета обязана проецироваться тем "
                         f"же правилом, что {_util.TOP_MODULE} (AC-5)")
        self.assertNotIn(IMPORTED_BY, sub_labels)

    def test_ac5_tests_sections_keep_only_purpose(self):
        """Секция `tests/*` в проекции по-прежнему несёт только
        «Назначение» — правило проекции для тестов эта задача не меняет.

        Ловит мутацию: правило подпакетов заведено расширением таблицы
        `_KEPT_FIELDS_BY_KIND` так, что вид секции определяется с
        сохранением полей по умолчанию для всех каталогов — секция
        `tests/*` начнёт носить «Публичные функции»/«Импортирует», и
        `assertEqual` покраснеет.
        """
        self.assertEqual([PURPOSE],
                         self._labels(self.projected, _util.TESTS_MODULE),
                         f"проекция секции {_util.TESTS_MODULE} (AC-5)")


if __name__ == "__main__":
    unittest.main()
