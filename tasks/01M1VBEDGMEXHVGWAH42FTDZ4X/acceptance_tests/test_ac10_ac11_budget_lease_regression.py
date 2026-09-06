"""Приёмочные тесты 01M1VBEDGMEXHVGWAH42FTDZ4X — AC-10, AC-11: регресс-
замки требования 1 SPEC.md, дополняющие test_ac1_ac2_ac3_ac4_
budget_lease_hostname.py двумя КРАЙНИМИ случаями того же правила «свой
хост — не отказ, чужой хост — отказ»: AC-10 сверяет lease, принадлежащий
САМОЙ вызывающей сессии (session_id совпадает буквально, не только
hostname), AC-11 — мутационный дубль AC-4 на чужом hostname, проверяющий
не текст отказа (это уже делает AC-4), а то, что `budget` при отказе НЕ
успевает ни одной мутацией: ни `tasks.budget_usd`, ни записи журнала.

Красен до реализации: AC-11 сегодня уже проходит (`lease.acquire`
отказывает до тела `_cmd_budget` — сверено ниже), но AC-10 — нет: `own`
lease сегодня и так пропускается (`row["session_id"] == session_id` в
`orchestrator/lease.py`), однако пометка «во время шага <роль>» (AC-2),
которую AC-10 требует тем же прогоном, ещё не реализована — AC-10
покраснеет на ней же.
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutoCycleTest, insert_lease  # noqa: E402
from orchestrator import budget, config, store  # noqa: E402

OWN_SESSION = "operator-own-terminal"
FOREIGN_SESSION = "operator-third-terminal"
FOREIGN_HOST_OTHER = "yet-another-operator-host.invalid"


class OwnSessionLiveLeaseTest(AutoCycleTest):
    """AC-10: lease живой и принадлежит ТОЙ ЖЕ session_id, которой вызван
    `budget` — потолок меняется и журналируется пометкой «во время шага
    <роль>», тем же путём, что и AC-1/AC-2 (не отдельным «свой lease —
    особый случай», а тем же кодом, что видит просто «свой хост»)."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("review", budget_usd=15.0, spent_usd=2.0)
        insert_lease(store.db(), self.TASK, OWN_SESSION, socket.gethostname())

    def test_ac10_own_session_live_lease_changes_ceiling_and_journals(self):
        """Собственный live-lease не отличим по исходу от чужого lease
        того же хоста (AC-1) — потолок меняется, журнал несёт «во время
        шага reviewer» (роль состояния `review`).

        Ловит мутацию: пометка «во время шага <роль>» условна на «lease
        принадлежит НЕ вызывающей сессии» вместо «lease живой вообще» —
        для своей же сессии detail останется старым форматом без
        упоминания шага, и `assertIn` не найдёт «во время шага».
        """
        self.capture(budget.cmd_budget, self.TASK, "30", OWN_SESSION)

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 30.0)

        details = [d for _, a, d in self.journal_rows() if a == "бюджет изменён"]
        self.assertEqual(len(details), 1, details)
        self.assertIn("во время шага", details[0])
        self.assertIn("reviewer", details[0])


class ForeignHostRefusalMutatesNothingTest(AutoCycleTest):
    """AC-11: чужой hostname отказывает (AC-4) БЕЗ единой мутации — ни
    `tasks.budget_usd`, ни журнальной записи «бюджет изменён»: рубеж
    снят, только если ОТКАЗ полностью замещает тело команды, не просто
    печатает предупреждение поверх него."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=10.0, spent_usd=1.0)
        insert_lease(store.db(), self.TASK, FOREIGN_SESSION, FOREIGN_HOST_OTHER)

    def test_ac11_refusal_leaves_no_trace_of_a_ceiling_change(self):
        """Ни `budget_usd`, ни журнал не меняются при отказе чужого хоста
        — рубеж держит ВЕСЬ вызов, а не только текст сообщения.

        Ловит мутацию: рубеж AC-1 реализован «наоборот» (отказ печатается,
        но `_cmd_budget` всё равно вызывается телом `run_locked` до
        `sys.exit`, либо `on_refusal` не останавливает выполнение) — тест
        поймает лишнюю запись «бюджет изменён» или изменившийся
        `budget_usd`, даже если сам текст отказа (AC-4) не пострадал.
        """
        journalled_before = len(self.journal_rows())

        with self.assertRaises(SystemExit):
            self.capture(budget.cmd_budget, self.TASK, "40")

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 10.0)
        new_rows = self.journal_rows()[journalled_before:]
        self.assertFalse(
            any(a == "бюджет изменён" for _, a, _ in new_rows),
            f"запись «бюджет изменён» появилась несмотря на отказ: {new_rows}")


if __name__ == "__main__":
    import unittest
    unittest.main()
