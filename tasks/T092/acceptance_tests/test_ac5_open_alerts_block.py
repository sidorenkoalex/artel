"""AC-5 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит блок
незакрытых алертов.

«Незакрытых» — неподтверждённых (`ack_ts IS NULL`, `store.open_alerts`,
тот же критерий, что использует `catalog.cmd_status`/`doctor.cmd_doctor`
для «триггеров»/несущего алерта в целом). Фикстура заводит один
открытый алерт и один закрытый (`store.ack_alert`) — открытый обязан
появиться в отчёте, закрытый — нет (иначе это не «блок незакрытых»,
а просто список всех алертов когда-либо заведённых).

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402
from orchestrator import store  # noqa: E402


class OpenAlertsBlockTest(ReportSandboxTest):

    OPEN_MESSAGE = "фикстура: конфликт подтяжки main (T092 AC-5, открытый)"
    ACKED_MESSAGE = "фикстура: инцидент закрыт Оператором (T092 AC-5)"

    def setUp(self):
        super().setUp()
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")

        self.open_id = self.mk_alert("incident", "test.ac5", self.OPEN_MESSAGE)

        self.acked_id = self.mk_alert(
            "incident", "test.ac5.acked", self.ACKED_MESSAGE)
        store.ack_alert(store.db(), self.acked_id, "operator",
                        "фикстура: подтверждено для проверки AC-5")

        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac5_open_alert_appears_in_report(self):
        self.assertIn(
            self.OPEN_MESSAGE, self.html,
            "незакрытый алерт отсутствует в отчёте")

    def test_ac5_acked_alert_is_not_shown_as_open(self):
        self.assertNotIn(
            self.ACKED_MESSAGE, self.html,
            "подтверждённый (закрытый) алерт показан как незакрытый")


if __name__ == "__main__":
    unittest.main()
