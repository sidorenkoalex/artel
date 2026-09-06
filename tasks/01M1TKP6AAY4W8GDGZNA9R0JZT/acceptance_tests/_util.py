"""Общие фикстуры планки P1a (восстановлены Оператором 06.09 через
amend-tests: исходный `_util.py` тест-автора был вычищен из каталога как
«посторонний» фильтром чекпоинта — белый список
`checkpoint._ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` не знал вспомогательных
модулей `_*.py`; регрессия №18).

Образцы планки лежат здесь, а не литералами в test_*.py: они несут
настоящий синтаксис пометок критериев (`# AC-n: manual|skip — причина`,
см. `scripts/guard.py::AC_MARKER`), а guard сканирует разметку любого
`test_*.py` на диске текстом — литерал в тестовом файле читался бы как
разметка ЭТОЙ задачи и искажал трассируемость. Имя `_util.py` не
подходит под `test_*.py`, поэтому guard его не сканирует.
"""
from __future__ import annotations

import configparser
import tomllib
from pathlib import Path

# Планка из двух зелёных проверок одного критерия AC-1 (тест сводки
# журнала amend-tests, AC-5): amend-tests требует «OK» прогона, сводка
# pytest для неё — «2 passed».
AC_TEST_TWO_PASSING = '''\
"""Зелёный с рождения: фикстура правки планки — две зелёные проверки
одного критерия для теста сводки журнала amend-tests."""
import unittest

# AC-2: manual — Оператор проверяет глазами на приёмке


class TwoPassingTest(unittest.TestCase):

    def test_ac1_first_check(self):
        """Зелёный с рождения: фикстура правки планки — проверка, что
        сводка прогона попадает в журнал, содержимое теста не важно."""
        self.assertTrue(True)

    def test_ac1_second_check(self):
        """Зелёный с рождения: вторая проверка того же критерия — чтобы
        сводка несла число тестов больше единицы."""
        self.assertEqual(2, 1 + 1)
'''

# Планка с одним тестом AC-1 и пометками manual/skip для AC-2/AC-3
# (регресс-тест разбора маркеров guard, AC-6): маркер краснозелёности в
# докстринге есть — `scan_redness_markers` ошибок не даёт.
MIXED_PLANK = '''\
"""Зелёный с рождения: синтетическая планка для регресс-теста разбора
маркеров guard — один тест AC-1 и пометки manual/skip для AC-2/AC-3."""
import unittest

# AC-2: manual — Оператор проверяет глазами на приёмке
# AC-3: skip — временно не тестируется, обоснование в PLAN.md


class MixedPlankTest(unittest.TestCase):

    def test_ac1_something_is_checked(self):
        """Зелёный с рождения: синтетическая планка для разбора маркеров,
        содержимое проверки не важно."""
        self.assertTrue(True)
'''

# Планка БЕЗ маркера «Красен до реализации:»/«Зелёный с рождения:» в
# докстринге — `scan_redness_markers` обязан назвать файл в ошибке.
NO_MARKER_PLANK = '''\
import unittest


class NoMarkerPlankTest(unittest.TestCase):

    def test_ac1_without_redness_marker(self):
        """Докстринг без пометки краснозелёности."""
        self.assertTrue(True)
'''


def read_pytest_config(root: Path) -> dict | None:
    """Конфигурация pytest пульта из `pyproject.toml`
    (`[tool.pytest.ini_options]`) либо `pytest.ini` (`[pytest]`) в корне
    `root`. Возвращает словарь с ключами `testpaths` (список строк),
    `python_files` (список строк), `timeout` (int либо None) — либо
    `None`, если ни одного файла конфигурации нет (тесты AC-7/AC-9
    отказывают `assertIsNotNone` до собственно проверки)."""
    pyproject = Path(root) / "pyproject.toml"
    ini = Path(root) / "pytest.ini"
    raw: dict | None = None
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        raw = data.get("tool", {}).get("pytest", {}).get("ini_options")
    if raw is None and ini.exists():
        parser = configparser.ConfigParser()
        parser.read(ini, encoding="utf-8")
        if parser.has_section("pytest"):
            raw = dict(parser["pytest"])
    if raw is None:
        return None

    def _as_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return value.split()
        return [str(v) for v in value]

    timeout = raw.get("timeout")
    return {
        "testpaths": _as_list(raw.get("testpaths")),
        "python_files": _as_list(raw.get("python_files")),
        "timeout": int(timeout) if timeout is not None else None,
    }
