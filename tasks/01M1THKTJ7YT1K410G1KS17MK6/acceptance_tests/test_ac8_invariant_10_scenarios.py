"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-8 (`tests/
test_invariants.py` дополнен: SPEC со значением выше `ROLE_BUDGET_CAP`
потолок не поднимает (отказ guard); потолок Оператора не перебивается
значением из SPEC).

AC-8 описывает не файл-носитель («тесты дописаны туда-то»), а два
наблюдаемых сценария инварианта 10 — эта планка проверяет сами сценарии
напрямую (тот же угол, что и остальные файлы этой планки), не факт
правки конкретного файла `tests/`: трассируемость AC читает имя метода
теста, не путь модуля, который он трогает.

Красен до реализации: `config.ROLE_BUDGET_CAP` не существует —
`AttributeError` на первой же строке каждого теста; сегодняшний guard
вообще не знает о потолке ролей (пустой список ошибок для любого числа
ниже старого `SUPPORTED_SCHEMA_VERSION`-предела), так что даже без
`AttributeError` первый сценарий не нашёл бы ожидаемого отказа.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from _sandbox import BudgetCeilingTest, check_spec  # noqa: E402


class SpecAboveCapDoesNotRaiseTheCeilingTest(BudgetCeilingTest):
    """Сценарий 1 инварианта 10: SPEC со значением выше `ROLE_BUDGET_CAP`
    потолок не поднимает — отказ guard блокирует сам переход, значение
    никогда не доходит до строки задачи.

    Ловит мутацию: guard пропускает SPEC с завышенным `budget_usd` без
    ошибки (проверка потолка ролей забыта или сравнивает не с той
    константой) — тогда `errors` пуст, хотя AC-8 требует именно отказ
    guard как механизм защиты потолка.
    """

    def test_ac8_guard_refuses_the_spec_before_any_ceiling_change(self):
        over_cap = config.ROLE_BUDGET_CAP + 1

        errors = check_spec(schema_version=5, budget=over_cap)

        self.assertTrue(
            errors, f"guard обязан отказать SPEC с budget_usd={over_cap} "
                    f"(потолок ролей {config.ROLE_BUDGET_CAP}) до того, как "
                    f"задача попадёт на переход")


class OperatorCeilingNotOverriddenTest(BudgetCeilingTest):
    """Сценарий 2 инварианта 10: потолок Оператора не перебивается
    значением из SPEC — вторая, независимая линия защиты на случай, если
    SPEC с завышенным значением всё же дошёл до `apply_spec_budget`
    (например, был написан ДО того, как guard начал проверять потолок
    ролей — старый беклог, версия ниже 5).

    Ловит мутацию: `apply_spec_budget` проверяет `budget_source` только
    для отказа СВОЕГО повторного применения, но не для значений,
    пришедших от SPEC поверх операторского — тогда потолок $60,
    поставленный Оператором, слетел бы на "$25" из SPEC.
    """

    def test_ac8_operator_ceiling_survives_a_spec_value_within_cap(self):
        self.set_task(budget_usd=60.0,
                      budget_source=config.BUDGET_SOURCE_OPERATOR)

        self.apply("25")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], 60.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_OPERATOR)


if __name__ == "__main__":
    unittest.main()
