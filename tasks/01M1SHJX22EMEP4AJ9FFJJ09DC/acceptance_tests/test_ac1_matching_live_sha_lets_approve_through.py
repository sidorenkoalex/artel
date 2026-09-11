"""AC-1 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «`approve <id>» без
аргумента на гейтах spec_gate, acceptance, merge_gate и escalated читает
живой sha артефактов задачи тем же источником, которым сегодня печатается
подсказка approve, и сверяет его с зафиксированным на последнем переходе
sha и чистотой рабочей копии/артефактной ветки.»

Юнит-контур на саму функцию `fsm.confirm_fixation` (гейт-агностичную —
её вызывает `_cmd_approve` одинаково для всех четырёх состояний
`fsm.APPROVE_NEEDS_SHA`), с замоканным `fixation.read`: живой git не
нужен, предмет проверки — САМ факт сравнения живого значения с
`tasks.fixed_sha`. Отрицательный исход сравнения (расхождение/грязная
копия) — отдельный файл `test_ac1_diverged_or_dirty_live_sha_blocks_
approve.py` (уже сегодня зелёный по другой причине, см. его маркер).

Красен до реализации: сегодня `confirm_fixation` при `sha is None`
безусловно печатает «approve требует sha» и возвращает `False`, даже
если живое чтение (`fixation.read`) совпадает с `tasks.fixed_sha` и
копия чистая, — сравнения с колонкой не происходит вовсе. Прогнано:
`assertTrue(result, ...)` падает на `False is not true`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fixation, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ConfirmFixationMatchingLiveShaLetsApproveThroughTest(TmpRootTest):
    """`confirm_fixation(conn, task_id, None)` при живом совпадении."""

    TASK = "T900"
    FIXED_SHA = "a" * 40

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача", "spec_gate",
                          "task/t900-x", config.DEFAULT_TARGET, 50.0)
        store.update_task(self.conn, self.TASK, fixed_sha=self.FIXED_SHA)

    def test_ac1_matching_live_sha_and_clean_copy_lets_approve_through(self):
        """Живое чтение (`fixation.read`, тот же источник, что и подсказка
        approve) совпадает с `tasks.fixed_sha`, копия чистая — `confirm_
        fixation(None)` обязана вернуть `True` без запроса sha у Оператора.

        Ловит мутацию: сегодняшний код возвращает `False` безусловно на
        ветке `sha is None` — этот ассерт красен именно по этой причине
        (`fixation.read` вызывается сегодня для печати подсказки, но
        результат не используется для сравнения).
        """
        with mock.patch.object(fixation, "read",
                               return_value=(self.FIXED_SHA, True)) as read_mock:
            result = fsm.confirm_fixation(self.conn, self.TASK, None)

        read_mock.assert_called_once_with(self.TASK, config.DEFAULT_TARGET)
        self.assertTrue(result, "живое совпадение обязано пропускать approve")


if __name__ == "__main__":
    unittest.main()
