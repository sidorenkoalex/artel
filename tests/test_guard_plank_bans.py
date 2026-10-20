"""Юнит-тесты запретов в тексте файла с меткой `AC-<n>: ` в `scripts/guard.py`
(SPEC 01M5AQH8M2DKBV30NBY86J34A7, требование 7) и номера критерия записи
отчёта (требования 3, 6).

Дополняют долгоживущий файл задачи
(tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py) свойствами, которых
он не касается: ключ объекта в кавычках и сокращение `{ retry }`, номер
строки аргумента многострочного вызова, незакрытая строка и шаблонная
строка, файл без метки по правилу; номер критерия по последнему сегменту
полного имени у Vitest и JUnit. Правило строится прямо из
`guard.PlankComponent`, без записи `targets.yaml`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import project_profile  # noqa: E402
from orchestrator.advance_gates import acceptance as gates  # noqa: E402
from orchestrator.reporters import outcome  # noqa: E402
from scripts import guard  # noqa: E402

VITEST = guard.PlankComponent("web", ("web/src/**/*.test.jsx",),
                              guard.LABEL_AC, guard.MARKER_SLASH)
RULE = guard.PlankRule(components=(VITEST,))
TAIL = " — запрещено в тексте планки"
BODY = "() => { expect(1).toBe(2); }"


def bans(text: str, name: str = "a.test.jsx") -> list[str]:
    return guard.plank_ban_errors([(name, text)], RULE)


class PlankBanFormsTest(unittest.TestCase):

    def test_quoted_and_shorthand_keys_are_banned(self):
        """Ключ `retry`/`timeout` в кавычках и сокращение `{ retry }` в аргументе первого уровня — запрет; иной ключ — нет.

        Сценарий: три файла — `it('AC-1: x', { 'retry': 2 }, …)`,
        `it('AC-1: x', { timeout }, …)` и `it('AC-1: x', { "meta": 1 }, …)`.
        У первых двух — по одной строке отказа с ключом, у третьего —
        ни одной.

        Ловит мутацию: ключ берётся только как имя без кавычек — `'retry'`
        пропущен; сокращение без двоеточия не читается ключом — `{ timeout }`
        пропущен.
        """
        quoted = bans(f"it('AC-1: x', {{ 'retry': 2 }}, {BODY});\n")
        short = bans(f"const timeout = 5;\nit('AC-1: x', {{ timeout }}, {BODY});\n")
        other = bans(f"it('AC-1: x', {{ \"meta\": 1 }}, {BODY});\n")
        self.assertEqual(len(quoted), 1, quoted)
        self.assertIn("ключом retry", quoted[0])
        self.assertEqual(len(short), 1, short)
        self.assertIn("ключом timeout", short[0])
        self.assertTrue(short[0].startswith("a.test.jsx:2: "), short)
        self.assertEqual(other, [])

    def test_line_of_argument_in_multiline_call(self):
        """Номер строки отказа — строка самого запрещённого аргумента многострочного вызова.

        Сценарий: вызов `it(` на строке 1, имя — на 2, колбэк — на 3–5,
        число `5000` — на 6. Отказ «a.test.jsx:6: числовой литерал 5000 …».

        Ловит мутацию: строка считается от головы вызова — в отказе 1;
        счёт строк от нуля — 5.
        """
        text = ("it(\n  'AC-1: x',\n  () => {\n    expect(1).toBe(2);\n  },\n"
                "  5000,\n);\n")
        errors = bans(text)
        self.assertEqual(errors, [f"a.test.jsx:6: числовой литерал 5000 в "
                                  f"аргументах it{TAIL}"])

    def test_unclosed_and_template_strings_and_unlabelled_file(self):
        """Незакрытая строка не роняет разбор и не прячет следующие строки; содержимое шаблонной строки — не запрет; файл без метки по правилу не проверяется.

        Сценарий: (а) строка `const s = 'oops` без закрывающей кавычки, на
        следующей строке `it.only(…)` — отказ на строке 2; (б) шаблонная
        строка `` `it.only ${x} vi.setConfig` `` — отказов нет; (в) тот же
        текст с `it.only` в файле `test_x.py` — отказов нет.

        Ловит мутацию: незакрытая `'` маскирует текст до конца файла —
        `it.only` не найден; маска не снимает шаблонные строки — ложный
        отказ; запрет применяется к любому файлу — отказ файлу pytest.
        """
        unclosed = bans(f"const s = 'oops\nit.only('AC-1: x', {BODY});\n")
        self.assertEqual(len(unclosed), 1, unclosed)
        self.assertTrue(unclosed[0].startswith("a.test.jsx:2: вызов .only"),
                        unclosed)
        self.assertEqual(bans("const s = `it.only ${x} vi.setConfig`;\n"), [])
        self.assertEqual(bans(f"it.only('AC-1: x', {BODY});\n",
                              name="test_x.py"), [])


class RecordCriterionTest(unittest.TestCase):

    def record(self, name: str) -> outcome.CaseResult:
        return outcome.CaseResult(project_profile.test_id("web", "a.jsx", name),
                                  outcome.FAILED)

    def cfile(self, report: str, labelled: bool) -> gates.CriterionFile:
        profile = project_profile.Profile(command=(), long_lived_dir="",
                                          long_lived_name="", weakening_scope=(),
                                          mutation_claim_scope=(), report=report)
        return gates.CriterionFile("a.jsx", "a.jsx", profile, labelled,
                                   frozenset(), True)

    def test_label_in_last_segment_of_full_name(self):
        """Номер критерия — по метке в последнем сегменте полного имени: « > » у `pult-vitest`, «::» у JUnit.

        Сценарий: Vitest — «группа > AC-7: кнопка» даёт 7, «AC-7: группа >
        кнопка» — ничего; JUnit — «Класс::test_ac3_x» даёт 3, «test_ac3_x::
        sub» — ничего.

        Ловит мутацию: метка ищется в начале полного имени, а не последнего
        сегмента — `describe` с меткой засчитан тестом критерия, а тест в
        `describe` без метки не найден.
        """
        vitest = self.cfile(project_profile.REPORT_VITEST, True)
        junit = self.cfile(project_profile.REPORT_JUNIT, False)
        self.assertEqual(gates.record_criterion(
            self.record("группа > AC-7: кнопка"), vitest), 7)
        self.assertIsNone(gates.record_criterion(
            self.record("AC-7: группа > кнопка"), vitest))
        self.assertEqual(gates.record_criterion(
            self.record("Класс::test_ac3_x"), junit), 3)
        self.assertIsNone(gates.record_criterion(
            self.record("test_ac3_x::sub"), junit))


if __name__ == "__main__":
    unittest.main()
