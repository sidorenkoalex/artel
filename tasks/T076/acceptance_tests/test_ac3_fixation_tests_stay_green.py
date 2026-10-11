"""AC-3 (tasks/T076/SPEC.md): существующие тесты фиксаций и целостности
остаются зелёными и не ослаблены (проверки не удалены и не смягчены
сверх требований 3-5 SPEC).

`tests/test_git_fixation.py` (T021) сам называет в докстрине модуля
(строки 9-13) НЕОСЛАБЛЯЕМЫЕ (ADR-0002) классы:
`FsmDecidesOnlyOnFixedHashesTest`, `IntegrityIncidentBlocksRunTest`,
`ApproveByShaTest`, `ExternalApproveDoesNotCommitOthersWorkInProgressTest`
— это единственное явное, машинно-проверяемое указание в кодовой базе
на то, какие именно проверки фиксации/целостности не подлежат
ослаблению; T031/T048/T051 (упомянутые в SPEC как «и смежные») проверяют
соседнюю механику (ветко-корректное чтение, worktree, подтяжка main),
не сам `fixed_sha`/`check_integrity`, и здесь не дублируются — тот же
довод, что и в SPEC T065 про `ManualGatesNeedTheOperatorTest` и т.п.

Зелёный с рождения: эти классы уже существуют и уже проходят на main
(до всякого кода T076) — тест кодирует их СЕГОДНЯШНЕЕ поведение как
нижнюю границу, которую реализация T076 обязана сохранить. Красный
прогон здесь в любой момент означал бы, что T076 удалила или смягчила
одну из этих проверок, а не прогресс задачи.
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


class FixationIntegrityTestsStayGreenTest(unittest.TestCase):

    def test_ac3_unweakened_fixation_test_classes_pass_unmodified(self):
        # Импорт ВНУТРИ теста, не на уровне модуля: `unittest discover`
        # подхватывает любые TestCase, видимые в пространстве имён
        # test-модуля (`loadTestsFromModule`) — импорт на уровне модуля
        # сделал бы эти классы видимыми и снаружи, и внешний discover
        # прогнал бы их ещё раз как будто они объявлены в этом файле
        # (см. tasks/T065/acceptance_tests/test_ac5_invariant_tests_stay_green.py).
        from tests.test_git_fixation import (
            ApproveByShaTest, ExternalApproveDoesNotCommitOthersWorkInProgressTest,
            FsmDecidesOnlyOnFixedHashesTest, IntegrityIncidentBlocksRunTest)

        for cls in (FsmDecidesOnlyOnFixedHashesTest, IntegrityIncidentBlocksRunTest,
                   ApproveByShaTest, ExternalApproveDoesNotCommitOthersWorkInProgressTest):
            with self.subTest(тест=cls.__name__):
                result = _run(cls)
                self.assertTrue(
                    result.wasSuccessful(),
                    f"{cls.__name__}: {len(result.failures)} провалов, "
                    f"{len(result.errors)} ошибок — проверка фиксации/"
                    f"целостности ослаблена ({[t[0] for t in result.failures + result.errors]})")


if __name__ == "__main__":
    unittest.main()
