"""AC-7 (SPEC): условия ADR-0007 п.3 б) полный прогон приёмочных тестов
задачи зелёный, в) полный набор `tests/` зелёный, г) бюджет задачи не
превышен, д) вердикт ревью approved текущей итерации — не изменены этой
правкой: поведение автогейта по этим условиям (порядок проверки,
причины отказа, короткое замыкание на первом невыполненном условии)
остаётся прежним.

Условие «б» (приёмочные тесты задачи зелёные) к моменту вызова
`_autogate_conditions` уже гарантированно выполнено кодом, ведущим к
состоянию `acceptance` (см. докстринг самой функции) — здесь не
проверяется отдельным отказом, только присутствие в перечне `ok` (уже
покрыто `test_ac2`).

Красен до реализации: планка этого файла закоммичена ТОЛЬКО в
артефактную ветку (`CLEAN_PLANKA`, как и в AC-2) — сегодняшний код
читает условие «а» с диска (`acc_tdir`, пустой после A7) и отказывает
ДО того, как вообще дойти до заглушенных здесь б/в/г/д, с причиной
«каталог приёмочных тестов пуст или отсутствует» вместо ожидаемых
причин б/в/г/д этого файла — все четыре теста краснеют именно на этом
несовпадении. Эта задача не трогает код самих условий б/в/г/д
(`workspace.on_task_branch`, `acceptance.run_full_suite`,
`budget.budget_block`, ok.append «вердикт REVIEW...», SPEC «Не
входит») — только источник чтения условия «а»; после его переключения
на ветку (планка снова видна) поведение б/в/г/д обязано остаться тем
же, что проверяют тесты этого файла.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateBranchSandbox, CLEAN_PLANKA  # noqa: E402
from orchestrator import acceptance, budget, fsm_autogate, store, workspace  # noqa: E402


class Adr0007ConditionsBVGDUnchangedTest(AutogateBranchSandbox):

    def setUp(self):
        super().setUp()
        self.seed_planka(CLEAN_PLANKA)

    def _call(self, *, on_task_branch=True, run_full_suite=(True, ""),
              budget_block=None, iteration=1):
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        with mock.patch.object(workspace, "on_task_branch",
                               return_value=on_task_branch), \
             mock.patch.object(workspace, "path", return_value=self.root), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=run_full_suite), \
             mock.patch.object(budget, "budget_block",
                               return_value=budget_block):
            return fsm_autogate._autogate_conditions(
                conn, self.TASK, t, self.stale_disk_dir(), iteration)

    def test_ac7_condition_v_worktree_not_ready_blocks_before_full_suite_run(self):
        """Условие «в» (полный набор `tests/`) требует worktree ветки
        задачи заведённым (`workspace.on_task_branch` не `True`) —
        блокирует ДО прогона полного набора, с прежней формулировкой
        причины, и не доходит до условий г/д.

        Ловит мутацию: если проверку worktree уберут или переставят
        ПОСЛЕ прогона `acceptance.run_full_suite`, `run_full_suite`
        (заглушенный на `(False, ...)`, легко отличимая формулировка)
        оказался бы вызван и/или причина сменилась бы на «полный набор
        tests/ красный» вместо «worktree задачи не заведён».
        """
        ok, reason = self._call(on_task_branch=False,
                                run_full_suite=(False, "MARKER-НЕ-ВЫЗЫВАЛСЯ"))

        self.assertEqual(
            reason,
            "автогейт: полный набор tests/ не проверен — worktree "
            "задачи не заведён")
        combined = "; ".join(ok)
        self.assertNotIn(
            "worktree ветки зелёный", combined,
            "короткое замыкание: условие «в» не имеет права попасть в "
            "перечень выполненных, если сам же и отказал")
        self.assertNotIn("бюджет", combined,
                         "короткое замыкание: условие «г» не имеет права "
                         "попасть в перечень после отказа на «в»")
        self.assertNotIn("REVIEW", combined,
                         "короткое замыкание: условие «д» не имеет права "
                         "попасть в перечень после отказа на «в»")

    def test_ac7_condition_v_red_full_suite_blocks_before_budget_check(self):
        """Условие «в»: полный набор `tests/` красный — блокирует с
        прежней причиной «полный набор tests/ красный», раньше условия
        «г» (бюджет), даже если бюджет ТОЖЕ пробит.

        Ловит мутацию: если порядок проверки «в»/«г» поменяют местами,
        при одновременном срабатывании обоих условие «г» (заглушенное
        здесь на отказ) обогнало бы «в», и `reason` стал бы «бюджет
        задачи исчерпан» вместо ожидаемого «полный набор tests/
        красный».
        """
        ok, reason = self._call(run_full_suite=(False, "красный хвост"),
                                budget_block="автогейт: бюджет задачи "
                                             "исчерпан")

        self.assertEqual(reason, "автогейт: полный набор tests/ красный")
        self.assertNotIn("полный набор tests/ в worktree ветки зелёный", ok)

    def test_ac7_condition_g_budget_exhausted_blocks_with_named_reason(self):
        """Условие «г» (бюджет) — единственное невыполненное условие —
        блокирует с прежней причиной «автогейт: бюджет задачи исчерпан»,
        остальные условия (а, б, в) попадают в перечень выполненных.

        Ловит мутацию: если причину отказа по бюджету изменят или
        перестанут проверять `budget.budget_block` вовсе (переход
        пройдёт до конца, `reason is None`).
        """
        ok, reason = self._call(budget_block="неважно какая строка "
                                             "budget.budget_block")

        self.assertEqual(reason, "автогейт: бюджет задачи исчерпан")
        combined = "; ".join(ok)
        self.assertIn(
            "worktree ветки зелёный", combined,
            "условие «в» выполнено (заглушено на успех) — обязано "
            "остаться в перечне")
        self.assertNotIn("REVIEW", combined,
                         "короткое замыкание: условие «д» не имеет права "
                         "попасть в перечень после отказа на «г»")

    def test_ac7_condition_d_review_iteration_ok_entry_uses_passed_iteration(self):
        """Условие «д» (вердикт REVIEW approved текущей итерации) — все
        условия выполнены, перечень `ok` несёт формулировку с НОМЕРОМ
        итерации, ПЕРЕДАННЫМ аргументом (не захардкоженной единицей).

        Ловит мутацию: если реализация подставит литерал `1` вместо
        параметра `iteration`, вызов с `iteration=7` не найдёт «(7)» в
        перечне.
        """
        ok, reason = self._call(iteration=7)

        self.assertIsNone(reason)
        self.assertIn("вердикт REVIEW approved текущей итерации (7)",
                      "; ".join(ok))


if __name__ == "__main__":
    unittest.main()
