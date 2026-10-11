"""Приёмочный тест T094 — AC-7 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-7: «doctor-сверка счётчика номеров задач при отсутствии новых
пронумерованных (Tnnn) задач сообщает информационный статус «счётчик не
движется», не блокируя и не алертуя пульт.»

Красен до реализации: сегодня `doctor.check_task_counters` (`orchestrator/
doctor.py`) при `next_number < observed_max` заводит именованный
incident-алерт (`doctor.task_counter`) и возвращает `Check(..., "fail",
...)` — ровно блокировку и алерт, которые критерий запрещает для этого
случая (требование 6: контур счётчика заморожен как legacy).

Сценарий: наблюдаемый мир несёт исторический `Tnnn` (каталог
`tasks/T00005/` — тот же источник, что уже сегодня читает
`coldstart._max_from_task_dirs`) старше счётчика, а НОВЫЕ пронумерованные
задачи с момента посева счётчика не заводились (ни одного вызова
`cmd_new` для `Tnnn` в этой песочнице) — счётчик «не движется» в
буквальном смысле критерия.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, config, doctor, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class Ac7DoctorCounterInformationalTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        (config.TASKS / "T00005").mkdir(parents=True)

    def test_ac7_no_new_numbered_tasks_reports_informational_not_moving(self):
        conn = store.db()

        check = doctor.check_task_counters(conn)

        self.assertNotEqual(
            check.status, "fail",
            f"счётчик номеров не должен блокировать doctor при "
            f"отсутствии новых Tnnn-задач (AC-7): {check}")
        self.assertIn(
            "не движется", check.detail,
            f"detail обязан нести информационную формулировку «счётчик "
            f"не движется» (AC-7): {check.detail!r}")

    def test_ac7_no_new_numbered_tasks_does_not_raise_an_alert(self):
        conn = store.db()

        doctor.check_task_counters(conn)

        open_incidents = [
            a for a in alerts.open_alerts(conn, "incident")
            if a["source"] == "doctor.task_counter"
        ]
        self.assertEqual(
            open_incidents, [],
            f"doctor не имеет права алертовать пульт по замороженному "
            f"счётчику при отсутствии новых Tnnn-задач (AC-7): "
            f"{open_incidents}")


if __name__ == "__main__":
    unittest.main()
