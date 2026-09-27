"""AC-10 — 01M3HJQV2QV9BXNXSH3F8STAYH: названные наборы `tests/` зелёные, ни
один существующий тест не ослаблен и не удалён.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. `tests/test_canary.py`, `tests/test_canary_sets.py`,
`tests/test_pin.py` и остальной набор `tests/` зелёные, ни один существующий
тест не ослаблен и не удалён.

Полный набор `tests/` здесь НЕ прогоняется (правило skills/
test-authoring.md: его гоняют CI кодовой ветки и автогейт приёмки) — целиком
прогоняются только три файла, названные критерием поимённо, а по остальному
набору проверяется то, что от планки зависит и стоит дешево: каждый модуль
`tests/`, существовавший до задачи, по-прежнему импортируется и собирается
(правка зон задачи не сломала его на уровне импорта), и ни один тестовый
метод не исчез.

«Не ослаблен» проверяется тем, что проверяемо механически: ни один тестовый
метод, существовавший в `tests/` до задачи, не исчез и не переименован.
Переписанное ВНУТРИ метода утверждение планка не запрещает — это предмет
ревью по диффу.

Зелёный с рождения: три набора проходят на сегодняшнем коде, все модули
`tests/` импортируются и ни один метод ещё не удалён — тест сохранения
существующего поведения. Он краснеет ровно тогда, когда правка задачи ломает
или выкидывает чужой тест.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

#: Наборы, названные критерием поимённо.
NAMED_SUITES = ("test_canary.py", "test_canary_sets.py", "test_pin.py")


def _modules_before() -> list:
    """Имена модулей `tests/test_*.py`, существовавших до этой задачи."""
    return sorted(Path(path).stem for path in _util.main_tree_files("tests")
                  if Path(path).name.startswith("test_")
                  and path.endswith(".py"))


class NamedSuitesStayGreenTest(unittest.TestCase):

    def test_ac10_named_suites_pass_on_the_branch(self):
        """Три названных критерием набора `tests/` прогоняются целиком и
        проходят без единого провала.

        Ловит мутацию: подъём потолка сделан правкой формулы вердикта так, что
        `tests/test_canary.py::RunOneTaskVerdictUsesNormalOutcomeTest`
        (вердикт — обратное `_needs_diagnostics`) перестаёт держаться —
        агрегированный результат перестанет быть успешным, и провалившийся
        метод будет назван в тексте.
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        missing = []
        for name in NAMED_SUITES:
            if not (_util.TESTS_DIR / name).is_file():
                missing.append(name)
                continue
            suite.addTests(loader.loadTestsFromName(f"tests.{Path(name).stem}"))

        self.assertEqual([], missing,
                         "файл(ы) названных наборов исчезли из ветки: "
                         + ", ".join(missing))

        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            "названные наборы не зелёные: провалы="
            + repr([str(case) for case, _ in result.failures])
            + "; ошибки=" + repr([str(case) for case, _ in result.errors]))

    def test_ac10_no_existing_test_method_disappeared(self):
        """Каждый тестовый метод, существовавший в `tests/` до задачи,
        существует в ветке под тем же именем.

        Ловит мутацию: тест, мешающий новому исходу или новому вердикту
        (например, `tests/test_canary.py::GreenCanaryRunsTest::
        test_red_runs_are_excluded`), удалён или переименован вместо
        приведения к новому поведению — `assertEqual` назовёт исчезнувшее имя.
        """
        gone = []
        for name in _modules_before():
            local = _util.TESTS_DIR / f"{name}.py"
            if not local.is_file():
                gone.append(f"{name}.py: файла нет")
                continue
            before = _util.unittest_method_names(
                _util.main_source(f"tests/{name}.py"))
            after = _util.unittest_method_names(
                local.read_text(encoding="utf-8"))
            gone.extend(f"{name}::{method}" for method in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовый метод(ы), существовавшие до задачи, исчезли из ветки — "
            "удаление теста это ослабление проверки (AC-10): "
            + ", ".join(gone))

    def test_ac10_every_existing_test_module_still_imports(self):
        """Каждый модуль `tests/`, существовавший до задачи, импортируется и
        собирается загрузчиком unittest.

        Ловит мутацию: константа-множитель потолка или новый исход заведены
        переименованием чего-то, что чужие наборы импортируют по имени
        (`canary._MERGE_GATE_KILL_ACTION`, `store.insert_canary_run`) —
        остальной набор `tests/` падал бы на импорте, и его провал не был бы
        виден до CI.
        """
        loader = unittest.TestLoader()
        for name in _modules_before():
            if not (_util.TESTS_DIR / f"{name}.py").is_file():
                continue
            loader.loadTestsFromName(f"tests.{name}")

        self.assertEqual([], list(loader.errors),
                         "модуль(и) tests/ не импортируются: "
                         + "; ".join(str(error)[:400] for error in loader.errors))


if __name__ == "__main__":
    unittest.main()
