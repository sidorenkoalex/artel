"""Приёмочный тест 01M2XFSJ1Z7BS6HR69SAT1D81Y — AC-7: существующий набор
`tests/test_auto_escalated_return_rework_gate.py` (юнит-тесты анкера рубежа
`auto._role_step_since_state_entry`, SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X) после
правки остаётся зелёным, и ни одна из его сегодняшних проверок не исчезает.

Зелёный с рождения: этот файл `tests/` зелёный и сейчас — критерий
запрещает чинить задачу ослаблением или удалением его ожиданий (ADR-0002,
принцип целостности), то есть фиксирует СОХРАНЕНИЕ существующего
поведения, а не появление нового. Проверяется исполнением (прогон модуля
целиком), а не чтением диффа, плюс сверкой имён тестовых методов —
молчаливое удаление проверки зелёным прогоном не отличается от её
прохождения.

Набор имён ниже — снимок модуля на момент написания планки: добавление
НОВЫХ тестов в тот же файл критерий не запрещает (сверка — на включение,
не на равенство), а исчезновение любого из перечисленных означает ровно
то, что критерий называет «удалением существующих проверок».
"""
import importlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

MODULE_NAME = "tests.test_auto_escalated_return_rework_gate"

EXISTING_CHECKS = frozenset({
    "test_no_entry_at_all_degrades_to_true",
    "test_review_return_without_a_developer_step_blocks",
    "test_developer_step_after_the_review_return_unblocks",
    "test_escalated_return_after_the_developer_step_does_not_hide_it",
    "test_budget_escalated_return_detail_is_ignored_the_same_way",
    "test_escalated_return_with_no_developer_step_still_blocks",
    "test_developer_step_after_the_escalated_return_unblocks",
    "test_legit_first_entry_detail_still_degrades_to_true",
    "test_only_an_escalated_return_entry_is_the_degenerate_case",
})


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


class ExistingReworkGateSuiteTest(unittest.TestCase):

    def test_ac7_existing_rework_gate_suite_passes_unweakened(self):
        """Модуль `tests/test_auto_escalated_return_rework_gate.py`
        загружается, все его тестовые методы на месте и прогон модуля
        целиком зелёный.

        Ловит мутацию: рубеж анкера починен «в лоб» — новый маркер
        обрабатывается так, что запись возврата из эскалации становится
        анкером ВСЕГДА (а не только вслед за маркером), и
        `test_escalated_return_after_the_developer_step_does_not_hide_it`
        краснеет; прогон здесь это покажет. Второй вариант — ту же
        покрасневшую проверку просто убирают из файла: её исчезновение
        поймает сверка с `EXISTING_CHECKS`.
        """
        module = importlib.import_module(MODULE_NAME)
        suite = unittest.TestLoader().loadTestsFromModule(module)
        names = {test.id().rsplit(".", 1)[-1] for test in _flatten(suite)}

        missing = sorted(EXISTING_CHECKS - names)
        self.assertEqual(
            missing, [],
            f"из {MODULE_NAME} исчезли проверки: {missing} — удаление "
            f"существующего теста не способ выполнения задачи")

        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            f"{MODULE_NAME} не зелёный после правки:\n{stream.getvalue()}")


if __name__ == "__main__":
    unittest.main()
