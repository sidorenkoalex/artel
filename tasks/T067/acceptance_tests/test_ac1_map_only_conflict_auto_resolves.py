"""AC-1 (tasks/T067/SPEC.md): конфликт подтяжки, где единственный
конфликтующий файл — `docs/codebase-map.md`: оркестратор не эскалирует,
а завершает merge сам — merge-коммит создан, содержимое карты
соответствует регенерации на слитом дереве (повторный прогон
`scripts/codebase_map.py` не даёт диффа), подтяжка возвращает тот же
исход, что и подтяжка без конфликта (штатное продолжение — переход
дальше), эскалации не происходит.

Красен до реализации: сегодня (T051) `_pull_main_or_escalate` эскалирует
ЛЮБОЙ конфликт подтяжки без разбора списка конфликтующих файлов — этот
сценарий (конфликт только по карте) при текущем коде уходит в
`escalated`, а не в `review`/`merge_gate`, как проверяют тесты этого
файла.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (MAP_REL, MapConflictRealGitTest,  # noqa: E402
                      PASSING_ACCEPTANCE_TEST, strip_built_at_sha)
from orchestrator import fsm  # noqa: E402


class InDevToReviewMapOnlyConflictAutoResolvesTest(MapConflictRealGitTest):

    def test_ac1_indev_to_review_autoresolves_map_only_conflict(self):
        wt = self.make_worktree()
        self.advance_from_in_dev(wt)
        self.diverge_map_only(wt)
        pre_main_head = self.main_head()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "review",
            "конфликт только по docs/codebase-map.md не имеет права "
            "эскалировать — переход обязан состояться, как и при обычной "
            "подтяжке без конфликта")
        self.assertNotIn("эскалац", out.lower())
        self.assertFalse(
            any("escalat" in (r["action"] or "").lower()
               for r in self.journal_rows()),
            "журнал не должен нести запись об эскалации")

        # merge-коммит фактически создан (2 родителя head'а ветки).
        parents = self.git("log", "-1", "--pretty=%P", cwd=wt).stdout.split()
        self.assertEqual(len(parents), 2,
                         "head ветки задачи обязан быть merge-коммитом "
                         "(2 родителя)")

        status = self.git("status", "--porcelain", cwd=wt).stdout
        self.assertEqual(status.strip(), "",
                         "рабочее дерево worktree обязано быть чистым "
                         "после завершённого merge-коммита")

        committed = (wt / MAP_REL).read_text(encoding="utf-8")
        regen = self.regenerate(wt)
        self.assertEqual(regen.returncode, 0, regen.stderr)
        fresh = (wt / MAP_REL).read_text(encoding="utf-8")
        self.assertEqual(
            strip_built_at_sha(committed), strip_built_at_sha(fresh),
            "содержимое карты после авторазрешения обязано соответствовать "
            "повторному прогону scripts/codebase_map.py (без диффа)")

        self.assertEqual(self.main_head(), pre_main_head,
                         "main не должен измениться самой подтяжкой")


class AcceptanceToMergeGateMapOnlyConflictAutoResolvesTest(MapConflictRealGitTest):

    def test_ac1_acceptance_to_merge_gate_autoresolves_map_only_conflict(self):
        self.set_state("acceptance")
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        self.commit_all(wt, f"{self.TASK}: приёмочные тесты")
        self.diverge_map_only(wt)
        pre_main_head = self.main_head()

        out = self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            "конфликт только по карте не имеет права эскалировать вход "
            "на гейт merge_gate")
        self.assertNotIn("эскалац", out.lower())

        parents = self.git("log", "-1", "--pretty=%P", cwd=wt).stdout.split()
        self.assertEqual(len(parents), 2)

        committed = (wt / MAP_REL).read_text(encoding="utf-8")
        regen = self.regenerate(wt)
        self.assertEqual(regen.returncode, 0, regen.stderr)
        fresh = (wt / MAP_REL).read_text(encoding="utf-8")
        self.assertEqual(strip_built_at_sha(committed), strip_built_at_sha(fresh))

        self.assertEqual(self.main_head(), pre_main_head)


if __name__ == "__main__":
    import unittest
    unittest.main()
