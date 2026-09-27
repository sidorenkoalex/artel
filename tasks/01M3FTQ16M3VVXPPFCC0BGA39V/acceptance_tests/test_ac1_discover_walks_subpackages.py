"""AC-1 — 01M3FTQ16M3VVXPPFCC0BGA39V: `discover_module_paths` обходит
подпакеты и не подбирает `.py` внутри `__pycache__`.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `codebase_map.discover_module_paths` на временном дереве, где у
пакета есть `__init__.py`, модуль верхнего уровня и подпакет с
`__init__.py` и модулем, возвращает и модули верхнего уровня, и модули
подпакета; путь внутри каталога `__pycache__` в результат не попадает.

Красен до реализации: `discover_module_paths` сегодня перебирает
`dir_path.glob("*.py")` без захода в подкаталоги (scripts/codebase_map.py:
38-46) — модули подпакета в результат не попадают, `assertIn` падает.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402


class DiscoverModulePathsTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _util.write_tree(self.tdir)
        self.found = _util.discovered_rel_paths(self.tdir)

    def test_ac1_discover_returns_top_level_and_subpackage_modules(self):
        """Дерево-фикстура с пакетом (`__init__.py` + модуль верхнего
        уровня) и подпакетом (`__init__.py` + два модуля) — перечень
        путей несёт и модули верхнего уровня, и модули подпакета.

        Ловит мутацию: рекурсия заведена только для `__init__.py`
        подпакета (обход подкаталогов добавляет пакет, но не его модули)
        либо вовсе не заведена — `orchestrator/doctor/preflight.py` не
        появится в перечне, и тест покраснеет.
        """
        for rel in (_util.TOP_INIT, _util.TOP_MODULE, _util.TOP_IMPORTER,
                    _util.SUB_INIT, _util.SUB_MODULE, _util.SUB_NEIGHBOUR,
                    _util.TESTS_MODULE):
            self.assertIn(
                rel, self.found,
                f"{rel} обязан попасть в перечень модулей карты (AC-1); "
                f"перечень: {self.found}")

    def test_ac1_pycache_paths_are_not_discovered(self):
        """Файл `.py`, лежащий внутри каталога `__pycache__` подпакета,
        в перечень модулей не входит вовсе.

        Ловит мутацию: рекурсивный обход написан голым
        `dir_path.rglob("*.py")` без отсечения служебных каталогов —
        мусорный `orchestrator/doctor/__pycache__/preflight.py` попадёт
        в перечень, и `assertNotIn` покраснеет.
        """
        self.assertNotIn(
            _util.PYCACHE_TRASH, self.found,
            f"путь внутри __pycache__ не должен попадать в перечень "
            f"модулей карты (AC-1); перечень: {self.found}")
        self.assertEqual(
            [], [rel for rel in self.found if "__pycache__" in rel],
            "в перечне модулей карты не должно быть ни одного пути с "
            "сегментом __pycache__ (AC-1)")


if __name__ == "__main__":
    unittest.main()
