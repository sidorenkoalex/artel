"""Юнит-тесты новых функций tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md
(требование 3): алерт `kind=warning` на «diff не собран» ревью-пакета
итерации > 1, авто-подтверждение на следующем удачном сборе.

Сквозной сценарий (реальный `runner.cmd_run`, заводит/закрывает алерт по
факту сборки пакета) гоняет приёмочный тест задачи (`tasks/
01M1P9RJVYHTAC087J4B2CAR44/acceptance_tests/
test_ac6_diff_not_collected_raises_warning_alert.py`); здесь — сами новые
функции `alerts.py` в изоляции, тем же приёмом, что `tests/
test_stall_alerts.py` использует для `attention`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, store  # noqa: E402
from tests.sandbox import SchemaTmpRootTest  # noqa: E402

TASK = "T001"
OTHER_TASK = "T002"


class WarningKindTest(unittest.TestCase):

    def test_warning_is_a_registered_alert_kind(self):
        """Ловит мутацию: kind "warning" не добавлен в `alerts.KINDS`
        (или опечатан) — любой вызов `raise_alert(..., "warning", ...)`
        бросит `ValueError` раньше, чем дело дойдёт до алерта."""
        self.assertIn("warning", alerts.KINDS)


class RaiseDiffNotCollectedAlertTest(SchemaTmpRootTest):

    def test_raises_an_open_warning_alert_naming_the_task(self):
        """Первый вызов заводит открытый алерт `kind=warning` с задачей в
        `target` и в тексте сообщения.

        Ловит мутацию: функция передаёт в `raise_alert` не тот `kind`
        (например, оставляет "incident") или не передаёт `task_id` в
        `target` — фильтр `open_alerts(..., "warning")` не найдёт
        строку, либо `rows[0]["target"]` разойдётся с TASK.
        """
        opened = alerts.raise_diff_not_collected_alert(
            store.db(), TASK, "fatal: bad revision")

        self.assertTrue(opened)
        rows = store.open_alerts(store.db(), "warning")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target"], TASK)
        self.assertIn(TASK, rows[0]["message"])
        self.assertIn("fatal: bad revision", rows[0]["message"])

    def test_repeated_call_with_the_same_reason_does_not_duplicate(self):
        """Дедуп — существующий `alerts.raise_alert`, не переопределяется
        этой задачей: повторный вызов с той же причиной не плодит
        второй алерт.

        Ловит мутацию: функция перестанет опираться на дедуп
        `raise_alert` (например, позовёт `store.insert_alert` напрямую).
        """
        alerts.raise_diff_not_collected_alert(store.db(), TASK, "причина")

        opened_again = alerts.raise_diff_not_collected_alert(
            store.db(), TASK, "причина")

        self.assertFalse(opened_again)
        self.assertEqual(len(store.open_alerts(store.db(), "warning")), 1)


class CloseDiffNotCollectedAlertsTest(SchemaTmpRootTest):

    def test_closes_open_warning_alert_of_this_task(self):
        """Открытый warning-алерт этой задачи закрывается вызовом
        `close_diff_not_collected_alerts`.

        Ловит мутацию: функция перестанет звать `store.ack_alert` для
        найденной строки — алерт останется открытым после вызова.
        """
        alerts.raise_diff_not_collected_alert(store.db(), TASK, "причина")

        alerts.close_diff_not_collected_alerts(store.db(), TASK)

        self.assertEqual(store.open_alerts(store.db(), "warning"), [])

    def test_leaves_another_tasks_warning_alert_open(self):
        """Закрытие алертов TASK не трогает открытый warning-алерт другой
        задачи (OTHER_TASK).

        Ловит мутацию: фильтр `row["target"] == task_id` будет снят —
        закрытие TASK заодно закроет чужой алерт.
        """
        alerts.raise_diff_not_collected_alert(store.db(), TASK, "причина")
        alerts.raise_diff_not_collected_alert(store.db(), OTHER_TASK, "причина")

        alerts.close_diff_not_collected_alerts(store.db(), TASK)

        opened = store.open_alerts(store.db(), "warning")
        self.assertEqual([r["target"] for r in opened], [OTHER_TASK])

    def test_leaves_other_warning_sources_of_this_task_open(self):
        """Закрытие трогает только алерты этого источника
        (`DIFF_NOT_COLLECTED_SOURCE`) — чужой `kind=warning` той же
        задачи (гипотетический будущий источник) остаётся открытым.

        Ловит мутацию: фильтр по `row["source"]` будет снят — закрытие
        заодно закроет warning-алерт другого источника той же задачи.
        """
        alerts.raise_alert(store.db(), TASK, "warning", "другой-источник",
                           "другая причина")

        alerts.close_diff_not_collected_alerts(store.db(), TASK)

        self.assertEqual(len(store.open_alerts(store.db(), "warning")), 1)

    def test_no_open_alert_is_a_no_op(self):
        """Вызов без единого открытого алерта задачи не бросает
        исключение и не заводит побочных строк.

        Ловит мутацию: цикл по `open_alerts` внутри функции перестанет
        корректно обрабатывать пустой результат.
        """
        alerts.close_diff_not_collected_alerts(store.db(), TASK)

        self.assertEqual(store.open_alerts(store.db(), "warning"), [])


if __name__ == "__main__":
    unittest.main()
