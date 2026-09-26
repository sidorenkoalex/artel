"""AC-3 — 01M3FTQ16M3VVXPPFCC0BGA39V: внутрипакетные относительные
импорты попадают в перечни «Импортирует»/«Импортируется».

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Для модуля подпакета, который импортирует сосед по подпакету через
`from . import x` и модуль родительского пакета через `from .. import y`,
оба целевых модуля попадают в его блок «Импортирует», а он сам — в блок
«Импортируется» каждого из них.

Красен до реализации: модуля подпакета сегодня нет в перечне вовсе
(`discover_module_paths` не рекурсирует), а `extract_imported_dotted_
names` бросает уровень 2 (`from .. import y`) через `continue`
(scripts/codebase_map.py:100-103) — ключа
`orchestrator/doctor/preflight.py` в `resolved_imports` нет, первый же
`assertIn` падает.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402


class RelativeImportsResolutionTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _util.write_tree(self.tdir)
        self.map_text, self.imports, self.imported_by = _util.built_map(self.tdir)

    def test_ac3_subpackage_module_imports_both_relative_targets(self):
        """`orchestrator/doctor/preflight.py` фикстуры несёт
        `from . import misc_checks` и `from .. import config` — оба
        целевых модуля стоят в его перечне «Импортирует».

        Ловит мутацию: разрешён только уровень 1 (сосед по подпакету), а
        уровень 2 по-прежнему отбрасывается (`elif node.level == 1: …
        else: continue`) — `orchestrator/config.py` в перечень не
        попадёт, и второй `assertIn` покраснеет.
        """
        self.assertIn(
            _util.SUB_MODULE, self.imports,
            f"{_util.SUB_MODULE} обязан быть в перечне модулей карты, "
            f"иначе его зависимости не считаются вовсе (AC-3); ключи: "
            f"{sorted(self.imports)}")
        targets = self.imports[_util.SUB_MODULE]
        self.assertIn(_util.SUB_NEIGHBOUR, targets,
                      f"`from . import misc_checks` обязан разрешаться в "
                      f"{_util.SUB_NEIGHBOUR} (AC-3); перечень: {targets}")
        self.assertIn(_util.TOP_MODULE, targets,
                      f"`from .. import config` обязан разрешаться в "
                      f"{_util.TOP_MODULE} (AC-3); перечень: {targets}")

    def test_ac3_both_targets_list_the_subpackage_module_as_importer(self):
        """Обратная сторона той же зависимости: и сосед по подпакету, и
        модуль родительского пакета несут `orchestrator/doctor/
        preflight.py` в перечне «Импортируется».

        Ловит мутацию: разрешённый относительный импорт кладётся только в
        `resolved_imports`, а обратный индекс `imported_by` наполняется
        по прежнему (абсолютному) набору целей — перечень «Импортируется»
        соседа останется пустым, и `assertIn` покраснеет.
        """
        for target in (_util.SUB_NEIGHBOUR, _util.TOP_MODULE):
            self.assertIn(
                target, self.imported_by,
                f"{target} обязан быть в перечне модулей карты (AC-3); "
                f"ключи: {sorted(self.imported_by)}")
            self.assertIn(
                _util.SUB_MODULE, self.imported_by[target],
                f"{target} обязан числить {_util.SUB_MODULE} среди "
                f"импортирующих (AC-3); перечень: {self.imported_by[target]}")

    def test_ac3_rendered_sections_carry_the_resolved_relative_targets(self):
        """Те же зависимости видны в готовом тексте карты: блок
        «Импортирует» секции модуля подпакета называет оба пути, а блок
        «Импортируется» секции соседа — путь модуля подпакета.

        Ловит мутацию: резолюция относительных импортов сделана в
        отдельной структуре, которую `render` не читает (секции остаются
        с прочерком «—») — поиск пути внутри текста блока покраснеет.
        """
        section = _util.section_text(self.map_text, _util.SUB_MODULE)
        self.assertIsNotNone(
            section, f"в карте нет секции `## {_util.SUB_MODULE}` (AC-3); "
                     f"секции: {_util.section_headers(self.map_text)}")
        imports_line = self._field_line(section, "Импортирует")
        self.assertIn(f"`{_util.SUB_NEIGHBOUR}`", imports_line)
        self.assertIn(f"`{_util.TOP_MODULE}`", imports_line)

        neighbour = _util.section_text(self.map_text, _util.SUB_NEIGHBOUR)
        self.assertIsNotNone(
            neighbour, f"в карте нет секции `## {_util.SUB_NEIGHBOUR}` (AC-3)")
        self.assertIn(f"`{_util.SUB_MODULE}`",
                      self._field_line(neighbour, "Импортируется"))

    def _field_line(self, section: str, label: str) -> str:
        """Строка блока `**<label>:**` секции — блоки «Импортирует» и
        «Импортируется» различаются только именем, сверять их содержимое
        по всему тексту секции нельзя."""
        prefix = f"**{label}:**"
        for line in section.splitlines():
            if line.startswith(prefix):
                return line
        self.fail(f"в секции нет блока {prefix} (AC-3):\n{section}")


if __name__ == "__main__":
    unittest.main()
