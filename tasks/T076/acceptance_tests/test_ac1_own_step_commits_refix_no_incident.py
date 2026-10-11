"""Красен до реализации: сегодня отклонённый переход (fsm.py:770-780,
ветка `tests_writing`, ошибки трассируемости/маркера красноты) только
журналит отказ и возвращает `False` — `store.record_fixation` не
вызывается нигде на этом пути (единственный вызыватель — `store.set_state`
на УСПЕШНОМ переходе, orchestrator/store.py:431-472). `fixed_sha` поэтому
остаётся тем, что было на входе в `tests_writing`, а собственный коммит
test_author внутри шага уводит голову ветки вперёд — тест ждёт
перефиксации и отсутствия инцидента, которых код пока не производит.

Сценарий — T069/T073 (tasks/T076/SPEC.md, «Контекст», AC-1): test_author
легитимно коммитит `acceptance_tests/` внутри шага, guard отклоняет
переход `tests_writing -> in_dev` по отсутствию маркера красноты
(SPEC T064) — единственный новый коммит порождён самим шагом задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fixation, fsm, store  # noqa: E402
from _sandbox import AC_TEST_NO_REDNESS_MARKER, T076Sandbox  # noqa: E402


class Ac1OwnStepCommitRefixesTest(T076Sandbox):

    def test_ac1_role_commit_inside_rejected_step_refixes_sha_without_incident(self):
        entry_sha = self.enter_tests_writing()
        conn = store.db()
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"], entry_sha)

        (self.task_dir() / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_NO_REDNESS_MARKER, encoding="utf-8")
        self.commit_as_test_author("acceptance_tests от test_author")
        committed_sha = self.head()
        self.assertNotEqual(
            committed_sha, entry_sha,
            "подготовка теста не удалась — коммит роли не сдвинул голову")

        self.capture(fsm.cmd_advance, self.TASK)  # guard: нет маркера красноты

        # Задача остаётся в исходном состоянии с обычной причиной отказа
        # гейта — как и сейчас (SPEC, требование 2).
        self.assertEqual(
            store.get_task(conn, self.TASK)["state"], "tests_writing",
            "переход не должен был случиться — критерий приёмки не про "
            "продвижение FSM, а про отсутствие ложной эскалации")
        refusal = [r for r in store.task_steps(conn, self.TASK)
                  if r["action"] == "переход отклонён: трассируемость AC"]
        self.assertTrue(
            refusal, "обычная причина отказа гейта должна остаться в "
            "журнале как и раньше (SPEC, требование 2)")

        # fixed_sha перефиксирован на текущую голову ветки.
        self.assertEqual(
            store.get_task(conn, self.TASK)["fixed_sha"], committed_sha,
            "AC-1: fixed_sha обязан быть перефиксирован на текущую голову "
            "ветки после отклонённого перехода, если все новые коммиты — "
            "коммиты собственного шага задачи")

        # Журнал задачи несёт запись о перефиксации.
        refix = [r for r in store.task_steps(conn, self.TASK)
                if "перефиксирован" in r["detail"]
                or "перефиксирован" in r["action"]]
        self.assertTrue(
            refix, "AC-1: журнал задачи должен содержать запись о "
            "перефиксации sha после отклонённого перехода")
        refix_text = " ".join(f"{r['action']} {r['detail']}" for r in refix)
        self.assertIn("отклонённого перехода", refix_text)
        self.assertIn("коммиты шага", refix_text)

        # Эскалация «инцидент целостности» не порождена: следующий старт
        # шага (fixation.check_integrity, orchestrator/runner.py:172) не
        # видит расхождения.
        self.assertIsNone(
            fixation.check_integrity(conn, self.TASK),
            "AC-1: сценарий T069/T073 не должен порождать эскалацию "
            "«инцидент целостности» на следующем старте шага")


if __name__ == "__main__":
    unittest.main()
