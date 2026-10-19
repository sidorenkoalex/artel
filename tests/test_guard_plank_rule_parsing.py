"""Юнит-тесты разбора планки по правилу компонента в `scripts/guard.py`
(SPEC 01M59KMPG2ZMK10V556VZVQD65, требования 1, 4, 8).

Дополняют долгоживущий файл задачи
(tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py) свойствами, которых
он не касается: счёт тестов сводки по правилу (`count_test_methods`),
подсказка «нет теста» правила из компонентов обоих видов метки и скобки
внутри строк таблицы `.each`. Правило строится прямо из
`guard.PlankComponent`, без записи `targets.yaml`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402

VITEST = guard.PlankComponent("web", ("web/src/**/*.test.jsx",),
                              guard.LABEL_AC, guard.MARKER_SLASH)
PYTEST = guard.PlankComponent("back", ("back/tests/**/test_*.py",))


def plank(case: unittest.TestCase, files: dict) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix="plank-rule-")
    case.addCleanup(tmp.cleanup)
    tdir = Path(tmp.name)
    (tdir / "acceptance_tests").mkdir()
    for name, text in files.items():
        (tdir / "acceptance_tests" / name).write_text(text, encoding="utf-8")
    return tdir


class CountTestMethodsByRuleTest(unittest.TestCase):

    def test_counts_test_calls_of_test_files_and_methods_of_pytest_files(self):
        """Счёт сводки по правилу: вызовы тестов тестовых `.jsx` и методы `.py` компонента pytest; помощник `.jsx` не считается.

        Сценарий: правило из компонента pytest и компонента с меткой
        `AC-<n>: `; в планке `a.test.jsx` с двумя вызовами, помощник
        `_util.jsx` с одним вызовом, `test_b.py` с одним методом и
        посторонний `vitest.config.js` с вызовом. Счёт — 3.

        Ловит мутацию: счёт по правилу читает помощники и посторонние
        файлы (`tests_only` снят у вызовов `.jsx`) либо файлы компонента
        с меткой считаются `TEST_METHOD` (0 вызовов `it`).
        """
        rule = guard.PlankRule(components=(PYTEST, VITEST))
        tdir = plank(self, {
            "a.test.jsx": "it('AC-1: a', () => {});\ntest('b', () => {});\n",
            "_util.jsx": "it('AC-2: helper', () => {});\n",
            "test_b.py": "def test_one():\n    pass\n",
            "vitest.config.js": "it('x', () => {});\n"})
        self.assertEqual(guard.count_test_methods(tdir, rule=rule), 3)
        self.assertEqual(guard.count_test_methods(tdir), 1)


class MixedRuleHintTest(unittest.TestCase):

    def test_missing_test_hint_names_both_forms_for_mixed_rule(self):
        """Подсказка «нет теста» правила с компонентами обоих видов называет и `def test_ac<n>_`, и `it('AC-<n>: …')`.

        Сценарий: правило из компонента pytest и компонента с меткой
        `AC-<n>: `; SPEC с одним непокрытым критерием AC-7. Ошибка
        называет обе формы теста и обе формы пометки; без правила —
        прежний текст только с `def test_ac7_`.

        Ловит мутацию: подсказка выбирается по первому компоненту правила
        (у смешанного правила — одна форма) либо смешанное правило
        получает прежний текст артели.
        """
        rule = guard.PlankRule(components=(PYTEST, VITEST))
        spec = ("---\nschema_version: 5\n---\n\n## Критерии приёмки\n\n"
                "AC-7. Критерий.\n")
        meta = {"schema_version": 5}
        mixed = guard.traceability_errors_from_content(spec, meta, set(), {},
                                                       rule=rule)
        self.assertEqual(len(mixed), 1, mixed)
        for form in ("'def test_ac7_...'", "it('AC-7: …')", "'# AC-7:",
                     "'// AC-7:"):
            with self.subTest(form=form):
                self.assertIn(form, mixed[0])
        artel = guard.traceability_errors_from_content(spec, meta, set(), {})
        self.assertIn("'def test_ac7_...'", artel[0])
        self.assertNotIn("it('AC-7", artel[0])


class EachTableStringsTest(unittest.TestCase):

    def test_parens_inside_each_table_strings_do_not_break_the_call(self):
        """Скобки внутри строк таблицы `.each` не обрывают разбор: литерал второго вызова — имя теста.

        Сценарий: `test.each([['(', ')'], [')', '(']])('AC-3: скобки %s',
        …)` — таблица несёт непарные скобки в строках. Имя теста — литерал
        `AC-3: скобки %s`, критерий AC-3 покрыт.

        Ловит мутацию: поиск закрывающей скобки `.each(…)` считает скобки
        внутри строковых литералов — пара находится не там, литерал
        второго вызова не читается.
        """
        source = ("test.each([['(', ')'], [')', '(']])"
                  "('AC-3: скобки %s', (a, b) => {});\n")
        self.assertEqual(guard.plank_test_names(source), ["AC-3: скобки %s"])
        rule = guard.PlankRule(components=(VITEST,))
        tested, _markers = guard.scan_ac_content([("x.test.jsx", source)],
                                                 rule=rule)
        self.assertEqual(tested, {3})


if __name__ == "__main__":
    unittest.main()
