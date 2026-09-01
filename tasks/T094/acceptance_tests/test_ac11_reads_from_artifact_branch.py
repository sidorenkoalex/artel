"""Приёмочный тест T094 — AC-11 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-11: «Каждая точка чтения из реестра (AC-1) у живой задачи читает
tasks/<id>/ из артефактной ветки пульта, а не из кодовой ветки
целевого; существующие тесты инвариантов 25-28 остаются зелёными.»

Область этого файла — ВТОРАЯ половина критерия (инварианты 25-28
зелёные): прогоняет модули, которые `docs/invariants.md` называет их
тестами. Первая половина («каждая точка чтения из реестра») по
построению не может быть исчерпана здесь — сам реестр (AC-1) пишет
разработчик в PLAN.md ПОСЛЕ выхода test_author из `tests_writing`;
перечислить «каждую» точку сейчас означало бы гадать за разработчика
(запрещено skills/test-authoring.md, «не изобретай компромисс»). Два
пункта минимума требования 1 из пяти покрыты ДРУГИМИ файлами этой же
папки напрямую: «хэш-фиксация гейтов» — `test_ac10_gate_fixation_two_
shas.py`, «ветко-корректные чтения» — тем же классом проверки, что и
инвариант 28 ниже. Оставшиеся («лок acceptance_tests», «guard в CI»,
«coldstart» — частично) проверяет Оператор при приёмке на РЕЕСТРЕ,
который к тому моменту уже существует в PLAN.md (manual, см.
test_manual_criteria.py, помечен там отдельно от этого файла).

Зелёный с рождения: перечисленные модули проходят уже сегодня — этот
тест их не переписывает, а фиксирует «не сломалось» тем же прогоном,
каким CI гоняет полный набор `tests/`; регресс любого из них после
переезда на артефактную ветку — ровно то, что критерий запрещает.
"""
import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Модули, которые docs/invariants.md называет тестами инвариантов 25-28.
INVARIANT_MODULE_NAMES = (
    "tests.test_git_fixation",
    "tests.test_acceptance_tests_flow",
    "tests.test_gitcmd_branch_reads",
)
INVARIANT_FILE_PATHS = (
    REPO_ROOT / "tasks" / "T031" / "acceptance_tests"
    / "test_branch_correct_reads.py",
    REPO_ROOT / "tasks" / "T047" / "acceptance_tests"
    / "test_branch_correct_status_reads.py",
)


class Ac11InvariantsStayGreenTest(unittest.TestCase):

    def test_ac11_invariant_25_to_28_test_modules_still_pass(self):
        suite = unittest.TestSuite()
        for name in INVARIANT_MODULE_NAMES:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
        for path in INVARIANT_FILE_PATHS:
            self.assertTrue(path.exists(), f"{path} отсутствует")
            spec_name = f"_invariant_module_{path.stem}"
            import importlib.util
            spec = importlib.util.spec_from_file_location(spec_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            f"тесты инвариантов 25-28 не проходят целиком (AC-11): "
            f"{len(result.failures)} failures, {len(result.errors)} errors — "
            f"{[t[0].id() for t in (result.failures + result.errors)]}")


if __name__ == "__main__":
    unittest.main()
