"""AC-2, AC-3 — вердикт единого помощника сравнения из
`orchestrator/config.py` на новых путях и на похожих незащищённых.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Помощник сравнения из `orchestrator/config.py` признаёт
защищёнными `conftest.py`, `tests/conftest.py`, `tests/sub/conftest.py`,
`pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`.

AC-3. Тот же помощник НЕ признаёт защищёнными
`tests/test_conftest_role_guard.py`, `docs/pyproject.md`,
`conftest.py.bak` и `tests/pytest.ini` (литералы требования 3 — только
корневые).

Помощник ищется по контракту, а не по угаданному имени: SPEC называет его
место (`orchestrator/config.py`), но не имя — см. `_protected.
comparison_helpers` и `_protected.HELPER_CONTRACT`.

Красен до реализации: функций в `orchestrator/config.py` нет ни одной (модуль — константы и `from pathlib import Path`), помощника сравнения не существует — `comparison_helpers()` пуст и `assertTrue` падает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402


class ComparisonHelperVerdictTest(unittest.TestCase):

    def setUp(self):
        self.helpers = _protected.comparison_helpers()
        self.assertTrue(self.helpers, _protected.HELPER_CONTRACT)

    def test_ac2_helper_protects_test_collection_settings(self):
        """Помощник отвечает «защищён» на `conftest.py` в корне и в двух
        вложенных каталогах и на четыре корневых файла настроек pytest.

        Ловит мутацию: запись-маска обслуживается той же префиксной
        формулой, что и остальные записи (`path == "**/conftest.py" or
        path.startswith("**/conftest.py")`) — вердикт на `conftest.py`,
        `tests/conftest.py` и `tests/sub/conftest.py` становится «не
        защищён», и именно тот обход, против которого задача заведена,
        остаётся открытым.
        """
        for name, helper in self.helpers:
            for path in _protected.PROTECTED_NEW_PATHS:
                with self.subTest(helper=name, path=path):
                    self.assertTrue(
                        helper(path),
                        f"{name}({path!r}) обязан быть истинным: путь покрыт "
                        f"записями требования 1")

    def test_ac3_helper_does_not_protect_lookalike_paths(self):
        """Помощник отвечает «не защищён» на путь, лишь похожий на новые
        записи: файл теста про conftest, документ про pyproject, резервную
        копию `conftest.py.bak` и вложенный `tests/pytest.ini`.

        Ловит мутацию: маска разобрана как «имя файла где-нибудь в пути»
        (`"conftest.py" in path`) вместо «последний компонент пути» —
        `conftest.py.bak` и `tests/test_conftest_role_guard.py` становятся
        защищёнными, и правка обычного файла тестов начинает требовать
        коммита Оператора в main. Второе наблюдаемое расхождение той же
        проверки: корневые литералы сверяются по последнему компоненту, а
        не префиксом, — тогда защищённым числится и `tests/pytest.ini`,
        которого требование 3 из перечня прямо исключает.
        """
        for name, helper in self.helpers:
            for path in _protected.UNPROTECTED_LOOKALIKE_PATHS:
                with self.subTest(helper=name, path=path):
                    self.assertFalse(
                        helper(path),
                        f"{name}({path!r}) обязан быть ложным: ни одна "
                        f"запись перечня этот путь не покрывает")


if __name__ == "__main__":
    unittest.main()
