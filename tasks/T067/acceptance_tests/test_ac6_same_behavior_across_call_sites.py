"""AC-6 (tasks/T067/SPEC.md): авторазрешение работает одинаково независимо
от того, из какой точки вызвана подтяжка (`in_dev -> review`,
`acceptance -> merge_gate`, внутри окна `merge_gate` по T053) — общей
функцией, без дублирования логики между точками вызова.

Три точки вызова `_pull_main_or_escalate` — общий узел, существующий с
T051/T053 (`orchestrator/fsm.py`, докстринг функции); этот файл проверяет
поведенческий срез критерия — конфликт только по карте авторазрешается
одинаково из ЛЮБОЙ из трёх точек. «Без дублирования логики» — структурное
следствие того, что все три сценария наблюдают ОДНО И ТО ЖЕ поведение при
вызове ОДНОЙ функции (её сигнатура не меняется, докстринг явно называет
все три точки её потребителями) — отдельный текст на каждую точку
подразумевал бы именно дублирование, которого требование 6 запрещает.

Красен до реализации: как и AC-1 — сегодня (T051/T053) любой конфликт
подтяжки эскалирует безусловно в каждой из трёх точек; все три сценария
здесь ожидают продолжения без эскалации.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (MAP_REL, MapConflictRealGitTest,  # noqa: E402
                      PASSING_ACCEPTANCE_TEST, strip_built_at_sha)
from orchestrator import fsm  # noqa: E402


class InDevToReviewCallSiteTest(MapConflictRealGitTest):

    def test_ac6_indev_to_review_call_site_autoresolves(self):
        wt = self.make_worktree()
        self.advance_from_in_dev(wt)
        self.diverge_map_only(wt)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")
        committed = (wt / MAP_REL).read_text(encoding="utf-8")
        regen = self.regenerate(wt)
        self.assertEqual(regen.returncode, 0, regen.stderr)
        self.assertEqual(strip_built_at_sha(committed),
                         strip_built_at_sha((wt / MAP_REL).read_text(encoding="utf-8")))


class AcceptanceToMergeGateCallSiteTest(MapConflictRealGitTest):

    def test_ac6_acceptance_to_merge_gate_call_site_autoresolves(self):
        self.set_state("acceptance")
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        self.commit_all(wt, f"{self.TASK}: приёмочные тесты")
        self.diverge_map_only(wt)

        self.approve()

        self.assertEqual(self.state(), "merge_gate")
        committed = (wt / MAP_REL).read_text(encoding="utf-8")
        regen = self.regenerate(wt)
        self.assertEqual(regen.returncode, 0, regen.stderr)
        self.assertEqual(strip_built_at_sha(committed),
                         strip_built_at_sha((wt / MAP_REL).read_text(encoding="utf-8")))


class MergeGateWindowCallSiteTest(MapConflictRealGitTest):

    def test_ac6_merge_gate_window_call_site_autoresolves(self):
        self.set_state("acceptance")
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        self.commit_all(wt, f"{self.TASK}: приёмочные тесты")
        # Вход на гейт — ветка ещё не отставала на этом шаге, конфликта
        # ещё нет.
        self.approve()
        self.assertEqual(self.state(), "merge_gate",
                         "предпосылка теста: вход на гейт обязан пройти")

        # main уходит вперёд, ПОКА задача стоит на гейте merge_gate —
        # сверка внутри окна (T053) обязана справиться с конфликтом карты
        # так же, как и остальные две точки.
        self.diverge_map_only(wt)

        out = self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            "подтяжка внутри окна не имеет права мержить в main в этом же "
            "вызове (T053, инвариант 19) — задача остаётся на гейте, даже "
            "когда сама подтяжка потребовала авторазрешения конфликта "
            "карты")
        self.assertNotIn("эскалац", out.lower())
        self.assertFalse(
            any("escalat" in (r["action"] or "").lower()
               for r in self.journal_rows()))

        committed = (wt / MAP_REL).read_text(encoding="utf-8")
        regen = self.regenerate(wt)
        self.assertEqual(regen.returncode, 0, regen.stderr)
        self.assertEqual(strip_built_at_sha(committed),
                         strip_built_at_sha((wt / MAP_REL).read_text(encoding="utf-8")))


if __name__ == "__main__":
    import unittest
    unittest.main()
