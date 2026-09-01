"""AC-7 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит долю
задач, прошедших acceptance автогейтом (актор `autogate`) против
прошедших руками (актор `operator`), рассчитанную по журналу отдельно
за всю историю и за последние 10 задач.

Переход acceptance -> merge_gate в журнале — запись `actor` =
`autogate`/`operator`, `action` = `"state -> merge_gate"`
(`orchestrator/fsm.py`: `_maybe_autogate_acceptance` для автогейта,
ветка `elif state == "acceptance":` команды `approve` для ручного
прохода — оба зовут `store.set_state(..., "merge_gate", <actor>, ...)`,
а `store.set_state` журналирует именно этим действием). Тест
воспроизводит журнал напрямую этой же парой (actor, action), не
прогоняя реальный FSM — SPEC требование 11 явно требует, чтобы отчёт
читал журнал существующими функциями `store.py`, то есть по этим же
записям.

Фикстура: 20 задач прошли acceptance (9 автогейтом, 11 руками), плюс
3 задачи-«шум» acceptance вообще не проходили (не должны попасть в
знаменатель). Последние 10 по id (T011..T020) размечены отдельно (7
автогейтом, 3 руками) так, чтобы доля «за последние 10» ЗАМЕТНО
отличалась от доли «за всю историю» — иначе тест не отличил бы
корректный расчёт окна от расчёта, подставляющего вместо него
общую историю. Оба набора процентов — круглые числа (45/55 и 70/30),
подобранные так, чтобы не пересекаться друг с другом и с id задач
(T001..T023) подстрокой.

Разметку/формат чисел (доля vs проценты vs дробь) SPEC не фиксирует —
тест ищет посчитанные значения где угодно в документе, не в
конкретном месте разметки.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402


class AutogateVsOperatorRatioTest(ReportSandboxTest):

    def setUp(self):
        super().setUp()
        # Старые 10 (T001..T010) — исключены из "последних 10":
        # 2 автогейт, 8 руками.
        for i in range(1, 11):
            task_id = f"T{i:03d}"
            self.mk_task(task_id, f"Старая задача {task_id}", "done",
                        budget_usd=1.0)
            actor = "autogate" if i <= 2 else "operator"
            self.mk_step(task_id, actor, "state -> merge_gate")

        # Последние 10 (T011..T020) — 7 автогейт, 3 руками.
        for i in range(11, 21):
            task_id = f"T{i:03d}"
            self.mk_task(task_id, f"Свежая задача {task_id}", "done",
                        budget_usd=1.0)
            actor = "autogate" if i <= 17 else "operator"
            self.mk_step(task_id, actor, "state -> merge_gate")

        # Шум: acceptance ни разу не проходили — не входят в знаменатель.
        for i in range(21, 24):
            task_id = f"T{i:03d}"
            self.mk_task(task_id, f"Ещё не готова {task_id}", "in_dev",
                        budget_usd=1.0)

        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac7_actors_named(self):
        self.assertIn("autogate", self.html)
        self.assertIn("operator", self.html)

    def test_ac7_all_history_ratio_present(self):
        """9 автогейт / 11 руками из 20 = 45% / 55%."""
        self.assertIn("45", self.html,
                     "доля автогейта за всю историю (45%) не найдена")
        self.assertIn("55", self.html,
                     "доля ручного прохода за всю историю (55%) не найдена")

    def test_ac7_last_10_tasks_ratio_present_and_differs_from_history(self):
        """7 автогейт / 3 руками из последних 10 = 70% / 30% — заметно
        отличается от 45%/55% за всю историю, что и доказывает, что
        отчёт действительно считает окно отдельно, а не дублирует
        общую историю под другой подписью."""
        self.assertIn("70", self.html,
                     "доля автогейта за последние 10 задач (70%) не найдена")
        self.assertIn("30", self.html,
                     "доля ручного прохода за последние 10 задач (30%) "
                     "не найдена")


if __name__ == "__main__":
    unittest.main()
