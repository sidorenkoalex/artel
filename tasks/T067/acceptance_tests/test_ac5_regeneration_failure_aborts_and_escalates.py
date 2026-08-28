"""AC-5 (tasks/T067/SPEC.md): регенерация карты при авторазрешении
(сценарий AC-1) завершается ненулевым кодом возврата: оркестратор
выполняет `git merge --abort`, задача переходит в `escalated`, ветка
задачи остаётся в состоянии до подтяжки — полусмерженного состояния
(незавершённый merge, застейдженная правка) не остаётся.

Красен до реализации: `_sandbox.py::BROKEN_GENERATOR_TEMPLATE` пишет
файл-маркер по абсолютному пути ВНЕ git-дерева и только потом падает
ненулевым кодом — тест проверяет, что этот файл появился, то есть что
оркестратор ДЕЙСТВИТЕЛЬНО запустил генератор на слитом дереве (не текст
диагностики, который SPEC дословно не фиксирует). Сегодня (T051)
конфликт эскалирует безусловно, ДО какой-либо попытки авторазрешения —
до генератора дело не доходит вовсе, маркер не появляется, и именно по
этой причине тест красный (не по случайному совпадению исхода
«escalated», которое старый код тоже дал бы, но по другой причине).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MapConflictRealGitTest, PASSING_ACCEPTANCE_TEST  # noqa: E402
from orchestrator import fsm  # noqa: E402


class RegenerationFailureAbortsAndEscalatesTest(MapConflictRealGitTest):

    broken_generator = True

    def test_ac5_broken_generator_aborts_merge_and_escalates(self):
        wt = self.make_worktree()
        self.advance_from_in_dev(wt)
        self.diverge_map_only(wt)
        pre_branch_head = self.branch_head()
        pre_main_head = self.main_head()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "провал регенерации при авторазрешении обязан эскалировать, "
            "а не оставлять полусмерженное состояние")
        self.assertEqual(self.branch_head(), pre_branch_head,
                         "ветка задачи обязана остаться в состоянии до "
                         "подтяжки")
        self.assertEqual(self.main_head(), pre_main_head,
                         "main не должен измениться")
        self.assert_no_merge_in_progress(wt)

        self.assertTrue(
            self.regen_marker_path.exists(),
            "генератор карты (scripts/codebase_map.py) не был запущен на "
            "слитом дереве — эскалация обязана случиться ПОСЛЕ попытки "
            "регенерации, а не вместо неё")


if __name__ == "__main__":
    import unittest
    unittest.main()
