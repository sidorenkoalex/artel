"""AC-2 (tasks/T049/SPEC.md): `doctor` поднимает алерт `kind=incident`,
если счётчик номеров target'а ниже наблюдаемого max.

Требование 3 SPEC называет область изменения буквально: «`doctor`
получает проверку «счётчик ≥ наблюдаемого max»» — по образцу уже
существующих точечных проверок `doctor.check_orphans`/
`doctor.check_backup_age`/`doctor.check_leases` (последняя — тоже новая
функция на момент написания её приёмочного теста, см.
tasks/T044/acceptance_tests/test_lease_readonly_and_doctor.py
`Ac6DoctorDetectsDeadPidLeaseTest`, тот же приём).

Тест зовёт `doctor.check_task_counters(conn)` напрямую, а не через
`doctor.all_checks()` — последняя тянет живой смоук CLI и сетевые
проверки forge, не имеющие отношения к этому критерию (тот же довод, что
у `tests/test_doctor.py::OrphansTest`).

Источник наблюдаемого max здесь — только каталог `tasks/T*` (самый
дешёвый из трёх источников требования 1, без настоящего git): критерию
AC-2 важен сам факт расхождения «счётчик < max», а не то, каким именно
источником max получен — это уже покрыто AC-1.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, config, doctor, store  # noqa: E402
from _sandbox import TmpRootTest, capture  # noqa: E402

OBSERVED_MAX = 10  # tasks/T010


class TaskCounterIncidentSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        (config.TASKS / "T010").mkdir(parents=True)

    def set_counter(self, next_number: int) -> None:
        conn = store.db()
        conn.execute("DELETE FROM task_counters WHERE target=?",
                     (config.DEFAULT_TARGET,))
        conn.execute(
            "INSERT INTO task_counters (target, next_number) VALUES (?,?)",
            (config.DEFAULT_TARGET, next_number))
        conn.commit()


class CounterBehindObservedMaxTest(TaskCounterIncidentSandbox):

    def test_ac2_counter_behind_observed_max_raises_an_incident_alert(self):
        self.set_counter(3)  # ниже наблюдаемого max (T010 -> 10)

        check = doctor.check_task_counters(store.db())

        self.assertEqual(check.status, "fail", check.detail)
        incidents = alerts.open_alerts(store.db(), "incident")
        self.assertTrue(
            incidents,
            "счётчик (3) ниже наблюдаемого max (10) не поднял incident-алерт")


class CounterAtOrAboveObservedMaxTest(TaskCounterIncidentSandbox):
    """Дословно требование 3: «счётчик ≥ наблюдаемого max» — здоровое
    состояние, не «строго больше» (это уже отдельная гарантия AC-1 про
    номер СОЗДАННОЙ задачи, не про сам счётчик)."""

    def test_ac2_counter_equal_to_observed_max_is_not_flagged(self):
        self.set_counter(OBSERVED_MAX)  # счётчик == наблюдаемый max

        check = doctor.check_task_counters(store.db())

        self.assertNotEqual(check.status, "fail", check.detail)
        incidents = alerts.open_alerts(store.db(), "incident")
        self.assertEqual(
            incidents, [],
            "счётчик, равный наблюдаемому max, ошибочно отмечен как "
            "коллизия — требование 3 явно допускает «≥», не только «>»")

    def test_ac2_counter_above_observed_max_is_not_flagged(self):
        self.set_counter(OBSERVED_MAX + 50)

        check = doctor.check_task_counters(store.db())

        self.assertNotEqual(check.status, "fail", check.detail)
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])


if __name__ == "__main__":
    unittest.main()
