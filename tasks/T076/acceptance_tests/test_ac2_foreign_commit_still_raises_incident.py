"""Зелёный с рождения: сегодня отклонённый переход (fsm.py:770-780,
ветка `tests_writing`) вообще никогда не перефиксирует `fixed_sha`
(`store.record_fixation` не вызывается на этом пути — единственный
вызыватель это `store.set_state` на УСПЕШНОМ переходе,
orchestrator/store.py:431-472), так что посторонний коммит здесь и
сейчас закономерно оставляет `fixed_sha` устаревшим и `check_integrity`
эскалирует «инцидент целостности» — то самое поведение, которое AC-2
требует СОХРАНИТЬ и после того, как AC-1 научит систему различать
«коммит собственного шага» от «постороннего».

Сценарий — SPEC T076, требование 3 / AC-2: коммит, не обёрнутый
журнальным окном «agent run started»/«agent run finished» роли шага
(в отличие от `T076Sandbox.commit_as_test_author`, используемого в
AC-1), должен по-прежнему приводить к эскалации при отклонённом
переходе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fixation, fsm, store  # noqa: E402
from _sandbox import AC_TEST_NO_REDNESS_MARKER, T076Sandbox  # noqa: E402


class Ac2ForeignCommitStillRaisesIncidentTest(T076Sandbox):

    def test_ac2_commit_outside_step_window_keeps_integrity_incident(self):
        entry_sha = self.enter_tests_writing()
        conn = store.db()
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"], entry_sha)

        (self.task_dir() / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_NO_REDNESS_MARKER, encoding="utf-8")
        # Посторонний коммит: НЕ обёрнут журнальными записями «agent run
        # started»/«agent run finished» роли текущего шага (сравни с
        # `commit_as_test_author` в AC-1) — вне окна шага задачи.
        self.commit_task_dir("посторонний коммит вне окна шага")
        committed_sha = self.head()
        self.assertNotEqual(
            committed_sha, entry_sha,
            "подготовка теста не удалась — посторонний коммит не сдвинул голову")

        self.capture(fsm.cmd_advance, self.TASK)  # guard: нет маркера красноты

        # Обычная причина отказа гейта остаётся, как и в AC-1 — этот
        # критерий не про неё, а про то, что эскалация ПО-ПРЕЖНЕМУ поднята.
        self.assertEqual(
            store.get_task(conn, self.TASK)["state"], "tests_writing")

        # fixed_sha НЕ перефиксирован — коммит не принадлежит шагу задачи.
        self.assertEqual(
            store.get_task(conn, self.TASK)["fixed_sha"], entry_sha,
            "AC-2: посторонний коммит не должен приводить к перефиксации "
            "fixed_sha")

        incident = fixation.check_integrity(conn, self.TASK)
        self.assertIsNotNone(
            incident,
            "AC-2: посторонний коммит при отклонённом переходе обязан "
            "по-прежнему приводить к эскалации «инцидент целостности»")
        self.assertIn(entry_sha, incident)
        self.assertIn(committed_sha, incident)

        # Интеграционно — как и раньше: старт шага (`runner.cmd_run`)
        # блокируется эскалацией, агент не запускается (сравни
        # `IntegrityIncidentBlocksRunTest.test_committed_change_after_approve_also_blocks_the_run`,
        # tests/test_git_fixation.py).
        out, popen = self.run_faked()
        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(
            store.get_task(conn, self.TASK)["state"], "escalated",
            "AC-2: посторонний коммит обязан эскалировать инцидент "
            "целостности при старте шага")
        self.assertIn("инцидент целостности", out)


if __name__ == "__main__":
    unittest.main()
