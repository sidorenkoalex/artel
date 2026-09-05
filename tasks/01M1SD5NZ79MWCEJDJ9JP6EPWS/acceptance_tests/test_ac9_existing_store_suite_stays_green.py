"""Приёмочный тест AC-9 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
`tests/test_store*.py`, тесты миграций (в т.ч.
`tests/test_store_schema_migration_parity.py`) и все тесты, где
встречается `mock.patch.object(store, ...)` или прямой вызов
`store.create_schema`/`store.migrate`, — зелёные без правки утверждений
после переноса схемы/миграций в `schema.py` и группировки запросов.

Список файлов не захардкожен единственным перечислением: собирается
ровно так же, как описывает сам критерий, — глоб `test_store*.py` по
`tests/` плюс grep по `mock.patch.object(store,` — так что появление
нового такого теста между запусками этой планки само попадает в
область следующего прогона, без правки этого файла. Полный набор
`tests/` здесь НЕ запускается (правило скила test-authoring: гоняет
CI) — только эти конкретные, явно перечисленные в самом критерии файлы.

Зелёный с рождения: сегодняшний (дорефакторинговый) `store.py` уже
проходит весь этот набор — тест фиксирует этот факт как планку,
которая обязана остаться истинной и после переноса схемы/миграций в
`schema.py` (AC-1/AC-2) и группировки запросов (AC-3).
"""
import io
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"

_MOCK_PATCH_STORE = re.compile(r"mock\.patch\.object\(store,")


def _store_regression_files() -> list:
    """`tests/test_store*.py` + все `tests/*.py`, где встречается
    `mock.patch.object(store, ...)` — буквально то, что перечисляет
    AC-9 (требование 5 SPEC называет `test_store*.py` и подмены
    `store.*` отдельно, глоб `tests/test_store*.py` не покрыл бы
    `tests/test_release.py`, единственный на сегодня файл со второй
    категорией)."""
    found = set(TESTS_DIR.glob("test_store*.py"))
    for path in TESTS_DIR.glob("*.py"):
        if _MOCK_PATCH_STORE.search(path.read_text(encoding="utf-8")):
            found.add(path)
    return sorted(found)


class StoreRegressionSuiteStaysGreenTest(unittest.TestCase):

    def test_ac9_store_regression_files_pass(self):
        """Файлы, найденные `_store_regression_files()`, запущенные
        целиком через `unittest`, проходят без единого провала/ошибки.

        Ловит мутацию: любая правка `store.py` в ходе переноса схемы в
        `schema.py` или группировки запросов, которая на деле поменяла
        поведение (не только структуру) — например, `store.migrate`
        перестал быть тем же объектом, что вызывает `store.db()`
        (`tests/test_store_schema_migration_parity.py` и
        `tests/test_release.py::mock.patch.object(store, "lease_row",
        ...)` перестают видеть свои подмены/сценарии) — уронит хотя бы
        один из этих файлов, и агрегированный результат перестанет
        быть успешным.
        """
        files = _store_regression_files()
        self.assertTrue(
            files,
            "не нашлось ни одного файла-кандидата — проверь TESTS_DIR "
            "и паттерны отбора")

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for path in files:
            module_name = f"tests.{path.stem}"
            suite.addTests(loader.loadTestsFromName(module_name))

        runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
        result = runner.run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            "регресс store: файлы=" + ", ".join(p.name for p in files) +
            "; провалы=" + repr([str(t) for t, _ in result.failures]) +
            "; ошибки=" + repr([str(t) for t, _ in result.errors]))


if __name__ == "__main__":
    unittest.main()
