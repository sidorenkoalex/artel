"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-3 (`scripts/guard.py`
отказывает SPEC или PLAN, чей `budget_usd` разбирается как число выше
`ROLE_BUDGET_CAP`, независимо от `schema_version`, с подсказкой поделить
задачу (01M1KS8K9RXWHX2PW3ZKB0P903) либо эскалировать вопрос бюджета
Оператору).

Значение потолка берётся из `config.ROLE_BUDGET_CAP` динамически (не
литералом) — задача-конвенция test-authoring.md: константа — крутилка
Оператора, тест обязан пережить её поворот.

Красен до реализации: `config.ROLE_BUDGET_CAP` не существует сегодня —
`setUpClass` падает `AttributeError` раньше первого теста класса, а не
на каком-то одном assert'е внутри (тот же красный результат для всех
тестов модуля разом, честно указывающий на отсутствие кода задачи, а не
на дефект теста).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from _sandbox import check_plan, check_spec  # noqa: E402


class GuardRefusesSpecAboveCapTest(unittest.TestCase):
    """SPEC с `budget_usd` выше `ROLE_BUDGET_CAP` — отказ, независимо от
    `schema_version` (проверено на версии ниже 5, где поле само по себе
    ещё не обязательно, — отказ идёт по ДРУГОЙ причине: значению, а не
    присутствию).

    Ловит мутацию: проверка потолка ролей по ошибке гейтится версией
    (например, `if version >= 5: ...`) — тогда `schema_version: 4` с
    `budget_usd` выше потолка проходит без единой ошибки, хотя AC-3
    прямо требует «независимо от schema_version».
    """

    def test_ac3_spec_v4_above_cap_is_refused(self):
        over_cap = config.ROLE_BUDGET_CAP + 20

        errors = check_spec(schema_version=4, budget=over_cap)

        self.assertTrue(errors, f"SPEC с budget_usd={over_cap} (выше "
                                f"потолка ролей {config.ROLE_BUDGET_CAP}) "
                                f"обязан быть отказан")

    def test_ac3_spec_v5_above_cap_is_refused(self):
        over_cap = config.ROLE_BUDGET_CAP + 20

        errors = check_spec(schema_version=5, budget=over_cap)

        self.assertTrue(errors, f"SPEC с budget_usd={over_cap} обязан "
                                f"быть отказан")

    def test_ac3_spec_at_cap_is_not_refused_by_this_rule(self):
        """Граница: значение РОВНО в потолок ролей ещё допустимо — «выше»,
        а не «начиная с»."""
        errors = check_spec(schema_version=5, budget=config.ROLE_BUDGET_CAP)

        self.assertFalse(
            any("ROLE_BUDGET_CAP" in e or "потолк" in e for e in errors),
            f"budget_usd == ROLE_BUDGET_CAP не обязан отказываться этим "
            f"правилом: {errors!r}")


class GuardRefusesPlanAboveCapTest(unittest.TestCase):
    """PLAN с `budget_usd` выше `ROLE_BUDGET_CAP` — тот же отказ, что и у
    SPEC (AC-3 буквально называет оба типа: «SPEC ИЛИ PLAN»).

    Ловит мутацию: новая проверка написана только внутри ветки
    `atype == "spec"` в `_content_errors` (по аналогии с
    `spec_zones_errors`/`split_assessment_errors` рядом) и забывает про
    PLAN — тогда этот тест находит пустой список ошибок там, где обязан
    быть непустой.
    """

    def test_ac3_plan_above_cap_is_refused(self):
        over_cap = config.ROLE_BUDGET_CAP + 20

        errors = check_plan(schema_version=4, budget=over_cap)

        self.assertTrue(errors, f"PLAN с budget_usd={over_cap} обязан "
                                f"быть отказан")


class RefusalNamesTheHintTest(unittest.TestCase):
    """Отказ несёт подсказку по существу («поделить задачу» ИЛИ
    «эскалировать»), а не только голое «сумма выше потолка» — AC-3
    прямо требует обе альтернативы в подсказке.

    Ловит мутацию: guard отказывает значению выше потолка, но текстом
    без единого слова про деление или эскалацию (например, просто
    «budget_usd выше ROLE_BUDGET_CAP») — тогда ни один из regex ниже не
    совпадёт, хотя список ошибок и непуст.
    """

    def test_ac3_refusal_mentions_split_or_escalation(self):
        over_cap = config.ROLE_BUDGET_CAP + 20

        errors = check_spec(schema_version=5, budget=over_cap)
        joined = "\n".join(errors)

        self.assertRegex(
            joined, r"раздел|подел",
            f"AC-3: подсказка обязана упоминать деление задачи; "
            f"ошибки: {errors!r}")
        self.assertRegex(
            joined, r"эскалир",
            f"AC-3: подсказка обязана упоминать эскалацию Оператору; "
            f"ошибки: {errors!r}")


if __name__ == "__main__":
    unittest.main()
