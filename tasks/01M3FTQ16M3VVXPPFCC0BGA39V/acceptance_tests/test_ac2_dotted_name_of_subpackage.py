"""AC-2 — 01M3FTQ16M3VVXPPFCC0BGA39V: dotted-имя модуля подпакета
строится по пути целиком.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. `codebase_map.module_dotted_name` даёт
`orchestrator.doctor.preflight` для модуля подпакета и
`orchestrator.doctor` для `__init__.py` подпакета.

Красен до реализации: `module_dotted_name` сегодня склеивает только
первый сегмент пути и `stem` (scripts/codebase_map.py:50-60) — для
модуля подпакета даёт `orchestrator.preflight`, а для его `__init__.py`
— `orchestrator`; оба `assertEqual` падают.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import codebase_map  # noqa: E402


class ModuleDottedNameTest(unittest.TestCase):

    def test_ac2_module_of_subpackage_gets_full_dotted_path(self):
        """Путь `orchestrator/doctor/preflight.py` -> dotted-имя
        `orchestrator.doctor.preflight` — то самое имя, которым модуль
        подпакета называет абсолютный импорт, и по которому его находит
        резолюция перечня зависимостей.

        Ловит мутацию: имя собрано из первого сегмента пути и `stem`
        (`orchestrator.preflight`) — такое имя не совпадёт ни с одним
        реальным import-выражением, и `assertEqual` покраснеет.
        """
        rel = Path(_util.SUB_MODULE)
        self.assertEqual(f"{_util.PKG}.{_util.SUBPKG}.preflight",
                         codebase_map.module_dotted_name(rel))

    def test_ac2_init_of_subpackage_is_named_by_the_subpackage(self):
        """`__init__.py` подпакета называется именем самого подпакета
        (`orchestrator.doctor`), а не `orchestrator.doctor.__init__` и не
        именем пакета верхнего уровня.

        Ловит мутацию: ветка `stem == "__init__"` осталась прежней и
        возвращает `rel_path.parts[0]` (`orchestrator`) — имя подпакета
        потеряется, и `assertEqual` покраснеет.
        """
        rel = Path(_util.SUB_INIT)
        self.assertEqual(f"{_util.PKG}.{_util.SUBPKG}",
                         codebase_map.module_dotted_name(rel))

    def test_ac2_top_level_names_are_unchanged(self):
        """Имена модулей верхнего уровня остаются прежними:
        `orchestrator/config.py` -> `orchestrator.config`,
        `orchestrator/__init__.py` -> `orchestrator`.

        Ловит мутацию: рекурсивная сборка имени применена ко всем путям
        без различения `__init__.py` (`orchestrator.__init__`) — на такое
        имя не ссылается ни `import orchestrator`, ни `from . import x`,
        и `assertEqual` покраснеет.
        """
        self.assertEqual(f"{_util.PKG}.config",
                         codebase_map.module_dotted_name(Path(_util.TOP_MODULE)))
        self.assertEqual(_util.PKG,
                         codebase_map.module_dotted_name(Path(_util.TOP_INIT)))


if __name__ == "__main__":
    unittest.main()
