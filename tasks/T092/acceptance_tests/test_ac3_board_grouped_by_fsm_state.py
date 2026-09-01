"""AC-3 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит борд
задач, сгруппированных по текущему состоянию FSM каждой задачи.

SPEC не фиксирует разметку борда (классы/теги) — только сам факт
группировки по состоянию. Тест поэтому не завязан на конкретные CSS-
классы утверждённого макета `tasks/T080/mockup.html` (`div.col.<state>`
+ `span.state-tag`), а проверяет свойство напрямую: рядом с меткой
состояния X в документе не должен всплывать идентификатор задачи,
которая на самом деле в состоянии Y (`_sandbox.label_chunks`) — то
есть таск на борде оказывается именно в СВОЁМ состоянии, не в чужом
и не размазан по всему документу без разбора.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest, label_chunks  # noqa: E402

STATE_A = "tests_writing"
STATE_B = "merge_gate"
STATE_C = "killed"


class BoardGroupedByStateTest(ReportSandboxTest):

    def setUp(self):
        super().setUp()
        # Заголовки НЕ содержат сами имена состояний подстрокой — иначе
        # заголовок задачи A сам создал бы ложную метку STATE_A/STATE_B/
        # STATE_C посреди текста, ломая разбиение label_chunks.
        self.task_a = self.mk_task("T001", "Первая задача-фикстура", STATE_A)
        self.task_b = self.mk_task("T002", "Вторая задача-фикстура", STATE_B)
        self.task_c = self.mk_task("T003", "Третья задача-фикстура", STATE_C)
        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac3_each_states_label_appears(self):
        for state in (STATE_A, STATE_B, STATE_C):
            self.assertIn(
                state, self.html,
                f"состояние {state} нигде не названо в отчёте")

    def test_ac3_each_task_id_appears(self):
        for task_id in (self.task_a, self.task_b, self.task_c):
            self.assertIn(task_id, self.html,
                          f"задача {task_id} не попала в отчёт")

    def test_ac3_tasks_grouped_under_their_own_state_not_a_wrong_one(self):
        by_task = {self.task_a: STATE_A, self.task_b: STATE_B,
                  self.task_c: STATE_C}
        chunks = label_chunks(self.html, (STATE_A, STATE_B, STATE_C))

        for label, text in chunks:
            for task_id, actual_state in by_task.items():
                if task_id in text and label != actual_state:
                    self.fail(
                        f"задача {task_id} (состояние {actual_state}) "
                        f"всплывает в блоке, помеченном {label}: "
                        f"...{text[:200]}...")


if __name__ == "__main__":
    unittest.main()
