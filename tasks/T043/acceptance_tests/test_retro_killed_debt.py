"""Приёмочные тесты T043 — AC-2, AC-8, AC-9 (половина killed-задачи).

Ред. Оператора 27.08 (`tasks/T043/TZ.md`, «Ответ Оператора на эскалацию
test_author», решение (d)) разрешила блокер, из-за которого предыдущий
прогон этой роли эскалировал ровно эти три критерия
(`git log` T043: `69239ae`): `kill` НЕ трогает main вовсе (инвариант 15,
`tests/test_invariants.py::KillKeepsMainIntactTest`, цел буквально), а
killed-RETRO доставляет в main следующий `merge_gate` ЛЮБОЙ другой,
живой задачи — тем же push, что и её собственный done-RETRO/merge.

`Ac2KillDoesNotTouchMainTest` — первая половина AC-2 (kill сам по себе).
`Ac2Ac8Ac9KilledRetroDebtTest` — вторая половина AC-2 (подбор долга на
ближайшем `merge_gate`) плюс AC-8 (цитата эскалации) и AC-9 (пометка
адреса killed-задачи вместо `<merge-sha>:tasks/<id>/`); форма адреса
done-задачи уже проверена в `test_retro_done.py::Ac1DoneRetroTest`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, store  # noqa: E402
from retro_sandbox import MERGE_SHA, RetroSandboxTest  # noqa: E402

ESCALATION_TEXT = "нужна помощь Оператора: неясен объём (killed-задача)"


class Ac2KillDoesNotTouchMainTest(RetroSandboxTest):
    """AC-2 (первая половина): `kill` (с любой текущей ветки) не создаёт
    ни коммитов, ни файлов RETRO в рабочем дереве; существующая уборка
    (каталог, ветка) выполняется как прежде, без исключений."""

    def setUp(self):
        super().setUp()
        self.other = self.new_task("Убиваемая задача")
        self.other_branch = self.task_row(self.other)["branch"]

    def _assert_main_untouched(self) -> None:
        subcommands = self.git_subcommands()
        self.assertNotIn(
            "commit", subcommands,
            "kill не должен коммитить в main (инвариант 15, требование 2)")
        self.assertNotIn(
            "push", subcommands,
            "kill не должен пушить в main (инвариант 15, требование 2)")
        self.assertFalse(
            self.retro_path(self.other).exists(),
            "kill не должен писать файл RETRO в рабочее дерево "
            "(инвариант 15, требование 2)")

        self.assertEqual(self.task_row(self.other)["state"], "killed")
        journal = "\n".join(
            f"{s['action']} {s['detail']}"
            for s in store.task_steps(store.db(), self.other))
        self.assertIn("уборка", journal,
                      "существующая уборка (каталог/ветка) должна "
                      "выполняться как прежде")

    def test_ac2_kill_from_main_leaves_main_untouched(self):
        self.kill(task=self.other, current_branch=config.MAIN_BRANCH)

        self._assert_main_untouched()

    def test_ac2_kill_from_task_branch_leaves_main_untouched(self):
        self.kill(task=self.other, current_branch=self.other_branch)

        self._assert_main_untouched()


class Ac2Ac8Ac9KilledRetroDebtTest(RetroSandboxTest):
    """AC-2 (вторая половина) + AC-8 + AC-9: killed-RETRO без ветки
    (истории в main нет) прилетает на ближайшем `merge_gate` другой,
    живой задачи — тем же push, что и её merge, с полями требований 6-8
    (причина снятия, полная цитата последней эскалации, пометка адреса)."""

    def setUp(self):
        super().setUp()
        self.other = self.new_task("Убиваемая задача")
        self.add_escalation(ESCALATION_TEXT, task=self.other)

        self.kill(task=self.other, current_branch=config.MAIN_BRANCH)
        self.assertEqual(self.task_row(self.other)["state"], "killed")
        self.assertFalse(
            self.retro_path(self.other).exists(),
            "killed-RETRO не должен появляться до ближайшего merge_gate")

        # Ближайший merge_gate — ДРУГОЙ, живой задачи (self.TASK).
        self.write_context_spec()
        self.set_state("merge_gate")

    def test_ac2_next_merge_gate_delivers_killed_retro_same_push(self):
        self.approve()

        self.assertEqual(self.state(), "done")
        subcommands = self.git_subcommands()
        self.assertIn("push", subcommands)
        push_index = subcommands.index("push")
        self.assertIn(
            "commit", subcommands[:push_index],
            "коммит killed-RETRO подобранного долга должен уйти тем же "
            "push, что и merge живой задачи (требование 2)")

        text = self.retro_text(self.other)
        self.assertIn(self.other, text, "нет id убитой задачи")
        self.assertIn(
            "kill switch", text,
            "нет причины снятия (запись kill в журнале steps, "
            "требование 6)")

    def test_ac8_killed_retro_quotes_last_escalation_verbatim(self):
        self.approve()

        text = self.retro_text(self.other)
        self.assertIn(
            ESCALATION_TEXT, text,
            "нет полного дословного текста последней эскалации "
            "(state -> escalated, требование 7)")

    def test_ac9_killed_retro_has_no_artifacts_address_placeholder(self):
        self.approve()

        text = self.retro_text(self.other)
        self.assertIn(
            "артефакты не сохранены (ветка удалена при kill)", text,
            "нет пометки об отсутствии адреса артефактов killed-задачи "
            "(требование 8)")
        self.assertNotIn(
            f"{MERGE_SHA}:tasks/{self.other}/", text,
            "killed-RETRO не должен содержать форму адреса done-задачи "
            "(требование 8)")


if __name__ == "__main__":
    import unittest
    unittest.main()
