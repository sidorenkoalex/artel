"""Приёмочный тест SPEC 01M291EJMA995AZ61MEMDZKWRY (AC-6): существующие
тесты `tests/test_merge_lock.py` (взятие, отказ, перехват мёртвого
держателя, освобождение) обязаны проходить без ослабления и без
изменения содержательных проверок — эта задача не трогает
`orchestrator/merge_lock.py` (SPEC, требование 7: «существующее
поведение orchestrator/merge_lock.py ... не ослабляется»), меняются
только точки вызова `acquire`/`release` в `fsm_merge_gate.py`.

Зелёный с рождения: `tests/test_merge_lock.py` кроет модуль
`orchestrator/merge_lock.py`, который эта SPEC не меняет (её "Не
входит" и требование 7 явно исключают ослабление его поведения) —
прогоняя этот уже существующий, уже зелёный набор как есть, тест ниже
фиксирует регрессионную планку: он обязан остаться зелёным и после
переноса `acquire`/`release` в `_cmd_approve_merge_gate_cycle`
(`orchestrator/fsm_merge_gate.py`), не только сегодня.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tests import test_merge_lock  # noqa: E402


class ExistingMergeLockSuiteRegressionTest(unittest.TestCase):

    def test_ac6_existing_merge_lock_tests_pass_without_weakening(self):
        """Загружает и исполняет ВЕСЬ модуль `tests/test_merge_lock.py`
        (взятие своей/чужой строки, перехват протухшего heartbeat и
        мёртвого pid, безусловное освобождение, атомарность конкурентного
        `acquire`) как единый под-набор и требует его полного успеха.

        Ловит мутацию: любое ослабление содержательной проверки в
        `orchestrator/merge_lock.py` (например, снятие ветки перехвата
        мёртвого pid в `_holder_is_dead`, или разрешение `release`
        снимать чужую сессию) уронит соответствующий метод
        `tests/test_merge_lock.py`, и агрегированный результат перестанет
        быть успешным.
        """
        suite = unittest.TestLoader().loadTestsFromModule(test_merge_lock)
        result = unittest.TestResult()
        suite.run(result)

        details = "\n".join(
            f"{case}:\n{trace}" for case, trace in
            (result.failures + result.errors))
        self.assertTrue(result.wasSuccessful(), details)


if __name__ == "__main__":
    unittest.main()
