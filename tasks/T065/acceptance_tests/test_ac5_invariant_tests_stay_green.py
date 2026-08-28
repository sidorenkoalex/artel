"""AC-5 (tasks/T065/SPEC.md): инвариантные тесты 7, 12 и 18
(`tests/test_invariants.py::ManualGatesNeedTheOperatorTest`,
`tests/test_invariants.py::MergeOnlyFromMergeGateTest`,
`AutoNeverPassesAGateTest`) остаются зелёными без изменений: продуктовые
`approve`/`auto` не получают нового пути автопрохода гейта — автопроход
существует только внутри команды `canary` для задач, заведённых ею же.

SPEC называет местом всех трёх классов `tests/test_invariants.py`; по
факту (проверено `grep -rn` по репозиторию на момент написания этого
теста) `AutoNeverPassesAGateTest` (инвариант 18 — «`auto` не проходит
гейт») живёт в `tests/test_auto_cycle.py`, не в `tests/test_invariants.py`
— неточность самого SPEC в скобке-адресе, не в формулировке критерия
(предмет критерия — что тест остаётся зелёным — от расположения файла не
меняется). Импорт ниже идёт по фактическому месту, не по тексту SPEC.

Зелёный с рождения: этот тест — не про код задачи T065, которого ещё
нет, а про то, что T065 (когда её код появится) не ослабит уже
существующие неослабляемые тесты (ADR-0002). Он проходит уже сегодня,
на пустой ветке до всякой реализации `canary`, и обязан продолжать
проходить после неё — красноту здесь создал бы только сам факт
ослабления инварианта, а не отсутствие кода T065.
"""
import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def _run(test_case_cls) -> unittest.TestResult:
    suite = unittest.TestLoader().loadTestsFromTestCase(test_case_cls)
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


class InvariantTestsStayGreenTest(unittest.TestCase):

    def test_ac5_named_invariant_tests_pass_unmodified(self):
        # Импорт ВНУТРИ теста, не на уровне модуля: `unittest discover`
        # сканирует каждый подхваченный test-модуль на ЛЮБые TestCase
        # внутри его пространства имён (`loadTestsFromModule`) — импорт
        # `ManualGatesNeedTheOperatorTest`/etc. на уровне модуля делает их
        # видимыми и снаружи этого теста, и внешний discover повторно (и
        # неконтролируемо — без `_run()` ниже) гоняет их ЕЩЁ РАЗ как будто
        # они объявлены в этом файле (проверено прогоном: без этой правки
        # `Ran N tests` внешнего discover считает их дважды).
        from tests.test_invariants import (
            ManualGatesNeedTheOperatorTest, MergeOnlyFromMergeGateTest)
        from tests.test_auto_cycle import AutoNeverPassesAGateTest

        for cls in (ManualGatesNeedTheOperatorTest, MergeOnlyFromMergeGateTest,
                   AutoNeverPassesAGateTest):
            with self.subTest(тест=cls.__name__):
                result = _run(cls)
                self.assertTrue(
                    result.wasSuccessful(),
                    f"{cls.__name__}: {len(result.failures)} провалов, "
                    f"{len(result.errors)} ошибок — инвариант ослаблен "
                    f"({[t[0] for t in result.failures + result.errors]})")


if __name__ == "__main__":
    unittest.main()
