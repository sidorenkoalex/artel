"""AC-4 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «Таймаут шага без единого usage-события (ни
финального, ни промежуточного): поведение не изменилось относительно
механики T040 — в журнал записана строка «стоимость шага неизвестна»,
открыт алерт kind=incident source=spend.unknown_cost, ни spent_usd, ни
spent_estimate_usd не изменились.»

Роль сценария — `developer`: этот сценарий (`saw_usage_event=False`) не
участвует в конфликте, эскалированном в test_ac1_token_rate_table.py —
курс роли здесь вообще не может быть применён (нет ни одного счётчика
токенов, применять курс не к чему), так что независимо от того, получит
ли `developer` курс в таблице требования 1, эта ветка обязана вести себя
одинаково. Тот же вызов, что и залоченный `tests/test_step_cost.py:337`
(`ChargeMissingResultTest.test_unrecoverable_cost_journals_and_raises_an_alert`)
— здесь пересобран как приёмочный тест, а не заимствован напрямую
(приёмочные тесты не импортируют `tests/`).

Красен до реализации: сценарий `saw_usage_event=False` сам по себе не
меняется (требование 4), но `test_ac4_timeout_without_any_usage_event_
touches_neither_column` читает ещё не существующую колонку
`tasks.spent_estimate_usd` (появится миграцией `orchestrator/store.py`
только вместе с требованием 1) — до неё `sqlite3.Row.__getitem__`
бросает `IndexError: No item with that key` на
`row["spent_estimate_usd"]`, а не тавтологично проходит.
`test_ac4_timeout_without_any_usage_event_raises_the_incident_alert`
уже проходит сегодня «случайно» — он проверяет только алерт
`kind=incident source=spend.unknown_cost`, часть поведения, которую
требование 4 явно НЕ меняет; оставлен как часть одного связного
сценария AC-4, не как отдельная приёмка.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import spend, store  # noqa: E402
from _sandbox import CostTmpRootTest  # noqa: E402


class NoUsageEventsUnchangedTest(CostTmpRootTest):

    def unknown_cost_alerts(self) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source='spend.unknown_cost'").fetchall()

    def test_ac4_timeout_without_any_usage_event_touches_neither_column(self):
        """Таймаут без единого usage-события (ни финального, ни
        промежуточного) не трогает ни `spent_usd`, ни
        `spent_estimate_usd`, и оставляет в журнале «стоимость шага
        неизвестна».

        Ловит мутацию: требование 3 (верхняя оценка) реализовано без
        ветвления по `saw_usage_event` — оценка добавится и здесь тоже,
        `spent_estimate_usd` перестанет быть 0.0, тест покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "developer", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens=0, saw_usage_event=False)

        row = self.task_row()
        self.assertEqual(row["spent_usd"], 0.0)
        self.assertEqual(row["spent_estimate_usd"] or 0.0, 0.0)
        detail = self.journal_rows()[-1][2]
        self.assertIn("стоимость шага неизвестна", detail)

    def test_ac4_timeout_without_any_usage_event_raises_the_incident_alert(self):
        """Тот же сценарий заводит ровно один алерт
        `kind=incident source=spend.unknown_cost`, как и до этой задачи.

        Ловит мутацию: `kind` для этого случая переключён на
        `threshold` (перепутан с новой веткой AC-3) — фильтр по
        `kind='incident'` не найдёт строку, тест покраснеет.
        """
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "developer", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens=0, saw_usage_event=False)

        found = self.unknown_cost_alerts()
        self.assertEqual(len(found), 1)
        self.assertIn(self.TASK, found[0]["message"])
