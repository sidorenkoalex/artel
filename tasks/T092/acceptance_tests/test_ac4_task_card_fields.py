"""AC-4 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит для
каждой задачи карточку с полями: статус, бюджет и расход, число
итераций ревью, эскалации (если задача эскалирована).

Разметку карточки SPEC не фиксирует — тест проверяет присутствие
каждого поля РЯДОМ с идентификатором задачи (`_sandbox.all_scopes`),
не конкретный тег/класс. Числа фикстуры подобраны так, чтобы не
пересекаться друг с другом и с самим id задачи подстрокой (см.
докстринг `_sandbox.py`).

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest, all_scopes  # noqa: E402


class TaskCardFieldsTest(ReportSandboxTest):

    BUDGET = 741.0     # "741"
    SPENT = 62.0        # "62"
    REVIEW_ITERS = 9    # "9" — не пересекается с "741"/"62"/"001"

    def setUp(self):
        super().setUp()
        self.task = self.mk_task(
            "T001", "Обычная задача-фикстура", "in_dev",
            budget_usd=self.BUDGET, spent_usd=self.SPENT,
            review_iters=self.REVIEW_ITERS)
        self.escalated_task = self.mk_task(
            "T002", "Эскалированная задача-фикстура", "escalated",
            budget_usd=15.0, spent_usd=1.0, review_iters=1,
            escalated_from="review")
        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def _scopes_for(self, task_id):
        scopes = all_scopes(self.html, task_id)
        self.assertTrue(scopes, f"задача {task_id} не найдена в отчёте")
        return scopes

    def test_ac4_card_shows_status(self):
        scopes = self._scopes_for(self.task)
        self.assertTrue(
            any("in_dev" in s for s in scopes),
            "рядом с задачей нет её статуса (состояния)")

    def test_ac4_card_shows_budget(self):
        scopes = self._scopes_for(self.task)
        self.assertTrue(
            any(str(int(self.BUDGET)) in s for s in scopes),
            f"рядом с задачей нет её бюджета (${self.BUDGET:.2f})")

    def test_ac4_card_shows_spend(self):
        scopes = self._scopes_for(self.task)
        self.assertTrue(
            any(str(int(self.SPENT)) in s for s in scopes),
            f"рядом с задачей нет её расхода (${self.SPENT:.2f})")

    def test_ac4_card_shows_review_iteration_count(self):
        scopes = self._scopes_for(self.task)
        self.assertTrue(
            any(str(self.REVIEW_ITERS) in s for s in scopes),
            "рядом с задачей нет числа итераций ревью "
            f"({self.REVIEW_ITERS})")

    def test_ac4_escalated_task_card_mentions_escalation(self):
        scopes = self._scopes_for(self.escalated_task)
        self.assertTrue(
            any("эскал" in s.lower() for s in scopes),
            "эскалированная задача — в карточке нет упоминания эскалации")


if __name__ == "__main__":
    unittest.main()
