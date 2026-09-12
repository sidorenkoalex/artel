"""AC-7 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md), сценарий (а): main
продвинулся только коммитом `docs/backlog.md`, в ветке задачи нет
merge-коммита подтяжки, `pull.evaluate` возвращает `Fresh`, в журнале
есть запись «свежесть: …»; мутационный тест, эмулирующий «подтяжка всё
равно выполняется», — красный.

Красен до реализации: правило AC-1 не реализовано — `pull.evaluate`
безусловно выполняет `git merge` при `behind > 0`, поэтому голова
worktree сдвигается и/или исход не `Fresh` (`grep -n "свежесть:"
orchestrator/pull.py` пуст) — ровно та же причина, что и требует AC-7
(«мутационный тест … красный»), только сейчас ею является сам
неисправленный код, а не гипотетическая мутация.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import pull  # noqa: E402


class ScenarioABacklogOnlyMainAdvanceStaysFreshTest(PullFreshnessSandbox):

    def test_ac7_scenario_a_backlog_only_main_advance_stays_fresh_without_merge(self):
        """main продвигается РОВНО ОДНИМ документным коммитом
        (`docs/backlog.md`), ветка задачи его не касается — `pull.
        evaluate` обязан вернуть `Fresh`, голова worktree ветки задачи
        обязана остаться НЕИЗМЕННОЙ (никакого merge-коммита подтяжки), и
        в журнале обязана появиться запись «свежесть: …».

        Ловит мутацию, буквально требуемую AC-7 («подтяжка всё равно
        выполняется»): `evaluate` игнорирует новую классификацию AC-1 и
        уходит в обычный `git merge` — голова worktree сдвинулась бы на
        merge-коммит, `assertEqual(head_after, head_before)` и
        `assertEqual(outcome, Fresh())` оба покраснели бы."""
        self.branch_off_main()
        self.commit_on_branch({"orchestrator/ac7_marker.py": "# ветка\n"},
                              f"{self.TASK}: правка ветки")
        head_before = self.worktree_head()
        self.add_main_commit({"docs/backlog.md": "строка копилки\n"},
                             "оператор: копилка — строка")

        outcome = self.evaluate()

        self.assertEqual(outcome, pull.Fresh())
        self.assertEqual(self.worktree_head(), head_before,
                         "подтяжка не имеет права коснуться ветки задачи — "
                         "merge-коммита в ветке появиться не должно")
        self.assertTrue(any(
            r["action"] == "свежесть: 1 документных коммитов main без подтяжки"
            for r in self.journal_rows()))


if __name__ == "__main__":
    unittest.main()
