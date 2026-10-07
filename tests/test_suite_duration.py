"""Unit cases for full-suite duration observations."""

import json

from orchestrator import alerts, config, doctor, store
from tests.sandbox import TmpRootTest


class SuiteDurationSeriesTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, "T001", "Первый", "in_dev",
                          "task/t001", config.DEFAULT_TARGET, 25.0)
        store.insert_task(self.conn, "T002", "Второй", "in_dev",
                          "task/t002", "other", 25.0)

    def record(self, task: str, per_test: float | None) -> None:
        metric = {"seconds_per_test": per_test, "xdist_workers": 2,
                  "load_end_1": 1.0, "load_end_5": 2.0,
                  "top_processes": [{"pid": 10, "cpu_percent": 5.0,
                                     "name": "other"}]}
        store.journal(self.conn, task, "orchestrator", "прогон: время",
                      json.dumps(metric))

    def test_timeout_does_not_reset_calibration_or_mix_targets(self):
        """Ловит мутацию: таймаут обнуляет окно или записи другого target
        меняют медиану, из-за чего рост после восьми прогонов теряется."""
        for _ in range(8):
            self.record("T001", 0.1)
        self.record("T001", None)
        for _ in range(8):
            self.record("T002", 10.0)
        self.record("T001", 0.2)
        checks = doctor.check_suite_duration(self.conn)
        self.assertEqual({item.name: item.status for item in checks},
                         {f"suite-duration:{config.DEFAULT_TARGET}": "warn",
                          "suite-duration:other": "ok"})
        triggered = [row for row in alerts.open_alerts(self.conn, "trigger")
                     if row["source"] == "suite.duration"]
        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0]["target"], config.DEFAULT_TARGET)

    def test_exact_threshold_does_not_trigger(self):
        """Ловит мутацию: сравнение меняется с `>` на `>=` и поднимает
        сигнал ровно на границе допустимого роста времени на тест."""
        for _ in range(8):
            self.record("T001", 1.0)
        self.record("T001", 1.6)
        self.assertEqual(doctor.check_suite_duration(self.conn)[0].status, "ok")
