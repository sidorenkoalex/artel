"""`orchestrator/rounds.py` — свойства подсчёта «кругов до кода», не
покрытые долгоживущим файлом задачи
(`tests/test_01m59dp2gv3san54m562cqy42r_rounds.py`): проект внешней задачи
как target оповещения и блок отчёта без задач окна.
"""
from orchestrator import config, report, rounds, store
from tests.sandbox import InitializedTmpRootTest


class RoundsRaiseOnceTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def test_alert_target_is_external_project_of_task(self):
        """Оповещение задачи внешнего проекта заведено на её проект.

        Ловит мутацию: target оповещения — константа `config.DEFAULT_TARGET`
        (или id задачи) вместо `store.task_target` — у задачи проекта
        `sled` target оповещения не `sled`.
        """
        store.insert_task(self.conn, "R0001", "Круги", "spec_gate",
                          "task/r0001-krugi", "sled", 25.0)
        for _ in range(config.ROUNDS_ALERT_SPEC_AUDITS):
            store.journal(self.conn, "R0001", "fsm", rounds.AUDIT_ACTION, "")
        self.assertTrue(rounds.raise_once(self.conn, "R0001"))
        found = [r for r in store.open_alerts(self.conn)
                 if r["source"] == rounds.ALERT_SOURCE]
        self.assertEqual([r["target"] for r in found], ["sled"])

    def test_report_block_without_window_tasks_says_so(self):
        """Без задач окна блок «Круги до кода» есть и говорит, что задач нет.

        Ловит мутацию: нет ветки «задач окна нет» — тело блока пустое (а
        при задачах пульта вне окна таблица итога по пустому набору роняет
        `statistics.median([])`).
        """
        html = report._rounds_html([], [])
        self.assertIn("нет", html)
        self.assertNotIn("<table", html)
