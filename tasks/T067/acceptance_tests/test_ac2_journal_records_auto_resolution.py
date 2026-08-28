"""AC-2 (tasks/T067/SPEC.md): в сценарии AC-1 в журнал задачи попадает
запись об авторазрешении конфликта карты: actor=orchestrator, файл
`docs/codebase-map.md`, способ разрешения (регенерация).

Красен до реализации: сегодня (T051) конфликт подтяжки, даже только по
карте, эскалирует — переход в `review` не происходит вовсе, а журнал
не несёт записи об авторазрешении (её ещё нет).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (MAP_REL, MapConflictRealGitTest,  # noqa: E402
                      PASSING_ACCEPTANCE_TEST)
from orchestrator import fsm  # noqa: E402


class JournalRecordsMapAutoResolutionTest(MapConflictRealGitTest):

    def test_ac2_journal_records_actor_file_and_method(self):
        wt = self.make_worktree()
        self.advance_from_in_dev(wt)
        self.diverge_map_only(wt)

        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review",
                         "предпосылка теста: авторазрешение обязано пройти "
                         "(см. AC-1)")

        rows = self.journal_rows()
        matching = [r for r in rows
                   if (r["actor"] or "") == "orchestrator"
                   and MAP_REL in (r["detail"] or "")]
        self.assertTrue(
            matching,
            f"нет записи журнала actor=orchestrator, называющей "
            f"{MAP_REL}; журнал: "
            f"{[(r['actor'], r['action'], r['detail']) for r in rows]}")

        text = " ".join(
            f"{r['action'] or ''} {r['detail'] or ''}" for r in matching
        ).lower()
        self.assertTrue(
            any(k in text for k in ("регенерац", "regen")),
            f"запись обязана называть способ разрешения (регенерация): "
            f"{text!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
