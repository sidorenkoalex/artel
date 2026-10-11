"""AC-9 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит
$/задачу по done-задачам и суммарный расход программы.

Суммарный расход программы — та же цифра, что и `store.total_spent`
(ADR-0010: «Учёт полный и обязательный» — веха, не предохранитель),
т.е. сумма `spent_usd` ПО ВСЕМ задачам независимо от состояния.
$/задачу — только по задачам в состоянии `done`.

Фикстура: 3 done-задачи с расходом 50/250/300 (сумма 600, $/задачу —
600/3 = 200 — ни одно слагаемое само не равно 200, чтобы совпадение не
прошло тест без реального деления) и одна НЕ done-задача с расходом
999. Суммарный расход программы обязан включать все четыре (1599);
$/задачу по done обязан остаться 200, не съехать из-за 999 не-done
задачи.

Разметку/формат чисел SPEC не фиксирует — тест ищет посчитанные
значения где угодно в документе.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402


class CostPerTaskAndTotalSpendTest(ReportSandboxTest):

    def setUp(self):
        super().setUp()
        self.mk_task("T001", "Done-задача 1", "done",
                    budget_usd=1.0, spent_usd=50.0)
        self.mk_task("T002", "Done-задача 2", "done",
                    budget_usd=1.0, spent_usd=250.0)
        self.mk_task("T003", "Done-задача 3", "done",
                    budget_usd=1.0, spent_usd=300.0)
        self.mk_task("T004", "Не done-задача", "in_dev",
                    budget_usd=1.0, spent_usd=999.0)

        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac9_total_program_spend_includes_all_tasks(self):
        self.assertIn(
            "1599", self.html,
            "суммарный расход программы (50+250+300+999=1599) не найден")

    def test_ac9_cost_per_done_task_excludes_non_done(self):
        self.assertIn(
            "200", self.html,
            "$/задачу по done-задачам (600/3=200) не найден")


if __name__ == "__main__":
    unittest.main()
