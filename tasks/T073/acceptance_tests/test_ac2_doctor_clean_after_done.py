"""AC-2 (tasks/T073/SPEC.md): после перехода в `done` `doctor` не
отмечает orphan-инцидент по уже закрытой задаче (проверки ветки/worktree
для неё зелёные).

Красен до реализации: `doctor.check_orphans` уже сегодня считает
orphan-инцидентом ветку `done`/`killed`-задачи, всё ещё существующую в
git (`orchestrator/doctor.py` `stale = [... r["state"] in ("done",
"killed") and gitcmd.branch_exists(r["branch"])]`, `Check
("orphans-branches", "fail", ...)`) — до появления кода AC-1 (уборка
ветки при done) этот `fail` наступает у ЛЮБОЙ смерженной задачи, что и
показывает T073 «Контекст» (Оператор руками чистил 18 веток). Тест
красен по этой самой причине, не по ошибке в самом тесте.
"""
import unittest

from orchestrator import alerts, doctor, store  # noqa: E402

from _sandbox import DoneTaskTest  # noqa: E402


class DoctorCleanAfterDoneTest(DoneTaskTest):

    def test_ac2_doctor_sees_no_orphan_branch_or_worktree_after_done(self):
        out = self.approve()
        self.assertEqual(self.state(), "done", out)

        conn = store.db()
        checks = doctor.check_orphans(conn)
        by_name = {c.name: c for c in checks}

        self.assertEqual(by_name["orphans-branches"].status, "ok",
                         by_name["orphans-branches"].detail)
        self.assertNotIn(self.branch, by_name["orphans-branches"].detail)
        self.assertEqual(by_name["orphans-worktrees"].status, "ok",
                         by_name["orphans-worktrees"].detail)
        self.assertNotIn(self.TASK, by_name["orphans-worktrees"].detail)

        branch_incidents = [a for a in alerts.open_alerts(conn, "incident")
                           if a["source"] == "doctor.orphans.branch"
                           and self.branch in a["message"]]
        self.assertEqual(branch_incidents, [])
        worktree_incidents = [a for a in alerts.open_alerts(conn, "incident")
                              if a["source"] == "doctor.orphans.worktree"
                              and self.TASK in a["message"]]
        self.assertEqual(worktree_incidents, [])


if __name__ == "__main__":
    unittest.main()
