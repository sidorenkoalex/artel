"""AC-1 — состав перечня `config.PROTECTED_PATHS`: пять новых записей
добавлены, прежние 12 стоят на прежних местах в прежнем порядке.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `config.PROTECTED_PATHS` содержит `**/conftest.py`,
`pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`, а прежние 12
записей — на прежних местах в прежнем порядке.

Красен до реализации: пяти новых записей в `config.PROTECTED_PATHS` ещё нет — `assertIn` падает на первой же (`**/conftest.py`).

Полная длина кортежа намеренно НЕ утверждается: «всего 17» — состояние
перечня на день задачи, а перечень пополняет Оператор и мимо этой задачи
(`models.yaml` приехал так же). Критерий требует «новые записи есть» и
«прежние 12 не съехали» — ровно это и проверяется.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402
from orchestrator import config  # noqa: E402


class ProtectedPathsListTest(unittest.TestCase):

    def test_ac1_new_entries_are_added(self):
        """Каждая из пяти записей требования 1 — маска `**/conftest.py` и
        четыре корневых литерала — присутствует в `config.PROTECTED_PATHS`.

        Ловит мутацию: разработчик добавил только четыре литерала, а
        запись-маску забыл (или написал её иначе — `conftest.py`,
        `*/conftest.py`, `**/conftest.py/`) — `assertIn` по точному
        значению маски покраснеет, тогда как без него планка проехала бы
        на литералах и «в любом каталоге» осталось бы незащищённым.
        """
        for entry in _protected.NEW_ENTRIES:
            with self.subTest(entry=entry):
                self.assertIn(entry, config.PROTECTED_PATHS)

    def test_ac1_legacy_twelve_entries_keep_their_places_and_order(self):
        """Первые двенадцать элементов кортежа — те же двенадцать записей
        в том же порядке, какими они были до задачи.

        Ловит мутацию: новые записи вписаны В НАЧАЛО кортежа (или маска
        воткнута рядом с `tests/test_invariants.py`, «к тестам») — состав
        перечня тот же, а прежние двенадцать съезжают с прежних мест, и
        срез первых двенадцати перестаёт совпадать со снимком. Наблюдаемое
        расхождение: `PROTECTED_PATHS[:12]` начинается с `**/conftest.py`
        вместо `gates.yaml`.
        """
        self.assertEqual(
            tuple(config.PROTECTED_PATHS[:len(_protected.LEGACY_ENTRIES)]),
            _protected.LEGACY_ENTRIES)


if __name__ == "__main__":
    unittest.main()
