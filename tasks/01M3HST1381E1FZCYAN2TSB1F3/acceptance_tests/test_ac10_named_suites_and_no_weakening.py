"""AC-10 — 01M3HST1381E1FZCYAN2TSB1F3: названные наборы зелёные, ни один
тест, гейт, лимит или guard-проверка не ослаблен и не удалён.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. `tests/test_canary.py`, `tests/test_canary_sets.py`,
`tests/test_providers_codex.py` зелёные; полный набор `tests/` зелёный; ни
один существующий тест, гейт, лимит или guard-проверка не ослаблен и не
удалён.

Полный набор `tests/` здесь НЕ прогоняется (правило skills/test-authoring.md:
его гоняют CI и автогейт приёмки, а шаг роли гоняет только планку и тесты
затронутых модулей) — прогоняются три файла, названные критерием поимённо.

«Не ослаблен и не удалён» проверяется тем, что проверяемо механически: ни
один тестовый метод, существовавший на main в ЛЮБОМ файле `tests/`, не
исчез и не переименован, и ни одна функция-проверка `scripts/guard.py`
(`check_*`/`scan_*` — носители гейтов, лимитов и guard-проверок) не
исчезла. Переписанное ВНУТРИ метода утверждение планка не запрещает — это
предмет ревью по диффу.

Зелёный с рождения: это тест СОХРАНЕНИЯ существующего поведения — три
набора проходят на сегодняшнем коде, и ни один метод ещё не удалён.
Краснеет ровно тогда, когда правка задачи ломает или выкидывает чужой тест
либо снимает guard-проверку.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

#: Наборы, названные критерием поимённо.
NAMED_SUITES = ("test_canary.py", "test_canary_sets.py",
                "test_providers_codex.py")

#: Носитель гейтов, лимитов и guard-проверок пульта.
GUARD_PY = "scripts/guard.py"


class NamedSuitesAndNoWeakeningTest(unittest.TestCase):

    def test_ac10_named_suites_pass_on_the_branch(self):
        """Три названных критерием набора `tests/` прогоняются целиком и
        проходят без единого провала.

        Ловит мутацию: перенос указателя вписан в `_ephemeral_clone`
        безусловно (или новая константа-путь в `config` не внесена в
        `_CLONE_CONFIG_ATTRS`/`_CLONE_EXEMPT_CONFIG_ATTRS`) — `tests/
        test_canary.py::CloneConfigAttrsInvariantTest` краснеет, и
        агрегированный результат назовёт провалившийся метод.
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

    def test_ac10_no_test_method_of_main_disappeared_from_tests(self):
        """Каждый тестовый метод, существовавший на main в любом файле
        `tests/`, существует в ветке под тем же именем.

        Ловит мутацию: тест, мешающий новому поведению эфемерного клона
        (например сверка состава дома роли клона или инвариант списка
        переадресуемых путей `config`), удалён или переименован вместо
        приведения к новому поведению — `assertEqual` назовёт исчезнувшее
        имя.
        """
        gone = []
        for rel in _util.main_tree_files("tests"):
            if not Path(rel).name.startswith("test_"):
                continue
            local = _util.REPO_ROOT / rel
            if not local.is_file():
                gone.append(f"{rel}: файла нет")
                continue
            before = _util.unittest_method_names(_util.main_source(rel))
            after = _util.unittest_method_names(
                local.read_text(encoding="utf-8"))
            gone.extend(f"{rel}::{method}" for method in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовый метод(ы) main исчезли из ветки — удаление теста это "
            "ослабление проверки (AC-10): " + ", ".join(gone))

    def test_ac10_no_guard_check_disappeared(self):
        """Каждая функция-проверка `scripts/guard.py`, существовавшая на
        main, существует в ветке под тем же именем.

        Ловит мутацию: guard-проверка, споткнувшаяся о новый файл или новую
        константу задачи, снята вместо починки — гейт пульта перестал бы
        ловить свой класс дефектов молча, а диффом это выглядело бы как
        уборка.
        """
        before = _util.guard_function_names(_util.main_source(GUARD_PY))
        after = _util.guard_function_names(
            (_util.REPO_ROOT / GUARD_PY).read_text(encoding="utf-8"))

        self.assertTrue(before, "предпосылка: на main у guard есть проверки")
        self.assertEqual(set(), before - after,
                         "проверки guard исчезли из ветки: "
                         + ", ".join(sorted(before - after)))


if __name__ == "__main__":
    unittest.main()
