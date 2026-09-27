"""Планка AC-7: исчерпание бюджета журналируется и эскалирует задачу
независимо от того, была ли в этом пребывании в состоянии запись «бюджет:
предупреждение».

Зелёный с рождения: эскалация по исчерпанию бюджета существует и сегодня
(`orchestrator/budget.py::enforce_budget`), а AC-7 требует сохранить её
ровно такой после введения дедупликации — тест сохранения существующего
поведения, его дело покраснеть, если новое подавление заденет запись об
исчерпании.

Песочница — `tests.sandbox.SchemaConnTmpRootTest`, та же, что у
`test_budget_warning_dedup.py`: одно пребывание в состоянии по построению
(записей `state -> <состояние>` у задачи нет до самой эскалации).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import budget, config, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

from _util import (BUDGET_WARNING_ACTION, capture_value,  # noqa: E402
                   spend_levels)


class BudgetExhaustionTest(SchemaConnTmpRootTest):
    """Требование 5 SPEC: запись об ИСЧЕРПАНИИ бюджета и эскалация по нему
    подавлению не подлежат."""

    def make_task(self, task_id: str, budget_usd: float) -> None:
        store.insert_task(self.conn, task_id, "Шум журнала", "in_dev",
                          f"task/{task_id.lower()}-shum",
                          config.DEFAULT_TARGET, budget_usd)

    def escalation_details(self, task_id: str) -> list[str]:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? "
            "AND action='state -> escalated' ORDER BY id", (task_id,))]

    def journal_count(self, task_id: str, action: str) -> int:
        return len(self.conn.execute(
            "SELECT id FROM steps WHERE task_id=? AND action=?",
            (task_id, action)).fetchall())

    def test_ac7_exhaustion_escalates_with_and_without_a_prior_warning(self):
        """Исчерпание бюджета журналируется и эскалирует задачу и ПОСЛЕ
        записи «бюджет: предупреждение» в том же пребывании в состоянии, и
        без неё.

        Два прогона одного сценария на двух задачах: у первой порог
        `config.BUDGET_ALERT_RATIO` уже пересечён и предупреждение
        записано, у второй расход перепрыгивает потолок сразу, без
        промежуточного предупреждения. Исход обязан быть одинаковым:
        `enforce_budget` возвращает True, состояние — `escalated`, в
        журнале ровно одна запись перехода с причиной «бюджет исчерпан».

        Ловит мутацию: подавление повторов навешено на `enforce_budget`
        целиком (один ключ на всю функцию, а не на одну её ветку
        предупреждения) — у задачи с предупреждением запись об исчерпании
        оказалась бы подавлена вместе с ним, эскалация не состоялась бы, и
        задача осталась бы в `in_dev`.
        """
        budget_usd = config.DEFAULT_BUDGET_USD
        warned_spend = spend_levels(budget_usd, 1)[0]

        for task_id, before in (("T001", warned_spend), ("T002", 0.0)):
            with self.subTest(task=task_id):
                self.make_task(task_id, budget_usd)
                store.update_task(self.conn, task_id, spent_usd=before)
                if before:
                    capture_value(budget.enforce_budget, self.conn, task_id,
                                  "in_dev")
                    self.assertEqual(
                        self.journal_count(task_id, BUDGET_WARNING_ACTION), 1,
                        "фикстура: предупреждение в этом пребывании было")
                store.update_task(self.conn, task_id, spent_usd=budget_usd)

                escalated, _ = capture_value(budget.enforce_budget, self.conn,
                                             task_id, "in_dev")

                self.assertTrue(escalated)
                self.assertEqual(
                    store.get_task(self.conn, task_id)["state"], "escalated")
                details = self.escalation_details(task_id)
                self.assertEqual(len(details), 1, details)
                self.assertIn("бюджет исчерпан", details[0])


if __name__ == "__main__":
    unittest.main()
