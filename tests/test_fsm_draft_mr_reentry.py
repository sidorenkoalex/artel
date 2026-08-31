"""Регресс-тесты REVIEW.md T079 итерации 1, замечание 1 (major):
`_maybe_ensure_draft_mr` обязан зваться на КАЖДОМ входе задачи в `in_dev`,
не только на шести точках, покрытых предыдущей итерацией — в том числе
на двух пропущенных: возврат из `escalated` (`_cmd_approve`, когда
`escalated_from` пуст или указывает на `in_dev`) и `reject` из
`acceptance` (`_cmd_reject`, унаследованный путь T052).

Белый ящик по `orchestrator/fsm.py`: `confirm_fixation` подменена
константой `True` — сверка фиксации не имеет отношения к точке вызова,
которую здесь проверяем (песочница без git, требование 3 самого
`confirm_fixation` — тот же приём, что и в его собственном докстринге).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"


class DraftMrOnReentryToInDevTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        patcher = mock.patch.object(fsm, "confirm_fixation", lambda *a: True)
        patcher.start()
        self.addCleanup(patcher.stop)
        ensure_patcher = mock.patch.object(fsm.github_adapter, "ensure_draft_mr")
        self.ensure_draft_mr = ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)

    def _insert(self, state: str, **overrides) -> None:
        store.insert_task(store.db(), TASK, "Задача", state,
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        if overrides:
            store.update_task(store.db(), TASK, **overrides)

    def test_approve_from_escalated_with_no_escalated_from_calls_draft_mr(self):
        # Эскалация по лимиту/вердикту ревьювера не пишет escalated_from
        # (fsm.py, докстринг ветки "escalated") — возврат идёт в in_dev
        # по дефолту.
        self._insert("escalated", escalated_from=None, answer_baseline=None)

        fsm._cmd_approve(store.db(), TASK, None, "sid")

        self.assertEqual(store.get_task(store.db(), TASK)["state"], "in_dev")
        self.ensure_draft_mr.assert_called_once()
        self.assertEqual(self.ensure_draft_mr.call_args[0][1], TASK)

    def test_approve_from_escalated_with_escalated_from_in_dev_calls_draft_mr(self):
        # Провал шага разработчика (runner.py) пишет escalated_from="in_dev"
        # явно — возврат тоже ведёт в in_dev, не только дефолтный случай.
        self._insert("escalated", escalated_from="in_dev", answer_baseline=None)

        fsm._cmd_approve(store.db(), TASK, None, "sid")

        self.assertEqual(store.get_task(store.db(), TASK)["state"], "in_dev")
        self.ensure_draft_mr.assert_called_once()

    def test_approve_from_escalated_to_a_non_in_dev_state_skips_draft_mr(self):
        # Возврат из эскалации в состояние, отличное от in_dev (провал
        # шага analyst/test_author), не должен заводить Draft MR — узел
        # остаётся побочным эффектом входа именно в in_dev.
        self._insert("escalated", escalated_from="spec_writing",
                    answer_baseline=None)

        fsm._cmd_approve(store.db(), TASK, None, "sid")

        self.assertEqual(store.get_task(store.db(), TASK)["state"],
                         "spec_writing")
        self.ensure_draft_mr.assert_not_called()

    def test_reject_from_acceptance_calls_draft_mr(self):
        self._insert("acceptance", accept_rejects=0)

        fsm._cmd_reject(store.db(), TASK, "не готово")

        self.assertEqual(store.get_task(store.db(), TASK)["state"], "in_dev")
        self.ensure_draft_mr.assert_called_once()
        self.assertEqual(self.ensure_draft_mr.call_args[0][1], TASK)

    def test_reject_from_acceptance_past_the_limit_escalates_without_draft_mr(self):
        # Лимит отказов приёмки исчерпан (config.LIMIT_ACCEPT_REJECTS) —
        # задача уходит в escalated, не in_dev: Draft MR тут заводить
        # не с чего.
        self._insert("acceptance", accept_rejects=config.LIMIT_ACCEPT_REJECTS)

        fsm._cmd_reject(store.db(), TASK, "снова не готово")

        self.assertEqual(store.get_task(store.db(), TASK)["state"],
                         "escalated")
        self.ensure_draft_mr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
