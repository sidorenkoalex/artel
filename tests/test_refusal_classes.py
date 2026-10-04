"""Юнит-тесты единого перечня классов отказов
`orchestrator/advance_gates/refusal_classes.py` (SPEC
01M446WEVJXARR5CDED8RE9CCR, требование 1): тексты действий, объявленные
константами в модулях гейтов, повторены в перечне литералами (модуль без
импортов пакета) — сверка держит их от расхождения.
"""
import unittest

from orchestrator import fixation
from orchestrator.advance_gates import (acceptance, plan_appendix,
                                        refusal_classes, test_integrity,
                                        tests_writing, zones)

ROLE = refusal_classes.ROLE_FIXES
OPERATOR = refusal_classes.OPERATOR_FIXES


class GateConstantsClassifiedTest(unittest.TestCase):

    def test_gate_action_constants_have_their_spec_class(self):
        """Константа действия каждого гейта несёт класс таблицы SPEC.

        Ловит мутацию: литерал перечня разошёлся с константой гейта
        (опечатка, переименование действия в модуле гейта без правки
        перечня) — `refusal_class` вернул бы класс по умолчанию «чинит
        Оператор», и `auto` остановился бы на отказе, который чинит роль.
        """
        expected = {
            zones.ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION: ROLE,
            plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION: ROLE,
            plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION: OPERATOR,
            tests_writing.LONG_LIVED_ACTION: ROLE,
            tests_writing.ARTIFACT_DISK_READ_ACTION: ROLE,
            tests_writing.TEST_GROUPS_ACTION: ROLE,
            tests_writing.CODE_COPY_REFUSAL_ACTION: OPERATOR,
            acceptance.LONG_LIVED_MANIFEST_ACTION: OPERATOR,
            test_integrity.TEST_INTEGRITY_REFUSAL_ACTION: OPERATOR,
            f"переход отклонён: {fixation.DOCS_REF_UNREAD_ACTION}": OPERATOR,
        }
        for action, klass in expected.items():
            with self.subTest(action=action):
                self.assertIn(action, refusal_classes.REFUSAL_CLASSES)
                self.assertEqual(refusal_classes.refusal_class(action), klass)

    def test_role_not_finished_subclass_is_role_class(self):
        """Подкласс «роль ещё не закончила» — часть класса «чинит роль».

        Ловит мутацию: действие подкласса выпало из перечня классов —
        `auto` остановился бы на «дерево не на ветке задачи» первого же
        входа в `in_dev`, не дав developer написать PLAN.md.
        """
        for action in refusal_classes.ROLE_NOT_FINISHED_REFUSAL_ACTIONS:
            with self.subTest(action=action):
                self.assertEqual(refusal_classes.refusal_class(action), ROLE)


if __name__ == "__main__":
    unittest.main()
