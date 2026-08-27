"""AC-4 (tasks/T048/SPEC.md): немедленный `kill` только что созданной
задачи оставляет main чистым (инвариант 15 и тесты T008/T020 живы —
см. tests/test_kill_cleanup.py, не дублируются здесь), полный текст
`TZ.md` (если он был) попадает в журнал БД записью `kill`, и последующий
`merge_gate` любой другой задачи доставляет killed-RETRO, чья «Суть»
построена из текста ТЗ, взятого из журнала.

Доставка killed-RETRO конкретно на `merge_gate` — уже устроенный и
протестированный механизм (SPEC T043, `orchestrator/fsm.py
_generate_and_commit_retro` подбирает killed-долги через
`retro.build_killed`, см. tests/test_fsm_retro.py); здесь проверяется
именно то, что меняет T048 — что сам генератор `retro.build_killed`
берёт «Суть» из текста ТЗ, положенного в журнал требованием 5, вызывая
его напрямую (тем же приёмом, что tests/test_retro.py), без повторной
симуляции всего цикла merge_gate соседней задачи.
"""
import unittest

from orchestrator import cleanup, retro, store  # noqa: E402

from _sandbox import TmpGitTaskTest  # noqa: E402

TITLE = "Мгновенный kill новой задачи"
TZ_MARKER = "AC4-МАРКЕР-УНИКАЛЬНОГО-ТЕКСТА-ТЗ"
TZ_TEXT = f"Первая строка ТЗ.\n{TZ_MARKER} — вторая строка с деталями.\n"


class KillJournalsTzAndFeedsRetroTest(TmpGitTaskTest):

    def test_ac4_kill_right_after_new_leaves_main_clean_and_feeds_retro_from_journal(self):
        tz_path = self.write_tz_file(TZ_TEXT)
        self.cli_new(TITLE, tz_path)
        row = self.last_task_row()
        task_id, branch = row["id"], row["branch"]

        self.capture(cleanup.cmd_kill, task_id)

        self.assertEqual(self.task_row(task_id)["state"], "killed")
        self.assertEqual(
            self.git("status", "--porcelain").stdout, "",
            "main обязан остаться чистым и после немедленного kill")
        self.assertFalse(
            self.branch_exists(branch),
            "неслитая ветка убитой задачи обязана быть убрана как раньше")

        conn = store.db()
        steps = store.task_steps(conn, task_id)
        journaled = "\n".join(s["detail"] or "" for s in steps)
        self.assertIn(
            TZ_TEXT.strip(), journaled,
            "полный текст TZ.md обязан попасть в журнал БД записью kill "
            "до удаления ветки")

        retro_text = retro.build_killed(conn, task_id)
        self.assertIn(
            TZ_MARKER, retro_text,
            "«Суть» killed-RETRO обязана строиться из текста ТЗ, "
            "взятого из журнала, а не из пустого шаблона SPEC.md")


if __name__ == "__main__":
    unittest.main()
