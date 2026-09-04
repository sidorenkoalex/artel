"""AC-10 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Перед фиксацией
команда прогоняет каталог tasks/<id>/acceptance_tests/ (unittest) и
отказывает, если итог прогона — не «OK» (падения, ошибки
импорта/атрибутов, кроме падений с маркером «Красен до реализации»,
разбираемых тем же способом, что переход tests_writing): tests_locked_sha
не обновляется, изменения каталога не коммитятся.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AC_TEST_BROKEN_NO_MARKER, AC_TEST_BROKEN_WITH_MARKER,  # noqa: E402
                      AmendSandbox)


class PretestRunGateTest(AmendSandbox):

    def test_ac10_failure_without_redness_marker_blocks_the_amend(self):
        """Оператор правит acceptance_tests/test_ac.py на заведомо
        падающий тест БЕЗ маркера «Красен до реализации» — команда
        обязана сама прогнать unittest, увидеть не-OK и отказать: коммита
        нет, tests_locked_sha не сдвигается.

        Ловит мутацию: команда не запускает прогон вовсе и коммитит
        правку «как есть» (обязательность прогона — ADR-0012-инцидент
        03.09, требование 6 SPEC), либо запускает, но игнорирует
        ненулевой код возврата.
        """
        locked = self.enter_in_dev()
        head_before = self.head()
        self.write_acceptance_tests(AC_TEST_BROKEN_NO_MARKER)

        out = self.run_amend(reason="правка, которая всё ломает")

        self.assertTrue(out.strip(), "отказ обязан называть причину")
        self.assertEqual(
            self.row()["tests_locked_sha"], locked,
            "tests_locked_sha не должен измениться при непрошедшем "
            "прогоне без маркера красноты")
        self.assertEqual(
            self.head(), head_before,
            "изменения каталога не должны коммититься при непрошедшем "
            "прогоне без маркера красноты")

    def test_ac10_failure_with_redness_marker_does_not_block_the_amend(self):
        """Тот же падающий тест, но с маркером «Красен до реализации» в
        докстринге модуля — тем же разбором, что и переход tests_writing
        (падение с маркером — норма), правка обязана пройти: коммит
        появляется, tests_locked_sha сдвигается на новый sha.

        Ловит мутацию: команда трактует ЛЮБОЕ падение прогона как отказ,
        не сверяясь с маркером красноты вовсе — тогда легитимная правка,
        вносящая намеренно красный (промаркированный) тест, безосновательно
        блокируется наравне с непроверенной поломкой.
        """
        locked = self.enter_in_dev()
        self.write_acceptance_tests(AC_TEST_BROKEN_WITH_MARKER)

        self.run_amend(reason="правка вносит намеренно красный тест")

        new_locked = self.row()["tests_locked_sha"]
        self.assertNotEqual(
            new_locked, locked,
            "правка с промаркированным падением обязана пройти и "
            "сдвинуть tests_locked_sha")
        self.assertEqual(new_locked, self.head())


if __name__ == "__main__":
    unittest.main()
