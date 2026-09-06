"""AC-11 (SPEC.md): тесты, разбирающие вывод `_run_summary()`/
`_RUN_SUMMARY` фикстурой конкретного формата (`tests/test_amend.py::
RunSummaryTest`), обновлены под формат сводки pytest без изменения
проверяемого ими поведения (итог события `AMEND_ACTION` называет
зелёный/красный исход и число тестов).

Красен до реализации: `tests/test_amend.py::RunSummaryTest` сегодня (не
все три теста файла — см. ниже) несёт фикстуры формата unittest («Ran N tests in Xs\\n\\nOK»/
«FAILED (failures=1)») — `test_ac11_fixtures_no_longer_use_unittest_wording`
и `test_ac11_fixtures_use_pytest_summary_wording` падают уже сейчас,
находя буквальный unittest-формат там, где должен быть pytest-формат.
`test_ac11_existing_run_summary_tests_still_pass_after_migration` СЕГОДНЯ
зелёный (старые unittest-фикстуры согласованы со старой unittest-
регуляркой `amend._RUN_SUMMARY` — паре менять нечего) — это ожидаемо и
не маскирует дефект: как только требование 2 переключит регулярку на
pytest-формат, старые фикстуры перестанут находить совпадение, и этот же
тест упадёт своими собственными assert'ами до тех пор, пока фикстуры не
обновят вместе с регуляркой; ловит именно этот промежуточный разрыв, не
проверяет что-то тавтологичное на сегодняшнем коде.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import tests.test_amend as test_amend  # noqa: E402


def _run_summary_test_class_source(repo_root: Path) -> str:
    source = (repo_root / "tests" / "test_amend.py").read_text(encoding="utf-8")
    start = source.index("class RunSummaryTest")
    rest = source[start + len("class RunSummaryTest"):]
    end = rest.find("\nclass ")
    body = rest if end == -1 else rest[:end]
    return "class RunSummaryTest" + body


class RunSummaryFixtureMigrationTest(unittest.TestCase):

    def setUp(self):
        self.class_source = _run_summary_test_class_source(REPO_ROOT)

    def test_ac11_fixtures_no_longer_use_unittest_wording(self):
        """Исходник `tests/test_amend.py::RunSummaryTest` не несёт больше
        буквального unittest-формата вывода («Ran N tests»/«FAILED
        (failures=»), которым были построены его фикстуры ДО перехода
        на pytest.

        Ловит мутацию: фикстуры скопированы из `test_ac4_run_summary.py`
        этой планки лишь частично (например, обновлена только зелёная
        фикстура, красная осталась в старом unittest-формате) — второй
        `assertNotIn` откажет.
        """
        self.assertNotIn("Ran ", self.class_source, self.class_source)
        self.assertNotIn(
            "FAILED (failures=", self.class_source, self.class_source)

    def test_ac11_fixtures_use_pytest_summary_wording(self):
        """Фикстуры `RunSummaryTest` несут pytest-словарь сводки («passed»
        для зелёного случая, «failed» для красного) — не абстрактные
        строки без связи с реальным форматом раннера.

        Ловит мутацию: фикстуры заменены на пустые/произвольные строки
        вместо реалистичного pytest-вывода (тест перестаёт проверять
        РЕАЛЬНЫЙ формат, становится тавтологией) — `assertIn` откажет.
        """
        self.assertIn("passed", self.class_source)
        self.assertIn("failed", self.class_source)

    def test_ac11_existing_run_summary_tests_still_pass_after_migration(self):
        """Сам класс `tests/test_amend.py::RunSummaryTest`, исполненный
        как есть, зелёный — обновление фикстур не изменило проверяемое
        им поведение (та же связка «сводка называет зелёный/красный
        исход и число тестов»), только формат образцов вывода.

        Ловит мутацию: фикстура обновлена под pytest-формат, но
        `amend._RUN_SUMMARY` при этом не подхватывает какой-то из её
        вариантов (например, обновили только «N passed», забыли «M
        failed, N passed») — конкретный тестовый метод класса упадёт
        своим собственным `assertEqual`, `wasSuccessful()` вернёт
        `False`.
        """
        suite = unittest.TestLoader().loadTestsFromTestCase(
            test_amend.RunSummaryTest)
        result = unittest.TextTestRunner(stream=_NullStream(), verbosity=0).run(suite)
        self.assertTrue(
            result.wasSuccessful(),
            f"tests/test_amend.py::RunSummaryTest не зелёный: "
            f"{result.failures + result.errors}")


class _NullStream:
    def write(self, *args, **kwargs):
        pass

    def flush(self):
        pass


if __name__ == "__main__":
    unittest.main()
