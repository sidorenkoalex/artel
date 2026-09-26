"""Приёмочные тесты 01M3EM7A84KE0W690M02VWPNXF — AC-5: комментарий рядом с
записью метки в `orchestrator/pull.py` больше не утверждает, что из
`acceptance`/`merge_gate` возврат из эскалации шага роли не заводит, и ни
один существующий тест подтяжки/эскалаций не удалён.

Полный прогон `tests/` эта планка не воспроизводит и воспроизводить не
вправе: его гоняют CI ветки и автогейт приёмки тем же набором целиком
(шаг роли полный набор не запускает — решение Оператора 05.09), а
вложенный pytest внутри планки удвоил бы прогон и его таймаут. Планка
фиксирует то, чего полный прогон не ловит: текст комментария и САМ ФАКТ
наличия существующих тестов (удаление теста полный прогон видит зелёным).
«Ослаблен» — суждение по диффу, его выносит ревьювер.

Красен до реализации: комментарий у записи метки (`orchestrator/pull.py::
_handle_merge_failure`, ~стр. 266-270) сегодня несёт ровно то утверждение,
которое требование 3 объявляет ложным («`acceptance`/`merge_gate` … не
заводят шага роли на возврате из escalated, метить их нечем») — первый
тест падает на `assertNotIn`. Второй тест (существующие тесты не удалены)
зелёный с рождения — это лок против «починки» планки удалением чужого
теста, а не ожидание нового кода.
"""
import importlib
import inspect
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import pull  # noqa: E402

# Утверждение, которое требование 3 объявляет ложным, — в сегодняшней
# формулировке и в ближайших её вариантах (комментарий переносится по
# строкам, поэтому текст комментариев склеивается в одну строку до сверки).
FALSE_CLAIM_PHRASES = (
    "метить их нечем",
    "не заводят шага роли",
    "не заводит шага роли",
    "не заводят шаг роли",
    "не заводит шаг роли",
)

# Существующие тесты подтяжки и эскалаций конфликта подтяжки — адреса, по
# которым AC-5 запрещает «чинить» планку удалением теста.
EXISTING_TESTS = (
    ("tests.test_pull", "PullEvaluateTest",
     ("test_conflict_on_two_file_unresolved_merge_conflict",
      "test_conflict_when_worktree_not_available",
      "test_conflict_on_red_acceptance_after_clean_merge")),
    ("tests.test_branch_freshness_gate", "BranchFreshnessGateTest",
     ("test_advance_escalates_on_pull_conflict_and_aborts",
      "test_approve_escalates_on_pull_conflict_and_aborts")),
    ("tests.test_fsm_map_conflict_autoresolve", "MapConflictAutoResolveTest",
     ("test_map_only_conflict_autoresolves_without_escalation",
      "test_map_plus_other_file_conflict_still_escalates")),
    ("tests.test_artifact_escalation_marker", "RoleStepAnchorAfterTheMarkerTest",
     ("test_return_after_the_marker_blocks_until_the_role_step",
      "test_marker_is_consumed_by_the_first_return")),
)


def comment_text(source: str) -> str:
    """Все комментарии `source` одной нормализованной строкой: комментарий
    занимает несколько строк подряд, и искомое утверждение сегодня
    разорвано переносом («не заводят» / «шага роли») — по отдельной строке
    его не найти."""
    parts = [line.strip().lstrip("#").strip()
             for line in source.splitlines() if line.strip().startswith("#")]
    return re.sub(r"\s+", " ", " ".join(parts))


class MarkerCommentDropsTheFalseClaimTest(unittest.TestCase):
    """AC-5, первая половина: комментарий в `orchestrator/pull.py` не
    утверждает, что из `acceptance`/`merge_gate` возврат из эскалации шага
    роли не заводит. Проверяются комментарии ВСЕГО файла, не только
    соседние с записью метки строки: утверждение не должно выжить и
    переездом на несколько строк выше/в другую функцию того же файла."""

    def test_ac5_pull_py_comments_do_not_claim_the_two_states_have_no_role_step(self):
        """Ни один комментарий `orchestrator/pull.py` не несёт утверждения
        «acceptance/merge_gate не заводят шага роли / метить их нечем».

        Ловит мутацию: разработчик правит только условие записи метки
        (`if state == "in_dev"` -> набор трёх состояний) и оставляет
        соседний комментарий прежним — код и комментарий начинают
        противоречить друг другу, и следующий читатель `pull.py` вернёт
        условие «как написано в комментарии»; `assertNotIn` ниже это
        поймает.
        """
        text = comment_text(inspect.getsource(pull))
        for phrase in FALSE_CLAIM_PHRASES:
            self.assertNotIn(
                phrase, text,
                f"комментарий orchestrator/pull.py всё ещё утверждает "
                f"«{phrase}» — требование 3 объявляет это утверждение ложным "
                f"(эскалация подтяжки не пишет escalated_from, поэтому "
                f"возврат из неё уходит в in_dev из всех трёх состояний)")


class ExistingPullAndEscalationTestsAreNotRemovedTest(unittest.TestCase):
    """AC-5, вторая половина: существующие тесты подтяжки и эскалаций
    остаются на месте — их удаление полный прогон `tests/` видит зелёным,
    поэтому факт наличия фиксируется здесь."""

    def test_ac5_existing_pull_and_escalation_tests_still_exist(self):
        """Каждый перечисленный тестовый метод существует в своём классе
        своего модуля `tests/`.

        Ловит мутацию: тест, покрасневший от правки условия записи метки
        (например, `test_map_plus_other_file_conflict_still_escalates`
        или `test_approve_escalates_on_pull_conflict_and_aborts`), удалён
        или переименован «под новое поведение» вместо починки кода —
        `assertTrue(hasattr(...))` ниже это поймает.
        """
        for module_name, class_name, methods in EXISTING_TESTS:
            module = importlib.import_module(module_name)
            case = getattr(module, class_name, None)
            self.assertIsNotNone(
                case, f"{module_name}: класс {class_name} удалён или "
                f"переименован")
            for method in methods:
                self.assertTrue(
                    hasattr(case, method),
                    f"{module_name}::{class_name}.{method} удалён или "
                    f"переименован — существующие тесты подтяжки и эскалаций "
                    f"задачей не ослабляются и не удаляются")


if __name__ == "__main__":
    unittest.main()
