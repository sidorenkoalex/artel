"""AC-8 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): approve merge_gate
при отсутствии sha головы ветки задачи в origin выполняет авто-push
тем же хелпером, что AC-3, журналирует его и продолжает approve в том
же вызове; при уже допушенной голове поведение approve не меняется и
попытки push нет.

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-8 (объединяет оба исхода одного критерия — отсутствие и
присутствие головы в origin — двумя методами).

Задача входит в `merge_gate` уже с полностью синхронным origin
(`_sandbox.HeadInOriginSandbox.enter_merge_gate` пушит голову ветки
после REVIEW.md) — «отсутствие головы» здесь смоделировано новым
коммитом ПОСЛЕ входа на гейт (сценарий не важен — SPEC требование 7
проверяет саму голову, не причину расхождения), не пушенным до approve.

Красен до реализации: сегодня `orchestrator/fsm_merge_gate.py::
_cmd_approve_merge_gate` не сверяет origin вовсе — approve доходит до
`done`, а origin остаётся со старой (допост-гейтной) головой ветки
задачи. Проверено прогоном на немодифицированном коде при подготовке
файла.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import HeadInOriginSandbox  # noqa: E402


class Ac8MergeGateAutoPushTest(HeadInOriginSandbox):

    def test_ac8_head_missing_from_origin_triggers_auto_push_and_continues(self):
        """Новый коммит ПОСЛЕ входа на merge_gate не запушен — approve
        обязан сам опубликовать актуальную голову и довести задачу до
        `done` тем же вызовом.

        Ловит мутацию: код, который проверяет origin только на входе В
        merge_gate (не в начале самого approve) — коммит, сделанный
        ПОСЛЕ входа на гейт (этот сценарий), остался бы неопубликован,
        и `origin_branch_sha()` после approve не совпал бы с головой.
        """
        self.enter_merge_gate()
        (self.task_dir() / "note.txt").write_text(
            "правка после входа на гейт\n", encoding="utf-8")
        expected_head = self.commit_task_dir("правка после входа на гейт")
        self.assertNotEqual(
            self.origin_branch_sha(), expected_head,
            "предпосылка теста: origin ещё не видел новую голову")
        since = len(self.steps())

        self.approve()

        self.assertEqual(self.state(), "done")
        self.assertEqual(
            self.origin_branch_sha(), expected_head,
            "AC-8: origin обязан получить push именно этой головы до "
            "merge")
        self.assertIn(
            "push", self.journal_tail(since),
            "AC-8: успешный авто-push обязан быть журналирован")

    def test_ac8_head_already_pushed_does_not_change_behavior(self):
        """Голова ветки задачи уже в origin к моменту approve —
        поведение не меняется, попытки push нет.

        Ловит мутацию: код, добавляющий БЕЗУСЛОВНЫЙ push на каждый
        approve merge_gate, даже когда голова уже там — сравнением sha
        origin до/после (должны совпасть, ветка задачи после успешного
        merge локально убирается, поэтому сверяется именно origin, не
        локальный branch_head) и отсутствием "push" в новых записях
        журнала.
        """
        self.enter_merge_gate()
        pre_origin_sha = self.origin_branch_sha()
        self.assertNotEqual(
            pre_origin_sha, "",
            "предпосылка теста: голова ветки задачи уже в origin на "
            "входе в merge_gate")
        since = len(self.steps())

        self.approve()

        self.assertEqual(self.state(), "done")
        tail = self.journal_tail(since)
        self.assertNotIn(
            "push", tail,
            f"AC-8: approve не должен был журналировать push, когда "
            f"голова уже в origin: {tail!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
